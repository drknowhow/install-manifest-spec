"""Compare two validated install-manifest dicts at the same manifest_version.

The diff classifies changes into three buckets:

  * `breaking` — a consumer of `a` cannot safely auto-upgrade to `b`.
    Surface area shrank, types got stricter, optional became required,
    a new external destination appeared, or a same-version body
    mutated (publishers are expected to bump version on any change).

  * `additive` — `b` adds capability or guard-rails that `a` lacked.
    Consumers can upgrade transparently.

  * `cosmetic` — text-only or version-bump-only changes that don't
    affect behavior.

v1 HARD CONSTRAINT: both manifests must declare the same
`manifest_version`. Cross-version diffing requires per-version
normalization rules that aren't worth building speculatively; if you
need to compare across versions, normalize manually first or upgrade
the publisher's older manifest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = ["Change", "DiffResult", "DiffError", "diff"]


class DiffError(Exception):
    """Raised when the inputs cannot be diffed under the v1 contract."""


@dataclass(frozen=True)
class Change:
    """One classified change between two manifests."""
    kind: str
    path: str
    before: Any
    after: Any
    message: str

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "path": self.path,
            "before": self.before,
            "after": self.after,
            "message": self.message,
        }


@dataclass
class DiffResult:
    """Three-bucket classification of changes between manifests."""
    breaking: List[Change] = field(default_factory=list)
    additive: List[Change] = field(default_factory=list)
    cosmetic: List[Change] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.breaking or self.additive or self.cosmetic)

    def as_dict(self) -> dict:
        return {
            "breaking": [c.as_dict() for c in self.breaking],
            "additive": [c.as_dict() for c in self.additive],
            "cosmetic": [c.as_dict() for c in self.cosmetic],
        }


def _by_key(items: List[dict], key: str) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for item in items or []:
        if isinstance(item, dict) and isinstance(item.get(key), str):
            out[item[key]] = item
    return out


def _diff_actions(a: dict, b: dict, out: DiffResult) -> None:
    """Compare actions[] keyed by action name."""
    actions_a = _by_key(a.get("actions") or [], "name")
    actions_b = _by_key(b.get("actions") or [], "name")

    for name in actions_a.keys() - actions_b.keys():
        out.breaking.append(Change(
            kind="action-removed",
            path=f"/actions/{name}",
            before=actions_a[name],
            after=None,
            message=f"action {name!r} was removed",
        ))
    for name in actions_b.keys() - actions_a.keys():
        out.additive.append(Change(
            kind="action-added",
            path=f"/actions/{name}",
            before=None,
            after=actions_b[name],
            message=f"action {name!r} was added",
        ))
    for name in actions_a.keys() & actions_b.keys():
        _diff_action_body(name, actions_a[name], actions_b[name], out)


def _diff_action_body(name: str, a: dict, b: dict, out: DiffResult) -> None:
    """Inspect a single action's input schema + docs for change classification."""
    base = f"/actions/{name}"

    # Input schema stricter-than checks.
    schema_a = a.get("input") if isinstance(a.get("input"), dict) else None
    schema_b = b.get("input") if isinstance(b.get("input"), dict) else None
    if schema_a or schema_b:
        _diff_input_schema(base + "/input", schema_a or {}, schema_b or {}, out)

    # Docs text changes are cosmetic.
    docs_a = a.get("docs") or {}
    docs_b = b.get("docs") or {}
    if isinstance(docs_a, dict) and isinstance(docs_b, dict) and docs_a != docs_b:
        out.cosmetic.append(Change(
            kind="docs-text-changed",
            path=f"{base}/docs",
            before=docs_a,
            after=docs_b,
            message=f"action {name!r} docs text changed",
        ))


