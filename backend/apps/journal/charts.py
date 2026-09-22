"""On-demand minute candles with persistent caching and Basic-plan rate limits."""

import json
import math
import os
import sqlite3
import time
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


class ChartError(ValueError):
    """A safe, user-facing market data error."""


def configuration() -> tuple[str, str]:
    values = {}
    path = settings.BASE_DIR / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in (
                "TWELVE_DATA_API_KEY",
                "TRADING_TIMEZONE",
            ):
                values[name.strip()] = value.strip().strip("\"'")

    return (
        os.environ.get("TWELVE_DATA_API_KEY", values.get("TWELVE_DATA_API_KEY", "")),
        os.environ.get(
            "TRADING_TIMEZONE", values.get("TRADING_TIMEZONE", "America/Los_Angeles")
        ),
    )


def execution_timestamp(value: str, zone: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(zone))

    return int(parsed.timestamp())


def parse_candles(payload: dict) -> list[dict]:
    candles = {}
    for row in payload.get("values", []):
        stamp = datetime.fromisoformat(row["datetime"]).replace(tzinfo=UTC)
        candle = {"time": int(stamp.timestamp())}
        for field in ("open", "high", "low", "close"):
            value = float(row[field])
            if not math.isfinite(value) or value < 0:
                raise ChartError("The provider returned invalid candle prices.")
            candle[field] = value
        if not (
            candle["low"]
            <= min(candle["open"], candle["close"])
            <= max(candle["open"], candle["close"])
            <= candle["high"]
        ):
            raise ChartError("The provider returned inconsistent candle prices.")
        candles[candle["time"]] = candle

    return sorted(candles.values(), key=lambda candle: candle["time"])


def candles_for_day(symbol: str, currency: str, day: str, zone: str) -> list[dict]:
    key, _ = configuration()
    if not key:
        raise ChartError("Add TWELVE_DATA_API_KEY to backend/.env to load charts.")
    start = datetime.combine(
        date.fromisoformat(day), datetime.min.time(), ZoneInfo(zone)
    )
    end = start + timedelta(days=1) - timedelta(seconds=1)
    now = time.time()
    cache_key = sha256(f"{symbol}|{currency}|{day}|{zone}|1min".encode()).hexdigest()
    database = sqlite3.connect(settings.BASE_DIR / "chart_cache.sqlite3", timeout=25)
    try:
        database.execute(
            "CREATE TABLE IF NOT EXISTS candles (key TEXT PRIMARY KEY, expires REAL, value TEXT)"
        )
        database.execute("CREATE TABLE IF NOT EXISTS requests (time REAL)")
        # Serialize requests across PyCharm and desktop server processes as well.
        database.execute("BEGIN IMMEDIATE")
        row = database.execute(
            "SELECT expires, value FROM candles WHERE key=?", (cache_key,)
        ).fetchone()
        if row and row[0] > now:
            return json.loads(row[1])
        database.execute("DELETE FROM requests WHERE time < ?", (now - 86400,))
        recent = database.execute(
            "SELECT COUNT(*) FROM requests WHERE time > ?", (now - 60,)
        ).fetchone()[0]
        daily = database.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        if recent >= 8 or daily >= 800:
            raise ChartError("Chart request limit reached. Please try again later.")
        database.execute("INSERT INTO requests VALUES (?)", (now,))
        params = {
            "symbol": symbol,
            "interval": "1min",
            "timezone": "UTC",
            "start_date": start.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "outputsize": 5000,
            "order": "ASC",
            "apikey": key,
        }
        try:
            with urlopen(
                "https://api.twelvedata.com/time_series?" + urlencode(params),
                timeout=15,
            ) as response:
                payload = json.load(response)
        except HTTPError as error:
            if error.code == 429:
                raise ChartError(
                    "Twelve Data rate limit reached. Please try again later."
                ) from None
            raise ChartError(
                "Twelve Data could not provide these candles. Check your key and plan access."
            ) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ChartError("Could not reach Twelve Data. Please try again.") from None
        if not isinstance(payload, dict):
            raise ChartError("The provider returned invalid candle data.")
        if payload.get("status") == "error":
            code = payload.get("code")
            messages = {
                401: "Twelve Data rejected the API key.",
                403: "These candles are not available with your Twelve Data access.",
                429: "Twelve Data rate limit reached. Please try again later.",
            }
            raise ChartError(
                messages.get(
                    code, "No candle data is available for this symbol and date."
                )
            )
        meta = payload.get("meta", {})
        if (
            meta.get("symbol", "").upper() != symbol.upper()
            or meta.get("currency") != currency
        ):
            raise ChartError(
                "The returned instrument or currency does not match this trade."
            )
        try:
            candles = parse_candles(payload)
        except (KeyError, TypeError, ValueError):
            raise ChartError("The provider returned invalid candle data.") from None
        candles = [
            c for c in candles if start.timestamp() <= c["time"] <= end.timestamp()
        ]
        # Cache settled sessions for a month, recent/empty sessions briefly.
        ttl = 2592000 if candles and end.timestamp() < now - 86400 else 300
        database.execute(
            "INSERT OR REPLACE INTO candles VALUES (?, ?, ?)",
            (cache_key, now + ttl, json.dumps(candles)),
        )

        return candles
    finally:
        database.commit()
        database.close()


@require_GET
def trade_chart(request: HttpRequest, key: str) -> JsonResponse:
    from .models import Execution
    from .views import trade_by_key

    trade = trade_by_key(key)
    _, zone = configuration()
    try:
        ZoneInfo(zone)
        rows = list(
            Execution.objects.filter(trade_id__in=trade["execution_ids"]).order_by(
                "execution_time", "pk"
            )
        )
        days = sorted({row.execution_time[:10] for row in rows})
        selected = request.GET.get("date", days[0] if days else "")
        if selected not in days:
            raise ChartError("Choose a date with executions for this trade.")
        markers = []
        for row in rows:
            if row.execution_time[:10] != selected:
                continue
            fill = row.data
            entry = (fill["side"] == "BUY") == (trade["direction"] == "Long")
            markers.append(
                {
                    "id": row.trade_id,
                    "time": execution_timestamp(row.execution_time, zone),
                    "side": fill["side"],
                    "kind": "Entry" if entry else "Exit",
                    "quantity": fill["quantity"],
                    "price": fill["price"],
                }
            )
        data = {
            "symbol": trade["symbol"],
            "dates": days,
            "date": selected,
            "timezone": zone,
            "markers": markers,
            "candles": [],
        }
        if trade["asset_class"] == "OPT":
            data["option_error"] = (
                "Historical option-contract candles are not available from the configured data source."
            )
        try:
            data["candles"] = candles_for_day(
                trade["symbol"], trade["currency"], selected, zone
            )
            if not data["candles"]:
                data["error"] = "No candles are available for this trading session."
        except ChartError as error:
            data["error"] = str(error)

        return JsonResponse(data)
    except (ValueError, KeyError, sqlite3.Error):
        return JsonResponse(
            {
                "error": "Unable to load this chart. Check the date and TRADING_TIMEZONE setting."
            },
            status=400,
        )
