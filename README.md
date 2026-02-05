# MS DNS Manager

A small web app that lists zones and A records on a **Windows DNS Server** and lets you add/remove A records. It runs in Docker and connects to Windows via **WinRM** (PowerShell remoting).

Designed to run on **Dockge** (recommended) or **TrueNAS Scale** as a custom app.

## Features

- **Login** – Sign in with your Windows (WinRM) account; credentials are verified against the DNS server and kept only in a server-side session (never in env).
- **List zones** – Shows Primary/Secondary zones from your Windows DNS server.
- **List A records** – Per-zone table of host name and IP.
- **Add A record** – Name (host) + IPv4.
- **Remove A record** – One click per record.

## Requirements

1. **Windows DNS Server** with:
   - WinRM enabled (HTTP 5985 or HTTPS 5986).
   - A user account that can run DNS cmdlets (e.g. in **DNSAdmins** or Domain Admin).
2. **Network** – The host running this app (Dockge/TrueNAS) must reach the Windows server on the WinRM port.

## Quick start with Dockge

1. In Dockge, create a new stack (e.g. `msdns`) and point it at this repo or a folder with the same files.
2. Set environment variables (or use a `.env` file). **Only the DNS server host** is in env; you sign in with your Windows account on the login page.

   | Variable | Description |
   |----------|-------------|
   | `WINDOWS_DNS_HOST` | IP or hostname of the Windows DNS server |
   | `WINRM_USE_HTTPS` | `true` for HTTPS (port 5986), else HTTP (5985) |
   | `WINRM_PORT` | Optional; default 5985 or 5986 |
   | `SECRET_KEY` | Secret for JWT; set to a random string in production |

3. Deploy the stack. Open the app (e.g. `http://your-host:8765`), sign in with your **Windows username and password** (the account that has DNS access), then select a zone and manage A records.

## Enabling WinRM on Windows

On the **Windows DNS server** (PowerShell as Administrator):

```powershell
# Allow WinRM and open firewall
Enable-PSRemoting -Force
Set-NetFirewallRule -Name "WINRM-HTTP-In-TCP" -RemoteAddress Any  # or your Docker host IP
```

For HTTPS (recommended in production):

```powershell
# Create a self-signed cert and bind WinRM to it
$cert = New-SelfSignedCertificate -DnsName $env:COMPUTERNAME -CertStoreLocation Cert:\LocalMachine\My
New-Item -Path WSMan:\LocalHost\Listener -Transport HTTPS -Address * -Port 5986 -CertificateThumbPrint $cert.Thumbprint -Force
# Open firewall for 5986
New-NetFirewallRule -DisplayName "WINRM HTTPS" -Direction Inbound -LocalPort 5986 -Protocol TCP -Action Allow
```

Ensure the WinRM user has rights to manage DNS (e.g. add the account to the **DNSAdmins** group or use a Domain Admin).

## Running with docker-compose (without Dockge)

```bash
cp .env.example .env
# Edit .env with your Windows DNS and app credentials
docker compose up -d
```

App will be at `http://localhost:8765`.

## TrueNAS Scale as a custom app

TrueNAS Scale apps are Helm-based. You can run this as a **custom workload**:

1. **Option A – Use the Docker image**
   - Build and push the image to a registry (e.g. GitHub Container Registry, Docker Hub), or build on the cluster.
   - In TrueNAS: **Apps** → **Discover Apps** → **Custom** (or **Launch Docker Image**), then use your image and set the same env vars as above. Expose port 8000 (or map to 8765).

2. **Option B – Helm chart**
   - Convert the `docker-compose.yaml` into a minimal Helm chart (Deployment + Service + optional Ingress) and add it to your catalog, or install with `helm install` and set env from a values file.

3. **Networking**
   - Ensure the TrueNAS/K3s network can reach your Windows DNS server on 5985/5986. If the app runs in a different VLAN, add a route or allow the WinRM port from the cluster nodes to the Windows host.

## Project layout

```
truenas-msdns/
├── app/
│   ├── main.py       # FastAPI app, routes, auth
│   ├── config.py     # Env-based config
│   ├── auth.py       # JWT login
│   ├── winrm_dns.py  # WinRM + PowerShell DNS commands
│   └── static/       # Frontend (HTML, CSS, JS)
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── .env.example
└── README.md
```

## API (for integrations)

- `POST /api/auth/login` – Form body: `username`, `password` (Windows/WinRM credentials). Verified against the DNS server; returns `{ "access_token": "..." }`. Credentials are stored only in a server-side session (24h).
- `GET /api/zones` – List zones (Bearer token required).
- `GET /api/zones/{zone}/records` – List A records (Bearer token required).
- `POST /api/zones/{zone}/records` – Body: `{ "name": "host", "ip": "1.2.3.4" }`.
- `DELETE /api/zones/{zone}/records?name=host&ip=1.2.3.4` – Remove A record; `ip` optional.

## License

MIT.
