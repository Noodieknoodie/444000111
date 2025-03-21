@echo off
cd /d "%~dp0backend"
call env\Scripts\activate
set PYTHONPATH=%cd%
python -m uvicorn main:app --reload || python -m uvicorn main:app --reload --port 6069
pause
