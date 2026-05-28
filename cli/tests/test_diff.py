"""Diff classification coverage.

Tests use `minimal_manifest_v0_4` as the base, mutate one surface at a
time, and assert the classification bucket. Cross-version diffs raise.
"""
from __future__ import annotations

import copy

import pytest

from install_manifest.diff import DiffError, diff


def _with(m: dict, **patch) -> dict:
    out = copy.deepcopy(m)
    out.update(patch)
    return out


# ---------------------------------------------------------------------------
# constraint: cross-version is rejected


def test_cross_version_raises(minimal_manifest, minimal_manifest_v0_3):
    with pytest.raises(DiffError):
        diff(minimal_manifest, minimal_manifest_v0_3)


def test_byte_equivalent_returns_empty(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    b = copy.deepcopy(minimal_manifest_v0_4)
    result = diff(a, b)
    assert result.is_empty()


# ---------------------------------------------------------------------------
# breaking: action removal, scope removal, kill_switch removal


def test_action_removed_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["actions"].append({
        "name": "extra",
        "summary": "another",
        "invocation": {"kind": "subcommand", "argv_template": ["extra"]},
        "output": {"format": "text"},
        "side_effects": "none",
        "idempotent": True,
    })
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    kinds = [c.kind for c in result.breaking]
    assert "action-removed" in kinds


def test_scope_removed_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["scopes"] = [{"resource": "gmail.messages", "actions": ["read"], "rationale": "x"}]
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "scope-removed" for c in result.breaking)


def test_kill_switch_removed_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b.pop("kill_switch")
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "kill-switch-removed" for c in result.breaking)


# ---------------------------------------------------------------------------
# breaking: input schema tightening


def _action_with_input(input_schema: dict) -> dict:
    return {
        "name": "act",
        "summary": "test",
        "invocation": {"kind": "stdin-json", "argv_template": ["act"]},
        "input": input_schema,
        "output": {"format": "json"},
        "side_effects": "none",
        "idempotent": True,
    }


def test_input_property_type_change_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["actions"] = [_action_with_input({
        "type": "object",
        "properties": {"q": {"type": "string"}},
    })]
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(a)
    b["actions"][0]["input"]["properties"]["q"] = {"type": "integer"}
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "input-type-changed" for c in result.breaking)


def test_input_property_now_required_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["actions"] = [_action_with_input({
        "type": "object",
        "properties": {"q": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["q"],
    })]
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(a)
    b["actions"][0]["input"]["required"] = ["q", "limit"]
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "input-now-required" for c in result.breaking)


def test_input_enum_added_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["actions"] = [_action_with_input({
        "type": "object",
        "properties": {"mode": {"type": "string"}},
    })]
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(a)
    b["actions"][0]["input"]["properties"]["mode"] = {"type": "string", "enum": ["a", "b"]}
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "input-enum-added" for c in result.breaking)


def test_input_additional_properties_closed_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["actions"] = [_action_with_input({
        "type": "object",
        "properties": {"q": {"type": "string"}},
        "additionalProperties": True,
    })]
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(a)
    b["actions"][0]["input"]["additionalProperties"] = False
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "input-additional-properties-closed" for c in result.breaking)


# ---------------------------------------------------------------------------
# breaking: env removed / required env added / external transmit added


def test_env_removed_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["env"] = [{"name": "X", "prompt": "p", "secret": False, "required": True}]
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "env-removed" for c in result.breaking)


def test_required_env_added_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["env"] = [{"name": "NEW", "prompt": "p", "secret": False, "required": True}]
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "env-added-required" for c in result.breaking)


def test_external_transmit_added_is_breaking(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["data_boundary"] = {"transmits": []}
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["data_boundary"] = {
        "transmits": [
            {"to_kind": "external", "to_constraint": "openai.com", "purpose": "summarize", "resource": "msgs"},
        ],
    }
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "external-transmit-added" for c in result.breaking)


# ---------------------------------------------------------------------------
# additive: action added, scope added, optional env added, verify/kill_switch added


def test_action_added_is_additive(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["actions"].append({
        "name": "extra",
        "summary": "another",
        "invocation": {"kind": "subcommand", "argv_template": ["extra"]},
        "output": {"format": "text"},
        "side_effects": "none",
        "idempotent": True,
    })
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "action-added" for c in result.additive)


def test_scope_added_is_additive(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["scopes"] = [{"resource": "gmail.messages", "actions": ["read"], "rationale": "x"}]
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "scope-added" for c in result.additive)


def test_scope_verb_added_is_additive(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["scopes"] = [{"resource": "gmail.messages", "actions": ["read"], "rationale": "x"}]
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(a)
    b["scopes"][0]["actions"] = ["read", "send"]
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "scope-verb-added" for c in result.additive)


def test_optional_env_added_is_additive(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["env"] = [{"name": "NEW", "prompt": "p", "secret": False, "required": False, "default": "x"}]
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "env-added-optional" for c in result.additive)


def test_kill_switch_added_is_additive(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a.pop("kill_switch")
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "kill-switch-added" for c in result.additive)


def test_verify_added_is_additive(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["verify"] = {"suite": {"ref": "x", "format": "jsonl-cases"}, "sla": {"p95_latency_ms": 1500}}
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "verify-added" for c in result.additive)


# ---------------------------------------------------------------------------
# cosmetic: version-only bump, docs text edits, summary edits


def test_version_only_bump_is_cosmetic(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["version"] = "1.0.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["tool"]["version"] = "1.0.1"
    result = diff(a, b)
    assert result.breaking == []
    assert result.additive == []
    assert any(c.kind == "tool-version-bumped" for c in result.cosmetic)


def test_action_docs_change_is_cosmetic(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["actions"][0]["docs"] = {"goal": "old"}
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(a)
    b["actions"][0]["docs"] = {"goal": "new and improved"}
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "docs-text-changed" for c in result.cosmetic)


def test_tool_summary_change_is_cosmetic(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["summary"] = "old"
    a["tool"]["version"] = "0.9.0"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["tool"]["summary"] = "new"
    b["tool"]["version"] = "1.0.0"
    result = diff(a, b)
    assert any(c.kind == "tool-summary-changed" for c in result.cosmetic)


# ---------------------------------------------------------------------------
# version-mutation: bodies differ at the same version


def test_same_version_body_differs_is_version_mutation(minimal_manifest_v0_4):
    a = copy.deepcopy(minimal_manifest_v0_4)
    a["tool"]["summary"] = "before"
    b = copy.deepcopy(minimal_manifest_v0_4)
    b["tool"]["summary"] = "after"
    # both still version 1.0.0
    result = diff(a, b)
    assert any(c.kind == "version-mutation" for c in result.breaking)
