"""Tests for the v0.3 schema and validate-dispatch behavior.

v0.3 adds three new top-level surfaces and one reserved per-action field:

  * `verify` (optional) — suite + sla + schedule
  * `data_boundary` (conditionally required) — reads / transmits / persists / retention
  * `actions[].docs` (optional, per-field char-capped)
  * `actions[].runtime_telemetry` (reserved opaque object, no v0.3 semantics)

Plus one narrowing: `data_boundary` is required when any scopes[].resource
matches the private-data prefix list. These tests exercise both the
additive surfaces and the narrowing.
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


def test_v0_3_is_supported():
    assert "0.3" in SUPPORTED_MANIFEST_VERSIONS


def test_prior_versions_still_supported():
    """v0.1 and v0.2 stay first-class. No silent break."""
    assert "0.1" in SUPPORTED_MANIFEST_VERSIONS
    assert "0.2" in SUPPORTED_MANIFEST_VERSIONS


def test_minimal_v0_3_manifest_validates(minimal_manifest_v0_3):
    result = validate(minimal_manifest_v0_3)
    assert result.ok, result.errors


def test_real_v0_3_example_validates(example_manifest_v0_3):
    """examples/gmail.v0.3.json is the canonical witness for the v0.3 schema."""
    result = validate(example_manifest_v0_3)
    assert result.ok, result.errors


# ---- Version dispatch ------------------------------------------------------


def test_v0_2_manifest_still_validates(example_manifest_v0_2):
    """A v0.2 manifest dispatches to the v0.2 schema even after v0.3 lands."""
    result = validate(example_manifest_v0_2)
    assert result.ok, result.errors


def test_v0_3_const_pinned(minimal_manifest_v0_3):
    """The v0.3 schema's manifest_version is const='0.3'."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    # Declaring 0.3 in the manifest but with a 0.2 shape would be a different
    # test; here we just check the const enforcement doesn't accept '0.3.0'.
    m["manifest_version"] = "0.3.0"
    result = validate(m)
    assert not result.ok


# ---- verify (additive, all optional) ---------------------------------------


def test_verify_block_optional(minimal_manifest_v0_3):
    """A v0.3 manifest without verify still validates."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    assert "verify" not in m
    result = validate(m)
    assert result.ok, result.errors


def test_verify_suite_minimum(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["verify"] = {
        "suite": {"ref": "./eval/cases.jsonl", "format": "jsonl-cases"},
    }
    result = validate(m)
    assert result.ok, result.errors


def test_verify_suite_format_enum(minimal_manifest_v0_3):
    """Only 'jsonl-cases' is accepted in v0.3."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["verify"] = {"suite": {"ref": "./x", "format": "yaml-cases"}}
    result = validate(m)
    assert not result.ok


