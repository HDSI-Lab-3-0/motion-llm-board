import serial, time

ANGLE_MAP = {"YES": 20, "NO": 50, "MAYBE": 80}

def send_label(port, label, baud=9600):
    angle = ANGLE_MAP[label]
    with serial.Serial(port, baud, timeout=1) as ser:
        time.sleep(2)
        ser.write(f"{angle}\n".encode())
        ser.flush()
        print(f"Sent {label} -> {angle}")

# Example:
# send_label("/dev/cu.usbmodem1101", "YES")

