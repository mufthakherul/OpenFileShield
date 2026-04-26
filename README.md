# OpenFileShield

OpenFileShield is a modern, open-source, public file intake platform.
Anyone can upload any file type without sign in, while the service performs fast threat scanning and stores detailed audit metadata for incident response.

## Highlights

- Open public upload endpoint with no sign in or registration
- Unlimited batch uploads in one request
- No application-level file size cap (storage capacity is the only practical limit)
- All file types supported (no extension allowlist)
- Threat scanning through open-source ClamAV
- Optional async upload queue endpoint for faster user response (`/api/upload/async`)
- Quarantine-first upload pipeline
- SHA256 deduplication mode to avoid duplicate physical storage
- Advanced metadata capture for investigation:
  - IP address
  - User-Agent
  - Accept-Language
  - Referer and Origin
  - device fingerprint hash
  - optional uploader name and email
  - optional file details/notes for the entire batch
- SHA256 hash for each upload
- Admin console at `/admin`
- Admin APIs with filtering and CSV export
- Time-series trend API for dashboard charts (`/api/trends`)
- Rate limiting and burst control against abuse

## Architecture At A Glance

1. File is streamed into quarantine.
2. SHA256 and size are calculated.
3. ClamAV scan runs.
4. Rejected files are deleted when policy requires.
5. Clean files are moved to uploads storage.
6. Full upload event is persisted for audit and analytics.

## Admin Capabilities

- Dashboard stats (`/api/stats`)
- Search and filter (`/api/uploads`)
- CSV export (`/api/uploads/export.csv`)
- Trend chart feed (`/api/trends?days=14`)
- Admin token protection via `x-admin-token`
- Live auto-refresh dashboard controls

## Local Start

### Option A: Docker (recommended)

```bash
copy .env.example .env
docker compose up --build -d
```

Default Docker URLs:

- Public uploader: http://localhost:8080/
- Admin console: http://localhost:8081/

In Docker mode the stack runs as split services (`app-public` and `app-admin`).
Admin access is still restricted by app-level local/private network checks.

Optional edge proxy profile:

```bash
docker compose --profile edge up --build -d
```

This enables Caddy with host-based routing from `PUBLIC_DOMAIN` and `ADMIN_DOMAIN`.

### Option B: Pure Python

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open:

- Upload UI: http://localhost:8080/
- Admin UI: http://localhost:8080/admin

The public upload form now accepts multiple files at once and includes an optional notes field for batch context.

### Option C: Split Public/Admin Ports (recommended for production)

Run separate instances so uploader traffic is public while admin remains local-only:

```bash
python -m app.run_dual
```

Default URLs:

- Public uploader: http://localhost:8080/
- Admin console: http://127.0.0.1:8081/

This mode sets app roles per process (`public` and `admin`) and enforces local/private network access for admin endpoints.

## Customization

Tune behavior in `.env`:

- `UPLOAD_RATE_LIMIT_PER_MINUTE`
- `UPLOAD_RATE_BURST_PER_10_SECONDS`
- `DEDUPE_MODE`
- `ASYNC_SCAN_ENABLED`
- `ASYNC_SCAN_WORKERS`
- `TREND_DAYS_DEFAULT`
- `SCAN_REQUIRED`
- `ENABLE_CSV_EXPORT`
- `ADMIN_AUTO_REFRESH_SECONDS`
- `SERVICE_NOTICE`
- `APP_ROLE`
- `ADMIN_LOCAL_ONLY`
- `PUBLIC_DOMAIN`
- `ADMIN_DOMAIN`
- `ACME_EMAIL`

## Workflows

This repo now includes a GitHub Actions CI workflow at `.github/workflows/ci.yml` that runs:

- Python backend tests (`pytest`)
- Playwright E2E tests (public and admin split apps)
- Docker compose build smoke check

## Automated E2E Tests (Playwright + TypeScript)

```bash
pnpm install
pnpm e2e:install
pnpm e2e:test
```

Optional environment overrides:

- `PUBLIC_BASE_URL` (default `http://127.0.0.1:8080`)
- `ADMIN_BASE_URL` (default `http://127.0.0.1:8081`)
- `ADMIN_TOKEN` (default `change-this-token`)

## Public Global Access From Personal PC

Use Cloudflare Tunnel, reverse proxy, or ngrok. Full guide:

- [docs/DEPLOY_PERSONAL_PC.md](docs/DEPLOY_PERSONAL_PC.md)
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)

## Compliance Notes

Since uploader identity metadata is collected, publish a clear privacy notice and legal basis before production use.

- [docs/PRIVACY.md](docs/PRIVACY.md)
- [SECURITY.md](SECURITY.md)

## License

MIT License. See [LICENSE](LICENSE).
