"""Small atomic status channel shared by the automatic runner and Pi display."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = Path(os.getenv("OUIJA_STATUS_FILE", PROJECT_ROOT / "data" / "ouija_status.json"))


def publish_status(status, heard="", response="", board="", detail=""):
    """Publish the latest display state without exposing partial JSON."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "heard": heard,
        "response": response,
        "board": board,
        "detail": detail,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    fd, temporary = tempfile.mkstemp(prefix=".ouija-status-", dir=STATUS_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.write("\n")
        os.replace(temporary, STATUS_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
