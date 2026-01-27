# motion-llm-board project:

LLM-powered "ouija" board

This project connects speech -> language models -> physical motion.
A user asks a question out loud, an LLM decides an answer, and a microcontroller moves servos on a physical board to indicate that response.

## What This Project Does
1. User asks a question (via microphone)
2. Speech-to-text converts audio into text
3. LLM reasoning layer decides an output:
   - YES
   - NO
   - MAYBE
   - Spelling mode
4. Host Python script sends the result over serial 
5. Microcontroller (Arduino) moves servos to the correct position on the board

## Project Structure
motion-llm-board/
│
├── scripts/        # Host-side Python
│   ├── LLM inference
│   ├── Serial communication
│   └── Whisper integration
│
├── esp32/          # Microcontroller firmware
│   ├── Servo control
│   └── Serial command parsing
│
├── data/           # Datasets, prompts, test inputs
│
└── README.md

## Speech-to-Text Dependency
This project uses 'realtime-whisper' for live transcription.

Clone separately:
https://github.com/davabase/whisper_real_time

Run in the 'whisperenv' conda environment
