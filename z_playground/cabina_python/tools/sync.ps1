# Quick sync script for Windows PowerShell
# Uses venv if available, otherwise uses system Python

$SCRIPT_DIR = $PSScriptRoot
$VENV_PYTHON = Join-Path $SCRIPT_DIR ".venv\Scripts\python.exe"
$SYNC_SCRIPT = Join-Path $SCRIPT_DIR "sync_to_esp32.py"

if (Test-Path $VENV_PYTHON) {
    & $VENV_PYTHON $SYNC_SCRIPT
} else {
    python $SYNC_SCRIPT
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nSync failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
} else {
    Read-Host "`nPress Enter to exit"
}

