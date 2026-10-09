"""Read-only Schwab trade history sync, serialized across local processes."""

import fcntl
import json
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .accounts import request_account, scoped_rows
from .executions import import_rows, normalize
from .ibkr_flex import flex_setting
from .models import BrokerageAccount, Execution
from .schwab_connection import connection_status, private_directory, write_private

PACIFIC = ZoneInfo("America/Los_Angeles")


class SyncError(ValueError):
    pass


def number(value: object) -> Decimal:
    result = Decimal(str(value))

    if not result.is_finite():
        raise SyncError("Schwab returned an invalid amount.")

    return result


def parse_transactions(items: list, source: str) -> list[dict]:
    rows = []
    zone = ZoneInfo(flex_setting("TRADING_TIMEZONE") or "America/New_York")

    for item in items:
        if item.get("type") != "TRADE":
            continue

        if item.get("status") != "VALID" or not item.get("activityId"):
            raise SyncError("A Schwab trade needs review before import (status or ID).")

        transfers = item.get("transferItems", [])
        securities = [
            x for x in transfers if x.get("instrument", {}).get("assetType") != "CURRENCY"
        ]

        if len(securities) != 1:
            raise SyncError("A Schwab trade has unsupported multiple legs; use CSV pending review.")

        fill = securities[0]
        instrument = fill["instrument"]
        asset = instrument.get("assetType")

        if asset not in {"EQUITY", "OPTION"}:
            raise SyncError("Schwab returned an unsupported instrument; use CSV for this trade.")

        amount = number(fill["amount"])
        price = number(fill["price"])
        stamp = datetime.fromisoformat(item["time"])

        if stamp.tzinfo is None or not amount:
            raise SyncError("Schwab returned an invalid execution time or quantity.")

        symbol = instrument["symbol"]
        expiry, strike, put_call = "", "", ""
        multiplier = 1

        if asset == "OPTION":
            match = re.fullmatch(r"([A-Z.]+)\s*(\d{6})([CP])(\d{8})", symbol)

            if not match or instrument.get("optionMultiplier", 100) != 100:
                raise SyncError("This option contract requires manual verification.")

            symbol, expiration, put_call, strike_digits = match.groups()
            expiry = f"20{expiration[:2]}-{expiration[2:4]}-{expiration[4:]}"
            strike = str(Decimal(strike_digits) / 1000)
            multiplier = 100

        fees = Decimal(0)

        for fee in transfers:
            if fee is fill:
                continue

            if fee.get("instrument", {}).get("symbol") != "CURRENCY_USD" or not fee.get("feeType"):
                raise SyncError("Schwab returned an unsupported currency or cash transfer.")

            fees -= abs(number(fee["cost"]))

        if abs(number(item["netAmount"]) - (-amount * price * multiplier + fees)) > Decimal("0.02"):
            raise SyncError("Schwab trade cash and fees do not reconcile; import held for review.")

        timestamp = stamp.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S")
        effect = {"OPENING": "OPEN", "CLOSING": "CLOSE"}.get(fill.get("positionEffect"))

        if effect is None:
            raise SyncError("Schwab trade is missing its opening/closing indicator.")

        rows.append(
            normalize(
                {
                    "TradeID": f"schwab-api-{item['activityId']}",
                    "ClientAccountID": source,
                    "AccountAlias": source,
                    "CurrencyPrimary": "USD",
                    "AssetClass": "OPT" if asset == "OPTION" else "STK",
                    "Symbol": symbol,
                    "Quantity": str(abs(amount)),
                    "Price": str(price),
                    "Buy/Sell": "BUY" if amount > 0 else "SELL",
                    "Commission": str(fees),
                    "OrderID": str(item.get("orderId", "")),
                    "OrderTime": timestamp,
                    "Date/Time": timestamp,
                    "Multiplier": multiplier,
                    "Expiry": expiry,
                    "Strike": strike,
                    "Put/Call": put_call,
                    "PositionEffect": effect,
                }
            )
        )

    return rows


