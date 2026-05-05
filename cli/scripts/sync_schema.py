"""Copy the canonical schema into the CLI package's _data directory.

Run this whenever schema/install-manifest-v0.1.json changes. CI guards
against drift via tests/test_schema_bundle.py::test_bundled_matches_canonical.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_DIR.parent

CANONICAL = REPO_ROOT / "schema" / "install-manifest-v0.1.json"
BUNDLED = CLI_DIR / "install_manifest" / "_data" / "install-manifest-v0.1.json"


def main() -> int:
    if not CANONICAL.is_file():
        print(f"error: canonical schema not found at {CANONICAL}", file=sys.stderr)
        return 1
    BUNDLED.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CANONICAL, BUNDLED)
    print(f"copied {CANONICAL} -> {BUNDLED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
