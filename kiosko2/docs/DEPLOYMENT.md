# Kiosko2 Deployment Guide

This document describes how to deploy the Kiosko2 vertical parking system to Raspberry Pi devices.

## Architecture Overview

Kiosko2 uses a modular architecture with two services:

1. **Backend (FastAPI)** - Port 8000
   - REST API for business logic
   - MQTT integration for sensor communication
   - SQLite database for persistence

2. **Frontend (Flask)** - Port 5000
   - Web UI for user interaction
   - Calls backend API for all operations

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Web Browser   │────▶│  Flask Frontend │────▶│FastAPI Backend│
│                 │     │   (Port 5000)   │     │  (Port 8000)  │
└─────────────────┘     └─────────────────┘     └───────┬──────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  MQTT Broker    │
                                               │   (Mosquitto)   │
                                               └────────┬────────┘
                                                         │
                                               ┌─────────▼────────┐
                                               │  Cabin Sensors   │
                                               │    (ESP32)       │
                                               └──────────────────┘
```

## Prerequisites

### Raspberry Pi Requirements
- Raspberry Pi 3B+ or newer
- Raspberry Pi OS (Bookworm or newer)
- Python 3.11+
- 2GB+ RAM recommended
- Network connectivity (Ethernet or WiFi)

### Windows Development Machine
- Git Bash or WSL2
- SSH client
- Python 3.10+ (for local development)

## Initial Pi Setup

### Option 1: Automated Setup

Run the setup script on the Raspberry Pi:

```bash
# Download and run the setup script
curl -sSL https://raw.githubusercontent.com/your-repo/main/kiosko2/scripts/setup_pi.sh | bash
```

### Option 2: Manual Setup

1. **Update system:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install dependencies:**
   ```bash
   sudo apt install -y python3 python3-pip python3-venv git curl libzbar0 mosquitto mosquitto-clients
   ```

3. **Install picamera2 (if using camera):**
   ```bash
   sudo apt install -y python3-picamera2 python3-libcamera
   ```

4. **Create deployment directory:**
   ```bash
   mkdir -p ~/verticalparking
   cd ~/verticalparking
   ```

5. **Clone repository:**
   ```bash
   git clone https://github.com/your-repo/verticalparking.git .
   ```

6. **Setup backend:**
   ```bash
   cd kiosko2/src/backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   deactivate
   ```

7. **Setup frontend:**
   ```bash
   cd ../frontend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   deactivate
   ```

## Configuration

### Environment Variables

Create `/home/pi/verticalparking/kiosko2/.env`:

```bash
# Backend Configuration
KIOSKO_DATABASE_PATH=/home/pi/verticalparking/kiosko2/data/kiosko.db
KIOSKO_MQTT_BROKER=127.0.0.1
KIOSKO_MQTT_PORT=1883
KIOSKO_SITE_ID=garage-01
KIOSKO_API_KEY=your-secret-api-key
KIOSKO_ENABLE_TEST_ENDPOINTS=false  # Set to true for E2E testing only

# Frontend Configuration
KIOSKO_BACKEND_URL=http://localhost:8000
FLASK_SECRET_KEY=your-flask-secret-key

# Printer Configuration (optional)
KIOSKO_PRINTER_ENABLED=true
KIOSKO_PRINTER_VENDOR_ID=0x0fe6
KIOSKO_PRINTER_PRODUCT_ID=0x811e

