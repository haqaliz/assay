"""Best-effort classification of a run's failures into denial records.

This is NOT a complete trace. Seatbelt gives the parent no event stream, so A2 can only see
what the child reports plus what it printed. A4 replaces this with mediated tool-call capture.

Two sources are trusted, in order:

1. ``assay-denial: <kind> <detail>`` lines, written by a mediated/instrumented child.
2. Fallback heuristics over stderr lines that say "Operation not permitted"/"Permission denied".
"""

from __future__ import annotations

from .records import DenialClass, DenialRecord

DENIAL_MARKER = "assay-denial:"
_DETAIL_LIMIT = 200

_NETWORK_WORDS = ("socket", "connect", "network", "tcp", "udp")
_WRITE_WORDS = ("write", "create", "delete", "truncate")
_READ_WORDS = ("read", "open", "getcwd")


def classify_failure(stderr: str, limit_exceeded: str | None = None) -> tuple[DenialRecord, ...]:
    records: list[DenialRecord] = []
    if limit_exceeded:
        records.append(DenialRecord(DenialClass.LIMIT, limit_exceeded))

    for raw in (stderr or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if DENIAL_MARKER in line:
            tail = line.split(DENIAL_MARKER, 1)[1].strip()
            raw_kind, _, detail = tail.partition(" ")
            records.append(
                DenialRecord(_as_kind(raw_kind), (detail.strip() or raw_kind)[:_DETAIL_LIMIT])
            )
        elif _looks_denied(line):
            records.append(DenialRecord(_guess_kind(line), line[:_DETAIL_LIMIT]))

    return _dedupe(records)


def _looks_denied(line: str) -> bool:
    return any(
        marker in line
        for marker in ("Operation not permitted", "Permission denied", "EPERM", "Errno 1")
    )


def _as_kind(raw: str) -> DenialClass:
    try:
        return DenialClass(raw.lower())
    except ValueError:
        return DenialClass.UNKNOWN


def _guess_kind(line: str) -> DenialClass:
    lowered = line.lower()
    for kind, words in (
        (DenialClass.NETWORK, _NETWORK_WORDS),
        (DenialClass.FILE_WRITE, _WRITE_WORDS),
        (DenialClass.FILE_READ, _READ_WORDS),
    ):
        if any(word in lowered for word in words):
            return kind
    return DenialClass.UNKNOWN


def _dedupe(records: list[DenialRecord]) -> tuple[DenialRecord, ...]:
    seen: set[tuple[DenialClass, str]] = set()
    unique: list[DenialRecord] = []
    for record in records:
        key = (record.kind, record.detail)
        if key not in seen:
            seen.add(key)
            unique.append(record)
    return tuple(unique)
