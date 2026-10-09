"""Persistent local Flex sync scheduling with a cross-process execution lease."""

import logging
import threading
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.db import close_old_connections, transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .accounts import request_account, scoped_rows
from .flex_import import reconcile_flex
from .ibkr_flex import FlexError, activity_query_id, credentials, download_report, parse_report
from .models import BrokerageAccount, BrokerSync

PACIFIC = ZoneInfo("America/Los_Angeles")
_started = False
_start_lock = threading.Lock()


def resolve_account(state: BrokerSync, rows: list[dict]) -> BrokerageAccount:
    identifiers = {row["account"] for row in rows}

    if len(identifiers) > 1:
        raise FlexError("Configure the Flex query for one IBKR account only.")

    accounts = BrokerageAccount.objects.filter(broker="ibkr")
    source = next(iter(identifiers), None)
    account = accounts.filter(pk=state.account_id).first() if state.account_id else None

    if account is None and source:
        account = accounts.filter(source_identifier=source).first()

    if account is None and accounts.count() == 1:
        account = accounts.first()

    if account is None:
        raise FlexError("Select an IBKR account and click Sync now to link this query.")

    if source and account.source_identifier and account.source_identifier != source:
        raise FlexError("This Flex report belongs to a different brokerage account.")

    if source and accounts.filter(source_identifier=source).exclude(pk=account.pk).exists():
        raise FlexError("This Flex report is already linked to another account.")

    return account


def is_due(state: BrokerSync, now: datetime, startup: bool = False) -> bool:
    if state.lease_until and state.lease_until > now:
        return False

    if state.status == "running" or state.requested:
        return True

    local = now.astimezone(PACIFIC)
    scheduled = local.weekday() < 5 and (local.hour, local.minute) >= (13, 15)

    if scheduled and state.scheduled_day != local.date():
        return True

    if state.retry_at and state.retry_at <= now:
        return True

    return startup and (
        state.last_attempt is None or now - state.last_attempt >= timedelta(minutes=10)
    )


def run_sync(startup: bool = False) -> None:
    if not all(credentials()):
        return

    now = timezone.now()
    run_id = uuid4().hex

    with transaction.atomic():
        # Obtain SQLite's writer lock before reading the singleton state.
        BrokerageAccount.objects.filter(pk=-1).update(name="")
        state, _ = BrokerSync.objects.get_or_create(pk=1)

        if not is_due(state, now, startup):
            return

        local = now.astimezone(PACIFIC)

        if local.weekday() < 5 and (local.hour, local.minute) >= (13, 15):
            state.scheduled_day = local.date()

        intended_account = state.account_id
        state.run_id = run_id
        state.lease_until = now + timedelta(minutes=10)
        state.last_attempt = now
        state.status = "running"
        state.message = "Fetching IBKR report…"
        state.requested = False
        state.retry_at = None
        state.save()

    try:
        # Each report uses its own configured period (Today vs historical).
        rows = parse_report(download_report())
        historical_query = activity_query_id()

        if historical_query:
            if historical_query == credentials()[1]:
                raise FlexError("Activity and Trade Confirmation Query IDs must differ.")

            historical = parse_report(download_report(query_id=historical_query))
            # Trial scope: today plus the last five reported trading sessions.
            dates = sorted(
                {
                    r["session_date"]
                    for r in historical
                    if r["session_date"] < local.date().isoformat()
                }
            )[-5:]
            rows = [r for r in rows if r["session_date"] == local.date().isoformat()]
            rows.extend(r for r in historical if r["session_date"] in dates)

        with transaction.atomic():
            BrokerageAccount.objects.filter(pk=-1).update(name="")
            state = BrokerSync.objects.get(pk=1)

            if state.run_id != run_id:
                return

            if intended_account and state.account_id != intended_account:
                raise FlexError("The linked account changed during sync. Please retry.")

            account = resolve_account(state, rows)
            result = reconcile_flex(scoped_rows(rows, account.pk), account.pk)

            if rows:
                account.source_identifier = rows[0]["account"]

            if result["imported"] > 0 or result["updated"] > 0:
                account.last_import_at = timezone.now()

            account.save(update_fields=["source_identifier", "last_import_at"])
            state.account = account
            state.status = "success"
            state.conflicts = result["conflicts"]
            state.message = (
                f"Sync finished with {len(state.conflicts)} executions needing review."
                if state.conflicts
                else "Sync complete."
                if rows
                else "Report contains no executions."
            )
            state.last_success = timezone.now()
            state.last_report_date = max((r["session_date"] for r in rows), default=None)
            state.imported = result["imported"]
            state.duplicates = result["duplicates"]
            state.failures = 0
            state.lease_until = None
            state.save()
    except Exception as error:  # noqa: BLE001 — redact credentials at boundary
        # Never persist raw network exceptions, URLs, report contents or credentials.
        message = (
            str(error)
            if isinstance(error, FlexError)
            else (
                "Sync could not import the report. Existing TradeIDs may have changed; "
                "review the CSV before reconciling. No partial import was saved."
            )
        )

        with transaction.atomic():
            state = BrokerSync.objects.get(pk=1)

            if state.run_id != run_id:
                return

            state.status = "error"
            state.message = message[:500]
            state.failures += 1
            state.lease_until = None
            state.retry_at = (
                timezone.now() + timedelta(minutes=15 * state.failures)
                if state.failures <= 3
                and not (isinstance(error, FlexError) and error.code in {"1012", "1015"})
                else None
            )
            state.save()


