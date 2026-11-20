import json
import tempfile
import unittest
import threading
from unittest.mock import Mock
from pathlib import Path
from unittest.mock import patch

from openrouter import status


class StatusTests(unittest.TestCase):
    def test_heartbeat_preserves_phase_source_and_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "status.json"
            updated = threading.Event()
            original = status._publish_status

            def observe(*args, **kwargs):
                original(*args, **kwargs)
                updated.set()

            with patch.object(status, "STATUS_FILE", destination):
                status.publish_status("MOVING", response="ANNA", source="Word bank · Names")
                with patch.object(status, '_publish_status', side_effect=observe):
                    with status.status_heartbeat(interval=0.01):
                        self.assertTrue(updated.wait(1))
                status.publish_progress('Arduino: DONE')
                payload = json.loads(destination.read_text())
                self.assertEqual(payload['status'], 'MOVING')
                self.assertEqual(payload['source'], 'Word bank · Names')
                self.assertEqual(payload['response'], 'ANNA')
                self.assertEqual(payload['detail'], 'Arduino: DONE')

    def test_display_shows_motion_and_source(self):
        from ui import ouijai_display as display
        ui = display.OuijaiDisplay.__new__(display.OuijaiDisplay)
        for name in ('status', 'heard', 'response', 'board', 'detail', 'root'):
            setattr(ui, name, Mock())
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'status.json'
            with patch.object(status, 'STATUS_FILE', destination):
                status.publish_status('MOVING', source='Random choice · DOGS / CATS')
            with patch.object(display, 'STATUS_FILE', destination):
                ui.poll()
        self.assertEqual(ui.status.configure.call_args.kwargs['text'], 'MOVING')
        self.assertIn('Random choice', ui.detail.configure.call_args.kwargs['text'])

    def test_publish_status_replaces_complete_json(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "ouija_status.json"
            with patch.object(status, "STATUS_FILE", destination):
                status.publish_status("LISTENING", heard="", board="READY")
            payload = json.loads(destination.read_text())
            self.assertEqual(payload["status"], "LISTENING")
            self.assertEqual(payload["board"], "READY")
            self.assertIn("updated_at", payload)

    def test_ready_states_drive_led_on(self):
        from openrouter.gpio_status_led import StatusLed
        led = StatusLed.__new__(StatusLed)
        led.pin = 17
        led._gpio = Mock()
        led.set_status("RESPONSE_READY")
        led._gpio.output.assert_called_once_with(led.pin, led._gpio.HIGH)
