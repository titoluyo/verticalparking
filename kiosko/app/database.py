"""
SQLite database helpers.
Stores usuarios and registros tables in kiosko.db at repo root.
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
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    try:
        cur = db.cursor()
        # Usuarios table for simple auth
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        # Registros table (basic parking records)
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

