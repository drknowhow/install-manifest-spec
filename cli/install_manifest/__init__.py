"""install-manifest — reference CLI for the install-manifest spec.

Supports manifest_version 0.1, 0.2, 0.3, 0.3.1, and 0.4. The validator
dispatches on the manifest's declared version automatically.

This release exposes:
  * build_manifest(...)                # scaffold a valid v0.4 manifest dict
  * fetch_manifest(url_or_path)
  * validate(manifest_dict)            # version-dispatched
  * render_consent(manifest_dict)
  * collect_env(env_specs, ...)
  * lint(manifest_dict)                # best-practice findings
  * diff(a, b)                         # same-version change classification

`build_manifest` (the `init` subcommand's engine) writes a local scaffold
file — the one authoring affordance. Tool-side-effecting operations
(install, smoke, persist, revoke) are intentionally not yet exposed — they
will land in subsequent versions, behind explicit subcommands.
"""
from .errors import (
    FetchError,
    ValidationError,
    EnvCollectionError,
)
from .fetch import fetch_manifest
from .init import build_manifest
from .validate import validate, ValidationResult
from .consent import render_consent, collect_consent
from .collect_env import collect_env
from .lint import lint, LintFinding
from .diff import diff, DiffResult, Change, DiffError

__version__ = "0.6.0"

__all__ = [
    "__version__",
    "build_manifest",
    "FetchError",
    "ValidationError",
    "EnvCollectionError",
    "fetch_manifest",
    "validate",
    "ValidationResult",
    "render_consent",
    "collect_consent",
    "collect_env",
    "lint",
    "LintFinding",
    "diff",
    "DiffResult",
    "Change",
    "DiffError",
]
