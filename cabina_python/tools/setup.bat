@echo off
REM Setup script for Windows - Creates venv and installs dependencies
echo ========================================
echo ESP32-S3 Development Tools Setup
echo ========================================
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "TOOLS_DIR=%SCRIPT_DIR%"
set "VENV_DIR=%TOOLS_DIR%.venv"

echo [1/3] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://www.python.org/
    pause
    exit /b 1
)
python --version
echo.

echo [2/3] Creating virtual environment...
if exist "%VENV_DIR%" (
    echo Virtual environment already exists at: %VENV_DIR%
    echo Skipping creation...
) else (
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
)
echo.

echo [3/3] Installing dependencies...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

python -m pip install --upgrade pip >nul 2>&1
pip install -r "%TOOLS_DIR%requirements.txt"
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To use the tools, activate the virtual environment:
echo   %VENV_DIR%\Scripts\activate.bat
echo.
echo Then run:
echo   python sync_to_esp32.py
echo   python monitor.py
echo.
echo Or use the batch files:
echo   sync.bat
echo   monitor.bat
echo.
pause

