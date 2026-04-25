# Architecture

## Components

- FastAPI web app (upload API + UI)
- ClamAV daemon (`clamd`) for malware scanning
- SQLite database for upload event records
- Local storage:
  - `data/quarantine` for pre-scan files
  - `data/uploads` for accepted files

## Upload Sequence

1. Browser submits file to `POST /api/upload`.
2. App streams file to quarantine.
3. App computes SHA256 and size.
4. App asks ClamAV to scan file.
5. App rejects or stores file based on scan result and policy.
6. App logs complete event details to database.

## Trust Boundaries

- Internet to app boundary (must use HTTPS in production)
- App to scanner boundary (internal network)
- App to storage/database boundary (filesystem and SQLite)

## Future Upgrades

- Replace SQLite with PostgreSQL
- Add object storage (S3-compatible)
- Add auth for admin and uploader portals
- Add asynchronous queue for very large files
