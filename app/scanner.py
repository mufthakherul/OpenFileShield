import os

import clamd

from .config import settings


class ClamAVScanner:
    def __init__(self) -> None:
        self._client = None

    def _connect(self):
        if self._client is not None:
            return self._client
        self._client = clamd.ClamdNetworkSocket(host=settings.clamd_host, port=settings.clamd_port)
        return self._client

    def ping(self) -> bool:
        try:
            return self._connect().ping() == "PONG"
        except Exception:
            return False

    def scan_file(self, file_path: str) -> tuple[bool, str]:
        if not os.path.exists(file_path):
            return False, "file_not_found"

        try:
            result = self._connect().scan(file_path)
            if result is None:
                return True, "clean"

            # Example result: {'/path/to/file': ('FOUND', 'Eicar-Test-Signature')}
            status, signature = list(result.values())[0]
            if status == "FOUND":
                return False, f"infected:{signature}"
            return False, f"scan_error:{status}"
        except Exception as exc:
            return False, f"scanner_unavailable:{exc.__class__.__name__}"


scanner = ClamAVScanner()
