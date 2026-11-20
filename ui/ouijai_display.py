"""AUTOMATIC START: simple yellow Raspberry Pi status display."""

import json
import os
import time
import tkinter as tk
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = Path(os.getenv("OUIJA_STATUS_FILE", ROOT / "data" / "ouija_status.json"))
STALE_SECONDS = 15
YELLOW = "#F4C542"
DARK = "#211A0D"
ERROR = "#8B1E1E"


class OuijaiDisplay:
    def __init__(self, root):
        self.root = root
        root.title("OUIJAI")
        root.configure(bg=YELLOW)
        root.attributes("-fullscreen", os.getenv("OUIJA_UI_FULLSCREEN", "true").lower() in ("1", "true", "yes"))
        root.bind("<Escape>", lambda _event: root.destroy())

        self.title = tk.Label(root, text="OUIJAI", bg=YELLOW, fg=DARK,
                              font=("DejaVu Sans", 52, "bold"))
        self.title.pack(pady=(35, 15))
        self.status = tk.Label(root, text="CALIBRATING...", bg=YELLOW, fg=DARK,
                               font=("DejaVu Sans", 28, "bold"))
        self.status.pack(pady=15)
        self.heard = tk.Label(root, text="Heard:\n—", bg=YELLOW, fg=DARK,
                              justify="left", anchor="w", wraplength=850,
                              font=("DejaVu Sans", 26, "bold"))
        self.heard.pack(fill="x", padx=70, pady=15)
        self.response = tk.Label(root, text="Response:\n—", bg=YELLOW, fg=DARK,
                                 justify="left", anchor="w", wraplength=850,
                                 font=("DejaVu Sans", 26, "bold"))
        self.response.pack(fill="x", padx=70, pady=15)
        self.board = tk.Label(root, text="Board: —", bg=YELLOW, fg=DARK,
                              font=("DejaVu Sans", 16))
        self.board.pack(pady=15)
        self.detail = tk.Label(root, text="", bg=YELLOW, fg=DARK,
                               font=("DejaVu Sans", 13))
        self.detail.pack(pady=5)
        self.poll()

    def poll(self):
        data = None
        try:
            data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            updated = data.get("updated_at", "")
            # ISO timestamps are only used as a freshness hint; invalid values are stale.
            age = time.time() - __import__("datetime").datetime.fromisoformat(updated).timestamp()
            if age > STALE_SECONDS:
                data = {"status": "SERVICE NOT RUNNING", "detail": "No recent status update"}
        except (OSError, ValueError, json.JSONDecodeError):
            data = {"status": "SERVICE NOT RUNNING", "detail": "Automatic listener is unavailable"}

        current = str(data.get("status", "UNKNOWN")).replace("_", " ")
        current = {
            "STARTING": "CALIBRATING",
            "THINKING": "RESPONDING",
            "MOVING": "RESPONDING",
            "RESPONSE READY": "RESPONDING",
        }.get(current, current)
        self.status.configure(text=current, fg=ERROR if "ERROR" in current or "NOT RUNNING" in current else DARK)
        self.heard.configure(text=f"Heard:\n{data.get('heard') or '—'}")
        self.response.configure(text=f"Response:\n{data.get('response') or '—'}")
        self.board.configure(text=f"Board: {data.get('board') or '—'}")
        self.detail.configure(text=data.get("detail") or "")
        self.root.after(250, self.poll)


if __name__ == "__main__":
    window = tk.Tk()
    OuijaiDisplay(window)
    window.mainloop()
