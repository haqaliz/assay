import pytest

from assay.sandbox import JailConfig, Limits, NetRule


def test_run_root_must_be_absolute(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        JailConfig(run_root=tmp_path.relative_to(tmp_path))


def test_run_root_must_exist(tmp_path):
    with pytest.raises(ValueError, match="exist"):
        JailConfig(run_root=tmp_path / "missing")


def test_run_root_must_be_a_directory(tmp_path):
    f = tmp_path / "file"
    f.write_text("x")
    with pytest.raises(ValueError, match="directory"):
        JailConfig(run_root=f)


def test_run_root_must_not_be_a_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        JailConfig(run_root=link)


def test_rejects_paths_with_quotes(tmp_path):
    """Profile strings interpolate paths; a quote would break out of the filter."""
    root = tmp_path / 'we"ird'
    root.mkdir()
    with pytest.raises(ValueError, match="quote"):
        JailConfig(run_root=root)


def test_netrule_rejects_ip_hosts(tmp_path):
    with pytest.raises(ValueError, match="localhost"):
        NetRule(host="1.1.1.1", port=443)


def test_netrule_rejects_bad_port():
    with pytest.raises(ValueError, match="port"):
        NetRule(port=0)
    with pytest.raises(ValueError, match="port"):
        NetRule(port=70000)
    with pytest.raises(ValueError, match="port"):
        NetRule(port=True)  # bool is an int subclass


def test_limits_must_be_positive():
    with pytest.raises(ValueError, match="wall_seconds"):
        Limits(wall_seconds=0)
    with pytest.raises(ValueError, match="cpu_seconds"):
        Limits(cpu_seconds=-1)
    with pytest.raises(ValueError, match="file_bytes"):
        Limits(file_bytes=0)


def test_env_must_be_strings(tmp_path):
    with pytest.raises(ValueError, match="env"):
        JailConfig(run_root=tmp_path, env={"TOKEN": 1})


def test_hash_is_stable_across_key_order_and_run_root(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    one = JailConfig(run_root=a, env={"A": "1", "B": "2"}, allow_network=(NetRule("localhost", 80),))
    two = JailConfig(run_root=b, env={"B": "2", "A": "1"}, allow_network=(NetRule("localhost", 80),))
    assert one.config_hash == two.config_hash
    assert one.config_hash.startswith("sha256:")


def test_hash_changes_when_operational_field_changes(tmp_path):
    base = JailConfig(run_root=tmp_path)
    assert base.config_hash != JailConfig(run_root=tmp_path, env={"X": "1"}).config_hash
    assert base.config_hash != JailConfig(run_root=tmp_path, limits=Limits(wall_seconds=10)).config_hash
    assert base.config_hash != JailConfig(
        run_root=tmp_path, allow_network=(NetRule("*", 443),)
    ).config_hash
