"""Human and canonical JSON renderings of an Assay result."""

from __future__ import annotations

from pathlib import Path

from assay.bundle import Bundle
from assay.canonical import canonical
from assay.capture import Trace
from assay.corpus import Label, Metrics, Ratio, Source
from assay.ingest import Skill
from assay.mcp.inspect import ServerReport
from assay.triage import Triage
from assay.verdict import Assessment, UnverifiedCause, Verdict

TRIAGE_NOTE = "pre-filter only; this is not a verdict. Run `assay check`."
MCP_NOTE = "inspection only; no verdict."


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


def bundle_refusal(cause: str, detail: str, path: Path, as_json: bool) -> str:
    """The CLI's envelope for a bundle that could not be built or verified."""
    if as_json:
        return canonical(
            {
                "schema": 1,
                "bundle": _path_text(path),
                "cause": cause,
                "detail": detail,
            }
        )
    return (
        f"bundle: {_screen(_path_text(path))}\n"
        f"cause: {cause.upper().replace('-', '_')}\n"
        f"detail: {_one_line(detail)}\n"
        "exit: 1\n"
    )


def corpus_refusal(cause: str, detail: str, path: Path, as_json: bool) -> str:
    """The CLI's envelope for a corpus that could not be loaded."""
    if as_json:
        return canonical(
            {
                "schema": 1,
                "corpus": _path_text(path),
                "cause": cause,
                "detail": detail,
            }
        )
    return (
        f"corpus: {_screen(_path_text(path))}\n"
        f"cause: {cause.upper().replace('-', '_')}\n"
        f"detail: {_one_line(detail)}\n"
        "exit: 1\n"
    )


def triage_refusal(cause: str, detail: str, path: Path, as_json: bool) -> str:
    """The CLI's envelope for a skill triage could not parse; never a verdict."""
    if as_json:
        return canonical(
            {
                "schema": 1,
                "skill": {"path": _path_text(path)},
                "cause": cause,
                "detail": detail,
            }
        )
    return (
        f"skill: {_screen(_path_text(path))}\n"
        f"cause: {cause.upper().replace('-', '_')}\n"
        f"detail: {_one_line(detail)}\n"
        "exit: 1\n"
    )


def render_corpus(metrics: Metrics, path: Path, as_json: bool) -> str:
    if as_json:
        return canonical(
            {"schema": 1, "corpus": _path_text(path), **metrics.to_payload()}
        )
    rows = (Verdict.MALICIOUS, Verdict.FLAGGED, Verdict.CLEAN)
    decided_malicious = sum(metrics.confusion[row][Label.MALICIOUS] for row in rows)
    decided_clean = sum(metrics.confusion[row][Label.CLEAN] for row in rows)
    lines = [
        f"corpus: {_screen(_path_text(path))}",
        f"cases: {metrics.total} "
        f"(malicious {metrics.by_label[Label.MALICIOUS]}, "
        f"clean {metrics.by_label[Label.CLEAN]})",
        f"decided: {metrics.decided} "
        f"(malicious {decided_malicious}, clean {decided_clean}) | "
        f"{_unverified(metrics)}",
        f"{'verdict':<12}{'malicious':>9}{'clean':>7}",
    ]
    lines.extend(
        f"{row.value:<12}"
        f"{metrics.confusion[row][Label.MALICIOUS]:>9}"
        f"{metrics.confusion[row][Label.CLEAN]:>7}"
        for row in rows
    )
    lines.extend(
        [
            f"malicious precision: {_ratio(metrics.malicious_precision)}",
            f"malicious recall: {_ratio(metrics.malicious_recall)}; "
            f"detected with any finding: {_ratio(metrics.detection_recall)}",
            f"clean false-malicious: {_ratio(metrics.clean_false_malicious)}",
            f"clean review: {_ratio(metrics.clean_review)}",
            f"coverage: {_ratio(metrics.coverage)}",
            f"false malicious: {_ids(metrics.false_malicious_cases)}",
            f"false negatives: {_ids(metrics.false_negative_cases)}",
            f"labels: {_labels(metrics.labelers)}",
            f"sources: {_sources(metrics.sources)}",
            "exit: 0",
        ]
    )
    return "\n".join(lines) + "\n"


def _unverified(metrics: Metrics) -> str:
    if metrics.unverified == 0:
        return "unverified: 0"
    causes = ", ".join(
        f"{cause.value} {metrics.unverified_by_cause[cause]}"
        for cause in UnverifiedCause
        if metrics.unverified_by_cause[cause]
    )
    return f"unverified: {metrics.unverified} ({causes})"


def _ratio(ratio: Ratio) -> str:
    if ratio.value is None:
        return "n/a (0/0)"
    return f"{ratio.value:.2f} ({ratio.numerator}/{ratio.denominator})"


def _ids(ids: tuple[str, ...]) -> str:
    return ", ".join(ids) if ids else "none"


def _labels(labelers: dict[str, int]) -> str:
    return (
        ", ".join(
            f"{_screen(name)} ({count})" for name, count in sorted(labelers.items())
        )
        or "none"
    )


