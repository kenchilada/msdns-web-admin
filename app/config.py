"""App configuration from environment."""
import os
from pathlib import Path


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


class Config:
    # Windows DNS server (WinRM) - only host in env; user/password come from login
    WINDOWS_DNS_HOST: str = _get("WINDOWS_DNS_HOST", "")
    WINRM_USE_HTTPS: bool = _get("WINRM_USE_HTTPS", "false").lower() in ("1", "true", "yes")
    WINRM_PORT: int = int(_get("WINRM_PORT") or "0")  # 0 = use 5986 (HTTPS) or 5985 (HTTP)
    # pywinrm transport: ntlm (default on Linux; required when WinRM Basic=false), basic, kerberos, credssp
    WINRM_TRANSPORT: str = (_get("WINRM_TRANSPORT", "ntlm") or "ntlm").lower()
    # HTTPS: path to PEM bundle for WinRM server cert; if set, TLS is verified against this CA/file.
    WINRM_CA_BUNDLE: str = _get("WINRM_CA_BUNDLE", "")
    # If true (and no WINRM_CA_BUNDLE), verify WinRM TLS against system trust store (needs ca-certificates).
    WINRM_VERIFY_TLS: bool = _get("WINRM_VERIFY_TLS", "false").lower() in ("1", "true", "yes")

    SECRET_KEY: str = _get("SECRET_KEY", "change-this-secret-in-production")

    # memory (default) or sqlite — SQLite shares sessions across uvicorn workers on one host (shared DB file).
    SESSION_BACKEND: str = (_get("SESSION_BACKEND", "memory") or "memory").lower()
    SESSION_SQLITE_PATH: str = _get("SESSION_SQLITE_PATH", str(Path("/tmp/msdns_sessions.db")))

    # Login brute-force throttle (slowapi), e.g. 10/minute, 30/hour
    LOGIN_RATE_LIMIT: str = _get("LOGIN_RATE_LIMIT", "10/minute")

    @classmethod
    def dns_host_configured(cls) -> bool:
        return bool(cls.WINDOWS_DNS_HOST)


config = Config()
