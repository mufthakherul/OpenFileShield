# OpenFileShield Deployment Guide

This guide covers local development, split public/admin production topology, and global exposure patterns.

## 1) Port Map

- Public uploader app: 8080
- Admin app (dedicated service): 8081
- ClamAV daemon: 3310
- Edge reverse proxy HTTP: 80
- Edge reverse proxy HTTPS: 443

## 2) Local Development (No Docker)

### Single-process mode

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Access:

- User/Uploader UI: http://localhost:8080/
- Admin UI: http://localhost:8080/admin

### Split public/admin mode

```powershell
.\.venv\Scripts\python -m app.run_dual
```

Access:

- User/Uploader UI (public service): http://localhost:8080/
- Admin UI (local/private only policy): http://127.0.0.1:8081/

## 3) Docker Deployment (Split Services)

Start services:

```powershell
copy .env.example .env
docker compose up --build -d
```

Service URLs:

- User/Uploader UI: http://localhost:8080/
- Admin UI: http://localhost:8081/
- Health: http://localhost:8080/api/health

Current container-level routes:

- Public service does not expose admin APIs/routes.
- Admin service is dedicated and enforced by app-level local/private checks.

Stop services:

```powershell
docker compose down
```

## 4) Global + Local Split Access Pattern

Goal:

- User/Uploader globally reachable from anywhere.
- Admin reachable only from local/private networks.

Recommended pattern:

1. Expose only public domain to internet.
2. Keep admin domain behind local/private network restrictions.
3. Enforce both network-level and app-level controls.

### Option A: Caddy edge profile (included)

Configure in .env:

- PUBLIC_DOMAIN=upload.yourdomain.com
- ADMIN_DOMAIN=admin.yourdomain.com
- ACME_EMAIL=you@yourdomain.com

Run:

```powershell
docker compose --profile edge up --build -d
```

Result:

- https://upload.yourdomain.com -> app-public
- https://admin.yourdomain.com -> app-admin (private IP only via edge + app policy)

### Option B: Cloudflare Tunnel (recommended on personal PC)

- Publish uploader domain through tunnel to local public service (8080).
- Do not publish admin service unless protected by IP allowlists and additional auth.

## 5) Public and Admin Access Matrix

- Local machine user UI: http://localhost:8080/
- Local machine admin UI: http://localhost:8081/ (split mode)
- LAN/private user UI: http://<local-ip>:8080/
- LAN/private admin UI: http://<local-ip>:8081/ (allowed if private IP)
- Internet user UI: use tunnel/reverse-proxy public domain
- Internet admin UI: blocked by policy unless explicitly reconfigured

## 6) Validation Commands

### Backend tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

### E2E browser tests

```powershell
pnpm install
pnpm e2e:install
pnpm e2e:test
```

### Quick endpoint checks

```powershell
Invoke-WebRequest http://127.0.0.1:8080/api/health
Invoke-WebRequest http://127.0.0.1:8081/
Invoke-WebRequest -Headers @{"x-admin-token"="change-this-token"} http://127.0.0.1:8081/api/stats
```

## 7) Hardening Checklist

- Change ADMIN_TOKEN immediately.
- Keep ADMIN_LOCAL_ONLY=true in production.
- Keep TRUST_X_FORWARDED_FOR=true only when behind trusted proxy.
- Put admin behind VPN/Zero Trust in addition to token auth.
- Rotate logs and DB backups.
- Keep ClamAV signatures and image updated.
