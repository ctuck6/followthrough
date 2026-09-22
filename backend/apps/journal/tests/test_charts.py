import io
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.journal.charts import (
    ChartError,
    candles_for_day,
    execution_timestamp,
    parse_candles,
)


class ChartTests(SimpleTestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings_override = override_settings(BASE_DIR=Path(self.folder.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.config = patch(
            "apps.journal.charts.configuration",
            return_value=("test-secret", "America/Los_Angeles"),
        )
        self.config.start()
        self.addCleanup(self.config.stop)
        self.payload = {
            "meta": {"symbol": "AMD", "currency": "USD"},
            "values": [
                {
                    "datetime": "2026-01-05 17:30:00",
                    "open": "10",
                    "high": "12",
                    "low": "9",
                    "close": "11",
                },
            ],
        }

    def test_local_timestamps_follow_daylight_saving(self) -> None:
        for text, hour in [("2026-01-05 09:30:42", 17), ("2026-09-21 09:30:42", 16)]:
            stamp = execution_timestamp(text, "America/Los_Angeles")
            self.assertEqual(datetime.fromtimestamp(stamp, UTC).hour, hour)
            self.assertEqual(stamp % 60, 42)

    def test_reopening_or_another_trade_reuses_cached_candles(self) -> None:
        with patch(
            "apps.journal.charts.urlopen",
            return_value=io.BytesIO(json.dumps(self.payload).encode()),
        ) as fetch:
            first = candles_for_day("AMD", "USD", "2026-01-05", "America/Los_Angeles")
            second = candles_for_day("AMD", "USD", "2026-01-05", "America/Los_Angeles")
            self.assertEqual(first, second)
            fetch.assert_called_once()

    def test_missing_key_never_calls_provider(self) -> None:
        with (
            patch("apps.journal.charts.configuration", return_value=("", "UTC")),
            patch("apps.journal.charts.urlopen") as fetch,
        ):
            with self.assertRaisesRegex(ChartError, "API_KEY"):
                candles_for_day("AMD", "USD", "2026-01-05", "UTC")
            fetch.assert_not_called()

    def test_request_limit_includes_unsuccessful_requests(self) -> None:
        def response(*args, **kwargs):
            return io.BytesIO(b'{"status":"error","code":403}')

        with patch("apps.journal.charts.urlopen", side_effect=response) as fetch:
            for _ in range(8):
                with self.assertRaises(ChartError):
                    candles_for_day("AMD", "USD", "2026-01-05", "UTC")
            with self.assertRaisesRegex(ChartError, "request limit"):
                candles_for_day("AMD", "USD", "2026-01-05", "UTC")
            self.assertEqual(fetch.call_count, 8)

    def test_prices_must_be_finite_and_consistent(self) -> None:
        self.payload["values"][0]["high"] = "NaN"
        with self.assertRaises(ChartError):
            parse_candles(self.payload)

    def test_wrong_currency_is_not_shown(self) -> None:
        with (
            patch(
                "apps.journal.charts.urlopen",
                return_value=io.BytesIO(json.dumps(self.payload).encode()),
            ),
            self.assertRaisesRegex(ChartError, "currency"),
        ):
            candles_for_day("AMD", "CAD", "2026-01-05", "UTC")


class ChartEndpointTests(SimpleTestCase):
    def test_unknown_trade_never_calls_provider(self) -> None:
        from django.http import Http404

        with (
            patch("apps.journal.views.trade_by_key", side_effect=Http404),
            patch("apps.journal.charts.candles_for_day") as provider,
        ):
            response = self.client.get("/api/trades/missing/chart/")
            self.assertEqual(response.status_code, 404)
            provider.assert_not_called()
