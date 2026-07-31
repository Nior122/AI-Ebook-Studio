@echo off
echo Starting AI Ebook Studio Backend...
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set OPENROUTER_API_KEY=sk-or-v1-58781c23693152c8a1656c0068c6d0db612142d621da51b81ff81a7082f528e
set AI_DEFAULT_PROVIDER=openrouter
set AI_DEFAULT_MODEL=openrouter/openai/gpt-4o-mini
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload --log-level info
pause