from unittest.mock import patch

from django.test import TestCase

from apps.journal.accounts import prepare_import
from apps.journal.models import BrokerageAccount


class AccountTests(TestCase):
    def test_account_creation_validation_and_limit(self) -> None:
        for number in range(10):
            response = self.client.post(
                "/api/accounts/",
                {"name": f"Account {number}", "broker": "ibkr"},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.client.post(
                "/api/accounts/",
                {"name": "Too many", "broker": "schwab"},
                content_type="application/json",
            ).status_code,
            400,
        )
        self.assertEqual(len(self.client.get("/api/accounts/").json()["accounts"]), 10)
        self.assertEqual(
            self.client.post(
                "/api/accounts/",
                {"name": "Bad", "broker": "unknown"},
                content_type="application/json",
            ).status_code,
            400,
        )

    @patch("apps.journal.executions.parse_csv", return_value=[{"account": "U123"}])
    def test_import_routes_and_prevents_wrong_account(self, parser: object) -> None:
        account = BrokerageAccount.objects.create(name="Main", broker="ibkr")
        rows, selected = prepare_import({"csv": "sample", "account_id": account.pk})
        self.assertEqual(selected.pk, account.pk)
        self.assertEqual(rows[0]["account"], "U123")
        with self.assertRaises(ValueError):
            prepare_import({"csv": "sample"})
        account.source_identifier = "U456"
        account.save()
        with self.assertRaises(ValueError):
            prepare_import({"csv": "sample", "account_id": account.pk})
        schwab = BrokerageAccount.objects.create(name="Schwab", broker="schwab")
        with self.assertRaisesMessage(ValueError, "thinkorswim account statement"):
            prepare_import({"csv": "sample", "account_id": schwab.pk})

    @patch("apps.journal.executions.parse_csv", return_value=[{"account": "U123"}])
    def test_same_source_cannot_be_linked_to_two_accounts(self, parser: object) -> None:
        BrokerageAccount.objects.create(name="Existing", broker="ibkr", source_identifier="U123")
        second = BrokerageAccount.objects.create(name="Second", broker="ibkr")
        with self.assertRaises(ValueError):
            prepare_import({"csv": "sample", "account_id": second.pk})
