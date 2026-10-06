"""Reconcile normalized Flex fills without changing trade identities."""

from django.db import transaction

from .executions import import_rows
from .models import Execution


@transaction.atomic
def reconcile_flex(rows: list[dict], account_id: int) -> dict:
    existing = {item.trade_id: item for item in Execution.objects.filter(account_id=account_id)}
    accepted = {}
    conflicts = {}
    duplicates = 0
    updated = 0

    for row in rows:
        key = row["trade_id"]
        stored = existing.get(key)
        previous = accepted.get(key) or (stored.data if stored else None)

        if previous is not None:
            differences = {
                field for field in set(previous) | set(row) if previous.get(field) != row.get(field)
            }
            # IDs and aliases do not affect FIFO, trade identity, or journal links.
            meaningful = differences - {"order_id", "account_alias"}

            if meaningful:
                conflicts[key] = {
                    "symbol": row["symbol"],
                    "date": row["session_date"],
                    "fields": sorted(meaningful),
                }
                accepted.pop(key, None)
                continue

            duplicates += 1

        if key not in conflicts:
            accepted[key] = row

    new = []

    for key, row in accepted.items():
        stored = existing.get(key)

        if stored is None:
            new.append(row)
        elif stored.data != row:
            stored.data = row
            stored.save(update_fields=["data"])
            updated += 1

    result = import_rows(new, account_id)

    return {
        **result,
        "duplicates": duplicates,
        "updated": updated,
        "conflicts": list(conflicts.values()),
    }
