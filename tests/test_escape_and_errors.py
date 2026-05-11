from app.errors import DNS_OPERATION_PUBLIC, LOGIN_FAILED_PUBLIC, public_dns_error, public_login_error
from app.winrm_dns import _escape_ps


def test_escape_ps_doubles_single_quotes():
    assert _escape_ps("foo'bar") == "foo''bar"


def test_public_dns_error_never_echoes_internal():
    secret = "SuperSecretWinRM-token-xyz"
    out = public_dns_error(f"failed: {secret}")
    assert secret not in out
    assert out == DNS_OPERATION_PUBLIC


def test_public_login_error_never_echoes_internal():
    secret = "bad-password-detail-leak"
    out = public_login_error(secret)
    assert secret not in out
    assert out == LOGIN_FAILED_PUBLIC
