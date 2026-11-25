@echo off
rem Creates your login (once). Usage: create-user.bat you@example.com
rem Forgot the password later? Run reset-password.bat you@example.com
setlocal
cd /d "%~dp0apps\api"
if "%~1"=="" (
  echo Usage: create-user.bat you@example.com
  exit /b 1
)
python -m uv run python -m careerpilot.cli create-user --email %1
