@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Сначала выполните setup.cmd.
  pause
  exit /b 1
)
echo Магазин: http://127.0.0.1:8000/
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
pause
