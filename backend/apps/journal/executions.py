"""Execution import and decimal FIFO accounting, independent of display sorting."""
import csv
import io
from collections import defaultdict, deque
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from django.db import transaction
from .models import Day, Execution, Rule
D = Decimal

def number(value, name, positive=False):
    try:
        result = D(str(value).strip())
        if not result.is_finite() or abs(result)>D('1000000000000') or (positive and result<=0): raise ValueError()
        return str(result.normalize())
    except (InvalidOperation, ValueError): raise ValueError(f'{name} must be a valid {"positive " if positive else ""}number.')

def stamp(value, name):
    try:
        value=str(value).strip().replace('T',' ')
        if len(value)==16: value+=':00'
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').isoformat(sep=' ')
    except ValueError: raise ValueError(f'{name} must be YYYY-MM-DD HH:MM:SS.')

def normalize(row):
    def text(key, default=''):
        value=str(row.get(key,default) or '').strip()
        if len(value)>200: raise ValueError(f'{key} is too long.')
        return value
    tid=text('TradeID')
    if not tid or len(tid)>100: raise ValueError('TradeID is required (up to 100 characters).')
    asset=text('AssetClass').upper()
    if asset not in ('STK','OPT'): raise ValueError('Only STK and OPT are supported.')
    symbol=text('UnderlyingSymbol') or text('UnderlyingSymbo') or text('Symbol')
    if not symbol: raise ValueError('UnderlyingSymbol or Symbol is required.')
    account=text('ClientAccountID') or text('AccountAlias')
    if not account: raise ValueError('AccountAlias or ClientAccountID is required.')
    currency=text('CurrencyPrimary').upper()
    if len(currency)!=3: raise ValueError('CurrencyPrimary must be a three-letter currency code.')
    if text('CommissionCurrency',currency).upper()!=currency: raise ValueError('Commission currency differs; FX conversion is not supported.')
    side=text('Buy/Sell').upper()
    if side not in ('BUY','SELL'): raise ValueError('Buy/Sell must be BUY or SELL.')
    quantity=abs(D(number(row.get('Quantity',''),'Quantity')))
    if not quantity: raise ValueError('Quantity must not be zero.')
    if asset=='OPT' and quantity!=quantity.to_integral_value(): raise ValueError('Option quantity must be whole contracts.')
    price=number(row.get('Price',''),'Price')
    if D(price)<0: raise ValueError('Price must not be negative.')
    multiplier=number(row.get('Multiplier',1 if asset=='STK' else ''),'Multiplier',True)
    order=stamp(text('OrderTime'),'OrderTime'); execution=stamp(text('Date/Time',order),'Date/Time')
    session=date.fromisoformat(text('TradeDate',execution[:10])).isoformat()
    commission=number(row.get('Commission',0),'Commission')
    effect=text('PositionEffect').upper();codes=text('Code').split(';')
    if not effect: effect='OPEN' if 'O' in codes else 'CLOSE' if 'C' in codes else 'AUTO'
    if effect not in ('OPEN','CLOSE','AUTO'): raise ValueError('PositionEffect must be OPEN, CLOSE or AUTO.')
    if text('TransactionType','ExchTrade') not in ('ExchTrade','Trade'): raise ValueError('Corrections, cancellations and non-trade events require reconciliation.')
    if text('LevelOfDetail','EXECUTION')!='EXECUTION': raise ValueError('Import EXECUTION-level rows only.')
    expiry=strike=put_call=''
    if asset=='OPT':
        expiry=date.fromisoformat(text('Expiry')).isoformat();strike=number(row.get('Strike',''),'Strike',True);put_call=text('Put/Call').upper()
        if put_call not in ('P','C'): raise ValueError('Put/Call must be P or C.')
    return dict(trade_id=tid,account=account,account_alias=text('AccountAlias',account),currency=currency,asset_class=asset,symbol=symbol.upper(),multiplier=multiplier,strike=strike,expiry=expiry,put_call=put_call,order_id=text('OrderID'),order_time=order,execution_time=execution,session_date=session,side=side,quantity=str(quantity.normalize()),price=price,commission=commission,effect=effect)

