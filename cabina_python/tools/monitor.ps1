# Quick monitor script for Windows PowerShell
# Uses venv if available, otherwise uses system Python

$SCRIPT_DIR = $PSScriptRoot
$VENV_PYTHON = Join-Path $SCRIPT_DIR ".venv\Scripts\python.exe"
$MONITOR_SCRIPT = Join-Path $SCRIPT_DIR "monitor.py"

if (Test-Path $VENV_PYTHON) {
    & $VENV_PYTHON $MONITOR_SCRIPT
} else {
    python $MONITOR_SCRIPT
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nMonitor failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
}

