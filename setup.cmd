@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  where py >nul 2>nul
  if not errorlevel 1 (py -3 -m venv .venv) else (python -m venv .venv)
)
if not exist .venv\Scripts\python.exe goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error
if not exist .env copy .env.example .env >nul
.venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 goto :error
.venv\Scripts\python.exe manage.py seed_demo
if errorlevel 1 goto :error
echo.
echo Готово. Заполните .env для ИИ-подбора. Запуск: run_server.cmd и run_desktop.cmd.
pause
exit /b 0
:error
echo.
echo Установка не завершена. Проверьте Python 3.11 или новее и сообщения выше.
pause
exit /b 1
