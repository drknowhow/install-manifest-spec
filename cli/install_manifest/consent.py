"""Render the consent screen and collect a yes/no decision.

The consent screen is the human-facing summary of the manifest. It includes:
  * Tool identity (name, version, summary, homepage).
  * Scopes — the (resource, actions, rationale) triples.
  * Cost — denominated in cents per the spec, or 'external' (billed elsewhere).
  * Kill switch — how this install can be revoked.
  * Smoke test — how the install will be verified.

The output is plain text rendered to a single string. Callers may print it
directly or feed it to whatever UI they have. `collect_consent()` is a
thin stdin prompt for CLI use; UI-driven hosts will roll their own.
"""
from __future__ import annotations

import sys
from typing import Iterable, Mapping, Sequence


def render_consent(manifest: Mapping) -> str:
    """Render a human-readable consent screen for `manifest`.

    Assumes `manifest` has already been validated.
    """
    lines: list[str] = []

    tool = manifest.get("tool", {})
    name = tool.get("name", "<unnamed>")
    version = tool.get("version", "?")
    summary = tool.get("summary", "")
    homepage = tool.get("homepage", "")

    lines.append(f"Install: {name} v{version}")
    if summary:
        lines.append(f"  {summary}")
    if homepage:
        lines.append(f"  {homepage}")
    lines.append("")

    # --- Scopes ----------------------------------------------------------
    scopes = manifest.get("scopes") or []
    if scopes:
        lines.append("Permissions this tool will exercise:")
        for s in scopes:
            res = s.get("resource", "?")
            actions = s.get("actions", [])
            actions_s = ", ".join(actions) if actions else "(none)"
            rationale = s.get("rationale", "")
            lines.append(f"  - {res}: {actions_s}")
            if rationale:
                lines.append(f"      {rationale}")
        lines.append("")
    else:
        lines.append("Permissions: none declared.")
        lines.append("")

    # --- Env -------------------------------------------------------------
    env = manifest.get("env") or []
    if env:
        secret_count = sum(1 for e in env if e.get("secret"))
        nonsecret_count = len(env) - secret_count
        lines.append(
            f"Credentials to collect: {len(env)} "
            f"({secret_count} secret, {nonsecret_count} non-secret)"
        )
        for e in env:
            tag = "secret" if e.get("secret") else "value"
            required = " (required)" if e.get("required", True) else ""
            lines.append(f"  - {e.get('name', '?')} [{tag}]{required}")
        lines.append("")

    # --- Cost ------------------------------------------------------------
    cost = manifest.get("cost")
    if cost:
        lines.append(_render_cost(cost))
        lines.append("")
    else:
        lines.append("Cost: not declared by manifest.")
        lines.append("")

    # --- Smoke -----------------------------------------------------------
    smoke = manifest.get("smoke") or {}
    kind = smoke.get("kind", "?")
    lines.append(f"Verification: {kind} smoke test will run after install.")

    # --- Kill switch -----------------------------------------------------
    kill = manifest.get("kill_switch") or {}
    kill_kind = kill.get("kind", "?")
    if kill_kind == "url":
        # Spec is DELETE-against-this-URL; no method/headers in the schema.
        url = kill.get("url", "?")
        lines.append(f"Revocation: DELETE {url}")
    elif kill_kind == "shell":
        cmd = kill.get("command", [])
        cmd_s = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        lines.append(f"Revocation: shell — {cmd_s}")
    elif kill_kind == "manual":
        instr_url = kill.get("instructions_url", "")
        if instr_url:
            lines.append(f"Revocation: MANUAL — see {instr_url}")
        else:
            lines.append("Revocation: MANUAL")
    else:
        lines.append(f"Revocation: {kill_kind}")
    lines.append("")

    # --- Support ---------------------------------------------------------
    support = manifest.get("support") or {}
    if support:
        for label, key in (
            ("Issues", "issues_url"),
            ("Security", "security_email"),
            ("Docs", "docs_url"),
        ):
            val = support.get(key)
            if val:
                lines.append(f"{label}: {val}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_cost(cost: Mapping) -> str:
    model = cost.get("usage_model")  # may be absent
    install_fee = cost.get("install_fee_cents")
    monthly_fee = cost.get("monthly_fee_cents")
    estimate_url = cost.get("estimate_url")

    if model == "external":
        return (
            "Cost: external billing — tool charges via its own credentials; "
            "the marketplace is not in the payment loop."
        )

    parts = []
    if model:
        parts.append(f"Cost: {model}")
    else:
        parts.append("Cost:")
    if install_fee is not None:
        parts.append(f"  one-time install: ${install_fee / 100:.2f}")
    if monthly_fee is not None:
        parts.append(f"  monthly: ${monthly_fee / 100:.2f}")
    if estimate_url:
        parts.append(f"  estimate: {estimate_url}")
    if len(parts) == 1:
        # We have a cost block but no concrete fields. Be honest about that.
        parts.append("  (no concrete cost fields declared)")
    return "\n".join(parts)


def collect_consent(
    *,
    prompt: str = "Proceed with install? [y/N]: ",
    stdin=None,
    stdout=None,
) -> bool:
    """Prompt the user for a yes/no decision. Defaults to no on EOF or empty."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        stdout.write(prompt)
        stdout.flush()
        line = stdin.readline()
    except (EOFError, KeyboardInterrupt):
        return False
    if not line:
        return False
    answer = line.strip().lower()
    return answer in ("y", "yes")
