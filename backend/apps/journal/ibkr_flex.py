"""IBKR Flex transport. Never surface URLs or credentials in errors."""

import csv
import io
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings

from .executions import normalize

BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/"
MAX_BYTES = 2 * 1024 * 1024


class FlexError(ValueError):
    """Safe error text suitable for the UI."""

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def credentials() -> tuple[str, str]:
    values = {}
    path = settings.BASE_DIR / ".env"

    if path.exists():
        for line in path.read_text().splitlines():
            name, separator, value = line.partition("=")

            if separator and name.strip() in {"IBKR_FLEX_TOKEN", "IBKR_FLEX_QUERY_ID"}:
                values[name.strip()] = value.strip().strip("\"'")

    return tuple(
        os.environ.get(key, values.get(key, ""))
        for key in ("IBKR_FLEX_TOKEN", "IBKR_FLEX_QUERY_ID")
    )


def fetch(endpoint: str, parameters: dict) -> str:
    request = Request(
        BASE_URL + endpoint + "?" + urlencode(parameters),
        headers={"User-Agent": "Followthrough/1.0"},
    )

    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            data = response.read(MAX_BYTES + 1)

        if len(data) > MAX_BYTES:
            raise FlexError("IBKR report exceeds 2 MB. Shorten the Flex query period.")

        return data.decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError):
        raise FlexError(
            "Could not reach IBKR Flex. Check your connection and try again."
        ) from None


def xml_response(content: str) -> ET.Element:
    if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        raise FlexError("IBKR returned an unsupported XML response.")

    try:
        return ET.fromstring(content)
    except ET.ParseError:
        raise FlexError("IBKR returned an invalid response.") from None


def error_message(root: ET.Element) -> str:
    code = root.findtext("ErrorCode", "")
    messages = {
        "1012": "The IBKR Flex token has expired. Replace it in backend/.env.",
        "1013": "IBKR rejected this IP address. Check your Flex token IP restrictions.",
        "1015": "IBKR rejected the Flex token. Check backend/.env.",
        "1018": "IBKR rate limit reached. Try again in a few minutes.",
        "1019": "IBKR is still generating the report. Try again shortly.",
        "1020": "IBKR could not validate the Flex query. Check the token and Query ID.",
    }

    return messages.get(
        code, "IBKR could not generate this Flex report. Check its configuration."
    )


def download_report(period: int = 30) -> str:
    token, query = credentials()

    if not token or not query:
        raise FlexError("Add IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID to backend/.env.")

    root = xml_response(
        fetch("SendRequest", {"t": token, "q": query, "v": "3", "p": str(period)})
    )

    if root.findtext("Status") != "Success":
        raise FlexError(error_message(root), root.findtext("ErrorCode", ""))

    reference = root.findtext("ReferenceCode")

    if not reference:
        raise FlexError("IBKR did not return a report reference.")

    for _ in range(8):
        # Stay below IBKR's ten requests per minute, including generation.
        time.sleep(10)
        content = fetch("GetStatement", {"t": token, "q": reference, "v": "3"})

        if not content.lstrip().startswith("<"):
            return content

        report = xml_response(content)

        if report.tag != "FlexStatementResponse":
            return content

        if report.findtext("ErrorCode") not in {"1018", "1019"}:
            raise FlexError(error_message(report), report.findtext("ErrorCode", ""))

    raise FlexError("IBKR is still preparing the report. Try again in a few minutes.")


def flex_date(value: str, timestamp: bool = False) -> str:
    if not value:
        return ""

    formats = (
        ("%Y%m%d;%H%M%S", "%Y%m%d;%H:%M:%S", "%Y-%m-%d;%H:%M:%S")
        if timestamp
        else ("%Y%m%d",)
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)  # noqa: DTZ007 -- preserve report wall time

            return parsed.strftime("%Y-%m-%d %H:%M:%S" if timestamp else "%Y-%m-%d")
        except ValueError:
            continue

    return value


def parse_report(content: str) -> list[dict]:
    if content.lstrip().startswith("<"):
        raise FlexError(
            "Set the IBKR Flex query output to CSV using the existing execution columns."
        )

    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    required = {"TradeID", "AssetClass", "Buy/Sell", "Quantity", "Price", "OrderTime"}

    if not required <= set(reader.fieldnames or []):
        raise FlexError(
            "The Flex query must include execution-level TradeID, AssetClass, Buy/Sell, Quantity, Price and OrderTime columns."
        )

    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise FlexError("The Flex report has duplicate columns.")

    rows = []

    for index, row in enumerate(reader, 2):
        if None in row or None in row.values():
            raise FlexError(f"Flex report row {index} has an incorrect column count.")

        for name in ("OrderTime", "Date/Time"):
            if row.get(name):
                row[name] = flex_date(row[name], timestamp=True)

        for name in ("TradeDate", "Expiry"):
            if row.get(name):
                row[name] = flex_date(row[name])

        try:
            rows.append(normalize(row))
        except (ValueError, ArithmeticError):
            raise FlexError(
                f"Flex report row {index} is invalid. Check execution columns, dates, currency and instrument fields."
            ) from None

        if len(rows) > 10000:
            raise FlexError("Import at most 10,000 executions per sync.")

    return rows
