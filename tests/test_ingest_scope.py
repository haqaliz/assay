from pathlib import Path

import pytest

from assay.ingest import ParseCause, Scope, SkillParseError
from assay.ingest.claude import _scope

PATH = Path("scope/SKILL.md")


def test_allowed_tools_is_a_comma_separated_string():
    assert _scope({"allowed-tools": "Read, Grep, Glob, Bash, Write"}, PATH) == Scope(
        tools={"Read", "Grep", "Glob", "Bash", "Write"}
    )


def test_allowed_tools_accepts_the_yaml_list_form_used_by_official_plugins():
    assert _scope({"allowed-tools": ["Read", "Write", "Bash(git *)"]}, PATH) == Scope(
        tools={"Read", "Write", "Bash(git *)"}
    )


def test_explicitly_empty_allowed_tools_list_is_declared_none():
    assert _scope({"allowed-tools": []}, PATH).tools == frozenset()


def test_allowed_tools_list_with_an_empty_member_is_refused():
    with pytest.raises(SkillParseError) as caught:
        _scope({"allowed-tools": ["Read", ""]}, PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE


def test_allowed_tools_list_with_a_non_string_member_is_refused():
    with pytest.raises(SkillParseError) as caught:
        _scope({"allowed-tools": ["Read", 1]}, PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE


def test_absent_allowed_tools_is_undeclared_not_empty():
    assert _scope({}, PATH).tools is None


def test_absent_metadata_assay_leaves_files_and_network_undeclared():
    scope = _scope({"metadata": {"owner": "someone"}}, PATH)
    assert scope.files is None
    assert scope.network is None


def test_explicitly_empty_assay_lists_are_declared_none():
    scope = _scope({"metadata": {"assay": {"files": [], "network": []}}}, PATH)
    assert scope.files == ()
    assert scope.network == ()
    assert scope != Scope()


def test_assay_lists_preserve_order_and_values():
    mapping = {"metadata": {"assay": {"files": ["./out/**", "report.md"], "network": ["api.example.com:443"]}}}
    scope = _scope(mapping, PATH)
    assert scope.files == ("./out/**", "report.md")
    assert scope.network == ("api.example.com:443",)


@pytest.mark.parametrize(
    "mapping",
    [
        {"allowed-tools": ""},
        {"allowed-tools": 3},
        {"allowed-tools": "Read,"},
        {"metadata": "not-a-mapping"},
        {"metadata": {"assay": "not-a-mapping"}},
        {"metadata": {"assay": {"files": "./out/**"}}},
        {"metadata": {"assay": {"files": ["ok", 3]}}},
        {"metadata": {"assay": {"files": ["ok", ""]}}},
        {"metadata": {"assay": {"files": ["  "]}}},
        {"metadata": {"assay": {"network": {"host": "x"}}}},
        {"metadata": {"assay": {"network": [None]}}},
    ],
)
def test_bad_scope_shapes_are_invalid_scope(mapping):
    with pytest.raises(SkillParseError) as caught:
        _scope(mapping, PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE


def test_unknown_keys_and_foreign_metadata_are_ignored():
    mapping = {
        "name": "extras",
        "license": "MIT",
        "homepage": "https://example.com",
        "compatibility": "claude",
        "version": "1.2.3",
        "model": "opus",
        "effort": "high",
        "argument-hint": "[file]",
        "tags": ["a", "b"],
        "metadata": {"owner": "someone", "assay": {"files": ["out.md"]}},
    }
    assert _scope(mapping, PATH).files == ("out.md",)
