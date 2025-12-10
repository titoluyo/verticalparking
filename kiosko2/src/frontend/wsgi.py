"""Flask frontend WSGI entry point for gunicorn."""

from app import create_app

# WSGI application entry point
application = create_app()
app = application  # Alias for compatibility