def state_for(account_id: int) -> dict:
    path = private_directory() / f"sync-{account_id}.json"

    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def run_account(account: BrokerageAccount, startup: bool = False) -> None:
    directory = private_directory()
    token = directory / f"token-{account.pk}.json"

    if not token.exists() or connection_status(account.pk)["status"] != "connected":
        return

    with (directory / f"sync-{account.pk}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return

        state = state_for(account.pk)
        now = timezone.now()
        local = now.astimezone(PACIFIC)
        scheduled = local.weekday() < 5 and (local.hour, local.minute) >= (13, 15)
        scheduled = scheduled and state.get("scheduled_day") != local.date().isoformat()
        last = datetime.fromisoformat(state["last_attempt"]) if state.get("last_attempt") else None
        due = (
            state.get("status") == "running"
            or state.get("requested")
            or scheduled
            or (startup and (not last or now - last > timedelta(minutes=10)))
        )
        retry = state.get("retry_at")
        due = due or (retry and datetime.fromisoformat(retry) <= now)

        if not due:
            return

        state.update(
            status="running",
            message="Fetching Schwab trades…",
            requested=False,
            last_attempt=now.isoformat(),
            retry_at=None,
        )

        if scheduled:
            state["scheduled_day"] = local.date().isoformat()

        path = directory / f"sync-{account.pk}.json"
        write_private(path, state)

        try:
            from schwab.auth import client_from_access_functions

            # Never allow HTTP request logs to expose credentials or account hashes.
            for name in ("httpx", "httpcore", "authlib", "schwab"):
                logging.getLogger(name).disabled = True

            client = client_from_access_functions(
                flex_setting("SCHWAB_APP_KEY"),
                flex_setting("SCHWAB_APP_SECRET"),
                lambda: json.loads(token.read_text()),
                lambda value, **kwargs: write_private(token, value),
            )
            response = client.get_account_numbers()

            if response.status_code != 200:
                raise SyncError("Schwab account access failed. Reconnect Schwab and retry.")

            accounts = response.json()
            source = account.source_identifier
            matches = (
                [a for a in accounts if "schwab:" + a["accountNumber"] == source]
                if source
                else accounts
            )

            if len(matches) != 1:
                raise SyncError(
                    "Cannot uniquely match this Schwab account. Account linking needs review."
                )

            linked = matches[0]
            source = "schwab:" + linked["accountNumber"]

            if (
                BrokerageAccount.objects.filter(broker="schwab", source_identifier=source)
                .exclude(pk=account.pk)
                .exists()
            ):
                raise SyncError("This Schwab account is already linked in Followthrough.")

            start = (
                datetime.fromisoformat(state["last_success"]) - timedelta(days=7)
                if state.get("last_success")
                else now - timedelta(days=60)
            )
            raw = []

            while start < now:
                end = min(start + timedelta(days=30), now)
                response = client.get_transactions(
                    linked["hashValue"],
                    start_date=start,
                    end_date=end,
                    transaction_types=[client.Transactions.TransactionType.TRADE],
                )

                if response.status_code != 200:
                    raise SyncError(
                        "Schwab trade history is unavailable. Reconnect or retry later."
                    )

                raw.extend(response.json())
                start = end

            rows = parse_transactions(raw, source)

            with transaction.atomic():
                BrokerageAccount.objects.filter(pk=-1).update(name="")
                # Do not guess identity across statement and API reference schemes.
                if (
                    rows
                    and Execution.objects.filter(account=account)
                    .exclude(data__source_trade_id__startswith="schwab-api-")
                    .exists()
                ):
                    raise SyncError(
                        "Existing CSV/manual trades need reconciliation before API import."
                    )

                result = import_rows(scoped_rows(rows, account.pk), account.pk)
                account.source_identifier = source

                if result["imported"]:
                    account.last_import_at = timezone.now()

                account.save(update_fields=["source_identifier", "last_import_at"])

            state.update(
                status="success",
                message="Sync complete." if rows else "No new trades reported.",
                last_success=timezone.now().isoformat(),
                failures=0,
                **result,
            )
        except Exception as error:  # noqa: BLE001 -- credentials must never reach UI/logs
            failures = state.get("failures", 0) + 1
            state.update(
                status="error",
                failures=failures,
                message=str(error)
                if isinstance(error, SyncError)
                else "Schwab sync failed. Reconnect or retry; no partial import was saved.",
                retry_at=(timezone.now() + timedelta(minutes=15 * failures)).isoformat()
                if failures <= 3
                else None,
            )

        write_private(path, state)


def run_all(startup: bool = False) -> None:
    for account in BrokerageAccount.objects.filter(broker="schwab"):
        run_account(account, startup)


@require_http_methods(["GET", "POST"])
def sync_status(request: HttpRequest) -> JsonResponse:
    account = BrokerageAccount.objects.filter(pk=request_account(request), broker="schwab").first()

    if account is None:
        return JsonResponse({"error": "Select a Schwab account."}, status=400)

    if request.method == "POST":
        if connection_status(account.pk)["status"] != "connected":
            return JsonResponse({"error": "Connect Schwab first."}, status=400)

        with (private_directory() / f"sync-{account.pk}.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return JsonResponse({"error": "Schwab sync is already running."}, status=409)

            state = state_for(account.pk)

            if state.get("last_attempt") and timezone.now() - datetime.fromisoformat(
                state["last_attempt"]
            ) < timedelta(seconds=60):
                return JsonResponse({"error": "Wait one minute before syncing again."}, status=429)

            state.update(requested=True, status="queued", message="Sync queued…")
            write_private(private_directory() / f"sync-{account.pk}.json", state)

        from .broker_sync import start_worker

        start_worker()

    state = state_for(account.pk)

    return JsonResponse(
        {k: state.get(k) for k in ("status", "message", "last_success", "imported", "duplicates")}
    )
