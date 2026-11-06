"""The version explicitly recorded for the running dashboard deployment.

The checkout's git HEAD is deliberately not used here: it may describe source
on disk rather than the version that was deployed.  Deployments may provide a
full SHA in ``DASHBOARD_DEPLOYED_COMMIT_SHA`` or write JSON metadata to
``DASHBOARD_DEPLOYMENT_METADATA`` (default: ``deployment-version.json`` beside
the dashboard).  Missing or malformed metadata is reported as unknown.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from paths import HERE

_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
_DEFAULT_METADATA = Path(HERE) / "deployment-version.json"


def _valid_sha(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value.lower() if _SHA.fullmatch(value) else None


def deployed_version() -> dict[str, str | None]:
    """Return only explicitly deployed metadata, shortened for display."""
    sha = _valid_sha(os.environ.get("DASHBOARD_DEPLOYED_COMMIT_SHA"))
    source = "environment" if sha else None
    if not sha:
        metadata_path = Path(os.environ.get(
            "DASHBOARD_DEPLOYMENT_METADATA", str(_DEFAULT_METADATA)))
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            metadata = None
        if isinstance(metadata, dict):
            sha = _valid_sha(metadata.get("deployed_commit_sha"))
            source = "deployment-metadata" if sha else None
    short_sha = sha[:7] if sha else None
    return {
        "deployed_sha": short_sha,
        "version_label": short_sha or "version unknown",
        "source": source,
    }
