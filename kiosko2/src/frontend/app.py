"""Flask frontend entry point (WSGI)."""

import os
from app import create_app

# WSGI application entry point for gunicorn
application = create_app()
app = application  # Alias for compatibility

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    application.run(host="0.0.0.0", port=port, debug=debug)
