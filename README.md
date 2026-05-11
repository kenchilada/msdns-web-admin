# MS DNS Manager

A small web app that lists zones and DNS records on a **Windows DNS Server** and lets you add, edit, or remove records. It runs in Docker and connects to Windows via **WinRM** (PowerShell remoting).

Designed to run on **Dockge** (recommended) or **TrueNAS Scale** as a custom app.

## Features

- **Login** – Sign in with your Windows (WinRM) account; credentials are verified against the DNS server and kept only in a server-side session (24h, optional SQLite backing). Login responses use generic errors; details are logged server-side only.
- **Logout** – Clears the JWT client-side and removes the server session (WinRM password dropped immediately).
- **List zones** – Shows Primary/Secondary zones from your Windows DNS server.
- **List records** – Per-zone table of DNS records (A, AAAA, CNAME, MX, TXT, NS, PTR, SRV, etc.).
- **Add / edit / remove** – Create, update, or delete records by type.

## Security notes

- **Rate limiting** – `POST /api/auth/login` is throttled (`LOGIN_RATE_LIMIT`, default `10/minute` per IP).
- **Sessions** – Default in-memory store is lost on restart and does not sync across separate containers. Use `SESSION_BACKEND=sqlite` with a **mounted** `SESSION_SQLITE_PATH` for multiple workers on one host or persistence; passwords are **encrypted at rest** with a key derived from `SECRET_KEY`. Changing `SECRET_KEY` invalidates existing SQLite sessions.
- **TLS** – For WinRM HTTPS, set `WINRM_CA_BUNDLE` to your CA PEM or `WINRM_VERIFY_TLS=true` for public CAs. Default remains “verify off” for self-signed WinRM certs (`WINRM_USE_HTTPS=true` without bundle).
- **Reverse proxy** – Terminate HTTPS in front of this app in production; keep it off the open internet without a boundary.
- **NTLM vs Kerberos** – This stack uses **NTLM** from Linux unless you add Kerberos tooling. If domain policy **restricts incoming NTLM** on the DNS server, interactive domain PCs may still work while this app does not until policy allows NTLM for that host or you implement Kerberos in the container.

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
         - WINRM_TRANSPORT=${WINRM_TRANSPORT:-ntlm}
         - WINRM_CA_BUNDLE=${WINRM_CA_BUNDLE:-}
         - WINRM_VERIFY_TLS=${WINRM_VERIFY_TLS:-false}
         - SESSION_BACKEND=${SESSION_BACKEND:-memory}
         - SESSION_SQLITE_PATH=${SESSION_SQLITE_PATH:-/tmp/msdns_sessions.db}
         - LOGIN_RATE_LIMIT=${LOGIN_RATE_LIMIT:-10/minute}
         - SECRET_KEY=${SECRET_KEY:-change-this-secret}
   ```

3. **Set environment variables** in Dockge’s .env / env section:

   | Variable | Description |
   |----------|-------------|
   | `WINDOWS_DNS_HOST` | IP or hostname of the Windows DNS server |
   | `WINRM_USE_HTTPS` | `true` for HTTPS (port 5986), else HTTP (5985) |
   | `WINRM_PORT` | Optional; default 5985 or 5986 |
   | `WINRM_TRANSPORT` | Optional; default `ntlm`. Kerberos needs krb5 setup in the container. |
   | `WINRM_CA_BUNDLE` | Optional PEM path: validate WinRM HTTPS against this CA (mount the file into the container). |
   | `WINRM_VERIFY_TLS` | If `true` and `WINRM_CA_BUNDLE` unset, validate HTTPS against the image trust store (`ca-certificates`). |
   | `SESSION_BACKEND` | `memory` (default) or `sqlite` — use SQLite when running **multiple uvicorn workers** so sessions are shared. |
   | `SESSION_SQLITE_PATH` | SQLite file path when `SESSION_BACKEND=sqlite` (mount a volume if you need persistence across container recreation). |
   | `LOGIN_RATE_LIMIT` | slowapi limit for `/api/auth/login`, default `10/minute` (per client IP). |
   | `SECRET_KEY` | Secret for JWT and encrypting passwords at rest in SQLite; use a long random string in production |

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

App will be at `http://localhost:8766` (see `ports` in `docker-compose.yaml`).

## Tests

```bash
pip install -r requirements.txt
pytest
```

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
│   ├── main.py          # FastAPI app, routes, rate limits
│   ├── config.py        # Env-based config
│   ├── auth.py          # JWT + session ids
│   ├── session_store.py # Memory / SQLite credential store
│   ├── errors.py        # Sanitized API error messages
│   ├── winrm_dns.py     # WinRM + PowerShell DNS commands
│   └── static/          # Frontend (HTML, CSS, JS)
├── tests/
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── .env.example
└── README.md
```

## API (for integrations)

- `POST /api/auth/login` – Form body: `username`, `password`. Returns `{ "access_token": "..." }`. Generic error body on failure (details in server logs). Rate limited.
- `POST /api/auth/logout` – Optional `Authorization: Bearer …`; drops the server-side session.
- `GET /api/zones` – List zones (Bearer token required).
- `GET /api/zones/{zone}/records` – List records (Bearer).
- `POST /api/zones/{zone}/records` – Body: `{ "type": "A", "name": "host", "data": { "ip": "1.2.3.4" } }` (shape of `data` depends on `type`).
- `DELETE /api/zones/{zone}/records?name=host` – Body optional JSON `{ "type": "…", "data": { … } }` to disambiguate.
- `PUT /api/zones/{zone}/records?name=host` – Body: `{ "type": "…", "old_data": {}, "new_data": {} }`.

## License

MIT.
