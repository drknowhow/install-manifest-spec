"""install-manifest — reference CLI for the install-manifest spec.

Supports manifest_version 0.1 and 0.2. The validator dispatches on the
manifest's declared version automatically.

This MVP exposes:
  * fetch_manifest(url_or_path)
  * validate(manifest_dict)            # version-dispatched
  * render_consent(manifest_dict)
  * collect_env(env_specs, ...)

Side-effecting operations (install, smoke, persist, revoke) are intentionally
not yet exposed — they will land in subsequent versions, behind explicit
subcommands. The current release is read-only and prompt-only.
"""
from .errors import (
    FetchError,
    ValidationError,
    EnvCollectionError,
)
from .fetch import fetch_manifest
from .validate import validate, ValidationResult
from .consent import render_consent, collect_consent
from .collect_env import collect_env

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "FetchError",
    "ValidationError",
    "EnvCollectionError",
    "fetch_manifest",
    "validate",
    "ValidationResult",
    "render_consent",
    "collect_consent",
    "collect_env",
]
