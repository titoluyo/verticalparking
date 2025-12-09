#!/usr/bin/env pwsh
# Simple monitoring script for presence service
param(
    [string]$Server = "192.168.10.50",
    [int]$Port = 5000,
    [int]$Interval = 2
)

$BaseUrl = "http://${Server}:${Port}/api"

Write-Host "=== Monitoring Presence Service ===" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

while ($true) {
    try {
        $timestamp = Get-Date -Format "HH:mm:ss"
        
        # Get active cabin
        $active = Invoke-RestMethod -Uri "$BaseUrl/active-cabin" -Method Get -TimeoutSec 3
        $cabinId = $active.active_cabin
        
        # Get presence status
        $presence = Invoke-RestMethod -Uri "$BaseUrl/presence" -Method Get -TimeoutSec 3
        
        Write-Host "[$timestamp] Active: $cabinId | State: $($presence.state) - $($presence.message)" -ForegroundColor $(if ($presence.state -eq "entered") { "Green" } elseif ($presence.state -eq "free") { "White" } else { "Yellow" })
        Write-Host "           Entry: $($presence.entry.present), Full: $($presence.full.present)" -ForegroundColor Gray
        
        Start-Sleep -Seconds $Interval
    } catch {
        Write-Host "[$timestamp] Error: $_" -ForegroundColor Red
        Start-Sleep -Seconds $Interval
    }
}

