"""Tests for install_manifest.validate."""
from __future__ import annotations

import copy

import pytest

from install_manifest.validate import (
    EXPECTED_MANIFEST_VERSION,
    validate,
    validate_or_raise,
)
from install_manifest.errors import ValidationError


def test_minimal_manifest_validates(minimal_manifest):
    result = validate(minimal_manifest)
    assert result.ok, result.errors
    assert result.summary == "ok"


def test_real_example_manifest_validates(example_manifest):
    """The example manifest in examples/gmail.json must validate against the
    schema. If this ever fails, either the schema or the example drifted."""
    result = validate(example_manifest)
    assert result.ok, result.errors


def test_wrong_top_level_type():
    result = validate("not a dict")
    assert not result.ok
    assert result.errors
    assert result.errors[0][0] == "/"


def test_missing_required_field(minimal_manifest):
    m = copy.deepcopy(minimal_manifest)
    del m["smoke"]
    result = validate(m)
    assert not result.ok
    # The error pointer for a missing required prop is at the parent.
    assert any("smoke" in msg for _, msg in result.errors), result.errors


def test_wrong_manifest_version(minimal_manifest):
    m = copy.deepcopy(minimal_manifest)
    m["manifest_version"] = "0.2"
    result = validate(m)
    assert not result.ok
    # Both the schema's const violation and our explicit message should be present.
    assert any(
        ptr == "/manifest_version" and "0.1" in msg
        for ptr, msg in result.errors
    ), result.errors


def test_bad_tool_id_pattern(minimal_manifest):
    m = copy.deepcopy(minimal_manifest)
    m["tool"]["id"] = "Bad ID With Spaces"
    result = validate(m)
    assert not result.ok
    assert any("/tool/id" == ptr for ptr, _ in result.errors), result.errors


def test_bad_env_name_pattern(minimal_manifest):
    m = copy.deepcopy(minimal_manifest)
    m["env"] = [
        {"name": "lowercase_bad", "prompt": "x", "secret": False},
    ]
    result = validate(m)
    assert not result.ok
    assert any(ptr.startswith("/env/0/name") for ptr, _ in result.errors), result.errors


def test_runtime_install_method_oneof(minimal_manifest):
    """A pip install method requires `package`. Removing it must fail."""
    m = copy.deepcopy(minimal_manifest)
    del m["runtime"]["install"]["package"]
    result = validate(m)
    assert not result.ok


def test_kill_switch_manual_requires_instructions_url(minimal_manifest):
    m = copy.deepcopy(minimal_manifest)
    del m["kill_switch"]["instructions_url"]
    result = validate(m)
    assert not result.ok


def test_validate_or_raise_passes(minimal_manifest):
    # Must not raise.
    validate_or_raise(minimal_manifest)


def test_validate_or_raise_raises(minimal_manifest):
    m = copy.deepcopy(minimal_manifest)
    m["manifest_version"] = "9.9"
    with pytest.raises(ValidationError) as exc:
        validate_or_raise(m)
    assert "manifest_version" in str(exc.value)


def test_expected_version_constant():
    """Pin: EXPECTED_MANIFEST_VERSION matches schema const. Catches drift."""
    assert EXPECTED_MANIFEST_VERSION == "0.1"
