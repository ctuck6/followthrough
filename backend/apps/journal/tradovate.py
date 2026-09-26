"""Import Tradovate order exports without inventing individual fills or fees."""

import csv
import io
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from .executions import normalize
from .thinkorswim import StatementRows

MULTIPLIERS = {
    "MNQ": "2",
    "NQ": "20",
    "MES": "5",
    "ES": "50",
    "MYM": "0.5",
    "YM": "5",
    "M2K": "5",
    "RTY": "50",
}


def parse_orders(content: str) -> StatementRows:
    if not isinstance(content, str) or len(content) > 2 * 1024 * 1024:
        raise ValueError("Choose a Tradovate orders CSV up to 2 MB.")

    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    required = {
        "orderId",
        "Account",
        "B/S",
        "Contract",
        "Product",
        "filledQty",
        "Fill Time",
        "Status",
        "Avg Fill Price",
        "Currency",
    }

    if not required <= set(reader.fieldnames or []):
        raise ValueError("Choose a Tradovate Orders CSV export.")

    result = StatementRows()
    result.warnings = [
        (
            "Tradovate Orders contains average fills per order, not individual executions. "
            "Commissions are absent; net P&L excludes fees."
        )
    ]
    seen = {}

    for line, raw in enumerate(reader, 2):
        row = {k: (v or "").strip() for k, v in raw.items() if k is not None}

        try:
            qty = Decimal(row["filledQty"] or "0")

            if not qty.is_finite() or qty < 0 or qty != qty.to_integral_value():
                raise ValueError("Invalid filled quantity.")

            if qty == 0:
                continue

            if row["Status"].lower() != "filled":
                raise ValueError(
                    "Partially filled orders require a final filled export."
                )

            product = row["Product"].upper()
            contract = row["Contract"].upper()

            if product not in MULTIPLIERS:
                raise ValueError(f"Unsupported futures product: {product}.")

            if not re.fullmatch(
                re.escape(product) + r"[FGHJKMNQUVXZ]\d{1,4}", contract
            ):
                raise ValueError("Invalid futures contract.")

            if not row["Account"] or not row["orderId"]:
                raise ValueError("Account and order ID are required.")

            timestamp = datetime.strptime(
                row["Fill Time"], "%m/%d/%Y %H:%M:%S"
            ).replace(tzinfo=UTC)
            source = "tradovate:" + row["Account"]
            item = normalize(
                {
                    "TradeID": "tradovate-"
                    + sha256(f"{source}:{row['orderId']}".encode()).hexdigest(),
                    "ClientAccountID": source,
                    "AccountAlias": row["Account"],
                    "CurrencyPrimary": row["Currency"],
                    "AssetClass": "FUT",
                    "Symbol": "/" + contract,
                    "Buy/Sell": row["B/S"].upper(),
                    "Quantity": str(qty),
                    "Price": row["Avg Fill Price"].replace(",", ""),
                    "Commission": "0",
                    "OrderID": row["orderId"],
                    "OrderTime": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "Multiplier": MULTIPLIERS[product],
                }
            )

            if item["trade_id"] in seen:
                if item != seen[item["trade_id"]]:
                    raise ValueError("Conflicting rows for the same order.")

                continue

            seen[item["trade_id"]] = item
            result.append(item)

        except (ValueError, InvalidOperation, KeyError) as error:
            raise ValueError(f"Tradovate row {line}: {error}") from error

        if len(result) > 10000:
            raise ValueError("Import at most 10,000 orders at once.")

    if not result:
        raise ValueError("No filled orders found.")

    result.sort(key=lambda item: item["order_time"])

    return result
