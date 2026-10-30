"""Human and canonical JSON renderings of an Assay result."""

from __future__ import annotations

import json
from pathlib import Path

from assay.capture import Trace
from assay.ingest import Skill
from assay.verdict import Assessment


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
                "skill": {"path": _path_text(path)},
                "verdict": "unverified",
                "cause": cause,
                "detail": detail,
            }
        )
    return (
        f"skill: {_screen(_path_text(path))}\n"
        "verdict: UNVERIFIED\n"
        f"cause: {cause.upper().replace('-', '_')}\n"
        f"detail: {_one_line(detail)}\n"
        "exit: 1\n"
    )


def render_human(
    skill: Skill,
    assessment: Assessment,
    trace_path: Path,
    trace: Trace,
    exit_code: int,
) -> str:
    lines = [
        f"skill: {_screen(skill.name)} {skill.content_hash[:12]}",
        f"verdict: {assessment.verdict.value.upper()}",
        f"cause: {_cause(assessment)}",
        f"strictness: {assessment.strictness.value} "
        f"(blocked: {'yes' if assessment.blocked else 'no'})",
    ]
    if assessment.findings:
        lines.append("findings:")
        lines.extend(
            f"[{finding.severity.value.upper()}] {finding.class_.value} "
            f"{_screen(finding.target)}: {_screen(finding.reason)}"
            for finding in assessment.findings
        )
    else:
        lines.append("findings: none")
    lines.append(f"trace: {_path_text(trace_path)}")
    lines.append(
        f"cost: ${trace.cost_usd:.4f} "
        f"({trace.input_tokens} input, {trace.output_tokens} output tokens)"
    )
    lines.append(f"exit: {exit_code}")
    return "\n".join(lines) + "\n"


def render_json(
    skill: Skill, assessment: Assessment, trace_path: Path, trace: Trace
) -> str:
    return canonical(
        {
            "schema": 1,
            "skill": {
                "name": skill.name,
                "content_hash": skill.content_hash,
                "path": _path_text(skill.source_path),
            },
            "verdict": assessment.verdict.value,
            "cause": assessment.cause.value if assessment.cause is not None else None,
            "blocked": assessment.blocked,
            "strictness": assessment.strictness.value,
            "findings": [
                {
                    "class": finding.class_.value,
                    "severity": finding.severity.value,
                    "target": finding.target,
                    "reason": finding.reason,
                    "outcome": finding.outcome.value,
                    "review_required": finding.review_required,
                }
                for finding in assessment.findings
            ],
            "trace": _path_text(trace_path),
            "trace_hash": assessment.trace_hash,
            "usage": {
                "input_tokens": trace.input_tokens,
                "output_tokens": trace.output_tokens,
            },
            "cost_usd": trace.cost_usd,
        }
    )


def _cause(assessment: Assessment) -> str:
    if assessment.cause is None:
        return "-"
    return assessment.cause.value.upper().replace("-", "_")


def _screen(value: str) -> str:
    """Keep a terminal report from being rewritten by a skill's own text."""
    return "".join(
        char
        if char.isprintable() and char not in "\r\n"
        else f"\\x{ord(char):02x}"
        for char in value
    )


def _one_line(value: str) -> str:
    return _screen(" ".join(value.split()))


def _path_text(path: Path) -> str:
    # A path decoded from argv can carry surrogates; both JSON and the terminal need valid text.
    return str(path).encode("utf-8", "backslashreplace").decode("utf-8")
