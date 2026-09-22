import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.journal.models import Attachment, Day, Execution, TradeReview, Rule, Profile, PendingFileDeletion
from apps.journal.services import save_attachment

class SettingsTests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory()
        self.override=override_settings(MEDIA_ROOT=self.media.name);self.override.enable()
        self.addCleanup(self.media.cleanup);self.addCleanup(self.override.disable)
        Rule.objects.create(text='Keep risk small',weight=1)
        Profile.objects.create(pk=1,display_name='Trader',bio='My profile')
        Day.objects.create(date='2026-09-18',plan='Plan',reflection='Notes',trades=[{'symbol':'TEST'}])
        Execution.objects.create(trade_id='test',session_date='2026-09-18',execution_time='2026-09-18 09:30:00',data={})
        TradeReview.objects.create(trade_key='trade',notes='Review')
        self.session=save_attachment('2026-09-18',SimpleUploadedFile('chart.txt',b'chart'))
        self.trade=save_attachment('2026-09-18',SimpleUploadedFile('trade.txt',b'trade'),'trade')
        self.files=[Path(self.session.file.path),Path(self.trade.file.path)]
    def clear(self):
        return self.client.delete('/api/trading-data/',{'confirmation':'CLEAR_ALL_TRADE_AND_JOURNAL_DATA'},content_type='application/json')
    def test_clear_removes_records_and_files_preserves_profile_rules(self):
        response=self.clear();self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'cleared':True,'pending_files':0})
        for model in [Day,Execution,TradeReview,Attachment,PendingFileDeletion]:self.assertEqual(model.objects.count(),0)
        self.assertTrue(all(not path.exists() for path in self.files))
        self.assertEqual(Profile.objects.get(pk=1).display_name,'Trader')
        self.assertEqual(Rule.objects.count(),1)
        self.assertEqual(self.clear().status_code,200)
    def test_requires_confirmation_method_and_csrf(self):
        self.assertEqual(self.client.get('/api/trading-data/').status_code,405)
        self.assertEqual(self.client.delete('/api/trading-data/',{},content_type='application/json').status_code,400)
        self.assertEqual(Client(enforce_csrf_checks=True).delete('/api/trading-data/',{'confirmation':'CLEAR_ALL_TRADE_AND_JOURNAL_DATA'},content_type='application/json').status_code,403)
        self.assertEqual(Execution.objects.count(),1)
        self.assertTrue(all(path.exists() for path in self.files))
    def test_file_failure_retained_for_retry(self):
        storage=Attachment._meta.get_field('file').storage
        with patch.object(storage,'delete',side_effect=OSError('Storage unavailable')):
            self.assertEqual(self.clear().json()['pending_files'],2)
        self.assertEqual(PendingFileDeletion.objects.count(),2)
        self.assertEqual(self.clear().json()['pending_files'],0)
        self.assertTrue(all(not path.exists() for path in self.files))
    def test_profile_roundtrip_and_validation(self):
        response=self.client.put('/api/profile/',{'display_name':'New name','bio':'Trading goals'},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/profile/').json(),{'display_name':'New name','bio':'Trading goals'})
        self.assertEqual(self.client.put('/api/profile/',{'display_name':'x'*101},content_type='application/json').status_code,400)
