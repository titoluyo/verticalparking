"""
SQLite database helpers.
Stores registros table in kiosko.db at the repo root.
"""
import sqlite3
from pathlib import Path
from typing import Iterable, Optional, Tuple
from flask import g


DB_PATH = Path(__file__).resolve().parent.parent / "kiosko.db"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e: Optional[BaseException] = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Initialize database with all required tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    try:
        cur = db.cursor()
        
        # Existing registros table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                placa TEXT NOT NULL,
                creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Tickets table - stores parking tickets with QR tokens
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
        
        # Cabinas table - stores cabin status (01-07)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cabinas (
                id TEXT PRIMARY KEY,
                estado TEXT NOT NULL DEFAULT 'free' CHECK(estado IN ('free', 'busy')),
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create index on token for fast lookups
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tickets_token ON tickets(token)
            """
        )
        
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tickets_cabina ON tickets(cabina_id)
            """
        )
        
        db.commit()
        
        # Initialize cabinas 01-06 if they don't exist
        for i in range(1, 7):
            cabina_id = f"CABINA-{i:02d}"
            cur.execute(
                """
                INSERT OR IGNORE INTO cabinas (id, estado) VALUES (?, 'free')
                """,
                (cabina_id,)
            )
        
        db.commit()
    finally:
        db.close()


def query(sql: str, params: Tuple = ()) -> Iterable[sqlite3.Row]:
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def execute(sql: str, params: Tuple = ()) -> int:
    cur = get_db().execute(sql, params)
    get_db().commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


# Ticket management functions
def create_ticket(token: str, cabina_id: str, vehicle_plate: Optional[str] = None) -> int:
    """Create a new parking ticket.
    
    Args:
        token: Unique token for QR code
        cabina_id: Cabin ID where vehicle is stored
        vehicle_plate: Optional vehicle license plate
        
    Returns:
        Ticket ID
    """
    return execute(
        """
        INSERT INTO tickets (token, cabina_id, vehicle_plate, status)
        VALUES (?, ?, ?, 'active')
        """,
        (token, cabina_id, vehicle_plate)
    )


def get_ticket_by_token(token: str) -> Optional[sqlite3.Row]:
    """Get ticket by token.
    
    Returns:
        Ticket row or None if not found
    """
    rows = list(query("SELECT * FROM tickets WHERE token = ?", (token,)))
    return rows[0] if rows else None


# Cabin management functions
def get_cabin(cabina_id: str) -> Optional[sqlite3.Row]:
    """Get cabin by ID.
    
    Returns:
        Cabin row or None if not found
    """
    rows = list(query("SELECT * FROM cabinas WHERE id = ?", (cabina_id,)))
    return rows[0] if rows else None


def update_cabin_status(cabina_id: str, estado: str) -> bool:
    """Update cabin status.
    
    Args:
        cabina_id: Cabin ID
        estado: 'free' or 'busy'
        
    Returns:
        True if successful
    """
    try:
        execute(
            """
            UPDATE cabinas SET estado = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (estado, cabina_id)
        )
        return True
    except Exception:
        return False


def find_free_cabin() -> Optional[str]:
    """Find the first available free cabin.
    
    Returns:
        Cabin ID or None if no free cabins
    """
    rows = list(query(
        """
        SELECT id FROM cabinas 
        WHERE estado = 'free' 
        ORDER BY id ASC
        LIMIT 1
        """
    ))
    return rows[0]["id"] if rows else None


def get_all_cabins() -> Iterable[sqlite3.Row]:
    """Get all cabins ordered by ID.
    
    Returns:
        Iterable of cabin rows
    """
    return query("SELECT * FROM cabinas ORDER BY id ASC")


# Cleanup functions
def cleanup_tickets() -> int:
    """Delete all tickets from the database.
    
    Returns:
        Number of tickets deleted
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) as count FROM tickets")
    count = cur.fetchone()["count"]
    cur.execute("DELETE FROM tickets")
    db.commit()
    cur.close()
    return count


def reset_cabins() -> int:
    """Reset all cabins to 'free' status.
    
    Returns:
        Number of cabins updated
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE cabinas SET estado = 'free', updated_at = CURRENT_TIMESTAMP")
    db.commit()
    count = cur.rowcount
    cur.close()
    return count


def cleanup_all() -> dict:
    """Clean up all data: delete tickets and reset cabins.
    
    Returns:
        Dictionary with counts of deleted tickets and reset cabins
    """
    tickets_count = cleanup_tickets()
    cabins_count = reset_cabins()
    return {
        "tickets_deleted": tickets_count,
        "cabins_reset": cabins_count
    }
