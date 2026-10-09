"""Run the temporary HTTPS OAuth callback listener, never a trading server."""

import fcntl
import logging

from django.core.management.base import BaseCommand

from apps.journal.ibkr_flex import flex_setting
from apps.journal.models import BrokerageAccount
from apps.journal.schwab_connection import private_directory, write_private


class Command(BaseCommand):
    help = "Authorize Schwab locally through its browser login."

    def add_arguments(self, parser) -> None:
        parser.add_argument("account_id", type=int)

    def handle(self, *args, **options) -> None:
        from schwab.auth import client_from_login_flow

        logging.disable(logging.CRITICAL)
        account_id = options["account_id"]
        directory = private_directory()
        status = directory / f"status-{account_id}.json"
        token = directory / f"token-{account_id}.json"

        try:
            BrokerageAccount.objects.get(pk=account_id, broker="schwab")
            with (directory / f"sync-{account_id}.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                client_from_login_flow(
                    flex_setting("SCHWAB_APP_KEY"),
                    flex_setting("SCHWAB_APP_SECRET"),
                    flex_setting("SCHWAB_CALLBACK_URL"),
                    str(token),
                    token_write_func=lambda value, **kwargs: write_private(token, value),
                    callback_timeout=300,
                    interactive=False,
                )
            write_private(
                status,
                {
                    "status": "connected",
                    "message": "Schwab connected.",
                },
            )
        except Exception:  # noqa: BLE001 -- redact OAuth secrets at the boundary
            # OAuth exceptions may contain URLs, authorization codes, or tokens.
            write_private(
                status,
                {
                    "status": "error",
                    "message": "Schwab sign-in did not complete. Check app approval and callback, then retry.",
                },
            )
