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
from .printer import PrinterService
from .video_stream import VideoStreamService
from .qr_detector import QRDetector
from .motor_control import MotorControlService


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
    
    # Printer service (thermal printer for tickets)
    try:
        app.logger.info("Initializing printer service...")
        printer_service = PrinterService.from_env(app.logger)
        app.config["PRINTER_SERVICE"] = printer_service
        status = printer_service.get_status()
        app.logger.info("Printer service initialized: status=%s, available=%s", status["status"], status["available"])
    except Exception as exc:
        # Keep app running even if printer is unavailable; surface via API later.
        app.logger.warning("Printer service not initialized: %s", exc)
        app.config["PRINTER_SERVICE"] = None
    
    # Camera service removed - using VideoStreamService (picamera2) for video streaming
    # QR code detection can be done client-side or via separate service if needed
    app.config["CAMERA_SERVICE"] = None
    
    # Video stream service (MJPEG streaming)
    try:
        app.logger.info("Initializing video stream service...")
        video_stream_service = VideoStreamService.from_env(app.logger)
        app.config["VIDEO_STREAM_SERVICE"] = video_stream_service
        status = video_stream_service.get_status()
        app.logger.info("Video stream service initialized: available=%s, enabled=%s, resolution=%s", 
                       status.get("available"), status.get("enabled"), status.get("resolution"))
        if not status.get("available"):
            app.logger.warning("Video stream service initialized but not available - check camera connection and picamera2 installation")
    except Exception as exc:
        # Keep app running even if video stream is unavailable; surface via API later.
        app.logger.error("Video stream service not initialized: %s", exc, exc_info=True)
        app.config["VIDEO_STREAM_SERVICE"] = None
    
    # QR code detector
    try:
        app.logger.info("Initializing QR detector...")
        qr_detector = QRDetector(app.logger)
        app.config["QR_DETECTOR"] = qr_detector
        if qr_detector.is_available():
            app.logger.info("QR detector initialized successfully")
        else:
            app.logger.warning("QR detector initialized but not available - check pyzbar and Pillow installation")
    except Exception as exc:
        app.logger.error("QR detector not initialized: %s", exc, exc_info=True)
        app.config["QR_DETECTOR"] = None
    
    # Motor control service (initialized after presence service since it needs MQTT config)
    try:
        presence_service = app.config.get("PRESENCE_SERVICE")
        if presence_service:
            app.logger.info("Initializing motor control service...")
            motor_service = MotorControlService(
                broker=presence_service.broker,
                port=presence_service.port,
                username=presence_service.username,
                password=presence_service.password,
                site=presence_service.site or "garage-01",
                topic_base=presence_service.topic_base or "parking",
                logger=app.logger
            )
            app.config["MOTOR_CONTROL_SERVICE"] = motor_service
            app.logger.info("Motor control service initialized successfully")
        else:
            app.logger.warning("Motor control service not initialized - presence service unavailable")
            app.config["MOTOR_CONTROL_SERVICE"] = None
    except Exception as exc:
        app.logger.error("Motor control service not initialized: %s", exc, exc_info=True)
        app.config["MOTOR_CONTROL_SERVICE"] = None

    # Blueprints
    app.register_blueprint(routes_bp)
    app.register_blueprint(api_bp)

    return app
