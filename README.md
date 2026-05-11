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

Dockge typically doesn’t build images from a Git repo, so this project publishes a pre-built image to [GitHub Container Registry](https://github.com/kenchilada/msdns-web-admin/pkgs/container/msdns-web-admin). Use that image in Dockge (no `build:` step).

1. **Create a new Compose** in Dockge (e.g. name: `msdns-web-admin`).

2. **Paste this in the Compose / services YAML** (replace any existing `services:` block):

   ```yaml
   services:
     msdns:
       image: ghcr.io/kenchilada/msdns-web-admin:latest
       container_name: msdns-manager
       restart: unless-stopped
       ports:
         - "8766:8000"
       environment:
         - WINDOWS_DNS_HOST=${WINDOWS_DNS_HOST:-}
         - WINRM_USE_HTTPS=${WINRM_USE_HTTPS:-false}
         - WINRM_PORT=${WINRM_PORT:-}
         - SECRET_KEY=${SECRET_KEY:-change-this-secret}
   ```

3. **Set environment variables** in Dockge’s .env / env section:

   | Variable | Description |
   |----------|-------------|
   | `WINDOWS_DNS_HOST` | IP or hostname of the Windows DNS server |
   | `WINRM_USE_HTTPS` | `true` for HTTPS (port 5986), else HTTP (5985) |
   | `WINRM_PORT` | Optional; default 5985 or 5986 |
   | `WINRM_TRANSPORT` | Optional; default `ntlm`. Use when WinRM has Basic disabled (typical). Kerberos requires extra container krb5 setup. |
   | `SECRET_KEY` | Secret for JWT; set to a random string in production |

4. **Deploy.** Open the app at `http://your-host:8766`, sign in with your **Windows username and password** (the account that has DNS access), then select a zone and manage records.

The image is built automatically on push to `master` (see [.github/workflows/docker-publish.yml](.github/workflows/docker-publish.yml)). After the first run, `ghcr.io/kenchilada/msdns-web-admin:latest` is public and no login is needed to pull.

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
