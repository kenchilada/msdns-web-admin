"""FastAPI app: login with Windows credentials, zones, all DNS record types."""
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth import create_access_token, create_session, get_winrm_credentials
from app.config import config
from app.winrm_dns import (
    add_record,
    list_records,
    list_zones,
    remove_record,
    test_connection,
    update_record,
)

app_path = Path(__file__).resolve().parent

from fastapi import FastAPI

app = FastAPI(title="MS DNS Manager", description="Manage DNS records on Windows DNS from TrueNAS/Dockge")

# --- Auth (login = Windows/WinRM credentials) ---
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.post("/api/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    if not config.dns_host_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Windows DNS server not configured (WINDOWS_DNS_HOST)",
        )
    ok, msg = test_connection(form.username, form.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg or "Invalid credentials")
    session_id = create_session(form.username, form.password)
    token = create_access_token(session_id)
    return TokenResponse(access_token=token)


# --- Zones ---
@app.get("/api/zones")
def api_list_zones(creds: Annotated[tuple[str, str], Depends(get_winrm_credentials)]):
    ok, data = list_zones(creds[0], creds[1])
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=data)
    return {"zones": data}


# --- DNS records (all types) ---
@app.get("/api/zones/{zone_name}/records")
def api_list_records(
    zone_name: str,
    creds: Annotated[tuple[str, str], Depends(get_winrm_credentials)],
):
    ok, data = list_records(zone_name, creds[0], creds[1])
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=data)
    return {"records": data}


class AddRecordBody(BaseModel):
    type: str
    name: str
    data: dict[str, Any] = {}


@app.post("/api/zones/{zone_name}/records")
def api_add_record(
    zone_name: str,
    body: AddRecordBody,
    creds: Annotated[tuple[str, str], Depends(get_winrm_credentials)],
):
    if not body.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name required")
    if not (body.type or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type required")
    ok, msg = add_record(
        zone_name, body.type.strip(), body.name.strip(), body.data or {}, creds[0], creds[1]
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)
    return {"message": msg}


class RemoveRecordBody(BaseModel):
    type: str
    data: dict[str, Any] = {}


@app.delete("/api/zones/{zone_name}/records")
def api_remove_record(
    zone_name: str,
    name: str,
    creds: Annotated[tuple[str, str], Depends(get_winrm_credentials)],
    body: RemoveRecordBody | None = None,
):
    if not name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name required")
    rr_type = (body.type if body else "").strip() or "A"
    data = (body.data if body else {}) or {}
    ok, msg = remove_record(zone_name, name.strip(), rr_type, data, creds[0], creds[1])
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)
    return {"message": msg}


class UpdateRecordBody(BaseModel):
    type: str
    old_data: dict[str, Any] = {}
    new_data: dict[str, Any] = {}


@app.put("/api/zones/{zone_name}/records")
def api_update_record(
    zone_name: str,
    name: str,
    body: UpdateRecordBody,
    creds: Annotated[tuple[str, str], Depends(get_winrm_credentials)],
):
    if not name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name required")
    if not (body.type or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type required")
    ok, msg = update_record(
        zone_name,
        name.strip(),
        body.type.strip(),
        body.old_data or {},
        body.new_data or {},
        creds[0],
        creds[1],
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)
    return {"message": msg}


# --- Health (no auth) ---
@app.get("/api/health")
def health():
    return {"ok": True, "dns_host_configured": config.dns_host_configured()}


# --- Serve frontend ---
static_dir = app_path / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")
else:
    @app.get("/")
    def index():
        return {"message": "MS DNS Manager API. Mount static files at /static and serve index.html at /."}
