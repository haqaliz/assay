from dataclasses import replace
from pathlib import Path

from assay.sandbox import JailConfig
from assay.sandbox.bubblewrap import BubblewrapSandbox


def make_config(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    return JailConfig(run_root=root)


def test_backend_is_part_of_the_config_hash(tmp_path):
    base = make_config(tmp_path)
    seatbelt = replace(base, backend="seatbelt")
    bubblewrap = replace(base, backend="bubblewrap")

    assert len({base.config_hash, seatbelt.config_hash, bubblewrap.config_hash}) == 3


def test_bubblewrap_run_records_its_backend_and_network_mode(tmp_path):
    bwrap = tmp_path / "bwrap"
    bwrap.write_text("#!/bin/sh\nexec /bin/true\n")
    bwrap.chmod(0o755)
    config = make_config(tmp_path)
    expected_hash = replace(config, backend="bubblewrap").config_hash

    record = BubblewrapSandbox(bwrap).run(["/bin/true"], config)

    assert record.backend == "bubblewrap"
    assert record.network_mode == "none"
    assert record.config_hash == expected_hash
