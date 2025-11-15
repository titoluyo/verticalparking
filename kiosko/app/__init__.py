"""
Flask application factory and extensions setup.
Initializes DB, blueprints, sessions, and Swagger docs.
"""
import logging
from flask import Flask
from flasgger import Swagger
from .database import init_db
from .routes import bp as routes_bp
from .api import bp as api_bp
from .presence import presence_service_from_env


def create_app() -> Flask:
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    # Use a simple secret key for sessions; override via env in production.
    app.config["SECRET_KEY"] = "change-this-in-production"

    # Configure logging to show INFO level and above (includes MQTT connection logs)
    app.logger.setLevel(logging.INFO)
    # Enable paho-mqtt library logging
    logging.getLogger("paho.mqtt.client").setLevel(logging.INFO)

    # Initialize database and ensure tables exist
    with app.app_context():
        init_db()

    # Swagger configuration (served at /apidocs/)
    app.config["SWAGGER"] = {
        "title": "Kiosko POS API",
        "uiversion": 3,
    }
    Swagger(app)

    # Background presence service (MQTT -> in-memory cache)
    try:
        app.logger.info("Starting presence service...")
        presence_service = presence_service_from_env(app.logger)
        presence_service.start()
        app.config["PRESENCE_SERVICE"] = presence_service
        app.logger.info("Presence service started.")
    except Exception as exc:
        # Keep app running even if MQTT is misconfigured; surface via API later.
        app.logger.warning("Presence service not started: %s", exc)
        app.config["PRESENCE_SERVICE"] = None

    # Blueprints
    app.register_blueprint(routes_bp)
    app.register_blueprint(api_bp)

    return app
