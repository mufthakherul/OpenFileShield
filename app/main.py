import csv
import hashlib
import ipaddress
import io
import os
import queue
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .models import UploadRecord
from .scanner import scanner
from .schemas import HealthResponse, TrendPoint, UploadBatchResponse, UploadResponse, UploadStatsResponse

@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.quarantine_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()

    if settings.async_scan_enabled:
        for idx in range(settings.async_scan_workers):
            thread = threading.Thread(target=queue_worker, args=(idx,), daemon=True)
            thread.start()
            workers.append(thread)

    yield

    stop_event.set()
    for _ in workers:
        scan_queue.put(None)


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
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
scan_queue: queue.Queue[dict | None] = queue.Queue()
stop_event = threading.Event()
workers: list[threading.Thread] = []

ADMIN_PATH_PREFIXES = (
    "/admin",
    "/api/stats",
    "/api/trends",
    "/api/upload/",
    "/api/uploads",
)
PUBLIC_PATH_PREFIXES = (
    "/",
    "/api/health",
    "/api/upload",
    "/api/upload/async",
    "/static",
    "/favicon.ico",
)


def ensure_sqlite_columns() -> None:
    extra_columns: dict[str, str] = {
        "file_extension": "TEXT",
        "request_id": "TEXT",
        "processing_ms": "INTEGER DEFAULT 0",
        "referer": "TEXT",
        "origin": "TEXT",
        "device_fingerprint": "TEXT",
        "scan_engine": "TEXT DEFAULT 'clamav'",
        "dedupe_of_id": "INTEGER",
        "uploader_notes": "TEXT",
    }

    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(upload_records)"))
        existing = {row[1] for row in rows}
        for column, sql_type in extra_columns.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE upload_records ADD COLUMN {column} {sql_type}"))
        conn.commit()


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


def is_admin_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in ADMIN_PATH_PREFIXES)


def is_public_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def is_local_or_private_ip(value: str) -> bool:
    try:
        ip_addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip_addr.is_loopback or ip_addr.is_private


def ensure_local_admin_access(request: Request) -> None:
    if not settings.admin_local_only:
        return
    client_ip = get_client_ip(request)
    if not is_local_or_private_ip(client_ip):
        raise HTTPException(status_code=403, detail="Admin access is limited to local/private networks")


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
        "scan_engine": row.scan_engine,
        "dedupe_of_id": row.dedupe_of_id,
        "processing_ms": row.processing_ms,
        "uploader_ip": row.uploader_ip,
        "user_agent": row.user_agent,
        "accept_language": row.accept_language,
        "referer": row.referer,
        "origin": row.origin,
        "device_fingerprint": row.device_fingerprint,
        "uploader_name": row.uploader_name,
        "uploader_email": row.uploader_email,
        "uploader_notes": row.uploader_notes,
        "created_at": row.created_at,
    }


def normalize_upload_files(
    file: UploadFile | None,
    files: list[UploadFile] | None,
) -> list[UploadFile]:
    upload_files: list[UploadFile] = []
    if file is not None:
        upload_files.append(file)
    if files:
        upload_files.extend(files)
    return [upload_file for upload_file in upload_files if upload_file.filename]


def build_upload_response(record: UploadRecord) -> UploadResponse:
    return UploadResponse(
        id=record.id,
        request_id=record.request_id,
        original_filename=record.original_filename,
        sha256=record.sha256,
        upload_status=record.upload_status,
        scan_result=record.scan_result,
        scan_engine=record.scan_engine,
        dedupe_of_id=record.dedupe_of_id,
        file_size_bytes=record.file_size_bytes,
        processing_ms=record.processing_ms,
        created_at=record.created_at,
    )


