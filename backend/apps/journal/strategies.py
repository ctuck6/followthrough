"""Strategy templates, trade checklists, and realized performance."""

import json
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from .executions import ledger
from .models import Strategy, TradeStrategy


def serialize(strategy: Strategy) -> dict:
    return {"id": strategy.pk, "name": strategy.name, "criteria": strategy.criteria}


def validate_create(data: dict) -> dict:
    name, criteria = data.get("name"), data.get("criteria")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Enter a strategy name of 1–100 characters.")
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 50:
        raise ValueError("Add between 1 and 50 criteria.")
    if any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 500 for t in criteria):
        raise ValueError("Each criterion must contain 1–500 characters.")

    return {
        "name": name.strip(),
        "criteria": [{"id": uuid4().hex, "text": text.strip()} for text in criteria],
    }


def strategy_stats() -> list[dict]:
    assignments = dict(TradeStrategy.objects.values_list("trade_key", "strategy_id"))
    results = {
        s.pk: {**serialize(s), "currencies": {}}
        for s in Strategy.objects.all().order_by("created_at", "pk")
    }
    for trade in ledger()["trades"]:
        record = results.get(assignments.get(trade["trade_id"]))
        if record is None:
            continue
        summary = record["currencies"].setdefault(
            trade["currency"],
            {
                "trades": 0,
                "closed": 0,
                "wins": 0,
                "losses": 0,
                "net": Decimal(0),
                "win_total": Decimal(0),
                "loss_total": Decimal(0),
            },
        )
        summary["trades"] += 1
        if trade["is_open"] or trade["net"] is None:
            continue
        value = Decimal(trade["net"])
        summary["closed"] += 1
        summary["net"] += value
        if value > 0:
            summary["wins"] += 1
            summary["win_total"] += value
        elif value < 0:
            summary["losses"] += 1
            summary["loss_total"] += value
    for record in results.values():
        for summary in record["currencies"].values():
            win_total, loss_total = summary.pop("win_total"), summary.pop("loss_total")
            summary["average_winner"] = (
                str(win_total / summary["wins"]) if summary["wins"] else None
            )
            summary["average_loser"] = (
                str(loss_total / summary["losses"]) if summary["losses"] else None
            )
            summary["expectancy"] = (
                str(summary["net"] / summary["closed"]) if summary["closed"] else None
            )
            summary["win_rate"] = (
                round(100 * summary["wins"] / summary["closed"], 1) if summary["closed"] else None
            )
            summary["net"] = str(summary["net"])

    return list(results.values())


def body(request: HttpRequest) -> dict:
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise TypeError("Expected an object.")

    return data


@require_http_methods(["GET", "POST"])
def strategies(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse({"strategies": strategy_stats()})
    try:
        strategy = Strategy.objects.create(**validate_create(body(request)))

        return JsonResponse({**serialize(strategy), "currencies": {}}, status=201)
    except (ValueError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=400)


@require_http_methods(["GET", "PUT"])
def trade_strategy(request: HttpRequest, key: str) -> JsonResponse:
    from .views import trade_by_key

    trade_by_key(key)
    if request.method == "GET":
        assignment = TradeStrategy.objects.filter(pk=key).first()

        return JsonResponse(
            {
                "strategies": [serialize(s) for s in Strategy.objects.all().order_by("name", "pk")],
                "strategy_id": assignment.strategy_id if assignment else None,
                "checked": assignment.checked if assignment else [],
            }
        )
    try:
        data = body(request)
        strategy_id, checked = data.get("strategy_id"), data.get("checked", [])
        if not isinstance(checked, list) or any(not isinstance(v, str) for v in checked):
            raise ValueError("Invalid criteria selection.")
        with transaction.atomic():
            if strategy_id is None:
                if checked:
                    raise ValueError("Choose a strategy before checking criteria.")
                TradeStrategy.objects.filter(pk=key).delete()
            else:
                if type(strategy_id) is not int:
                    raise ValueError("Invalid strategy.")
                strategy = Strategy.objects.get(pk=strategy_id)
                if not set(checked) <= {c["id"] for c in strategy.criteria}:
                    raise ValueError("Some criteria do not belong to this strategy.")
                checked = list(dict.fromkeys(checked))
                TradeStrategy.objects.update_or_create(
                    trade_key=key,
                    defaults={"strategy": strategy, "checked": checked},
                )

        return JsonResponse({"strategy_id": strategy_id, "checked": checked})
    except (ValueError, TypeError, Strategy.DoesNotExist) as error:
        return JsonResponse({"error": str(error) or "Strategy not found."}, status=400)


@require_http_methods(["PUT", "DELETE"])
def strategy_detail(request: HttpRequest, pk: int) -> JsonResponse:
    from django.shortcuts import get_object_or_404

    with transaction.atomic():
        strategy = get_object_or_404(Strategy.objects.select_for_update(), pk=pk)
        if request.method == "DELETE":
            strategy.delete()

            return JsonResponse({"deleted": pk})
        try:
            data = body(request)
            criteria = data.get("criteria")
            if not isinstance(criteria, list) or any(not isinstance(c, dict) for c in criteria):
                raise ValueError("Invalid criteria.")
            validated = validate_create(
                {"name": data.get("name"), "criteria": [c.get("text") for c in criteria]}
            )
            previous = {c["id"]: c["text"] for c in strategy.criteria}
            seen = set()
            for source, target in zip(criteria, validated["criteria"], strict=True):
                identifier = source.get("id")
                if identifier is not None:
                    if (
                        not isinstance(identifier, str)
                        or identifier not in previous
                        or identifier in seen
                    ):
                        raise ValueError("Invalid criterion identifier.")
                    seen.add(identifier)
                    # Changed requirements must be reassessed on linked trades.
                    if previous[identifier] == target["text"]:
                        target["id"] = identifier
            strategy.name = validated["name"]
            strategy.criteria = validated["criteria"]
            strategy.save(update_fields=["name", "criteria"])
            valid_ids = {c["id"] for c in strategy.criteria}
            for assignment in TradeStrategy.objects.filter(strategy=strategy):
                assignment.checked = [c for c in assignment.checked if c in valid_ids]
                assignment.save(update_fields=["checked"])

            return JsonResponse(serialize(strategy))
        except (ValueError, TypeError) as error:
            return JsonResponse({"error": str(error)}, status=400)
