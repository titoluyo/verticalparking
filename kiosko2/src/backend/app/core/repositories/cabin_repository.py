"""SQLite implementation of cabin repository."""

import sqlite3
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from ..interfaces.repositories import ICabinRepository
from ..models import Cabin, CabinStatus


class SQLiteCabinRepository(ICabinRepository):
    """SQLite implementation of ICabinRepository."""
    
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
    
    def get(self, cabina_id: str) -> Optional[Cabin]:
        """Get cabin by ID."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM cabinas WHERE id = ?", (cabina_id,))
            row = cur.fetchone()
            if row:
                return self._row_to_cabin(row)
            return None
        finally:
            conn.close()
    
    def get_all(self) -> List[Cabin]:
        """Get all cabins ordered by ID."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM cabinas ORDER BY id ASC")
            rows = cur.fetchall()
            return [self._row_to_cabin(row) for row in rows]
        finally:
            conn.close()
    
    def update_status(self, cabina_id: str, estado: CabinStatus) -> bool:
        """Update cabin status."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE cabinas SET estado = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (estado.value, cabina_id)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    
    def update_minimum_distance(self, cabina_id: str, minimum_distance: int) -> bool:
        """Update minimum distance (floor level) for a cabin."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE cabinas SET minimum_distance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (minimum_distance, cabina_id)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    
    def find_free_cabin(self) -> Optional[str]:
        """Find the first available free cabin."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id FROM cabinas 
                WHERE estado = 'free' 
                ORDER BY id ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            return row["id"] if row else None
        finally:
            conn.close()
    
    def reset_all(self) -> int:
        """Reset all cabins to free status."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE cabinas SET estado = 'free', updated_at = CURRENT_TIMESTAMP")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
    
    def _row_to_cabin(self, row: sqlite3.Row) -> Cabin:
        """Convert database row to Cabin model."""
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        
        # Get minimum_distance safely
        try:
            minimum_distance = row["minimum_distance"]
        except (KeyError, IndexError):
            minimum_distance = None
        
        cabin = Cabin(
            id=row["id"],
            estado=CabinStatus(row["estado"]),
            minimum_distance=minimum_distance,
            updated_at=updated_at,
        )
        # Set MQTT ID
        cabin.id_mqtt = Cabin.db_id_to_mqtt(cabin.id)
        return cabin


class InMemoryCabinRepository(ICabinRepository):
    """In-memory implementation of ICabinRepository for testing."""
    
    def __init__(self):
        self._cabins: dict[str, dict] = {}
        # Initialize with default cabins
        for i in range(1, 7):
            cabin_id = f"CABINA-{i:02d}"
            self._cabins[cabin_id] = {
                "id": cabin_id,
                "estado": CabinStatus.FREE,
                "minimum_distance": None,
                "updated_at": datetime.now(),
            }
    
    def get(self, cabina_id: str) -> Optional[Cabin]:
        if cabina_id in self._cabins:
            data = self._cabins[cabina_id]
            cabin = Cabin(**data)
            cabin.id_mqtt = Cabin.db_id_to_mqtt(cabin.id)
            return cabin
        return None
    
    def get_all(self) -> List[Cabin]:
        cabins = []
        for cabin_id in sorted(self._cabins.keys()):
            data = self._cabins[cabin_id]
            cabin = Cabin(**data)
            cabin.id_mqtt = Cabin.db_id_to_mqtt(cabin.id)
            cabins.append(cabin)
        return cabins
    
    def update_status(self, cabina_id: str, estado: CabinStatus) -> bool:
        if cabina_id in self._cabins:
            self._cabins[cabina_id]["estado"] = estado
            self._cabins[cabina_id]["updated_at"] = datetime.now()
            return True
        return False
    
    def update_minimum_distance(self, cabina_id: str, minimum_distance: int) -> bool:
        if cabina_id in self._cabins:
            self._cabins[cabina_id]["minimum_distance"] = minimum_distance
            self._cabins[cabina_id]["updated_at"] = datetime.now()
            return True
        return False
    
    def find_free_cabin(self) -> Optional[str]:
        for cabin_id in sorted(self._cabins.keys()):
            if self._cabins[cabin_id]["estado"] == CabinStatus.FREE:
                return cabin_id
        return None
    
    def reset_all(self) -> int:
        count = 0
        for cabin_id in self._cabins:
            self._cabins[cabin_id]["estado"] = CabinStatus.FREE
            self._cabins[cabin_id]["updated_at"] = datetime.now()
            count += 1
        return count
