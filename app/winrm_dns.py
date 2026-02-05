"""Run PowerShell DNS commands on Windows via WinRM."""
import json
import logging
from typing import Any

import winrm

from app.config import config

logger = logging.getLogger(__name__)


def _session(winrm_user: str, winrm_password: str) -> winrm.Session:
    protocol = "https" if config.WINRM_USE_HTTPS else "http"
    port = config.WINRM_PORT or (5986 if config.WINRM_USE_HTTPS else 5985)
    url = f"{protocol}://{config.WINDOWS_DNS_HOST}:{port}/wsman"
    # Domain\username requires NTLM; basic auth only works for local accounts
    transport = "ntlm" if "\\" in winrm_user else "basic"
    return winrm.Session(
        url,
        auth=(winrm_user, winrm_password),
        transport=transport,
        server_cert_validation="ignore" if config.WINRM_USE_HTTPS else None,
    )


def _run_ps(script: str, winrm_user: str, winrm_password: str) -> tuple[bool, str]:
    """Run PowerShell script; return (success, stdout or error)."""
    if not config.dns_host_configured():
        return False, "Windows DNS server not configured (set WINDOWS_DNS_HOST)"
    try:
        s = _session(winrm_user, winrm_password)
        r = s.run_ps(script)
        if r.status_code != 0:
            err = r.std_err.decode("utf-8", errors="replace") if r.std_err else "Unknown error"
            return False, err.strip() or f"Exit code {r.status_code}"
        out = (r.std_out or b"").decode("utf-8", errors="replace").strip()
        return True, out
    except Exception as e:
        logger.exception("WinRM error")
        return False, str(e)


def _escape_ps(s: str) -> str:
    return s.replace("'", "''")


def test_connection(winrm_user: str, winrm_password: str) -> tuple[bool, str]:
    """Verify credentials by running a minimal DNS command. Returns (success, message)."""
    script = """
$ErrorActionPreference = 'Stop'
Get-DnsServerZone | Select-Object -First 1 | Out-Null
"""
    return _run_ps(script, winrm_user, winrm_password)


def list_zones(winrm_user: str, winrm_password: str) -> tuple[bool, list[str] | str]:
    """Return list of zone names, or (False, error_message)."""
    script = """
$ErrorActionPreference = 'Stop'
(Get-DnsServerZone | Where-Object { $_.ZoneType -eq 'Primary' -or $_.ZoneType -eq 'Secondary' }).ZoneName | ConvertTo-Json -Compress
"""
    ok, out = _run_ps(script, winrm_user, winrm_password)
    if not ok:
        return False, out
    try:
        data = json.loads(out)
        if isinstance(data, str):
            return True, [data]
        return True, list(data) if data else []
    except json.JSONDecodeError:
        return False, f"Invalid response: {out[:200]}"


