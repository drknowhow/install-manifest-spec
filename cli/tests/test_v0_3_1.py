"""Tests for the v0.3.1 schema and validate-dispatch behavior.

v0.3.1 is strictly additive on top of v0.3 and adds:

  * `kill_switch.kind = "none"` (stateless tools), validator-gated by
    env-empty + data_boundary.persists-empty
  * `kill_switch.manual.instructions` inline prose (mutually exclusive
    with `instructions_url`)
  * `tool.namespace` optional sibling field
  * `runtime.install.layout` enum on the git install variant
  * `smoke.success.json_pointer_in` (set-membership)
  * `smoke.success.json_pointer_present` (non-null, non-empty)
  * `smoke.success.json_pointer_exists` (existence-only — predates the
    others as a v0.3.1 addition for symmetry)

Every v0.3 manifest must validate against the v0.3.1 schema unmodified
(after bumping manifest_version to "0.3.1"). These tests exercise that
back-compat plus each new field's happy path and failure-mode.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from install_manifest.validate import (
    SUPPORTED_MANIFEST_VERSIONS,
    validate,
    validate_or_raise,
)
from install_manifest.errors import ValidationError


# ---- Sanity ----------------------------------------------------------------


def test_v0_3_1_is_supported():
    assert "0.3.1" in SUPPORTED_MANIFEST_VERSIONS


def test_prior_versions_still_supported():
    """v0.1, v0.2, v0.3 stay first-class. No silent break."""
    for v in ("0.1", "0.2", "0.3"):
        assert v in SUPPORTED_MANIFEST_VERSIONS


def test_minimal_v0_3_1_manifest_validates(minimal_manifest_v0_3_1):
    result = validate(minimal_manifest_v0_3_1)
    assert result.ok, result.errors


# ---- Back-compat: v0.3 manifests validate at 0.3.1 -------------------------


def test_v0_3_example_validates_at_0_3_1(example_manifest_v0_3):
    """gmail.v0.3.json with manifest_version bumped to '0.3.1' validates."""
    bumped = copy.deepcopy(example_manifest_v0_3)
    bumped["manifest_version"] = "0.3.1"
    result = validate(bumped)
    assert result.ok, result.errors


def test_v0_3_minimal_validates_at_0_3_1(minimal_manifest_v0_3):
    bumped = copy.deepcopy(minimal_manifest_v0_3)
    bumped["manifest_version"] = "0.3.1"
    result = validate(bumped)
    assert result.ok, result.errors


@pytest.mark.parametrize(
    "filename",
    [
        "muninn-flowing.v0.3.json",
        "muninn-verify-patch.v0.3.json",
        "muninn-perch-publish.v0.3.json",
    ],
)
def test_muninn_attesting_manifests_validate_at_0_3_1(filename):
    """Each attesting community manifest validates unmodified against v0.3.1
    after a manifest_version bump. This is the load-bearing regression bed:
    if any of these four breaks, the 'additive' claim is false.
    """
    path = Path(__file__).resolve().parents[2] / "examples" / filename
    manifest = json.loads(path.read_text(encoding="utf-8"))
    # Sanity: each ships as v0.3.
    assert manifest["manifest_version"] == "0.3"
    bumped = copy.deepcopy(manifest)
    bumped["manifest_version"] = "0.3.1"
    result = validate(bumped)
    assert result.ok, result.errors


# ---- kill_switch.kind = "none" ---------------------------------------------


def _stateless_base(minimal_manifest_v0_3_1) -> dict:
    """Build a stateless v0.3.1 manifest: no env, no data_boundary, kind=none."""
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["kill_switch"] = {"kind": "none"}
    return m


def test_kill_switch_none_happy_path(minimal_manifest_v0_3_1):
    m = _stateless_base(minimal_manifest_v0_3_1)
    result = validate(m)
    assert result.ok, result.errors


def test_kill_switch_none_with_env_rejected(minimal_manifest_v0_3_1):
    m = _stateless_base(minimal_manifest_v0_3_1)
    m["env"] = [{"name": "API_KEY", "prompt": "API key", "secret": True}]
    result = validate(m)
    assert not result.ok
    # Some validator should complain about the kind=none + env interaction.


def test_kill_switch_none_with_empty_env_ok(minimal_manifest_v0_3_1):
    m = _stateless_base(minimal_manifest_v0_3_1)
    m["env"] = []  # explicit empty array, semantically same as absent
    result = validate(m)
    assert result.ok, result.errors


def test_kill_switch_none_with_persists_rejected(minimal_manifest_v0_3_1):
    m = _stateless_base(minimal_manifest_v0_3_1)
    m["data_boundary"] = {
        "persists": [{"where": "tool_local", "fields": ["/log"]}]
    }
    result = validate(m)
    assert not result.ok


def test_kill_switch_none_with_data_boundary_but_no_persists_ok(
    minimal_manifest_v0_3_1,
):
    """data_boundary may be present as long as persists is absent or empty."""
    m = _stateless_base(minimal_manifest_v0_3_1)
    m["data_boundary"] = {
        "reads": [{"resource": "fs.local", "sensitivity": "low"}]
    }
    result = validate(m)
    assert result.ok, result.errors


# ---- kill_switch.manual inline instructions --------------------------------


def test_kill_switch_manual_inline_instructions(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["kill_switch"] = {
        "kind": "manual",
        "instructions": "1. Rotate the PAT.\n2. Delete the config.\n3. Uninstall.",
    }
    result = validate(m)
    assert result.ok, result.errors


def test_kill_switch_manual_inline_and_url_mutually_exclusive(
    minimal_manifest_v0_3_1,
):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["kill_switch"] = {
        "kind": "manual",
        "instructions": "step",
        "instructions_url": "https://example.com/revoke",
    }
    result = validate(m)
    assert not result.ok


def test_kill_switch_manual_neither_rejected(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["kill_switch"] = {"kind": "manual"}
    result = validate(m)
    assert not result.ok


def test_kill_switch_manual_inline_max_length(minimal_manifest_v0_3_1):
    """2000-char cap is enforced."""
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["kill_switch"] = {"kind": "manual", "instructions": "x" * 2001}
    result = validate(m)
    assert not result.ok


# ---- tool.namespace --------------------------------------------------------


def test_namespace_optional(minimal_manifest_v0_3_1):
    """Existing single-field id manifests continue to validate."""
    assert "namespace" not in minimal_manifest_v0_3_1["tool"]
    result = validate(minimal_manifest_v0_3_1)
    assert result.ok, result.errors


def test_namespace_happy_path(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["tool"]["namespace"] = "muninn"
    m["tool"]["id"] = "flowing"
    result = validate(m)
    assert result.ok, result.errors


def test_namespace_too_short_rejected(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["tool"]["namespace"] = "x"  # 1 char, regex requires 2-32
    result = validate(m)
    assert not result.ok


def test_namespace_uppercase_rejected(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["tool"]["namespace"] = "Muninn"
    result = validate(m)
    assert not result.ok


# ---- runtime.install.layout (git variant) ----------------------------------


def _git_install_manifest(minimal_manifest_v0_3_1) -> dict:
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["runtime"]["install"] = {
        "method": "git",
        "url": "https://github.com/oaustegard/claude-skills",
        "ref": "main",
        "subpath": "flowing",
    }
    return m


def test_layout_optional_defaults_package(minimal_manifest_v0_3_1):
    m = _git_install_manifest(minimal_manifest_v0_3_1)
    result = validate(m)
    assert result.ok, result.errors


@pytest.mark.parametrize("layout", ["package", "skill-bundle", "raw"])
def test_layout_enum_valid(minimal_manifest_v0_3_1, layout):
    m = _git_install_manifest(minimal_manifest_v0_3_1)
    m["runtime"]["install"]["layout"] = layout
    result = validate(m)
    assert result.ok, result.errors


def test_layout_unknown_value_rejected(minimal_manifest_v0_3_1):
    m = _git_install_manifest(minimal_manifest_v0_3_1)
    m["runtime"]["install"]["layout"] = "monorepo"
    result = validate(m)
    assert not result.ok


def test_layout_not_on_pip_variant(minimal_manifest_v0_3_1):
    """layout is git-only — pip install with a layout field must fail."""
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["runtime"]["install"] = {
        "method": "pip",
        "package": "tinytool",
        "version_spec": "==1.0.0",
        "layout": "package",
    }
    result = validate(m)
    assert not result.ok


# ---- smoke.success.json_pointer_in -----------------------------------------


def test_json_pointer_in_happy_path(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "success": {
            "json_pointer_in": {
                "/verdict": ["CORRECT", "LIKELY_CORRECT"],
            },
        },
    }
    result = validate(m)
    assert result.ok, result.errors


def test_json_pointer_in_non_array_value_rejected(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "success": {"json_pointer_in": {"/x": "not-an-array"}},
    }
    result = validate(m)
    assert not result.ok


def test_json_pointer_in_empty_array_rejected(minimal_manifest_v0_3_1):
    """minItems=1 — empty array makes no sense as set-membership."""
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "success": {"json_pointer_in": {"/x": []}},
    }
    result = validate(m)
    assert not result.ok


# ---- smoke.success.json_pointer_present ------------------------------------


def test_json_pointer_present_happy_path(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "success": {"json_pointer_present": "/answer"},
    }
    result = validate(m)
    assert result.ok, result.errors


def test_json_pointer_present_must_be_string(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "success": {"json_pointer_present": ["/answer"]},
    }
    result = validate(m)
    assert not result.ok


# ---- smoke.success combinations stay AND ----------------------------------


def test_multiple_success_predicates_combine_via_and(minimal_manifest_v0_3_1):
    """v0.3 spec: success conditions AND across present fields.
    v0.3.1's new fields participate in the same AND."""
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "success": {
            "json_pointer_in": {"/verdict": ["CORRECT"]},
            "json_pointer_present": "/answer",
            "no_error_field": True,
        },
    }
    result = validate(m)
    assert result.ok, result.errors


# ---- validate_or_raise -----------------------------------------------------


def test_validate_or_raise_passes_for_minimal(minimal_manifest_v0_3_1):
    validate_or_raise(minimal_manifest_v0_3_1)


def test_validate_or_raise_raises_on_failure(minimal_manifest_v0_3_1):
    m = copy.deepcopy(minimal_manifest_v0_3_1)
    m["kill_switch"] = {"kind": "manual"}  # missing both instructions fields
    with pytest.raises(ValidationError):
        validate_or_raise(m)
