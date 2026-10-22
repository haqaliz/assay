from assay.sandbox import DenialClass, DenialRecord, RunRecord


def _record(**over):
    base = dict(
        exit_code=0,
        signal=None,
        duration_s=0.1,
        stdout="",
        stderr="",
        truncated=False,
        denials=(),
        limit_exceeded=None,
        config_hash="sha256:x",
        run_root="/tmp/run",
        started_at="2026-10-23T00:00:00Z",
    )
    base.update(over)
    return RunRecord(**base)


def test_ok_on_clean_exit():
    assert _record().ok


def test_not_ok_on_nonzero_exit():
    assert not _record(exit_code=1).ok


def test_not_ok_on_signal():
    assert not _record(exit_code=137, signal=9).ok


def test_not_ok_on_limit_breach():
    assert not _record(limit_exceeded="wall_seconds").ok


def test_denial_kinds_are_stable_strings():
    assert DenialClass.NETWORK == "network"
    assert DenialRecord(DenialClass.NETWORK, "1.1.1.1:80").kind is DenialClass.NETWORK
