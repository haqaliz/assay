import hashlib
import json

import pytest

from assay.mcp.server import Server, ServerError, parse_server


def write(tmp_path, payload, name="mcp.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_mcp_servers_selects_the_only_entry(tmp_path):
    path = write(
        tmp_path,
        {
            "mcpServers": {
                "demo": {"command": "python3", "args": ["-u", "server.py"]}
            }
        },
    )

    server = parse_server(path)

    assert isinstance(server, Server)
    assert server.name == "demo"
    assert server.command == "python3"
    assert server.args == ("-u", "server.py")
    assert server.transport == "stdio"
    assert server.source_path == path
    assert server.source_hash == hashlib.sha256(path.read_bytes()).hexdigest()


def test_multiple_servers_need_a_name(tmp_path):
    path = write(
        tmp_path,
        {
            "mcpServers": {
                "demo": {"command": "python3"},
                "other": {"command": "node"},
            }
        },
    )

    with pytest.raises(ServerError, match="demo"):
        parse_server(path)
    assert parse_server(path, name="other").command == "node"
    with pytest.raises(ServerError, match="missing"):
        parse_server(path, name="missing")


def test_a_named_entry_must_match_when_one_exists(tmp_path):
    path = write(tmp_path, {"mcpServers": {"demo": {"command": "python3"}}})

    with pytest.raises(ServerError, match="other"):
        parse_server(path, name="other")


def test_a_single_object_uses_the_name_or_file_stem(tmp_path):
    path = write(tmp_path, {"command": "python3"}, name="demo.json")

    assert parse_server(path).name == "demo"
    assert parse_server(path, name="custom").name == "custom"


def test_env_values_are_refused_and_never_echoed(tmp_path):
    path = write(
        tmp_path,
        {"command": "python3", "env": {"API_KEY": "super-secret-value"}},
    )

    with pytest.raises(ServerError) as exc:
        parse_server(path)

    assert "env" in str(exc.value).lower()
    assert "super-secret-value" not in str(exc.value)


def test_an_empty_env_is_allowed(tmp_path):
    path = write(tmp_path, {"command": "python3", "env": {}})

    assert parse_server(path).command == "python3"


def test_url_transport_is_refused(tmp_path):
    path = write(tmp_path, {"command": "python3", "url": "https://example.test"})

    with pytest.raises(ServerError, match="stdio"):
        parse_server(path)


def test_command_is_required(tmp_path):
    path = write(tmp_path, {"args": ["-u"]})

    with pytest.raises(ServerError, match="command"):
        parse_server(path)

    path = write(tmp_path, {"command": ""})
    with pytest.raises(ServerError, match="command"):
        parse_server(path)


def test_args_must_be_a_list_of_strings(tmp_path):
    path = write(tmp_path, {"command": "python3", "args": "server.py"})
    with pytest.raises(ServerError, match="args"):
        parse_server(path)

    path = write(tmp_path, {"command": "python3", "args": ["ok", 3]})
    with pytest.raises(ServerError, match="args"):
        parse_server(path)


def test_malformed_json_is_a_server_error(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ServerError, match="JSON"):
        parse_server(path)


def test_a_root_without_a_server_is_refused(tmp_path):
    path = write(tmp_path, {"mcpServers": {}})

    with pytest.raises(ServerError, match="server"):
        parse_server(path)
