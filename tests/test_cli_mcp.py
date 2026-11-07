import json
import shutil
import sys
from pathlib import Path

import pytest

from assay.cli.main import main

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
    reason="Seatbelt is macOS-only",
)

FIXTURE = Path(__file__).parent / "fixtures" / "mcp_server.py"


def write_manifest(tmp_path, payload, name="mcp.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def manifest_for_fixture(tmp_path):
    fixture = tmp_path / "mcp_server.py"
    shutil.copy2(FIXTURE, fixture)
    return write_manifest(
        tmp_path,
        {"command": "/usr/bin/python3", "args": ["-u", str(fixture)]},
    )


def test_the_cli_inspects_the_fixture(capsys, tmp_path):
    manifest = manifest_for_fixture(tmp_path)

    code = main(["mcp", str(manifest)])
    out = capsys.readouterr().out

    assert code == 0
    assert "started: yes" in out
    assert "tools: echo, read_inside, read_outside, slow" in out
    assert "note: inspection only; no verdict." in out
    assert "CLEAN" not in out
    assert "FLAGGED" not in out
    assert "MALICIOUS" not in out


def test_the_cli_json_has_no_verdict(capsys, tmp_path):
    manifest = manifest_for_fixture(tmp_path)

    code = main(["mcp", str(manifest), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert code == 0
    assert payload["started"] is True
    assert payload["protocol_version"] == "2026-07-28"
    assert payload["note"] == "inspection only; no verdict."
    assert payload["exit"] == 0
    assert "verdict" not in payload
    assert "findings" not in payload
    assert {tool["name"] for tool in payload["tools"]} == {
        "echo",
        "read_inside",
        "read_outside",
        "slow",
    }


def test_the_cli_reports_a_missing_command(capsys, tmp_path):
    manifest = write_manifest(tmp_path, {"command": "/no/such/mcp-command"})

    code = main(["mcp", str(manifest)])
    out = capsys.readouterr().out

    assert code == 1
    assert "started: no" in out
    assert "error:" in out
    assert "note: inspection only; no verdict." in out


def test_the_cli_refuses_malformed_json(capsys, tmp_path):
    manifest = tmp_path / "mcp.json"
    manifest.write_text("{not json", encoding="utf-8")

    code = main(["mcp", str(manifest)])
    captured = capsys.readouterr()

    assert code == 2
    assert "error:" in captured.err
    assert captured.out == ""


def test_the_cli_needs_a_name_for_multiple_servers(capsys, tmp_path):
    fixture = tmp_path / "mcp_server.py"
    shutil.copy2(FIXTURE, fixture)
    manifest = write_manifest(
        tmp_path,
        {
            "mcpServers": {
                "good": {"command": "/usr/bin/python3", "args": ["-u", str(fixture)]},
                "bad": {"command": "/no/such/mcp-command"},
            }
        },
    )

    assert main(["mcp", str(manifest)]) == 2
    assert "choose --name" in capsys.readouterr().err

    assert main(["mcp", str(manifest), "--name", "good"]) == 0
    assert "server: good" in capsys.readouterr().out
