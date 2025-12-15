@echo off
cd /d %~dp0
start "" cmd /c "uvicorn main:app --reload"
timeout /t 5 >nul
start "" http://127.0.0.1:8000/signup