<#
.SYNOPSIS
  Inicia la app Flask en Windows (PowerShell) para desarrollo local.

.DESCRIPTION
  - Crea/activa entorno virtual (.venv)
  - Instala dependencias de requirements.txt
  - Establece PORT (por defecto 5000)
  - Inicia app.py y registra logs en .\logs\app.log

.PARAMETER Background
  Ejecuta la app en segundo plano (proceso separado) y retorna inmediatamente.

.PARAMETER Port
  Puerto HTTP para la app (por defecto 5000).

.PARAMETER OpenBrowser
  Abre el navegador en http://localhost:PORT tras iniciar.

.EXAMPLE
  ./start_kiosk.ps1 -Port 5000 -OpenBrowser

.EXAMPLE
  ./start_kiosk.ps1 -Background
#>
param(
  [switch]$Background,
  [int]$Port = 5000,
  [switch]$OpenBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Ir a la carpeta del script
Set-Location -Path $PSScriptRoot

$venv = Join-Path $PSScriptRoot '.venv'
$logs = Join-Path $PSScriptRoot 'logs'
$logFile = Join-Path $logs 'app.log'

if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }

# Crear venv si no existe
if (-not (Test-Path $venv)) {
  Write-Host '[kiosk] Creando entorno virtual (.venv)...'
  python -m venv $venv
}

# Activar venv
$activate = Join-Path $venv 'Scripts\Activate.ps1'
. $activate

Write-Host '[kiosk] Actualizando pip y dependencias...'
python -m pip install --upgrade pip | Out-Null
pip install -r (Join-Path $PSScriptRoot 'requirements.txt') | Out-Null

# Definir puerto
$env:PORT = "$Port"
Write-Host "[kiosk] Usando puerto :$Port"

if ($Background) {
  Write-Host '[kiosk] Iniciando en segundo plano...'
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'python'
  $psi.Arguments = 'app.py'
  $psi.WorkingDirectory = $PSScriptRoot
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false
  $proc = [System.Diagnostics.Process]::Start($psi)
  # Adjuntar logging asíncrono
  $stdOut = $proc.StandardOutput
  $stdErr = $proc.StandardError
  Start-Job -ScriptBlock {
    param($outStream, $errStream, $file)
    while (-not $outStream.EndOfStream) { $line = $outStream.ReadLine(); if ($line) { Add-Content -Path $file -Value $line } }
    while (-not $errStream.EndOfStream) { $line = $errStream.ReadLine(); if ($line) { Add-Content -Path $file -Value $line } }
  } -ArgumentList $stdOut, $stdErr, $logFile | Out-Null
  Write-Host "[kiosk] PID: $($proc.Id) | Logs: $logFile"
} else {
  Write-Host '[kiosk] Iniciando en primer plano (Ctrl+C para salir)...'
  # Redirige stdout+stderr al log y pantalla con Tee; evita que stderr se trate como error
  "[kiosk] $(Get-Date -Format s) Arrancando app.py" | Tee-Object -FilePath $logFile -Append | Out-Null
  $prevErrPref = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  & python app.py 2>&1 | Tee-Object -FilePath $logFile -Append
  $ErrorActionPreference = $prevErrPref
}

if ($OpenBrowser) {
  Start-Sleep -Seconds 1
  Start-Process "http://localhost:$Port"
}
