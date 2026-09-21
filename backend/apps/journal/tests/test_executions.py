from django.test import TestCase
from apps.journal.executions import normalize, import_rows, ledger, parse_csv
from apps.journal.models import Execution

class ExecutionTests(TestCase):
    def row(self, tid, side='BUY', qty='10', price='10', effect='OPEN', day='2026-09-18', **extra):
        return normalize({'TradeID':tid,'AccountAlias':'Test','CurrencyPrimary':'USD','AssetClass':'STK','Symbol':'ABC','Buy/Sell':side,'Quantity':qty,'Price':price,'PositionEffect':effect,'OrderTime':day+' 09:30:00','Commission':'-1',**extra})
    def test_overnight_fifo_and_fees(self):
        import_rows([self.row('1'),self.row('2',price='12'),self.row('3','SELL','15','15','CLOSE','2026-09-19')])
        result=ledger();close=result['executions'][-1]
        self.assertEqual(float(close['gross']),65)
        self.assertEqual(float(close['net']),62.5)
        self.assertEqual(float(result['open_lots'][0]['qty']),5)
    def test_short_option_multiplier(self):
        opt={'AssetClass':'OPT','Multiplier':'100','Strike':'50','Expiry':'2026-09-25','Put/Call':'P'}
        import_rows([self.row('1','SELL','2','5',**opt),self.row('2','BUY','2','3','CLOSE',**opt)])
        self.assertEqual(float(ledger()['executions'][-1]['net']),398)
    def test_missing_opening_fill(self):
        import_rows([self.row('2','SELL','10','15','CLOSE')])
        self.assertIsNone(ledger()['executions'][0]['net'])
        import_rows([self.row('1',day='2026-09-17')])
        self.assertEqual(float(ledger()['executions'][-1]['net']),48)
    def test_duplicate_and_conflict_atomic(self):
        row=self.row('1');self.assertEqual(import_rows([row,row]),{'imported':1,'duplicates':1})
        self.assertEqual(import_rows([row])['duplicates'],1)
        with self.assertRaises(ValueError):import_rows([self.row('2'),self.row('1',price='99')])
        self.assertEqual(Execution.objects.count(),1)
    def test_accounts_and_currencies_do_not_match(self):
        import_rows([self.row('1'),self.row('2','SELL','10','15','CLOSE',CurrencyPrimary='CAD')])
        self.assertIsNone(ledger()['executions'][-1]['net'])
    def test_api_validation(self):
        response=self.client.post('/api/executions/',data={'execution':{}},content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_duplicate_preview_keeps_session_destination(self):
        import_rows([self.row('1')])
        response=self.client.post('/api/executions/',data={'execution':{'TradeID':'1','AccountAlias':'Test','CurrencyPrimary':'USD','AssetClass':'STK','Symbol':'ABC','Buy/Sell':'BUY','Quantity':'10','Price':'10','PositionEffect':'OPEN','OrderTime':'2026-09-18 09:30:00','Commission':'-1'},'preview':True},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['dates'],['2026-09-18'])
        self.assertEqual(response.json()['duplicates'],1)
        self.assertEqual(response.json()['rows'],[])
