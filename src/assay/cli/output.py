"""Human and canonical JSON renderings of an Assay result."""

from __future__ import annotations

import json
from pathlib import Path


def canonical(payload: dict[str, object]) -> str:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    )


def refusal(cause: str, detail: str, path: Path, as_json: bool) -> str:
    """The CLI's envelope for a refusal that never produced an Assessment."""
    if as_json:
        return canonical(
            {
                "schema": 1,
                "skill": {"path": str(path)},
                "verdict": "unverified",
                "cause": cause,
                "detail": detail,
            }
        )
    return (
        f"skill: {path}\n"
        "verdict: UNVERIFIED\n"
        f"cause: {cause.upper().replace('-', '_')}\n"
        f"detail: {detail}\n"
    )
