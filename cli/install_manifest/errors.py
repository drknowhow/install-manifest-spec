"""Typed exceptions for install-manifest.

Each exception corresponds to one phase of the install flow and maps to a
distinct CLI exit code (see __main__.py).
"""
from __future__ import annotations


class InstallManifestError(Exception):
    """Base class for all install-manifest errors."""


class FetchError(InstallManifestError):
    """Raised when the manifest cannot be fetched (network, 404, TLS, etc.)."""


class ValidationError(InstallManifestError):
    """Raised when the manifest is structurally invalid against the schema.

    The structured `validate()` API returns a `ValidationResult` rather than
    raising; this exception is for callers that prefer raise-on-invalid.
    """


class EnvCollectionError(InstallManifestError):
    """Raised when env collection fails (missing required, regex mismatch, etc.)."""


class SchemaError(InstallManifestError):
    """Raised when the bundled schema cannot be located or loaded.

    This is an internal/installation problem, not a manifest problem.
    """
