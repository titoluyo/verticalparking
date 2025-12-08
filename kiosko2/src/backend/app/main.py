"""
Kiosko2 Backend - FastAPI Application Entry Point.

A modular, SOLID-compliant backend for the vertical parking system.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings, init_database
from .dependencies import (
    set_presence_service,
    set_motor_service,
    set_printer_service,
)
from .api.v1 import api_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("kiosko2")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    settings = get_settings()
    
    # Startup
    logger.info("Starting Kiosko2 Backend...")
    
    # Initialize database
    logger.info(f"Initializing database: {settings.database_path}")
    init_database(settings.database_path)
    
    # Initialize presence service
    try:
        from .infrastructure.mqtt import PresenceService
        
        presence_service = PresenceService(
            broker=settings.mqtt_broker,
            port=settings.mqtt_port,
            username=settings.mqtt_user,
            password=settings.mqtt_password,
            cabins=settings.cabin_list,
            topic_base=settings.topic_base,
            site=settings.site_id,
            logger=logger,
        )
        presence_service.start()
        set_presence_service(presence_service)
        logger.info("Presence service started")
    except Exception as e:
        logger.warning(f"Presence service not started: {e}")
    
    # Initialize motor control service
    try:
        from .infrastructure.mqtt import MotorControlService
        
        motor_service = MotorControlService(
            broker=settings.mqtt_broker,
            port=settings.mqtt_port,
            username=settings.mqtt_user,
            password=settings.mqtt_password,
            site=settings.site_id,
            topic_base=settings.topic_base,
            logger=logger,
        )
        set_motor_service(motor_service)
        logger.info("Motor control service initialized")
    except Exception as e:
        logger.warning(f"Motor control service not initialized: {e}")
    
    # Initialize printer service (placeholder - import actual implementation)
    # For now, printer service is optional
    set_printer_service(None)
    logger.info("Printer service: not configured")
    
    logger.info("Kiosko2 Backend started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Kiosko2 Backend...")
    
    # Stop presence service
    from .dependencies import get_presence_service
    presence = get_presence_service()
    if presence:
        presence.stop()
        logger.info("Presence service stopped")
    
    logger.info("Kiosko2 Backend shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="Backend API for the Kiosko2 vertical parking system",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": settings.app_name,
            "version": "2.0.0",
            "docs": "/api/docs",
        }
    
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
