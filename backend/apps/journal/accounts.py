"""Local brokerage account configuration and import routing."""

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import BrokerageAccount
from .strategies import body


def serialize(account: BrokerageAccount) -> dict:
    return {
        "id": account.pk,
        "name": account.name,
        "broker": account.broker,
        "broker_name": account.get_broker_display(),
        "source_identifier": account.source_identifier,
        "last_import_at": account.last_import_at.isoformat() if account.last_import_at else None,
    }


@require_http_methods(["GET", "POST"])
def accounts(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse(
            {"accounts": [serialize(a) for a in BrokerageAccount.objects.order_by("pk")]}
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

    rows = parse_statement(data["csv"]) if account.broker == "schwab" else parse_csv(data["csv"])
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
        raise ValueError("This CSV account is already linked to another account in Settings.")
    return rows, account


def record_import(account: BrokerageAccount | None, rows: list) -> None:
    if account is not None:
        account.source_identifier = rows[0]["account"]
        account.last_import_at = timezone.now()
        account.save(update_fields=["source_identifier", "last_import_at"])
