from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    id: int
    request_id: str
    original_filename: str
    sha256: str
    upload_status: str
    scan_result: str
    scan_engine: str
    dedupe_of_id: int | None = None
    file_size_bytes: int
    processing_ms: int
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    scanner: str


class UploadStatsResponse(BaseModel):
    total: int
    stored: int
    rejected: int
    duplicates: int
    queued: int
    scanner_up: bool


class TrendPoint(BaseModel):
    day: str
    stored: int
    rejected: int
    queued: int
