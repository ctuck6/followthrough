from django.apps import apps
from django.db import IntegrityError, transaction
from django.test import TestCase
from ..models import Day

class ModelTests(TestCase):
    def test_namespace_keeps_existing_database_identity(self):
        self.assertEqual(apps.get_app_config('journal').name, 'apps.journal')
        self.assertEqual(Day._meta.db_table, 'journal_day')

    def test_one_journal_per_date(self):
        Day.objects.create(date='2026-09-19')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Day.objects.create(date='2026-09-19')
