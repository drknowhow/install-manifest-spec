"""Validate a manifest dict against the bundled JSON Schema for its declared version.

Two surfaces:

  * `validate(manifest)` — returns a structured `ValidationResult`
    (`.ok`, `.errors`, `.summary`) without raising. The CLI dispatch
    uses this so it can pretty-print every violation at once.

  * `validate_or_raise(manifest)` — raises `ValidationError` on any
    schema violation. Useful for callers that want fail-fast semantics.

The schema is loaded once-per-version (lazily) on first call from the
bundled `_data/install-manifest-vX.Y.json` shipped with the package. In a
development checkout the validator falls back to the canonical
`schema/install-manifest-vX.Y.json` at the repo root, so editing a schema
and running tests does not require a re-copy step.

Version dispatch:
  - The manifest's top-level `manifest_version` selects the schema.
  - Versions advertised in `SUPPORTED_MANIFEST_VERSIONS` get a real
    schema lookup. Anything else fails with a clear "unsupported version"
    message rather than silently validating against a wrong schema.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import jsonschema
from jsonschema import Draft202012Validator

from .errors import SchemaError, ValidationError

# Tuple is the order versions are surfaced in error messages.
SUPPORTED_MANIFEST_VERSIONS: Tuple[str, ...] = ("0.1", "0.2", "0.3")

# Back-compat alias kept for any callers who pinned the v0.1-only constant.
EXPECTED_MANIFEST_VERSION = "0.1"

_SCHEMA_FILENAME_FMT = "install-manifest-v{version}.json"


@dataclass
class ValidationResult:
    """Structured validation outcome."""
    ok: bool
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (json_pointer, message)
    summary: str = ""


# Per-version validator cache.
_validators: Dict[str, Draft202012Validator] = {}


def _schema_filename(version: str) -> str:
    return _SCHEMA_FILENAME_FMT.format(version=version)


def _load_schema_dict(version: str) -> dict:
    """Locate and load the bundled or repo-root schema for the given version."""
    filename = _schema_filename(version)

    # 1. Packaged copy (works after `pip install`).
    try:
        files = resources.files("install_manifest").joinpath("_data").joinpath(filename)
        if files.is_file():
            return json.loads(files.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):
        pass

    # 2. Development fallback: walk up to find schema/<filename>.
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / filename
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))

    raise SchemaError(
        f"could not locate bundled schema {filename}. "
        "Reinstall the package or run from the repo root."
    )


def _get_validator(version: str) -> Draft202012Validator:
    cached = _validators.get(version)
    if cached is not None:
        return cached
    schema = _load_schema_dict(version)
    # Confirm meta-validity so a corrupted bundled schema fails loudly
    # rather than silently rejecting valid manifests.
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    _validators[version] = validator
    return validator


def _format_pointer(error: jsonschema.ValidationError) -> str:
    if not error.absolute_path:
        return "/"
    parts = []
    for token in error.absolute_path:
        token_s = str(token).replace("~", "~0").replace("/", "~1")
        parts.append(token_s)
    return "/" + "/".join(parts)


def _iter_errors(manifest: Any, version: str) -> Iterator[jsonschema.ValidationError]:
    validator = _get_validator(version)
    yield from validator.iter_errors(manifest)


def validate(manifest: Any) -> ValidationResult:
    """Validate `manifest` against the bundled schema for its declared version.

    Returns a `ValidationResult`. Never raises for schema violations or
    unsupported versions; raises `SchemaError` only if the bundled schema
    cannot be loaded.
    """
    if not isinstance(manifest, dict):
        return ValidationResult(
            ok=False,
            errors=[("/", f"manifest top-level must be an object, got {type(manifest).__name__}")],
            summary="invalid type at root",
        )

    declared_version = manifest.get("manifest_version")
    if declared_version is None:
        return ValidationResult(
            ok=False,
            errors=[("/manifest_version", "manifest_version is required")],
            summary="missing manifest_version",
        )

    if declared_version not in SUPPORTED_MANIFEST_VERSIONS:
        supported = ", ".join(repr(v) for v in SUPPORTED_MANIFEST_VERSIONS)
        msg = (
            f"manifest_version is {declared_version!r}; "
            f"this CLI supports {{{supported}}}"
        )
        return ValidationResult(
            ok=False,
            errors=[("/manifest_version", msg)],
            summary="unsupported manifest_version",
        )

    errors: List[Tuple[str, str]] = []
    for err in _iter_errors(manifest, declared_version):
        errors.append((_format_pointer(err), err.message))

    if not errors:
        return ValidationResult(ok=True, summary="ok")

    return ValidationResult(
        ok=False,
        errors=errors,
        summary=f"{len(errors)} error(s)",
    )


def validate_or_raise(manifest: Any) -> None:
    """Same as `validate()` but raises `ValidationError` on failure."""
    result = validate(manifest)
    if not result.ok:
        lines = [f"{p}: {m}" for p, m in result.errors]
        raise ValidationError(f"manifest invalid: {result.summary}\n  " + "\n  ".join(lines))
