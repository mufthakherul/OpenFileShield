from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OpenFileShield"
    app_host: str = "0.0.0.0"
    app_port: int = 8080

    database_url: str = "sqlite:///./data/openfileshield.db"
    upload_dir: str = "./data/uploads"
    quarantine_dir: str = "./data/quarantine"
    max_file_size_mb: int = 200
    allowed_file_types: str = "*"

    scan_required: bool = True
    clamd_host: str = "clamav"
    clamd_port: int = 3310

    upload_rate_limit_per_minute: int = 60
    upload_rate_burst_per_10_seconds: int = 12
    request_timeout_seconds: int = 120
    dedupe_mode: str = "reference"
    async_scan_enabled: bool = True
    async_scan_workers: int = 2
    trend_days_default: int = 14

    trust_x_forwarded_for: bool = True
    admin_token: str = "change-this-token"
    max_admin_results: int = 500
    default_admin_results: int = 100
    enable_csv_export: bool = True
    admin_auto_refresh_seconds: int = 15
    service_notice: str = "Public upload with malware scanning and audit logging"


settings = Settings()
