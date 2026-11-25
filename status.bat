@echo off
rem Shows what is running: web app, API, database, search service, and the API's own health checks.
setlocal
cd /d "%~dp0"
echo.
for %%P in (3100 8010 5433 8080) do (
  netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul
  if errorlevel 1 ( echo   port %%P : not running ) else ( echo   port %%P : running )
)
echo   (3100 = web app, 8010 = API, 5433 = database, 8080 = search service, optional)
echo.
echo API health:
curl -s -m 3 http://localhost:8010/healthz
echo.
curl -s -m 5 http://localhost:8010/readyz
echo.
echo.
echo Containers:
docker ps --filter "name=careerpilot" --format "  {{.Names}}  {{.Status}}"
exit /b 0
