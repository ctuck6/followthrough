from decimal import Decimal

from django.test import TestCase

from apps.journal.executions import import_rows, ledger
from apps.journal.thinkorswim import parse_statement


class ThinkorswimTests(TestCase):
    def statement(self, rows: str) -> str:
        return (
            "Account Statement for TEST (margin)\n\nCash Balance\nDATE,TIME,TYPE,REF #,DESCRIPTION,Misc Fees,Commissions & Fees,AMOUNT,BALANCE\n"
            + rows
            + "\n\nAccount Trade History\nignored\n"
        )

    def test_options_fees_fifo_and_repeat_dedup(self) -> None:
        data = self.statement(
            '7/31/26,07:14:05,TRD,="101",BOT +1 XYZ 100 (Weeklys) 31 JUL 26 120 CALL @3.10,-0.01,-0.65,-310,0\n7/31/26,07:19:31,TRD,="102",SOLD -1 XYZ 100 (Weeklys) 31 JUL 26 120 CALL @4.60,-0.09,-0.65,460,0'
        )
        rows = parse_statement(data)
        self.assertEqual(rows[0]["expiry"], "2026-07-31")
        self.assertEqual(rows[0]["commission"], "-0.66")
        self.assertEqual(import_rows(rows)["imported"], 2)
        self.assertEqual(import_rows(parse_statement(data))["duplicates"], 2)
        self.assertEqual(Decimal(ledger()["trades"][0]["net"]), Decimal("148.60"))

    def test_identical_fills_with_different_references_and_futures_warning(self) -> None:
        rows = parse_statement(
            self.statement(
                '8/5/26,08:32:08,TRD,="1",BOT +5 ABC @9.45,,,-47.25,0\n8/5/26,08:32:08,TRD,="2",BOT +5 ABC @9.45,,,-47.25,0\n8/5/26,08:33:00,TRD,="3",BOT +2 /MNQU26:XCME @29924.75,,-4.50,,0'
            )
        )
        self.assertEqual(len(rows), 3)
        self.assertNotEqual(rows[0]["trade_id"], rows[1]["trade_id"])
        self.assertEqual(rows[2]["asset_class"], "FUT")
        self.assertEqual(rows[2]["multiplier"], "2")
        self.assertEqual(rows.warnings, [])

    def test_malformed_trade_is_not_silently_skipped(self) -> None:
        with self.assertRaises(ValueError):
            parse_statement(self.statement('8/5/26,08:32:08,TRD,="1",BOT +5 ABC @9.45,,,-1,0'))

    def test_empty_accounts_is_success(self) -> None:
        response = self.client.get("/api/accounts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"accounts": [], "has_unassigned": False})

    def test_futures_long_short_and_contract_separation(self) -> None:
        text = self.statement(
            '8/5/26,07:24:11,TRD,="1",BOT +2 /MNQU26:XCME @29924.75,,-4.50,,0\n8/5/26,07:29:51,TRD,="2",SOLD -2 /MNQU26:XCME @29918.00,,-4.50,-27,0\n8/5/26,07:33:31,TRD,="3",SOLD -2 /MNQU26:XCME @29889.25,,-4.50,,0\n8/5/26,07:37:58,TRD,="4",BOT +2 /MNQU26:XCME @29849.75,,-4.50,158,0'
        )
        rows = parse_statement(text)
        import_rows(rows)
        trades = ledger()["trades"]
        self.assertEqual([Decimal(t["gross"]) for t in trades], [Decimal("-27"), Decimal("158")])
        self.assertEqual([Decimal(t["net"]) for t in trades], [Decimal("-36"), Decimal("149")])
        self.assertEqual(import_rows(parse_statement(text))["duplicates"], 4)
