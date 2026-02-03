# Ouija Board on Raspberry Pi 4

**Speech -> LLM -> Physical motion**

A voice-controlled, LLM-driven "ouija-style" board running on a Raspberry Pi 4, combining local speech-to-text with a cloud-based large language model to drive physical motion.

## Overview
This project connects real-time speech iinput to a physical system using a hybrid edge-and-cloud AI pipeline.

Speech is transcribed locally on the Raspberry Pi using **whisper.cpp**.
The resulting text is then classified by a large language model (LLM) to determine how the board should respond.
That decision is translated into physical movement via serial-controlled motors.

The LLM is an active part of the system's decision-making pipeline.

## What This System Does
1. User presses **ENTER** and speaks a question aloud
2. Audio is captured from a **USB microphone**
3. **whisper.cpp** performs local speech-to-text transcription
4. The transcribed question is sent to a **large language model (LLM)
5. The LLM reasoning layer decides an output
   - YES / NO / MAYBE
   - ONE WORD
6. The Raspberry Pi translates the LLM's decision into serial commands 
7. An Arduino drives motors that move a physical pointer on the board

---
## System Architecture
```
┌────────────┐
│    User    │
└─────┬──────┘
      │  speaks
      ▼
┌────────────┐
│ Microphone │
│  (USB)     │
└─────┬──────┘
      │  audio stream
      ▼
┌──────────────────────┐
│   Raspberry Pi 4     │
│  (System Controller)│
└─────┬────────────────┘
      │
      ▼
┌──────────────────────┐
│     whisper.cpp      │
│  Local Speech-to-Text│
└─────┬────────────────┘
      │  transcribed text
      ▼
┌──────────────────────────────┐
│ Algorithmic Routing Layer    │
│ (Python orchestration logic) │
└─────┬────────────────────────┘
      │  structured prompt
      ▼
┌──────────────────────────────┐
│ OpenRouter API               │
│ Large Language Model (LLM)   │
│ Question Type Classification│
└─────┬────────────────────────┘
      │  response mode
      ▼
┌──────────────────────────────┐
│ Decision Layer (Host Python) │
│ • Enforces output constraints│
│ • Selects final response     │
│ • Produces control token     │
└─────┬────────────────────────┘
      │  serial command
      ▼
┌──────────────────────────────┐
│ Serial Communication         │
│ (USB / pyserial)             │
└─────┬────────────────────────┘
      │
      ▼
┌──────────────────────────────┐
│ Arduino / ESP32              │
│ GRBL Motor Control Logic     │
└─────┬────────────────────────┘
      │  motor signals
      ▼
┌──────────────────────────────┐
│ Physical Board               │
│ Motors / Servos              │
│ Visual Response Display      │
└──────────────────────────────┘

```
## Project Structure
```
motion-llm-board/
│
├── openrouter/                # Stable Raspberry Pi implementation
│   │
│   ├── pi_runner.py           # Main entry point (Pi runtime)
│   ├── pi_whispercpp_v4.py    # Local STT + VAD (whisper.cpp)
│   ├── ouija_hardware.py      # Serial → motor control interface
│   │
│   └── __init__.py
│
├── experimental/              # Experimental / research code (not maintained)
│   │
│   ├── tinker/                # Tinker LLM inference + server experiments
│   ├── training/              # Datasets + fine-tuning scripts
│   └── prototypes/            # Early runner versions and throwaway tests
│
├── data/                      # Prompts, logs, test inputs
│
├── requirements.txt           # Python dependencies (Pi)
├── README.md                  # Project overview + architecture
├── .gitignore

```
**Important**
- `openrouter/` is the recommended and maintained version
- `experimental/` is kept for transparency and learning purposes only

---

## Requirements
**Hardware**
- Raspberry Pi 4
- USB microphone
- Arduino (Uno/Nano/compatible)
- Motors or servos connected to Arduino
- USB cable
- Physical board

**Software**
- Raspberry Pi OS (64-bit)
- Python 3.10
- whisper.cpp
- ALSA (arecord)
- Openrouter LLM

## System Dependencies (APT)
Update system packages first:
```bash 
sudo apt update && sudo apt upgrade -y
```
Install required build + audiio tools:
```bash
sudo apt install -y \
  git wget curl \
  build-essential cmake pkg-config \
  alsa-utils ffmpeg \
  libasound2-dev
```
Install Miniconda (ARM64)
Download Miniconda for **Linux aarch64**:
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash Miniconda3-latest-Linux-aarch64.sh
```
Activate conda:
```bash
source ~/.bashrc
conda --version
```

## Python Setup
1. Create a virtual environment
```bash
conda create -n ouija-board python=3.10 -y
conda activate ouija-board
```
2. Install Requirements
Install project dependencies
```bash
pip install -r requirements.txt
```
If you get audio-related build errors (common on Pi), install these and retry:
```bash
sudo apt install -y python3-dev portaudio19-dev
```

## Set OpenRouter API Key (Required for LLM Classification)
This project uses OpenRouter for the LLM classification layer.
```bash
export OPENROUTER_API_KEY="YOUR_KEY"
```

## whisper.cpp Setup (Local Speech-to-Text)
This project uses `whisper.cpp` for local transcription on the Pi.
You must clone and set up the Whisper real-time repository separately.

1. Clone the Whisper Repository:
From home:
```bash
cd ~
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
```
Build (recommended):
```bash
make -j2
```

2. Download a Whisper Model
From the whisper.cpp folder:
```bash
cd ~/whisper.cpp/models
bash ./download-ggml-model.sh tiny.en
```
Confirm:
```bash
ls -lh ggml-tiny.en.bin
```

## Microphone Setup (ALSA)
List recording devices:
```bash
arecord -l
```
You'll see something like:
```arduino
card 3: USB Audio [USB Audio], device 0: USB Audio 
```
This maps to:
```makefile
plughw:3,0
```
Set it in `openrouter/pi_whispercpp_v4.py`:
```python
USB_MIC_ALSA = "plughw:3,0"
```

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

8. Example GRBL Command (Test Motors)
Send this in the Serial Monitor to test motion:
```gcode
G1 X-10 Y-10 F200
```
If the motors move, GRBL is working correctly.

## Running the Project
From the repo:
```bash
cd ~/motion-llm-board
conda activate ouija-board
python openrouter.pi_runner

## Experimental Folder (Not Required)
The `experimental/` directory contains:
- Tinker inference code
- Training scripts
- Early prototypes and trials

These are not needed to run the project and may require additional setup.
