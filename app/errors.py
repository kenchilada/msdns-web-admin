"""Map internal failures to safe API messages; keep details in logs."""
import logging

logger = logging.getLogger(__name__)

LOGIN_FAILED_PUBLIC = (
    "Sign-in failed. Verify DOMAIN\\user, password, and WinRM access to the DNS server."
)

DNS_OPERATION_PUBLIC = (
    "The DNS server did not complete the operation. Check server logs or try again."
)


def log_internal(category: str, message: str, max_len: int = 2000) -> None:
    text = (message or "").strip()
    if len(text) > max_len:
        text = text[:max_len] + "…"
    logger.warning("%s: %s", category, text)


def public_login_error(internal_detail: str) -> str:
    log_internal("login_failure", internal_detail)
    return LOGIN_FAILED_PUBLIC


def public_dns_error(internal_detail: str | object) -> str:
    log_internal("dns_winrm_failure", str(internal_detail))
    return DNS_OPERATION_PUBLIC
