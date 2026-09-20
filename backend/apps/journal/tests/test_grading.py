import json
from django.test import TestCase, Client
from ..models import Rule, Day
from ..grading import grade

class JournalTests(TestCase):
    def test_weighted_grade_and_pending(self):
        checks = [{'weight':3,'status':'followed'}, {'weight':1,'status':'broken'}, {'weight':10,'status':'na'}]
        self.assertEqual(grade(checks), {'score':75,'grade':'C'})
        checks[1]['status']='pending'
        self.assertIsNone(grade(checks)['score'])
        self.assertIsNone(grade([])['score'])
        self.assertIsNone(grade([{'weight':1,'status':'na'}])['score'])

