"""Lint a (validated) install-manifest dict for best-practice issues.

Lint runs AFTER schema validation. Its rules are pure functions over the
parsed dict — no I/O, no network. Severity in v1 is `"warning"` only;
schema violations belong in `validate.py` (errors), not here.

Initial rule catalog (v1):

  LM001  missing `verify` block on manifest_version >= 0.3
  LM002  missing `kill_switch` on manifest_version >= 0.3
  LM003  `data_boundary.transmits[]` with `to_kind=external` and no `to_constraint`
  LM004  `data_boundary.transmits[]` entries with no `to_kind` (suggest v0.4 upgrade)
  LM005  `actions[]` entry with missing or empty `docs.goal`
  LM006  `verify` present but `verify.sla.p95_latency_ms` missing
  LM007  `tool.id` not kebab-case
  LM008  `tool.version` not SemVer
  LM009  any `http://` URL anywhere in the manifest
  LM010  `env[]` entry with `secret: true` and no `regex` or `min_length`

Each rule is its own small function; `lint(manifest)` calls them all and
returns the concatenated findings sorted by `(code, path)`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

__all__ = ["LintFinding", "lint", "RULE_DESCRIPTIONS"]


@dataclass(frozen=True)
class LintFinding:
    """One linter finding. v1 severity is always 'warning'."""
    severity: str
    code: str
    path: str
    message: str
    suggestion: Optional[str] = None

    def as_dict(self) -> dict:
        d = {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }
        if self.suggestion is not None:
            d["suggestion"] = self.suggestion
        return d


# Public, stable catalog used by the CLI to render `--list-rules` if/when added.
RULE_DESCRIPTIONS: dict = {
    "LM001": "missing `verify` block on manifest_version >= 0.3",
    "LM002": "missing `kill_switch` on manifest_version >= 0.3",
    "LM003": "data_boundary.transmits[] entry with to_kind=external and no to_constraint",
    "LM004": "data_boundary.transmits[] entries without to_kind (loose v0.3; upgrade to v0.4)",
    "LM005": "actions[] entry with missing or empty docs.goal",
    "LM006": "verify block present but verify.sla.p95_latency_ms missing",
    "LM007": "tool.id is not kebab-case",
    "LM008": "tool.version is not SemVer",
    "LM009": "manifest contains an http:// URL (use https://)",
    "LM010": "env[] secret entry has neither regex nor min_length",
}


_KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
# SemVer 2.0.0 regex, simplified (stdlib only — no `packaging` dep).
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def _version_at_least(declared: str, floor: str) -> bool:
    """True if `declared` >= `floor` under the spec's MAJOR.MINOR(.PATCH) order.

    Manifests use short version strings like '0.3', '0.3.1', '0.4'. We treat
    missing components as 0. This is purely a comparator for the lint rules,
    not a SemVer implementation.
    """
    def parts(s: str) -> Tuple[int, ...]:
        return tuple(int(x) for x in (s.split(".") + ["0", "0", "0"])[:3] if x.isdigit())

    return parts(declared) >= parts(floor)


# ----- individual rules ----------------------------------------------------


def _rule_LM001_missing_verify(m: dict) -> List[LintFinding]:
    ver = str(m.get("manifest_version", ""))
    if not _version_at_least(ver, "0.3"):
        return []
    if "verify" in m:
        return []
    return [LintFinding(
        severity="warning",
        code="LM001",
        path="/verify",
        message="manifest_version >= 0.3 should declare a `verify` block (eval suite + SLA)",
        suggestion="add a `verify` block with `suite`, `sla`, and `schedule`",
    )]


def _rule_LM002_missing_kill_switch(m: dict) -> List[LintFinding]:
    ver = str(m.get("manifest_version", ""))
    if not _version_at_least(ver, "0.3"):
        return []
    if "kill_switch" in m:
        return []
    return [LintFinding(
        severity="warning",
        code="LM002",
        path="/kill_switch",
        message="manifest_version >= 0.3 should declare a `kill_switch` block",
        suggestion="add a `kill_switch` with kind `manual` or `shell`",
    )]


def _rule_LM003_external_no_constraint(m: dict) -> List[LintFinding]:
    db = m.get("data_boundary") or {}
    transmits = db.get("transmits") or []
    findings: List[LintFinding] = []
    for i, entry in enumerate(transmits):
        if not isinstance(entry, dict):
            continue
        if entry.get("to_kind") == "external" and not entry.get("to_constraint"):
            findings.append(LintFinding(
                severity="warning",
                code="LM003",
                path=f"/data_boundary/transmits/{i}",
                message="external transmit destination has no `to_constraint` (publisher gives no hint about where data goes)",
                suggestion="add `to_constraint` describing the allowed destination(s)",
            ))
    return findings


def _rule_LM004_transmits_loose_v0_3(m: dict) -> List[LintFinding]:
    ver = str(m.get("manifest_version", ""))
    # If manifest already declares 0.4+, to_kind is expected; LM004 only
    # flags loose v0.3 manifests that should upgrade.
    if _version_at_least(ver, "0.4"):
        return []
    db = m.get("data_boundary") or {}
    transmits = db.get("transmits") or []
    if not transmits:
        return []
    if all(isinstance(e, dict) and "to_kind" not in e for e in transmits):
        return [LintFinding(
            severity="warning",
            code="LM004",
            path="/data_boundary/transmits",
            message="transmits[] entries declare no `to_kind` (allowed in v0.3, but loose)",
            suggestion="upgrade to manifest_version 0.4 and add `to_kind` to each transmit entry",
        )]
    return []


def _rule_LM005_action_docs_goal(m: dict) -> List[LintFinding]:
    actions = m.get("actions") or []
    findings: List[LintFinding] = []
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        docs = action.get("docs") or {}
        goal = docs.get("goal") if isinstance(docs, dict) else None
        if not (isinstance(goal, str) and goal.strip()):
            name = action.get("name", "?")
            findings.append(LintFinding(
                severity="warning",
                code="LM005",
                path=f"/actions/{i}/docs/goal",
                message=f"action {name!r} is missing `docs.goal`",
                suggestion="add a one-sentence `docs.goal` describing what the action accomplishes",
            ))
    return findings


def _rule_LM006_missing_p95(m: dict) -> List[LintFinding]:
    verify = m.get("verify")
    if not isinstance(verify, dict):
        return []
    sla = verify.get("sla") or {}
    if "p95_latency_ms" in sla:
        return []
    return [LintFinding(
        severity="warning",
        code="LM006",
        path="/verify/sla/p95_latency_ms",
        message="`verify.sla` is present but does not declare `p95_latency_ms`",
        suggestion="add `verify.sla.p95_latency_ms` so consumers can hold the publisher to a latency budget",
    )]


def _rule_LM007_tool_id_kebab(m: dict) -> List[LintFinding]:
    tool = m.get("tool") or {}
    tool_id = tool.get("id")
    if not isinstance(tool_id, str) or not tool_id:
        return []
    if _KEBAB_RE.match(tool_id):
        return []
    return [LintFinding(
        severity="warning",
        code="LM007",
        path="/tool/id",
        message=f"tool.id {tool_id!r} is not kebab-case",
        suggestion="use lower-case kebab-case: lowercase letters, digits, and single hyphens",
    )]


def _rule_LM008_tool_version_semver(m: dict) -> List[LintFinding]:
    tool = m.get("tool") or {}
    version = tool.get("version")
    if not isinstance(version, str) or not version:
        return []
    if _SEMVER_RE.match(version):
        return []
    return [LintFinding(
        severity="warning",
        code="LM008",
        path="/tool/version",
        message=f"tool.version {version!r} is not a SemVer 2.0.0 version string",
        suggestion="use MAJOR.MINOR.PATCH (e.g., '0.1.0'), optionally with -prerelease and +build",
    )]


def _rule_LM009_no_http(m: dict) -> List[LintFinding]:
    """Walk the manifest and flag any string containing http:// (case-insensitive).

    Uses substring match because URLs show up in many shapes — homepage,
    obtain_url, scopes.provider_scope, verify.suite.ref, etc. We don't
    want to enumerate every site they could legally appear at.
    """
    findings: List[LintFinding] = []
    seen_paths: set = set()

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}")
        elif isinstance(node, str):
            if "http://" in node.lower() and path not in seen_paths:
                seen_paths.add(path)
                findings.append(LintFinding(
                    severity="warning",
                    code="LM009",
                    path=path,
                    message=f"value contains an http:// URL: {node!r}",
                    suggestion="use https:// (plaintext URLs are vulnerable to MITM and content injection)",
                ))

    walk(m, "")
    return findings


def _rule_LM010_secret_no_constraint(m: dict) -> List[LintFinding]:
    env_specs = m.get("env") or []
    findings: List[LintFinding] = []
    for i, spec in enumerate(env_specs):
        if not isinstance(spec, dict):
            continue
        if not spec.get("secret"):
            continue
        # `regex` or `validation_regex` (manifests have used both names
        # across spec versions); `min_length` mirrors the explicit length
        # constraint surface.
        has_regex = bool(spec.get("regex") or spec.get("validation_regex"))
        has_min_len = "min_length" in spec
        if has_regex or has_min_len:
            continue
        name = spec.get("name", "?")
        findings.append(LintFinding(
            severity="warning",
            code="LM010",
            path=f"/env/{i}",
            message=f"secret env var {name!r} has neither regex nor min_length",
            suggestion="add `regex` or `min_length` so paste-errors and empty strings fail early",
        ))
    return findings


_RULES: Tuple[Callable[[dict], List[LintFinding]], ...] = (
    _rule_LM001_missing_verify,
    _rule_LM002_missing_kill_switch,
    _rule_LM003_external_no_constraint,
    _rule_LM004_transmits_loose_v0_3,
    _rule_LM005_action_docs_goal,
    _rule_LM006_missing_p95,
    _rule_LM007_tool_id_kebab,
    _rule_LM008_tool_version_semver,
    _rule_LM009_no_http,
    _rule_LM010_secret_no_constraint,
)


def lint(manifest: dict) -> List[LintFinding]:
    """Run every lint rule against `manifest`.

    Returns findings sorted by `(code, path)` for stable output. The input
    is assumed to be a structurally-valid manifest (already passed
    `validate`); rules guard their own inputs defensively, but invalid
    manifests are not the use-case.
    """
    if not isinstance(manifest, dict):
        return []
    findings: List[LintFinding] = []
    for rule in _RULES:
        findings.extend(rule(manifest))
    findings.sort(key=lambda f: (f.code, f.path))
    return findings
