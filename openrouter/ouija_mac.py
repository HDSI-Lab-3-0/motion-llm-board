import serial
import time

# --- CONFIGURATION ---
MAC_PORT = '/dev/cu.usbmodem1101'  # Make sure this is correct
BAUD_RATE = 115200

# --- SYMMETRIC AND ARCHED MAP (X Range: 0 to -41 | Y: 0 to -38) ---
MAP = {
    # Top Row (Upper arc) - Y goes from -14 at the edges to -6 in the center
    'A': (-5, 0), 'B': (-34, -11), 'C': (-30, -9),  'D': (-26, -7.5),
    'E': (-22, -6.5), 'F': (-19, -6),  'G': (-16, -6),  'H': (-25, -6.5),
    'I': (0, -7.5),  'J': (-6, -9),   'K': (-3, -11),  'L': (-1, -14),
    'M': (0, -14),

    # Bottom Row (Lower arc) - Y goes from -24 at the edges to -15 in the center
    'N': (-36, -24), 'O': (-32, -21), 'P': (-28, -18), 'Q': (-24, -16),
    'R': (-21, -15), 'S': (0, -15), 'T': (-15, -15), 'U': (-12, -16),
    'V': (-9, -18),  'W': (-6, -21),  'X': (-3, -24),  'Y': (-8, -24),  # Y/Z adjusted to the right
    'Z': (0, -24),

    # Control elements and extras
    'YES': (-36, -4), 
    'NO': (-5, -4),
    'GOODBYE': (-20, -36),  # Bottom center
    ' ': (-15, -10)          # Rest position (center of the board)
}

def send_command(arduino, command):
    arduino.write(f"{command}\n".encode())
    while True:
        line = arduino.readline().decode('utf-8').strip()
        if 'ok' in line:
            break

def spell_text(arduino, text):
    text = text.upper()
    for letter in text:
        if letter in MAP:
            x, y = MAP[letter]
            print(f"Moving to {letter}: X={x}, Y={y}")
            # F400 is a safe speed for short movements
            send_command(arduino, f"G1 X{x} Y{y} F400")
            time.sleep(1.5)  # Pause so the user can read
        elif letter == " ":
            send_command(
                arduino,
                f"G1 X{MAP[' '][0]} Y{MAP[' '][1]} F400"
            )
            time.sleep(1)

# --- EXECUTION ---
try:
    print("Connecting to the Mac...")
    arduino = serial.Serial(MAC_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Safety wait for Arduino reset
    
    # Initial calibration: go home
    # (we assume the magnet is in the top-right corner at startup)
    print("System ready. The origin (0,0) is the Moon (Right).")
    
    while True:
        word = input("\nEnter a word (or 'exit'): ")
        if word.lower() == 'exit':
            break
        
        spell_text(arduino, word)
        
        # When finished, return to the center rest position
        print("Returning to center...")
        send_command(
            arduino,
            f"G1 X{MAP[' '][0]} Y{MAP[' '][1]} F500"
        )

    arduino.close()
    print("Connection closed.")

except Exception as error:
    print(f"Error detected: {error}")
