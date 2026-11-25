@echo off
rem Starts CareerPilot on this PC: database, schema update, API (port 8010) and web app (port 3100).
rem Safe to run again: anything already running is left alone. Stop everything with stop.bat.
setlocal
cd /d "%~dp0"
title CareerPilot launcher

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is not installed or not on PATH. Install Docker Desktop, then run start.bat again.
  exit /b 1
)
docker info >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop is not running. Start it, wait until it says "Running", then run start.bat again.
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 is not on PATH. Install it from python.org and tick "Add python.exe to PATH".
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js 22 is not installed. Install it from nodejs.org, then run start.bat again.
  exit /b 1
)
python -m uv --version >nul 2>nul
if errorlevel 1 (
  echo The uv tool is missing. Run:  python -m pip install uv   then run start.bat again.
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example. Open it to add your keys later.
)

echo [1/5] Starting the database...
docker compose up -d postgres
if errorlevel 1 goto :fail
rem The search service is optional (used for interview research and pay lookups).
docker compose --profile tools up -d searxng >nul 2>nul

echo [2/5] Waiting for the database to be ready...
set /a tries=0
:waitdb
set "health="
for /f "delims=" %%H in ('docker inspect -f "{{.State.Health.Status}}" careerpilot-postgres-1 2^>nul') do set "health=%%H"
if "%health%"=="healthy" goto :dbready
set /a tries+=1
if %tries% geq 30 (
  echo The database did not become ready. Run: docker compose logs postgres
  goto :fail
)
timeout /t 2 /nobreak >nul
goto :waitdb
:dbready

echo [3/5] Installing what is missing (first run only)...
if not exist "apps\api\.venv" (
  pushd apps\api
  python -m uv sync
  if errorlevel 1 ( popd & goto :fail )
  popd
)
if not exist "apps\web\node_modules" (
  pushd apps\web
  call npm install
  if errorlevel 1 ( popd & goto :fail )
  popd
)

echo [4/5] Bringing the database schema up to date...
pushd apps\api
python -m uv run alembic upgrade head
if errorlevel 1 ( popd & goto :fail )
popd

echo [5/5] Starting the API and the web app in their own windows...
netstat -ano | findstr /R /C:":8010 .*LISTENING" >nul
if errorlevel 1 (
  start "CareerPilot API (port 8010)" /d "%~dp0apps\api" cmd /k python -m uv run uvicorn careerpilot.main:app_factory --factory --reload --port 8010
) else (
  echo   API is already running on port 8010.
)
netstat -ano | findstr /R /C:":3100 .*LISTENING" >nul
if errorlevel 1 (
  start "CareerPilot Web (port 3100)" /d "%~dp0apps\web" cmd /k npm run dev
) else (
  echo   Web app is already running on port 3100.
)

echo Waiting for the web app to answer (the first start compiles for a minute)...
set /a tries=0
:waitweb
curl -s -o nul -m 3 http://localhost:3100/login
if not errorlevel 1 goto :webready
set /a tries+=1
if %tries% geq 60 (
  echo The web app did not answer in 3 minutes. Look at the "CareerPilot Web" window for the error.
  goto :fail
)
timeout /t 3 /nobreak >nul
goto :waitweb
:webready

set "users=0"
for /f "delims=" %%U in ('docker exec careerpilot-postgres-1 psql -U careerpilot -d careerpilot -tAc "select count(*) from users" 2^>nul') do set "users=%%U"
echo.
echo CareerPilot is running:  http://localhost:3100
if "%users%"=="0" (
  echo.
  echo There is no user yet. Create yours once ^(it asks for a password of 12+ characters^):
  echo     create-user.bat you@example.com
) else (
  start "" http://localhost:3100
)
echo.
echo To stop everything: stop.bat     To see what is running: status.bat
exit /b 0

:fail
echo.
echo Start-up stopped because of the error above.
exit /b 1
