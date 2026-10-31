"""The one canonical JSON encoding shared by the CLI and bundles."""

from __future__ import annotations

import json


def canonical(payload: dict[str, object]) -> str:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    )
