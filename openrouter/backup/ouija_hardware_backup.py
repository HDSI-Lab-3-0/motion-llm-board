import time
import serial

# --- CONFIGURATION ---
DEFAULT_PORT = "/dev/cu.usbmodem1101"
DEFAULT_BAUD = 115200

# --- MAP (X Range: 0 to -41 | Y: 0 to -38) ---
MAP = {
    # Top Row (Upper arc)
    "A": (-5, 0),   "B": (-34, -11), "C": (-30, -9),   "D": (-26, -7.5),
    "E": (-22, -6.5), "F": (-19, -6),  "G": (-16, -6),  "H": (-25, -6.5),
    "I": (0, -7.5), "J": (-6, -9),   "K": (-3, -11),  "L": (-1, -14),
    "M": (0, -14),

    # Bottom Row (Lower arc)
    "N": (-36, -24), "O": (-32, -21), "P": (-28, -18), "Q": (-24, -16),
    "R": (-21, -15), "S": (0, -15),   "T": (-15, -15), "U": (-12, -16),
    "V": (-9, -18),  "W": (-6, -21),  "X": (-3, -24),  "Y": (-8, -24),
    "Z": (0, -24),

    # Control elements
    "YES": (-36, -4),
    "NO": (-5, -4),
    # If you don't have a dedicated MAYBE spot, we will spell "MAYBE" instead
    # "MAYBE": (-20, -4),

    "GOODBYE": (-20, -36),
    " ": (-15, -10),  # Rest position (center)
}

class OuijaHardware:
    def __init__(self, port: str = DEFAULT_PORT, baud: int = DEFAULT_BAUD, timeout: float = 1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.arduino = None

    def connect(self):
        if self.arduino and self.arduino.is_open:
            return
        self.arduino = serial.Serial(self.port, self.baud, timeout=self.timeout)
        time.sleep(2)  # allow Arduino reset

    def close(self):
        if self.arduino:
            try:
                self.arduino.close()
            except:
                pass

    def _send_command(self, command: str):
        if not self.arduino or not self.arduino.is_open:
            raise RuntimeError("Hardware not connected. Call connect() first.")

        self.arduino.write(f"{command}\n".encode())

        # Wait for 'ok' with timeout (prevents hanging forever)
        t0 = time.time()
        while True:
            line = self.arduino.readline().decode("utf-8", errors="ignore").strip()
            if "ok" in line.lower():
                return
            if time.time() - t0 > 5.0:
                raise TimeoutError(f"No 'ok' received for command: {command}")

    def move_to(self, token: str, speed: int = 400, dwell: float = 1.2):
        token = token.upper()
        if token not in MAP:
            raise ValueError(f"Unknown token '{token}'. Not in MAP.")
        x, y = MAP[token]
        self._send_command(f"G1 X{x} Y{y} F{speed}")
        time.sleep(dwell)

    def rest(self, speed: int = 500):
        self.move_to(" ", speed=speed, dwell=0.5)

    def spell_text(self, text: str, speed: int = 400):
        text = text.upper()
        for ch in text:
            if ch == " ":
                self.move_to(" ", speed=speed, dwell=0.6)
            elif ch in MAP:
                self.move_to(ch, speed=speed, dwell=1.2)
            else:
                # ignore punctuation/unsupported symbols
                continue
