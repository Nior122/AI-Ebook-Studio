@echo off
cd /d "%~dp0"

echo Starting frontend on port 3000...
call npm run dev
pause