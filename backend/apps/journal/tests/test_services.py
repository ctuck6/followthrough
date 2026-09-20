from datetime import date
from django.test import TestCase
from ..models import Rule
from ..services import save_day, save_rule
from ..selectors import journal_state

class ServiceTests(TestCase):
    def test_rule_replacement_keeps_historical_snapshot(self):
        old = save_rule({'text': 'Respect the stop', 'weight': 3})
        day = save_day(date(2026, 9, 19), {'checks': [{'id': old.id, 'status': 'followed'}]})
        replacement = save_rule({'id': old.id, 'text': 'Plan the stop', 'weight': 5})
        old.refresh_from_db()
        day.refresh_from_db()
        self.assertFalse(old.active)
        self.assertEqual(day.checks[0]['text'], 'Respect the stop')
        self.assertEqual(journal_state()['rules'][0]['id'], replacement.id)
        self.assertEqual(journal_state()['days'][0]['grade'], 'A')

    def test_failed_rule_replacement_rolls_back(self):
        old = Rule.objects.create(text='Original', weight=1)
        with self.assertRaises(ValueError):
            save_rule({'id': old.id, 'text': '', 'weight': 1})
        old.refresh_from_db()
        self.assertTrue(old.active)
        self.assertEqual(Rule.objects.count(), 1)
