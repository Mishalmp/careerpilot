@echo off
rem Sets a new password and signs every session out. Usage: reset-password.bat you@example.com
setlocal
cd /d "%~dp0apps\api"
if "%~1"=="" (
  echo Usage: reset-password.bat you@example.com
  exit /b 1
)
python -m uv run python -m careerpilot.cli reset-password --email %1
