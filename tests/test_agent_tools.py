from pathlib import Path

import pytest

from assay.agent import AgentUnavailable, ToolCall
from assay.agent import tools
from assay.agent.tools import MAX_TOOL_PAYLOAD_BYTES, TOOLS, Toolbox
from assay.sandbox import (
    DenialClass,
    DenialRecord,
    NetRule,
    RunRecord,
    SandboxFailed,
    SandboxUnavailable,
)


def record(**over):
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
        started_at="2026-10-29T00:00:00Z",
    )
    base.update(over)
    return RunRecord(**base)


class FakeSandbox:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result if result is not None else record()
        self.error = error

    def run(self, argv, config):
        self.calls.append((list(argv), config))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def run_root(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    return root


@pytest.fixture
def fake_curl(tmp_path, monkeypatch):
    curl = tmp_path / "curl"
    curl.write_text("")
    monkeypatch.setattr(tools, "CURL", curl)
    return curl


def box(sandbox, run_root, fake_curl):
    return Toolbox(sandbox, run_root)


def call(name, **arguments):
    return ToolCall(id="t1", name=name, arguments=arguments)


def test_tools_always_offer_the_four_floor_classes():
    assert [spec.name for spec in TOOLS] == ["read_file", "write_file", "run_shell", "http_get"]
    for spec in TOOLS:
        assert spec.input_schema["type"] == "object"
        assert spec.input_schema["properties"]
        assert spec.input_schema["required"]


def test_run_root_must_be_an_existing_real_directory(fake_curl, tmp_path):
    with pytest.raises(SandboxUnavailable):
        Toolbox(FakeSandbox(), tmp_path / "missing")
    plain = tmp_path / "plain"
    plain.write_text("")
    with pytest.raises(SandboxUnavailable):
        Toolbox(FakeSandbox(), plain)
    link = tmp_path / "link"
    link.symlink_to(tmp_path)
    with pytest.raises(SandboxUnavailable):
        Toolbox(FakeSandbox(), link)


def test_missing_curl_is_unavailable_at_construction(run_root, tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "CURL", tmp_path / "no-curl")
    with pytest.raises(AgentUnavailable, match="missing-tool"):
        Toolbox(FakeSandbox(), run_root)


def test_read_file_is_one_confined_cat_with_no_network(run_root, fake_curl):
    sandbox = FakeSandbox(record(stdout="hello\n"))
    result = box(sandbox, run_root, fake_curl).execute(call("read_file", path="notes/a.txt"))
    (argv, config), = sandbox.calls
    assert argv == ["/bin/cat", "--", "notes/a.txt"]
    assert config.allow_network == ()
    assert config.env == {}
    assert config.run_root == run_root.resolve()
    assert config.keep is True
    assert result.ok
    assert result.output == "hello\n"
    assert result.record is sandbox.result


def test_write_file_stages_outside_the_run_root_then_copies_it(run_root, fake_curl):
    seen = []

    class CapturingSandbox:
        def run(self, argv, config):
            seen.append((list(argv), Path(argv[2]).read_text(), config))
            return record()

    toolbox = Toolbox(CapturingSandbox(), run_root)
    result = toolbox.execute(call("write_file", path="out.md", content="hi there"))
    (argv, staged_content, config), = seen
    assert argv[0] == "/bin/cp"
    assert argv[1] == "--"
    assert argv[3] == "out.md"
    staged = Path(argv[2])
    assert toolbox.io_root in staged.parents
    assert run_root.resolve() not in staged.parents
    assert config.allow_read_extra == (toolbox.io_root,)
    assert staged_content == "hi there"
    assert result.ok
    assert list(toolbox.io_root.iterdir()) == []
    toolbox.close()
    assert not toolbox.io_root.exists()


def test_write_file_refuses_an_oversized_payload_without_running(run_root, fake_curl):
    sandbox = FakeSandbox()
    toolbox = Toolbox(sandbox, run_root)
    result = toolbox.execute(
        call("write_file", path="big.bin", content="x" * (MAX_TOOL_PAYLOAD_BYTES + 1))
    )
    assert not result.ok
    assert result.record is None
    assert sandbox.calls == []


def test_run_shell_is_one_sh_with_no_network(run_root, fake_curl):
    sandbox = FakeSandbox()
    box(sandbox, run_root, fake_curl).execute(call("run_shell", command="echo hi"))
    (argv, config), = sandbox.calls
    assert argv == ["/bin/sh", "-c", "echo hi"]
    assert config.allow_network == ()


def test_http_get_is_curl_with_ports_80_and_443_only(run_root, fake_curl):
    sandbox = FakeSandbox()
    box(sandbox, run_root, fake_curl).execute(call("http_get", url="https://203.0.113.10/x"))
    (argv, config), = sandbox.calls
    assert argv == [
        str(fake_curl),
        "-sS",
        "--max-time",
        "10",
        "--url",
        "https://203.0.113.10/x",
    ]
    assert config.allow_network == (NetRule("*", 80), NetRule("*", 443))


def test_http_get_resolves_a_hostname_in_the_parent(run_root, fake_curl, monkeypatch):
    monkeypatch.setattr(tools, "_resolve", lambda host, port: "203.0.113.10")
    sandbox = FakeSandbox()
    box(sandbox, run_root, fake_curl).execute(call("http_get", url="https://example.com/x"))
    (argv, _), = sandbox.calls
    assert "--resolve" in argv
    assert argv[argv.index("--resolve") + 1] == "example.com:443:203.0.113.10"


@pytest.mark.parametrize(
    "url",
    ["file:///etc/hosts", "-Kcfg", "ftp://example.com", "https://", "gopher://x"],
)
def test_http_get_refuses_non_http_urls_and_curl_options(run_root, fake_curl, url):
    sandbox = FakeSandbox()
    result = Toolbox(sandbox, run_root).execute(call("http_get", url=url))
    assert not result.ok
    assert sandbox.calls == []


@pytest.mark.parametrize(
    "bad_call",
    [
        call("no_such_tool"),
        ToolCall(id="t", name="read_file", arguments={}),
        call("read_file", path=""),
        call("read_file", path=3),
        call("write_file", path="a.txt"),
        call("write_file", path="a.txt", content=""),
        call("write_file", path=1, content="x"),
        call("run_shell", command=None),
        call("run_shell", command=""),
        call("http_get", url=""),
        call("http_get", url=["https://example.com"]),
        call("read_file", path="a\x00b"),
        call("read_file", path="a\ud800b"),
        call("write_file", path="a.txt", content="\ud800"),
    ],
)
def test_invalid_tool_calls_fail_without_running_the_sandbox(run_root, fake_curl, bad_call):
    sandbox = FakeSandbox()
    result = Toolbox(sandbox, run_root).execute(bad_call)
    assert not result.ok
    assert result.record is None
    assert sandbox.calls == []


def test_every_action_gets_a_scrubbed_env_and_the_shared_run_root(run_root, fake_curl):
    sandbox = FakeSandbox()
    toolbox = Toolbox(sandbox, run_root)
    for each in (
        call("read_file", path="a"),
        call("write_file", path="b", content="x"),
        call("run_shell", command="true"),
        call("http_get", url="https://203.0.113.10"),
    ):
        toolbox.execute(each)
    assert len(sandbox.calls) == 4
    for argv, config in sandbox.calls:
        assert config.env == {}
        assert "ANTHROPIC_API_KEY" not in config.env
        assert config.run_root == toolbox.run_root


def test_denied_run_is_not_ok_and_keeps_its_denials(run_root, fake_curl):
    denial = DenialRecord(DenialClass.FILE_WRITE, "cp: ../escape.md: Permission denied")
    denied = record(exit_code=1, stderr=denial.detail, denials=(denial,))
    result = box(FakeSandbox(denied), run_root, fake_curl).execute(
        call("write_file", path="../escape.md", content="x")
    )
    assert not result.ok
    assert result.record is denied
    assert result.record.denials == (denial,)
    assert "Permission denied" in result.output


def test_sandbox_failure_becomes_a_failed_result_not_an_exception(run_root, fake_curl):
    error = SandboxFailed("no jail")
    result = box(FakeSandbox(error=error), run_root, fake_curl).execute(
        call("read_file", path="a.txt")
    )
    assert not result.ok
    assert result.record is None
    assert str(error) in result.output


def test_sandbox_unavailable_propagates_so_the_driver_can_name_it(run_root, fake_curl):
    with pytest.raises(SandboxUnavailable):
        box(FakeSandbox(error=SandboxUnavailable("no backend")), run_root, fake_curl).execute(
            call("read_file", path="a.txt")
        )


def test_long_output_is_capped_to_one_megabyte_of_utf8(run_root, fake_curl):
    sandbox = FakeSandbox(record(stdout="é" * (MAX_TOOL_PAYLOAD_BYTES + 100)))
    result = box(sandbox, run_root, fake_curl).execute(call("read_file", path="a"))
    assert result.ok
    assert len(result.output.encode("utf-8")) <= MAX_TOOL_PAYLOAD_BYTES
