"""Guard test: every bundled schema must stay byte-identical to its repo-canonical sibling.

The CLI bundles a copy of every install-manifest schema at
install_manifest/_data/install-manifest-vX.Y.json so the validator works
post-`pip install`. The canonical versions live at the repo root in
schema/install-manifest-vX.Y.json. Drift between any pair is a class of
bug we want to catch in CI rather than discover at runtime.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

CLI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_DIR.parent

CANONICAL_DIR = REPO_ROOT / "schema"
BUNDLED_DIR = CLI_DIR / "install_manifest" / "_data"

SCHEMA_GLOB = "install-manifest-v*.json"


def _canonical_schemas() -> list[Path]:
    return sorted(CANONICAL_DIR.glob(SCHEMA_GLOB))


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_at_least_one_canonical_schema_exists():
    schemas = _canonical_schemas()
    assert schemas, f"no canonical schemas found in {CANONICAL_DIR}"


@pytest.mark.parametrize("canonical", _canonical_schemas(), ids=lambda p: p.name)
def test_bundled_schema_exists(canonical: Path):
    bundled = BUNDLED_DIR / canonical.name
    assert bundled.is_file(), (
        f"missing bundled schema at {bundled} — "
        "run scripts/sync_schema.py to copy it from the canonical location"
    )


@pytest.mark.parametrize("canonical", _canonical_schemas(), ids=lambda p: p.name)
def test_bundled_matches_canonical(canonical: Path):
    """Byte-identical: the bundled copy is whatever scripts/sync_schema.py produced."""
    bundled = BUNDLED_DIR / canonical.name
    canon_h = _sha256(canonical)
    bundle_h = _sha256(bundled)
    assert canon_h == bundle_h, (
        f"bundled schema {canonical.name} is out of sync with canonical. "
        f"canonical={canon_h[:12]} bundled={bundle_h[:12]}. "
        "Run: python cli/scripts/sync_schema.py"
    )


@pytest.mark.parametrize("canonical", _canonical_schemas(), ids=lambda p: p.name)
def test_bundled_is_valid_json(canonical: Path):
    bundled = BUNDLED_DIR / canonical.name
    json.loads(bundled.read_text(encoding="utf-8"))
