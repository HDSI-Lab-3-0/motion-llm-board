"""Small atomic status channel shared by the automatic runner and Pi display."""

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = Path(os.getenv("OUIJA_STATUS_FILE", PROJECT_ROOT / "data" / "ouija_status.json"))


_lock = threading.RLock()
_latest = None


def publish_status(status, heard="", response="", board="", detail="", source=""):
    with _lock:
        _publish_status(status, heard, response, board, detail, source)


def _publish_status(status, heard="", response="", board="", detail="", source=""):
    """Publish the latest display state without exposing partial JSON."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    global _latest
    payload = {
        "status": status,
        "heard": heard,
        "response": response,
        "board": board,
        "detail": detail,
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    fd, temporary = tempfile.mkstemp(prefix=".ouija-status-", dir=STATUS_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.write("\n")
        os.replace(temporary, STATUS_FILE)
        _latest = payload
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def status_heartbeat(interval=3):
    """Keep the current phase fresh during blocking generation and motion."""
    stopped = threading.Event()

    def beat():
        while not stopped.wait(interval):
            with _lock:
                if _latest:
                    fields = {k: v for k, v in _latest.items() if k != "updated_at"}
                    try:
                        _publish_status(**fields)
                    except OSError:
                        # A failed status write must not replay or interrupt motion.
                        pass

    worker = threading.Thread(target=beat, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stopped.set()
        worker.join()


def publish_progress(detail):
    """Attach hardware acknowledgements without changing the active phase."""
    with _lock:
        if _latest:
            fields = {k: v for k, v in _latest.items() if k != "updated_at"}
            fields["detail"] = detail
            _publish_status(**fields)
