"""
Kiosko2 Frontend - Flask Application Factory.

A thin UI layer that delegates business logic to the FastAPI backend.
"""

import os
import logging
from flask import Flask

from .routes import bp as routes_bp
from .api_client import BackendClient


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    
    # Configuration
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-in-production")
    app.config["BACKEND_URL"] = os.getenv("KIOSKO_BACKEND_URL", "http://localhost:8000")
    
    # Configure logging
    app.logger.setLevel(logging.INFO)
    
    # Initialize backend client
    backend_client = BackendClient(app.config["BACKEND_URL"])
    app.config["BACKEND_CLIENT"] = backend_client
    
    # Register blueprints
    app.register_blueprint(routes_bp)
    
    app.logger.info(f"Flask frontend initialized, backend URL: {app.config['BACKEND_URL']}")
    
    return app
