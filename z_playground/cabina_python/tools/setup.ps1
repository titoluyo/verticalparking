# Setup script for Windows PowerShell - Creates venv and installs dependencies
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ESP32-S3 Development Tools Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get the directory where this script is located
$SCRIPT_DIR = $PSScriptRoot
$TOOLS_DIR = $SCRIPT_DIR
$VENV_DIR = Join-Path $TOOLS_DIR ".venv"

Write-Host "[1/3] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found"
    }
    Write-Host $pythonVersion -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.7+ from https://www.python.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "[2/3] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path $VENV_DIR) {
    Write-Host "Virtual environment already exists at: $VENV_DIR" -ForegroundColor Gray
    Write-Host "Skipping creation..." -ForegroundColor Gray
} else {
    try {
        python -m venv $VENV_DIR
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create venv"
        }
        Write-Host "Virtual environment created successfully!" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Host ""

Write-Host "[3/3] Installing dependencies..." -ForegroundColor Yellow
$activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Host "ERROR: Failed to find activation script" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate the virtual environment
& $activateScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

try {
    python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
    pip install -r (Join-Path $TOOLS_DIR "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install dependencies"
    }
} catch {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To use the tools, activate the virtual environment:" -ForegroundColor Yellow
Write-Host "  $VENV_DIR\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Then run:" -ForegroundColor Yellow
Write-Host "  python sync_to_esp32.py" -ForegroundColor White
Write-Host "  python monitor.py" -ForegroundColor White
Write-Host ""
Write-Host "Or use the scripts:" -ForegroundColor Yellow
Write-Host "  .\sync.ps1" -ForegroundColor White
Write-Host "  .\monitor.ps1" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"

