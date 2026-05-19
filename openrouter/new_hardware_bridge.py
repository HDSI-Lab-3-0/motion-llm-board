import argparse
import re
import sys
import time
from typing import Optional

import serial
from serial.tools import list_ports


BAUD_RATE = 115200
DEFAULT_TIMEOUT = 1.0


def find_arduino_port() -> Optional[str]:
    """
    Auto-detect likely Arduino serial port.
    Works on Mac/Linux/Windows in most cases.
    """
    ports = list(list_ports.comports())

    for port in ports:
        name = port.device
        desc = (port.description or "").lower()

        if (
            "arduino" in desc
            or "usb serial" in desc
            or "usbmodem" in name
            or "usbserial" in name
            or "ch340" in desc
        ):
            return name

    return None


class OuijaBridge:
    def __init__(self, port: Optional[str] = None, baud: int = BAUD_RATE):
        self.port = port or find_arduino_port()

        if not self.port:
            raise RuntimeError(
                "Could not find Arduino port. "
                "Plug in Arduino, then check Arduino IDE > Tools > Port."
            )

        print(f"Connecting to Arduino on {self.port}...")
        self.ser = serial.Serial(self.port, baud, timeout=DEFAULT_TIMEOUT)

        # Arduino usually resets when serial opens.
        # Give it time to boot and auto-home if your sketch does that.
        time.sleep(2)

        self.flush_startup_output()

    def flush_startup_output(self):
        """
        Reads any startup/autohoming messages currently waiting.
        """
        print("Reading startup output...")
        start = time.time()

        while time.time() - start < 3:
            line = self.read_line()
            if line:
                print(f"<< {line}")

    def read_line(self) -> Optional[str]:
        try:
            raw = self.ser.readline()
            if not raw:
                return None
            return raw.decode(errors="ignore").strip()
        except Exception:
            return None

    def send_command(self, command: str, wait_done: bool = True, timeout: float = 120.0) -> list[str]:
        """
        Sends one command to Arduino and collects responses.

        wait_done=True waits until one of:
        - DONE
        - OK SPELL_DONE
        - OK HOMEALL
        - READY_AT_CENTER
        - ERR ...
        """
        command = command.strip()

        if not command:
            return []

        print(f">> {command}")
        self.ser.write((command + "\n").encode())

        responses = []
        start = time.time()

        while time.time() - start < timeout:
            line = self.read_line()

            if not line:
                continue

            print(f"<< {line}")
            responses.append(line)

            if line.startswith("ERR"):
                break

            if not wait_done:
                break

            if (
                line.startswith("DONE")
                or line == "OK SPELL_DONE"
                or line == "OK HOMEALL"
                or line == "READY_AT_CENTER"
                or line.startswith("OK HOMED")
            ):
                # For SPELL, OK SPELL_DONE is the real end.
                # For GOTO, DONE is enough.
                if command.upper().startswith("SPELL") and line != "OK SPELL_DONE":
                    continue
                break

        else:
            print("WARNING: timed out waiting for Arduino response.")

        return responses

    def spell(self, word: str):
        clean = sanitize_word(word)

        if not clean:
            print("No valid word to spell.")
            return

        self.send_command(f"SPELL {clean}", wait_done=True)

    def goto_yes(self):
        self.send_command("YES", wait_done=True)

    def goto_no(self):
        self.send_command("NO", wait_done=True)

    def center(self):
        self.send_command("CENTER", wait_done=True)

    def close(self):
        self.ser.close()


def sanitize_word(text: str) -> str:
    """
    Keeps only letters. Converts to uppercase.
    Examples:
    - "yes!" -> "YES"
    - "hello world" -> "HELLOWORLD"
    """
    letters_only = re.sub(r"[^A-Za-z]", "", text)
    return letters_only.upper()


def interactive_mode(bridge: OuijaBridge):
    print("\nInteractive mode.")
    print("Type a word like HELLO, or a raw command like: SPELL HELLO, YES, NO, WHERE, HOMEALL")
    print("Type EXIT to quit.\n")

    while True:
        user_input = input("ouija> ").strip()

        if not user_input:
            continue

        if user_input.upper() in {"EXIT", "QUIT"}:
            break

        upper = user_input.upper()

        # Raw command passthrough
        if upper.startswith(("SPELL ", "GOTO ", "OFFSET ", "HOME", "WHERE", "SWITCH", "ZERO", "CENTER", "YES", "NO")):
            bridge.send_command(user_input, wait_done=True)
        else:
            bridge.spell(user_input)


def main():
    parser = argparse.ArgumentParser(description="Python bridge for Arduino Ouija motion platform.")
    parser.add_argument("--port", help="Serial port, e.g. /dev/cu.usbmodem1101 or COM3")
    parser.add_argument("--word", help="Word to spell, e.g. HELLO")
    parser.add_argument("--command", help='Raw Arduino command, e.g. "SPELL HELLO" or "WHERE"')
    parser.add_argument("--interactive", action="store_true", help="Run interactive command mode")

    args = parser.parse_args()

    try:
        bridge = OuijaBridge(port=args.port)

        if args.command:
            bridge.send_command(args.command, wait_done=True)

        elif args.word:
            bridge.spell(args.word)

        elif args.interactive:
            interactive_mode(bridge)

        else:
            print("No action provided. Try:")
            print("  python ouija_bridge.py --interactive")
            print("  python ouija_bridge.py --word HELLO")
            print('  python ouija_bridge.py --command "SPELL YES"')

        bridge.close()

    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
