import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openrouter import status


class StatusTests(unittest.TestCase):
    def test_publish_status_replaces_complete_json(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "ouija_status.json"
            with patch.object(status, "STATUS_FILE", destination):
                status.publish_status("LISTENING", heard="", board="READY")
            payload = json.loads(destination.read_text())
            self.assertEqual(payload["status"], "LISTENING")
            self.assertEqual(payload["board"], "READY")
            self.assertIn("updated_at", payload)
