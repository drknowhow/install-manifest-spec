"""CLI surface tests for `install-manifest lint`.

Drives `__main__.main(argv=[...])` directly so we get real argparse + exit
codes without spawning subprocesses (fast on Windows CI).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from install_manifest.__main__ import main


def _write_manifest(tmp_path: Path, manifest: dict, name: str = "m.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


def _clean(base: dict) -> dict:
    m = copy.deepcopy(base)
    m["tool"]["id"] = "clean-tool"
    m["tool"]["version"] = "1.0.0"
    m["verify"] = {
        "suite": {"ref": "./suite.jsonl", "format": "jsonl-cases"},
        "sla": {"p95_latency_ms": 1500},
    }
    m["actions"][0]["docs"] = {"goal": "Print the tool version."}
    return m


def test_lint_clean_exits_zero(tmp_path, minimal_manifest_v0_4, capsys):
    path = _write_manifest(tmp_path, _clean(minimal_manifest_v0_4))
    rc = main(["lint", str(path)])
    assert rc == 0


def test_lint_with_findings_exits_zero_by_default(tmp_path, minimal_manifest_v0_4, capsys):
    m = _clean(minimal_manifest_v0_4)
    m["tool"]["id"] = "double--hyphen"  # LM007 — schema-valid lowercase but bad kebab
    path = _write_manifest(tmp_path, m)
    rc = main(["lint", str(path)])
    assert rc == 0


def test_lint_strict_with_findings_exits_six(tmp_path, minimal_manifest_v0_4, capsys):
    m = _clean(minimal_manifest_v0_4)
    m["tool"]["id"] = "double--hyphen"  # LM007 — schema-valid lowercase but bad kebab
    path = _write_manifest(tmp_path, m)
    rc = main(["lint", "--strict", str(path)])
    assert rc == 6


def test_lint_ignore_drops_finding(tmp_path, minimal_manifest_v0_4, capsys):
    m = _clean(minimal_manifest_v0_4)
    m["tool"]["id"] = "double--hyphen"  # LM007 — schema-valid lowercase but bad kebab
    path = _write_manifest(tmp_path, m)
    rc = main(["lint", "--strict", "--ignore", "LM007", str(path)])
    assert rc == 0


def test_lint_json_output_is_array(tmp_path, minimal_manifest_v0_4, capsys):
    m = _clean(minimal_manifest_v0_4)
    m["tool"]["id"] = "double--hyphen"  # LM007 — schema-valid lowercase but bad kebab
    m["tool"]["version"] = "01.0.0"  # LM008 — schema-valid but leading-zero SemVer
    path = _write_manifest(tmp_path, m)
    rc = main(["lint", "--json", str(path)])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    codes = {f["code"] for f in data}
    assert {"LM007", "LM008"}.issubset(codes)


def test_lint_invalid_manifest_exits_three(tmp_path, capsys):
    bad = {"manifest_version": "0.4"}  # missing required tool, runtime, etc.
    path = _write_manifest(tmp_path, bad)
    rc = main(["lint", str(path)])
    assert rc == 3


def test_lint_fetch_failure_exits_two(tmp_path, capsys):
    rc = main(["lint", str(tmp_path / "does-not-exist.json")])
    assert rc == 2


def test_lint_finding_lines_on_stderr(tmp_path, minimal_manifest_v0_4, capsys):
    m = _clean(minimal_manifest_v0_4)
    m["tool"]["id"] = "double--hyphen"
    path = _write_manifest(tmp_path, m)
    main(["lint", str(path)])
    err = capsys.readouterr().err
    assert "LM007" in err
    assert "warning" in err
