from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import json
import uuid
import time
account_found = False
unique_id = "null" # fetch from other code
app = FastAPI()
existing = Jinja2Templates(directory="existing")
newuser = Jinja2Templates(directory="new")
"""
@app.get("/", response_class=HTMLResponse)
async def identify(request: Request):
    # identification page goes here
    global account_found, unique_id
    return existing.TemplateResponse("recognition.html", {"request": request})
"""
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    global account_found, unique_id, nm, ag, clg, mon, yr
    if account_found: 
        with open("data.json", "r") as file:
            data = json.load(file)
        for item in data:
            if item.get("id") == unique_id:
                nm = item.get("name")
                ag = item.get("age")
                clg = item.get("college")
                mon = item.get("month")
                yr = item.get("year")
        return existing.TemplateResponse("account.html", {"request": request, "name": nm, "age": ag, "college": clg, "month": mon, "year": yr})
    else:
        return RedirectResponse(url="/signup")

@app.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    if account_found:
        return RedirectResponse(url="/", status_code=303)
    return newuser.TemplateResponse("newuser.html", {"request": request})

@app.post("/submit", response_class=HTMLResponse)
async def submit_data(name: str = Form(...), age: str = Form(...), college: str = Form(...), month: str = Form(...), year: str = Form(...)):
    global account_found, unique_id
    unique_id = str(uuid.uuid4())
    new_data = {"id": unique_id, "name": name, "age": age, "college": college, "month": month, "year": year}
    try:
        with open("data.json", "r") as file:
            existing_data = json.load(file)
    except:
        existing_data = []
    existing_data.append(new_data)
    with open("data.json", "w") as file:
        json.dump(existing_data, file, indent=4)
    account_found = True 
    return RedirectResponse(url="/", status_code=303)

@app.post("/redirect_exit", response_class=HTMLResponse)
async def signout(request: Request):
    global account_found, unique_id
    account_found = False
    unique_id = "null"
    return RedirectResponse(url="/", status_code=303)

@app.post("/account-settings", response_class=HTMLResponse)
async def settings(request: Request):
    global unique_id
    with open("data.json", "r") as file:
        data = json.load(file)
    for item in data:
        if item.get("id") == unique_id:
            nm = item.get("name")
            ag = item.get("age")
            clg = item.get("college")
            mon = item.get("month")
            yr = item.get("year")
            id = item.get("id")

    return existing.TemplateResponse("account_settings.html", {"request": request, "id": id, "name": nm, "age": ag, "college": clg, "month": mon, "year": yr})
@app.post("/configure", response_class=HTMLResponse)
async def configure(name: str = Form(...), age: str = Form(...), college: str = Form(...), month: str = Form(...), year: str = Form(...)):
    global unique_id, account_found
    with open("data.json", "r") as file:
        existing_data = json.load(file)
    with open("data.json", "w") as file:
        existing_data = [x for x in existing_data if x.get("id") != unique_id]
    new_data = {"id": unique_id, "name": name, "age": age, "college": college, "month": month, "year": year}
    existing_data.append(new_data)
    with open("data.json", "w") as file:
        json.dump(existing_data, file, indent=4)
    return RedirectResponse(url="/", status_code=303)

@app.post("/cancel-configure", response_class=HTMLResponse)
async def cancel_configure(request: Request):
    return RedirectResponse(url="/", status_code=303)

    



"""
@app.post("/signin", response_class=HTMLResponse)
async def signin(request: Request):
    global account_found, unique_id # if face found, both variables must be updated by other program and communicated here
    # get unique id from other program here
    return RedirectResponse(url="/")
"""







