"""Shared test fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_MANIFEST_PATH = REPO_ROOT / "examples" / "gmail.json"


@pytest.fixture
def example_manifest_path() -> Path:
    return EXAMPLE_MANIFEST_PATH


@pytest.fixture
def example_manifest() -> dict:
    return json.loads(EXAMPLE_MANIFEST_PATH.read_text(encoding="utf-8"))


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
