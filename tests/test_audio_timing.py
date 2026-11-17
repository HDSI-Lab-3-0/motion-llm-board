import io
import struct
import unittest
import wave
from unittest.mock import Mock, patch

from openrouter import pi_whispercpp_v4 as audio


class AudioTimingTests(unittest.TestCase):
    def capture(self, levels):
        block = lambda level: struct.pack('<h', level) * 4000
        proc = Mock(stdout=io.BytesIO(b''.join(block(n) for n in levels)))
        proc.poll.return_value = None
        return proc

    def test_calibration_then_ready_and_continuous_question(self):
        proc = self.capture([10, 800, 900, 0, 0])
        messages = []

        def transcribe(path):
            self.assertTrue(proc.stdout.closed)
            with wave.open(path) as wav:
                self.assertEqual(wav.getnframes(), 16000)
            return ' hello  there '

        with patch.object(audio.subprocess, 'Popen', return_value=proc) as launch, \
                patch.object(audio, 'transcribe_wav', side_effect=transcribe) as decode, \
                patch('builtins.print', side_effect=lambda msg, **kw: messages.append(msg)):
            result = audio.listen_question_near_realtime(
                chunk_s=.25, calibrate_chunks=1, silence_chunks_to_stop=2)
        self.assertEqual(result, 'hello there')
        launch.assert_called_once()
        decode.assert_called_once()
        self.assertIn('Preparing', messages[0])
        self.assertIn('Listening', messages[1])
        self.assertIn('Speech detected', messages[2])
        self.assertIn('Recording complete', messages[3])
        self.assertIn('Transcription complete', messages[-1])
        proc.terminate.assert_called_once()

    def test_failed_capture_never_announces_ready(self):
        proc = self.capture([])
        with patch.object(audio.subprocess, 'Popen', return_value=proc), \
                patch('builtins.print') as log, \
                patch.object(audio, 'transcribe_wav') as decode:
            with self.assertRaisesRegex(RuntimeError, 'Microphone stopped'):
                audio.listen_question_near_realtime(chunk_s=.25)
        self.assertFalse(any('Listening' in str(c) for c in log.call_args_list))
        decode.assert_not_called()
        self.assertTrue(proc.stdout.closed)

    def test_silence_does_not_transcribe(self):
        proc = self.capture([0, 0, 0])
        with patch.object(audio.subprocess, 'Popen', return_value=proc), \
                patch('builtins.print'), patch.object(audio, 'transcribe_wav') as decode:
            self.assertEqual(audio.listen_question_near_realtime(
                chunk_s=.25, max_seconds=.5, calibrate_chunks=1), '')
        decode.assert_not_called()
