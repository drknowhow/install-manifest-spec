"""CLI surface tests for `install-manifest diff`."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from install_manifest.__main__ import main


def _write(tmp_path: Path, manifest: dict, name: str) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


def test_diff_byte_equivalent_exits_zero(tmp_path, minimal_manifest_v0_4):
    a = _write(tmp_path, minimal_manifest_v0_4, "a.json")
    b = _write(tmp_path, minimal_manifest_v0_4, "b.json")
    rc = main(["diff", str(a), str(b)])
    assert rc == 0


def test_diff_breaking_default_exits_zero(tmp_path, minimal_manifest_v0_4):
    """Default mode reports but never fails."""
    a_dict = copy.deepcopy(minimal_manifest_v0_4)
    a_dict["actions"].append({
        "name": "extra",
        "summary": "x",
        "invocation": {"kind": "subcommand", "argv_template": ["extra"]},
        "output": {"format": "text"},
        "side_effects": "none",
        "idempotent": True,
    })
    a_dict["tool"]["version"] = "0.9.0"
    b_dict = copy.deepcopy(minimal_manifest_v0_4)
    b_dict["tool"]["version"] = "1.0.0"
    a = _write(tmp_path, a_dict, "a.json")
    b = _write(tmp_path, b_dict, "b.json")
    rc = main(["diff", str(a), str(b)])
    assert rc == 0


def test_diff_upgrade_safe_with_breaking_exits_seven(tmp_path, minimal_manifest_v0_4):
    a_dict = copy.deepcopy(minimal_manifest_v0_4)
    a_dict["actions"].append({
        "name": "extra",
        "summary": "x",
        "invocation": {"kind": "subcommand", "argv_template": ["extra"]},
        "output": {"format": "text"},
        "side_effects": "none",
        "idempotent": True,
    })
    a_dict["tool"]["version"] = "0.9.0"
    b_dict = copy.deepcopy(minimal_manifest_v0_4)
    b_dict["tool"]["version"] = "1.0.0"
    a = _write(tmp_path, a_dict, "a.json")
    b = _write(tmp_path, b_dict, "b.json")
    rc = main(["diff", "--upgrade-safe", str(a), str(b)])
    assert rc == 7


def test_diff_upgrade_safe_additive_only_exits_zero(tmp_path, minimal_manifest_v0_4):
    a_dict = copy.deepcopy(minimal_manifest_v0_4)
    a_dict["tool"]["version"] = "0.9.0"
    b_dict = copy.deepcopy(minimal_manifest_v0_4)
    b_dict["actions"].append({
        "name": "extra",
        "summary": "x",
        "invocation": {"kind": "subcommand", "argv_template": ["extra"]},
        "output": {"format": "text"},
        "side_effects": "none",
        "idempotent": True,
    })
    b_dict["tool"]["version"] = "1.0.0"
    a = _write(tmp_path, a_dict, "a.json")
    b = _write(tmp_path, b_dict, "b.json")
    rc = main(["diff", "--upgrade-safe", str(a), str(b)])
    assert rc == 0


def test_diff_json_format(tmp_path, minimal_manifest_v0_4, capsys):
    a_dict = copy.deepcopy(minimal_manifest_v0_4)
    a_dict["tool"]["version"] = "0.9.0"
    b_dict = copy.deepcopy(minimal_manifest_v0_4)
    b_dict["tool"]["version"] = "1.0.0"
    a = _write(tmp_path, a_dict, "a.json")
    b = _write(tmp_path, b_dict, "b.json")
    rc = main(["diff", "--format", "json", str(a), str(b)])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert set(data.keys()) == {"breaking", "additive", "cosmetic"}
    assert any(c["kind"] == "tool-version-bumped" for c in data["cosmetic"])


def test_diff_cross_version_exits_three(tmp_path, minimal_manifest, minimal_manifest_v0_3):
    a = _write(tmp_path, minimal_manifest, "a.json")
    b = _write(tmp_path, minimal_manifest_v0_3, "b.json")
    rc = main(["diff", str(a), str(b)])
    assert rc == 3


def test_diff_fetch_failure_exits_two(tmp_path, minimal_manifest_v0_4):
    a = _write(tmp_path, minimal_manifest_v0_4, "a.json")
    rc = main(["diff", str(a), str(tmp_path / "missing.json")])
    assert rc == 2
