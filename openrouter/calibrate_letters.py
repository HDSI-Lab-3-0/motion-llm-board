#!/usr/bin/env python3
"""
calibrate_letters.py

Interactive calibration tool for testing letter positions without asking questions.

Usage examples:
  python calibrate_letters.py
  python calibrate_letters.py --port /dev/cu.usbmodem1101
  python calibrate_letters.py --scan
"""

import argparse
import time

# If this file is in the same folder as your OuijaHardware file,
# adjust the import accordingly.
# Example if your class is in openrouter/ouija_hardware.py:
# from openrouter.ouija_hardware import OuijaHardware, MAP

# If you're literally pasting this in the same file as the class, you can remove the import.
from ouija_hardware import OuijaHardware  # <-- change if needed


def print_help():
    print(
        """
Commands:
  A..Z / YES / NO / GOODBYE      move directly to token
  "text"                        spell text (quotes optional)
  scan                          auto-run through all tokens
  row1                          run A-M in your map order
  row2                          run N-Z in your map order
  rest                          go to rest position (" ")
  xy X Y                        move to raw XY (example: xy -20 -10)
  speed N                       set feedrate (example: speed 400)
  dwell S                       set dwell seconds (example: dwell 1.2)
  help                          show this
  q                             quit
"""
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None, help="Serial port (e.g. /dev/cu.usbmodem1101)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--scan", action="store_true", help="Scan all tokens then exit")
    args = ap.parse_args()

    hw = OuijaHardware(
        port=args.port or "/dev/cu.usbmodem1101",  # default fallback
        baud=args.baud,
    )

    speed = 400
    dwell = 1.2

    hw.connect()
    print(f"Connected on {hw.port} @ {hw.baud}")
    hw.rest(speed=500)

    tokens_row1 = list("ABCDEFGHIJKLM")
    tokens_row2 = list("NOPQRSTUVWXYZ")
    control_tokens = ["YES", "NO", "GOODBYE", " "]

    def do_scan():
        # Only scan tokens that exist in the map
        ordered = [t for t in (tokens_row1 + tokens_row2 + control_tokens) if t in hw.map]
        print("Scanning:", " ".join(ordered))
        for t in ordered:
            print(f"-> {t}")
            hw.move_to(t, speed=speed, dwell=dwell)
        hw.rest(speed=500)

    if args.scan:
        do_scan()
        hw.close()
        return

    print_help()

    try:
        while True:
            cmd = input("calibrate> ").strip()
            if not cmd:
                continue

            low = cmd.lower()

            if low in ("q", "quit", "exit"):
                break

            if low in ("help", "?"):
                print_help()
                continue

            if low == "rest":
                hw.rest(speed=500)
                continue

            if low == "scan":
                do_scan()
                continue

            if low == "row1":
                for t in tokens_row1:
                    if t in hw.map:
                        print(f"-> {t}")
                        hw.move_to(t, speed=speed, dwell=dwell)
                hw.rest(speed=500)
                continue

            if low == "row2":
                for t in tokens_row2:
                    if t in hw.map:
                        print(f"-> {t}")
                        hw.move_to(t, speed=speed, dwell=dwell)
                hw.rest(speed=500)
                continue

            if low.startswith("speed "):
                try:
                    speed = int(cmd.split()[1])
                    print(f"speed set to {speed}")
                except Exception:
                    print("Usage: speed 400")
                continue

            if low.startswith("dwell "):
                try:
                    dwell = float(cmd.split()[1])
                    print(f"dwell set to {dwell}")
                except Exception:
                    print("Usage: dwell 1.2")
                continue

            if low.startswith("xy "):
                try:
                    _, xs, ys = cmd.split()
                    x = float(xs)
                    y = float(ys)
                    hw.move_xy(x, y, speed=speed, dwell=dwell)
                except Exception:
                    print('Usage: xy -20 -10')
                continue

            # If they typed a token like "A" or "YES"
            token = cmd.strip().strip('"').upper()

            # If it's multiple letters, treat as spell
            if len(token) > 1 and token not in hw.map:
                print(f'Spelling "{token}"')
                hw.spell_text(token, speed=speed)
                hw.rest(speed=500)
                continue

            if token in hw.map:
                hw.move_to(token, speed=speed, dwell=dwell)
            else:
                print(f"Unknown token: {token} (not in map)")

    finally:
        try:
            hw.rest(speed=500)
        except Exception:
            pass
        hw.close()
        print("Disconnected.")


if __name__ == "__main__":
    main()

