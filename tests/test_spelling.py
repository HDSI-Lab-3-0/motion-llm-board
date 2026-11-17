import unittest
from unittest.mock import Mock, patch
from openrouter import runner_spooky4 as runner
from openrouter.spelling import extract_spell_target


class SpellingRegressionTests(unittest.TestCase):
    def test_repeated_letters_keep_exact_command(self):
        for word in ('GOOD', 'BOOKKEEPER', 'AAA'):
            with self.subTest(word=word):
                self.assertEqual(extract_spell_target(f'Spell {word}'), word)
                bridge = runner.OuijaArduinoBridge(port='FAKE')
                bridge.ser = Mock()
                bridge.ser.readline.side_effect = [
                    b'REPEAT LETTER O\n', b'DONE -7 3\n', b'DONE -3 32\n',
                    b'OK SPELL_DONE\n']
                bridge.spell_text(word)
                bridge.ser.write.assert_called_once_with(f'SPELL {word}\n'.encode())
                self.assertEqual(bridge.ser.readline.call_count, 4)

    def test_diagnostic_bridge_waits_for_whole_word(self):
        from openrouter.new_hardware_bridge import OuijaBridge
        bridge = OuijaBridge.__new__(OuijaBridge)
        bridge.ser = Mock()
        bridge.ser.readline.side_effect = [
            b'REPEAT LETTER O\n', b'DONE -7 3\n', b'DONE -3 32\n', b'OK SPELL_DONE\n']
        bridge.spell('GOOD')
        self.assertEqual(bridge.ser.readline.call_count, 4)
        bridge.ser.write.assert_called_once_with(b'SPELL GOOD\n')

    def test_polite_requests(self):
        for text in ('Hello? Can you spell Apple, please? Hey, thanks.', 'Spell apple.', 'Could you please spell the word apple?', 'Would you spell "apple", please?'):
            with self.subTest(text=text):
                self.assertEqual(extract_spell_target(text), 'APPLE')

    def test_non_commands(self):
        for text in ("Don't spell apple.", 'Can you not spell apple?', 'Is "spell apple" a command?', 'Can you hear me?', 'Spell apple. Spell pear.', 'Spell ' + 'a' * 20):
            with self.subTest(text=text):
                self.assertIsNone(extract_spell_target(text))

    def test_real_runner_sends_exact_word(self):
        board = Mock()
        text = 'Hello? Can you spell Apple, please? Hey, thanks.'
        with patch.object(runner, 'HARDWARE_ENABLED', True), patch.object(runner, 'OuijaArduinoBridge', return_value=board), patch('builtins.input', side_effect=['t', text, 'q']), patch.object(runner.time, 'sleep'), patch.object(runner, 'ollama_completion') as model:
            runner.main()
        board.spell_text.assert_called_once_with('APPLE')
        model.assert_not_called()
        bridge = runner.OuijaArduinoBridge(port='FAKE')
        bridge.ser = Mock()
        bridge.ser.readline.return_value = b'OK SPELL_DONE\n'
        bridge.spell_text('APPLE')
        bridge.ser.write.assert_called_once_with(b'SPELL APPLE\n')
