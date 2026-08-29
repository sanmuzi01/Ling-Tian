from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 mining-rights-daily-agent/0.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class FetchError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_bytes(url: str, timeout: float = 15) -> tuple[bytes, str | None]:
    request = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.read(), response.headers.get("content-type")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc


def fetch_text(url: str, timeout: float = 15) -> str:
    body, content_type = fetch_bytes(url, timeout=timeout)
    encoding = "utf-8"
    if content_type and "charset=" in content_type:
        encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
