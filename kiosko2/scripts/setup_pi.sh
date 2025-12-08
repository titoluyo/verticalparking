#!/bin/bash
#
# Raspberry Pi Initial Setup Script for Kiosko2
# Run this script once on a fresh Raspberry Pi installation.
#
# Usage: curl -sSL https://raw.githubusercontent.com/your-repo/main/kiosko2/scripts/setup_pi.sh | bash
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

# Configuration
DEPLOY_DIR="${HOME}/verticalparking"
KIOSKO_USER="${USER}"
BACKEND_PORT=8000
FRONTEND_PORT=5000

log_info "Starting Raspberry Pi setup for Kiosko2..."

# Update system
log_info "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
log_info "Installing dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    libzbar0 \
    mosquitto \
    mosquitto-clients

# Install picamera2 (Raspberry Pi only)
if [ -f /etc/os-release ] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    log_info "Installing picamera2..."
    sudo apt install -y python3-picamera2 python3-libcamera || log_warn "picamera2 installation failed"
fi

# Create deployment directory
log_info "Creating deployment directory..."
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# Clone or update repository (if URL is provided)
if [ -n "$REPO_URL" ]; then
    if [ -d ".git" ]; then
        log_info "Updating repository..."
        git pull origin main
    else
        log_info "Cloning repository..."
        git clone "$REPO_URL" .
    fi
fi

# Create systemd service files
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
ExecStart=${DEPLOY_DIR}/kiosko2/src/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT}
Restart=always
RestartSec=5

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
ExecStart=${DEPLOY_DIR}/kiosko2/src/frontend/.venv/bin/gunicorn -w 2 -b 0.0.0.0:${FRONTEND_PORT} app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
log_info "Reloading systemd..."
sudo systemctl daemon-reload

# Enable services (but don't start yet)
log_info "Enabling services..."
sudo systemctl enable kiosko2-backend
sudo systemctl enable kiosko2-frontend

# Create data directory
mkdir -p "${DEPLOY_DIR}/kiosko2/data"

# Create environment file template
log_info "Creating environment file template..."
cat > "${DEPLOY_DIR}/kiosko2/.env.template" << EOF
# Kiosko2 Environment Configuration
# Copy this file to .env and customize

# Backend Configuration
KIOSKO_DATABASE_PATH=${DEPLOY_DIR}/kiosko2/data/kiosko.db
KIOSKO_MQTT_BROKER=127.0.0.1
KIOSKO_MQTT_PORT=1883
KIOSKO_SITE_ID=garage-01
KIOSKO_API_KEY=change-this-secret-key
KIOSKO_ENABLE_TEST_ENDPOINTS=true

# Frontend Configuration
KIOSKO_BACKEND_URL=http://localhost:${BACKEND_PORT}
FLASK_SECRET_KEY=change-this-secret-key

# Printer Configuration (optional)
# KIOSKO_PRINTER_ENABLED=true
# KIOSKO_PRINTER_VENDOR_ID=0x0fe6
# KIOSKO_PRINTER_PRODUCT_ID=0x811e

# Video Configuration (optional)
# KIOSKO_VIDEO_ENABLED=true
EOF

# Configure Mosquitto
log_info "Configuring Mosquitto MQTT broker..."
sudo tee /etc/mosquitto/conf.d/kiosko.conf > /dev/null << EOF
listener 1883
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log
EOF

sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# Setup complete
log_info "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy the kiosko2 directory to ${DEPLOY_DIR}/kiosko2"
echo "2. Create virtual environments and install dependencies:"
echo "   cd ${DEPLOY_DIR}/kiosko2/src/backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
echo "   cd ${DEPLOY_DIR}/kiosko2/src/frontend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
echo "3. Copy .env.template to .env and configure"
echo "4. Start services:"
echo "   sudo systemctl start kiosko2-backend"
echo "   sudo systemctl start kiosko2-frontend"
echo ""
echo "Services will be available at:"
echo "  - Backend API: http://$(hostname -I | cut -d' ' -f1):${BACKEND_PORT}/api/v1"
echo "  - Frontend UI: http://$(hostname -I | cut -d' ' -f1):${FRONTEND_PORT}"
