import time
import serial
import json
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import glob

# =====================================================
# CONFIGURATION
# =====================================================

DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 1.0

# If you pass port=None, we'll try to auto-detect on Mac/Pi.
DEFAULT_PORT = None  # <-- IMPORTANT: let it auto-detect by default

# =====================================================
# MAP COORDINATES (in MILLIMETERS) around REST=(0,0)
# You should calibrate these with your board by adjusting ouija_map_override.json.
# =====================================================

# NOTE:
# - Set REST " " to (0,0). You will physically place the planchette at REST on startup.
# - Then we run G92 X0 Y0 so the coordinate system is repeatable after restart.
MAP: Dict[str, Tuple[float, float]] = {
    # Control elements / rest
    " ": (0.0, 0.0),       # REST / center reference (physical reference)
    "YES": (-60.0, 60.0),
    "NO": (60.0, 60.0),
    "GOODBYE": (0.0, -70.0),

    # A..M (upper arc-ish) (ROUGH defaults - override via json)
    "A": (-70.0, 35.0),
    "B": (-58.0, 44.0),
    "C": (-46.0, 50.0),
    "D": (-34.0, 54.0),
    "E": (-22.0, 56.0),
    "F": (-10.0, 56.0),
    "G": (10.0, 56.0),
    "H": (22.0, 56.0),
    "I": (34.0, 54.0),
    "J": (46.0, 50.0),
    "K": (58.0, 44.0),
    "L": (70.0, 35.0),
    "M": (0.0, 40.0),

    # N..Z (lower arc-ish) (ROUGH defaults - override via json)
    "N": (-70.0, 5.0),
    "O": (-58.0, -2.0),
    "P": (-46.0, -8.0),
    "Q": (-34.0, -14.0),
    "R": (-22.0, -18.0),
    "S": (-10.0, -20.0),
    "T": (10.0, -20.0),
    "U": (22.0, -18.0),
    "V": (34.0, -14.0),
    "W": (46.0, -8.0),
    "X": (58.0, -2.0),
    "Y": (70.0, 5.0),
    "Z": (0.0, -25.0),
}


def _guess_serial_ports() -> List[str]:
    """
    Return a list of candidate serial ports for macOS + Raspberry Pi/Linux.
    """
    patterns = [
        # macOS
        "/dev/cu.usbmodem*",
        "/dev/cu.usbserial*",
        "/dev/tty.usbmodem*",
        "/dev/tty.usbserial*",
        # Raspberry Pi / Linux
        "/dev/ttyACM*",
        "/dev/ttyUSB*",
    ]
    ports: List[str] = []
    for pat in patterns:
        ports.extend(sorted(glob.glob(pat)))
    # De-dup while preserving order
    seen = set()
    out = []
    for p in ports:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


