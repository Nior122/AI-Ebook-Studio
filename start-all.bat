@echo off
echo Starting AI Ebook Studio - Backend and Frontend...
echo ================================================
echo Backend will run on http://localhost:8765
echo Frontend will run on http://localhost:3000
echo ================================================
echo.

echo Starting Backend...
start "AI Ebook Studio - Backend" cmd /c "cd /d \"%~dp0backend\" && call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload --log-level info"

timeout /t 3 /nobreak >nul

echo Starting Frontend...
start "AI Ebook Studio - Frontend" cmd /c "cd /d \"%~dp0frontend\" && npm run dev"

echo.
echo Both services are starting in separate windows.
echo Backend: http://localhost:8765
echo Frontend: http://localhost:3000
pause