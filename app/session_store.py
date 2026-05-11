"""Pluggable session storage: in-memory (default) or SQLite for multi-worker / persistence."""
from __future__ import annotations

import base64
import hashlib
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet

_SESSION_TTL = timedelta(hours=24)


def _fernet(secret_key: str) -> Fernet:
    raw = hashlib.sha256(secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


class SessionStore(ABC):
    """Stores WinRM credentials keyed by opaque session id."""

    ttl: timedelta = _SESSION_TTL

    @abstractmethod
    def create_session(self, username: str, password: str) -> str:
        ...

    @abstractmethod
    def get_session_credentials(self, session_id: str) -> tuple[str, str] | None:
        ...

    @abstractmethod
    def drop_session(self, session_id: str) -> None:
        ...


class MemorySessionStore(SessionStore):
    _sessions: dict[str, dict]

    def __init__(self) -> None:
        self._sessions = {}

    def _expire_old_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        for sid, data in list(self._sessions.items()):
            if now - data["created_at"] > self.ttl:
                del self._sessions[sid]

    def create_session(self, username: str, password: str) -> str:
        self._expire_old_sessions()
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "username": username,
            "password": password,
            "created_at": datetime.now(timezone.utc),
        }
        return session_id

    def get_session_credentials(self, session_id: str) -> tuple[str, str] | None:
        self._expire_old_sessions()
        data = self._sessions.get(session_id)
        if not data:
            return None
        if datetime.now(timezone.utc) - data["created_at"] > self.ttl:
            del self._sessions[session_id]
            return None
        return data["username"], data["password"]

    def drop_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class SQLiteSessionStore(SessionStore):
    """SQLite-backed sessions (passwords encrypted at rest). Shared file works across uvicorn workers."""

    def __init__(self, db_path: str, secret_key: str) -> None:
        self._path = Path(db_path)
        self._fernet = _fernet(secret_key)
        self._lock = threading.Lock()

    def init_db(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    password_enc BLOB NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self._path),
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        return conn

    def _expire_old(self, conn: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc) - self.ttl).timestamp()
        conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))

    def create_session(self, username: str, password: str) -> str:
        session_id = str(uuid.uuid4())
        created = datetime.now(timezone.utc).timestamp()
        enc = self._fernet.encrypt(password.encode("utf-8"))
        with self._lock:
            with self._connect() as conn:
                self._expire_old(conn)
                conn.execute(
                    "INSERT INTO sessions (session_id, username, password_enc, created_at) VALUES (?, ?, ?, ?)",
                    (session_id, username, enc, created),
                )
                conn.commit()
        return session_id

    def get_session_credentials(self, session_id: str) -> tuple[str, str] | None:
        with self._lock:
            with self._connect() as conn:
                self._expire_old(conn)
                row = conn.execute(
                    "SELECT username, password_enc, created_at FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if not row:
                    return None
                created_at = datetime.fromtimestamp(row["created_at"], tz=timezone.utc)
                if datetime.now(timezone.utc) - created_at > self.ttl:
                    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                    conn.commit()
                    return None
                password = self._fernet.decrypt(row["password_enc"]).decode("utf-8")
                return row["username"], password

    def drop_session(self, session_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
