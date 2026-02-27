#!/usr/bin/env python3
"""
calibrate_letters.py

Interactive calibration tool for testing Ouija letter positions WITHOUT asking questions.

✅ Key behaviors (for drift-after-restart setups without homing switches):
- On connect, it forces GRBL modal state (mm/absolute) via OuijaHardware.connect()
- It prompts you to physically place the planchette at REST, then sets X0 Y0 (G92)
- REST token " " must be (0,0) in your MAP (handled in the updated ouija_hardware.py)

Usage examples:
  python calibrate_letters.py
  python calibrate_letters.py --port /dev/ttyACM0
  python calibrate_letters.py --scan
"""

import argparse
import sys
import time

from ouija_hardware import OuijaHardware


def print_help():
    print(
        """
Commands:
  A..Z / YES / NO / GOODBYE      move directly to token
  text HELLO                     spell text (no quotes needed)
  "HELLO"                        spell text (quotes optional)
  scan                           auto-run through all tokens
  row1                           run A-M
  row2                           run N-Z
  rest                           go to rest position (" ")
  zero                           set current physical position as X0 Y0 (G92)
  xy X Y                         move to raw XY mm (example: xy -20 -10)
  speed N                        set feedrate (example: speed 400)
  dwell S                        set dwell seconds (example: dwell 0.6)
  help                           show this
  q                              quit
"""
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None, help="Serial port (Pi: /dev/ttyACM0, Mac: /dev/cu.usbmodemXXXX)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--no-manual-zero", action="store_true",
                    help="Skip the manual REST->G92 X0 Y0 prompt on connect.")
    ap.add_argument("--scan", action="store_true", help="Scan all tokens then exit")
    args = ap.parse_args()

    # IMPORTANT:
    # - manual_zero_on_connect=True is what fixes drift AFTER restart (no homing switches)
    hw = OuijaHardware(
        port=args.port,
        baud=args.baud,
        debug_serial=False,
        auto_unlock_and_set_modes=True,
        manual_zero_on_connect=(not args.no_manual_zero),
    )

    speed = 400
    dwell = 0.6

    hw.connect()
    print(f"Connected on {hw.port} @ {hw.baud}")

    # After connect (and manual zero), resting is now consistent.
    try:
        hw.rest(speed=500)
    except Exception:
        pass

    tokens_row1 = list("ABCDEFGHIJKLM")
    tokens_row2 = list("NOPQRSTUVWXYZ")
    control_tokens = ["YES", "NO", "GOODBYE", " "]

    def do_scan():
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

            if low == "zero":
                print("Place planchette at your physical REST reference, then press ENTER.")
                input()
                hw.set_zero_here()
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
                    print("Usage: dwell 0.6")
                continue

            if low.startswith("xy "):
                try:
                    _, xs, ys = cmd.split()
                    x = float(xs)
                    y = float(ys)
                    hw.move_xy(x, y, speed=speed, dwell=dwell)
                except Exception:
                    print("Usage: xy -20 -10")
                continue

            # Allow: text HELLO WORLD
            if low.startswith("text "):
                text = cmd[5:].strip().strip('"')
                if not text:
                    print('Usage: text HELLO')
                    continue
                print(f'Spelling "{text}"')
                hw.spell_text(text, speed=speed)
                hw.rest(speed=500)
                continue

            # Otherwise treat input as token or raw spelling
            token = cmd.strip().strip('"').upper()

            # If it's multiple letters and not a known token, treat as spell
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