#!/bin/bash
#
# One-time setup script for systemd services on Raspberry Pi
# Run this once on the Pi to configure the services
# After this, the deployment workflow will handle updates
#
# Usage:
#   ./setup_services.sh
#   or
#   curl -sSL https://raw.githubusercontent.com/titoluyo/verticalparking/main/kiosko2/scripts/setup_services.sh | bash

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

# Configuration
# Detect the actual user (even if script is run with sudo)
if [ -n "$SUDO_USER" ]; then
    KIOSKO_USER="$SUDO_USER"
elif [ -n "$USER" ] && [ "$USER" != "root" ]; then
    KIOSKO_USER="$USER"
else
    # Fallback: try to get the user from the home directory
    KIOSKO_USER=$(basename "$HOME" 2>/dev/null || echo "pi")
    log_warn "Could not detect user, using: $KIOSKO_USER"
fi

DEPLOY_DIR="/home/${KIOSKO_USER}/verticalparking_deploy"
BACKEND_PORT=8000
FRONTEND_PORT=5000

log_info "Detected user: $KIOSKO_USER"
log_info "Deployment directory: $DEPLOY_DIR"

log_info "Setting up Kiosko2 systemd services..."

# Check if deployment directory exists
if [ ! -d "$DEPLOY_DIR/kiosko2" ]; then
    log_warn "Deployment directory not found: $DEPLOY_DIR/kiosko2"
    log_info "Creating directory structure..."
    mkdir -p "$DEPLOY_DIR/kiosko2/data"
    log_warn "Note: Services will be created but won't work until code is deployed"
fi

# Create data directory
mkdir -p "${DEPLOY_DIR}/kiosko2/data"

log_info "Creating systemd service files..."

# Backend service
sudo tee /etc/systemd/system/kiosko2-backend.service > /dev/null << EOF
[Unit]
Description=Kiosko2 Backend Service
After=network.target mosquitto.service

[Service]
Type=simple
User=${KIOSKO_USER}
Group=${KIOSKO_USER}
WorkingDirectory=${DEPLOY_DIR}/kiosko2/src/backend
Environment="PATH=${DEPLOY_DIR}/kiosko2/src/backend/.venv/bin"
Environment="KIOSKO_DATABASE_PATH=${DEPLOY_DIR}/kiosko2/data/kiosko.db"
Environment="KIOSKO_MQTT_BROKER=127.0.0.1"
Environment="KIOSKO_MQTT_PORT=1883"
ExecStart=${DEPLOY_DIR}/kiosko2/src/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT} --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Frontend service
sudo tee /etc/systemd/system/kiosko2-frontend.service > /dev/null << EOF
[Unit]
Description=Kiosko2 Frontend Service
After=network.target kiosko2-backend.service

[Service]
Type=simple
User=${KIOSKO_USER}
Group=${KIOSKO_USER}
WorkingDirectory=${DEPLOY_DIR}/kiosko2/src/frontend
Environment="PATH=${DEPLOY_DIR}/kiosko2/src/frontend/.venv/bin"
Environment="KIOSKO_BACKEND_URL=http://localhost:${BACKEND_PORT}"
Environment="FLASK_SECRET_KEY=change-this-in-production"
# Use --access-logfile and --error-logfile for better debugging
ExecStart=${DEPLOY_DIR}/kiosko2/src/frontend/.venv/bin/gunicorn -w 2 -b 0.0.0.0:${FRONTEND_PORT} --access-logfile - --error-logfile - --log-level info wsgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
log_info "Reloading systemd..."
sudo systemctl daemon-reload

# Enable services
log_info "Enabling services..."
sudo systemctl enable kiosko2-backend
sudo systemctl enable kiosko2-frontend

log_info "Services configured successfully!"
echo ""
log_info "Service files created:"
echo "  - /etc/systemd/system/kiosko2-backend.service"
echo "  - /etc/systemd/system/kiosko2-frontend.service"
echo ""
log_info "Services are enabled and will start automatically on boot"
echo ""
log_warn "Note: Services won't start until code is deployed and virtual environments are created"
log_info "After first deployment, you can start services with:"
echo "  sudo systemctl start kiosko2-backend"
echo "  sudo systemctl start kiosko2-frontend"
echo ""
log_info "Check service status with:"
echo "  sudo systemctl status kiosko2-backend"
echo "  sudo systemctl status kiosko2-frontend"
echo ""
log_info "View live logs with:"
echo "  sudo journalctl -u kiosko2-backend -f"
echo "  sudo journalctl -u kiosko2-frontend -f"
echo "  sudo journalctl -u kiosko2-backend -u kiosko2-frontend -f  # Both services"
echo "  Or use: ./view_logs.sh [backend|frontend|both]"

