from assay.canonical import canonical
from assay.cli.output import canonical as cli_canonical


def test_canonical_sorts_keys():
    assert canonical({"b": 2, "a": 1}) == '{"a":1,"b":2}\n'


def test_canonical_uses_compact_separators():
    assert canonical({"a": [1, 2], "b": {"c": 3}}) == '{"a":[1,2],"b":{"c":3}}\n'


def test_canonical_keeps_utf8_unescaped():
    assert canonical({"b": 2, "a": "é"}) == '{"a":"é","b":2}\n'


def test_canonical_ends_with_exactly_one_newline():
    text = canonical({"a": 1})
    assert text.endswith("\n")
    assert text.count("\n") == 1


def test_canonical_empty_object():
    assert canonical({}) == "{}\n"


def test_cli_output_still_exposes_the_canonical_helper():
    assert cli_canonical is canonical
