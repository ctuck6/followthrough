"""Read stock and option executions from thinkorswim Cash Balance sections."""

import csv
import io
import re
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from .executions import normalize


class StatementRows(list):
    warnings: list[str]


def amount(value: str) -> Decimal:
    text = value.strip().replace(",", "").replace("$", "")
    if not text or text == "--":
        return Decimal(0)
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    value = Decimal(text)
    if not value.is_finite():
        raise ValueError("Invalid statement amount.")
    return value


def parse_statement(content: str) -> StatementRows:
    if not isinstance(content, str) or len(content) > 2 * 1024 * 1024:
        raise ValueError("Choose a statement CSV up to 2 MB.")
    account = re.search(r"Account Statement for (\S+)", content)
    if not account:
        raise ValueError("Choose a thinkorswim account statement CSV.")
    source = "schwab:" + account[1]
    records = list(csv.reader(io.StringIO(content.lstrip("\ufeff"))))
    try:
        start = next(i for i, row in enumerate(records) if row == ["Cash Balance"]) + 1
    except StopIteration as error:
        raise ValueError("The statement has no Cash Balance section.") from error
    header = records[start]
    required = {
        "DATE",
        "TIME",
        "TYPE",
        "REF #",
        "DESCRIPTION",
        "Misc Fees",
        "Commissions & Fees",
        "AMOUNT",
    }
    if not required <= set(header):
        raise ValueError("Unsupported thinkorswim Cash Balance columns.")
    result = StatementRows()
    result.warnings = []
    for line, values in enumerate(records[start + 1 :], start + 2):
        if not values:
            break
        if len(values) != len(header):
            raise ValueError(f"Statement row {line}: incorrect column count.")
        row = dict(zip(header, values, strict=True))
        if row["TYPE"] != "TRD":
            if row["TYPE"] not in ("BAL", ""):
                raise ValueError(f"Statement row {line}: unsupported account event {row['TYPE']}.")
            continue
        description = row["DESCRIPTION"].strip()
        match = re.fullmatch(
            r"(BOT|SOLD)\s+([+-]?[\d,]+)\s+([/A-Za-z0-9.:\-]+)(.*?)\s+@([\d.]+)", description
        )
        if not match:
            raise ValueError(f"Statement row {line}: unsupported trade description.")
        side, quantity, symbol, contract, price = match.groups()
        future = symbol.startswith("/")
        option = None
        if contract.strip():
            option = re.fullmatch(
                r"\s+(\d+)\s+(?:\([^)]*\)\s+)?(\d{1,2} [A-Z]{3} \d{2})\s+([\d.]+)\s+(CALL|PUT)",
                contract,
            )
            if not option:
                raise ValueError(f"Statement row {line}: unsupported option contract.")
        ref = row["REF #"].strip().removeprefix('="').removesuffix('"')
        if not ref or ref == "--":
            raise ValueError(f"Statement row {line}: missing execution reference.")
        # Preserve statement wall-clock time, as with the existing local-time ledger.
        timestamp = (
            datetime.strptime(row["DATE"] + " " + row["TIME"], "%m/%d/%y %H:%M:%S")
            .replace(tzinfo=UTC)
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        multiplier = int(option[1]) if option else 1
        if future:
            root = re.fullmatch(r"/([A-Z]+)[FGHJKMNQUVXZ]\d{1,4}(?::[A-Z]+)?", symbol)
            multipliers = {
                "MNQ": 2,
                "NQ": 20,
                "MES": 5,
                "ES": 50,
                "MYM": 0.5,
                "YM": 5,
                "M2K": 5,
                "RTY": 50,
            }
            if not root or root[1] not in multipliers:
                raise ValueError(
                    f"Statement row {line}: futures contract multiplier is not configured for {symbol}."
                )
            multiplier = Decimal(str(multipliers[root[1]]))
        qty = abs(Decimal(quantity.replace(",", "")))
        expected = qty * Decimal(price) * multiplier * (-1 if side == "BOT" else 1)
        if not future and abs(amount(row["AMOUNT"]) - expected) > Decimal("0.02"):
            raise ValueError(
                f"Statement row {line}: trade amount does not match quantity and price."
            )
        fees = amount(row["Misc Fees"]) + amount(row["Commissions & Fees"])
        result.append(
            normalize(
                {
                    "TradeID": "tos-" + sha256(f"{source}:{ref}".encode()).hexdigest(),
                    "ClientAccountID": source,
                    "AccountAlias": account[1],
                    "CurrencyPrimary": "USD",
                    "AssetClass": "FUT" if future else "OPT" if option else "STK",
                    "Symbol": symbol,
                    "Buy/Sell": "BUY" if side == "BOT" else "SELL",
                    "Quantity": str(qty),
                    "Price": price,
                    "Commission": str(fees),
                    "OrderID": ref,
                    "OrderTime": timestamp,
                    "Multiplier": multiplier,
                    "Expiry": datetime.strptime(option[2], "%d %b %y")
                    .replace(tzinfo=UTC)
                    .date()
                    .isoformat()
                    if option
                    else "",
                    "Strike": option[3] if option else "",
                    "Put/Call": option[4][0] if option else "",
                }
            )
        )
        if len(result) > 10000:
            raise ValueError("Import at most 10,000 executions at once.")
    if not result:
        raise ValueError("No supported executions found.")
    return result
