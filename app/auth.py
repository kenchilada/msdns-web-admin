"""Session-based auth: login with Windows (WinRM) credentials, stored server-side."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import config
from app.session_store import MemorySessionStore, SessionStore

scheme = HTTPBearer(auto_error=False)

_SESSION_TTL_HOURS = 24

# Default store; replaced by configure_session_store() from main lifespan (e.g. SQLite).
_store: SessionStore = MemorySessionStore()


def configure_session_store(store: SessionStore) -> None:
    global _store
    _store = store


def create_session(username: str, password: str) -> str:
    return _store.create_session(username, password)


def get_session_credentials(session_id: str) -> tuple[str, str] | None:
    return _store.get_session_credentials(session_id)


def drop_session(session_id: str) -> None:
    _store.drop_session(session_id)


def create_access_token(session_id: str) -> str:
    from datetime import datetime, timedelta, timezone

    expire = datetime.now(timezone.utc) + timedelta(hours=_SESSION_TTL_HOURS)
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
