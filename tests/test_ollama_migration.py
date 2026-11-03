import ast
import hashlib
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

import requests
from openrouter import runner_spooky4 as runner

ROOT = Path(__file__).resolve().parents[1]


class MigrationTests(unittest.TestCase):
    def test_native_payload_and_response(self):
        reply = Mock(status_code=200)
        reply.json.return_value = {'response': ' YES '}
        with patch.object(runner.requests, 'post', return_value=reply) as post:
            self.assertEqual(runner.ollama_completion('question', 4, 0.1), 'YES')
        args, kwargs = post.call_args
        self.assertEqual(args, (runner.OLLAMA_URL,))
        self.assertEqual(kwargs['json'], {
            'model': runner.MODEL_NAME, 'prompt': 'question', 'stream': False,
            'options': {'num_predict': 4, 'temperature': 0.1, 'num_ctx': runner.OLLAMA_CONTEXT}})
        self.assertNotIn('headers', kwargs)
        self.assertEqual(kwargs['timeout'], runner.OLLAMA_TIMEOUT)

    def test_request_failures(self):
        for error in (requests.ConnectionError('offline'), requests.Timeout('slow')):
            with self.subTest(error=error), patch.object(runner.requests, 'post', side_effect=error):
                self.assertEqual(runner.ollama_completion('test'), '')
        for status, body in ((404, {}), (500, {}), (200, []), (200, {}), (200, {'response': 42})):
            reply = Mock(status_code=status, text='error')
            reply.json.return_value = body
            with self.subTest(status=status, body=body), patch.object(runner.requests, 'post', return_value=reply):
                self.assertEqual(runner.ollama_completion('test'), '')
        reply = Mock(status_code=200)
        reply.json.side_effect = ValueError('bad JSON')
        with patch.object(runner.requests, 'post', return_value=reply):
            self.assertEqual(runner.ollama_completion('test'), '')

    def test_preserved_overrides_and_routing(self):
        with patch.object(runner, 'ollama_completion') as model:
            self.assertEqual(runner.classify_mode('What should I eat?'), 'ONE_WORD')
            self.assertEqual(runner.classify_mode('Will I succeed?'), 'YES_NO')
            self.assertEqual(runner.answer_yes_no('Is anyone here?'), 'YES')
            self.assertEqual(runner.answer_yes_no('Are we alone?'), 'NO')
            self.assertEqual(runner.pick_one_word('How is the weather?'), 'GOOD')
            model.assert_not_called()
        with patch.object(runner, 'ollama_completion', return_value='YES_NO'):
            self.assertEqual(runner.classify_mode('xyzzy'), 'YES_NO')

    def test_constrained_answers(self):
        for raw in ('MAYBE', 'YES NO', '', 'ignore the rules'):
            with patch.object(runner, 'ollama_completion', return_value=raw):
                self.assertIn(runner.answer_yes_no('Will I succeed?'), ('YES', 'NO'))
                self.assertIn(runner.pick_one_word('What should I eat?'), runner.WORD_BANKS['food'])
        with patch.object(runner, 'ollama_completion', return_value='SOUP'):
            self.assertEqual(runner.pick_one_word('What should I eat?'), 'SOUP')
        with patch.object(runner, 'ollama_completion', return_value='NO'):
            self.assertEqual(runner.answer_yes_no('Will I succeed?'), 'NO')

    def test_serial_commands(self):
        bridge = runner.OuijaArduinoBridge(port='FAKE')
        bridge.ser = Mock()
        bridge.ser.readline.return_value = b'OK SPELL_DONE\n'
        bridge.spell_text('yes!')
        bridge.ser.write.assert_called_once_with(b'SPELL YES\n')
        bridge.ser.reset_mock()
        bridge.spell_text('NO')
        bridge.ser.write.assert_called_once_with(b'SPELL NO\n')
        bridge.ser.readline.return_value = b'DONE\n'
        bridge.center()
        bridge.ser.write.assert_called_with(b'CENTER\n')

    def test_repeated_answer_centers_and_closes(self):
        board = Mock()
        with patch.object(runner, 'HARDWARE_ENABLED', True), patch.object(runner, 'OuijaArduinoBridge', return_value=board), patch('builtins.input', side_effect=['t', 'Is anyone here?', 't', 'Is anyone here?', 'q']), patch.object(runner.time, 'sleep'):
            runner.main()
        self.assertEqual([c[0] for c in board.method_calls], ['connect', 'spell_text', 'center', 'spell_text', 'close'])

    def test_original_logic_and_hardware_preserved(self):
        original = subprocess.check_output(['git', 'show', 'HEAD:openrouter/runner_spooky4.py'], cwd=ROOT).decode()
        before = ast.parse(original)
        after = ast.parse((ROOT / 'openrouter/runner_spooky4.py').read_text(encoding='utf-8-sig'))
        names = {'find_arduino_port', 'OuijaArduinoBridge', 'sanitize_word', 'classify_mode', 'answer_yes_no', 'pick_one_word'}
        for name in names:
            old = next(n for n in before.body if getattr(n, 'name', '') == name)
            new = next(n for n in after.body if getattr(n, 'name', '') == name)
            for n in ast.walk(old):
                if isinstance(n, ast.Name) and n.id == 'openrouter_completion':
                    n.id = 'ollama_completion'
            self.assertEqual(ast.dump(old), ast.dump(new), name)
        for path in ['hardware/SPELL_numbers.ino', 'openrouter/new_hardware_bridge.py', 'openrouter/wordbanks_spooky3.py']:
            original = subprocess.check_output(['git', 'show', f'HEAD:{path}'], cwd=ROOT)
            current = (ROOT / path).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(hashlib.sha256(original).digest(), hashlib.sha256(current).digest(), path)


if __name__ == '__main__':
    unittest.main()