def _diff_input_schema(base: str, sa: dict, sb: dict, out: DiffResult) -> None:
    """Apply the breaking-rule subset for action input schemas."""
    props_a = sa.get("properties") or {}
    props_b = sb.get("properties") or {}
    req_a = set(sa.get("required") or [])
    req_b = set(sb.get("required") or [])

    # Type-change of an existing property.
    for prop in props_a.keys() & props_b.keys():
        t_a = props_a[prop].get("type") if isinstance(props_a[prop], dict) else None
        t_b = props_b[prop].get("type") if isinstance(props_b[prop], dict) else None
        if t_a is not None and t_b is not None and t_a != t_b:
            out.breaking.append(Change(
                kind="input-type-changed",
                path=f"{base}/properties/{prop}/type",
                before=t_a,
                after=t_b,
                message=f"property {prop!r} type changed from {t_a!r} to {t_b!r}",
            ))
        # Previously-loose enum → gained an enum constraint.
        enum_a = props_a[prop].get("enum") if isinstance(props_a[prop], dict) else None
        enum_b = props_b[prop].get("enum") if isinstance(props_b[prop], dict) else None
        if enum_a is None and enum_b is not None:
            out.breaking.append(Change(
                kind="input-enum-added",
                path=f"{base}/properties/{prop}/enum",
                before=None,
                after=enum_b,
                message=f"property {prop!r} gained an enum constraint",
            ))

    # Optional-became-required.
    for prop in (req_b - req_a):
        if prop in props_a:
            out.breaking.append(Change(
                kind="input-now-required",
                path=f"{base}/required/{prop}",
                before=False,
                after=True,
                message=f"property {prop!r} became required",
            ))

    # additionalProperties true → false.
    add_a = sa.get("additionalProperties")
    add_b = sb.get("additionalProperties")
    if add_a is not False and add_b is False:
        out.breaking.append(Change(
            kind="input-additional-properties-closed",
            path=f"{base}/additionalProperties",
            before=add_a,
            after=add_b,
            message="additionalProperties tightened from open to closed",
        ))


def _diff_scopes(a: dict, b: dict, out: DiffResult) -> None:
    scopes_a = _by_key(a.get("scopes") or [], "resource")
    scopes_b = _by_key(b.get("scopes") or [], "resource")

    for res in scopes_a.keys() - scopes_b.keys():
        out.breaking.append(Change(
            kind="scope-removed",
            path=f"/scopes/{res}",
            before=scopes_a[res],
            after=None,
            message=f"scope on resource {res!r} was removed",
        ))
    for res in scopes_b.keys() - scopes_a.keys():
        # New scope is additive (new verbs add to the published surface but
        # the consumer chose to install — they implicitly accept).
        out.additive.append(Change(
            kind="scope-added",
            path=f"/scopes/{res}",
            before=None,
            after=scopes_b[res],
            message=f"scope on resource {res!r} was added",
        ))
    for res in scopes_a.keys() & scopes_b.keys():
        verbs_a = set(scopes_a[res].get("actions") or [])
        verbs_b = set(scopes_b[res].get("actions") or [])
        for v in (verbs_b - verbs_a):
            out.additive.append(Change(
                kind="scope-verb-added",
                path=f"/scopes/{res}/actions/{v}",
                before=None,
                after=v,
                message=f"scope {res!r} gained verb {v!r}",
            ))
        for v in (verbs_a - verbs_b):
            out.breaking.append(Change(
                kind="scope-verb-removed",
                path=f"/scopes/{res}/actions/{v}",
                before=v,
                after=None,
                message=f"scope {res!r} dropped verb {v!r}",
            ))


def _diff_env(a: dict, b: dict, out: DiffResult) -> None:
    env_a = _by_key(a.get("env") or [], "name")
    env_b = _by_key(b.get("env") or [], "name")

    for name in env_a.keys() - env_b.keys():
        out.breaking.append(Change(
            kind="env-removed",
            path=f"/env/{name}",
            before=env_a[name],
            after=None,
            message=f"env var {name!r} was removed",
        ))
    for name in env_b.keys() - env_a.keys():
        spec_b = env_b[name]
        # Optional new env var with a default OR explicitly not required → additive.
        is_required = spec_b.get("required") is True
        has_default = "default" in spec_b
        if has_default or not is_required:
            out.additive.append(Change(
                kind="env-added-optional",
                path=f"/env/{name}",
                before=None,
                after=spec_b,
                message=f"optional env var {name!r} was added",
            ))
        else:
            out.breaking.append(Change(
                kind="env-added-required",
                path=f"/env/{name}",
                before=None,
                after=spec_b,
                message=f"required env var {name!r} was added — existing consumers will fail",
            ))


def _diff_kill_switch(a: dict, b: dict, out: DiffResult) -> None:
    ks_a = a.get("kill_switch")
    ks_b = b.get("kill_switch")
    if ks_a and not ks_b:
        out.breaking.append(Change(
            kind="kill-switch-removed",
            path="/kill_switch",
            before=ks_a,
            after=None,
            message="kill_switch was removed",
        ))
    elif ks_b and not ks_a:
        out.additive.append(Change(
            kind="kill-switch-added",
            path="/kill_switch",
            before=None,
            after=ks_b,
            message="kill_switch was added",
        ))