def _sources(sources: dict[Source, int]) -> str:
    return (
        ", ".join(
            f"{source.value} {count}"
            for source, count in sorted(
                sources.items(), key=lambda item: item[0].value
            )
        )
        or "none"
    )


def _summary_lines(name: str, content_hash: str, assessment: Assessment) -> list[str]:
    lines = [
        f"skill: {_screen(name)} {content_hash[:12]}",
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
    return lines


def render_human(
    skill: Skill,
    assessment: Assessment,
    trace_path: Path,
    trace: Trace,
    exit_code: int,
) -> str:
    lines = _summary_lines(skill.name, skill.content_hash, assessment)
    lines[1:1] = [
        f"format: {skill.format.value}",
        f"requirements: {', '.join(skill.requirements) or 'none'}",
    ]
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
                "format": skill.format.value,
                "requirements": list(skill.requirements),
            },
            "verdict": assessment.verdict.value,
            "cause": assessment.cause.value if assessment.cause is not None else None,
            "blocked": assessment.blocked,
            "strictness": assessment.strictness.value,
            "findings": [finding.to_payload() for finding in assessment.findings],
            "trace": _path_text(trace_path),
            "trace_hash": assessment.trace_hash,
            "usage": {
                "input_tokens": trace.input_tokens,
                "output_tokens": trace.output_tokens,
            },
            "cost_usd": trace.cost_usd,
        }
    )


def render_triage(skill: Skill, record: Triage, as_json: bool) -> str:
    if as_json:
        return canonical(
            {
                "schema": 1,
                "skill": {
                    "name": skill.name,
                    "content_hash": skill.content_hash,
                    "path": _path_text(skill.source_path),
                    "format": skill.format.value,
                },
                "priority": record.priority.value,
                "signals": list(record.signals),
                "note": TRIAGE_NOTE,
            }
        )
    return (
        f"skill: {_screen(skill.name)} {skill.content_hash[:12]}\n"
        f"format: {skill.format.value}\n"
        f"priority: {record.priority.value.upper()}\n"
        f"signals: {', '.join(record.signals) or 'none'}\n"
        f"note: {TRIAGE_NOTE}\n"
        "exit: 0\n"
    )


def render_mcp(report: ServerReport, as_json: bool) -> str:
    exit_code = 0 if report.started and report.error is None else 1
    if as_json:
        payload = report.to_payload()
        payload["schema"] = 1
        payload["note"] = MCP_NOTE
        payload["exit"] = exit_code
        return canonical(payload)
    lines = [
        f"server: {_one_line(report.server.name)}",
        f"command: {_one_line(' '.join([report.server.command, *report.server.args]))}",
        f"transport: {report.server.transport}",
        f"started: {'yes' if report.started else 'no'}",
    ]
    if report.protocol_version is not None:
        lines.append(f"protocol: {_one_line(report.protocol_version)}")
    lines.append(f"tools: {_one_line(', '.join(tool.name for tool in report.tools) or 'none')}")
    if report.session is not None:
        denials = ", ".join(
            f"{denial.kind.value} {denial.detail}" for denial in report.session.denials
        )
        lines.append(f"denials: {_one_line(denials or 'none')}")
    if report.error is not None:
        lines.append(f"error: {_one_line(report.error)}")
    lines.append(f"note: {MCP_NOTE}")
    lines.append(f"exit: {exit_code}")
    return "\n".join(lines) + "\n"


def render_bundle(bundle: Bundle, path: Path, as_json: bool) -> str:
    if as_json:
        return canonical(_bundle_report(bundle, path))
    lines = _summary_lines(
        bundle.trace.skill_name, bundle.trace.skill_content_hash, bundle.assessment
    )
    lines.append(f"bundle: {_path_text(path)}")
    lines.append(f"signer: {bundle.signature.signer}")
    lines.append("exit: 0")
    return "\n".join(lines) + "\n"


def render_verify(bundle: Bundle, path: Path, as_json: bool) -> str:
    if as_json:
        payload = _bundle_report(bundle, path)
        payload["verified"] = True
        payload["replay"] = True
        return canonical(payload)
    lines = [f"bundle: {_path_text(path)}"]
    lines.extend(
        _summary_lines(
            bundle.trace.skill_name, bundle.trace.skill_content_hash, bundle.assessment
        )
    )
    lines.append(f"trace: {bundle.trace.hash}")
    lines.append(
        f"sandbox: {', '.join(bundle.trace.sandbox_config_hashes) or 'none'}"
    )
    lines.append(f"signer: {bundle.signature.signer}")
    lines.append("signature: verified")
    lines.append("replay: verified")
    lines.append("exit: 0")
    return "\n".join(lines) + "\n"


def _bundle_report(bundle: Bundle, path: Path) -> dict[str, object]:
    return {
        "schema": 1,
        "bundle": _path_text(path),
        "skill": {
            "name": bundle.trace.skill_name,
            "content_hash": "sha256:" + bundle.trace.skill_content_hash,
        },
        "assessment": bundle.assessment.to_payload(),
        "trace_hash": bundle.trace.hash,
        "sandbox": list(bundle.trace.sandbox_config_hashes),
        "signer": bundle.signature.signer,
    }


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
