"""Session-based auth: login with Windows (WinRM) credentials, stored server-side."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import config

scheme = HTTPBearer(auto_error=False)

# Server-side session store: session_id -> { username, password, created_at }
# Credentials are only in memory and never logged; sessions expire after 24h.
_SESSIONS: dict[str, dict] = {}
_SESSION_TTL = timedelta(hours=24)


def _expire_old_sessions() -> None:
    now = datetime.now(timezone.utc)
    for sid, data in list(_SESSIONS.items()):
        if now - data["created_at"] > _SESSION_TTL:
            del _SESSIONS[sid]


def create_session(username: str, password: str) -> str:
    _expire_old_sessions()
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {
        "username": username,
        "password": password,
        "created_at": datetime.now(timezone.utc),
    }
    return session_id


def get_session_credentials(session_id: str) -> tuple[str, str] | None:
    _expire_old_sessions()
    data = _SESSIONS.get(session_id)
    if not data:
        return None
    if datetime.now(timezone.utc) - data["created_at"] > _SESSION_TTL:
        del _SESSIONS[session_id]
        return None
    return data["username"], data["password"]


def drop_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def create_access_token(session_id: str) -> str:
    expire = datetime.now(timezone.utc) + _SESSION_TTL
    return jwt.encode(
        {"sub": session_id, "exp": expire},
        config.SECRET_KEY,
        algorithm="HS256",
    )


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_session_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(scheme)],
) -> str:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session_id = decode_token(credentials.credentials)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session_id


async def get_winrm_credentials(
    session_id: Annotated[str, Depends(get_current_session_id)],
) -> tuple[str, str]:
    """Resolve session to (username, password) for WinRM. 401 if session missing/expired."""
    creds = get_session_credentials(session_id)
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return creds