def worker() -> None:
    startup = True
    pause = threading.Event()

    while True:
        try:
            close_old_connections()
            run_sync(startup=startup)
            from .schwab_sync import run_all

            run_all(startup=startup)
            startup = False
        except Exception:  # noqa: BLE001 — keep scheduler alive without logging secrets
            logging.getLogger(__name__).warning("IBKR sync scheduler unavailable; retrying.")
        finally:
            close_old_connections()

        pause.wait(15)


def start_worker() -> None:
    global _started

    with _start_lock:
        if _started:
            return

        _started = True
        threading.Thread(target=worker, name="ibkr-flex-sync", daemon=True).start()


@require_http_methods(["GET", "POST"])
def sync_status(request: HttpRequest) -> JsonResponse:
    account_id = request_account(request)
    account = BrokerageAccount.objects.filter(pk=account_id, broker="ibkr").first()
    configured = all(credentials())

    if request.method == "POST":
        if account is None or not configured:
            return JsonResponse(
                {"error": "Select an IBKR account with Flex credentials configured."},
                status=400,
            )

        with transaction.atomic():
            BrokerageAccount.objects.filter(pk=-1).update(name="")
            state, _ = BrokerSync.objects.get_or_create(pk=1)

            if state.account_id and state.account_id != account.pk:
                return JsonResponse(
                    {"error": "The configured Flex query is linked to another account."},
                    status=400,
                )

            if state.lease_until and state.lease_until > timezone.now():
                return JsonResponse({"error": "An IBKR sync is already running."}, status=409)

            if state.last_attempt and timezone.now() - state.last_attempt < timedelta(seconds=60):
                return JsonResponse(
                    {"error": "Wait one minute before requesting another sync."},
                    status=429,
                )

            state.account = account
            state.requested = True
            state.status = "queued"
            state.message = "Sync queued…"
            state.failures = 0
            state.save()

        start_worker()

    state = BrokerSync.objects.filter(pk=1).first()
    belongs = state is not None and state.account_id in (None, account_id)

    return JsonResponse(
        {
            "configured": configured,
            "available": account is not None
            and (state is None or state.account_id in (None, account_id)),
            "status": state.status if belongs else "idle",
            "message": state.message if belongs else "",
            "last_success": state.last_success.isoformat()
            if belongs and state.last_success
            else None,
            "last_report_date": str(state.last_report_date)
            if belongs and state.last_report_date
            else None,
            "imported": state.imported if belongs else 0,
            "duplicates": state.duplicates if belongs else 0,
            "conflicts": state.conflicts if belongs else [],
        },
        status=202 if request.method == "POST" else 200,
    )
