#!/usr/bin/env pwsh
# Script to test presence service endpoints from Windows
# Usage: .\test_presence.ps1 [server] [port]
# Example: .\test_presence.ps1 192.168.10.50 5000

param(
    [string]$Server = "192.168.10.50",
    [int]$Port = 5000
)

$BaseUrl = "http://${Server}:${Port}/api"

Write-Host "Testing Presence Service Endpoints" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Gray
Write-Host ""

# Test 1: Get active cabin
Write-Host "1. Getting active cabin..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/active-cabin" -Method Get
    Write-Host "   Active cabin: $($response.active_cabin)" -ForegroundColor Green
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}
Write-Host ""

# Test 2: Get presence status (for active cabin)
Write-Host "2. Getting presence status (active cabin)..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/presence" -Method Get
    Write-Host "   State: $($response.state)" -ForegroundColor Green
    Write-Host "   Message: $($response.message)" -ForegroundColor Green
    Write-Host "   Entry: $($response.entry.present), Full: $($response.full.present)" -ForegroundColor Green
    Write-Host "   Previous: entry=$($response.entry.present), full=$($response.full.present)" -ForegroundColor Gray
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}
Write-Host ""

# Test 3: Get debug info for all cabins
Write-Host "3. Getting debug info for all cabins..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/presence/debug/all-cabins" -Method Get
    Write-Host "   Active cabin: $($response.active_cabin)" -ForegroundColor Green
    Write-Host "   Connected: $($response.connected)" -ForegroundColor Green
    Write-Host "   Time since connection: $([math]::Round($response.time_since_connection, 1))s" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Cabin details:" -ForegroundColor Cyan
    foreach ($cabinId in ($response.cabins.PSObject.Properties.Name | Sort-Object)) {
        $cabin = $response.cabins.$cabinId
        $active = if ($cabin.is_active) { "*" } else { " " }
        Write-Host "   $active $cabinId" -ForegroundColor $(if ($cabin.is_active) { "Yellow" } else { "White" })
        if ($cabin.sensors) {
            $entry = $cabin.sensors.entry
            $full = $cabin.sensors.full
            $prev = $cabin.previous_state
            Write-Host "      Entry: $($entry.present) (age: $([math]::Round($entry.age_seconds, 1))s)" -ForegroundColor Gray
            Write-Host "      Full:  $($full.present) (age: $([math]::Round($full.age_seconds, 1))s)" -ForegroundColor Gray
            Write-Host "      Previous: entry=$($prev.entry), full=$($prev.full)" -ForegroundColor DarkGray
            if ($cabin.computed_state) {
                Write-Host "      Computed state: $($cabin.computed_state.state) - $($cabin.computed_state.message)" -ForegroundColor $(if ($cabin.computed_state.state -eq "entered") { "Green" } elseif ($cabin.computed_state.state -eq "free") { "White" } else { "Yellow" })
            }
        }
    }
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}
Write-Host ""

# Test 4: Get debug info for active cabin specifically
Write-Host "4. Getting detailed debug info for active cabin..." -ForegroundColor Yellow
try {
    $activeCabin = (Invoke-RestMethod -Uri "$BaseUrl/active-cabin" -Method Get).active_cabin
    if ($activeCabin) {
        $response = Invoke-RestMethod -Uri "$BaseUrl/presence/debug/cabin/$activeCabin" -Method Get
        Write-Host "   Cabin: $($response.cabin_id)" -ForegroundColor Green
        Write-Host "   Is Active: $($response.is_active)" -ForegroundColor Green
        Write-Host "   Entry sensor: $($response.sensors.entry.present) (age: $([math]::Round($response.sensors.entry.age_seconds, 1))s)" -ForegroundColor Gray
        Write-Host "   Full sensor: $($response.sensors.full.present) (age: $([math]::Round($response.sensors.full.age_seconds, 1))s)" -ForegroundColor Gray
        Write-Host "   Previous state: entry=$($response.previous_state.entry), full=$($response.previous_state.full)" -ForegroundColor DarkGray
        Write-Host "   Computed state: $($response.computed_state.state) - $($response.computed_state.message)" -ForegroundColor $(if ($response.computed_state.state -eq "entered") { "Green" } elseif ($response.computed_state.state -eq "free") { "White" } else { "Yellow" })
    }
} catch {
    Write-Host "   Error: $_" -ForegroundColor Red
}
Write-Host ""

Write-Host "Done!" -ForegroundColor Cyan