def list_records(
    zone: str, winrm_user: str, winrm_password: str
) -> tuple[bool, list[dict[str, Any]] | str]:
    """Return list of all DNS records in zone: {name, type, data}. data is type-specific (e.g. ip, target, exchange)."""
    zone_esc = _escape_ps(zone)
    script = f"""
$ErrorActionPreference = 'Stop'
$zone = '{zone_esc}'
$result = @()
Get-DnsServerResourceRecord -ZoneName $zone | Where-Object {{ $_.RecordType -notin 'SOA' }} | ForEach-Object {{
  $r = $_
  $data = @{{}}
  switch ($r.RecordType.ToString()) {{
    'A'       {{ $data = @{{ ip = $r.RecordData.IPv4Address.ToString() }} }}
    'AAAA'    {{ $data = @{{ ip = $r.RecordData.IPv6Address.ToString() }} }}
    'CNAME'   {{ $data = @{{ target = $r.RecordData.HostNameAlias }} }}
    'MX'      {{ $data = @{{ exchange = $r.RecordData.MailExchange; preference = $r.RecordData.Preference }} }}
    'TXT'     {{ $data = @{{ text = ($r.RecordData.DescriptiveText -join ' ') }} }}
    'PTR'     {{ $data = @{{ target = $r.RecordData.PtrDomainName }} }}
    'NS'      {{ $data = @{{ target = $r.RecordData.NameServer }} }}
    'SRV'     {{ $data = @{{ target = $r.RecordData.DomainName; port = $r.RecordData.Port; priority = $r.RecordData.Priority; weight = $r.RecordData.Weight }} }}
    default   {{ $data = @{{ raw = $r.RecordData.ToString() }} }}
  }}
  $result += [PSCustomObject]@{{ Name = $r.HostName; Type = $r.RecordType.ToString(); Data = $data }}
}}
if ($result.Count -eq 0) {{ '[]' }} elseif ($result.Count -eq 1) {{ $result | ConvertTo-Json -Depth 5 -Compress }} else {{ $result | ConvertTo-Json -Depth 5 -Compress }}
"""
    ok, out = _run_ps(script, winrm_user, winrm_password)
    if not ok:
        return False, out
    if not out or out.strip() == "":
        return True, []
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        records = []
        for r in data or []:
            rec = {"name": r.get("Name", ""), "type": r.get("Type", "Unknown"), "data": r.get("Data", {})}
            if isinstance(rec["data"], str):
                rec["data"] = {"value": rec["data"]}
            records.append(rec)
        return True, records
    except (json.JSONDecodeError, TypeError) as e:
        return False, f"Invalid response: {e}"


def remove_record(
    zone: str,
    name: str,
    rr_type: str,
    data: dict[str, Any],
    winrm_user: str,
    winrm_password: str,
) -> tuple[bool, str]:
    """Remove one DNS record identified by zone, name, type, and data (e.g. ip, target)."""
    zone_esc = _escape_ps(zone)
    name_esc = _escape_ps(name)
    type_esc = _escape_ps(rr_type)
    # Build filter expression from data (e.g. ip, target, exchange+preference)
    v = None
    if "ip" in data and data["ip"]:
        v = _escape_ps(str(data["ip"]))
        if rr_type == "A":
            filter_expr = "$_.RecordData.IPv4Address.ToString() -eq '" + v + "'"
        else:
            filter_expr = "$_.RecordData.IPv6Address.ToString() -eq '" + v + "'"
    elif "target" in data and data["target"]:
        v = _escape_ps(str(data["target"]).strip())
        if rr_type.upper() == "CNAME":
            filter_expr = "$_.RecordData.HostNameAlias.ToString() -eq '" + v + "'"
        elif rr_type.upper() == "NS":
            filter_expr = "$_.RecordData.NameServer.ToString() -eq '" + v + "'"
        elif rr_type.upper() == "PTR":
            filter_expr = "$_.RecordData.PtrDomainName.ToString() -eq '" + v + "'"
        elif rr_type.upper() == "SRV":
            filter_expr = "$_.RecordData.DomainName.ToString() -eq '" + v + "'"
        else:
            filter_expr = "$true"
    elif "exchange" in data and data.get("exchange"):
        ex = _escape_ps(str(data["exchange"]).strip())
        pref = data.get("preference", 0)
        filter_expr = "$_.RecordData.MailExchange.ToString() -eq '" + ex + "' -and $_.RecordData.Preference -eq " + str(int(pref))
    elif "text" in data:
        v = _escape_ps(str(data["text"]))
        filter_expr = "($_.RecordData.DescriptiveText -join ' ') -eq '" + v + "'"
    elif "raw" in data:
        return False, "Cannot remove record by raw data; specify type-specific fields."
    else:
        filter_expr = "$true"
    # Filter by type using case-insensitive string comparison (PowerShell may return "CName" not "CNAME")
    rr_type_upper = rr_type.upper()
    type_filter = f"$_.RecordType.ToString() -ieq '{rr_type_upper}'"
    script = f"""
$ErrorActionPreference = 'Stop'
$zone = '{zone_esc}'
$name = '{name_esc}'
Get-DnsServerResourceRecord -ZoneName $zone -Name $name | Where-Object {{ {type_filter} }} | Where-Object {{ {filter_expr} }} | Remove-DnsServerResourceRecord -ZoneName $zone -Force
"""
    ok, out = _run_ps(script, winrm_user, winrm_password)
    if ok:
        return True, "Record removed."
    return False, out


