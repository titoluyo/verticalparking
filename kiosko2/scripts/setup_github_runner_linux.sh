#!/bin/bash
#
# Setup GitHub Actions Self-Hosted Runner on Linux (for mini PC or laptop)
# This allows GitHub Actions to deploy to Raspberry Pi via SSH from your Linux machine
#
# Usage: 
#   ./setup_github_runner_linux.sh <GITHUB_TOKEN> <REPO_OWNER> <REPO_NAME>
#
# Or set environment variables:
#   export GITHUB_TOKEN=your_token
#   export REPO_OWNER=your_username
#   export REPO_NAME=verticalparking
#   ./setup_github_runner_linux.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get parameters
GITHUB_TOKEN="${1:-${GITHUB_TOKEN}}"
REPO_OWNER="${2:-${REPO_OWNER}}"
REPO_NAME="${3:-${REPO_NAME}}"

if [ -z "$GITHUB_TOKEN" ] || [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    log_error "Missing required parameters"
    echo "Usage: $0 <GITHUB_TOKEN> <REPO_OWNER> <REPO_NAME>"
    echo "Or set: GITHUB_TOKEN, REPO_OWNER, REPO_NAME environment variables"
    exit 1
fi

RUNNER_USER="${USER}"
RUNNER_DIR="${HOME}/actions-runner"
REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}"
RUNNER_NAME="linux-$(hostname)"

log_info "Setting up GitHub Actions runner for ${REPO_URL}"

# Install dependencies
log_info "Installing dependencies..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y curl jq tar
elif command -v yum &> /dev/null; then
    sudo yum install -y curl jq tar
elif command -v dnf &> /dev/null; then
    sudo dnf install -y curl jq tar
else
    log_warn "Could not detect package manager. Please install: curl, jq, tar"
fi

# Create runner directory
log_info "Creating runner directory..."
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download runner
log_info "Downloading runner..."
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r '.tag_name' | sed 's/^v//')

# Detect architecture
ARCH="x64"  # Default to x64
if [ "$(uname -m)" = "aarch64" ] || [ "$(uname -m)" = "arm64" ]; then
    ARCH="arm64"
elif [ "$(uname -m)" = "x86_64" ]; then
    ARCH="x64"
fi

RUNNER_FILE="actions-runner-linux-${ARCH}-${RUNNER_VERSION}.tar.gz"
curl -o "$RUNNER_FILE" -L "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_FILE}"

# Extract
log_info "Extracting runner..."
tar xzf "$RUNNER_FILE"
rm "$RUNNER_FILE"

# Configure runner
log_info "Configuring runner..."
./config.sh \
    --url "$REPO_URL" \
    --token "$GITHUB_TOKEN" \
    --name "$RUNNER_NAME" \
    --work "_work" \
    --replace

# Install as systemd service
log_info "Installing runner as systemd service..."
sudo ./svc.sh install "$RUNNER_USER"

# Start service
log_info "Starting runner service..."
sudo ./svc.sh start

# Enable service to start on boot
log_info "Enabling runner service to start on boot..."
SERVICE_NAME="actions.runner.${REPO_OWNER}-${REPO_NAME}.${RUNNER_NAME}.service"
sudo systemctl enable "$SERVICE_NAME"

log_info "GitHub Actions runner setup complete!"
echo ""
echo "The runner is now registered and will start automatically on boot."
echo "You can check its status with: sudo systemctl status $SERVICE_NAME"
echo ""
echo "To stop the runner: sudo ./svc.sh stop"
echo "To start the runner: sudo ./svc.sh start"
echo "To uninstall: sudo ./svc.sh uninstall && ./config.sh remove --token <token>"
echo ""
log_warn "IMPORTANT: Configure GitHub Secrets in your repository:"
echo "  - PI_HOST: Raspberry Pi IP (e.g., 192.168.10.50)"
echo "  - PI_USER: SSH username (usually 'pi')"
echo "  - PI_SSH_KEY: Private SSH key content (for SSH authentication)"
echo "  - PI_SSH_PORT: SSH port (optional, defaults to 22)"

