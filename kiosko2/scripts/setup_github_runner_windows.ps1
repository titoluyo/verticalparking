# Setup GitHub Actions Self-Hosted Runner on Windows
# This allows GitHub Actions to deploy to Raspberry Pi via SSH from your Windows machine
#
# Usage:
#   .\setup_github_runner_windows.ps1 -GitHubToken <TOKEN> -RepoOwner <USERNAME> -RepoName <REPO>
#
# Or set environment variables:
#   $env:GITHUB_TOKEN = "your_token"
#   $env:REPO_OWNER = "your_username"
#   $env:REPO_NAME = "verticalparking"
#   .\setup_github_runner_windows.ps1

param(
    [string]$GitHubToken = $env:GITHUB_TOKEN,
    [string]$RepoOwner = $env:REPO_OWNER,
    [string]$RepoName = $env:REPO_NAME
)

if (-not $GitHubToken -or -not $RepoOwner -or -not $RepoName) {
    Write-Host "Error: Missing required parameters" -ForegroundColor Red
    Write-Host "Usage: .\setup_github_runner_windows.ps1 -GitHubToken <TOKEN> -RepoOwner <USERNAME> -RepoName <REPO>" -ForegroundColor Yellow
    Write-Host "Or set environment variables: GITHUB_TOKEN, REPO_OWNER, REPO_NAME" -ForegroundColor Yellow
    exit 1
}

$RepoUrl = "https://github.com/$RepoOwner/$RepoName"
$RunnerDir = "$env:USERPROFILE\actions-runner"
$RunnerName = "windows-$(hostname)"

Write-Host "Setting up GitHub Actions runner for $RepoUrl" -ForegroundColor Green
Write-Host "Runner will be installed to: $RunnerDir" -ForegroundColor Cyan

# Create runner directory
Write-Host "`nCreating runner directory..." -ForegroundColor Green
New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null
Set-Location $RunnerDir

# Download runner
Write-Host "Downloading runner..." -ForegroundColor Green
$LatestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/actions/runner/releases/latest"
$RunnerVersion = $LatestRelease.tag_name -replace '^v', ''
$RunnerFile = "actions-runner-win-x64-$RunnerVersion.zip"
$RunnerUrl = "https://github.com/actions/runner/releases/download/v$RunnerVersion/$RunnerFile"

Invoke-WebRequest -Uri $RunnerUrl -OutFile $RunnerFile

# Extract
Write-Host "Extracting runner..." -ForegroundColor Green
Expand-Archive -Path $RunnerFile -DestinationPath . -Force
Remove-Item $RunnerFile

# Configure runner
Write-Host "Configuring runner..." -ForegroundColor Green
Push-Location $RunnerDir
try {
    .\config.cmd --url $RepoUrl --token $GitHubToken --name $RunnerName --work "_work" --replace
    
    # Install as Windows service
    Write-Host "`nInstalling runner as Windows service..." -ForegroundColor Green
    .\svc.cmd install
    
    # Start service
    Write-Host "Starting runner service..." -ForegroundColor Green
    .\svc.cmd start
} catch {
    Write-Host "Error configuring runner: $_" -ForegroundColor Red
    Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Make sure the token has 'repo' scope (for private repos) or 'public_repo' (for public repos)" -ForegroundColor Yellow
    Write-Host "2. Try using a registration token from: https://github.com/$RepoOwner/$RepoName/settings/actions/runners/new" -ForegroundColor Yellow
    Write-Host "3. Or use Docker instead (see setup_github_runner_docker.sh)" -ForegroundColor Yellow
    throw
} finally {
    Pop-Location
}

Write-Host "`nGitHub Actions runner setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "The runner is now registered and will start automatically on boot." -ForegroundColor Cyan
Write-Host "You can check its status in: Services (services.msc) -> GitHub Actions Runner" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop the runner: .\svc.cmd stop" -ForegroundColor Yellow
Write-Host "To start the runner: .\svc.cmd start" -ForegroundColor Yellow
Write-Host "To uninstall: .\svc.cmd uninstall && .\config.cmd remove --token <token>" -ForegroundColor Yellow
Write-Host ""
Write-Host "IMPORTANT: Configure GitHub Secrets in your repository:" -ForegroundColor Yellow
Write-Host "  - PI_HOST: Raspberry Pi IP (e.g., 192.168.10.50)" -ForegroundColor Yellow
Write-Host "  - PI_USER: SSH username (usually 'pi')" -ForegroundColor Yellow
Write-Host "  - PI_SSH_KEY: Private SSH key content (for SSH authentication)" -ForegroundColor Yellow
Write-Host "  - PI_SSH_PORT: SSH port (optional, defaults to 22)" -ForegroundColor Yellow