def add_record(
    zone: str,
    rr_type: str,
    name: str,
    data: dict[str, Any],
    winrm_user: str,
    winrm_password: str,
) -> tuple[bool, str]:
    """Add a DNS record. data keys depend on type: A/AAAA -> ip, CNAME/NS/PTR -> target, MX -> exchange + preference, TXT -> text, SRV -> target, port, priority, weight."""
    zone_esc = _escape_ps(zone)
    name_esc = _escape_ps(name)
    t = rr_type.upper()
    if t == "A":
        ip = str(data.get("ip", "")).strip()
        if not ip:
            return False, "A record requires 'ip'."
        script = f"Add-DnsServerResourceRecordA -ZoneName '{zone_esc}' -Name '{name_esc}' -IPv4Address '{_escape_ps(ip)}'"
    elif t == "AAAA":
        ip = str(data.get("ip", "")).strip()
        if not ip:
            return False, "AAAA record requires 'ip'."
        script = f"Add-DnsServerResourceRecordAAAA -ZoneName '{zone_esc}' -Name '{name_esc}' -IPv6Address '{_escape_ps(ip)}'"
    elif t == "CNAME":
        target = str(data.get("target", "")).strip()
        if not target:
            return False, "CNAME record requires 'target'."
        script = f"Add-DnsServerResourceRecordCName -ZoneName '{zone_esc}' -Name '{name_esc}' -HostNameAlias '{_escape_ps(target)}'"
    elif t == "MX":
        exchange = str(data.get("exchange", "")).strip()
        preference = int(data.get("preference", 10))
        if not exchange:
            return False, "MX record requires 'exchange'."
        script = f"Add-DnsServerResourceRecordMX -ZoneName '{zone_esc}' -Name '{name_esc}' -MailExchange '{_escape_ps(exchange)}' -Preference {preference}"
    elif t == "TXT":
        text = str(data.get("text", "")).strip()
        if not text:
            return False, "TXT record requires 'text'."
        script = f"Add-DnsServerResourceRecord -ZoneName '{zone_esc}' -Name '{name_esc}' -DescriptiveText '{_escape_ps(text)}' -Txt"
    elif t == "NS":
        target = str(data.get("target", "")).strip()
        if not target:
            return False, "NS record requires 'target'."
        script = f"Add-DnsServerResourceRecord -ZoneName '{zone_esc}' -Name '{name_esc}' -NS -NameServer '{_escape_ps(target)}'"
    elif t == "PTR":
        target = str(data.get("target", "")).strip()
        if not target:
            return False, "PTR record requires 'target'."
        script = f"Add-DnsServerResourceRecordPtr -ZoneName '{zone_esc}' -Name '{name_esc}' -PtrDomainName '{_escape_ps(target)}'"
    elif t == "SRV":
        target = str(data.get("target", "")).strip()
        port = int(data.get("port", 0))
        priority = int(data.get("priority", 0))
        weight = int(data.get("weight", 0))
        if not target:
            return False, "SRV record requires 'target'."
        script = f"Add-DnsServerResourceRecord -ZoneName '{zone_esc}' -Name '{name_esc}' -Srv -DomainName '{_escape_ps(target)}' -Port {port} -Priority {priority} -Weight {weight}"
    else:
        return False, f"Unsupported record type: {rr_type}"
    full_script = "$ErrorActionPreference = 'Stop'\n" + script
    ok, out = _run_ps(full_script, winrm_user, winrm_password)
    if ok:
        return True, "Record added."
    return False, out


def update_record(
    zone: str,
    name: str,
    rr_type: str,
    old_data: dict[str, Any],
    new_data: dict[str, Any],
    winrm_user: str,
    winrm_password: str,
) -> tuple[bool, str]:
    """Update a record by removing the old one and adding with new data."""
    ok, msg = remove_record(zone, name, rr_type, old_data, winrm_user, winrm_password)
    if not ok:
        return False, msg
    return add_record(zone, rr_type, name, new_data, winrm_user, winrm_password)