def test_verify_pass_threshold_bounds(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["verify"] = {
        "suite": {"ref": "./x", "format": "jsonl-cases", "pass_threshold": 1.5},
    }
    result = validate(m)
    assert not result.ok


def test_verify_sla_error_rate_bounds(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["verify"] = {"sla": {"error_rate_max": 1.5}}
    result = validate(m)
    assert not result.ok


def test_verify_schedule_cadence_enum(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["verify"] = {"schedule": {"cadence": "hourly"}}  # not in enum
    result = validate(m)
    assert not result.ok


def test_verify_additional_properties_rejected(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["verify"] = {"unknown_block": {}}
    result = validate(m)
    assert not result.ok


# ---- data_boundary (the narrowing) ----------------------------------------


def test_data_boundary_not_required_when_no_private_scopes(minimal_manifest_v0_3):
    """If no scopes[].resource matches the private-data pattern, data_boundary stays optional."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["scopes"] = [
        {
            "resource": "net.outbound",
            "actions": ["read"],
            "rationale": "Tool calls a public weather API.",
        }
    ]
    # No data_boundary block.
    result = validate(m)
    assert result.ok, result.errors


@pytest.mark.parametrize(
    "private_resource",
    [
        "gmail.messages",
        "calendar.events",
        "drive.files",
        "contacts.entries",
        "messages.sms",
        "files.user_documents",
        "photos.library",
        "location.history",
        "health.activity",
        "finance.transactions",
        "payments.charges",
        "stripe.charges",
        "plaid.accounts",
    ],
)
def test_data_boundary_required_when_scopes_touch_private_data(
    minimal_manifest_v0_3, private_resource
):
    """Every prefix in the v0.3 list triggers the data_boundary requirement."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["scopes"] = [
        {
            "resource": private_resource,
            "actions": ["read"],
            "rationale": "Required for the tool's core function.",
        }
    ]
    # No data_boundary block — this MUST fail.
    result = validate(m)
    assert not result.ok, f"expected {private_resource!r} to require data_boundary"


def test_data_boundary_satisfies_requirement(minimal_manifest_v0_3):
    """When data_boundary is present and shaped correctly, the manifest validates."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["scopes"] = [
        {
            "resource": "gmail.messages",
            "actions": ["read"],
            "rationale": "Reads inbox content.",
        }
    ]
    m["data_boundary"] = {
        "reads": [{"resource": "gmail.messages", "sensitivity": "high"}],
        "transmits": [],
        "persists": [],
        "retention": {"tool_local_days": 0},
    }
    result = validate(m)
    assert result.ok, result.errors


def test_data_boundary_transmits_retention_enum(minimal_manifest_v0_3):
    """third_party_retention is a controlled enum."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["scopes"] = [
        {"resource": "gmail.messages", "actions": ["read"], "rationale": "needed"}
    ]
    m["data_boundary"] = {
        "reads": [{"resource": "gmail.messages", "sensitivity": "high"}],
        "transmits": [
            {
                "to": "api.example.com",
                "fields": ["gmail.messages.body"],
                "purpose": "classification",
                "third_party_retention": "forever-and-ever",  # not in enum
            }
        ],
    }
    result = validate(m)
    assert not result.ok


def test_data_boundary_vendor_tos_required_when_none_per_vendor_tos(minimal_manifest_v0_3):
    """vendor_tos_url is required iff third_party_retention='none-per-vendor-tos'."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["scopes"] = [
        {"resource": "gmail.messages", "actions": ["read"], "rationale": "needed"}
    ]
    m["data_boundary"] = {
        "reads": [{"resource": "gmail.messages", "sensitivity": "high"}],
        "transmits": [
            {
                "to": "api.example.com",
                "fields": ["gmail.messages.body"],
                "purpose": "classification",
                "third_party_retention": "none-per-vendor-tos",
                # missing vendor_tos_url
            }
        ],
    }
    result = validate(m)
    assert not result.ok


def test_data_boundary_persists_where_enum(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["scopes"] = [
        {"resource": "gmail.messages", "actions": ["read"], "rationale": "needed"}
    ]
    m["data_boundary"] = {
        "reads": [{"resource": "gmail.messages", "sensitivity": "high"}],
        "persists": [{"where": "the_cloud_somewhere", "fields": ["x"]}],
    }
    result = validate(m)
    assert not result.ok


def test_data_boundary_reads_sensitivity_enum(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["scopes"] = [
        {"resource": "gmail.messages", "actions": ["read"], "rationale": "needed"}
    ]
    m["data_boundary"] = {
        "reads": [{"resource": "gmail.messages", "sensitivity": "extreme"}],
    }
    result = validate(m)
    assert not result.ok


# ---- actions[].docs --------------------------------------------------------


def test_action_docs_optional(minimal_manifest_v0_3):
    """Actions without docs still validate."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    assert "docs" not in m["actions"][0]
    result = validate(m)
    assert result.ok, result.errors


def test_action_docs_accepts_well_shaped(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["actions"][0]["docs"] = {
        "goal": "Print the tool's version string.",
        "inputs_brief": "(none)",
        "outputs_brief": "version (semver string)",
        "errors_brief": "(none)",
        "example": "tinytool --version",
    }
    result = validate(m)
    assert result.ok, result.errors


def test_action_docs_field_cap_200(minimal_manifest_v0_3):
    """Each docs.* field is capped at 200 chars."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["actions"][0]["docs"] = {"goal": "x" * 201}
    result = validate(m)
    assert not result.ok


def test_action_docs_additional_properties_rejected(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["actions"][0]["docs"] = {"unknown_doc_field": "nope"}
    result = validate(m)
    assert not result.ok


# ---- actions[].runtime_telemetry (reserved, opaque) ------------------------


def test_runtime_telemetry_accepts_empty_object(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["actions"][0]["runtime_telemetry"] = {}
    result = validate(m)
    assert result.ok, result.errors


def test_runtime_telemetry_accepts_arbitrary_shape(minimal_manifest_v0_3):
    """The whole point of reserving: v0.3 doesn't lint the contents."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["actions"][0]["runtime_telemetry"] = {
        "any_future_v0_5_field": [1, 2, 3],
        "nested": {"endpoint": "https://x"},
    }
    result = validate(m)
    assert result.ok, result.errors


def test_runtime_telemetry_must_be_object(minimal_manifest_v0_3):
    """Reserved-as-opaque-object means strings/arrays still fail."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["actions"][0]["runtime_telemetry"] = "telemetry-on"
    result = validate(m)
    assert not result.ok


# ---- v0.2 surfaces still work in v0.3 --------------------------------------


def test_v0_2_smoke_action_call_kind_still_supported(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["smoke"] = {
        "kind": "action-call",
        "action": "version",
        "arguments": {},
        "success": {"no_error_field": True},
    }
    result = validate(m)
    assert result.ok, result.errors


def test_actions_required_for_non_mcp_stdio_in_v0_3(minimal_manifest_v0_3):
    """The v0.2 if/then for actions[] carries forward unchanged."""
    m = copy.deepcopy(minimal_manifest_v0_3)
    del m["actions"]
    result = validate(m)
    assert not result.ok


def test_validate_or_raise_passes_for_v0_3(minimal_manifest_v0_3):
    validate_or_raise(minimal_manifest_v0_3)


def test_validate_or_raise_raises_for_bad_v0_3(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["actions"][0]["side_effects"] = "ruinous"
    with pytest.raises(ValidationError):
        validate_or_raise(m)
