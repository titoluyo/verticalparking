@echo off
REM Quick monitor script for Windows
REM Uses venv if available, otherwise uses system Python

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" "%SCRIPT_DIR%monitor.py"
) else (
    python "%SCRIPT_DIR%monitor.py"
)
pause

