import shutil
import subprocess
from pathlib import Path

import pytest

from assay.bundle import Bundle, build, replay, verify
from assay.corpus import load_corpus

REPO = Path(__file__).resolve().parents[1]

requires_ssh_keygen = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed"
)


def generate_key(path: Path) -> None:
    subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "assay-replay-test",
            "-f",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


@requires_ssh_keygen
def test_a_corpus_case_builds_verifies_and_replays(tmp_path):
    private_key = tmp_path / "key"
    generate_key(private_key)
    case = load_corpus(REPO / "corpus")[0]
    source = (case.path / "SKILL.md").read_bytes().decode("utf-8")

    bundle = build(case.skill, source, case.trace, case.strictness, private_key)

    assert verify(bundle, private_key.with_suffix(".pub")) is None
    assert bundle.skill.source == source
    assert replay(Bundle.from_json(bundle.to_json())) == bundle.assessment
