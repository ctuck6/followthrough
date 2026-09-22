from django.test import TestCase
from apps.journal.models import Rule,Day,Execution,TradeReview
from apps.journal.executions import normalize,import_rows,ledger

class DeletionTests(TestCase):
    def fill(self,tid,side,qty,time):
        return normalize({'TradeID':tid,'AccountAlias':'Test','CurrencyPrimary':'USD','AssetClass':'STK','Symbol':'ABC','Buy/Sell':side,'Quantity':qty,'Price':'10','PositionEffect':'AUTO','OrderTime':f'2026-09-18 {time}:00','Commission':'-1'})
    def test_rules_bulk_preserves_saved_snapshot(self):
        rules=[Rule.objects.create(text=f'Rule {i}') for i in range(2)]
        checks=[{'id':r.id,'text':r.text,'weight':1,'status':'followed'} for r in rules]
        Day.objects.create(date='2026-09-18',checks=checks)
        response=self.client.delete('/api/rules/delete/',{'ids':[r.id for r in rules]},content_type='application/json')
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['rules'],[])
        self.assertEqual(Day.objects.get().checks,checks)
    def test_invalid_bulk_is_atomic(self):
        r=Rule.objects.create(text='Keep')
        response=self.client.delete('/api/rules/delete/',{'ids':[r.id,9999]},content_type='application/json')
        self.assertEqual(response.status_code,400);self.assertTrue(Rule.objects.get(pk=r.id).active)
    def test_delete_partial_exit_reopens_position(self):
        import_rows([self.fill('1','BUY',10,'09:30'),self.fill('2','SELL',4,'10:00'),self.fill('3','SELL',6,'10:01')])
        response=self.client.delete('/api/executions/delete/',{'ids':['3']},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['trades'][0]['remaining'],'6')
        self.assertTrue(response.json()['trades'][0]['is_open'])
    def test_delete_opening_fill_moves_journal_to_surviving_trade(self):
        import_rows([self.fill('1','BUY',10,'09:30'),self.fill('2','BUY',5,'09:31')])
        old=ledger()['trades'][0]['trade_id'];TradeReview.objects.create(trade_key=old,notes='Keep notes')
        response=self.client.delete('/api/executions/delete/',{'ids':['1']},content_type='application/json')
        new=response.json()['trades'][0]['trade_id']
        self.assertNotEqual(old,new);self.assertEqual(TradeReview.objects.get(pk=new).notes,'Keep notes')
    def test_delete_all_trade_executions_removes_trade_journal(self):
        import_rows([self.fill('1','BUY',10,'09:30'),self.fill('2','SELL',10,'10:00')])
        TradeReview.objects.create(trade_key=ledger()['trades'][0]['trade_id'],notes='Review')
        response=self.client.delete('/api/executions/delete/',{'ids':['1','2']},content_type='application/json')
        self.assertEqual(response.json()['trades'],[]);self.assertEqual(TradeReview.objects.count(),0)
        self.assertEqual(Execution.objects.count(),0)
