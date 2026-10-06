from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.journal.accounts import scoped_rows
from apps.journal.broker_sync import is_due, run_sync
from apps.journal.executions import import_rows
from apps.journal.ibkr_flex import FlexError, download_report, parse_report
from apps.journal.models import BrokerageAccount, BrokerSync, Execution

HEADER = "TradeID,AccountAlias,CurrencyPrimary,AssetClass,Symbol,Buy/Sell,Quantity,Price,OrderTime,Commission\n"
REPORT = HEADER + "1,Test,USD,STK,ABC,BUY,10,10,20261002;093000,-1\n"


class FlexTests(TestCase):
    def setUp(self) -> None:
        activity = patch("apps.journal.broker_sync.activity_query_id", return_value="")
        activity.start()
        self.addCleanup(activity.stop)

    def test_csv_dates_empty_and_validation(self) -> None:
        self.assertEqual(parse_report(REPORT)[0]["session_date"], "2026-10-02")
        self.assertEqual(parse_report(HEADER), [])

        with self.assertRaises(FlexError):
            parse_report("<FlexQueryResponse/>")

        with self.assertRaises(FlexError):
            parse_report(REPORT.replace(",10,10,", ",NaN,10,"))

    @patch("apps.journal.ibkr_flex.time.sleep")
    @patch("apps.journal.ibkr_flex.credentials", return_value=("secret", "123"))
    @patch("apps.journal.ibkr_flex.fetch")
    def test_generation_polling(self, fetch: object, creds: object, sleep: object) -> None:
        fetch.side_effect = [
            "<FlexStatementResponse><Status>Success</Status><ReferenceCode>ref</ReferenceCode></FlexStatementResponse>",
            "<FlexStatementResponse><ErrorCode>1019</ErrorCode></FlexStatementResponse>",
            REPORT,
        ]
        self.assertEqual(download_report(), REPORT)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(fetch.call_args_list[0].args[1], {"t": "secret", "q": "123", "v": "3"})
        self.assertEqual(fetch.call_args.args[0], "GetStatement")

    def test_schedule_dst_weekends_and_lease(self) -> None:
        state = BrokerSync()
        summer = datetime(2026, 10, 2, 20, 15, tzinfo=UTC)
        winter = datetime(2026, 12, 1, 21, 15, tzinfo=UTC)
        self.assertFalse(is_due(state, summer - timedelta(minutes=1)))
        self.assertTrue(is_due(state, summer))
        self.assertTrue(is_due(state, winter))
        self.assertFalse(is_due(state, summer + timedelta(days=1)))
        self.assertTrue(is_due(state, summer + timedelta(days=1), startup=True))
        state.lease_until = summer + timedelta(minutes=1)
        state.requested = True
        self.assertFalse(is_due(state, summer, startup=True))
        state.status = "running"
        self.assertTrue(is_due(state, summer + timedelta(minutes=2)))

    @patch("apps.journal.broker_sync.credentials", return_value=("secret", "123"))
    @patch("apps.journal.broker_sync.download_report", return_value=REPORT)
    def test_existing_csv_deduplication(self, download: object, creds: object) -> None:
        account = BrokerageAccount.objects.create(
            name="Main", broker="ibkr", source_identifier="Test"
        )
        import_rows(scoped_rows(parse_report(REPORT), account.pk), account.pk)
        state = BrokerSync.objects.create(pk=1, requested=True)
        run_sync()
        state.refresh_from_db()
        self.assertEqual(state.status, "success")
        self.assertEqual(state.account_id, account.pk)
        self.assertEqual(state.duplicates, 1)
        self.assertEqual(Execution.objects.count(), 1)

    @patch("apps.journal.broker_sync.credentials", return_value=("secret", "123"))
    @patch("apps.journal.broker_sync.download_report", return_value=REPORT)
    def test_wrong_account_and_conflicting_report_do_not_import(
        self, download: object, creds: object
    ) -> None:
        account = BrokerageAccount.objects.create(
            name="Other", broker="ibkr", source_identifier="Other"
        )
        state = BrokerSync.objects.create(pk=1, account=account, requested=True)
        run_sync()
        state.refresh_from_db()
        self.assertEqual(state.status, "error")
        self.assertEqual(Execution.objects.count(), 0)
        self.assertIsNotNone(state.retry_at)

    @patch("apps.journal.broker_sync.credentials", return_value=("secret", "123"))
    @patch(
        "apps.journal.broker_sync.download_report",
        side_effect=RuntimeError("token=secret"),
    )
    def test_errors_redacted_and_retries_bounded(self, download: object, creds: object) -> None:
        state = BrokerSync.objects.create(pk=1, requested=True, failures=3)
        run_sync()
        state.refresh_from_db()
        self.assertEqual(state.status, "error")
        self.assertNotIn("secret", state.message)
        self.assertIsNone(state.retry_at)

    @patch("apps.journal.broker_sync.start_worker")
    @patch("apps.journal.broker_sync.credentials", return_value=("secret", "123"))
    def test_manual_queue_is_scoped(self, creds: object, worker: object) -> None:
        account = BrokerageAccount.objects.create(name="Main", broker="ibkr")
        url = f"/api/broker-sync/?account_id={account.pk}"
        self.assertEqual(self.client.post(url).status_code, 202)
        self.assertTrue(BrokerSync.objects.get(pk=1).requested)
        self.assertNotIn("secret", self.client.get(url).content.decode())
        BrokerSync.objects.update(lease_until=timezone.now() + timedelta(minutes=1))
        self.assertEqual(self.client.post(url).status_code, 409)

    @patch("apps.journal.ibkr_flex.time.sleep")
    @patch("apps.journal.ibkr_flex.credentials", return_value=("secret", "123"))
    @patch("apps.journal.ibkr_flex.fetch")
    def test_expired_token_at_both_stages(
        self, fetch: object, creds: object, sleep: object
    ) -> None:
        expired = "<FlexStatementResponse><Status>Fail</Status><ErrorCode>1012</ErrorCode></FlexStatementResponse>"
        success = "<FlexStatementResponse><Status>Success</Status><ReferenceCode>ref</ReferenceCode></FlexStatementResponse>"
        for responses in ([expired], [success, expired]):
            fetch.side_effect = responses
            with self.assertRaises(FlexError) as caught:
                download_report()
            self.assertEqual(caught.exception.code, "1012")
            self.assertIn("expired", str(caught.exception))
            self.assertNotIn("secret", str(caught.exception))

    @patch("apps.journal.broker_sync.credentials", return_value=("secret", "123"))
    @patch(
        "apps.journal.broker_sync.download_report",
        side_effect=FlexError("Token expired", "1012"),
    )
    def test_expired_token_does_not_retry(self, download: object, creds: object) -> None:
        run_sync(startup=True)
        state = BrokerSync.objects.get(pk=1)
        self.assertEqual(state.status, "error")
        self.assertIsNone(state.retry_at)
        self.assertEqual(Execution.objects.count(), 0)

    @patch("apps.journal.broker_sync.credentials", return_value=("secret", "123"))
    @patch("apps.journal.broker_sync.download_report")
    def test_import_timestamp_only_changes_for_new_executions(
        self, download: object, creds: object
    ) -> None:
        previous = timezone.now() - timedelta(days=1)
        account = BrokerageAccount.objects.create(
            name="Main", broker="ibkr", last_import_at=previous
        )
        state = BrokerSync.objects.create(pk=1, account=account, requested=True)
        download.return_value = HEADER
        run_sync()
        account.refresh_from_db()
        self.assertEqual(account.last_import_at, previous)
        download.return_value = REPORT
        BrokerSync.objects.filter(pk=1).update(requested=True)
        run_sync()
        account.refresh_from_db()
        imported_at = account.last_import_at
        self.assertGreater(imported_at, previous)
        BrokerSync.objects.filter(pk=1).update(requested=True)
        run_sync()
        account.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(account.last_import_at, imported_at)
        self.assertEqual(state.imported, 0)
        self.assertEqual(state.duplicates, 1)
        self.assertGreater(state.last_success, imported_at)

    @patch("apps.journal.broker_sync.credentials", return_value=("secret", "today"))
    @patch("apps.journal.broker_sync.activity_query_id", return_value="history")
    @patch("apps.journal.broker_sync.download_report")
    def test_dual_query_deduplicates_and_rolls_back_on_failure(
        self, download: object, activity: object, creds: object
    ) -> None:
        account = BrokerageAccount.objects.create(name="Main", broker="ibkr")
        state = BrokerSync.objects.create(pk=1, account=account, requested=True)
        download.side_effect = [REPORT, FlexError("Historical report unavailable")]
        run_sync()
        self.assertEqual(Execution.objects.count(), 0)
        account.refresh_from_db()
        self.assertIsNone(account.last_import_at)
        BrokerSync.objects.filter(pk=1).update(requested=True)
        download.side_effect = [
            REPORT,
            REPORT + REPORT.splitlines(True)[1].replace("1,Test", "2,Test"),
        ]
        run_sync()
        state.refresh_from_db()
        self.assertEqual(state.status, "success")
        self.assertEqual(state.imported, 2)
        self.assertEqual(state.duplicates, 0)
        self.assertEqual(download.call_args.kwargs, {"query_id": "history"})

    def test_activity_column_aliases_match_confirmation(self) -> None:
        activity = REPORT.replace("Price,", "TradePrice,").replace("Commission", "IBCommission")
        self.assertEqual(parse_report(activity), parse_report(REPORT))
