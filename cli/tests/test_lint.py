"""Lint rule coverage.

One fixture per rule (LM001-LM010) plus a clean fixture that triggers no
findings. The clean fixture also exercises that adding only the rule's
target violation makes that specific code appear.

Fixtures are built from `minimal_manifest_v0_3` (or v0.4) to keep them
schema-valid by default — we mutate just enough to trip one rule at a
time. Schema-validity is not strictly required by `lint()` (it guards
its own inputs), but using validated bases keeps the catalogue honest:
real publishers see these warnings on otherwise-valid manifests.
"""
from __future__ import annotations

import copy

import pytest

from install_manifest.lint import LintFinding, RULE_DESCRIPTIONS, lint


def _strip_block(m: dict, key: str) -> dict:
    out = copy.deepcopy(m)
    out.pop(key, None)
    return out


# ---------------------------------------------------------------------------
# clean baseline


def _clean_v0_4_manifest(base: dict) -> dict:
    """Take minimal_manifest_v0_4 and add verify + kill_switch + lint-clean tool."""
    m = copy.deepcopy(base)
    m["tool"]["id"] = "clean-tool"
    m["tool"]["version"] = "1.0.0"
    m["verify"] = {
        "suite": {"ref": "./suite.jsonl", "format": "jsonl-cases"},
        "sla": {"p95_latency_ms": 1500},
    }
    # actions[0] needs docs.goal
    m["actions"][0]["docs"] = {"goal": "Print the tool version."}
    return m


def test_clean_manifest_has_no_findings(minimal_manifest_v0_4):
    clean = _clean_v0_4_manifest(minimal_manifest_v0_4)
    assert lint(clean) == []


# ---------------------------------------------------------------------------
# LM001 — missing verify


