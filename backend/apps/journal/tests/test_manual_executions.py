from uuid import uuid4
from django.test import TestCase
from apps.journal.executions import ledger
from apps.journal.models import Execution

class ManualExecutionTests(TestCase):
    def data(self,side='BUY',qty='10',time='09:30',**extra):
        return {'id':str(uuid4()),'asset':'STK','symbol':'TEST','side':side,'quantity':qty,'price':'10','commission':'1','executed_at':f'2026-09-18T{time}',**extra}
    def post(self,data):return self.client.post('/api/manual-executions/',data,content_type='application/json')
    def test_partial_then_flat_and_dedup(self):
        entry=self.data();self.assertEqual(self.post(entry).status_code,201)
        self.assertEqual(self.post(entry).json()['duplicates'],1)
        response=self.post(self.data('SELL','4','10:00',price='12'))
        trade=response.json()['trades'][0]
        self.assertTrue(trade['is_open']);self.assertEqual(float(trade['remaining']),6)
        response=self.post(self.data('SELL','6','10:01',price='12'))
        trade=response.json()['trades'][0]
        self.assertFalse(trade['is_open']);self.assertEqual(float(trade['remaining']),0)
        self.assertEqual(float(trade['net']),17)
        self.assertEqual(Execution.objects.count(),3)
    def test_short_option_and_reversal(self):
        opt={'asset':'OPT','multiplier':'100','strike':'50','expiry':'2026-09-25','put_call':'P'}
        self.post(self.data('SELL','2',price='5',**opt))
        trade=self.post(self.data('BUY','2','10:00',price='3',**opt)).json()['trades'][0]
        self.assertFalse(trade['is_open']);self.assertEqual(trade['direction'],'Short');self.assertEqual(float(trade['net']),398)
    def test_invalid_cost_atomic(self):
        self.assertEqual(self.post(self.data(commission='-1')).status_code,400)
        self.assertEqual(Execution.objects.count(),0)
    def test_identical_timestamps_preserve_manual_submission_order(self):
        self.post(self.data(id='ffffffff-ffff-4fff-8fff-ffffffffffff'))
        trade=self.post(self.data('SELL','4',id='00000000-0000-4000-8000-000000000000')).json()['trades'][0]
        self.assertEqual(trade['direction'],'Long')
        self.assertEqual(float(trade['remaining']),6)
