@echo off
rem Stops the API and web app (ports 8010 and 3100) and the database containers. Your data is kept.
setlocal
cd /d "%~dp0"
echo Stopping the API and the web app...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-dev.ps1"
echo Stopping the database and search containers (data stays in the Docker volume)...
docker compose --profile tools stop >nul 2>nul
echo Done. Run start.bat to start again.
exit /b 0
