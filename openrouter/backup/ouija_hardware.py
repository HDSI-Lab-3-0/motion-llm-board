import time
import serial
import json
import os
from pathlib import Path
from typing import Optional

# --- CONFIGURATION ---
DEFAULT_PORT = "/dev/cu.usbmodem1101"
DEFAULT_BAUD = 115200

# --- MAP (X Range: 1..42 | Y: 0..50) ---
# Reduced vocabulary board to spell: YES / NO / MAYBE using letters: Y E S N O M A B (+ E reused)
MAP = {
    # Reference points
    "PRELOAD": (1, 0),     # approach point to reduce backlash
    " ": (21, 25),         # Rest / neutral (adjust if you want)

    # YES (top)
    "Y": (8, 44),
    "E": (21, 48),
    "S": (34, 44),

    # NO (bottom-ish)
    "N": (8, 10),
    "O": (34, 10),

    # MAYBE letters (middle)
    "M": (14, 30),
    "A": (28, 30),
    "B": (21, 20),

    # Optional control tokens if you still call these elsewhere
    "YES": (10, 46),
    "NO": (32, 12),
    "GOODBYE": (21, 2),
}


class OuijaHardware:
    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baud: int = DEFAULT_BAUD,
        timeout: float = 1.0,
        map_override_path: Optional[str] = None,
        debug_serial: bool = False,
    ):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.debug_serial = debug_serial

        self.arduino = None

        # ✅ Always create map first
        self.map = dict(MAP)

        # ✅ Then attempt override safely (never crash init)
        try:
            self._load_map_override(map_override_path)
        except Exception as e:
            print(f"[WARN] Map override failed: {e}")

    def _load_map_override(self, map_override_path: Optional[str]):
        # Safety: ensure map exists (prevents AttributeError)
        if not hasattr(self, "map"):
            self.map = dict(MAP)

        # Priority:
        # 1) explicit arg
        # 2) env var OUJIA_MAP_OVERRIDE_PATH
        # 3) openrouter/ouija_map_override.json if present
        path = map_override_path or os.getenv("OUJIA_MAP_OVERRIDE_PATH")
        if not path:
            path = str(Path(__file__).resolve().parent / "ouija_map_override.json")

        p = Path(path)
        if not p.exists():
            return

        raw_text = p.read_text(encoding="utf-8")
        raw = json.loads(raw_text)

        if not isinstance(raw, dict):
            return

        for k, v in raw.items():
            if not isinstance(k, str):
                continue
            if (
                isinstance(v, (list, tuple))
                and len(v) == 2
                and isinstance(v[0], (int, float))
                and isinstance(v[1], (int, float))
            ):
                self.map[k.upper()] = (float(v[0]), float(v[1]))

    def connect(self):
        if self.arduino and self.arduino.is_open:
            return

        self.arduino = serial.Serial(self.port, self.baud, timeout=self.timeout)

        # give Arduino time to reset on serial open
        time.sleep(2)

        # Optional: clear any buffered startup text
        try:
            self.arduino.reset_input_buffer()
        except Exception:
            pass

    def close(self):
        if self.arduino:
            try:
                self.arduino.close()
            except Exception:
                pass

    def _send_command(self, command: str):
        if not self.arduino or not self.arduino.is_open:
            raise RuntimeError("Hardware not connected. Call connect() first.")

        if self.debug_serial:
            print(f"[SERIAL->] {command}")

        self.arduino.write(f"{command}\n".encode("utf-8"))

        # Wait for 'ok' with timeout (prevents hanging forever)
        t0 = time.time()
        while True:
            line = self.arduino.readline().decode("utf-8", errors="ignore").strip()

            if self.debug_serial and line:
                print(f"[SERIAL<-] {line}")

            if "ok" in line.lower():
                return

            if time.time() - t0 > 5.0:
                raise TimeoutError(f"No 'ok' received for command: {command}")

    def raw(self, command: str):
        """Send raw gcode/serial command (expects Arduino to respond with ok)."""
        self._send_command(command)

    def move_xy(self, x: float, y: float, speed: int = 400, dwell: float = 1.2):
        """Move to raw X/Y coordinates."""
        self._send_command(f"G1 X{x} Y{y} F{speed}")
        time.sleep(dwell)

    def move_to(self, token: str, speed: int = 400, dwell: float = 1.2):
        """Move to a mapped token like 'A' or 'YES'."""
        token = token.upper()
        if token not in self.map:
            raise ValueError(f"Unknown token '{token}'. Not in MAP.")
        x, y = self.map[token]
        self.move_xy(x, y, speed=speed, dwell=dwell)

    def rest(self, speed: int = 500):
        """Go to rest/center position."""
        self.move_to(" ", speed=speed, dwell=0.5)

    def spell_text(self, text: str, speed: int = 400):
        """
        Move letter-by-letter for simple spelling.
        Adds a PRELOAD move before each character to reduce backlash / rail slop effects.
        """
        text = text.upper()
        for ch in text:
            if ch == " ":
                self.move_to(" ", speed=speed, dwell=0.6)
            elif ch in self.map:
                # Always approach from same direction for repeatability
                if "PRELOAD" in self.map:
                    self.move_to("PRELOAD", speed=speed, dwell=0.35)
                self.move_to(ch, speed=speed, dwell=1.2)
            else:
                # ignore punctuation/unsupported symbols
                continue


# Optional: quick manual test mode (nice for debugging without calibrate_letters.py)
if __name__ == "__main__":
    hw = OuijaHardware(debug_serial=False)
    hw.connect()
    print("Connected. Type Y/E/S/N/O/M/A/B, YES, NO, GOODBYE, rest, or q to quit.")
    try:
        while True:
            s = input("test> ").strip()
            if not s:
                continue
            if s.lower() in ("q", "quit", "exit"):
                break
            if s.lower() == "rest":
                hw.rest()
                continue
            token = s.upper()
            if token in hw.map:
                hw.move_to(token)
            else:
                # If they type a word like MAYBE, spell it
                if len(token) > 1:
                    print(f'Spelling "{token}"')
                    hw.spell_text(token)
                    hw.rest(speed=500)
                else:
                    print("Not in map.")
    finally:
        hw.close()
        print("Closed.")