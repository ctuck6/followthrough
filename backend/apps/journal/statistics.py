"""Completed-trade performance reports, separated by currency."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from .accounts import request_account
from .charts import configuration
from .executions import ledger
from .models import TradeStrategy


@require_GET
def statistics(request: HttpRequest) -> JsonResponse:
    try:
        start = date.fromisoformat(request.GET.get("start", ""))
        end = date.fromisoformat(request.GET.get("end", ""))
        if start > end:
            raise ValueError("Start date must precede end date.")
    except ValueError:
        return JsonResponse({"error": "Choose a valid date range."}, status=400)
    links = dict(
        TradeStrategy.objects.select_related("strategy").values_list(
            "trade_key", "strategy__name"
        )
    )
    local_zone = ZoneInfo(configuration()[1])
    rows = []
    for trade in ledger(request_account(request))["trades"]:
        if trade["is_open"] or trade["net"] is None or not trade["close_time"]:
            continue
        closed = trade["close_time"][:10]
        if not start.isoformat() <= closed <= end.isoformat():
            continue
        opened = (
            datetime.fromisoformat(trade["order_time"])
            .replace(tzinfo=local_zone)
            .astimezone(ZoneInfo("America/New_York"))
        )
        hour = str(opened.hour)
        rows.append(
            {
                "trade_id": trade["trade_id"],
                "date": closed,
                "net": str(Decimal(trade["net"])),
                "currency": trade["currency"],
                "ticker": trade["symbol"],
                "instrument": "Futures"
                if trade["asset_class"] == "FUT"
                else "Options"
                if trade["asset_class"] == "OPT"
                else "Stocks",
                "hour": hour,
                "entry_minute": opened.hour * 60 + opened.minute,
                "strategy": links.get(trade["trade_id"], "No strategy"),
            }
        )
    return JsonResponse({"rows": rows})
