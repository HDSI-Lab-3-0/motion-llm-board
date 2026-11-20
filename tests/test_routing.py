import unittest
from unittest.mock import patch

from openrouter import routing
from openrouter import runner_spooky4 as runner


class RoutingTests(unittest.TestCase):
    def test_names_bypass_model_and_vary(self):
        with patch.object(runner, 'ollama_completion') as model:
            first = runner.pick_one_word('what is ur name??')
            second = runner.pick_one_word("what’s your name?")
        self.assertIn(first, routing.WORD_BANKS['names'])
        self.assertNotEqual(first, second)
        model.assert_not_called()

    def test_choices_and_nonchoices(self):
        for question, choices in [
            ('Do you like dogs or cats?', ['DOGS', 'CATS']),
            ('Tea, coffee, or water?', ['TEA', 'COFFEE', 'WATER']),
            ('Would you prefer ice cream or apple pie?', ['ICE CREAM', 'APPLE PIE']),
        ]:
            self.assertEqual(routing.offered_choices(question), choices)
            self.assertEqual(runner.classify_mode(question), 'ONE_WORD')
            with patch.object(runner, 'ollama_completion') as model:
                self.assertIn(runner.pick_one_word(question), choices)
            model.assert_not_called()
        for question in ['Do you have any brothers or sisters?',
                         'Are you here, or is nobody listening?']:
            self.assertEqual(routing.offered_choices(question), [])
            self.assertEqual(runner.classify_mode(question), 'YES_NO')

    def test_specific_banks_and_word_boundaries(self):
        self.assertEqual(routing.select_bank('Who are you?'), 'names')
        self.assertEqual(routing.select_bank('What should I eat?'), 'food')
        self.assertEqual(routing.select_bank('Tell me something'), 'generic')
        self.assertEqual(routing.select_bank('Explain this'), 'generic')
        self.assertIsNone(routing.direct_response('What is my name?'))
