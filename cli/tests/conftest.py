"""Shared test fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_MANIFEST_PATH = REPO_ROOT / "examples" / "gmail.json"
EXAMPLE_MANIFEST_V0_2_PATH = REPO_ROOT / "examples" / "gmail.v0.2.json"
EXAMPLE_MANIFEST_V0_3_PATH = REPO_ROOT / "examples" / "gmail.v0.3.json"


@pytest.fixture
def example_manifest_path() -> Path:
    return EXAMPLE_MANIFEST_PATH


@pytest.fixture
def example_manifest() -> dict:
    return json.loads(EXAMPLE_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def example_manifest_v0_2_path() -> Path:
    return EXAMPLE_MANIFEST_V0_2_PATH


@pytest.fixture
def example_manifest_v0_2() -> dict:
    return json.loads(EXAMPLE_MANIFEST_V0_2_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def example_manifest_v0_3_path() -> Path:
    return EXAMPLE_MANIFEST_V0_3_PATH


@pytest.fixture
def example_manifest_v0_3() -> dict:
    return json.loads(EXAMPLE_MANIFEST_V0_3_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def minimal_manifest() -> dict:
    """Smallest fully-valid v0.1 manifest. Useful as a base for variant tests."""
    return {
        "manifest_version": "0.1",
        "tool": {
            "id": "tinytool",
            "version": "1.0.0",
            "name": "Tiny Tool",
            "summary": "A tiny tool, used in tests.",
            "homepage": "https://example.com/tinytool",
        },
        "runtime": {
            "kind": "shell-binary",
            "install": {"method": "pip", "package": "tinytool", "version_spec": "==1.0.0"},
            "entrypoint": {"command": ["tinytool"]},
        },
        "smoke": {
            "kind": "shell",
            "command": ["tinytool", "--version"],
            "success": {"exit_code": 0},
        },
        "kill_switch": {
            "kind": "manual",
            "instructions_url": "https://example.com/tinytool/revoke",
        },
    }


@pytest.fixture
def minimal_manifest_v0_2() -> dict:
    """Smallest fully-valid v0.2 manifest.

    Uses runtime.kind = 'shell-binary', which means the if/then conditional
    in v0.2 forces actions[] to be present (with at least one entry). The
    fixture supplies one read-only action so the manifest validates.
    """
    return {
        "manifest_version": "0.2",
        "tool": {
            "id": "tinytool",
            "version": "1.0.0",
            "name": "Tiny Tool",
            "summary": "A tiny tool, used in tests.",
            "homepage": "https://example.com/tinytool",
        },
        "runtime": {
            "kind": "shell-binary",
            "install": {"method": "pip", "package": "tinytool", "version_spec": "==1.0.0"},
            "entrypoint": {"command": ["tinytool"]},
        },
        "actions": [
            {
                "name": "version",
                "summary": "Print the tool's version.",
                "invocation": {
                    "kind": "subcommand",
                    "argv_template": ["--version"],
                },
                "output": {"format": "text"},
                "side_effects": "none",
                "idempotent": True,
            }
        ],
        "smoke": {
            "kind": "shell",
            "command": ["tinytool", "--version"],
            "success": {"exit_code": 0},
        },
        "kill_switch": {
            "kind": "manual",
            "instructions_url": "https://example.com/tinytool/revoke",
        },
    }


@pytest.fixture
def minimal_manifest_v0_3() -> dict:
    """Smallest fully-valid v0.3 manifest.

    Mirrors minimal_manifest_v0_2: shell-binary runtime forces actions[] via the
    same if/then. Uses no scopes[] entries that match the private-data prefix
    pattern, so data_boundary is NOT required and can be omitted to keep the
    fixture minimal. Tests that exercise the data_boundary requirement add a
    matching scope explicitly.
    """
    return {
        "manifest_version": "0.3",
        "tool": {
            "id": "tinytool",
            "version": "1.0.0",
            "name": "Tiny Tool",
            "summary": "A tiny tool, used in tests.",
            "homepage": "https://example.com/tinytool",
        },
        "runtime": {
            "kind": "shell-binary",
            "install": {"method": "pip", "package": "tinytool", "version_spec": "==1.0.0"},
            "entrypoint": {"command": ["tinytool"]},
        },
        "actions": [
            {
                "name": "version",
                "summary": "Print the tool's version.",
                "invocation": {
                    "kind": "subcommand",
                    "argv_template": ["--version"],
                },
                "output": {"format": "text"},
                "side_effects": "none",
                "idempotent": True,
            }
        ],
        "smoke": {
            "kind": "shell",
            "command": ["tinytool", "--version"],
            "success": {"exit_code": 0},
        },
        "kill_switch": {
            "kind": "manual",
            "instructions_url": "https://example.com/tinytool/revoke",
        },
    }
