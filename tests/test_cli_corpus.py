import importlib
import json

import pytest

from assay.canonical import canonical
from assay.capture import Event, EventKind, EventOutcome, Trace, TraceStore
from assay.ingest import parse_skill

cli_main = importlib.import_module("assay.cli.main")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST"):
        monkeypatch.delenv(name, raising=False)


def event(kind, target):
    return Event(
        kind=kind,
        outcome=EventOutcome.OK,
        target=target,
        content_sha256="d" * 64,
        content_bytes=2,
        excerpt="hi",
    )


def skill_text(*, tools="Read", files=None, network=None):
    metadata = []
    if files is not None:
        metadata.append(f"    files: {json.dumps(files)}")
    if network is not None:
        metadata.append(f"    network: {json.dumps(network)}")
    scope = "metadata:\n  assay:\n" + "\n".join(metadata) + "\n" if metadata else ""
    return (
        "---\n"
        "name: demo\n"
        "description: A demo skill.\n"
        f"allowed-tools: {tools}\n"
        f"{scope}"
        "---\nBody.\n"
    )


def make_case(
    root,
    case_id,
    *,
    label,
    files=None,
    network=None,
    tools="Read",
    events=(),
    cause=None,
):
    directory = root / case_id
    directory.mkdir()
    (directory / "SKILL.md").write_text(
        skill_text(tools=tools, files=files, network=network), encoding="utf-8"
    )
    skill = parse_skill(directory / "SKILL.md")
    trace = Trace(
        skill_name=skill.name,
        skill_content_hash=skill.content_hash,
        task_sha256="b" * 64,
        cause=cause,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=tuple(events),
        sandbox_config_hashes=(),
    )
    saved = TraceStore(directory).save(trace)
    payload = {
        "schema": 1,
        "id": case_id,
        "label": label,
        "labeler": "aliz",
        "labeled_at": "2026-11-03",
        "rationale": "It does what the skill says.",
        "source": "synthetic",
        "strictness": "standard",
        "trace": saved.name,
        "expected_classes": [],
    }
    (directory / "case.json").write_text(json.dumps(payload), encoding="utf-8")
    return directory


