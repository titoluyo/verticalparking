# Start Python HTTP server for OTA firmware updates
# This script binds to all interfaces (0.0.0.0) so ESP32 can access it

$ErrorActionPreference = "Stop"

Write-Host "Starting OTA firmware server on port 8080..." -ForegroundColor Green
Write-Host "Server will be accessible at: http://192.168.10.147:8080/cabina-firmware.bin" -ForegroundColor Yellow
Write-Host ""

# Get the build directory
$buildDir = Join-Path $PSScriptRoot "build"
if (-not (Test-Path $buildDir)) {
    Write-Host "ERROR: Build directory not found. Run 'idf.py build' first." -ForegroundColor Red
    exit 1
}

$firmwarePath = Join-Path $buildDir "cabina-firmware.bin"
if (-not (Test-Path $firmwarePath)) {
    Write-Host "ERROR: Firmware binary not found at: $firmwarePath" -ForegroundColor Red
    Write-Host "Run 'idf.py build' first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Firmware binary found: $firmwarePath" -ForegroundColor Green
Write-Host "File size: $((Get-Item $firmwarePath).Length) bytes" -ForegroundColor Cyan
Write-Host ""

# Check if firewall rule exists
$firewallRule = Get-NetFirewallRule -Name "Python HTTP Server OTA" -ErrorAction SilentlyContinue
if (-not $firewallRule) {
    Write-Host "WARNING: Firewall rule not found. You may need to allow port 8080 in Windows Firewall." -ForegroundColor Yellow
    Write-Host "Run as Administrator: netsh advfirewall firewall add rule name=`"Python HTTP Server OTA`" dir=in action=allow protocol=TCP localport=8080" -ForegroundColor Yellow
    Write-Host ""
}

# Change to build directory and start server
Set-Location $buildDir

Write-Host "Starting HTTP server... Press Ctrl+C to stop." -ForegroundColor Green
Write-Host ""

# Start Python HTTP server on all interfaces (0.0.0.0)
python -m http.server 8080 --bind 0.0.0.0

