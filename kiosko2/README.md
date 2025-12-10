# Kiosko2 - Vertical Parking System

A modular, SOLID-compliant parking management system with a FastAPI backend and Flask frontend.

## Architecture

```
kiosko2/
├── src/
│   ├── backend/              # FastAPI backend service
│   │   ├── app/
│   │   │   ├── main.py       # FastAPI app entry point
│   │   │   ├── api/v1/       # API routes
│   │   │   ├── core/         # Business logic (SOLID)
│   │   │   │   ├── services/ # Business services
│   │   │   │   ├── repositories/ # Data access layer
│   │   │   │   ├── models/   # Domain models
│   │   │   │   └── interfaces/ # Abstract interfaces
│   │   │   └── infrastructure/ # External integrations
│   │   ├── tests/            # Unit & integration tests
│   │   └── requirements.txt
│   │
│   └── frontend/             # Flask frontend (thin UI layer)
│       ├── app/
│       │   ├── routes.py     # UI routes
│       │   ├── static/       # CSS, JS
│       │   └── templates/    # Jinja2 templates
│       └── requirements.txt
│
├── scripts/                  # Deployment scripts
│   ├── deploy.sh            # Manual deployment script
│   ├── setup_pi.sh          # Raspberry Pi setup
│   ├── setup_github_runner_windows.ps1  # GitHub Actions runner (Windows)
│   ├── setup_github_runner_linux.sh     # GitHub Actions runner (Linux)
│   └── test_remote.sh       # Remote E2E testing
│
└── docs/
    └── DEPLOYMENT.md        # Deployment documentation
```

## Quick Start

### Backend Development

```bash
cd src/backend
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Run backend
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v
```

### Frontend Development

```bash
cd src/frontend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set backend URL
export KIOSKO_BACKEND_URL=http://localhost:8000

# Run frontend
python app.py
```

### Access Points

- **Backend API**: http://localhost:8000/api/v1
- **API Documentation**: http://localhost:8000/api/docs
- **Frontend UI**: http://localhost:5000

## Key Features

### SOLID Principles

- **Single Responsibility**: Each service handles one domain
- **Open/Closed**: Dependency injection for extensibility
- **Liskov Substitution**: Interface-based repositories
- **Interface Segregation**: Small, focused interfaces
- **Dependency Inversion**: Services depend on abstractions

### Testing Strategy

- **Unit Tests**: Services with mocked dependencies
- **Integration Tests**: API endpoints with test database
- **E2E Tests**: Protected endpoints for remote testing

### Deployment

- GitHub Actions CI/CD with self-hosted runner (works with private IPs)
- Automated deployment on push to `main` branch
- Systemd service management
- Automated rollback support

## Configuration

Environment variables (see `.env.template`):

```bash
# Backend
KIOSKO_DATABASE_PATH=./kiosko.db
KIOSKO_MQTT_BROKER=127.0.0.1
KIOSKO_API_KEY=your-secret-key
KIOSKO_ENABLE_TEST_ENDPOINTS=true

# Frontend
KIOSKO_BACKEND_URL=http://localhost:8000
FLASK_SECRET_KEY=your-flask-secret
```

## API Endpoints

### Tickets
- `POST /api/v1/tickets/` - Create ticket
- `GET /api/v1/tickets/{token}` - Get ticket
- `POST /api/v1/tickets/scan` - Scan QR code
- `POST /api/v1/tickets/{token}/complete` - Complete ticket

### Cabins
- `GET /api/v1/cabins/` - List all cabins
- `GET /api/v1/cabins/{id}` - Get cabin
- `POST /api/v1/cabins/active` - Set active cabin
- `POST /api/v1/cabins/{id}/floor-level` - Set floor level
- `POST /api/v1/cabins/{id}/calibrate/start` - Start calibration

### Health
- `GET /api/v1/health` - Health check
- `GET /api/v1/ready` - Readiness probe
- `GET /api/v1/live` - Liveness probe

### Test (Protected)
- `GET /api/v1/test/ping` - Verify API key
- `POST /api/v1/test/cleanup` - Reset database
- `POST /api/v1/test/store-vehicle` - Test store
- `POST /api/v1/test/retrieve-vehicle` - Test retrieve

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions.

### GitHub Actions (Recommended)

**Option A: Using Docker (Easiest)**

1. **Get registration token:**
   - Go to: `https://github.com/<USERNAME>/verticalparking/settings/actions/runners/new`
   - Copy the registration token

2. **Run Docker setup:**
   ```powershell
   # Windows
   cd kiosko2\scripts
   .\setup_github_runner_docker.ps1 -RepoOwner <USERNAME> -RepoName verticalparking
   ```
   ```bash
   # Linux/Mac/WSL
   cd kiosko2/scripts
   chmod +x setup_github_runner_docker.sh
   ./setup_github_runner_docker.sh <USERNAME> verticalparking
   ```

**Option B: Native Installation**

1. **Get registration token** (same as above)

2. **Setup SSH key for Pi access:**
   ```bash
   ssh-keygen -t ed25519 -C "github-actions-runner"
   ssh-copy-id -i ~/.ssh/id_ed25519.pub pi@192.168.10.50
   ```

3. **Setup runner:**
   ```powershell
   # Windows
   cd kiosko2\scripts
   .\setup_github_runner_windows.ps1 -GitHubToken <REGISTRATION_TOKEN> -RepoOwner <USERNAME> -RepoName verticalparking
   ```
   ```bash
   # Linux
   cd kiosko2/scripts
   ./setup_github_runner_linux.sh <REGISTRATION_TOKEN> <USERNAME> verticalparking
   ```

3. **Configure GitHub Secrets:**
   - `PI_HOST`: `192.168.10.50`
   - `PI_USER`: `pi`
   - `PI_SSH_KEY`: Your private SSH key content
   - `PI_SSH_PORT`: `22` (optional)

4. **One-time setup on Raspberry Pi:**
   ```bash
   # SSH into Pi and run:
   curl -sSL https://raw.githubusercontent.com/titoluyo/verticalparking/main/kiosko2/scripts/setup_services.sh | bash
   ```
   This configures systemd services (only needed once).

5. **Automatic deployment:**
   - Push to `main` branch → Tests run → Auto-deploy to Pi via SSH
   - Works even if Pi is on private network (192.168.x.x)

### Manual Deployment

```bash
# From Windows/Linux development machine
export PI_HOST=192.168.1.100
export PI_USER=pi
./scripts/deploy.sh
```

## License

See LICENSE file in the root repository.
