# PowerShell script to create junctions to espp components
# Run this from the cabina-firmware-esp32c6 directory

$componentsPath = Join-Path $PSScriptRoot "components"
$esppPath = Resolve-Path (Join-Path $PSScriptRoot "..\espp\components")

Write-Host "Components path: $componentsPath"
Write-Host "ESPP path: $esppPath"
Write-Host ""

$components = @("base_component", "base_peripheral", "format", "logger", "i2c", "vl53l", "cli", "task", "runqueue", "utils")

foreach ($component in $components) {
    $junctionPath = Join-Path $componentsPath $component
    $targetPath = Join-Path $esppPath $component
    
    if (Test-Path $junctionPath) {
        Write-Host "Removing existing: $junctionPath"
        Remove-Item $junctionPath -Force
    }
    
    Write-Host "Creating junction: $component -> $targetPath"
    try {
        New-Item -ItemType Junction -Path $junctionPath -Target $targetPath -Force | Out-Null
        Write-Host "  ✓ Created successfully"
    } catch {
        Write-Host "  ✗ Error: $_"
    }
}

Write-Host ""
Write-Host "Verifying junctions:"
Get-ChildItem $componentsPath | Select-Object Name, LinkType, Target | Format-Table




