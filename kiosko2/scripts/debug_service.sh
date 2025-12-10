#!/bin/bash
#
# Debug script for kiosko2 services
# Run this on the Raspberry Pi to diagnose service issues
#

SERVICE_NAME="${1:-kiosko2-frontend}"

echo "=== Debugging $SERVICE_NAME ==="
echo ""

# Check service status
echo "1. Service Status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l
echo ""

# Check recent logs
echo "2. Recent Logs (last 50 lines):"
sudo journalctl -u "$SERVICE_NAME" -n 50 --no-pager
echo ""

# Check if port is in use
if [ "$SERVICE_NAME" = "kiosko2-frontend" ]; then
    PORT=5000
elif [ "$SERVICE_NAME" = "kiosko2-backend" ]; then
    PORT=8000
else
    PORT="unknown"
fi

if [ "$PORT" != "unknown" ]; then
    echo "3. Checking if port $PORT is in use:"
    sudo lsof -i :$PORT || echo "Port $PORT is not in use"
    echo ""
fi

# Check service file
echo "4. Service File Content:"
cat /etc/systemd/system/${SERVICE_NAME}.service
echo ""

# Try to run manually
if [ "$SERVICE_NAME" = "kiosko2-frontend" ]; then
    DEPLOY_DIR="/home/${USER}/verticalparking_deploy"
    echo "5. Testing manual execution:"
    echo "   Working directory: $DEPLOY_DIR/kiosko2/src/frontend"
    if [ -d "$DEPLOY_DIR/kiosko2/src/frontend" ]; then
        cd "$DEPLOY_DIR/kiosko2/src/frontend"
        if [ -d ".venv" ]; then
            echo "   Activating virtual environment..."
            source .venv/bin/activate
            echo "   Testing imports..."
            python3 -c "from app import create_app; app = create_app(); print('✓ App created successfully')" || echo "✗ Import failed"
            echo "   Testing gunicorn..."
            .venv/bin/gunicorn --check-config app:app || echo "✗ Gunicorn config check failed"
            deactivate
        else
            echo "   ✗ Virtual environment not found at .venv"
        fi
    else
        echo "   ✗ Frontend directory not found"
    fi
fi

echo ""
echo "=== Debug complete ==="

