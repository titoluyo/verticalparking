"""
Main entry point for the Kiosko POS Flask app.
Compatible with Windows 11 and Raspberry Pi OS.
"""
from app import create_app
import os


def _get_port() -> int:
    try:
        return int(os.getenv("PORT", "5000"))
    except ValueError:
        return 5000


app = create_app()


if __name__ == "__main__":
    # Bind to 0.0.0.0 to allow LAN access; default port 5000 for dev.
    # Use `PORT` env to override.
    app.run(host="0.0.0.0", port=_get_port())

