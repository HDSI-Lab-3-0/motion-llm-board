import unittest
from unittest.mock import Mock, patch
from openrouter import runner_spooky4 as runner
from openrouter.response_policy import personal_or_presence_response


class PersonalPolicyTests(unittest.TestCase):
    def test_facts_and_presence(self):
        for question in ('Do you know how old I am?', 'How old am I?', 'What is my name?', 'Will I get married?', 'Are you here? What is my birthday?'):
            self.assertEqual(personal_or_presence_response(question), 'WAIT')
        for question in ('Are you here?', 'Is anyone here?', 'Can you hear me?'):
            self.assertEqual(personal_or_presence_response(question), 'YES')
        self.assertIsNone(personal_or_presence_response('What should I eat?'))

    def test_runner_spells_wait_without_model(self):
        board = Mock()
        with patch.object(runner, 'HARDWARE_ENABLED', True), patch.object(runner, 'OuijaArduinoBridge', return_value=board), patch('builtins.input', side_effect=['t', 'How old am I?', 'q']), patch.object(runner.time, 'sleep'), patch.object(runner, 'ollama_completion') as model:
            runner.main()
        board.spell_text.assert_called_once_with('WAIT')
        model.assert_not_called()
