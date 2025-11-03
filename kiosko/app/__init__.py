"""
Flask application factory and extensions setup.
Initializes DB, blueprints, sessions, and Swagger docs.
"""
from flask import Flask
from flasgger import Swagger
from .database import init_db
from .routes import bp as routes_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    # Use a simple secret key for sessions; override via env in production.
    app.config["SECRET_KEY"] = "change-this-in-production"

    # Initialize database and ensure tables exist
    with app.app_context():
        init_db()

    # Swagger configuration (served at /apidocs/)
    app.config["SWAGGER"] = {
        "title": "Kiosko POS API",
        "uiversion": 3,
    }
    Swagger(app)

    # Blueprints
    app.register_blueprint(routes_bp)

    return app

