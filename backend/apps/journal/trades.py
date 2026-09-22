"""Group executions into flat-to-flat positions, keeping partial fills together."""
from decimal import Decimal as D
from hashlib import sha256


def group_trades(rows):
    active = {}
    trades = []
    def start(row, sign, suffix=''):
        trade = {**row, 'trade_id': sha256((row['trade_id']+suffix).encode()).hexdigest(),
                 'direction': 'Long' if sign == 1 else 'Short', 'sessions': [],
                 'quantity': D(0), 'remaining': D(0), 'entry_value': D(0),
                 'exit_value': D(0), 'exit_quantity': D(0), 'gross': D(0), 'net': D(0),
                 'commission': D(0), 'close_time': '', 'incomplete': False, 'fill_count': 0, 'execution_ids': []}
        trades.append(trade)
        return trade
    def record(t, row, qty):
        t['fill_count'] += 1
        if row['trade_id'] not in t['execution_ids']:t['execution_ids'].append(row['trade_id'])
        if row['session_date'] not in t['sessions']: t['sessions'].append(row['session_date'])
        t['commission'] += D(row['commission']) * qty / D(row['quantity'])
    for r in rows:
        key = tuple(r[k] for k in ('account','currency','asset_class','symbol','expiry','strike','put_call','multiplier'))+(r.get('manual_group',''),)
        sign = 1 if r['side'] == 'BUY' else -1
        qty = D(r['quantity'])
        t = active.get(key)
        if t and (1 if t['direction']=='Long' else -1) != sign:
            take = min(qty, t['remaining'])
            record(t,r,take)
            t['remaining'] -= take; t['exit_quantity'] += take
            t['exit_value'] += D(r['price'])*take
            if r['gross'] is None: t['incomplete'] = True
            else: t['gross'] += D(r['gross']); t['net'] += D(r['net'])
            qty -= take
            if not t['remaining']:
                t['close_time'] = r['execution_time']; active.pop(key); t = None
        if qty:
            if r['effect']=='CLOSE':
                missing = start(r,-sign,':missing');record(missing,r,qty)
                missing['incomplete']=True;missing['close_time']=r['execution_time']
                missing['exit_quantity']=qty;missing['exit_value']=D(r['price'])*qty
                continue
            if t is None:
                t=start(r,sign);active[key]=t
            record(t,r,qty);t['quantity']+=qty;t['remaining']+=qty;t['entry_value']+=D(r['price'])*qty
            if r['gross'] is None:t['incomplete']=True
    for t in trades:
        t['price'] = str(t.pop('entry_value')/t['quantity']) if t['quantity'] else None
        t['exit_price'] = str(t.pop('exit_value')/t['exit_quantity']) if t['exit_quantity'] else None
        t['is_open'] = bool(t['remaining'])
        t['status'] = 'Incomplete' if t['incomplete'] else 'Open' if t['is_open'] else 'Closed'
        for name in ('quantity','remaining','exit_quantity','commission','gross','net'):t[name]=str(t[name])
        if t['incomplete']:t['gross']=t['net']=None
    return trades
