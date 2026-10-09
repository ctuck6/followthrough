"""Local-only Schwab authorization; no brokerage credentials leave the backend."""

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from .accounts import request_account
from .ibkr_flex import flex_setting
from .models import BrokerageAccount


def private_directory() -> Path:
    directory = settings.BASE_DIR / ".schwab"
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)

    return directory


def write_private(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)

    os.replace(temporary, path)
    path.chmod(0o600)


def connection_status(account_id: int) -> dict:
    directory = private_directory()
    path = directory / f"status-{account_id}.json"

    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        value = {"status": "disconnected", "message": ""}

    if value["status"] == "connecting" and time.time() - value.get("started", 0) > 360:
        value = {"status": "error", "message": "Schwab sign-in timed out. Connect again."}

    return {"status": value["status"], "message": value.get("message", "")}


@require_http_methods(["GET", "POST"])
def connection(request: HttpRequest) -> JsonResponse:
    account_id = request_account(request)
    account = BrokerageAccount.objects.filter(pk=account_id, broker="schwab").first()
    configured = all(
        flex_setting(key) for key in ("SCHWAB_APP_KEY", "SCHWAB_APP_SECRET", "SCHWAB_CALLBACK_URL")
    )

    if account is None:
        return JsonResponse({"error": "Select a Charles Schwab account."}, status=400)

    if request.method == "POST":
        if not configured:
            return JsonResponse({"error": "Schwab credentials are not configured."}, status=400)

        if flex_setting("SCHWAB_CALLBACK_URL") != "https://127.0.0.1:8182":
            return JsonResponse(
                {"error": "Set the callback to https://127.0.0.1:8182."}, status=400
            )

        directory = private_directory()

        with (directory / "launch.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)

            for path in directory.glob("status-*.json"):
                value = json.loads(path.read_text())

                if (
                    value.get("status") == "connecting"
                    and time.time() - value.get("started", 0) < 360
                ):
                    return JsonResponse({"error": "A Schwab sign-in is already open."}, status=409)

            write_private(
                directory / f"status-{account.pk}.json",
                {
                    "status": "connecting",
                    "started": time.time(),
                    "message": "Complete sign-in in your browser.",
                },
            )

            try:
                subprocess.Popen(
                    [
                        sys.executable,
                        str(settings.BASE_DIR / "manage.py"),
                        "connect_schwab",
                        str(account.pk),
                    ],
                    cwd=settings.BASE_DIR,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError:
                write_private(
                    directory / f"status-{account.pk}.json",
                    {"status": "error", "message": "Could not start Schwab sign-in."},
                )
                return JsonResponse({"error": "Could not start Schwab sign-in."}, status=503)

    return JsonResponse({"configured": configured, **connection_status(account.pk)})
