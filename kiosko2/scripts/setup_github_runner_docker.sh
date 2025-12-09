#!/bin/bash
#
# Setup GitHub Actions Self-Hosted Runner using Docker
# Works on Windows (WSL2), Linux, and macOS
# This is the recommended approach as it's more reliable and easier to manage
#
# Usage:
#   ./setup_github_runner_docker.sh <REPO_OWNER> <REPO_NAME>
#
# The script will prompt you to:
#   1. Get a registration token from GitHub
#   2. Enter the token when prompted
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_prompt() {
    echo -e "${BLUE}[PROMPT]${NC} $1"
}

# Get parameters
REPO_OWNER="${1}"
REPO_NAME="${2}"

if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    log_error "Missing required parameters"
    echo "Usage: $0 <REPO_OWNER> <REPO_NAME>"
    echo "Example: $0 titoluyo verticalparking"
    exit 1
fi

REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}"
RUNNER_NAME="docker-runner-$(hostname)"
CONTAINER_NAME="github-runner-${REPO_NAME}"

log_info "Setting up GitHub Actions runner using Docker for ${REPO_URL}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first:"
    echo "  - Windows: Install Docker Desktop from https://www.docker.com/products/docker-desktop"
    echo "  - Linux: sudo apt install docker.io (or equivalent)"
    echo "  - macOS: Install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    log_error "Docker is not running. Please start Docker Desktop or the Docker service."
    exit 1
fi

log_info "Docker is installed and running"

# Get registration token
log_prompt "To get a registration token:"
echo "  1. Go to: https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/actions/runners/new"
echo "  2. Copy the registration token"
echo ""
read -sp "Enter the registration token: " REGISTRATION_TOKEN
echo ""

if [ -z "$REGISTRATION_TOKEN" ]; then
    log_error "Registration token is required"
    exit 1
fi

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_warn "Stopping existing container..."
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
fi

# Create docker network if it doesn't exist
docker network create github-runner-net 2>/dev/null || true

# Run the runner container
log_info "Starting GitHub Actions runner container..."
log_info "Using myoung34/github-runner image (popular community image)"
docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    --network github-runner-net \
    -e RUNNER_NAME="${RUNNER_NAME}" \
    -e GITHUB_TOKEN="${REGISTRATION_TOKEN}" \
    -e REPO_URL="${REPO_URL}" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    myoung34/github-runner:latest

# Wait a moment for container to start
sleep 2

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "Container is running successfully!"
else
    log_error "Container failed to start. Check logs with: docker logs ${CONTAINER_NAME}"
    exit 1
fi

log_info "GitHub Actions runner container started!"
echo ""
log_info "Container name: ${CONTAINER_NAME}"
log_info "Runner name: ${RUNNER_NAME}"
echo ""
log_info "Useful commands:"
echo "  View logs:        docker logs -f ${CONTAINER_NAME}"
echo "  Stop runner:      docker stop ${CONTAINER_NAME}"
echo "  Start runner:     docker start ${CONTAINER_NAME}"
echo "  Remove runner:    docker rm -f ${CONTAINER_NAME}"
echo ""
log_warn "IMPORTANT: Configure GitHub Secrets in your repository:"
echo "  - PI_HOST: Raspberry Pi IP (e.g., 192.168.10.50)"
echo "  - PI_USER: SSH username (usually 'pi')"
echo "  - PI_SSH_KEY: Private SSH key content (for SSH authentication)"
echo "  - PI_SSH_PORT: SSH port (optional, defaults to 22)"
echo ""
log_info "The runner will automatically connect to GitHub and be ready for jobs!"

