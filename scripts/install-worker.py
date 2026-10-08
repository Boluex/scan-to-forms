#!/usr/bin/env python3
"""Install user services on this Ubuntu host without root or embedded secrets."""

import argparse
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument(
    "--start",
    action="store_true",
    help="Start OCR after installing; does not enable boot startup",
)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
venv = root / ".venv/bin"
if not (venv / "celery").exists() or not (root / ".env.worker").exists():
    raise SystemExit(
        "Create .venv, install requirements, and fill .env.worker first. See docs/REMOTE_OCR_WORKER.md"
    )
os.chmod(root / ".env.worker", 0o600)
units = Path.home() / ".config/systemd/user"
units.mkdir(parents=True, exist_ok=True)


# Systemd quotes paths with spaces. Escape percent specifiers and literal quotes.
def quote(value):
    return (
        '"'
        + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
        + '"'
    )


common = f"""[Unit]
Description=ScanToForms {{description}}
After=network-online.target

[Service]
Type=simple
WorkingDirectory={str(root / "backend").replace("%", "%%")}
Environment={quote("SCANTO_FORMS_ENV_FILE=" + str(root / ".env.worker"))}
Environment={quote("PADDLE_PDX_CACHE_HOME=" + str(root / ".cache/paddlex"))}
Environment=OMP_NUM_THREADS=1
Environment=OPENBLAS_NUM_THREADS=1
ExecStart={{command}}
Restart=on-failure
RestartSec=30
TimeoutStopSec=660
KillSignal=SIGTERM
UMask=0077
Nice=10

[Install]
WantedBy=default.target
"""
services = {
    "scanforms-ocr": (
        "OCR worker",
        f"{quote(venv / 'celery')} -A config worker --loglevel=info --concurrency=1 --hostname=ubuntu@%H --without-gossip --without-mingle --without-heartbeat",
    ),
    "scanforms-push": (
        "push notification sender",
        f"{quote(venv / 'python')} manage.py send_push_notifications --watch --interval=30",
    ),
}
for name, (description, command) in services.items():
    (units / f"{name}.service").write_text(
        common.format(description=description, command=command)
    )
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
print(
    "Installed scanforms-ocr and scanforms-push user services. Automatic startup is disabled."
)
if args.start:
    subprocess.run(["systemctl", "--user", "start", "scanforms-ocr"], check=True)
    subprocess.run(["systemctl", "--user", "is-active", "scanforms-ocr"], check=True)
print(
    "Start push only after configuring Firebase: systemctl --user start scanforms-push"
)
