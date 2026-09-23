"""Completed-trade performance reports, separated by currency."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

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
        TradeStrategy.objects.select_related("strategy").values_list("trade_key", "strategy__name")
    )
    local_zone = ZoneInfo(configuration()[1])
    rows = []
    for trade in ledger()["trades"]:
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
        minute = opened.hour * 60 + opened.minute
        hour = str(opened.hour) if 570 <= minute < 960 else "outside"
        rows.append(
            {
                "date": closed,
                "net": str(Decimal(trade["net"])),
                "currency": trade["currency"],
                "ticker": trade["symbol"],
                "instrument": "Options" if trade["asset_class"] == "OPT" else "Stocks",
                "hour": hour,
                "strategy": links.get(trade["trade_id"], "No strategy"),
            }
        )
    return JsonResponse({"rows": rows})
