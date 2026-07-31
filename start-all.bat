@echo off
set ROOT=%~dp0
set BACKEND_NEW=%ROOT%backend\start_backend.bat
set FRONTEND_NEW=%ROOT%frontend\start_frontend.bat

echo Starting AI Ebook Studio...
start "AI Ebook Studio - Backend" /min cmd /k "%BACKEND_NEW%"
timeout /t 3 /nobreak >nul
start "AI Ebook Studio - Frontend" /min cmd /k "%FRONTEND_NEW%"
echo.
echo Backend  : http://localhost:8765
echo Frontend : http://localhost:3000
timeout /t 5 >nul
exit