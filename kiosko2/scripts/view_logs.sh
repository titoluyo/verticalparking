#!/bin/bash
#
# View live logs for kiosko2 services
# Usage:
#   ./view_logs.sh [backend|frontend|both]
#

SERVICE="${1:-both}"

case "$SERVICE" in
    backend)
        echo "Viewing live logs for kiosko2-backend..."
        sudo journalctl -u kiosko2-backend -f
        ;;
    frontend)
        echo "Viewing live logs for kiosko2-frontend..."
        sudo journalctl -u kiosko2-frontend -f
        ;;
    both|*)
        echo "Viewing live logs for both services (press Ctrl+C to exit)..."
        echo ""
        # Use journalctl to follow both services
        sudo journalctl -u kiosko2-backend -u kiosko2-frontend -f
        ;;
esac

