import csv
import hashlib
import io
import os
import shutil
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .models import UploadRecord
from .scanner import scanner
from .schemas import HealthResponse, UploadResponse, UploadStatsResponse

app = FastAPI(title=settings.app_name, version="0.2.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._minute_windows: dict[str, deque[float]] = defaultdict(deque)
        self._burst_windows: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, per_minute: int, burst_per_10s: int) -> bool:
        now = time.time()

        minute_window = self._minute_windows[key]
        while minute_window and now - minute_window[0] > 60:
            minute_window.popleft()

        burst_window = self._burst_windows[key]
        while burst_window and now - burst_window[0] > 10:
            burst_window.popleft()

        if len(minute_window) >= per_minute or len(burst_window) >= burst_per_10s:
            return False

        minute_window.append(now)
        burst_window.append(now)
        return True


limiter = InMemoryRateLimiter()


def ensure_sqlite_columns() -> None:
    extra_columns: dict[str, str] = {
        "file_extension": "TEXT",
        "request_id": "TEXT",
        "processing_ms": "INTEGER DEFAULT 0",
        "referer": "TEXT",
        "origin": "TEXT",
        "device_fingerprint": "TEXT",
    }

    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(upload_records)"))
        existing = {row[1] for row in rows}
        for column, sql_type in extra_columns.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE upload_records ADD COLUMN {column} {sql_type}"))
        conn.commit()


@app.on_event("startup")
def startup() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.quarantine_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()


def get_client_ip(request: Request) -> str:
    if settings.trust_x_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def device_fingerprint(client_ip: str, user_agent: str, accept_language: str) -> str:
    source = f"{client_ip}|{user_agent}|{accept_language}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def save_stream_to_file(upload_file: UploadFile, output_path: str) -> tuple[int, str]:
    sha256 = hashlib.sha256()
    size = 0
    with open(output_path, "wb") as out_file:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            sha256.update(chunk)
            out_file.write(chunk)
    return size, sha256.hexdigest()


def ensure_admin(x_admin_token: str | None) -> None:
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


def build_upload_record_payload(row: UploadRecord) -> dict:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "original_filename": row.original_filename,
        "saved_filename": row.saved_filename,
        "file_size_bytes": row.file_size_bytes,
        "mime_type": row.mime_type,
        "file_extension": row.file_extension,
        "sha256": row.sha256,
        "upload_status": row.upload_status,
        "scan_result": row.scan_result,
        "processing_ms": row.processing_ms,
        "uploader_ip": row.uploader_ip,
        "user_agent": row.user_agent,
        "accept_language": row.accept_language,
        "referer": row.referer,
        "origin": row.origin,
        "device_fingerprint": row.device_fingerprint,
        "uploader_name": row.uploader_name,
        "uploader_email": row.uploader_email,
        "created_at": row.created_at,
    }


def query_uploads(
    db: Session,
    *,
    status: str | None,
    q: str | None,
    ip: str | None,
    limit: int,
    from_ts: str | None,
    to_ts: str | None,
) -> list[UploadRecord]:
    query = db.query(UploadRecord)

    if status:
        query = query.filter(UploadRecord.upload_status == status)
    if q:
        pattern = f"%{q}%"
        query = query.filter(UploadRecord.original_filename.ilike(pattern))
    if ip:
        query = query.filter(UploadRecord.uploader_ip == ip)
    if from_ts:
        query = query.filter(UploadRecord.created_at >= datetime.fromisoformat(from_ts))
    if to_ts:
        query = query.filter(UploadRecord.created_at <= datetime.fromisoformat(to_ts))

    return query.order_by(UploadRecord.created_at.desc()).limit(limit).all()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "max_file_mb": settings.max_file_size_mb,
            "service_notice": settings.service_notice,
        },
    )


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", scanner="up" if scanner.ping() else "down")


