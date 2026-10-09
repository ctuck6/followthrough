import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.journal.models import BrokerageAccount, Execution
from apps.journal.schwab_connection import private_directory, write_private
from apps.journal.schwab_sync import SyncError, parse_transactions, run_account, state_for


def trade(activity=1, amount=2, symbol="ABC", asset="EQUITY", price=10, fees=1):
    multiplier = 100 if asset == "OPTION" else 1
    return {
        "activityId": activity,
        "type": "TRADE",
        "status": "VALID",
        "time": "2026-10-09T14:00:00Z",
        "orderId": 100,
        "netAmount": -amount * price * multiplier - fees,
        "transferItems": [
            {
                "instrument": {"assetType": asset, "symbol": symbol},
                "amount": amount,
                "price": price,
                "positionEffect": "OPENING",
            },
            {
                "instrument": {"assetType": "CURRENCY", "symbol": "CURRENCY_USD"},
                "cost": fees,
                "feeType": "COMMISSION",
            },
        ],
    }


class SchwabSyncTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(BASE_DIR=Path(directory.name))
        settings.enable()
        self.addCleanup(settings.disable)
        self.account = BrokerageAccount.objects.create(name="Schwab", broker="schwab")
        root = private_directory()
        write_private(root / f"token-{self.account.pk}.json", {})
        write_private(root / f"status-{self.account.pk}.json", {"status": "connected"})

    def test_stock_option_and_cash_validation(self):
        with patch("apps.journal.schwab_sync.flex_setting", return_value="America/Los_Angeles"):
            row = parse_transactions([trade()], "schwab:test")[0]
            self.assertEqual(row["execution_time"], "2026-10-09 07:00:00")
            self.assertEqual(row["commission"], "-1")
            option = parse_transactions(
                [trade(symbol="ABC   261016C00100000", asset="OPTION")], "schwab:test"
            )[0]
            self.assertEqual(option["expiry"], "2026-10-16")
            self.assertEqual(Decimal(option["strike"]), 100)
            self.assertEqual(Decimal(option["multiplier"]), 100)
            bad = trade()
            bad["netAmount"] = 999
            with self.assertRaises(SyncError):
                parse_transactions([bad], "schwab:test")

    @patch("schwab.auth.client_from_access_functions")
    def test_empty_then_new_then_duplicate(self, factory):
        client = MagicMock()
        factory.return_value = client
        client.get_account_numbers.return_value.status_code = 200
        client.get_account_numbers.return_value.json.return_value = [
            {"accountNumber": "test", "hashValue": "private"}
        ]
        client.get_transactions.return_value.status_code = 200
        client.get_transactions.return_value.json.return_value = []
        run_account(self.account, startup=True)
        self.account.refresh_from_db()
        self.assertEqual(state_for(self.account.pk)["status"], "success")
        self.assertIsNone(self.account.last_import_at)
        for expected in (1, 0):
            state = state_for(self.account.pk)
            state["requested"] = True
            write_private(private_directory() / f"sync-{self.account.pk}.json", state)
            client.get_transactions.return_value.json.return_value = [trade()]
            run_account(self.account)
            self.assertEqual(state_for(self.account.pk)["imported"], expected)
        self.assertEqual(Execution.objects.count(), 1)

    @patch("schwab.auth.client_from_access_functions", side_effect=RuntimeError("secret"))
    def test_error_is_redacted(self, factory):
        run_account(self.account, startup=True)
        state = state_for(self.account.pk)
        self.assertEqual(state["status"], "error")
        self.assertNotIn("secret", state["message"])
        self.assertEqual(Execution.objects.count(), 0)
