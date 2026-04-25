# Architecture

## Components

- FastAPI web app (upload API + UI)
- ClamAV daemon (`clamd`) for malware scanning
- SQLite database for upload event records
- In-memory worker queue for asynchronous scan processing
- Local storage:
  - `data/quarantine` for pre-scan files
  - `data/uploads` for accepted files

## Upload Sequence

1. Browser submits file to `POST /api/upload`.
2. App streams file to quarantine.
3. App computes SHA256 and size.
4. App checks dedupe cache by SHA256.
5. If unique, app scans with ClamAV (sync or async worker path).
6. App rejects, stores, or references existing stored file.
7. App logs complete event details to database.

## Trust Boundaries

- Internet to app boundary (must use HTTPS in production)
- App to scanner boundary (internal network)
- App to storage/database boundary (filesystem and SQLite)

## Future Upgrades

- Replace SQLite with PostgreSQL
- Add object storage (S3-compatible)
- Add Redis-backed distributed queue for horizontal scaling
- Add signed temporary download URLs for approved retrieval workflows