# Video Configuration (optional)
KIOSKO_VIDEO_ENABLED=true
```

### Systemd Services

The setup script creates these service files:

**Backend Service** (`/etc/systemd/system/kiosko2-backend.service`):
```ini
[Unit]
Description=Kiosko2 Backend Service
After=network.target mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/verticalparking/kiosko2/src/backend
Environment="PATH=/home/pi/verticalparking/kiosko2/src/backend/.venv/bin"
ExecStart=/home/pi/verticalparking/kiosko2/src/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Frontend Service** (`/etc/systemd/system/kiosko2-frontend.service`):
```ini
[Unit]
Description=Kiosko2 Frontend Service
After=network.target kiosko2-backend.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/verticalparking/kiosko2/src/frontend
Environment="PATH=/home/pi/verticalparking/kiosko2/src/frontend/.venv/bin"
ExecStart=/home/pi/verticalparking/kiosko2/src/frontend/.venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Deployment Methods

### Method 1: GitHub Actions with Self-Hosted Runner (Recommended)

This method uses a GitHub Actions self-hosted runner installed on your development machine (Windows laptop or Linux mini PC). The runner connects to the Raspberry Pi via SSH to deploy, which works even if the Pi is on a private network (e.g., `192.168.10.50`).

**Benefits:**
- Runner runs on a more powerful machine (Windows/Linux laptop/mini PC)
- Can manage multiple Raspberry Pis from one runner
- Pi doesn't need to run the runner service (saves resources)
- Works with private IP addresses since runner is on the same network

#### Setup GitHub Actions Runner

**Option A: Using Docker (Recommended - Easier and More Reliable)**

1. **Get Registration Token:**
   - Go to: `https://github.com/<USERNAME>/<REPO>/settings/actions/runners/new`
   - Copy the registration token (it's different from a PAT)

2. **Run Docker Setup:**
   
   On Windows (PowerShell):
   ```powershell
   cd kiosko2\scripts
   .\setup_github_runner_docker.ps1 -RepoOwner <USERNAME> -RepoName verticalparking
   ```
   
   On Linux/Mac/WSL:
   ```bash
   cd kiosko2/scripts
   chmod +x setup_github_runner_docker.sh
   ./setup_github_runner_docker.sh <USERNAME> verticalparking
   ```

3. **Or use Docker Compose:**
   ```bash
   # Create .env file
   echo "GITHUB_TOKEN=<registration_token>" > .env
   echo "GITHUB_REPOSITORY=<username>/verticalparking" >> .env
   echo "RUNNER_NAME=docker-runner" >> .env
   
   # Start runner
   docker-compose -f kiosko2/scripts/docker-compose.runner.yml up -d
   ```

**Option B: Native Installation (Alternative)**

1. **Get Registration Token:**
   - Go to: `https://github.com/<USERNAME>/<REPO>/settings/actions/runners/new`
   - Copy the registration token

2. **Setup SSH Key for Pi Access:**
   ```bash
   # On Windows (PowerShell) or Linux
   # Generate SSH key if you don't have one
   ssh-keygen -t ed25519 -C "github-actions-runner"
   
   # Copy public key to Raspberry Pi
   ssh-copy-id -i ~/.ssh/id_ed25519.pub pi@192.168.10.50
   
   # Test connection
   ssh pi@192.168.10.50 "echo 'SSH connection successful'"
   ```

3. **Install Runner on Windows:**
   ```powershell
   cd kiosko2\scripts
   .\setup_github_runner_windows.ps1 -GitHubToken <REGISTRATION_TOKEN> -RepoOwner <USERNAME> -RepoName verticalparking
   ```
   
   **Note:** Use the registration token from step 1, NOT a Personal Access Token (PAT).

   Or on Linux:
   ```bash
   cd kiosko2/scripts
   chmod +x setup_github_runner_linux.sh
   ./setup_github_runner_linux.sh <REGISTRATION_TOKEN> <USERNAME> verticalparking
   ```

4. **Configure GitHub Secrets:**
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Add these secrets:
     - `PI_HOST`: `192.168.10.50` (your Pi's IP)
     - `PI_USER`: `pi` (SSH username)
     - `PI_SSH_KEY`: Contents of your private SSH key (`~/.ssh/id_ed25519` on Linux, or the key file on Windows)
     - `PI_SSH_PORT`: `22` (optional, only if using non-standard port)

5. **Verify the runner is registered:**
   - Go to your GitHub repository → Settings → Actions → Runners
   - You should see your Windows/Linux runner listed

#### How It Works

- Tests run on GitHub-hosted runners (Ubuntu)
- When tests pass, the deployment job runs on your self-hosted runner (Windows/Linux machine)
- The runner checks out code, creates a deployment package, and SSHes to the Pi
- The Pi receives the package, updates dependencies, and restarts services
- No need for GitHub to access your Pi's private IP directly

#### Managing the Runner

**Windows:**
```powershell
# Check runner status
Get-Service | Where-Object {$_.Name -like "*GitHub Actions*"}

# Stop runner
cd $env:USERPROFILE\actions-runner
.\svc.cmd stop

# Start runner
.\svc.cmd start

# Uninstall runner
.\svc.cmd uninstall
.\config.cmd remove --token <token>
```

**Linux:**
```bash
# Check runner status
sudo systemctl status actions.runner.<owner>-<repo>.<runner-name>.service

# View runner logs
journalctl -u actions.runner.<owner>-<repo>.<runner-name>.service -f

# Stop runner
cd ~/actions-runner
sudo ./svc.sh stop

# Start runner
sudo ./svc.sh start

# Uninstall runner
sudo ./svc.sh uninstall
cd ~/actions-runner
./config.sh remove --token <token>
```

**Note:** The runner needs:
- Internet access to communicate with GitHub
- Network access to the Raspberry Pi (same LAN or VPN)
- SSH key configured for passwordless access to the Pi

### Method 2: Manual Deployment Script

From your development machine:

```bash
# Set environment variables
export PI_HOST=192.168.1.100
export PI_USER=pi
export PI_SSH_KEY=~/.ssh/id_rsa

# Run deployment
cd kiosko2/scripts
./deploy.sh
```

### Method 3: Direct Git Pull

On the Raspberry Pi:

```bash
cd ~/verticalparking
git pull origin main

# Update backend
cd kiosko2/src/backend
source .venv/bin/activate
pip install -r requirements.txt
deactivate

# Update frontend
cd ../frontend
source .venv/bin/activate
pip install -r requirements.txt
deactivate

# Restart services
sudo systemctl restart kiosko2-backend kiosko2-frontend
```

## Service Management

```bash
# Start services
sudo systemctl start kiosko2-backend
sudo systemctl start kiosko2-frontend

# Stop services
sudo systemctl stop kiosko2-backend
sudo systemctl stop kiosko2-frontend

# Restart services
sudo systemctl restart kiosko2-backend kiosko2-frontend

# Check status
sudo systemctl status kiosko2-backend
sudo systemctl status kiosko2-frontend

# View logs
journalctl -u kiosko2-backend -f
journalctl -u kiosko2-frontend -f
```

## Remote E2E Testing

### Setup

1. Enable test endpoints in `.env`:
   ```bash
   KIOSKO_ENABLE_TEST_ENDPOINTS=true
   KIOSKO_API_KEY=your-test-api-key
   ```

2. Restart backend:
   ```bash
   sudo systemctl restart kiosko2-backend
   ```

### Running Tests

From Windows (Git Bash) or Linux:

```bash
# Set environment
export KIOSKO_REMOTE_URL=http://192.168.1.100:8000
export KIOSKO_TEST_API_KEY=your-test-api-key

# Run tests
cd kiosko2/scripts
./test_remote.sh
```

Or with arguments:
```bash
./test_remote.sh http://192.168.1.100:8000 your-test-api-key
```

## Security Considerations

### Production Checklist

1. **Disable test endpoints:**
   ```bash
   KIOSKO_ENABLE_TEST_ENDPOINTS=false
   ```

2. **Use strong secrets:**
   - Generate random API key: `openssl rand -hex 32`
   - Generate Flask secret: `python3 -c "import secrets; print(secrets.token_hex(32))"`

3. **Firewall configuration:**
   ```bash
   # Allow only local network access
   sudo ufw allow from 192.168.1.0/24 to any port 5000
   sudo ufw allow from 192.168.1.0/24 to any port 8000
   ```

4. **MQTT security:**
   ```bash
   # /etc/mosquitto/conf.d/kiosko.conf
   listener 1883 localhost  # Only allow local connections
   allow_anonymous false
   password_file /etc/mosquitto/passwd
   ```

5. **SSL/TLS (optional):**
   Consider using nginx as a reverse proxy with SSL certificates.

## Troubleshooting

### Service won't start

```bash
# Check service status
sudo systemctl status kiosko2-backend

# Check logs for errors
journalctl -u kiosko2-backend -n 100 --no-pager

# Common issues:
# - Missing .venv: Create with `python3 -m venv .venv`
# - Permission issues: Check file ownership
# - Port in use: Check with `lsof -i :8000`
```

### MQTT connection failed

```bash
# Check Mosquitto status
sudo systemctl status mosquitto

# Test MQTT locally
mosquitto_sub -t '#' -v  # Subscribe to all topics
mosquitto_pub -t 'test' -m 'hello'  # Publish test message
```

### Database errors

```bash
# Check database file permissions
ls -la ~/verticalparking/kiosko2/data/

# Reset database (WARNING: deletes all data)
rm ~/verticalparking/kiosko2/data/kiosko.db
sudo systemctl restart kiosko2-backend
```

### Frontend can't reach backend

```bash
# Check backend is running
curl http://localhost:8000/api/v1/health

# Check KIOSKO_BACKEND_URL environment variable
# Ensure it's set correctly in the frontend service
```

## Rollback

If deployment fails, restore from backup:

```bash
# List available backups
ls -la ~/backups/

# Restore a backup
cd ~/verticalparking
rm -rf kiosko2
tar -xzvf ~/backups/kiosko2_YYYYMMDD_HHMMSS.tar.gz

# Restart services
sudo systemctl restart kiosko2-backend kiosko2-frontend
```

## Monitoring

### Health Endpoints

- Backend: `http://PI_IP:8000/api/v1/health`
- Frontend: `http://PI_IP:5000/`

### Prometheus Metrics (Optional)

Add to `requirements.txt`:
```
prometheus-fastapi-instrumentator
```

Enable in `main.py`:
```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

## Contact & Support

For issues, please open a GitHub issue or contact the development team.
