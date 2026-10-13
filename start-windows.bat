@echo off
setlocal
cd /d "%~dp0"

if not exist "backend_venv\Scripts\python.exe" (
    echo Backend belum terpasang.
    echo Jalankan dulu:
    echo py -m venv backend_venv
    echo backend_venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    pause
    exit /b 1
)

if not exist "backend\.env" (
    echo backend\.env belum ada. Bot akan meminta Telegram token.
)

start "Cheat Clip Pro Backend" cmd /k "cd /d "%~dp0" && backend_venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
start "Cheat Clip Pro Bot" cmd /k "cd /d "%~dp0" && set PYTHONPATH=%~dp0&& backend_venv\Scripts\python.exe -m backend.bot"

echo Backend dan bot sedang dijalankan.
