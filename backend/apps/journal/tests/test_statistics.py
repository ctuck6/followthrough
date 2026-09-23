from unittest.mock import patch

from django.test import TestCase

from apps.journal.models import Strategy, TradeStrategy


class StatisticsTests(TestCase):
    @patch("apps.journal.statistics.configuration", return_value=("", "America/Los_Angeles"))
    @patch("apps.journal.statistics.ledger")
    def test_closed_range_strategy_and_market_hours(
        self, mock_ledger: object, config: object
    ) -> None:
        strategy = Strategy.objects.create(name="Breakout")
        TradeStrategy.objects.create(trade_key="1", strategy=strategy)
        base = {
            "trade_id": "1",
            "is_open": False,
            "net": "-12.50",
            "close_time": "2026-09-22 10:00:00",
            "order_time": "2026-09-21 06:30:00",
            "currency": "USD",
            "symbol": "AMD",
            "asset_class": "OPT",
        }
        mock_ledger.return_value = {
            "trades": [
                base,
                {**base, "is_open": True},
                {**base, "net": None},
                {**base, "close_time": "2026-09-20 10:00:00"},
                {
                    **base,
                    "trade_id": "2",
                    "order_time": "2026-09-22 05:00:00",
                    "asset_class": "STK",
                },
            ]
        }
        response = self.client.get("/api/statistics/?start=2026-09-22&end=2026-09-22")
        self.assertEqual(response.status_code, 200)
        rows = response.json()["rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["hour"], "9")
        self.assertEqual(rows[0]["strategy"], "Breakout")
        self.assertEqual(rows[0]["instrument"], "Options")
        self.assertEqual(rows[0]["net"], "-12.50")
        self.assertEqual(rows[1]["hour"], "outside")
        self.assertEqual(rows[1]["strategy"], "No strategy")

    def test_invalid_range(self) -> None:
        self.assertEqual(self.client.get("/api/statistics/?start=bad&end=bad").status_code, 400)
        self.assertEqual(
            self.client.get("/api/statistics/?start=2026-09-22&end=2026-09-01").status_code, 400
        )
