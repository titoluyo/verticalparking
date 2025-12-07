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
        
        # Cabinas table - stores cabin status (01-06)
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
        
        # Add minimum_distance column if it doesn't exist (for existing databases)
        cur.execute(
            """
            SELECT COUNT(*) FROM pragma_table_info('cabinas') WHERE name='minimum_distance'
            """
        )
        if cur.fetchone()[0] == 0:
            cur.execute(
                """
                ALTER TABLE cabinas ADD COLUMN minimum_distance INTEGER
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
        
        # Add minimum_distance column if it doesn't exist (for existing databases)
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM pragma_table_info('cabinas') WHERE name='minimum_distance'
                """
            )
            if cur.fetchone()[0] == 0:
                cur.execute(
                    """
                    ALTER TABLE cabinas ADD COLUMN minimum_distance INTEGER
                    """
                )
                db.commit()
        except Exception:
            # Column might already exist or table doesn't exist yet
            pass
        
        # Remove cabin 07 if it exists (no longer used)
        cur.execute("DELETE FROM cabinas WHERE id = 'CABINA-07'")
        
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


def has_active_ticket(cabina_id: str) -> bool:
    """Check if a cabin has an active ticket.
    
    Args:
        cabina_id: Cabin ID to check
        
    Returns:
        True if cabin has an active ticket, False otherwise
    """
    rows = list(query(
        "SELECT id FROM tickets WHERE cabina_id = ? AND status = 'active' LIMIT 1",
        (cabina_id,)
    ))
    has_ticket = len(rows) > 0
    return has_ticket


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


def get_next_cabin_circular(current_cabin_id: str) -> str:
    """Get the next cabin in circular order (01→02→03→04→05→06→01).
    
    Args:
        current_cabin_id: Current cabin ID (e.g., "CABINA-01" or "CABINA-06")
    
    Returns:
        Next cabin ID in circular order (CABINA-06 wraps to CABINA-01)
    """
    # Extract number from cabin ID
    if current_cabin_id.startswith("CABINA-"):
        num_str = current_cabin_id[7:]
    else:
        num_str = current_cabin_id
    
    try:
        cabin_num = int(num_str)
        # Circular: 1-6, wraps 6→1
        next_num = (cabin_num % 6) + 1
        return f"CABINA-{next_num:02d}"
    except (ValueError, TypeError):
        # If can't parse, default to CABINA-01
        return "CABINA-01"


def find_next_free_cabin_circular(start_cabin_id: Optional[str] = None, logger=None) -> Optional[str]:
    """Find the next free cabin in circular order (01→02→03→04→05→06→01).
    
    A cabin is considered free if it has no active ticket, regardless of database estado.
    
    Args:
        start_cabin_id: Cabin ID to start searching from (e.g., "CABINA-03").
                       If None, starts from CABINA-01.
                       Search starts from the NEXT cabin after start_cabin_id.
        logger: Optional logger for debugging
    
    Returns:
        Cabin ID of next free cabin in circular order, or None if no free cabins
    """
    import logging
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Get all cabins ordered by ID
    all_cabins = list(query("SELECT id, estado FROM cabinas ORDER BY id ASC"))
    if not all_cabins:
        logger.warning("No cabins found in database")
        return None
    
    # Extract cabin numbers and create ordered list
    cabin_list = [row["id"] for row in all_cabins]  # ["CABINA-01", "CABINA-02", ...]
    
    # Determine starting index
    start_idx = 0
    if start_cabin_id:
        try:
            start_idx = cabin_list.index(start_cabin_id)
            logger.debug(f"Starting circular search from {start_cabin_id} (index {start_idx})")
        except ValueError:
            # Cabin not found, start from beginning
            logger.warning(f"Start cabin {start_cabin_id} not found, starting from beginning")
            start_idx = 0
    
    # Search circularly: start from start_idx+1 (next cabin), then wrap around
    # Check if each cabin has an active ticket (not just database estado)
    # First pass: from start_idx+1 to end
    for i in range(start_idx + 1, len(cabin_list)):
        cabin_id = cabin_list[i]
        # Check if cabin actually has an active ticket
        has_ticket = has_active_ticket(cabin_id)
        logger.debug(f"Checking {cabin_id}: has_active_ticket={has_ticket}")
        if not has_ticket:
            logger.info(f"Found free cabin: {cabin_id}")
            # Also update database estado to match reality
            update_cabin_status(cabin_id, "free")
            return cabin_id
    
    # Second pass: from beginning to start_idx (wrap around, but skip start_idx itself)
    for i in range(0, start_idx):
        cabin_id = cabin_list[i]
        # Check if cabin actually has an active ticket
        has_ticket = has_active_ticket(cabin_id)
        logger.debug(f"Checking {cabin_id}: has_active_ticket={has_ticket}")
        if not has_ticket:
            logger.info(f"Found free cabin (wrapped): {cabin_id}")
            # Also update database estado to match reality
            update_cabin_status(cabin_id, "free")
            return cabin_id
    
    logger.warning(f"No free cabins found in circular search starting from {start_cabin_id} (all have active tickets)")
    return None


def get_all_cabins() -> Iterable[sqlite3.Row]:
    """Get all cabins ordered by ID.
    
    Returns:
        Iterable of cabin rows
    """
    return query("SELECT * FROM cabinas ORDER BY id ASC")


def update_cabin_minimum_distance(cabina_id: str, minimum_distance: int) -> bool:
    """Update minimum distance for a cabin (floor level).
    
    Args:
        cabina_id: Cabin ID
        minimum_distance: Minimum distance in mm (closest to sensor = floor level)
        
    Returns:
        True if successful
    """
    try:
        execute(
            """
            UPDATE cabinas SET minimum_distance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (minimum_distance, cabina_id)
        )
        return True
    except Exception:
        return False


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
