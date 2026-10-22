import pytest

from assay.sandbox import JailConfig, NetRule
from assay.sandbox.seatbelt import HOST_DATA_DENY, build_profile


def profile(tmp_path, config=None):
    return build_profile(config or JailConfig(run_root=tmp_path))


def test_starts_closed(tmp_path):
    assert "(deny default)" in profile(tmp_path)


def test_every_host_data_path_is_denied(tmp_path):
    text = profile(tmp_path)
    for path in HOST_DATA_DENY:
        assert f'(subpath "{path}")' in text


def test_run_root_is_readable_and_writable(tmp_path):
    text = profile(tmp_path)
    assert f'(allow file-read* (subpath "{tmp_path}")' in text
    assert f'(allow file-write* (subpath "{tmp_path}")' in text


def test_dev_null_is_writable(tmp_path):
    assert '(literal "/dev/null")' in profile(tmp_path)


def test_extra_read_paths_are_allowed(tmp_path):
    extra = tmp_path / "corpus"
    extra.mkdir()
    text = profile(tmp_path, JailConfig(run_root=tmp_path, allow_read_extra=(extra,)))
    assert f'(subpath "{extra}")' in text


def test_no_network_rule_when_allowlist_is_empty(tmp_path):
    assert "(allow network" not in profile(tmp_path)


def test_network_rules_are_port_scoped(tmp_path):
    config = JailConfig(run_root=tmp_path, allow_network=(NetRule("localhost", 8931),))
    text = profile(tmp_path, config)
    assert '(allow network-outbound (remote tcp "localhost:8931"))' in text


def test_multiple_network_rules(tmp_path):
    config = JailConfig(
        run_root=tmp_path, allow_network=(NetRule("*", 443), NetRule("localhost", 80))
    )
    text = profile(tmp_path, config)
    assert text.count("network-outbound") == 2
    assert '(allow network-outbound (remote tcp "*:443"))' in text


def test_no_wildcard_network_grant_ever(tmp_path):
    config = JailConfig(run_root=tmp_path, allow_network=(NetRule("*", 443),))
    text = profile(tmp_path, config)
    assert "(allow network*)" not in text
    assert "(allow network-outbound)" not in text


def test_profile_is_deterministic(tmp_path):
    config = JailConfig(run_root=tmp_path, allow_network=(NetRule("*", 443),), env={"A": "1"})
    assert build_profile(config) == build_profile(config)