def parse_csv(content):
    if not isinstance(content,str) or len(content)>2*1024*1024: raise ValueError('Choose a CSV up to 2 MB.')
    reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    if not reader.fieldnames or 'TradeID' not in reader.fieldnames: raise ValueError('Choose an IBKR execution CSV containing TradeID.')
    if len(reader.fieldnames)!=len(set(reader.fieldnames)): raise ValueError('Duplicate CSV column names.')
    result=[]
    for index,row in enumerate(reader,2):
        if len(result)>=10000: raise ValueError('Import at most 10,000 executions at once.')
        if None in row or None in row.values(): raise ValueError(f'Row {index}: incorrect column count.')
        try: result.append(normalize(row))
        except (ValueError,InvalidOperation) as exc: raise ValueError(f'Row {index}: {exc}')
    if not result: raise ValueError('The CSV has no executions.')
    return result

def inspect_batch(rows):
    existing={item.trade_id:item.data for item in Execution.objects.filter(trade_id__in=[r['trade_id'] for r in rows])}
    unique={};duplicates=0
    for row in rows:
        tid=row['trade_id'];previous=unique.get(tid) or existing.get(tid)
        if previous is not None:
            if previous!=row: raise ValueError(f'TradeID {tid} already exists with different data. Nothing imported.')
            duplicates+=1
        else: unique[tid]=row
    return list(unique.values()),duplicates

@transaction.atomic
def import_rows(rows):
    new,duplicates=inspect_batch(rows);count=0
    for row in new:
        item,created=Execution.objects.get_or_create(trade_id=row['trade_id'],defaults={'session_date':row['session_date'],'execution_time':row['execution_time'],'data':row})
        if not created and item.data!=row: raise ValueError(f'Conflicting TradeID {row["trade_id"]}.')
        count+=int(created)
        if not created: duplicates+=1
    for day in {r['session_date'] for r in new}:
        Day.objects.get_or_create(date=day,defaults={'checks':[dict(r,status='pending') for r in Rule.objects.filter(active=True).values('id','text','weight')]})
    return {'imported':count,'duplicates':duplicates}

def ledger():
    books=defaultdict(deque);result=[];summaries={}
    # Manual fills at the same timestamp keep their submission order.
    ordered=sorted(Execution.objects.all(),key=lambda item:(item.execution_time,(1,item.pk) if item.trade_id.startswith('manual-') else (0,item.trade_id)))
    for model in ordered:
        row=dict(model.data);qty=D(row['quantity']);remaining=qty;sign=1 if row['side']=='BUY' else -1
        key=tuple(row[field] for field in ('account','currency','asset_class','symbol','expiry','strike','put_call','multiplier'))+(row.get('manual_group',''),)
        lots=books[key];gross=D(0);fees=D(0);matched=D(0);incomplete=False
        if row['effect']=='OPEN' and lots and lots[0]['sign']!=sign: incomplete=True
        else:
            while remaining and lots and lots[0]['sign']!=sign:
                lot=lots[0];take=min(remaining,lot['qty'])
                gross+=(D(row['price'])-lot['price'])*take*D(row['multiplier'])*lot['sign']
                fees+=lot['fee_per_unit']*take+D(row['commission'])/qty*take
                lot['qty']-=take;remaining-=take;matched+=take
                if not lot['qty']:lots.popleft()
            if remaining:
                if row['effect']=='CLOSE':incomplete=True
                else:lots.append({'qty':remaining,'price':D(row['price']),'sign':sign,'fee_per_unit':D(row['commission'])/qty,'trade_id':row['trade_id']})
        row.update(gross=None if incomplete else str(gross),net=None if incomplete else str(gross+fees),matched_quantity=str(matched),unmatched_quantity=str(remaining if incomplete else 0),status='P&L incomplete' if incomplete else 'Closed' if matched==qty else 'Partial close / open' if matched else 'Open',direction='Long' if (sign==-1 if matched else sign==1) else 'Short')
        result.append(row)
        summary=summaries.setdefault(row['session_date'],{}).setdefault(row['currency'],{'gross':D(0),'net':D(0),'commission':D(0),'incomplete':0})
        summary['commission']+=D(row['commission']);summary['incomplete']+=int(incomplete)
        if not incomplete:summary['gross']+=gross;summary['net']+=gross+fees
    for groups in summaries.values():
        for summary in groups.values():
            for name in ('gross','net','commission'):summary[name]=str(summary[name])
    open_lots=[{'account':key[0],'currency':key[1],'asset_class':key[2],'symbol':key[3],'expiry':key[4],'strike':key[5],'put_call':key[6],'multiplier':key[7],**{k:str(v) for k,v in lot.items()}} for key,lots in books.items() for lot in lots]
    from .trades import group_trades
    return {'executions':result,'summaries':summaries,'open_lots':open_lots,'trades':group_trades(result)}
