from uuid import uuid4
from django.test import TestCase
from apps.journal.executions import ledger
from apps.journal.models import Execution

class ManualTradeTests(TestCase):
    def data(self,**extra):
        return {'id':str(uuid4()),'asset':'STK','symbol':'TEST','direction':'Long','quantity':'10','entry_price':'10','exit_price':'12','commission':'2','opened_at':'2026-09-18T09:30','closed_at':'2026-09-18T10:30',**extra}
    def post(self,data):return self.client.post('/api/manual-trades/',data,content_type='application/json')
    def test_completed_and_retry(self):
        data=self.data();response=self.post(data)
        self.assertEqual(response.status_code,201)
        trade=response.json()['trades'][0]
        self.assertFalse(trade['is_open']);self.assertEqual(float(trade['net']),18)
        self.assertEqual(self.post(data).json()['duplicates'],2)
        self.assertEqual(Execution.objects.count(),2)
    def test_open_and_separate_manual_positions(self):
        self.post(self.data(closed_at=''));self.post(self.data(closed_at=''))
        trades=ledger()['trades'];self.assertEqual(len(trades),2)
        self.assertTrue(all(t['is_open'] for t in trades))
    def test_overnight_short_option(self):
        response=self.post(self.data(asset='OPT',direction='Short',quantity='2',entry_price='5',exit_price='3',multiplier='100',strike='50',expiry='2026-09-25',put_call='P',closed_at='2026-09-19T10:00'))
        self.assertEqual(response.status_code,201)
        trade=response.json()['trades'][0]
        self.assertEqual(float(trade['net']),398)
        self.assertEqual(trade['sessions'],['2026-09-18','2026-09-19'])
    def test_invalid_close_or_fee_does_not_save_entry(self):
        for patch in [{'closed_at':'2026-09-17T10:00'},{'commission':'-1'},{'exit_price':''}]:
            self.assertEqual(self.post(self.data(**patch)).status_code,400)
        self.assertEqual(Execution.objects.count(),0)
