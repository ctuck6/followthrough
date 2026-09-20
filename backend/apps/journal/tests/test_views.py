import json
from django.test import TestCase, Client
from ..models import Rule, Day
from ..grading import grade

class JournalTests(TestCase):
    def test_snapshot_and_pnl_independence(self):
        rule=Rule.objects.create(text='Respect risk',weight=2)
        body={'plan':'Plan','checks':[{'id':rule.id,'status':'followed','weight':999}], 'trades':[{'symbol':'ES','side':'Long','pnl':'-500.00','notes':''}]}
        r=self.client.put('/api/days/2026-09-19/',json.dumps(body),content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['grade'],'A')
        self.assertEqual(r.json()['checks'][0]['weight'],2)
        rule.active=False;rule.save()
        Rule.objects.create(text='New rule',weight=5)
        r=self.client.put('/api/days/2026-09-19/',json.dumps(body),content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['checks'][0]['text'],'Respect risk')
        self.assertEqual(self.client.get('/api/state/').json()['days'][0]['plan'],'Plan')

    def test_invalid_data_cannot_create_day(self):
        rule=Rule.objects.create(text='Rule',weight=1)
        base={'checks':[{'id':rule.id,'status':'followed'}], 'trades':[{'symbol':'ES','side':'Long','pnl':'NaN'}]}
        self.assertEqual(self.client.put('/api/days/2026-09-19/',json.dumps(base),content_type='application/json').status_code,400)
        self.assertEqual(Day.objects.count(),0)
        base['trades']=[];base['checks']=[]
        self.assertEqual(self.client.put('/api/days/2026-09-19/',json.dumps(base),content_type='application/json').status_code,400)
        self.assertEqual(self.client.put('/api/days/not-a-date/','{}',content_type='application/json').status_code,400)

    def test_csrf_required(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/rules/',json.dumps({'text':'Rule','weight':1}),content_type='application/json').status_code,403)
        token=client.get('/api/state/').json()['csrfToken']
        self.assertEqual(client.post('/api/rules/',json.dumps({'text':'Rule','weight':1}),content_type='application/json',HTTP_X_CSRFTOKEN=token).status_code,201)

    def test_draft_persistence_and_date_isolation(self):
        other = Day.objects.create(date='2026-09-18', plan='Keep this day')
        body = {'checks': [], 'draft_trade': {'symbol':'ES', 'side':'Long', 'pnl':'-', 'notes':'Still writing'}}
        response = self.client.put('/api/days/2026-09-19/', json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['draft_trade']['pnl'], '-')
        self.assertEqual(response.json()['trades'], [])
        other.refresh_from_db()
        self.assertEqual(other.plan, 'Keep this day')
        self.assertEqual(Day.objects.get(date='2026-09-19').draft_trade['notes'], 'Still writing')