@app.get("/api/stats", response_model=UploadStatsResponse)
def stats(
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UploadStatsResponse:
    ensure_admin(x_admin_token)
    total = db.query(UploadRecord).count()
    stored = db.query(UploadRecord).filter(UploadRecord.upload_status == "stored").count()
    rejected = db.query(UploadRecord).filter(UploadRecord.upload_status == "rejected").count()
    return UploadStatsResponse(total=total, stored=stored, rejected=rejected, scanner_up=scanner.ping())


@app.post("/api/upload", response_model=UploadResponse)
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    consent: bool = Form(...),
    uploader_name: str | None = Form(default=None),
    uploader_email: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    request_id = uuid.uuid4().hex

    if not consent:
        raise HTTPException(status_code=400, detail="Consent is required")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    uploader_ip = get_client_ip(request)
    if not limiter.allow(
        uploader_ip,
        per_minute=settings.upload_rate_limit_per_minute,
        burst_per_10s=settings.upload_rate_burst_per_10_seconds,
    ):
        raise HTTPException(status_code=429, detail="Too many uploads from this IP. Please retry shortly.")

    ext = Path(file.filename).suffix.lower()
    token = str(uuid.uuid4())
    quarantined_path = os.path.join(settings.quarantine_dir, f"{token}{ext}")

    try:
        size, digest = save_stream_to_file(file, quarantined_path)
    finally:
        file.file.close()

    if size > settings.max_file_size_mb * 1024 * 1024:
        if os.path.exists(quarantined_path):
            os.remove(quarantined_path)
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_file_size_mb} MB")

    is_clean, scan_result = scanner.scan_file(quarantined_path)

    ua = request.headers.get("user-agent", "unknown")
    lang = request.headers.get("accept-language", "")
    referer = request.headers.get("referer")
    origin = request.headers.get("origin")
    fingerprint = device_fingerprint(uploader_ip, ua, lang)
    processing_ms = int((time.perf_counter() - started) * 1000)

    if not is_clean and settings.scan_required:
        if os.path.exists(quarantined_path):
            os.remove(quarantined_path)

        record = UploadRecord(
            request_id=request_id,
            original_filename=file.filename,
            saved_filename="",
            file_size_bytes=size,
            mime_type=file.content_type or "application/octet-stream",
            file_extension=ext,
            sha256=digest,
            upload_status="rejected",
            scan_result=scan_result,
            processing_ms=processing_ms,
            uploader_ip=uploader_ip,
            user_agent=ua,
            accept_language=lang,
            referer=referer,
            origin=origin,
            device_fingerprint=fingerprint,
            uploader_name=uploader_name,
            uploader_email=uploader_email,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        raise HTTPException(status_code=400, detail=f"Upload rejected: {scan_result}")

    final_name = f"{token}{ext}"
    final_path = os.path.join(settings.upload_dir, final_name)
    shutil.move(quarantined_path, final_path)

    record = UploadRecord(
        request_id=request_id,
        original_filename=file.filename,
        saved_filename=final_name,
        file_size_bytes=size,
        mime_type=file.content_type or "application/octet-stream",
        file_extension=ext,
        sha256=digest,
        upload_status="stored",
        scan_result=scan_result,
        processing_ms=processing_ms,
        uploader_ip=uploader_ip,
        user_agent=ua,
        accept_language=lang,
        referer=referer,
        origin=origin,
        device_fingerprint=fingerprint,
        uploader_name=uploader_name,
        uploader_email=uploader_email,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return UploadResponse(
        id=record.id,
        request_id=record.request_id,
        original_filename=record.original_filename,
        sha256=record.sha256,
        upload_status=record.upload_status,
        scan_result=record.scan_result,
        file_size_bytes=record.file_size_bytes,
        processing_ms=record.processing_ms,
        created_at=record.created_at,
    )


@app.get("/api/uploads")
def list_uploads(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    ip: str | None = Query(default=None),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
    limit: int = Query(default=settings.default_admin_results, ge=1, le=settings.max_admin_results),
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    ensure_admin(x_admin_token)
    rows = query_uploads(
        db,
        status=status,
        q=q,
        ip=ip,
        limit=limit,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    return [build_upload_record_payload(row) for row in rows]


@app.get("/api/uploads/export.csv")
def export_uploads_csv(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    ip: str | None = Query(default=None),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
    limit: int = Query(default=settings.default_admin_results, ge=1, le=settings.max_admin_results),
    x_admin_token: str | None = Header(default=None),
    x_admin_token_query: str | None = Query(default=None, alias="x_admin_token"),
    db: Session = Depends(get_db),
):
    ensure_admin(x_admin_token or x_admin_token_query)
    if not settings.enable_csv_export:
        raise HTTPException(status_code=403, detail="CSV export disabled")

    rows = query_uploads(
        db,
        status=status,
        q=q,
        ip=ip,
        limit=limit,
        from_ts=from_ts,
        to_ts=to_ts,
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "request_id",
            "created_at",
            "original_filename",
            "saved_filename",
            "file_size_bytes",
            "mime_type",
            "file_extension",
            "sha256",
            "upload_status",
            "scan_result",
            "processing_ms",
            "uploader_ip",
            "device_fingerprint",
            "uploader_name",
            "uploader_email",
            "user_agent",
            "accept_language",
            "referer",
            "origin",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(build_upload_record_payload(row))

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=upload_audit.csv"},
    )
