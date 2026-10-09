import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.journal.models import BrokerageAccount
from apps.journal.schwab_connection import write_private


class SchwabConnectionTests(TestCase):
    def setUp(self) -> None:
        self.account = BrokerageAccount.objects.create(name="Schwab", broker="schwab")
        self.url = f"/api/schwab/connection/?account_id={self.account.pk}"
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(BASE_DIR=Path(directory.name))
        settings.enable()
        self.addCleanup(settings.disable)

    @patch("apps.journal.schwab_connection.subprocess.Popen")
    @patch("apps.journal.schwab_connection.flex_setting")
    def test_connect_and_duplicate_guard_without_secret_output(self, setting, spawn) -> None:
        setting.side_effect = lambda key: (
            "https://127.0.0.1:8182" if key.endswith("URL") else "private-secret"
        )
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "connecting")
        self.assertNotIn("private-secret", response.content.decode())
        self.assertNotIn("private-secret", str(spawn.call_args))
        self.assertEqual(self.client.post(self.url).status_code, 409)
        self.assertEqual(spawn.call_count, 1)

    @patch("apps.journal.schwab_connection.flex_setting", return_value="")
    def test_missing_credentials_and_wrong_account(self, setting) -> None:
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.account.broker = "ibkr"
        self.account.save()
        self.assertEqual(self.client.get(self.url).status_code, 400)

    def test_private_token_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token.json"
            write_private(path, {"token": "secret"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
