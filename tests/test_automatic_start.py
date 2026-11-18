"""AUTOMATIC START: audio rejection, unattended routing, and fault handling."""
import io
import struct
import sys
import unittest
from unittest.mock import Mock, patch

from openrouter import pi_whispercpp_v4 as audio
from openrouter import runner_spooky4 as runner


class AutomaticStartTests(unittest.TestCase):
    def test_rejected_transcripts_and_short_speech(self):
        for text in ("", "...", "[BLANK_AUDIO]", "(inaudible)", "background noise",
                     "hi hi hi hi hi hi"):
            self.assertEqual(audio.validate_transcript(text).status, "BACKGROUND_NOISE")
        for text in ("Hello", "Why?", "Spell Jack", "What is my name?"):
            result = audio.validate_transcript(text)
            self.assertEqual(result.status, "SPEECH")
            self.assertEqual(result.text, text)

    def test_automatic_silence_and_click_do_not_transcribe(self):
        # Fifty calibration frames, quiet, one click, quiet, then capture fault.
        levels = [0] * 60 + [1000] + [0] * 60
        pcm = b"".join(struct.pack("<h", level) * 320 for level in levels)
        proc = Mock(stdout=io.BytesIO(pcm))
        proc.poll.return_value = None
        vad = Mock()
        vad.is_speech.side_effect = lambda data, rate: audio.audioop.rms(data, 2) > 500
        module = Mock()
        module.Vad.return_value = vad
        with patch.dict(sys.modules, {"webrtcvad": module}), \
                patch.object(audio.subprocess, "Popen", return_value=proc), \
                patch.object(audio, "transcribe_wav") as decode:
            with self.assertRaisesRegex(RuntimeError, "Microphone stopped"):
                audio.listen_question_near_realtime(automatic=True)
        decode.assert_not_called()
        self.assertTrue(proc.stdout.closed)

    def test_automatic_valid_speech_preserves_leading_audio(self):
        levels = [0] * 60 + [1000] * 15 + [0] * 50
        pcm = b"".join(struct.pack("<h", level) * 320 for level in levels)
        proc = Mock(stdout=io.BytesIO(pcm))
        proc.poll.return_value = None
        vad = Mock()
        vad.is_speech.side_effect = lambda data, rate: audio.audioop.rms(data, 2) > 500
        module = Mock()
        module.Vad.return_value = vad
        with patch.dict(sys.modules, {"webrtcvad": module}), \
                patch.object(audio.subprocess, "Popen", return_value=proc), \
                patch.object(audio, "transcribe_wav", return_value="Hello"):
            result = audio.listen_question_near_realtime(automatic=True)
        self.assertEqual(result, audio.AudioResult("SPEECH", text="Hello"))
        self.assertTrue(proc.stdout.closed)

    def test_rejected_audio_never_reaches_model_or_hardware(self):
        bridge = Mock(ready=True)
        with patch.object(runner, "check_automatic_dependencies"), \
                patch.object(runner, "HARDWARE_ENABLED", True), \
                patch.object(runner, "OuijaArduinoBridge", return_value=bridge), \
                patch.object(runner.signal, "signal"), \
                patch.object(runner.time, "sleep"), \
                patch.object(runner, "listen_question_near_realtime", side_effect=[
                    audio.AudioResult("BACKGROUND_NOISE"), KeyboardInterrupt]), \
                patch("builtins.input", side_effect=AssertionError("stdin used")), \
                patch.object(runner, "classify_mode") as classify, \
                patch.object(runner, "ollama_completion") as model:
            runner.main(auto_listen=True)
        classify.assert_not_called()
        model.assert_not_called()
        bridge.spell_text.assert_not_called()
        bridge.close.assert_called_once()

    def test_missing_homing_ack_blocks_automatic_start(self):
        bridge = Mock(ready=False)
        with patch.object(runner, "check_automatic_dependencies"), \
                patch.object(runner.signal, "signal"), \
                patch.object(runner, "HARDWARE_ENABLED", True), \
                patch.object(runner, "OuijaArduinoBridge", return_value=bridge):
            with self.assertRaisesRegex(RuntimeError, "READY_AT_CENTER"):
                runner.main(auto_listen=True)
        bridge.close.assert_called_once()

    def test_movement_timeout_not_success(self):
        bridge = runner.OuijaArduinoBridge(port="FAKE")
        bridge.strict_automatic = True
        bridge.ser = Mock()
        with self.assertRaises(TimeoutError):
            bridge.send_command("SPELL HELLO", timeout_s=0)
