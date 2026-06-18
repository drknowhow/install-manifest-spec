"""Scaffold a new install manifest — `install-manifest init`.

Authoring a v0.4 manifest by hand means reading the schema and getting a
dozen required/conditional fields right before `validate` even passes.
`init` removes that cold-start tax: it emits a **valid** v0.4 manifest
pre-filled with the common shape (an mcp-stdio tool installed via pip) and
clearly-marked `TODO:` placeholders the author edits in place.

Design choices:
  * The scaffold targets the 80% case — `runtime.kind = "mcp-stdio"`
    installed via `pip`. It's the simplest shape that still validates and
    the most common one publishers ship. Other runtime kinds are a future
    flag; for now the author edits `runtime` after scaffolding.
  * Every placeholder is schema-VALID, not just a `TODO` string. Free-text
    fields carry `TODO:` prose; pattern/format/enum-constrained fields
    (ids, URIs, enums, env names) carry real placeholder values so the
    emitted file passes `validate` immediately. The author then replaces
    the content, not the structure.
  * `build_manifest()` is a pure function returning the dict, so it's unit
    -testable and re-usable; the CLI layer only handles prompting + I/O.

The emitted manifest deliberately includes a few *optional* sections
(`env`, `scopes`, one example `action`, `support`) as a teaching template.
None of them trip the schema's conditional requirements:
  * `scopes[].resource = "net.outbound"` is NOT a private-data prefix, so
    `data_boundary` is not forced.
  * `kill_switch.kind = "manual"` is valid alongside the example `env`
    entry (the stateless `"none"` kind would not be).
"""
from __future__ import annotations

from typing import Optional

# The scaffold always emits the current schema version. Older versions have
# a different shape; targeting one version keeps the generated file honest.
SCAFFOLD_MANIFEST_VERSION = "0.4"

# Defaults used when a field is neither supplied via flag nor entered at a
# prompt. All chosen to satisfy the v0.4 schema's pattern/format constraints.
DEFAULT_ID = "my-tool"
DEFAULT_HOMEPAGE = "https://example.com"


def _module_from_id(tool_id: str) -> str:
    """Best-effort Python module name from a tool id ('my-tool' -> 'my_tool')."""
    return tool_id.replace("-", "_")


def _name_from_id(tool_id: str) -> str:
    """Title-cased display name from a tool id ('my-tool' -> 'My Tool')."""
    return tool_id.replace("-", " ").replace("_", " ").strip().title() or "My Tool"


def build_manifest(
    *,
    tool_id: str = DEFAULT_ID,
    name: Optional[str] = None,
    summary: Optional[str] = None,
    homepage: str = DEFAULT_HOMEPAGE,
    package: Optional[str] = None,
    author: Optional[str] = None,
) -> dict:
    """Return a valid v0.4 install-manifest scaffold as a dict.

    Only `tool_id` meaningfully drives the shape; everything else falls back
    to a schema-valid placeholder. The result is intended to pass
    `validate()` unmodified and then be hand-edited (search for `TODO:`).
    """
    tool_id = tool_id or DEFAULT_ID
    name = name or _name_from_id(tool_id)
    summary = summary or "TODO: one-sentence description of what this tool does."
    package = package or tool_id
    module = _module_from_id(tool_id)

    tool: dict = {
        "id": tool_id,
        "version": "0.1.0",
        "name": name,
        "summary": summary,
        "description": "TODO: optional longer description (markdown allowed). Delete this field if unused.",
        "homepage": homepage or DEFAULT_HOMEPAGE,
        "license": "MIT",
        "tags": ["todo-category"],
    }
    if author:
        tool["author"] = {"name": author}

    return {
        "manifest_version": SCAFFOLD_MANIFEST_VERSION,
        "tool": tool,
        "runtime": {
            "kind": "mcp-stdio",
            "install": {"method": "pip", "package": package},
            "entrypoint": {"command": ["python", "-m", f"{module}.server"]},
        },
        "env": [
            {
                "name": "API_KEY",
                "prompt": "TODO: explain what this value is and where the owner gets it. Delete this env entry if the tool needs no secrets.",
                "secret": True,
                "obtain_url": "https://example.com/get-an-api-key",
            }
        ],
        "scopes": [
            {
                "resource": "net.outbound",
                "actions": ["read"],
                "rationale": "TODO: explain why the tool needs this access. Shown to the human owner at install.",
            }
        ],
        "actions": [
            {
                "name": "example_action",
                "summary": "TODO: one-sentence description of what this action does.",
                "invocation": {"kind": "mcp-tool", "tool_name": "example_action"},
                "side_effects": "read",
                "docs": {"goal": "TODO: what the action accomplishes, agent-readable, one sentence."},
            }
        ],
        "smoke": {
            "kind": "shell",
            "command": ["echo", "ok"],
            "success": {"exit_code": 0},
        },
        "kill_switch": {
            "kind": "manual",
            "instructions": "TODO: how the owner revokes this tool (e.g. delete the API key at <url> and uninstall the package).",
        },
        "support": {
            "issues_url": "https://example.com/issues",
        },
    }
