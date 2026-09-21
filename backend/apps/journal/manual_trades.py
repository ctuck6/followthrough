"""Convert a manually entered trade to an atomic entry/optional exit pair."""
from uuid import UUID
from decimal import Decimal
from .models import Execution
from .executions import normalize, import_rows, number, stamp


def save_manual_trade(data):
    identifier=str(UUID(data['id']))
    opening=stamp(data['opened_at'],'Opening time')
    closing=stamp(data['closed_at'],'Closing time') if data.get('closed_at') else None
    if closing and closing<opening: raise ValueError('Closing time must be on or after opening time.')
    if data.get('direction') not in ('Long','Short'):raise ValueError('Choose Long or Short.')
    fees=Decimal(number(data.get('commission',0),'Commissions'))
    if fees<0:raise ValueError('Enter commissions as a positive cost.')
    first=Execution.objects.order_by('created_at').first()
    account=first.data['account'] if first else 'Personal'
    alias=first.data['account_alias'] if first else 'Personal'
    currency=first.data['currency'] if first else 'USD'
    common={'ClientAccountID':account,'AccountAlias':alias,'CurrencyPrimary':currency,
            'AssetClass':data['asset'],'UnderlyingSymbol':data['symbol'],'Quantity':data['quantity'],
            'Multiplier':data.get('multiplier',1),'Strike':data.get('strike',''),
            'Expiry':data.get('expiry',''),'Put/Call':data.get('put_call','')}
    side='BUY' if data['direction']=='Long' else 'SELL'
    entry=normalize({**common,'TradeID':f'manual-{identifier}-entry','OrderTime':opening,'Buy/Sell':side,
                     'Price':data['entry_price'],'Commission':str(-fees),'PositionEffect':'OPEN'})
    entry['manual_group']=identifier
    rows=[entry]
    if closing:
        exit=normalize({**common,'TradeID':f'manual-{identifier}-exit','OrderTime':closing,
                        'Buy/Sell':'SELL' if side=='BUY' else 'BUY','Price':data['exit_price'],
                        'Commission':'0','PositionEffect':'CLOSE'})
        exit['manual_group']=identifier
        rows.append(exit)
    return import_rows(rows)
