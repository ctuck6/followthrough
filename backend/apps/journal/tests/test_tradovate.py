import csv
import io
from decimal import Decimal

from django.test import TestCase

from apps.journal.accounts import prepare_import, scoped_rows
from apps.journal.executions import import_rows, ledger
from apps.journal.models import BrokerageAccount
from apps.journal.tradovate import parse_orders


def export(rows: list[tuple]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "orderId",
            "Account",
            "B/S",
            "Contract",
            "Product",
            "filledQty",
            "Fill Time",
            "Status",
            "Avg Fill Price",
            "Currency",
        ]
    )

    for identifier, side, price, qty, status in rows:
        writer.writerow(
            [
                identifier,
                "TEST",
                side,
                "MNQH6",
                "MNQ",
                qty,
                f"12/26/2025 08:48:{identifier}",
                status,
                price,
                "USD",
            ]
        )

    return output.getvalue()


class TradovateTests(TestCase):
    def test_fifo_and_repeat_import(self) -> None:
        account = BrokerageAccount.objects.create(name="Futures", broker="tradovate")
        content = export(
            [
                ("33", "Buy", "25922", 5, "Filled"),
                ("50", "Sell", "25914.25", 5, "Filled"),
            ]
        )
        rows, selected = prepare_import({"csv": content, "account_id": account.pk})
        self.assertEqual(selected, account)
        self.assertTrue(rows.warnings)
        result = import_rows(scoped_rows(rows, account.pk), account.pk)
        self.assertEqual(result["imported"], 2)
        repeat = import_rows(scoped_rows(rows, account.pk), account.pk)
        self.assertEqual(repeat["duplicates"], 2)
        summary = ledger(account.pk)["summaries"]["2025-12-26"]["USD"]
        self.assertEqual(Decimal(summary["gross"]), Decimal("-77.5"))
        self.assertEqual(summary["gross"], summary["net"])

    def test_unfilled_skipped_partial_rejected(self) -> None:
        content = export(
            [
                ("33", "Buy", "100", 0, "Canceled"),
                ("50", "Buy", "100", 1, "Filled"),
            ]
        )
        self.assertEqual(len(parse_orders(content)), 1)

        with self.assertRaisesMessage(ValueError, "Partially filled"):
            parse_orders(content.replace("Filled", "Working"))

    def test_unknown_contract_and_conflicting_duplicate_rejected(self) -> None:
        content = export([("33", "Buy", "100", 1, "Filled")])

        with self.assertRaisesMessage(ValueError, "Unsupported futures product"):
            parse_orders(content.replace("MNQ", "UNKNOWN"))

        with self.assertRaisesMessage(ValueError, "Conflicting"):
            parse_orders(
                export(
                    [
                        ("33", "Buy", "100", 1, "Filled"),
                        ("33", "Buy", "101", 1, "Filled"),
                    ]
                )
            )
