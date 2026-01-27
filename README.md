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

Clone separately:
https://github.com/davabase/whisper_real_time

Run in the 'whisperenv' conda environment
