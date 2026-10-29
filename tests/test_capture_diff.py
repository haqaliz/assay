from pathlib import Path

import pytest

from assay.capture import (
    Dimension,
    DimensionStatus,
    DivergenceStatus,
    Event,
    EventKind,
    EventOutcome,
    Trace,
    diff,
)
from assay.ingest import Scope, Skill


def skill(scope):
    return Skill(
        name="demo",
        description="does a demo",
        scope=scope,
        body="BODY\n",
        source_path=Path("SKILL.md"),
        content_hash="a" * 64,
    )


def event(kind, target, outcome=EventOutcome.OK):
    return Event(
        kind=kind,
        outcome=outcome,
        target=target,
        content_sha256="c" * 64,
        content_bytes=0,
        excerpt="",
    )


def trace(*events):
    return Trace(
        skill_name="demo",
        skill_content_hash="a" * 64,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=tuple(events),
    )


def test_dimension_and_status_enums_are_the_closed_sets():
    assert {dimension.value for dimension in Dimension} == {
        "files",
        "network",
        "shell",
        "instructions",
    }
    assert {status.value for status in DimensionStatus} == {"declared", "undeclared"}
    assert {status.value for status in DivergenceStatus} == {"exceeded", "undeclared"}


def test_empty_trace_has_no_divergences_and_four_coverage_rows():
    result = diff(skill(Scope()), trace())

    assert result.divergences == ()
    assert [(row.dimension, row.declared, row.events) for row in result.coverage] == [
        (Dimension.FILES, False, 0),
        (Dimension.NETWORK, False, 0),
        (Dimension.SHELL, False, 0),
        (Dimension.INSTRUCTIONS, True, 0),
    ]
    assert all(
        row.declared
        for row in diff(skill(Scope(files=(), network=(), tools=())), trace()).coverage
    )


@pytest.mark.parametrize(
    "declared, target, expected",
    [
        (None, "out/x.txt", DivergenceStatus.UNDECLARED),
        ((), "out/x.txt", DivergenceStatus.EXCEEDED),
        (("./out/*",), "out/x.txt", None),
        (("out/*",), "out/a/b.txt", None),
        (("out/x.txt",), "./out/x.txt", None),
        (("in/*",), "out/x.txt", DivergenceStatus.EXCEEDED),
        (("out/*",), "../out/x.txt", DivergenceStatus.EXCEEDED),
    ],
)
def test_file_matrix(declared, target, expected):
    result = diff(skill(Scope(files=declared)), trace(event(EventKind.FILE_READ, target)))

    if expected is None:
        assert result.divergences == ()
    else:
        assert [(d.kind, d.target, d.status) for d in result.divergences] == [
            (EventKind.FILE_READ, target, expected)
        ]


def test_file_matrix_applies_to_writes_too():
    matched = diff(skill(Scope(files=("out/*",))), trace(event(EventKind.FILE_WRITE, "out/x")))
    exceeded = diff(skill(Scope(files=("in/*",))), trace(event(EventKind.FILE_WRITE, "out/x")))

    assert matched.divergences == ()
    assert [(d.kind, d.status) for d in exceeded.divergences] == [
        (EventKind.FILE_WRITE, DivergenceStatus.EXCEEDED)
    ]


@pytest.mark.parametrize(
    "declared, target, expected",
    [
        (None, "api.example.com:443", DivergenceStatus.UNDECLARED),
        ((), "api.example.com:443", DivergenceStatus.EXCEEDED),
        (("api.example.com:443",), "api.example.com:443", None),
        (("api.example.com",), "api.example.com:443", None),
        (("API.example.com:443",), "api.example.com:443", None),
        (("api.example.com:8443",), "api.example.com:443", DivergenceStatus.EXCEEDED),
        (("other.example.com:443",), "api.example.com:443", DivergenceStatus.EXCEEDED),
    ],
)
def test_network_matrix(declared, target, expected):
    result = diff(skill(Scope(network=declared)), trace(event(EventKind.NETWORK, target)))

    if expected is None:
        assert result.divergences == ()
    else:
        assert [(d.kind, d.target, d.status) for d in result.divergences] == [
            (EventKind.NETWORK, target, expected)
        ]


@pytest.mark.parametrize(
    "tools, expected",
    [
        (None, DivergenceStatus.UNDECLARED),
        (frozenset(), DivergenceStatus.EXCEEDED),
        (frozenset({"Bash"}), None),
        (frozenset({"Bash(git:*)", "Read"}), None),
        (frozenset({"Read", "Write"}), DivergenceStatus.EXCEEDED),
        (frozenset({"bash"}), DivergenceStatus.EXCEEDED),
    ],
)
def test_shell_matrix(tools, expected):
    result = diff(skill(Scope(tools=tools)), trace(event(EventKind.SHELL, "echo hi")))

    if expected is None:
        assert result.divergences == ()
    else:
        assert [(d.kind, d.target, d.status) for d in result.divergences] == [
            (EventKind.SHELL, "echo hi", expected)
        ]


def test_instructions_and_unknown_tools_never_diverge_but_are_counted():
    result = diff(
        skill(Scope(files=(), network=(), tools=frozenset())),
        trace(
            event(EventKind.INSTRUCTION, "system"),
            event(EventKind.INSTRUCTION, "user"),
            event(EventKind.TOOL, "mystery"),
        ),
    )

    assert result.divergences == ()
    assert [(row.dimension, row.events) for row in result.coverage] == [
        (Dimension.FILES, 0),
        (Dimension.NETWORK, 0),
        (Dimension.SHELL, 0),
        (Dimension.INSTRUCTIONS, 2),
    ]


def test_coverage_counts_events_per_dimension():
    result = diff(
        skill(Scope(files=(), network=(), tools=frozenset())),
        trace(
            event(EventKind.FILE_READ, "a"),
            event(EventKind.FILE_WRITE, "b"),
            event(EventKind.NETWORK, "a.example.com:443"),
            event(EventKind.SHELL, "true"),
            event(EventKind.TOOL, "mystery"),
        ),
    )

    assert [row.events for row in result.coverage] == [2, 1, 1, 0]


def test_divergence_reasons_name_the_scope_or_the_missing_declaration():
    undeclared = diff(
        skill(Scope()),
        trace(
            event(EventKind.FILE_READ, "out/x"),
            event(EventKind.NETWORK, "a.example.com:443"),
            event(EventKind.SHELL, "true"),
        ),
    )
    assert [divergence.reason for divergence in undeclared.divergences] == [
        "no file scope declared",
        "no network scope declared",
        "no tool scope declared",
    ]

    declared = diff(
        skill(Scope(files=(), network=("a.example.com:443",), tools=frozenset({"Read"}))),
        trace(
            event(EventKind.FILE_READ, "out/x"),
            event(EventKind.NETWORK, "b.example.com:443"),
            event(EventKind.SHELL, "true"),
        ),
    )
    assert [divergence.reason for divergence in declared.divergences] == [
        "file scope is declared empty",
        "no declared network entry matches 'b.example.com:443'",
        "tool scope does not declare Bash",
    ]


@pytest.mark.parametrize("outcome", [EventOutcome.DENIED, EventOutcome.FAILED])
def test_denied_and_failed_file_events_diverge_like_successful_ones(outcome):
    result = diff(
        skill(Scope(files=())),
        trace(event(EventKind.FILE_READ, "out/x", outcome)),
    )
    assert [(d.target, d.status) for d in result.divergences] == [
        ("out/x", DivergenceStatus.EXCEEDED)
    ]