class OuijaHardware:
    """
    GRBL-backed XY motion controller for a physical "ouija-style" board.
    """

    def __init__(
        self,
        port: Optional[str] = DEFAULT_PORT,
        baud: int = DEFAULT_BAUD,
        timeout: float = DEFAULT_TIMEOUT,
        map_override_path: Optional[str] = None,
        debug_serial: bool = False,
        auto_unlock_and_set_modes: bool = True,
        manual_zero_on_connect: bool = True,
        persist_wcs_file: Optional[str] = None,
    ):
        """
        Args:
          port: serial port. If None, we auto-detect.
          auto_unlock_and_set_modes: send $X and modal setup (G21/G90/G94/G17).
          manual_zero_on_connect: prompt user (or print prompt) to place planchette at REST then G92 X0 Y0.
          persist_wcs_file: optional JSON file to store offsets if you later add a workflow; not required.
        """
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.debug_serial = debug_serial
        self.auto_unlock_and_set_modes = auto_unlock_and_set_modes
        self.manual_zero_on_connect = manual_zero_on_connect

        self.persist_wcs_file = persist_wcs_file or str(Path(__file__).resolve().parent / "ouija_wcs_state.json")

        self.arduino: Optional[serial.Serial] = None

        # Create map first
        self.map: Dict[str, Tuple[float, float]] = dict(MAP)

        # Then attempt override
        try:
            self._load_map_override(map_override_path)
        except Exception as e:
            print(f"[WARN] Map override failed: {e}")

    # -----------------------------------------------------
    # MAP OVERRIDE
    # -----------------------------------------------------
    def _load_map_override(self, map_override_path: Optional[str]):
        """
        Override map coordinates from JSON:
          { "A": [x, y], "YES": [x, y], " ": [0,0], ... }
        """
        path = map_override_path or os.getenv("OUJIA_MAP_OVERRIDE_PATH")
        if not path:
            path = str(Path(__file__).resolve().parent / "ouija_map_override.json")

        p = Path(path)
        if not p.exists():
            return

        raw = json.loads(p.read_text(encoding="utf-8"))
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

        # Ensure rest exists
        if " " not in self.map:
            self.map[" "] = (0.0, 0.0)

    # -----------------------------------------------------
    # SERIAL / GRBL
    # -----------------------------------------------------
    def _pick_port(self) -> str:
        if self.port:
            return self.port

        env_port = os.getenv("OUJIA_SERIAL_PORT")
        if env_port:
            return env_port

        candidates = _guess_serial_ports()
        if not candidates:
            raise RuntimeError(
                "No serial ports found. Set --port, or set OUJIA_SERIAL_PORT, "
                "or plug in the Arduino and check /dev/ttyACM* (Pi) or /dev/cu.usbmodem* (Mac)."
            )
        return candidates[0]

    def connect(self):
        if self.arduino and self.arduino.is_open:
            return

        self.port = self._pick_port()
        self.arduino = serial.Serial(self.port, self.baud, timeout=self.timeout)

        # Give Arduino time to reset on open
        time.sleep(2.0)

        # Clear any buffered startup text
        try:
            self.arduino.reset_input_buffer()
        except Exception:
            pass

        if self.auto_unlock_and_set_modes:
            self._initialize_grbl_modes()

        if self.manual_zero_on_connect:
            # IMPORTANT: manual zero makes rest + map stable after restart.
            self._manual_zero_prompt_and_set()

    def _initialize_grbl_modes(self):
        """
        Force a known GRBL "modal" state so Mac/Pi behave the same.
        """
        # Wake up (blank line)
        self.raw("")
        # Unlock (in case of alarm lock)
        self.raw("$X")
        # Modal sanity:
        self.raw("G21")  # millimeters
        self.raw("G90")  # absolute positioning
        self.raw("G94")  # feed rate units/min
        self.raw("G17")  # XY plane

    def _manual_zero_prompt_and_set(self):
        """
        Without homing switches, we need a repeatable reference.
        You physically place the planchette at the REST point, then we set that as (0,0).
        """
        print("\n[OUJIA] Place the planchette/pointer at your physical REST mark (center).")
        print("[OUJIA] Then press ENTER to set that position as X0 Y0.\n")
        try:
            input()
        except EOFError:
            # Non-interactive environment; still allow calling set_zero_here() manually.
            print("[OUJIA] (No stdin available) Skipping manual zero prompt. Call hw.set_zero_here() after positioning.")
            return

        self.set_zero_here()

    def set_zero_here(self):
        """
        Set the *current physical position* as work zero (0,0).
        This is what stabilizes the map across restarts without homing switches.
        """
        # Define current position as (0,0)
        self.raw("G92 X0 Y0")
        # Optional small pause
        time.sleep(0.05)
        print("[OUJIA] Zero set: current position is now X0 Y0")

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

        # Wait for 'ok' (or error/alarm) with timeout
        t0 = time.time()
        last_line = ""
        while True:
            line = self.arduino.readline().decode("utf-8", errors="ignore").strip()
            if line:
                last_line = line
                if self.debug_serial:
                    print(f"[SERIAL<-] {line}")

            low = line.lower()
            if "ok" in low:
                return
            if "error" in low or "alarm" in low:
                raise RuntimeError(f"GRBL responded with: {line} for command: {command}")

            if time.time() - t0 > 5.0:
                raise TimeoutError(f"No 'ok' received for command: {command}. Last line: {last_line}")

    def raw(self, command: str):
        """Send raw gcode/serial command (expects GRBL to respond with ok)."""
        self._send_command(command)

    # -----------------------------------------------------
    # MOTION
    # -----------------------------------------------------
    def move_xy(self, x: float, y: float, speed: int = 400, dwell: float = 0.4):
        """
        Move to X/Y in mm using linear move.
        """
        self._send_command(f"G1 X{x:.3f} Y{y:.3f} F{int(speed)}")
        time.sleep(dwell)

    def move_to(self, token: str, speed: int = 400, dwell: float = 0.6):
        token = token.upper()
        if token not in self.map:
            raise ValueError(f"Unknown token '{token}'. Not in MAP.")
        x, y = self.map[token]
        self.move_xy(x, y, speed=speed, dwell=dwell)

    def rest(self, speed: int = 500):
        self.move_to(" ", speed=speed, dwell=0.3)

    def spell_text(self, text: str, speed: int = 400):
        text = text.upper()
        for ch in text:
            if ch == " ":
                self.move_to(" ", speed=speed, dwell=0.25)
            elif ch in self.map:
                self.move_to(ch, speed=speed, dwell=0.6)
            else:
                continue


if __name__ == "__main__":
    # Manual test
    hw = OuijaHardware(debug_serial=False, manual_zero_on_connect=True)
    hw.connect()
    print(f"Connected on {hw.port} @ {hw.baud}")
    print("Type A..Z, YES, NO, GOODBYE, rest, or q to quit.")
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
            if s.lower() == "zero":
                hw.set_zero_here()
                continue
            token = s.upper()
            if token in hw.map:
                hw.move_to(token)
            else:
                print("Not in map. (Tip: type 'zero' to set current as 0,0)")
    finally:
        hw.close()
        print("Closed.")