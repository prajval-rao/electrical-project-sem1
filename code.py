from fastapi import FastAPI, Request, WebSocket, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import json
import uuid
import time
import threading
import uvicorn
import cv2
import face_recognition
import numpy as np
import pickle
import serial
import asyncio

current_id = None
current_name = None
current_mood = None
latest_enc = None
LAST_FRAME_TIME = 0

ESP32_STREAM = "http://192.168.1.14:81/stream"
SERIAL_PORT = "COM5"
BAUD = 9600
ENC_FILE = "encodings.pickle"
TOLERANCE = 0.45
SCALE = 0.25
FRAME_INTERVAL = 0.05

print("Opening serial...")
arduino = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
time.sleep(2)
print("Serial connected")

try:
    with open(ENC_FILE, "rb") as f:
        data = pickle.load(f)
        known_enc = data["encodings"]
        known_names = data["names"]
        known_ids = data["ids"]
except:
    known_enc, known_names, known_ids = [], [], []

print("Connecting to ESP32 stream...")
cap = cv2.VideoCapture(ESP32_STREAM, cv2.CAP_FFMPEG)
time.sleep(2)
if not cap.isOpened():
    print("❌ Failed to open ESP32 stream")
    exit()
print("✅ Stream opened")

cv2.namedWindow("Pico Brain", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Pico Brain", 640, 480)

existing = Jinja2Templates(directory="existing")
newuser = Jinja2Templates(directory="new")

def set_mood(m):
    global current_mood
    if m != current_mood:
        arduino.write(f"MOOD,{m}\n".encode())
        current_mood = m

def register_face(enc, name):
    if enc is None or not name:
        return None, None
    uid = str(uuid.uuid4())
    known_enc.append(enc)
    known_names.append(name)
    known_ids.append(uid)
    with open(ENC_FILE, "wb") as f:
        pickle.dump({"encodings": known_enc, "names": known_names, "ids": known_ids}, f)
    print(f"[INFO] Registered {name}")
    return uid, name

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    global current_id
    if current_id not in known_ids:
        return RedirectResponse(url="/signup")

    index = known_ids.index(current_id)
    with open("data.json", "r") as file:
        data = json.load(file)
    for item in data:
        if item.get("id") == current_id:
            nm = known_names[index]
            ag = item.get("age")
            clg = item.get("college")
            mon = item.get("month")
            yr = item.get("year")
    return existing.TemplateResponse("account.html", {
        "request": request,
        "name": nm,
        "age": ag,
        "college": clg,
        "month": mon,
        "year": yr
        })

@app.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    return newuser.TemplateResponse("newuser.html", {"request": request})

@app.post("/submit", response_class=HTMLResponse)
async def submit_data(
    age: str = Form(...),
    college: str = Form(...),
    month: str = Form(...),
    year: str = Form(...)
    ):
    global latest_enc, current_id, current_name

    if latest_enc is None:
        return RedirectResponse(url="/signup", status_code=303)

    current_id, current_name = register_face(latest_enc, current_name)
    latest_enc = None

    with open("currentuser.txt", "w") as f:
        f.write(current_name)

    new_data = {
        "id": current_id,
        "name": current_name,
        "age": age,
        "college": college,
        "month": month,
        "year": year
    }
    try:
        with open("data.json", "r") as file:
            existing_data = json.load(file)
    except FileNotFoundError:
        existing_data = []

    existing_data.append(new_data)
    with open("data.json", "w") as file:
        json.dump(existing_data, file, indent=4)

    return RedirectResponse(url="/", status_code=303)

@app.websocket("/ws/signup")
async def ws_signup(ws: WebSocket):
    await ws.accept()
    while True:
        await ws.send_json({"id": current_id})
        await asyncio.sleep(0.5)

@app.post("/redirect_exit", response_class=HTMLResponse)
async def signout(request: Request):
    global current_name, current_id
    current_name = "Unknown"
    current_id = "null"
    return RedirectResponse(url="/", status_code=303)

@app.post("/account-settings", response_class=HTMLResponse)
async def settings(request: Request):
    # no login check needed, user is already “logged in”
    with open("data.json", "r") as file:
        data = json.load(file)
    user_data = next((item for item in data if item.get("id") == current_id), None)
    if user_data is None:
        return RedirectResponse(url="/signup")
    return existing.TemplateResponse("account_settings.html", {
        "request": request,
        "id": current_id,
        "name": user_data.get("name"),
        "age": user_data.get("age"),
        "college": user_data.get("college"),
        "month": user_data.get("month"),
        "year": user_data.get("year")
    })

@app.post("/configure", response_class=HTMLResponse)
async def configure(name: str = Form(...), age: str = Form(...), college: str = Form(...), month: str = Form(...), year: str = Form(...)):
    # update user data directly, no login check
    with open("data.json", "r") as file:
        existing_data = json.load(file)
    existing_data = [x for x in existing_data if x.get("id") != current_id]
    new_data = {"id": current_id, "name": name, "age": age, "college": college, "month": month, "year": year}
    existing_data.append(new_data)
    with open("data.json", "w") as file:
        json.dump(existing_data, file, indent=4)
    current_name = name
    return RedirectResponse(url="/", status_code=303)

@app.post("/cancel-configure", response_class=HTMLResponse)
async def cancel_configure(request: Request):
    return RedirectResponse(url="/", status_code=303)

fail_count = 0
def face_loop():
    global LAST_FRAME_TIME, current_id, current_name, fail_count, latest_enc
    try:
        while True:
            now = time.time()
            if now - LAST_FRAME_TIME < FRAME_INTERVAL:
                time.sleep(0.01)
                continue
            LAST_FRAME_TIME = now

            ret, frame = cap.read()
            if not ret or frame is None:
                fail_count += 1
                if fail_count % 30 == 0:
                    print("⚠️ Dropped frames")
                time.sleep(0.01)
                continue
            fail_count = 0

            h, w = frame.shape[:2]
            cx = w // 2

            small = cv2.resize(frame, (0,0), fx=SCALE, fy=SCALE)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

            boxes = face_recognition.face_locations(rgb, model="hog")
            encs = face_recognition.face_encodings(rgb, boxes)

            if not encs:
                set_mood("IDLE")
                arduino.write(b"CENTER\n")
                current_name = None
                current_id = None
            else:
                enc = encs[0]
                current_name = "Unknown"
                if known_enc:
                    d = face_recognition.face_distance(known_enc, enc)
                    i = np.argmin(d)
                    if d[i] < TOLERANCE:
                        current_name = known_names[i]
                        current_id = known_ids[i]

                top, right, bottom, left = boxes[0]
                left = int(left / SCALE)
                right = int(right / SCALE)
                fx = (left + right) // 2
                dx = fx - cx

                if current_name == "Unknown":
                    latest_enc = enc
                    set_mood("ALERT")
                else:
                    set_mood("FRIENDLY")

                arduino.write(f"TRACK,{dx}\n".encode())
                color = (0,255,0) if current_name != "Unknown" else (0,0,255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, current_name, (left, top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            cv2.imshow("Pico Brain", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        arduino.close()
        cv2.destroyAllWindows()

face_thread = threading.Thread(target=face_loop, daemon=True)
face_thread.start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
