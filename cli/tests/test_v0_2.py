"""Tests for the v0.2 schema and validate-dispatch behavior.

The v0.2 schema adds a top-level `actions[]` catalog and a fourth smoke
kind (`action-call`). Validation also gains version dispatch: a v0.2
manifest must validate against the v0.2 schema, and a v0.1 manifest
against v0.1.

These tests use the v0.2 gmail example as the canonical witness — if the
schema cannot describe that example, it is not ready.
"""
from __future__ import annotations

import copy

import pytest

from install_manifest.validate import (
    SUPPORTED_MANIFEST_VERSIONS,
    validate,
    validate_or_raise,
)
from install_manifest.errors import ValidationError


# ---- Sanity ----------------------------------------------------------------


def test_v0_2_is_supported():
    assert "0.2" in SUPPORTED_MANIFEST_VERSIONS


def test_v0_1_still_supported():
    """v0.1 stays a first-class supported version. No silent break."""
    assert "0.1" in SUPPORTED_MANIFEST_VERSIONS


def test_minimal_v0_2_manifest_validates(minimal_manifest_v0_2):
    result = validate(minimal_manifest_v0_2)
    assert result.ok, result.errors


def test_real_v0_2_example_validates(example_manifest_v0_2):
    """examples/gmail.v0.2.json is the canonical witness for the v0.2 schema."""
    result = validate(example_manifest_v0_2)
    assert result.ok, result.errors


# ---- Version dispatch ------------------------------------------------------


def test_v0_1_manifest_dispatches_to_v0_1_schema(example_manifest):
    """A v0.1 manifest still validates under the new dispatch validator."""
    result = validate(example_manifest)
    assert result.ok, result.errors


def test_v0_2_manifest_rejects_v0_1_only_field_absence(minimal_manifest_v0_2):
    """v0.2 still requires every v0.1 field. Sanity: removing tool.id breaks it."""
    m = copy.deepcopy(minimal_manifest_v0_2)
    del m["tool"]["id"]
    result = validate(m)
    assert not result.ok


# ---- actions[] required-when-non-mcp-stdio (the if/then conditional) ------


@pytest.mark.parametrize(
    "kind",
    ["python-module", "node-module", "shell-binary", "container", "mcp-http"],
)
def test_actions_required_for_non_mcp_stdio_kinds(minimal_manifest_v0_2, kind):
    """Every non-mcp-stdio runtime.kind must require actions[]."""
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["runtime"]["kind"] = kind
    # mcp-http requires endpoint_url, not entrypoint; swap.
    if kind == "mcp-http":
        m["runtime"].pop("entrypoint", None)
        m["runtime"]["endpoint_url"] = "https://example.com/mcp"
    del m["actions"]
    result = validate(m)
    assert not result.ok, f"kind={kind!r} should require actions[]"
    assert any("actions" in msg or "/actions" in ptr for ptr, msg in result.errors), result.errors


def test_actions_required_minitems_for_non_mcp_stdio(minimal_manifest_v0_2):
    """Empty actions[] is still a violation when the kind is non-mcp-stdio."""
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"] = []
    result = validate(m)
    assert not result.ok


def test_actions_optional_for_mcp_stdio(minimal_manifest_v0_2):
    """mcp-stdio is exempt: the protocol's own discovery covers operations."""
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["runtime"]["kind"] = "mcp-stdio"
    del m["actions"]
    result = validate(m)
    assert result.ok, result.errors


# ---- actions[] field-level constraints ------------------------------------


def test_action_name_pattern(minimal_manifest_v0_2):
    """Action names must be lowercase snake_case, no leading digit."""
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["name"] = "Has Spaces"
    result = validate(m)
    assert not result.ok
    assert any(ptr.startswith("/actions/0/name") for ptr, _ in result.errors), result.errors


def test_action_side_effects_required(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    del m["actions"][0]["side_effects"]
    result = validate(m)
    assert not result.ok
    assert any("side_effects" in msg for _, msg in result.errors), result.errors


def test_action_side_effects_enum(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["side_effects"] = "ruinous"
    result = validate(m)
    assert not result.ok


def test_action_invocation_oneof_subcommand_requires_argv_template(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["invocation"] = {"kind": "subcommand"}  # missing argv_template
    result = validate(m)
    assert not result.ok


def test_action_invocation_http_requires_path(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["invocation"] = {"kind": "http", "method": "GET"}  # missing path
    result = validate(m)
    assert not result.ok


def test_action_invocation_http_method_enum(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["invocation"] = {"kind": "http", "method": "TRACE", "path": "/x"}
    result = validate(m)
    assert not result.ok


def test_action_output_format_required(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["output"] = {}  # missing format
    result = validate(m)
    assert not result.ok


def test_action_error_envelope_default_raw(minimal_manifest_v0_2):
    """error_envelope is optional; absent means raw. Manifest still validates."""
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0].pop("error_envelope", None)
    result = validate(m)
    assert result.ok, result.errors


def test_action_error_envelope_enum(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["error_envelope"] = "fancy"
    result = validate(m)
    assert not result.ok


def test_action_examples_max_items(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["examples"] = [{"description": f"e{i}"} for i in range(5)]
    result = validate(m)
    assert not result.ok


def test_action_additional_properties_rejected(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["totally_unknown_field"] = "nope"
    result = validate(m)
    assert not result.ok


# ---- smoke.kind = "action-call" -------------------------------------------


def test_smoke_action_call_kind(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "arguments": {},
        "success": {"no_error_field": True},
    }
    result = validate(m)
    assert result.ok, result.errors


def test_smoke_action_call_requires_action(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["smoke"] = {
        "kind": "action-call",
        "arguments": {},
        "success": {"no_error_field": True},
    }
    result = validate(m)
    assert not result.ok


def test_smoke_action_call_action_name_pattern(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["smoke"] = {
        "kind": "action-call",
        "action": "Bad Name",
        "success": {"no_error_field": True},
    }
    result = validate(m)
    assert not result.ok


# ---- Other v0.2 deltas -----------------------------------------------------


def test_env_prompt_cap_raised_to_800(minimal_manifest_v0_2):
    """v0.2 raised env[].prompt cap from 280 to 800."""
    m = copy.deepcopy(minimal_manifest_v0_2)
    long_prompt = "x" * 500  # would have failed v0.1 (>280)
    m["env"] = [{"name": "FOO", "prompt": long_prompt, "secret": False}]
    result = validate(m)
    assert result.ok, result.errors


def test_env_prompt_cap_still_enforced_at_800(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    too_long = "x" * 801
    m["env"] = [{"name": "FOO", "prompt": too_long, "secret": False}]
    result = validate(m)
    assert not result.ok


def test_validate_or_raise_passes_for_v0_2(minimal_manifest_v0_2):
    validate_or_raise(minimal_manifest_v0_2)


def test_validate_or_raise_raises_for_bad_v0_2(minimal_manifest_v0_2):
    m = copy.deepcopy(minimal_manifest_v0_2)
    m["actions"][0]["side_effects"] = "ruinous"
    with pytest.raises(ValidationError):
        validate_or_raise(m)
