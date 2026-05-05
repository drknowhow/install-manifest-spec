"""Copy every canonical install-manifest schema into the CLI package's _data dir.

Run this whenever any schema/install-manifest-vX.Y.json changes. CI guards
against drift via tests/test_schema_bundle.py.

Behavior:
  - Iterates every file matching schema/install-manifest-v*.json at the repo root.
  - Copies each to cli/install_manifest/_data/<same-filename>.
  - Prints one line per copied file.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_DIR.parent
CANONICAL_DIR = REPO_ROOT / "schema"
BUNDLED_DIR = CLI_DIR / "install_manifest" / "_data"

SCHEMA_GLOB = "install-manifest-v*.json"


def main() -> int:
    if not CANONICAL_DIR.is_dir():
        print(f"error: canonical schema dir not found at {CANONICAL_DIR}", file=sys.stderr)
        return 1

    schemas = sorted(CANONICAL_DIR.glob(SCHEMA_GLOB))
    if not schemas:
        print(f"error: no schemas matched {CANONICAL_DIR}/{SCHEMA_GLOB}", file=sys.stderr)
        return 1

    BUNDLED_DIR.mkdir(parents=True, exist_ok=True)

    for src in schemas:
        dst = BUNDLED_DIR / src.name
        shutil.copy2(src, dst)
        print(f"copied {src} -> {dst}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
