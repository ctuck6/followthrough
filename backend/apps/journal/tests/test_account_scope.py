"""Account boundaries for journals, manual fills, attachments, and reports."""

from uuid import uuid4

from django.test import TestCase

from apps.journal.accounts import scoped_rows
from apps.journal.executions import import_rows, ledger, normalize
from apps.journal.models import Attachment, BrokerageAccount, Day, Execution


class AccountScopeTests(TestCase):
    def setUp(self) -> None:
        self.first = BrokerageAccount.objects.create(name="First", broker="ibkr")
        self.second = BrokerageAccount.objects.create(name="Second", broker="schwab")

    def fill(self, tid: str, side: str = "BUY", price: str = "10") -> dict:
        return normalize(
            {
                "TradeID": tid,
                "AccountAlias": "Same alias",
                "CurrencyPrimary": "USD",
                "AssetClass": "STK",
                "Symbol": "ABC",
                "Buy/Sell": side,
                "Quantity": "10",
                "Price": price,
                "Commission": "-1",
                "OrderTime": "2026-09-24 09:30:00",
            }
        )

    def test_same_day_has_independent_journals_and_attachments(self) -> None:
        for account, plan in [(self.first, "Plan A"), (self.second, "Plan B")]:
            result = self.client.put(
                f"/api/days/2026-09-24/?account_id={account.pk}",
                {"plan": plan, "checks": [], "trades": []},
                content_type="application/json",
            )
            self.assertEqual(result.status_code, 200)
            Attachment.objects.create(account=account, date="2026-09-24", name=plan)
        for account, plan in [(self.first, "Plan A"), (self.second, "Plan B")]:
            self.assertEqual(
                self.client.get(f"/api/state/?account_id={account.pk}").json()["days"][0]["plan"],
                plan,
            )
            attachments = self.client.get(
                f"/api/days/2026-09-24/attachments/?account_id={account.pk}"
            ).json()["attachments"]
            self.assertEqual([a["name"] for a in attachments], [plan])
        self.assertEqual(Day.objects.count(), 2)
        self.assertEqual(self.client.get("/api/state/?account_id=unassigned").json()["days"], [])
        self.assertEqual(self.client.get("/api/state/?account_id=99999").status_code, 404)

    def test_duplicate_ids_and_fifo_are_isolated(self) -> None:
        opening = self.fill("same-id")
        for account in [self.first, self.second]:
            self.assertEqual(
                import_rows(scoped_rows([opening], account.pk), account.pk)["imported"], 1
            )
            self.assertEqual(
                import_rows(scoped_rows([opening], account.pk), account.pk)["duplicates"], 1
            )
        import_rows(scoped_rows([self.fill("close", "SELL", "12")], self.first.pk), self.first.pk)
        self.assertEqual(Execution.objects.count(), 3)
        self.assertEqual(ledger(self.first.pk)["trades"][0]["net"], "18")
        self.assertTrue(ledger(self.second.pk)["trades"][0]["is_open"])
        self.assertEqual(len(ledger()["trades"]), 2)
        rows = self.client.get(
            f"/api/statistics/?start=2026-09-01&end=2026-09-30&account_id={self.second.pk}"
        ).json()["rows"]
        self.assertEqual(rows, [])
        key = ledger(self.first.pk)["trades"][0]["trade_id"]
        self.assertEqual(
            self.client.get(f"/api/trades/{key}/journal/?account_id={self.second.pk}").status_code,
            404,
        )
        identifier = ledger(self.first.pk)["executions"][0]["trade_id"]
        self.assertEqual(
            self.client.delete(
                f"/api/executions/delete/?account_id={self.second.pk}",
                {"ids": [identifier]},
                content_type="application/json",
            ).status_code,
            400,
        )
        self.assertEqual(Execution.objects.count(), 3)

    def test_manual_execution_uses_selected_account_and_migrated_dedupe(self) -> None:
        row = self.fill("legacy")
        import_rows([row], self.first.pk)
        self.assertEqual(
            import_rows(scoped_rows([row], self.first.pk), self.first.pk)["duplicates"], 1
        )
        response = self.client.post(
            f"/api/manual-executions/?account_id={self.second.pk}",
            {
                "id": str(uuid4()),
                "asset": "STK",
                "symbol": "XYZ",
                "side": "BUY",
                "quantity": "1",
                "price": "25",
                "commission": "1",
                "executed_at": "2026-09-24T10:00:00",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual([r["symbol"] for r in response.json()["executions"]], ["XYZ"])
        self.assertEqual(
            Execution.objects.get(account=self.second).data["account"],
            f"brokerage:{self.second.pk}",
        )

    def test_csv_preview_commit_and_repeat_keep_account_scope(self) -> None:
        csv = (
            "TradeID,AccountAlias,CurrencyPrimary,AssetClass,Symbol,Buy/Sell,"
            "Quantity,Price,OrderTime,Commission\n"
            "csv-1,Example,USD,STK,ABC,BUY,2,10,2026-09-24 09:30:00,-1\n"
        )
        url = f"/api/executions/?account_id={self.first.pk}"
        body = {"csv": csv, "account_id": self.first.pk, "preview": True}
        preview = self.client.post(url, body, content_type="application/json")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(len(preview.json()["rows"]), 1)
        self.assertEqual(Execution.objects.count(), 0)
        body.pop("preview")
        result = self.client.post(url, body, content_type="application/json")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()["imported"], 1)
        result = self.client.post(url, body, content_type="application/json")
        self.assertEqual(result.json()["duplicates"], 1)
        self.assertEqual(Execution.objects.get().account_id, self.first.pk)
        self.assertEqual(
            self.client.get(f"/api/executions/?account_id={self.second.pk}").json()["executions"],
            [],
        )
        self.assertEqual(
            self.client.post(
                f"/api/executions/?account_id={self.second.pk}",
                body,
                content_type="application/json",
            ).status_code,
            400,
        )
