"""Account lifecycle operations must never clear another account's journal."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings

from apps.journal.account_services import transfer_unassigned
from apps.journal.accounts import scoped_rows
from apps.journal.executions import import_rows, ledger, normalize
from apps.journal.models import (
    Attachment,
    BrokerageAccount,
    Day,
    Execution,
    PendingFileDeletion,
    Profile,
    Rule,
    Strategy,
    TradeReview,
    TradeStrategy,
)
from apps.journal.services import save_attachment


class AccountManagementTests(TestCase):
    def setUp(self) -> None:
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.first = BrokerageAccount.objects.create(name="First", broker="ibkr")
        self.second = BrokerageAccount.objects.create(name="Second", broker="ibkr")
        Rule.objects.create(text="Risk rule")
        Profile.objects.create(display_name="Trader")
        self.strategy = Strategy.objects.create(name="Breakout", criteria=[])
        self.keys = {}
        self.files = {}
        for account in [self.first, self.second]:
            row = normalize(
                {
                    "TradeID": "opening",
                    "AccountAlias": account.name,
                    "CurrencyPrimary": "USD",
                    "AssetClass": "STK",
                    "Symbol": "ABC",
                    "Buy/Sell": "BUY",
                    "Quantity": "2",
                    "Price": "10",
                    "OrderTime": "2026-09-24 09:30:00",
                }
            )
            import_rows(scoped_rows([row], account.pk), account.pk)
            key = ledger(account.pk)["trades"][0]["trade_id"]
            self.keys[account.pk] = key
            TradeReview.objects.create(trade_key=key, notes=account.name)
            TradeStrategy.objects.create(trade_key=key, strategy=self.strategy)
            attachment = save_attachment(
                "2026-09-24", SimpleUploadedFile("chart.txt", b"chart"), key, account.pk
            )
            self.files[account.pk] = Path(attachment.file.path)
            save_attachment(
                "2026-09-24",
                SimpleUploadedFile("session.txt", b"session"),
                account_id=account.pk,
            )

    def action(self, kind: str, account: BrokerageAccount) -> HttpResponse:
        return self.client.delete(
            f"/api/accounts/{account.pk}/{'' if kind == 'DELETE' else 'data/'}",
            {"confirmation": f"{kind}_ACCOUNT_{account.pk}"},
            content_type="application/json",
        )

    def test_clear_is_account_scoped_and_preserves_configuration(self) -> None:
        result = self.action("CLEAR", self.first)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"cleared": True, "pending_files": 0})
        for model in [Day, Execution, Attachment]:
            self.assertFalse(model.objects.filter(account=self.first).exists())
            self.assertTrue(model.objects.filter(account=self.second).exists())
        for model in [TradeReview, TradeStrategy]:
            self.assertFalse(model.objects.filter(pk=self.keys[self.first.pk]).exists())
            self.assertTrue(model.objects.filter(pk=self.keys[self.second.pk]).exists())
        self.assertFalse(self.files[self.first.pk].exists())
        self.assertTrue(self.files[self.second.pk].exists())
        self.assertEqual(BrokerageAccount.objects.count(), 2)
        self.assertEqual(Profile.objects.count(), 1)
        self.assertEqual(Rule.objects.count(), 1)
        self.assertEqual(Strategy.objects.count(), 1)

    def test_delete_waits_for_failed_file_cleanup_and_can_retry(self) -> None:
        storage = Attachment._meta.get_field("file").storage
        with patch.object(storage, "delete", side_effect=OSError("Unavailable")):
            result = self.action("DELETE", self.first).json()
        self.assertFalse(result["deleted"])
        self.assertEqual(result["pending_files"], 2)
        self.assertTrue(BrokerageAccount.objects.filter(pk=self.first.pk).exists())
        result = self.action("DELETE", self.first).json()
        self.assertTrue(result["deleted"])
        self.assertFalse(BrokerageAccount.objects.filter(pk=self.first.pk).exists())
        self.assertFalse(PendingFileDeletion.objects.exists())
        self.assertTrue(self.files[self.second.pk].exists())
        self.assertTrue(Execution.objects.filter(account=self.second).exists())

    def test_edit_confirmation_csrf_and_retired_global_endpoint(self) -> None:
        url = f"/api/accounts/{self.first.pk}/"
        changed = self.client.put(
            url, {"name": "Renamed", "broker": "ibkr"}, content_type="application/json"
        )
        self.assertEqual(changed.json()["name"], "Renamed")
        self.assertTrue(changed.json()["broker_locked"])
        self.assertEqual(
            self.client.put(
                url,
                {"name": "Renamed", "broker": "schwab"},
                content_type="application/json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.delete(url, {}, content_type="application/json").status_code,
            400,
        )
        self.assertEqual(
            self.client.delete(
                f"{url}data/",
                {"confirmation": f"CLEAR_ACCOUNT_{self.second.pk}"},
                content_type="application/json",
            ).status_code,
            400,
        )
        self.assertEqual(
            Client(enforce_csrf_checks=True)
            .delete(
                url,
                {"confirmation": f"DELETE_ACCOUNT_{self.first.pk}"},
                content_type="application/json",
            )
            .status_code,
            403,
        )
        self.assertEqual(self.client.delete("/api/trading-data/").status_code, 404)

    def test_transfer_preserves_trade_ids_pnl_notes_links_and_files(self) -> None:
        key = self.keys[self.first.pk]
        expected = ledger(self.first.pk)["summaries"]
        for model in [Day, Execution, Attachment]:
            model.objects.filter(account=self.first).update(account=None)
        counts = transfer_unassigned(self.first.pk)
        self.assertEqual(
            counts, {"days": 1, "executions": 1, "attachments": 2, "trades": 1}
        )
        self.assertEqual(ledger(self.first.pk)["summaries"], expected)
        self.assertEqual(ledger(self.first.pk)["trades"][0]["trade_id"], key)
        self.assertEqual(TradeReview.objects.get(pk=key).notes, "First")
        self.assertEqual(
            TradeStrategy.objects.get(pk=key).strategy_id, self.strategy.pk
        )
        self.assertTrue(self.files[self.first.pk].exists())
        self.assertEqual(Execution.objects.filter(account=self.second).count(), 1)

    def test_transfer_refuses_conflicting_destination_without_mutations(self) -> None:
        Day.objects.create(date="2026-09-24", plan="Original legacy plan")
        with self.assertRaises(ValueError):
            transfer_unassigned(self.first.pk)
        self.assertEqual(Day.objects.get(account=None).plan, "Original legacy plan")
