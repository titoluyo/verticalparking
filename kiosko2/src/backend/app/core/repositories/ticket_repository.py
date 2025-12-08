"""SQLite implementation of ticket repository."""

import sqlite3
from datetime import datetime
from typing import Optional
from pathlib import Path

from ..interfaces.repositories import ITicketRepository
from ..models import Ticket, TicketStatus


class SQLiteTicketRepository(ITicketRepository):
    """SQLite implementation of ITicketRepository."""
    
    def __init__(self, db_path: Path):
        """Initialize repository with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def create(self, token: str, cabina_id: str, vehicle_plate: Optional[str] = None) -> int:
        """Create a new ticket."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO tickets (token, cabina_id, vehicle_plate, status)
                VALUES (?, ?, ?, 'active')
                """,
                (token, cabina_id, vehicle_plate)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    
    def get_by_token(self, token: str) -> Optional[Ticket]:
        """Get ticket by token."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM tickets WHERE token = ?", (token,))
            row = cur.fetchone()
            if row:
                return self._row_to_ticket(row)
            return None
        finally:
            conn.close()
    
    def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        """Get ticket by ID."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            row = cur.fetchone()
            if row:
                return self._row_to_ticket(row)
            return None
        finally:
            conn.close()
    
    def has_active_ticket(self, cabina_id: str) -> bool:
        """Check if a cabin has an active ticket."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM tickets WHERE cabina_id = ? AND status = 'active' LIMIT 1",
                (cabina_id,)
            )
            return cur.fetchone() is not None
        finally:
            conn.close()
    
    def complete_ticket(self, token: str) -> bool:
        """Mark a ticket as completed."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE tickets 
                SET status = 'completed', exit_timestamp = CURRENT_TIMESTAMP
                WHERE token = ? AND status = 'active'
                """,
                (token,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    
    def delete_all(self) -> int:
        """Delete all tickets."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as count FROM tickets")
            count = cur.fetchone()["count"]
            cur.execute("DELETE FROM tickets")
            conn.commit()
            return count
        finally:
            conn.close()
    
    def _row_to_ticket(self, row: sqlite3.Row) -> Ticket:
        """Convert database row to Ticket model."""
        entry_ts = row["entry_timestamp"]
        exit_ts = row["exit_timestamp"]
        
        # Parse datetime strings
        if isinstance(entry_ts, str):
            entry_ts = datetime.fromisoformat(entry_ts.replace("Z", "+00:00"))
        if isinstance(exit_ts, str):
            exit_ts = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
        
        return Ticket(
            id=row["id"],
            token=row["token"],
            cabina_id=row["cabina_id"],
            entry_timestamp=entry_ts,
            exit_timestamp=exit_ts,
            vehicle_plate=row["vehicle_plate"],
            status=TicketStatus(row["status"]),
        )


class InMemoryTicketRepository(ITicketRepository):
    """In-memory implementation of ITicketRepository for testing."""
    
    def __init__(self):
        self._tickets: dict[int, dict] = {}
        self._next_id = 1
    
    def create(self, token: str, cabina_id: str, vehicle_plate: Optional[str] = None) -> int:
        ticket_id = self._next_id
        self._next_id += 1
        self._tickets[ticket_id] = {
            "id": ticket_id,
            "token": token,
            "cabina_id": cabina_id,
            "entry_timestamp": datetime.now(),
            "exit_timestamp": None,
            "vehicle_plate": vehicle_plate,
            "status": TicketStatus.ACTIVE,
        }
        return ticket_id
    
    def get_by_token(self, token: str) -> Optional[Ticket]:
        for ticket in self._tickets.values():
            if ticket["token"] == token:
                return Ticket(**ticket)
        return None
    
    def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        if ticket_id in self._tickets:
            return Ticket(**self._tickets[ticket_id])
        return None
    
    def has_active_ticket(self, cabina_id: str) -> bool:
        for ticket in self._tickets.values():
            if ticket["cabina_id"] == cabina_id and ticket["status"] == TicketStatus.ACTIVE:
                return True
        return False
    
    def complete_ticket(self, token: str) -> bool:
        for ticket in self._tickets.values():
            if ticket["token"] == token and ticket["status"] == TicketStatus.ACTIVE:
                ticket["status"] = TicketStatus.COMPLETED
                ticket["exit_timestamp"] = datetime.now()
                return True
        return False
    
    def delete_all(self) -> int:
        count = len(self._tickets)
        self._tickets.clear()
        return count
