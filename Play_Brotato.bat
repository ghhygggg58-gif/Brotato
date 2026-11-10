@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY_CMD="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    echo [Brotato Python] Python 3.11+ was not found on your PATH.
    echo Please install Python from https://www.python.org/downloads/ and check "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [Brotato Python] First-time setup: creating .venv and installing game libraries...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install "pygame-ce>=2.5.0" "numpy>=1.26.0"
    if errorlevel 1 (
        echo Failed to install required packages.
        pause
        exit /b 1
    )
)

echo [Brotato Python] Launching game...
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 (
    echo.
    echo Game exited with an error. Press any key to close...
    pause >nul
)