def store_upload_record(
    db: Session,
    *,
    request: Request,
    upload_file: UploadFile,
    request_id: str,
    started: float,
    uploader_name: str | None,
    uploader_email: str | None,
    uploader_notes: str | None,
    async_mode: bool,
) -> UploadResponse:
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    uploader_ip = get_client_ip(request)
    ext = Path(upload_file.filename).suffix.lower()
    token = str(uuid.uuid4())
    final_name = f"{token}{ext}"
    quarantined_path = os.path.join(settings.quarantine_dir, final_name)

    try:
        size, digest = save_stream_to_file(upload_file, quarantined_path)
    finally:
        upload_file.file.close()

    record = UploadRecord(
        request_id=request_id,
        original_filename=upload_file.filename,
        saved_filename="",
        file_size_bytes=size,
        mime_type=upload_file.content_type or "application/octet-stream",
        file_extension=ext,
        sha256=digest,
        upload_status="queued" if async_mode else "processing",
        scan_result="queued" if async_mode else "processing",
        scan_engine="queue" if async_mode else "pending",
        dedupe_of_id=None,
        processing_ms=0,
        uploader_name=uploader_name,
        uploader_email=uploader_email,
        uploader_notes=uploader_notes,
    )
    enrich_record_from_headers(record, request, uploader_ip)
    db.add(record)
    db.commit()
    db.refresh(record)

    if async_mode:
        scan_queue.put(
            {
                "record_id": record.id,
                "quarantined_path": quarantined_path,
                "final_name": final_name,
                "started": started,
            }
        )
        return build_upload_response(record)

    processed = process_record(
        db,
        record=record,
        quarantined_path=quarantined_path,
        final_name=final_name,
        started=started,
    )
    return build_upload_response(processed)


def upload_batch_response(records: list[UploadResponse], request_id: str) -> UploadBatchResponse:
    queued = sum(1 for record in records if record.upload_status == "queued")
    processing = sum(1 for record in records if record.upload_status == "processing")
    checking = queued + processing
    return UploadBatchResponse(
        request_id=request_id,
        total_files=len(records),
        stored=sum(1 for record in records if record.upload_status == "stored" or record.upload_status == "stored_duplicate"),
        rejected=sum(1 for record in records if record.upload_status == "rejected"),
        queued=queued,
        processing=processing,
        checking=checking,
        items=records,
    )


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


def find_dedupe_match(db: Session, digest: str, current_id: int | None = None) -> UploadRecord | None:
    query = db.query(UploadRecord).filter(UploadRecord.sha256 == digest)
    query = query.filter(UploadRecord.upload_status.in_(["stored", "stored_duplicate"]))
    if current_id is not None:
        query = query.filter(UploadRecord.id != current_id)
    return query.order_by(UploadRecord.created_at.asc()).first()


def enrich_record_from_headers(record: UploadRecord, request: Request, uploader_ip: str) -> None:
    ua = request.headers.get("user-agent", "unknown")
    lang = request.headers.get("accept-language", "")
    record.uploader_ip = uploader_ip
    record.user_agent = ua
    record.accept_language = lang
    record.referer = request.headers.get("referer")
    record.origin = request.headers.get("origin")
    record.device_fingerprint = device_fingerprint(uploader_ip, ua, lang)


def process_record(
    db: Session,
    *,
    record: UploadRecord,
    quarantined_path: str,
    final_name: str,
    started: float,
) -> UploadRecord:
    dedupe_match = None
    if settings.dedupe_mode == "reference":
        dedupe_match = find_dedupe_match(db, record.sha256, current_id=record.id)

    if dedupe_match is not None:
        if os.path.exists(quarantined_path):
            os.remove(quarantined_path)
        record.saved_filename = dedupe_match.saved_filename
        record.upload_status = "stored_duplicate"
        record.scan_result = "clean_deduplicated"
        record.scan_engine = "dedupe-cache"
        record.dedupe_of_id = dedupe_match.id
        record.processing_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        db.refresh(record)
        return record

    if settings.malware_scan_enabled:
        is_clean, scan_result = scanner.scan_file(quarantined_path)
        record.scan_engine = "clamav"
    else:
        is_clean, scan_result = True, "scan_disabled"
        record.scan_engine = "disabled"

    if not is_clean and settings.scan_required:
        if os.path.exists(quarantined_path):
            os.remove(quarantined_path)
        record.saved_filename = ""
        record.upload_status = "rejected"
        record.scan_result = scan_result
        record.processing_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        db.refresh(record)
        return record

    final_path = os.path.join(settings.upload_dir, final_name)
    shutil.move(quarantined_path, final_path)

    record.saved_filename = final_name
    record.upload_status = "stored"
    record.scan_result = scan_result
    record.processing_ms = int((time.perf_counter() - started) * 1000)
    db.commit()
    db.refresh(record)
    return record


