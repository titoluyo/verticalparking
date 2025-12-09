# Alternative: Setup GitHub Actions Runner using official runner image
# This uses a different approach that might work better
#
# Usage:
#   .\setup_github_runner_docker_alternative.ps1 -RepoOwner <USERNAME> -RepoName <REPO>

param(
    [string]$RepoOwner,
    [string]$RepoName
)

if (-not $RepoOwner -or -not $RepoName) {
    Write-Host "Error: Missing required parameters" -ForegroundColor Red
    Write-Host "Usage: .\setup_github_runner_docker_alternative.ps1 -RepoOwner <USERNAME> -RepoName <REPO>" -ForegroundColor Yellow
    exit 1
}

$RepoUrl = "https://github.com/$RepoOwner/$RepoName"
$RunnerName = "docker-runner-$(hostname)"
$ContainerName = "github-runner-$RepoName"

Write-Host "Alternative setup using official runner approach" -ForegroundColor Green
Write-Host "Repository: $RepoUrl" -ForegroundColor Cyan

# Get registration token
Write-Host ""
Write-Host "Get a FRESH registration token (they expire in ~1 hour):" -ForegroundColor Yellow
Write-Host "  https://github.com/$RepoOwner/$RepoName/settings/actions/runners/new" -ForegroundColor Cyan
Write-Host ""
$RegistrationToken = Read-Host "Enter the registration token"

if ([string]::IsNullOrEmpty($RegistrationToken)) {
    Write-Host "Error: Registration token is required" -ForegroundColor Red
    exit 1
}

# Stop existing container
if (docker ps -a --format '{{.Names}}' | Select-String -Pattern "^${ContainerName}$") {
    Write-Host "Removing existing container..." -ForegroundColor Yellow
    docker stop $ContainerName 2>$null
    docker rm $ContainerName 2>$null
}

# Create a directory for runner data
$RunnerDataDir = "$env:USERPROFILE\github-runner-data\$RepoName"
New-Item -ItemType Directory -Force -Path $RunnerDataDir | Out-Null

Write-Host "Using direct runner configuration approach..." -ForegroundColor Green
Write-Host "This will download and configure the runner inside a container" -ForegroundColor Cyan

# Use a base image and configure runner manually
docker run -d `
    --name $ContainerName `
    --restart unless-stopped `
    -e RUNNER_NAME="$RunnerName" `
    -e GITHUB_TOKEN="$RegistrationToken" `
    -e REPO_URL="$RepoUrl" `
    -v "${RunnerDataDir}:/runner" `
    -v /var/run/docker.sock:/var/run/docker.sock `
    myoung34/github-runner:latest

Write-Host ""
Write-Host "Container started. Waiting for configuration..." -ForegroundColor Green
Start-Sleep -Seconds 5

# Check status
$Logs = docker logs $ContainerName 2>&1
if ($Logs -match "Connected to GitHub" -or $Logs -match "Listening for Jobs") {
    Write-Host "SUCCESS: Runner is connected and ready!" -ForegroundColor Green
} else {
    Write-Host "Checking configuration..." -ForegroundColor Yellow
    Write-Host "View logs: docker logs -f $ContainerName" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "If you see token errors, get a NEW token and try again." -ForegroundColor Yellow
}

