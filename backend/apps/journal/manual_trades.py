"""Convert a manually entered trade to an atomic entry/optional exit pair."""

from decimal import Decimal
from uuid import UUID

from .accounts import scoped_rows
from .executions import import_rows, normalize, number, stamp
from .models import BrokerageAccount, Execution


def save_manual_trade(data, account_id=None):
    identifier = str(UUID(data["id"]))
    opening = stamp(data["opened_at"], "Opening time")
    closing = stamp(data["closed_at"], "Closing time") if data.get("closed_at") else None
    if closing and closing < opening:
        raise ValueError("Closing time must be on or after opening time.")
    if data.get("direction") not in ("Long", "Short"):
        raise ValueError("Choose Long or Short.")
    fees = Decimal(number(data.get("commission", 0), "Commissions"))
    if fees < 0:
        raise ValueError("Enter commissions as a positive cost.")
    first = Execution.objects.filter(account_id=account_id).order_by("created_at").first()
    selected = BrokerageAccount.objects.filter(pk=account_id).first()
    fallback = selected.source_identifier or f"brokerage:{account_id}" if selected else "Personal"
    account = first.data["account"] if first else fallback
    alias = first.data["account_alias"] if first else fallback
    currency = first.data["currency"] if first else "USD"
    common = {
        "ClientAccountID": account,
        "AccountAlias": alias,
        "CurrencyPrimary": currency,
        "AssetClass": data["asset"],
        "UnderlyingSymbol": data["symbol"],
        "Quantity": data["quantity"],
        "Multiplier": data.get("multiplier", 1),
        "Strike": data.get("strike", ""),
        "Expiry": data.get("expiry", ""),
        "Put/Call": data.get("put_call", ""),
    }
    side = "BUY" if data["direction"] == "Long" else "SELL"
    entry = normalize(
        {
            **common,
            "TradeID": f"manual-{identifier}-entry",
            "OrderTime": opening,
            "Buy/Sell": side,
            "Price": data["entry_price"],
            "Commission": str(-fees),
            "PositionEffect": "OPEN",
        }
    )
    entry["manual_group"] = identifier
    rows = [entry]
    if closing:
        exit = normalize(
            {
                **common,
                "TradeID": f"manual-{identifier}-exit",
                "OrderTime": closing,
                "Buy/Sell": "SELL" if side == "BUY" else "BUY",
                "Price": data["exit_price"],
                "Commission": "0",
                "PositionEffect": "CLOSE",
            }
        )
        exit["manual_group"] = identifier
        rows.append(exit)
    return import_rows(scoped_rows(rows, account_id), account_id)


def save_manual_execution(data, account_id=None):
    identifier = str(UUID(data["id"]))
    fees = Decimal(number(data.get("commission", 0), "Commissions"))
    if fees < 0:
        raise ValueError("Enter commissions as a positive cost.")
    first = Execution.objects.filter(account_id=account_id).order_by("created_at").first()
    selected = BrokerageAccount.objects.filter(pk=account_id).first()
    fallback = selected.source_identifier or f"brokerage:{account_id}" if selected else "Personal"
    row = normalize(
        {
            "TradeID": f"manual-fill-{identifier}",
            "ClientAccountID": first.data["account"] if first else fallback,
            "AccountAlias": first.data["account_alias"] if first else fallback,
            "CurrencyPrimary": first.data["currency"] if first else "USD",
            "AssetClass": data["asset"],
            "UnderlyingSymbol": data["symbol"],
            "Buy/Sell": data["side"],
            "Quantity": data["quantity"],
            "Price": data["price"],
            "Commission": str(-fees),
            "OrderTime": data["executed_at"],
            "Multiplier": data.get("multiplier", 1),
            "Strike": data.get("strike", ""),
            "Expiry": data.get("expiry", ""),
            "Put/Call": data.get("put_call", ""),
            "PositionEffect": "AUTO",
        }
    )
    return import_rows(scoped_rows([row], account_id), account_id)
