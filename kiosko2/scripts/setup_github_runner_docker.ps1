# Setup GitHub Actions Self-Hosted Runner using Docker
# Works on Windows (with Docker Desktop)
# This is the recommended approach as it's more reliable and easier to manage
#
# Usage:
#   .\setup_github_runner_docker.ps1 -RepoOwner <USERNAME> -RepoName <REPO>
#
# The script will prompt you to get a registration token from GitHub

param(
    [string]$RepoOwner,
    [string]$RepoName
)

if (-not $RepoOwner -or -not $RepoName) {
    Write-Host "Error: Missing required parameters" -ForegroundColor Red
    Write-Host "Usage: .\setup_github_runner_docker.ps1 -RepoOwner <USERNAME> -RepoName <REPO>" -ForegroundColor Yellow
    Write-Host "Example: .\setup_github_runner_docker.ps1 -RepoOwner titoluyo -RepoName verticalparking" -ForegroundColor Yellow
    exit 1
}

$RepoUrl = "https://github.com/$RepoOwner/$RepoName"
$RunnerName = "docker-runner-$(hostname)"
$ContainerName = "github-runner-$RepoName"

Write-Host "Setting up GitHub Actions runner using Docker for $RepoUrl" -ForegroundColor Green

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed." -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "Error: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host "Docker is installed and running" -ForegroundColor Green

# Get registration token
Write-Host ""
Write-Host "To get a registration token:" -ForegroundColor Cyan
Write-Host "  1. Go to: https://github.com/$RepoOwner/$RepoName/settings/actions/runners/new" -ForegroundColor Yellow
Write-Host "  2. Copy the registration token (it expires in ~1 hour!)" -ForegroundColor Yellow
Write-Host "  3. Make sure you copy the ENTIRE token" -ForegroundColor Yellow
Write-Host ""
$RegistrationToken = Read-Host "Enter the registration token" -AsSecureString
$RegistrationTokenPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($RegistrationToken)
)

if ([string]::IsNullOrEmpty($RegistrationTokenPlain)) {
    Write-Host "Error: Registration token is required" -ForegroundColor Red
    exit 1
}

# Validate token format (should be alphanumeric, typically starts with A)
if ($RegistrationTokenPlain.Length -lt 20) {
    Write-Host "Warning: Token seems too short. Make sure you copied the entire token." -ForegroundColor Yellow
}

Write-Host "Token received (length: $($RegistrationTokenPlain.Length) characters)" -ForegroundColor Green

# Stop and remove existing container if it exists
if (docker ps -a --format '{{.Names}}' | Select-String -Pattern "^${ContainerName}$") {
    Write-Host "Stopping existing container..." -ForegroundColor Yellow
    docker stop $ContainerName 2>$null
    docker rm $ContainerName 2>$null
}

# Create docker network if it doesn't exist
docker network create github-runner-net 2>$null

Write-Host "ContainerName: $ContainerName" -ForegroundColor Cyan
Write-Host "RunnerName: $RunnerName" -ForegroundColor Cyan
Write-Host "RepoUrl: $RepoUrl" -ForegroundColor Cyan
Write-Host "RegistrationTokenPlain: $RegistrationTokenPlain" -ForegroundColor Cyan

# Run the runner container
Write-Host "Starting GitHub Actions runner container..." -ForegroundColor Green
Write-Host "Using myoung34/github-runner image (popular community image)" -ForegroundColor Cyan
docker run -d `
    --name $ContainerName `
    --restart unless-stopped `
    --network github-runner-net `
    -e RUNNER_NAME="$RunnerName" `
    -e GITHUB_TOKEN="$RegistrationTokenPlain" `
    -e REPO_URL="$RepoUrl" `
    -v /var/run/docker.sock:/var/run/docker.sock `
    myoung34/github-runner:latest

# Wait a moment for container to start
Start-Sleep -Seconds 2

# Wait a bit more for configuration
Start-Sleep -Seconds 3

# Check if container is running
$ContainerRunning = docker ps --format '{{.Names}}' | Select-String -Pattern "^${ContainerName}$"
if ($ContainerRunning) {
    Write-Host "Container is running!" -ForegroundColor Green
    Write-Host "Checking configuration status..." -ForegroundColor Cyan
    
    # Check logs for configuration status
    $Logs = docker logs $ContainerName 2>&1 | Select-Object -Last 10
    if ($Logs -match "Connected to GitHub") {
        Write-Host "Runner successfully connected to GitHub!" -ForegroundColor Green
    } elseif ($Logs -match "Invalid.*token" -or $Logs -match "Not configured") {
        Write-Host ""
        Write-Host "ERROR: Token validation failed!" -ForegroundColor Red
        Write-Host "Possible causes:" -ForegroundColor Yellow
        Write-Host "  1. Token expired (registration tokens expire in ~1 hour)" -ForegroundColor White
        Write-Host "  2. Token was copied incorrectly (missing characters)" -ForegroundColor White
        Write-Host "  3. Token is for a different repository" -ForegroundColor White
        Write-Host ""
        Write-Host "Solution:" -ForegroundColor Yellow
        Write-Host "  1. Get a NEW registration token from:" -ForegroundColor White
        Write-Host "     https://github.com/$RepoOwner/$RepoName/settings/actions/runners/new" -ForegroundColor Cyan
        Write-Host "  2. Stop this container: docker stop $ContainerName" -ForegroundColor White
        Write-Host "  3. Remove this container: docker rm $ContainerName" -ForegroundColor White
        Write-Host "  4. Run this script again with the new token" -ForegroundColor White
        Write-Host ""
        Write-Host "View full logs: docker logs $ContainerName" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "Container started. Check logs to verify: docker logs -f $ContainerName" -ForegroundColor Yellow
    }
} else {
    Write-Host "Container failed to start. Check logs with: docker logs $ContainerName" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "GitHub Actions runner container started!" -ForegroundColor Green
Write-Host ""
Write-Host "Container name: $ContainerName" -ForegroundColor Cyan
Write-Host "Runner name: $RunnerName" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  View logs:        docker logs -f $ContainerName" -ForegroundColor White
Write-Host "  Stop runner:      docker stop $ContainerName" -ForegroundColor White
Write-Host "  Start runner:     docker start $ContainerName" -ForegroundColor White
Write-Host "  Remove runner:    docker rm -f $ContainerName" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANT: Configure GitHub Secrets in your repository:" -ForegroundColor Yellow
Write-Host "  - PI_HOST: Raspberry Pi IP (e.g., 192.168.10.50)" -ForegroundColor White
Write-Host "  - PI_USER: SSH username (usually 'pi')" -ForegroundColor White
Write-Host "  - PI_SSH_KEY: Private SSH key content (for SSH authentication)" -ForegroundColor White
Write-Host "  - PI_SSH_PORT: SSH port (optional, defaults to 22)" -ForegroundColor White
Write-Host ""
Write-Host "The runner will automatically connect to GitHub and be ready for jobs!" -ForegroundColor Green

