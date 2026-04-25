from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class UploadRecord(Base):
    __tablename__ = "upload_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    saved_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(50), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    upload_status: Mapped[str] = mapped_column(String(32), nullable=False)
    scan_result: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    processing_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    uploader_ip: Mapped[str] = mapped_column(String(128), nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    accept_language: Mapped[str] = mapped_column(String(255), nullable=True)
    referer: Mapped[str] = mapped_column(String(1024), nullable=True)
    origin: Mapped[str] = mapped_column(String(1024), nullable=True)
    device_fingerprint: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    uploader_name: Mapped[str] = mapped_column(String(255), nullable=True)
    uploader_email: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
