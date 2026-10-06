from django.test import TestCase

from apps.journal.accounts import scoped_rows
from apps.journal.executions import import_rows
from apps.journal.flex_import import reconcile_flex
from apps.journal.ibkr_flex import parse_report
from apps.journal.models import BrokerageAccount, Execution
from apps.journal.tests.test_broker_sync import REPORT


class FlexReconcileTests(TestCase):
    def test_conflict_does_not_block_new_fill_or_modify_existing(self) -> None:
        account = BrokerageAccount.objects.create(name="Test", broker="ibkr")
        row = scoped_rows(parse_report(REPORT), account.pk)[0]
        import_rows([row], account.pk)
        result = reconcile_flex([{**row, "price": "999"}, {**row, "trade_id": "new"}], account.pk)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["conflicts"][0]["fields"], ["price"])
        self.assertEqual(Execution.objects.get(trade_id=row["trade_id"]).data, row)

    def test_metadata_updates_are_idempotent_but_timing_is_flagged(self) -> None:
        account = BrokerageAccount.objects.create(name="Test", broker="ibkr")
        row = scoped_rows(parse_report(REPORT), account.pk)[0]
        import_rows([row], account.pk)
        corrected = {**row, "order_id": "correct"}
        self.assertEqual(reconcile_flex([corrected], account.pk)["updated"], 1)
        self.assertEqual(reconcile_flex([corrected], account.pk)["updated"], 0)
        result = reconcile_flex(
            [{**corrected, "execution_time": "2026-10-02 09:31:00"}], account.pk
        )
        self.assertEqual(len(result["conflicts"]), 1)

    def test_activity_fields_normalize_to_same_fill(self) -> None:
        confirmation = REPORT.replace(
            "Commission\n", "Commission,OrderID,Date/Time,Code\n"
        ).replace("-1\n", "-1,123,20261002;093001,O\n")
        activity = (
            confirmation.replace("Price,", "TradePrice,")
            .replace("Commission", "IBCommission")
            .replace("OrderID", "IBOrderID")
            .replace("Date/Time", "DateTime")
            .replace("Code", "Open/CloseIndicator")
        )
        self.assertEqual(parse_report(confirmation), parse_report(activity))
