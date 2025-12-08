"""Configuration management for the backend service."""

import os
from pathlib import Path
from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "Kiosko2 Backend"
    debug: bool = False
    environment: str = "development"
    
    # Database
    database_path: Path = Path("kiosko.db")
    
    # API Security
    api_key: Optional[str] = None  # For test endpoints
    enable_test_endpoints: bool = True
    
    # MQTT Configuration
    mqtt_broker: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_user: Optional[str] = None
    mqtt_password: Optional[str] = None
    topic_base: str = "parking"
    site_id: str = "garage-01"
    
    # Cabins
    cabins: str = "cabina-01,cabina-02,cabina-03,cabina-04,cabina-05,cabina-06"
    
    # Printer Configuration
    printer_enabled: bool = True
    printer_vendor_id: Optional[str] = None
    printer_product_id: Optional[str] = None
    printer_serial: Optional[str] = None
    printer_baudrate: int = 9600
    
    # Video/Camera Configuration
    video_enabled: bool = True
    camera_resolution_width: int = 640
    camera_resolution_height: int = 480
    camera_framerate: int = 30
    
    # CORS
    cors_origins: str = "*"
    
    class Config:
        env_prefix = "KIOSKO_"
        env_file = ".env"
        extra = "ignore"
    
    @property
    def cabin_list(self) -> list[str]:
        """Get list of cabin IDs."""
        return [c.strip() for c in self.cabins.split(",") if c.strip()]
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Get list of CORS origins."""
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def init_database(db_path: Path) -> None:
    """Initialize database with required tables.
    
    Args:
        db_path: Path to SQLite database file
    """
    import sqlite3
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    
    try:
        cur = conn.cursor()
        
        # Tickets table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                cabina_id TEXT NOT NULL,
                entry_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                exit_timestamp DATETIME,
                vehicle_plate TEXT,
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'cancelled'))
            )
            """
        )
        
        # Cabinas table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cabinas (
                id TEXT PRIMARY KEY,
                estado TEXT NOT NULL DEFAULT 'free' CHECK(estado IN ('free', 'busy')),
                minimum_distance INTEGER,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tickets_token ON tickets(token)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tickets_cabina ON tickets(cabina_id)")
        
        conn.commit()
        
        # Initialize cabinas 01-06
        for i in range(1, 7):
            cabina_id = f"CABINA-{i:02d}"
            cur.execute(
                "INSERT OR IGNORE INTO cabinas (id, estado) VALUES (?, 'free')",
                (cabina_id,)
            )
        
        conn.commit()
    finally:
        conn.close()