def test_LM001_missing_verify(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m.pop("verify")
    codes = {f.code for f in lint(m)}
    assert "LM001" in codes


def test_LM001_does_not_fire_below_v0_3(minimal_manifest):
    # v0.1 has no verify block by design.
    assert "LM001" not in {f.code for f in lint(minimal_manifest)}


# ---------------------------------------------------------------------------
# LM002 — missing kill_switch


def test_LM002_missing_kill_switch(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m.pop("kill_switch")
    codes = {f.code for f in lint(m)}
    assert "LM002" in codes


# ---------------------------------------------------------------------------
# LM003 — external transmit without to_constraint


def test_LM003_external_without_constraint(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["data_boundary"] = {
        "transmits": [
            {"to_kind": "external", "purpose": "summarization"},
        ],
    }
    findings = [f for f in lint(m) if f.code == "LM003"]
    assert len(findings) == 1
    assert findings[0].path == "/data_boundary/transmits/0"


def test_LM003_silent_when_constraint_present(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["data_boundary"] = {
        "transmits": [
            {"to_kind": "external", "to_constraint": "openai.com only", "purpose": "x"},
        ],
    }
    assert "LM003" not in {f.code for f in lint(m)}


# ---------------------------------------------------------------------------
# LM004 — loose v0.3 transmits (no to_kind)


def test_LM004_loose_v0_3_transmits(minimal_manifest_v0_3):
    m = copy.deepcopy(minimal_manifest_v0_3)
    m["tool"]["id"] = "clean-tool"
    m["tool"]["version"] = "1.0.0"
    m["actions"][0]["docs"] = {"goal": "Print the tool version."}
    m["verify"] = {"suite": {"ref": "x", "format": "jsonl-cases"}, "sla": {"p95_latency_ms": 1500}}
    m["data_boundary"] = {"transmits": [{"resource": "x.api", "purpose": "call"}]}
    findings = [f for f in lint(m) if f.code == "LM004"]
    assert len(findings) == 1


def test_LM004_silent_on_v0_4(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    # Even loose-shaped transmits on v0.4 don't trigger LM004; the upgrade
    # advice is moot once you're already on the newer version.
    m["data_boundary"] = {"transmits": [{"resource": "x.api"}]}
    assert "LM004" not in {f.code for f in lint(m)}


# ---------------------------------------------------------------------------
# LM005 — actions missing docs.goal


def test_LM005_missing_docs_goal(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["actions"][0].pop("docs", None)
    findings = [f for f in lint(m) if f.code == "LM005"]
    assert len(findings) == 1
    assert "version" in findings[0].message  # action name in message


def test_LM005_empty_goal_also_flagged(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["actions"][0]["docs"] = {"goal": "   "}
    assert "LM005" in {f.code for f in lint(m)}


# ---------------------------------------------------------------------------
# LM006 — verify present but no p95


def test_LM006_missing_p95(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["verify"]["sla"] = {"p50_latency_ms": 100}
    findings = [f for f in lint(m) if f.code == "LM006"]
    assert len(findings) == 1


# ---------------------------------------------------------------------------
# LM007 — tool.id not kebab-case


@pytest.mark.parametrize("bad_id", [
    "PascalCase",
    "snake_case",
    "1-leading-digit",
    "trailing-",
    "double--hyphen",
    "has space",
])
def test_LM007_bad_tool_id(minimal_manifest_v0_4, bad_id):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["tool"]["id"] = bad_id
    codes = {f.code for f in lint(m)}
    assert "LM007" in codes


def test_LM007_silent_on_good_id(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["tool"]["id"] = "clean-tool-2"
    assert "LM007" not in {f.code for f in lint(m)}


# ---------------------------------------------------------------------------
# LM008 — tool.version not SemVer


@pytest.mark.parametrize("bad_version", [
    "1",
    "1.0",
    "v1.0.0",
    "1.0.0.0",
    "abc",
])
def test_LM008_bad_version(minimal_manifest_v0_4, bad_version):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["tool"]["version"] = bad_version
    assert "LM008" in {f.code for f in lint(m)}


@pytest.mark.parametrize("good_version", [
    "1.0.0",
    "0.1.0",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0+build.1",
    "1.0.0-rc.1+build.2",
])
def test_LM008_good_version(minimal_manifest_v0_4, good_version):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["tool"]["version"] = good_version
    assert "LM008" not in {f.code for f in lint(m)}


# ---------------------------------------------------------------------------
# LM009 — http:// URL anywhere


def test_LM009_http_in_homepage(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["tool"]["homepage"] = "http://example.com/tinytool"
    findings = [f for f in lint(m) if f.code == "LM009"]
    assert len(findings) == 1
    assert findings[0].path == "/tool/homepage"


def test_LM009_http_deep_inside_actions(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["actions"][0]["docs"]["example"] = "see http://example.com/foo"
    assert "LM009" in {f.code for f in lint(m)}


# ---------------------------------------------------------------------------
# LM010 — secret env var without regex or min_length


def test_LM010_secret_without_constraint(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["env"] = [
        {"name": "MY_SECRET", "secret": True, "required": True, "prompt": "p"},
    ]
    findings = [f for f in lint(m) if f.code == "LM010"]
    assert len(findings) == 1


def test_LM010_silent_with_regex(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m["env"] = [
        {
            "name": "MY_SECRET",
            "secret": True,
            "required": True,
            "prompt": "p",
            "validation_regex": "^.{8,}$",
        },
    ]
    assert "LM010" not in {f.code for f in lint(m)}


# ---------------------------------------------------------------------------
# Sort order + general shape


def test_findings_sorted_by_code_then_path(minimal_manifest_v0_4):
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    # Trigger LM005, LM007, LM008, LM009 simultaneously.
    m["tool"]["id"] = "BadCase"
    m["tool"]["version"] = "v1"
    m["tool"]["homepage"] = "http://example.com"
    m["actions"][0].pop("docs", None)
    findings = lint(m)
    codes = [f.code for f in findings]
    assert codes == sorted(codes)


def test_rule_descriptions_cover_all_codes(minimal_manifest_v0_4):
    # Every code the linter can emit must be in the public catalog.
    m = _clean_v0_4_manifest(minimal_manifest_v0_4)
    m.pop("verify")
    m.pop("kill_switch")
    m["tool"]["id"] = "BadCase"
    m["tool"]["version"] = "v1"
    m["tool"]["homepage"] = "http://example.com"
    m["actions"][0].pop("docs", None)
    m["env"] = [{"name": "X", "secret": True, "required": True, "prompt": "p"}]
    m["data_boundary"] = {"transmits": [{"to_kind": "external"}]}
    findings = lint(m)
    for f in findings:
        assert f.code in RULE_DESCRIPTIONS, f.code


def test_lint_returns_empty_on_non_dict():
    assert lint("not a dict") == []  # type: ignore[arg-type]


def test_finding_as_dict_round_trip():
    f = LintFinding("warning", "LM999", "/x", "msg", suggestion="do better")
    d = f.as_dict()
    assert d["code"] == "LM999"
    assert d["suggestion"] == "do better"
    f2 = LintFinding("warning", "LM999", "/x", "msg")
    assert "suggestion" not in f2.as_dict()
