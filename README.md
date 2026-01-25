# motion-llm-board project:

Motion "ouija" board project:
- LLM decides an output (YES/NO/Maybe or spelling mode)
- Host Python sends commands over serial
- Arudino moves servos to positions

## Folders
- scripts/ : Python scripts (LLM + serial + whisper integration)
- esp32/   : microcontroller code
- data/    : datasets / test inputs

## Speech-to-Text Dependency
This project uses 'realtime-whisper' for live transcription.

Clone separately:
https://github.com/davabase/whisper_real_rime

Run in the 'whisperenv' conda environment