def make_corpus(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    make_case(
        root,
        "malicious-shell",
        label="malicious",
        files=[],
        network=[],
        events=[event(EventKind.SHELL, "rm -rf /")],
    )
    make_case(
        root,
        "malicious-flagged",
        label="malicious",
        files=[],
        network=[],
        events=[event(EventKind.SHELL, "find .")],
    )
    make_case(
        root,
        "clean-read",
        label="clean",
        files=["in.txt"],
        network=[],
        events=[event(EventKind.FILE_READ, "in.txt")],
    )
    make_case(
        root,
        "clean-flagged",
        label="clean",
        events=[event(EventKind.FILE_WRITE, "/Users/aliz/Desktop/report.md")],
    )
    make_case(
        root,
        "clean-budget",
        label="clean",
        files=["in.txt"],
        network=[],
        events=[event(EventKind.FILE_READ, "in.txt")],
        cause="step-limit",
    )
    return root


def test_corpus_human_report_is_exact(tmp_path, capsys):
    root = make_corpus(tmp_path)

    assert cli_main.main(["corpus", str(root)]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        f"corpus: {root}\n"
        "cases: 5 (malicious 2, clean 3)\n"
        "decided: 4 (malicious 2, clean 2) | unverified: 1 (budget-limit 1)\n"
        "verdict     malicious  clean\n"
        "malicious           1      0\n"
        "flagged             1      1\n"
        "clean               0      1\n"
        "malicious precision: 1.00 (1/1)\n"
        "malicious recall: 0.50 (1/2); detected with any finding: 1.00 (2/2)\n"
        "clean false-malicious: 0.00 (0/2)\n"
        "clean review: 0.50 (1/2)\n"
        "coverage: 0.80 (4/5)\n"
        "false malicious: none\n"
        "false negatives: none\n"
        "labels: aliz (5)\n"
        "sources: synthetic 5\n"
        "exit: 0\n"
    )


def test_corpus_json_is_canonical_and_byte_stable(tmp_path, capsys):
    root = make_corpus(tmp_path)
    argv = ["corpus", str(root), "--json"]

    assert cli_main.main(argv) == 0
    first = capsys.readouterr().out
    assert cli_main.main(argv) == 0
    second = capsys.readouterr().out

    assert first == second
    assert first.count("\n") == 1
    payload = json.loads(first)
    assert first == canonical(payload)
    assert set(payload) == {
        "schema",
        "corpus",
        "total",
        "by_label",
        "decided",
        "unverified",
        "unverified_by_cause",
        "confusion",
        "malicious_precision",
        "malicious_recall",
        "detection_recall",
        "clean_false_malicious",
        "clean_review",
        "coverage",
        "false_malicious_cases",
        "false_negative_cases",
        "labelers",
        "sources",
        "cases",
    }
    assert payload["schema"] == 1
    assert payload["corpus"] == str(root)
    assert payload["total"] == 5
    assert payload["unverified_by_cause"]["budget-limit"] == 1


def test_corpus_exits_zero_when_metrics_are_poor(tmp_path, capsys):
    root = tmp_path / "corpus"
    root.mkdir()
    make_case(
        root,
        "false-negative",
        label="malicious",
        files=["in.txt"],
        network=[],
        events=[event(EventKind.FILE_READ, "in.txt")],
    )

    assert cli_main.main(["corpus", str(root)]) == 0
    report = capsys.readouterr().out
    assert "false negatives: false-negative\n" in report
    assert "malicious precision: n/a (0/0)\n" in report

    assert cli_main.main(["corpus", str(root), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["malicious_precision"]["value"] is None
    assert payload["false_negative_cases"] == ["false-negative"]


def test_corpus_refuses_a_missing_directory(tmp_path, capsys):
    missing = tmp_path / "missing"

    assert cli_main.main(["corpus", str(missing)]) == 1

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith(
        f"corpus: {missing}\ncause: CORPUS_UNREADABLE\ndetail: "
    )
    assert captured.out.endswith("\nexit: 1\n")
    assert "Traceback" not in captured.out


def test_corpus_refuses_an_empty_directory(tmp_path, capsys):
    root = tmp_path / "corpus"
    root.mkdir()

    assert cli_main.main(["corpus", str(root)]) == 1

    captured = capsys.readouterr()
    assert captured.out.startswith(f"corpus: {root}\ncause: CORPUS_EMPTY\ndetail: ")
    assert captured.out.endswith("\nexit: 1\n")


def test_corpus_refuses_a_broken_case(tmp_path, capsys):
    root = tmp_path / "corpus"
    root.mkdir()
    directory = make_case(root, "broken-case", label="malicious", files=[], network=[])
    payload = json.loads((directory / "case.json").read_text(encoding="utf-8"))
    payload["label"] = "evil"
    (directory / "case.json").write_text(json.dumps(payload), encoding="utf-8")

    assert cli_main.main(["corpus", str(root)]) == 1

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "cause: CASE_INVALID\n" in captured.out
    assert (
        "detail: broken-case: label must be one of malicious, clean, got 'evil'\n"
        in captured.out
    )
    assert captured.out.endswith("exit: 1\n")
    assert "Traceback" not in captured.out


def test_corpus_json_refusal_has_schema_corpus_cause_detail(tmp_path, capsys):
    missing = tmp_path / "missing"

    assert cli_main.main(["corpus", str(missing), "--json"]) == 1

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert out == canonical(payload)
    assert set(payload) == {"schema", "corpus", "cause", "detail"}
    assert payload["schema"] == 1
    assert payload["corpus"] == str(missing)
    assert payload["cause"] == "corpus-unreadable"
    assert "missing" in payload["detail"]
