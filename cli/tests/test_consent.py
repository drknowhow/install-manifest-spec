"""Tests for install_manifest.consent."""
from __future__ import annotations

import io

from install_manifest.consent import collect_consent, render_consent


def test_render_minimal(minimal_manifest):
    out = render_consent(minimal_manifest)
    assert "Tiny Tool" in out
    assert "v1.0.0" in out
    # Permissions section says 'none declared' if no scopes.
    assert "none declared" in out
    # Verification line mentions the smoke kind.
    assert "shell smoke" in out
    # Manual revocation echoes the instructions URL.
    assert "MANUAL" in out
    assert "example.com" in out


def test_render_with_scopes(minimal_manifest):
    m = dict(minimal_manifest)
    m["scopes"] = [
        {
            "resource": "fs.local",
            "actions": ["read", "write"],
            "rationale": "Reads and writes config files in the user's home directory.",
        },
    ]
    out = render_consent(m)
    assert "fs.local" in out
    assert "read, write" in out
    assert "Reads and writes" in out


def test_render_secret_count(minimal_manifest):
    m = dict(minimal_manifest)
    m["env"] = [
        {"name": "API_KEY", "prompt": "API key", "secret": True},
        {"name": "REGION", "prompt": "Region", "secret": False},
    ]
    out = render_consent(m)
    assert "1 secret" in out
    assert "1 non-secret" in out
    assert "API_KEY" in out
    assert "REGION" in out


def test_render_external_cost(minimal_manifest):
    m = dict(minimal_manifest)
    m["cost"] = {"usage_model": "external"}
    out = render_consent(m)
    assert "external billing" in out


def test_render_concrete_cost(minimal_manifest):
    m = dict(minimal_manifest)
    m["cost"] = {
        "usage_model": "per-call",
        "install_fee_cents": 0,
        "monthly_fee_cents": 500,
    }
    out = render_consent(m)
    assert "per-call" in out
    assert "$5.00" in out


def test_render_url_kill_switch(minimal_manifest):
    m = dict(minimal_manifest)
    m["kill_switch"] = {"kind": "url", "url": "https://example.com/revoke"}
    out = render_consent(m)
    assert "DELETE https://example.com/revoke" in out


def test_render_no_secret_value_in_output(minimal_manifest):
    """Defense-in-depth: even though render_consent never sees env values,
    confirm secret env names are present but not flagged as values."""
    m = dict(minimal_manifest)
    m["env"] = [{"name": "VERY_SECRET_KEY", "prompt": "Token", "secret": True}]
    out = render_consent(m)
    assert "VERY_SECRET_KEY" in out
    assert "[secret]" in out


def test_collect_consent_yes():
    stdin = io.StringIO("y\n")
    stdout = io.StringIO()
    assert collect_consent(stdin=stdin, stdout=stdout) is True


def test_collect_consent_no_default():
    stdin = io.StringIO("\n")
    stdout = io.StringIO()
    assert collect_consent(stdin=stdin, stdout=stdout) is False


def test_collect_consent_eof():
    stdin = io.StringIO("")
    stdout = io.StringIO()
    assert collect_consent(stdin=stdin, stdout=stdout) is False


def test_collect_consent_explicit_no():
    stdin = io.StringIO("no\n")
    stdout = io.StringIO()
    assert collect_consent(stdin=stdin, stdout=stdout) is False