def _diff_verify(a: dict, b: dict, out: DiffResult) -> None:
    v_a = a.get("verify")
    v_b = b.get("verify")
    if not v_a and v_b:
        out.additive.append(Change(
            kind="verify-added",
            path="/verify",
            before=None,
            after=v_b,
            message="verify block was added",
        ))


def _diff_data_boundary(a: dict, b: dict, out: DiffResult) -> None:
    """Flag newly-added external transmits as breaking."""
    db_a = a.get("data_boundary") or {}
    db_b = b.get("data_boundary") or {}

    def externals(entries: List[Any]) -> List[dict]:
        return [
            e for e in (entries or [])
            if isinstance(e, dict) and e.get("to_kind") == "external"
        ]

    ext_a = externals(db_a.get("transmits") or [])
    ext_b = externals(db_b.get("transmits") or [])

    def fingerprint(e: dict) -> str:
        # Stable-ish identity for external transmits — purpose+constraint
        # narrows enough to detect "new third party appeared".
        return f"{e.get('purpose', '')}::{e.get('to_constraint', '')}::{e.get('resource', '')}"

    seen_a = {fingerprint(e) for e in ext_a}
    for entry in ext_b:
        if fingerprint(entry) not in seen_a:
            out.breaking.append(Change(
                kind="external-transmit-added",
                path="/data_boundary/transmits",
                before=None,
                after=entry,
                message="a new external transmit destination appeared (broadens what the tool sends out)",
            ))


def _diff_cosmetic_top_level(a: dict, b: dict, out: DiffResult) -> None:
    tool_a = a.get("tool") or {}
    tool_b = b.get("tool") or {}

    # tool.docs.*
    docs_a = tool_a.get("docs") or {}
    docs_b = tool_b.get("docs") or {}
    if isinstance(docs_a, dict) and isinstance(docs_b, dict) and docs_a != docs_b:
        out.cosmetic.append(Change(
            kind="tool-docs-changed",
            path="/tool/docs",
            before=docs_a,
            after=docs_b,
            message="tool.docs text changed",
        ))

    # summary
    if tool_a.get("summary") != tool_b.get("summary"):
        out.cosmetic.append(Change(
            kind="tool-summary-changed",
            path="/tool/summary",
            before=tool_a.get("summary"),
            after=tool_b.get("summary"),
            message="tool.summary changed",
        ))


def _is_version_only_change(a: dict, b: dict) -> bool:
    """True iff the only top-level change in `tool` is the version string."""
    tool_a = dict(a.get("tool") or {})
    tool_b = dict(b.get("tool") or {})
    if tool_a.get("version") == tool_b.get("version"):
        return False
    tool_a.pop("version", None)
    tool_b.pop("version", None)
    # All other tool fields must match AND all non-tool top-level fields must match.
    if tool_a != tool_b:
        return False
    rest_a = {k: v for k, v in a.items() if k != "tool"}
    rest_b = {k: v for k, v in b.items() if k != "tool"}
    return rest_a == rest_b


def diff(a: dict, b: dict) -> DiffResult:
    """Classify changes between two same-version manifests.

    Raises:
        DiffError: if `a` and `b` declare different `manifest_version` values
            (cross-version diffing is out of scope for v1).
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise DiffError("both inputs must be dict-shaped manifests")

    if a.get("manifest_version") != b.get("manifest_version"):
        raise DiffError("cross-version diff not supported in v1")

    out = DiffResult()

    if a == b:
        return out

    # Cosmetic-only path: tool.version bumped, everything else identical.
    if _is_version_only_change(a, b):
        out.cosmetic.append(Change(
            kind="tool-version-bumped",
            path="/tool/version",
            before=(a.get("tool") or {}).get("version"),
            after=(b.get("tool") or {}).get("version"),
            message="tool.version bumped with no other changes",
        ))
        return out

    # Same-version-body-changed: bodies differ but version is identical.
    if (a.get("tool") or {}).get("version") == (b.get("tool") or {}).get("version"):
        out.breaking.append(Change(
            kind="version-mutation",
            path="/",
            before=(a.get("tool") or {}).get("version"),
            after=(b.get("tool") or {}).get("version"),
            message="manifests at the same tool.version differ — publishers must bump version on any change",
        ))

    _diff_actions(a, b, out)
    _diff_scopes(a, b, out)
    _diff_env(a, b, out)
    _diff_kill_switch(a, b, out)
    _diff_verify(a, b, out)
    _diff_data_boundary(a, b, out)
    _diff_cosmetic_top_level(a, b, out)

    return out
