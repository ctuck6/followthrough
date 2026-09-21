import tempfile
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.journal.executions import normalize,import_rows,ledger

class TradeTests(TestCase):
    def fill(self,tid,side='BUY',qty=10,price=10,effect='OPEN',day='2026-09-18'):
        return normalize({'TradeID':tid,'AccountAlias':'Test','CurrencyPrimary':'USD','AssetClass':'STK','Symbol':'ABC','Buy/Sell':side,'Quantity':qty,'Price':price,'PositionEffect':effect,'OrderTime':day+' 09:30:00','Commission':'-1'})
    def test_partial_fills_and_reentry(self):
        import_rows([self.fill('1'),self.fill('2',qty=5),self.fill('3','SELL',5,12,'CLOSE'),self.fill('4','SELL',10,12,'CLOSE'),self.fill('5')])
        trades=ledger()['trades']
        self.assertEqual(len(trades),2)
        self.assertEqual(float(trades[0]['net']),26)
        self.assertEqual(trades[0]['fill_count'],4)
        self.assertFalse(trades[0]['is_open'])
        self.assertTrue(trades[1]['is_open'])
    def test_overnight_stable_identity(self):
        import_rows([self.fill('1')]);key=ledger()['trades'][0]['trade_id']
        import_rows([self.fill('2','SELL',5,12,'CLOSE',day='2026-09-19')])
        trade=ledger()['trades'][0]
        self.assertEqual(key,trade['trade_id'])
        self.assertEqual(trade['sessions'],['2026-09-18','2026-09-19'])
        self.assertTrue(trade['is_open'])
        self.assertEqual(float(trade['remaining']),5)
    def test_reversal(self):
        import_rows([self.fill('1'),self.fill('2','SELL',15,12,'AUTO'),self.fill('3','BUY',5,11,'CLOSE')])
        trades=ledger()['trades']
        self.assertEqual([t['direction'] for t in trades],['Long','Short'])
        self.assertTrue(all(not t['is_open'] for t in trades))
        self.assertAlmostEqual(sum(float(t['net']) for t in trades),22)
    def test_journal_and_scoped_attachments(self):
        import_rows([self.fill('1'),self.fill('2','SELL',10,12,'CLOSE'),self.fill('3')])
        a,b=ledger()['trades'];url=f'/api/trades/{a["trade_id"]}/'
        self.assertEqual(self.client.put(url+'journal/',{'notes':'Followed the plan'},content_type='application/json').status_code,200)
        self.assertEqual(self.client.get(url+'journal/').json()['notes'],'Followed the plan')
        self.assertEqual(self.client.get(f'/api/trades/{b["trade_id"]}/journal/').json()['notes'],'')
        with tempfile.TemporaryDirectory() as media,override_settings(MEDIA_ROOT=media):
            response=self.client.post(url+'attachments/',{'file':SimpleUploadedFile('chart.txt',b'chart')})
            self.assertEqual(response.status_code,201)
            aid=response.json()['id']
            self.assertEqual(len(self.client.get(url+'attachments/').json()['attachments']),1)
            self.assertEqual(self.client.get('/api/days/2026-09-18/attachments/').json()['attachments'],[])
            self.assertEqual(self.client.delete(f'/api/trades/{b["trade_id"]}/attachments/{aid}/').status_code,404)
            self.assertEqual(self.client.delete(url+f'attachments/{aid}/').status_code,200)
