"""Guard test: bundled schema must stay byte-identical to repo-canonical schema.

The CLI bundles a copy of the schema at install_manifest/_data/install-manifest-v0.1.json
so it works post-`pip install`. The canonical version lives at the repo root in
schema/install-manifest-v0.1.json. Drift between them is a class of bug we want
to catch in CI rather than discover at runtime.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_DIR.parent

CANONICAL = REPO_ROOT / "schema" / "install-manifest-v0.1.json"
BUNDLED = CLI_DIR / "install_manifest" / "_data" / "install-manifest-v0.1.json"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_canonical_schema_exists():
    assert CANONICAL.is_file(), f"missing canonical schema at {CANONICAL}"


def test_bundled_schema_exists():
    assert BUNDLED.is_file(), (
        f"missing bundled schema at {BUNDLED} — "
        "run scripts/sync_schema.py to copy it from the canonical location"
    )


def test_bundled_matches_canonical():
    """Byte-identical: the bundled copy is whatever scripts/sync_schema.py produced."""
    canon_h = _sha256(CANONICAL)
    bundle_h = _sha256(BUNDLED)
    assert canon_h == bundle_h, (
        "bundled schema is out of sync with canonical schema. "
        f"canonical={canon_h[:12]} bundled={bundle_h[:12]}. "
        "Run: python cli/scripts/sync_schema.py"
    )


def test_bundled_is_valid_json():
    json.loads(BUNDLED.read_text(encoding="utf-8"))
