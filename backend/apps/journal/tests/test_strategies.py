from unittest.mock import patch

from django.test import TestCase

from apps.journal.models import Strategy, TradeStrategy
from apps.journal.strategies import strategy_stats


class StrategyTests(TestCase):
    def test_create_validation_and_criteria_ids(self) -> None:
        response = self.client.post(
            "/api/strategies/",
            {"name": " Breakout ", "criteria": [" Volume ", "Retest"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        strategy = response.json()
        self.assertEqual(strategy["name"], "Breakout")
        self.assertEqual(strategy["criteria"][0]["text"], "Volume")
        self.assertNotEqual(strategy["criteria"][0]["id"], strategy["criteria"][1]["id"])
        for criteria in ([], [""], "wrong"):
            response = self.client.post(
                "/api/strategies/",
                {"name": "Bad", "criteria": criteria},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Strategy.objects.count(), 1)

    @patch("apps.journal.views.trade_by_key", return_value={})
    def test_assignment_roundtrip_validation_and_unlink(self, lookup: object) -> None:
        strategy = Strategy.objects.create(
            name="Breakout", criteria=[{"id": "volume", "text": "Volume"}]
        )
        url = "/api/trades/example/strategy/"
        payload = {"strategy_id": strategy.pk, "checked": ["volume"]}
        self.assertEqual(
            self.client.put(url, payload, content_type="application/json").status_code, 200
        )
        self.assertEqual(self.client.get(url).json()["checked"], ["volume"])
        payload["checked"] = ["foreign"]
        self.assertEqual(
            self.client.put(url, payload, content_type="application/json").status_code, 400
        )
        self.assertEqual(TradeStrategy.objects.get().checked, ["volume"])
        self.assertEqual(
            self.client.put(
                url, {"strategy_id": None}, content_type="application/json"
            ).status_code,
            200,
        )
        self.assertFalse(TradeStrategy.objects.exists())

    @patch("apps.journal.strategies.ledger")
    def test_closed_performance_and_currency_separation(self, mock_ledger: object) -> None:
        strategy = Strategy.objects.create(name="Test")
        trades = []
        for i, (currency, net, is_open) in enumerate(
            [
                ("USD", "20", False),
                ("USD", "-10", False),
                ("USD", "0", False),
                ("USD", "900", True),
                ("USD", None, False),
                ("CAD", "100", False),
            ]
        ):
            key = str(i)
            TradeStrategy.objects.create(trade_key=key, strategy=strategy)
            trades.append({"trade_id": key, "currency": currency, "net": net, "is_open": is_open})
        mock_ledger.return_value = {"trades": trades}
        result = strategy_stats()[0]["currencies"]
        self.assertEqual(result["USD"]["trades"], 5)
        self.assertEqual(result["USD"]["closed"], 3)
        self.assertEqual(result["USD"]["net"], "10")
        self.assertEqual(result["USD"]["win_rate"], 33.3)
        self.assertEqual(result["USD"]["average_loser"], "-10")
        self.assertEqual(result["CAD"]["net"], "100")

    def test_edit_preserves_unchanged_checks_and_resets_changed_criteria(self) -> None:
        strategy = Strategy.objects.create(
            name="Old",
            criteria=[
                {"id": "a", "text": "Keep"},
                {"id": "b", "text": "Change"},
                {"id": "c", "text": "Remove"},
            ],
        )
        assignment = TradeStrategy.objects.create(
            trade_key="trade", strategy=strategy, checked=["a", "b", "c"]
        )
        response = self.client.put(
            f"/api/strategies/{strategy.pk}/",
            {
                "name": "Updated",
                "criteria": [
                    {"id": "a", "text": "Keep"},
                    {"id": "b", "text": "New requirement"},
                    {"text": "Added"},
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.checked, ["a"])
        self.assertEqual(response.json()["name"], "Updated")
        self.assertNotEqual(response.json()["criteria"][1]["id"], "b")
        bad = self.client.put(
            f"/api/strategies/{strategy.pk}/",
            {"name": "Bad", "criteria": [{"id": "foreign", "text": "Test"}]},
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)
        strategy.refresh_from_db()
        self.assertEqual(strategy.name, "Updated")

    def test_delete_unlinks_without_removing_trade_journals(self) -> None:
        from apps.journal.models import TradeReview

        strategy = Strategy.objects.create(name="Remove")
        TradeStrategy.objects.create(trade_key="trade", strategy=strategy)
        TradeReview.objects.create(trade_key="trade", notes="Keep journal")
        response = self.client.delete(f"/api/strategies/{strategy.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Strategy.objects.exists())
        self.assertFalse(TradeStrategy.objects.exists())
        self.assertEqual(TradeReview.objects.get().notes, "Keep journal")