def queue_worker(worker_id: int) -> None:
    while not stop_event.is_set():
        try:
            task = scan_queue.get(timeout=1)
        except queue.Empty:
            continue

        if task is None:
            scan_queue.task_done()
            break

        db = SessionLocal()
        try:
            record = db.query(UploadRecord).filter(UploadRecord.id == task["record_id"]).first()
            if record is None:
                continue
            process_record(
                db,
                record=record,
                quarantined_path=task["quarantined_path"],
                final_name=task["final_name"],
                started=task["started"],
            )
        except Exception:
            if record is not None:
                record.upload_status = "rejected"
                record.scan_result = "internal_processing_error"
                db.commit()
        finally:
            db.close()
            scan_queue.task_done()


@app.middleware("http")
async def app_role_guard(request: Request, call_next):
    path = request.url.path
    role = settings.app_role.lower()

    if role == "public" and is_admin_path(path):
        return Response(status_code=404)
    if role == "admin" and not is_admin_path(path) and not is_public_path(path):
        return Response(status_code=404)
    if role == "admin" and is_admin_path(path):
        try:
            ensure_local_admin_access(request)
        except HTTPException as exc:
            return Response(content=exc.detail, status_code=exc.status_code)

    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if settings.app_role.lower() == "admin":
        ensure_local_admin_access(request)
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={
                "request": request,
                "admin_auto_refresh_seconds": settings.admin_auto_refresh_seconds,
                "trend_days_default": settings.trend_days_default,
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "service_notice": settings.service_notice,
            "admin_base_url": settings.admin_base_url,
        },
    )


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    ensure_local_admin_access(request)
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "request": request,
            "admin_auto_refresh_seconds": settings.admin_auto_refresh_seconds,
            "trend_days_default": settings.trend_days_default,
        },
    )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if not settings.malware_scan_enabled:
        return HealthResponse(status="ok", scanner="disabled")
    return HealthResponse(status="ok", scanner="up" if scanner.ping() else "down")


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/api/stats", response_model=UploadStatsResponse)
def stats(
    request: Request,
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UploadStatsResponse:
    ensure_local_admin_access(request)
    ensure_admin(x_admin_token)
    total = db.query(UploadRecord).count()
    stored = db.query(UploadRecord).filter(UploadRecord.upload_status == "stored").count()
    rejected = db.query(UploadRecord).filter(UploadRecord.upload_status == "rejected").count()
    duplicates = db.query(UploadRecord).filter(UploadRecord.upload_status == "stored_duplicate").count()
    queued = db.query(UploadRecord).filter(UploadRecord.upload_status == "queued").count()
    return UploadStatsResponse(
        total=total,
        stored=stored,
        rejected=rejected,
        duplicates=duplicates,
        queued=queued,
        scanner_up=(not settings.malware_scan_enabled) or scanner.ping(),
    )


@app.get("/api/trends", response_model=list[TrendPoint])
def trends(
    request: Request,
    days: int = Query(default=settings.trend_days_default, ge=1, le=60),
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    ensure_local_admin_access(request)
    ensure_admin(x_admin_token)
    start_day = datetime.now(UTC) - timedelta(days=days - 1)

    rows = (
        db.query(UploadRecord.created_at, UploadRecord.upload_status)
        .filter(UploadRecord.created_at >= start_day.replace(tzinfo=None))
        .all()
    )

    buckets: dict[str, dict[str, int]] = {}
    for offset in range(days):
        day = (datetime.now(UTC) - timedelta(days=(days - 1 - offset))).date().isoformat()
        buckets[day] = {"stored": 0, "rejected": 0, "queued": 0}

    for created_at, upload_status in rows:
        day = created_at.date().isoformat()
        if day not in buckets:
            continue
        if upload_status == "stored" or upload_status == "stored_duplicate":
            buckets[day]["stored"] += 1
        elif upload_status == "rejected":
            buckets[day]["rejected"] += 1
        elif upload_status == "queued":
            buckets[day]["queued"] += 1

    return [
        TrendPoint(day=day, stored=values["stored"], rejected=values["rejected"], queued=values["queued"])
        for day, values in buckets.items()
    ]


@app.post("/api/upload", response_model=UploadBatchResponse)
def upload_file(
    request: Request,
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    consent: bool = Form(...),
    uploader_name: str | None = Form(default=None),
    uploader_email: str | None = Form(default=None),
    uploader_notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    request_id = uuid.uuid4().hex

    if not consent:
        raise HTTPException(status_code=400, detail="Consent is required")
    upload_files = normalize_upload_files(file, files)
    if not upload_files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploader_ip = get_client_ip(request)
    if not limiter.allow(
        uploader_ip,
        per_minute=settings.upload_rate_limit_per_minute,
        burst_per_10s=settings.upload_rate_burst_per_10_seconds,
    ):
        raise HTTPException(status_code=429, detail="Too many uploads from this IP. Please retry shortly.")

    records: list[UploadResponse] = []
    for upload_file in upload_files:
        records.append(
            store_upload_record(
                db,
                request=request,
                upload_file=upload_file,
                request_id=request_id,
                started=started,
                uploader_name=uploader_name,
                uploader_email=uploader_email,
                uploader_notes=uploader_notes,
                async_mode=False,
            )
        )

    return upload_batch_response(records, request_id)


@app.post("/api/upload/async", response_model=UploadBatchResponse)
def upload_file_async(
    request: Request,
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    consent: bool = Form(...),
    uploader_name: str | None = Form(default=None),
    uploader_email: str | None = Form(default=None),
    uploader_notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if not settings.async_scan_enabled:
        raise HTTPException(status_code=403, detail="Async scan is disabled")

    started = time.perf_counter()
    request_id = uuid.uuid4().hex

    if not consent:
        raise HTTPException(status_code=400, detail="Consent is required")
    upload_files = normalize_upload_files(file, files)
    if not upload_files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploader_ip = get_client_ip(request)
    if not limiter.allow(
        uploader_ip,
        per_minute=settings.upload_rate_limit_per_minute,
        burst_per_10s=settings.upload_rate_burst_per_10_seconds,
    ):
        raise HTTPException(status_code=429, detail="Too many uploads from this IP. Please retry shortly.")

    records: list[UploadResponse] = []
    for upload_file in upload_files:
        records.append(
            store_upload_record(
                db,
                request=request,
                upload_file=upload_file,
                request_id=request_id,
                started=started,
                uploader_name=uploader_name,
                uploader_email=uploader_email,
                uploader_notes=uploader_notes,
                async_mode=True,
            )
        )

    return upload_batch_response(records, request_id)


@app.get("/api/upload/{upload_id}")
def get_upload(
    request: Request,
    upload_id: int,
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    ensure_local_admin_access(request)
    ensure_admin(x_admin_token)
    row = db.query(UploadRecord).filter(UploadRecord.id == upload_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return build_upload_record_payload(row)


@app.get("/api/uploads")
def list_uploads(
    request: Request,
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    ip: str | None = Query(default=None),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
    limit: int = Query(default=settings.default_admin_results, ge=1, le=settings.max_admin_results),
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    ensure_local_admin_access(request)
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
    request: Request,
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
    ensure_local_admin_access(request)
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
            "scan_engine",
            "dedupe_of_id",
            "processing_ms",
            "uploader_ip",
            "device_fingerprint",
            "uploader_name",
            "uploader_email",
            "uploader_notes",
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
