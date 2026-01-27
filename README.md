# Spirit Board:

A physical, voice-controlled "ouija-style" board powered by a large language model (LLM). 

This project connects speech -> language models -> physical motion.
A user asks a question out loud, an LLM decides an answer, and a microcontroller moves servos on a physical board to indicate that response.

## What This Project Does
1. User presses ENTER and speaks a question
2. Whisper performs real-time speech-to-text
3. The question is sent to an LLM (OpenRouter API)
4. LLM reasoning layer decides an output
   - YES
   - NO
   - MAYBE
   - ONE WORD
5. Host Python script sends the result over serial 
6. Microcontroller (Arduino) moves servos to the correct position on the board

---

## Project Structure
```
motion-llm-board/
│
├── openrouter/           # STABLE VERSION
│   ├── runner.py        # Main entry point
│   ├── ouija_hardware.py
│   └── ouija_mac.py
│
├── experimental/        E# Experiments (not maintained)
│   ├── tinker/          # Tinker inference + server code
│   ├── training/        # Dataset + training scripts
│   └── prototypes/      # Early runner versions
│
├── data/                # Prompts, logs, test inputs
├── requirements.txt
├── README.md
└── .gitignore
```
**Important**
- openrouter/ is the recommended and maintained version
- experimental/ is kept for transparency and learning purposes only

---

## Requirements
**Hardware**
- Arduino (Uno/Nano/compatible)
- Motors or servos connected to Arduino
- USB cable

**Software**
- macOS (Apple Silicon supported)
- Python 3.10
- Arduino IDE (ARM64 on Apple Silicon)
- Homebrew

## Python Setup
1. Create a virtual environment
```bash
conda create -n spirit-board python=3.10 -y
conda activate spirit-board
```
2. Install dependencies
```bash
pip install -r requirements.txt
```

## Whisper Setup (Required for Speech-to-Text)
This project relies on local Whisper transcription
You must clone and set up the Whisper real-time repository separately.

1. Clone the Whisper Repository:
```bash
cd ~
git clone https://github.com/davabase/whisper_real_time.git realtime-whisper
```

2. Ensure You Are in the Project Environment
Activate the same environment you use to run this project:
```bash
conda activate spirit-board
```

3. Install PyTorch
```bash
conda install pytorch -c pytorch -y
```

4. Install Whisper
```bash
pip install -U openai-whisper
pip install git+https://github.com/openai/whisper.git
pip install --upgrade --no-deps --force-reinstall git+https://github.com/openai/whisper.git
```

5. Install Homebrew (macOS only)
If Homebrew is not installed:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Add Homebrew to PATH
Apple Silicon:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Intel Mac:
```bash
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/usr/local/bin/brew shellenv)"
```

Verify
```bash
uname -m
brew --version
```

6. Install System Audio Dependencies
```bash
brew install ffmpeg portaudio
```

7. Install PyAudio
Make sure your project environment is active:
```bash
conda activate spirit-board
pip install pyaudio
```

If installation fails:
```bash
export LDFLAGS="-L$(brew --prefix portaudio)/lib"
export CPPFLAGS="-I$(brew --prefix portaudio)/include"
pip install --no-binary :all: pyaudio
```

8. Install Whisper Real-Time Dependencies
```bash
cd ~/realtime-whisper
pip install -r requirements.txt
```

9. Test Real-Time Transcription
```bash
python transcribe_demo.py
```
For faster transcription:
```bash
python transcribe_demo.py --model base --record_timeout 1 --phrase_timeout 1.2 --energy_threshold 1000
```
If transcription works here, Whisper is correctly installed.

**Microphone Permissions (macOS)**
Go to:
**System Settings -> Privacy & Security -> Microphone**
Restart Terminal after enabling permissions

## OpenRouter API Setup
Create an environment variable:
```bash 
export OPENROUTER_API_KEY="your_api_key_here"
```

## Running the Project (OpenRouter Version)
From the repo root:
```bash
python -m openrouter.runner
```
You should see:
```pgsql
[READY] Press ENTER to listen (or 'q' to quit)
```
Speak a question and see the response. 

## Arduino GRBL Setup (28BYJ-48 Servo)
This project uses a modified GRBL firmware to control servo/stepper motors via Arduino.

1. Download the GRBL Repository
- Go to: 
https://github.com/ruizivo/GRBL-28byj-48-Servo
- Click **Code -> Download ZIP**
- Unzip the downloaded folder

2. Install GRBL as an Arduino Library
- Locate your "Arduino" folder
- Create new folder inside named "libraries"
- Copy the entire grbl folder from the unzipped repository into libraries

3. Locate the Upload Sketch
Inside the GRBL folder, navigate to:
```
grbl/
└── examples/
    └── grblUpload/
        └── grblUpload.ino
```
This is the sketch you will upload to the Arduino

4. Open and Upload the Sketch
- Open Arduino IDE
- Open the sketch:
```bash
File -> Open -> libraries/grbl/examples/grblUpload/grblUpload.ino
```
- Select your board:
```scss
Tools -> Board -> (your Arduino model)
```
- Select the correct port:
```bash
Tools -> Port -> /dev/cu.usbmodemXXXX
```
- Click Upload

5. Required Compilation Fix (IMPORTANT)
If the upload fails with an error related to stepper.c file:
- Open the file
```bash
grbl/stepper.c
```
- Find this line:
```c
dir_outbits
```
- Change it to:
```c
step_outbits
```
- Save the file
- Upload the sketch again
This fix is required for this GRBL fork.

6. Verify Arduino Connection (Serial Monitor)
- Open:
```arduino
Tools -> Serial Monitor
```
- Set:
**Baud rate:** 115200
**Line ending:** New Line
- You should see GRBL startup text or responses to commands

7. Python Serial Setup
Make sure your project's Python environment is active:
```bash
conda activate spirit-board
```
Install PySerial:
```bash
pip install pyserial
```
Verify the serial port in your Python code matches the Arduino port

8. Debugging Serial Issues
If commands return errors or nothing responds:
- Close the Serial Monitor
- Unplug the USB cable
- Plug the USB cable back in
- Reopen Serial Monitor
- Confirm settings again:
	Baud rate: 115200
	Line ending: New Line
This resets the serial connection.

9. Example GRBL Command (Test Motors)
Send this in the Serial Monitor to test motion:
```gcode
G1 X-10 Y-10 F200
```
If the motors move, GRBL is working correctly.

## Exeperimental Folder (Not Required)
The experimental/ directory contains:
- Tinker inference code
- Training scripts
- Early prototpyes and trials
These are not needed to run the project and may require additional setup.
