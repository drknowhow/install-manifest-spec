"""Tests for the v0.4 schema and validate-dispatch behavior.

v0.4 is strictly additive on top of v0.3.1 and adds:

  * `runtime.install.method = "preinstalled"` with a required `locator`
    object discriminated by `kind` (python-module | binary-on-path |
    mcp-server-id). Closes issue #5 (tools baked into the agent runtime).

  * `data_boundary.transmits[].to_kind = "agent-supplied"` plus optional
    `to_constraint` prose. When present, `to` is omitted; otherwise `to`
    remains required. Closes issue #4 (variable-target outbound).

Every v0.3.1 manifest must validate against the v0.4 schema unmodified
(after bumping manifest_version to "0.4"). These tests exercise that
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


def test_v0_4_is_supported():
    assert "0.4" in SUPPORTED_MANIFEST_VERSIONS


def test_prior_versions_still_supported():
    """v0.1, v0.2, v0.3, v0.3.1 stay first-class. No silent break."""
    for v in ("0.1", "0.2", "0.3", "0.3.1"):
        assert v in SUPPORTED_MANIFEST_VERSIONS


def test_minimal_v0_4_manifest_validates(minimal_manifest_v0_4):
    result = validate(minimal_manifest_v0_4)
    assert result.ok, result.errors


# ---- Back-compat: v0.3.1 and v0.3 manifests validate at 0.4 ----------------


def test_v0_3_1_minimal_validates_at_0_4(minimal_manifest_v0_3_1):
    bumped = copy.deepcopy(minimal_manifest_v0_3_1)
    bumped["manifest_version"] = "0.4"
    result = validate(bumped)
    assert result.ok, result.errors


def test_v0_3_minimal_validates_at_0_4(minimal_manifest_v0_3):
    bumped = copy.deepcopy(minimal_manifest_v0_3)
    bumped["manifest_version"] = "0.4"
    result = validate(bumped)
    assert result.ok, result.errors


def test_v0_3_example_validates_at_0_4(example_manifest_v0_3):
    """gmail.v0.3.json with manifest_version bumped to '0.4' validates."""
    bumped = copy.deepcopy(example_manifest_v0_3)
    bumped["manifest_version"] = "0.4"
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
def test_muninn_attesting_manifests_validate_at_0_4(filename):
    """Each attesting community manifest validates unmodified against v0.4
    after a manifest_version bump. Load-bearing regression bed: if any of
    these breaks, the 'additive' claim is false.
    """
    path = Path(__file__).resolve().parents[2] / "examples" / filename
    manifest = json.loads(path.read_text(encoding="utf-8"))
    bumped = copy.deepcopy(manifest)
    bumped["manifest_version"] = "0.4"
    result = validate(bumped)
    assert result.ok, result.errors


# ---- runtime.install.method = "preinstalled" -------------------------------


def _preinstalled_base(minimal_manifest_v0_4, locator: dict) -> dict:
    m = copy.deepcopy(minimal_manifest_v0_4)
    m["runtime"]["install"] = {"method": "preinstalled", "locator": locator}
    return m


def test_preinstalled_python_module_happy(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "python-module", "module": "muninn_bsky_card"},
    )
    result = validate(m)
    assert result.ok, result.errors


def test_preinstalled_binary_on_path_happy(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "binary-on-path", "binary": "git"},
    )
    result = validate(m)
    assert result.ok, result.errors


def test_preinstalled_mcp_server_id_happy(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "mcp-server-id", "server_id": "yep_tools"},
    )
    result = validate(m)
    assert result.ok, result.errors


def test_preinstalled_missing_locator_rejected(minimal_manifest_v0_4):
    m = copy.deepcopy(minimal_manifest_v0_4)
    m["runtime"]["install"] = {"method": "preinstalled"}
    result = validate(m)
    assert not result.ok
    # locator is required when method='preinstalled'.


def test_preinstalled_locator_missing_kind_rejected(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"module": "muninn_bsky_card"},  # no kind
    )
    result = validate(m)
    assert not result.ok


def test_preinstalled_locator_unknown_kind_rejected(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "wishful-thinking", "ref": "x"},
    )
    result = validate(m)
    assert not result.ok


def test_preinstalled_python_module_missing_module_rejected(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "python-module"},  # no `module`
    )
    result = validate(m)
    assert not result.ok


def test_preinstalled_binary_on_path_missing_binary_rejected(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "binary-on-path"},  # no `binary`
    )
    result = validate(m)
    assert not result.ok


def test_preinstalled_mcp_server_id_missing_server_id_rejected(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "mcp-server-id"},  # no `server_id`
    )
    result = validate(m)
    assert not result.ok


def test_preinstalled_locator_python_module_with_extra_field_rejected(minimal_manifest_v0_4):
    m = _preinstalled_base(
        minimal_manifest_v0_4,
        {"kind": "python-module", "module": "x", "binary": "y"},
    )
    result = validate(m)
    assert not result.ok


def test_preinstalled_install_with_pip_fields_rejected(minimal_manifest_v0_4):
    """method=preinstalled is exclusive — can't carry pip fields."""
    m = copy.deepcopy(minimal_manifest_v0_4)
    m["runtime"]["install"] = {
        "method": "preinstalled",
        "locator": {"kind": "python-module", "module": "x"},
        "package": "x",  # leftover pip field
    }
    result = validate(m)
    assert not result.ok


