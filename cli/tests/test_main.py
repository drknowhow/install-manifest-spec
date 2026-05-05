"""End-to-end tests of the argparse dispatch.

We invoke `install_manifest.__main__.main(argv)` directly so we can capture
exit codes and assert on output without a subprocess.
"""
from __future__ import annotations

import io
import json
import sys

import pytest

from install_manifest.__main__ import main


def _run(argv, capsys):
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_validate_ok(tmp_path, minimal_manifest, capsys):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(minimal_manifest), encoding="utf-8")
    code, out, _err = _run(["validate", str(p)], capsys)
    assert code == 0
    assert "ok:" in out
    assert "Tiny Tool" in out


def test_validate_invalid(tmp_path, minimal_manifest, capsys):
    """An unsupported manifest_version short-circuits with a clear error."""
    bad = dict(minimal_manifest)
    bad["manifest_version"] = "9.9"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    code, _out, err = _run(["validate", str(p)], capsys)
    assert code == 3
    assert "manifest_version" in err


def test_validate_fetch_fail(tmp_path, capsys):
    code, _out, err = _run(["validate", str(tmp_path / "nonexistent.json")], capsys)
    assert code == 2
    assert "error:" in err


def test_show_renders_consent(tmp_path, minimal_manifest, capsys):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(minimal_manifest), encoding="utf-8")
    code, out, _err = _run(["show", str(p)], capsys)
    assert code == 0
    assert "Tiny Tool" in out
    assert "Verification:" in out


def test_collect_env_non_interactive_without_yes_fails(tmp_path, minimal_manifest, capsys):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(minimal_manifest), encoding="utf-8")
    code, _out, err = _run(
        ["collect-env", str(p), "--non-interactive"],
        capsys,
    )
    assert code == 4
    assert "non-interactive" in err.lower()


def test_collect_env_non_interactive_with_yes_succeeds_when_no_env(tmp_path, minimal_manifest, capsys):
    """Minimal manifest has no env block, so --yes --non-interactive should succeed."""
    p = tmp_path / "m.json"
    p.write_text(json.dumps(minimal_manifest), encoding="utf-8")
    code, out, _err = _run(
        ["collect-env", str(p), "--yes", "--non-interactive"],
        capsys,
    )
    assert code == 0
    assert "collected:" in out


def test_collect_env_uses_env_flag(tmp_path, minimal_manifest, capsys):
    m = dict(minimal_manifest)
    m["env"] = [{"name": "TOKEN", "prompt": "Token", "secret": True}]
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m), encoding="utf-8")
    code, out, _err = _run(
        ["collect-env", str(p), "--yes", "--non-interactive", "--env", "TOKEN=tok_xyz"],
        capsys,
    )
    assert code == 0
    # Secret value must NOT appear in stdout; only a length-redacted form.
    assert "tok_xyz" not in out
    assert "TOKEN: <secret" in out


def test_collect_env_missing_required_in_non_interactive(tmp_path, minimal_manifest, capsys):
    m = dict(minimal_manifest)
    m["env"] = [{"name": "REQ", "prompt": "Required value", "secret": False}]
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m), encoding="utf-8")
    code, _out, err = _run(
        ["collect-env", str(p), "--yes", "--non-interactive"],
        capsys,
    )
    assert code == 5
    assert "REQ" in err
