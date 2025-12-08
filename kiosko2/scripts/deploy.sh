#!/bin/bash
#
# Kiosko2 Deployment Script
# Usage: ./deploy.sh [--skip-tests]
#
# Environment variables:
#   PI_HOST     - Raspberry Pi hostname or IP address
#   PI_USER     - SSH username (default: pi)
#   PI_SSH_KEY  - Path to SSH private key
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-raspberrypi.local}"
REMOTE_DIR="/home/${PI_USER}/verticalparking/kiosko2"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
SKIP_TESTS=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --skip-tests) SKIP_TESTS=true ;;
        --help|-h)
            echo "Usage: $0 [--skip-tests]"
            echo ""
            echo "Options:"
            echo "  --skip-tests  Skip running tests before deployment"
            exit 0
            ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Check SSH key
SSH_OPTS=""
if [ -n "$PI_SSH_KEY" ]; then
    SSH_OPTS="-i $PI_SSH_KEY"
fi

log_info "Deploying to ${PI_USER}@${PI_HOST}"

# Run tests
if [ "$SKIP_TESTS" = false ]; then
    log_info "Running tests..."
    cd "${PROJECT_DIR}/src/backend"
    
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    pip install -q -r requirements.txt
    
    pytest tests/unit tests/integration -v
    
    if [ $? -ne 0 ]; then
        log_error "Tests failed. Deployment aborted."
        exit 1
    fi
    
    deactivate
    log_info "Tests passed!"
fi

# Create deployment package
log_info "Creating deployment package..."
cd "$PROJECT_DIR"
PACKAGE_FILE="/tmp/kiosko2-deploy.tar.gz"

tar -czvf "$PACKAGE_FILE" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='*.egg-info' \
    --exclude='.venv' \
    --exclude='venv' \
    -C "$(dirname "$PROJECT_DIR")" \
    kiosko2/

# Transfer package
log_info "Transferring package to Raspberry Pi..."
scp $SSH_OPTS "$PACKAGE_FILE" "${PI_USER}@${PI_HOST}:/tmp/"

# Deploy on Pi
log_info "Deploying on Raspberry Pi..."
ssh $SSH_OPTS "${PI_USER}@${PI_HOST}" << 'ENDSSH'
set -e

DEPLOY_DIR="/home/${USER}/verticalparking"
BACKUP_DIR="/home/${USER}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create directories
mkdir -p "$DEPLOY_DIR" "$BACKUP_DIR"

# Backup current deployment
if [ -d "$DEPLOY_DIR/kiosko2" ]; then
    echo "Creating backup..."
    tar -czvf "$BACKUP_DIR/kiosko2_$TIMESTAMP.tar.gz" -C "$DEPLOY_DIR" kiosko2/ || true
fi

# Extract new deployment
echo "Extracting new deployment..."
tar -xzvf /tmp/kiosko2-deploy.tar.gz -C "$DEPLOY_DIR"

# Update backend dependencies
echo "Updating backend dependencies..."
cd "$DEPLOY_DIR/kiosko2/src/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Update frontend dependencies
echo "Updating frontend dependencies..."
cd "$DEPLOY_DIR/kiosko2/src/frontend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Restart services
echo "Restarting services..."
sudo systemctl restart kiosko2-backend || echo "Backend service not configured"
sudo systemctl restart kiosko2-frontend || echo "Frontend service not configured"

# Health check
echo "Running health check..."
sleep 3
curl -sf http://localhost:8000/api/v1/health || echo "Backend health check failed"
curl -sf http://localhost:5000/ || echo "Frontend health check failed"

echo "Deployment complete!"
ENDSSH

# Cleanup
rm -f "$PACKAGE_FILE"

log_info "Deployment successful!"