# ---- data_boundary.transmits[] to_kind = "agent-supplied" ------------------


def _agent_supplied_base(minimal_manifest_v0_4) -> dict:
    """v0.4 manifest with a scope touching private data and a data_boundary
    declaring one agent-supplied outbound. Mirrors the muninn-bsky-card
    case that surfaced issue #4."""
    m = copy.deepcopy(minimal_manifest_v0_4)
    # Add a private-data scope to force data_boundary.
    m["scopes"] = [
        {
            "resource": "gmail.messages",
            "actions": ["read"],
            "rationale": "Read sender lines to compose link cards.",
        },
        {
            "resource": "net.outbound",
            "actions": ["read"],
            "rationale": "Fetch agent-supplied URL for Open Graph metadata.",
        },
    ]
    m["data_boundary"] = {
        "reads": [{"resource": "gmail.messages", "sensitivity": "medium"}],
        "transmits": [
            {
                "to_kind": "agent-supplied",
                "to_constraint": "https-only no-private-ranges",
                "fields": ["/url"],
                "purpose": "Fetch URL for Open Graph metadata extraction.",
                "third_party_retention": "unknown",
            }
        ],
    }
    return m


def test_transmits_agent_supplied_happy(minimal_manifest_v0_4):
    m = _agent_supplied_base(minimal_manifest_v0_4)
    result = validate(m)
    assert result.ok, result.errors


def test_transmits_agent_supplied_to_constraint_optional(minimal_manifest_v0_4):
    m = _agent_supplied_base(minimal_manifest_v0_4)
    del m["data_boundary"]["transmits"][0]["to_constraint"]
    result = validate(m)
    assert result.ok, result.errors


def test_transmits_both_to_and_to_kind_rejected(minimal_manifest_v0_4):
    m = _agent_supplied_base(minimal_manifest_v0_4)
    m["data_boundary"]["transmits"][0]["to"] = "api.example.com"
    # to_kind already present
    result = validate(m)
    assert not result.ok


def test_transmits_neither_to_nor_to_kind_rejected(minimal_manifest_v0_4):
    m = _agent_supplied_base(minimal_manifest_v0_4)
    del m["data_boundary"]["transmits"][0]["to_kind"]
    del m["data_boundary"]["transmits"][0]["to_constraint"]
    # Neither to nor to_kind now.
    result = validate(m)
    assert not result.ok


def test_transmits_fixed_to_still_works(minimal_manifest_v0_4):
    """The classic v0.3 shape (bare `to` hostname) remains valid."""
    m = _agent_supplied_base(minimal_manifest_v0_4)
    m["data_boundary"]["transmits"][0] = {
        "to": "api.openai.com",
        "fields": ["/subject"],
        "purpose": "Classification.",
        "third_party_retention": "session-only",
    }
    result = validate(m)
    assert result.ok, result.errors


def test_transmits_to_kind_unknown_value_rejected(minimal_manifest_v0_4):
    m = _agent_supplied_base(minimal_manifest_v0_4)
    m["data_boundary"]["transmits"][0]["to_kind"] = "wildcard-pattern"
    result = validate(m)
    assert not result.ok


def test_transmits_to_constraint_too_long_rejected(minimal_manifest_v0_4):
    m = _agent_supplied_base(minimal_manifest_v0_4)
    m["data_boundary"]["transmits"][0]["to_constraint"] = "x" * 281
    result = validate(m)
    assert not result.ok


# ---- validate_or_raise -----------------------------------------------------


def test_validate_or_raise_passes_v0_4(minimal_manifest_v0_4):
    validate_or_raise(minimal_manifest_v0_4)


def test_validate_or_raise_fails_preinstalled_missing_locator(minimal_manifest_v0_4):
    m = copy.deepcopy(minimal_manifest_v0_4)
    m["runtime"]["install"] = {"method": "preinstalled"}
    with pytest.raises(ValidationError):
        validate_or_raise(m)
