"""Local brokerage account configuration and import routing."""

from django.db import transaction
from django.db.models import F
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Attachment, BrokerageAccount, Day, Execution
from .strategies import body


def serialize(account: BrokerageAccount) -> dict:
    return {
        "id": account.pk,
        "name": account.name,
        "broker_locked": Execution.objects.filter(account=account).exists()
        or bool(account.source_identifier),
        "broker": account.broker,
        "broker_name": account.get_broker_display(),
        "source_identifier": account.source_identifier,
        "last_import_at": account.last_import_at.isoformat()
        if account.last_import_at
        else None,
    }


@require_http_methods(["GET", "POST"])
def accounts(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse(
            {
                "accounts": [
                    serialize(a) for a in BrokerageAccount.objects.order_by("pk")
                ],
                "has_unassigned": Day.objects.filter(account=None).exists()
                or Execution.objects.filter(account=None).exists()
                or Attachment.objects.filter(account=None).exists(),
            }
        )
    try:
        data = body(request)
        name = data.get("name", "")
        broker = data.get("broker")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError("Enter an account name of 1–100 characters.")
        if broker not in ("ibkr", "schwab"):
            raise ValueError("Choose Charles Schwab or Interactive Brokers.")
        with transaction.atomic():
            # Obtain SQLite's writer lock before checking the account limit.
            BrokerageAccount.objects.filter(pk=-1).update(name="")
            if BrokerageAccount.objects.count() >= 10:
                raise ValueError("You can add up to 10 brokerage accounts.")
            account = BrokerageAccount.objects.create(name=name.strip(), broker=broker)
        return JsonResponse(serialize(account), status=201)
    except (ValueError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=400)


def prepare_import(data: dict) -> tuple[list, BrokerageAccount | None]:
    from .executions import parse_csv

    identifier = data.get("account_id")
    if identifier is None:
        if BrokerageAccount.objects.exists():
            raise ValueError("Choose a brokerage account before importing.")
        return parse_csv(data["csv"]), None
    try:
        account = BrokerageAccount.objects.get(pk=identifier)
    except (BrokerageAccount.DoesNotExist, ValueError, TypeError) as error:
        raise ValueError("Choose a valid brokerage account.") from error
    from .thinkorswim import parse_statement

    rows = (
        parse_statement(data["csv"])
        if account.broker == "schwab"
        else parse_csv(data["csv"])
    )
    identifiers = {r["account"] for r in rows}
    if len(identifiers) != 1:
        raise ValueError("Upload executions for one brokerage account at a time.")
    source = identifiers.pop()
    if account.source_identifier and account.source_identifier != source:
        raise ValueError("This CSV belongs to a different brokerage account.")
    if (
        BrokerageAccount.objects.filter(broker=account.broker, source_identifier=source)
        .exclude(pk=account.pk)
        .exists()
    ):
        raise ValueError(
            "This CSV account is already linked to another account in Settings."
        )
    return rows, account


def record_import(account: BrokerageAccount | None, rows: list) -> None:
    if account is not None:
        account.source_identifier = rows[0]["account"]
        account.last_import_at = timezone.now()
        account.save(update_fields=["source_identifier", "last_import_at"])


def request_account(request: HttpRequest) -> int | None:
    """Resolve an explicit account; an omitted scope means legacy unassigned data."""
    from django.http import Http404

    identifier = request.GET.get("account_id")
    if identifier in (None, "", "unassigned"):
        return None

    if (
        not identifier.isdecimal()
        or not BrokerageAccount.objects.filter(pk=identifier).exists()
    ):
        raise Http404("Brokerage account not found.")

    return int(identifier)


def scoped_rows(rows: list, account_id: int | None) -> list:
    """Namespace new broker IDs while preserving identifiers on migrated trades."""
    from hashlib import sha256

    if account_id is None:
        return rows

    existing = {
        item.data.get("source_trade_id", item.trade_id): item
        for item in Execution.objects.filter(account_id=account_id)
    }
    result = []
    for row in rows:
        source = row["trade_id"]
        prior = existing.get(source)
        value = dict(row)
        if prior is not None:
            value["trade_id"] = prior.trade_id
            if "source_trade_id" in prior.data:
                value["source_trade_id"] = source
        else:
            value["source_trade_id"] = source
            prefix = "manual-" if source.startswith("manual-") else "account-"
            value["trade_id"] = (
                prefix + sha256(f"{account_id}:{source}".encode()).hexdigest()
            )
        result.append(value)

    return result


@require_http_methods(["PUT", "DELETE"])
def account_detail(request: HttpRequest, pk: int) -> JsonResponse:
    from django.shortcuts import get_object_or_404

    from .account_services import clear_account_data

    account = get_object_or_404(BrokerageAccount, pk=pk)
    try:
        data = body(request)
        if request.method == "DELETE":
            if data.get("confirmation") != f"DELETE_ACCOUNT_{pk}":
                raise ValueError("Confirm deletion of this account and all its data.")

            result = clear_account_data(pk)
            if result["pending_files"]:
                return JsonResponse({**result, "deleted": False})

            with transaction.atomic():
                BrokerageAccount.objects.filter(pk=pk).update(name=F("name"))
                if (
                    Execution.objects.filter(account_id=pk).exists()
                    or Day.objects.filter(account_id=pk).exists()
                    or Attachment.objects.filter(account_id=pk).exists()
                ):
                    raise ValueError(
                        "New account data was saved. Retry deleting this account."
                    )

                BrokerageAccount.objects.get(pk=pk).delete()

            return JsonResponse({**result, "deleted": True})

        name, broker = data.get("name"), data.get("broker")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError("Enter an account name of 1–100 characters.")

        if broker not in ("ibkr", "schwab"):
            raise ValueError("Choose Charles Schwab or Interactive Brokers.")

        with transaction.atomic():
            BrokerageAccount.objects.filter(pk=pk).update(name=F("name"))
            account.refresh_from_db()
            if broker != account.broker and (
                account.source_identifier
                or Execution.objects.filter(account=account).exists()
            ):
                raise ValueError(
                    "Clear this account's trading data before changing its broker."
                )

            account.name, account.broker = name.strip(), broker
            account.save(update_fields=["name", "broker"])

        return JsonResponse(serialize(account))
    except (ValueError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=400)


@require_http_methods(["DELETE"])
def account_data(request: HttpRequest, pk: int) -> JsonResponse:
    from django.shortcuts import get_object_or_404

    from .account_services import clear_account_data

    get_object_or_404(BrokerageAccount, pk=pk)
    try:
        if body(request).get("confirmation") != f"CLEAR_ACCOUNT_{pk}":
            raise ValueError("Confirm clearing all trading data for this account.")

        return JsonResponse(clear_account_data(pk))
    except (ValueError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=400)
