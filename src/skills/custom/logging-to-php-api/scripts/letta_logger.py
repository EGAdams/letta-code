"""
LettaLogger — sends structured log entries to the americansjewelry.com PHP API.

Each class gets one envelope row in monitored_objects keyed by object_view_id
(convention: ClassName_Year, e.g. "ProviderManager_2026").

object_data is a JSON-encoded list of log entries that is fully replaced on
every flush.  Logging never raises — failures are silently swallowed so they
cannot crash the host object.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Literal

_BASE_URL = "https://americansjewelry.com/libraries/local-php-api/index.php/object"
_TIMEOUT = 5  # seconds

Status = Literal["green", "yellow", "red"]


class LettaLogger:
    """Append-and-flush logger that upserts to the PHP monitored_objects API."""

    def __init__(self, object_view_id: str) -> None:
        self.object_view_id = object_view_id
        self._entries: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(
        self,
        method: str,
        event: str,
        data: Any = None,
        status: Status = "green",
    ) -> None:
        """Append a log entry and flush to the API (fire-and-forget)."""
        entry: dict = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "event": event,
            "status": status,
        }
        if data is not None:
            entry["data"] = data
        self._entries.append(entry)
        self._flush()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        """Upsert current entries to the PHP API (insert-first strategy)."""
        payload = json.dumps({
            "object_view_id": self.object_view_id,
            "object_data": json.dumps(self._entries),
        }).encode("utf-8")

        if self._post("/insert", payload):
            return  # new row created
        self._post("/update", payload)  # row already existed

    def _post(self, path: str, payload: bytes) -> bool:
        """POST payload to BASE_URL+path.  Returns True on HTTP 2xx response."""
        try:
            req = urllib.request.Request(
                _BASE_URL + path,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "User-Agent": "Mozilla/5.0 (compatible; LettaLogger/1.0)",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                resp.read()  # drain response body
                return True  # urlopen raises on HTTP errors; reaching here means 2xx
        except Exception:
            return False
