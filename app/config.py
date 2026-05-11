"""App configuration from environment."""
import os

def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


class Config:
    # Windows DNS server (WinRM) - only host in env; user/password come from login
    WINDOWS_DNS_HOST: str = _get("WINDOWS_DNS_HOST", "")
    WINRM_USE_HTTPS: bool = _get("WINRM_USE_HTTPS", "false").lower() in ("1", "true", "yes")
    WINRM_PORT: int = int(_get("WINRM_PORT") or "0")  # 0 = use 5986 (HTTPS) or 5985 (HTTP)
    # pywinrm transport: ntlm (default on Linux; required when WinRM Basic=false), basic, kerberos, credssp
    WINRM_TRANSPORT: str = (_get("WINRM_TRANSPORT", "ntlm") or "ntlm").lower()

    SECRET_KEY: str = _get("SECRET_KEY", "change-this-secret-in-production")

    @classmethod
    def dns_host_configured(cls) -> bool:
        return bool(cls.WINDOWS_DNS_HOST)


config = Config()
