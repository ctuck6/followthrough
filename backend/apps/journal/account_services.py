"""Account lifecycle operations with explicit ownership boundaries."""

from django.db import transaction
from django.db.models import F, Q

from .executions import ledger
from .models import (
    Attachment,
    BrokerageAccount,
    Day,
    Execution,
    PendingFileDeletion,
    TradeReview,
    TradeStrategy,
)


def clear_account_data(account_id: int) -> dict:
    with transaction.atomic():
        # Take SQLite's writer lock before deriving trade keys or removing records.
        BrokerageAccount.objects.filter(pk=account_id).update(last_import_at=None)
        account = BrokerageAccount.objects.get(pk=account_id)
        keys = [trade["trade_id"] for trade in ledger(account_id)["trades"]]
        attachments = Attachment.objects.filter(
            Q(account=account) | Q(trade_key__in=keys)
        )
        for name in attachments.exclude(file="").values_list("file", flat=True):
            PendingFileDeletion.objects.update_or_create(
                name=name, defaults={"account": account}
            )
        attachments.delete()
        TradeReview.objects.filter(trade_key__in=keys).delete()
        TradeStrategy.objects.filter(trade_key__in=keys).delete()
        Execution.objects.filter(account=account).delete()
        Day.objects.filter(account=account).delete()
        account.source_identifier = ""
        account.save(update_fields=["source_identifier"])

    storage = Attachment._meta.get_field("file").storage
    for item in PendingFileDeletion.objects.filter(account_id=account_id):
        try:
            storage.delete(item.name)
        except OSError:
            continue

        item.delete()

    return {
        "cleared": True,
        "pending_files": PendingFileDeletion.objects.filter(
            account_id=account_id
        ).count(),
    }


def transfer_unassigned(account_id: int) -> dict:
    """Move legacy records without changing execution IDs or journal linkage."""
    with transaction.atomic():
        BrokerageAccount.objects.filter(pk=account_id).update(name=F("name"))
        account = BrokerageAccount.objects.get(pk=account_id)
        legacy_days = Day.objects.filter(account=None)
        if Day.objects.filter(
            account=account, date__in=legacy_days.values("date")
        ).exists():
            raise ValueError("The destination already has journal data on these dates.")

        legacy = Execution.objects.filter(account=None)
        if Execution.objects.filter(account=account).exists():
            raise ValueError(
                "Transfer requires an account without existing executions."
            )

        before = ledger(None)
        keys = {trade["trade_id"] for trade in before["trades"]}
        sources = {row["account"] for row in legacy.values_list("data", flat=True)}
        if len(sources) > 1:
            raise ValueError("Legacy executions contain multiple brokerage sources.")

        source = next(iter(sources), "")
        if account.source_identifier and source and account.source_identifier != source:
            raise ValueError(
                "The destination is linked to a different brokerage source."
            )

        if (
            source
            and BrokerageAccount.objects.filter(
                broker=account.broker, source_identifier=source
            )
            .exclude(pk=account_id)
            .exists()
        ):
            raise ValueError(
                "Another account is already linked to this brokerage source."
            )

        counts = {
            "days": legacy_days.update(account=account),
            "executions": legacy.update(account=account),
            "attachments": Attachment.objects.filter(
                Q(account=None) | Q(trade_key__in=keys)
            ).update(account=account),
        }
        after = ledger(account_id)
        if (
            keys != {trade["trade_id"] for trade in after["trades"]}
            or before["summaries"] != after["summaries"]
        ):
            raise ValueError("Transfer changed trade grouping; no changes were saved.")

        account.source_identifier = source or account.source_identifier
        account.last_import_at = (
            Execution.objects.filter(account=account)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        account.save(update_fields=["source_identifier", "last_import_at"])
        counts["trades"] = len(keys)

    return counts
