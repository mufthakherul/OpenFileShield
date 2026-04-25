import os
import signal
import subprocess
import sys
from pathlib import Path

from app.config import settings


def start_instance(role: str, host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["APP_ROLE"] = role
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    return subprocess.Popen(command, cwd=str(Path(__file__).resolve().parents[1]), env=env)


def main() -> int:
    public_host = settings.app_host
    public_port = settings.public_port
    admin_host = settings.admin_host
    admin_port = settings.admin_port

    public_proc = start_instance("public", public_host, public_port)
    admin_proc = start_instance("admin", admin_host, admin_port)

    print(f"Public app: http://{public_host}:{public_port}")
    print(f"Admin app:  http://{admin_host}:{admin_port}")

    try:
        public_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (public_proc, admin_proc):
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
