import pytest

from assay.sandbox import DenialClass
from assay.sandbox.denials import DENIAL_MARKER, classify_failure


def kinds(stderr, limit_exceeded=None):
    return [d.kind for d in classify_failure(stderr, limit_exceeded)]


def test_no_stderr_no_denials():
    assert classify_failure("") == ()


def test_limit_breach_is_first_and_named():
    records = classify_failure("", "wall_seconds")
    assert records[0].kind is DenialClass.LIMIT
    assert records[0].detail == "wall_seconds"


def test_structured_marker_is_trusted_and_typed():
    records = classify_failure("assay-denial: network 1.1.1.1:80 refused")
    assert records[0].kind is DenialClass.NETWORK
    assert "1.1.1.1:80" in records[0].detail


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("assay-denial: file-read /etc/passwd", DenialClass.FILE_READ),
        ("assay-denial: file-write /tmp/x", DenialClass.FILE_WRITE),
        ("assay-denial: process fork denied", DenialClass.PROCESS),
        ("assay-denial: limit cpu", DenialClass.LIMIT),
        ("assay-denial: nonsense whatever", DenialClass.UNKNOWN),
    ],
)
def test_marker_kinds(line, kind):
    assert kinds(line) == [kind]


def test_marker_without_detail_keeps_the_line():
    records = classify_failure("assay-denial: network")
    assert records[0].kind is DenialClass.NETWORK
    assert records[0].detail == "network"


def test_marker_works_mid_line():
    assert kinds("some log prefix assay-denial: file-read /etc/passwd") == [DenialClass.FILE_READ]


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("PermissionError: [Errno 1] Operation not permitted", DenialClass.UNKNOWN),
        ("socket.connect failed: Operation not permitted", DenialClass.NETWORK),
        ("cannot open ~/.ssh/id_rsa: Permission denied (read)", DenialClass.FILE_READ),
        ("sh: cannot create /etc/x: Permission denied (write)", DenialClass.FILE_WRITE),
    ],
)
def test_heuristic_lines(line, kind):
    assert kinds(line) == [kind]


def test_unrelated_stderr_is_ignored():
    assert kinds("Traceback (most recent call last):\n  boom") == []


def test_duplicates_collapse():
    line = "socket.connect: Operation not permitted"
    assert kinds(f"{line}\n{line}\n{line}") == [DenialClass.NETWORK]


def test_detail_is_truncated():
    records = classify_failure("assay-denial: network " + "x" * 500)
    assert len(records[0].detail) == 200


def test_marker_constant_is_stable():
    assert DENIAL_MARKER == "assay-denial:"
