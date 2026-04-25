# Changelog

## 0.3.0 - 2026-04-25

- Added optional asynchronous background scan queue endpoint (`/api/upload/async`)
- Added SHA256 deduplication (reference mode) to reduce duplicate storage
- Added admin trend analytics API (`/api/trends`) and live auto-refresh dashboard
- Expanded admin stats with duplicates and queued counters
- Added per-upload scan engine attribution and dedupe linkage in records
- Added upload detail endpoint (`/api/upload/{upload_id}`)
- Improved frontend UX with async/sync scan mode selector
- Improved admin UI with trend chart rendering and refresh controls
- Expanded environment customization options for queue and analytics behavior

## 0.1.0 - 2026-04-25

- Initial project scaffold
- FastAPI upload service
- ClamAV integration via clamd
- Metadata/audit logging to SQLite
- Basic web upload UI
- Docker Compose setup for app + ClamAV
- Security and privacy documentation
