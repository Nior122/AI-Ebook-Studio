@echo off
cd /d "%~dp0"

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Starting backend on port 8765...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload --log-level info
pause