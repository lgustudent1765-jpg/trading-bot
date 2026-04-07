@echo off
title Algo-Trade Startup
echo ============================================
echo   Algo-Trade Paper Trading System
echo ============================================
echo.

REM ---- Check Python is available ----
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM ---- Check Node is available ----
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Install Node.js from https://nodejs.org
    pause
    exit /b 1
)

REM ---- Setup Python virtual environment if not present ----
if not exist ".venv\Scripts\activate.bat" (
    echo Setting up Python environment (first run only)...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt -q
    echo Python environment ready.
) else (
    call .venv\Scripts\activate.bat
)

REM ---- Copy config files if not present ----
if not exist ".env" (
    echo Creating .env from template...
    copy .env.template .env >nul
)
if not exist "config.yaml" (
    echo Creating config.yaml from template...
    copy config.yaml.template config.yaml >nul
)

REM ---- Create data/logs directories ----
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo.
echo Starting backend (paper trade mode)...
start "Algo-Trade Backend" cmd /k "title Algo-Trade Backend && cd /d "%~dp0" && call .venv\Scripts\activate.bat && python -m src.cli.main --mode paper"

echo Waiting for backend to initialise...
timeout /t 4 /nobreak >nul

echo Starting frontend dashboard...
start "Algo-Trade Frontend" cmd /k "title Algo-Trade Frontend && cd /d "%~dp0frontend" && npm install --silent 2>nul && npm run dev"

echo.
echo ============================================
echo   Both services are starting up.
echo.
echo   Backend API:  http://localhost:8080
echo   Dashboard:    http://localhost:3000
echo.
echo   Wait ~15 seconds, then open your browser
echo   to http://localhost:3000
echo ============================================
echo.
echo Close either terminal window to stop that service.
pause
