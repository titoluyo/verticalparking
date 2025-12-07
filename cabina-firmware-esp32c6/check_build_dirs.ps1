# Diagnostic script to check for build directories
# Run this from cabina-firmware-esp32c6 directory

Write-Host "=== Checking for build directories ===" -ForegroundColor Cyan

# Check project build directory
$projectBuild = Join-Path $PSScriptRoot "build"
if (Test-Path $projectBuild) {
    Write-Host "✓ Project build directory EXISTS: $projectBuild" -ForegroundColor Yellow
    Write-Host "  Should be removed with: Remove-Item build -Recurse -Force" -ForegroundColor Gray
} else {
    Write-Host "✓ Project build directory does not exist (good)" -ForegroundColor Green
}

# Check format component build directory
$formatBuild = Join-Path $PSScriptRoot "..\espp\components\format\build"
if (Test-Path $formatBuild) {
    Write-Host "✗ Format component build directory EXISTS: $formatBuild" -ForegroundColor Red
    Write-Host "  This is causing the issue! Remove it with:" -ForegroundColor Yellow
    Write-Host "  Remove-Item '$formatBuild' -Recurse -Force" -ForegroundColor White
} else {
    Write-Host "✓ Format component build directory does not exist (good)" -ForegroundColor Green
}

# Check if we're in the right directory
Write-Host "`n=== Current directory ===" -ForegroundColor Cyan
Write-Host "Current: $(Get-Location)" -ForegroundColor White
Write-Host "Expected: $PSScriptRoot" -ForegroundColor White

# Check components directory
$componentsDir = Join-Path $PSScriptRoot "components"
if (Test-Path $componentsDir) {
    Write-Host "`n=== Components directory ===" -ForegroundColor Cyan
    $components = Get-ChildItem $componentsDir
    Write-Host "Found $($components.Count) component junctions:" -ForegroundColor White
    foreach ($comp in $components) {
        $linkType = if ($comp.LinkType) { $comp.LinkType } else { "Directory" }
        Write-Host "  - $($comp.Name) ($linkType)" -ForegroundColor Gray
    }
} else {
    Write-Host "`n✗ Components directory not found!" -ForegroundColor Red
}

Write-Host "`n=== Recommendations ===" -ForegroundColor Cyan
if (Test-Path $formatBuild) {
    Write-Host "1. Remove format build directory:" -ForegroundColor Yellow
    Write-Host "   Remove-Item '$formatBuild' -Recurse -Force" -ForegroundColor White
}
if (Test-Path $projectBuild) {
    Write-Host "2. Remove project build directory:" -ForegroundColor Yellow
    Write-Host "   cd cabina-firmware-esp32c6" -ForegroundColor White
    Write-Host "   Remove-Item build -Recurse -Force" -ForegroundColor White
}
Write-Host "3. Then try: idf.py menuconfig" -ForegroundColor Yellow





