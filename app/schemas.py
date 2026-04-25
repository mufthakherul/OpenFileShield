from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    id: int
    request_id: str
    original_filename: str
    sha256: str
    upload_status: str
    scan_result: str
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
    scanner_up: bool
