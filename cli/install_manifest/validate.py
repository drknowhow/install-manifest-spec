"""Validate a manifest dict against the bundled v0.1 JSON Schema.

Two surfaces:

  * `validate(manifest)` — returns a structured `ValidationResult`
    (`.ok`, `.errors`, `.summary`) without raising. The CLI dispatch
    uses this so it can pretty-print every violation at once.

  * `validate_or_raise(manifest)` — raises `ValidationError` on any
    schema violation. Useful for callers that want fail-fast semantics.

The schema is loaded once (lazily) on first call from the bundled
`_data/install-manifest-v0.1.json` shipped with the package. In a
development checkout the validator falls back to the canonical
`schema/install-manifest-v0.1.json` at the repo root, so editing the
schema and running tests does not require a re-copy step.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Iterator, List, Tuple

import jsonschema
from jsonschema import Draft202012Validator

from .errors import SchemaError, ValidationError

SCHEMA_FILENAME = "install-manifest-v0.1.json"
EXPECTED_MANIFEST_VERSION = "0.1"


@dataclass
class ValidationResult:
    """Structured validation outcome."""
    ok: bool
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (json_pointer, message)
    summary: str = ""


_validator: Draft202012Validator | None = None


def _load_schema_dict() -> dict:
    """Locate and load the bundled or repo-root schema."""
    # 1. Packaged copy (works after `pip install`).
    try:
        files = resources.files("install_manifest").joinpath("_data").joinpath(SCHEMA_FILENAME)
        if files.is_file():
            return json.loads(files.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):
        pass

    # 2. Development fallback: walk up to find schema/install-manifest-v0.1.json.
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / SCHEMA_FILENAME
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))

    raise SchemaError(
        f"could not locate bundled schema {SCHEMA_FILENAME}. "
        "Reinstall the package or run from the repo root."
    )


def _get_validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        schema = _load_schema_dict()
        # Confirm meta-validity so a corrupted bundled schema fails loudly
        # rather than silently rejecting valid manifests.
        Draft202012Validator.check_schema(schema)
        _validator = Draft202012Validator(schema)
    return _validator


def _format_pointer(error: jsonschema.ValidationError) -> str:
    if not error.absolute_path:
        return "/"
    parts = []
    for token in error.absolute_path:
        token_s = str(token).replace("~", "~0").replace("/", "~1")
        parts.append(token_s)
    return "/" + "/".join(parts)


def _iter_errors(manifest: Any) -> Iterator[jsonschema.ValidationError]:
    validator = _get_validator()
    yield from validator.iter_errors(manifest)


def validate(manifest: Any) -> ValidationResult:
    """Validate `manifest` against the bundled v0.1 schema.

    Returns a `ValidationResult`. Never raises for schema violations;
    raises `SchemaError` only if the bundled schema cannot be loaded.
    """
    if not isinstance(manifest, dict):
        return ValidationResult(
            ok=False,
            errors=[("/", f"manifest top-level must be an object, got {type(manifest).__name__}")],
            summary="invalid type at root",
        )

    errors: List[Tuple[str, str]] = []
    for err in _iter_errors(manifest):
        errors.append((_format_pointer(err), err.message))

    # Extra sanity: manifest_version must literally be "0.1". The schema
    # already enforces this, but surface it as the first error if missing
    # so the user sees the version mismatch front and center.
    declared_version = manifest.get("manifest_version")
    if declared_version is not None and declared_version != EXPECTED_MANIFEST_VERSION:
        # Preserve any other errors, but make sure the version mismatch
        # message is unambiguous.
        version_msg = (
            f"manifest_version is {declared_version!r}; "
            f"this CLI only supports {EXPECTED_MANIFEST_VERSION!r}"
        )
        if not any(p == "/manifest_version" for p, _ in errors):
            errors.insert(0, ("/manifest_version", version_msg))

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
