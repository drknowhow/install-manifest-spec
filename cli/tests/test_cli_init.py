"""End-to-end tests for `install-manifest init` (argparse dispatch)."""
from __future__ import annotations

import json

from install_manifest.__main__ import main
from install_manifest.validate import validate


def _run(argv, capsys):
    code = main(argv)
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def test_init_writes_valid_file(tmp_path, capsys):
    out = tmp_path / "acme.json"
    code, _out, err = _run(["init", "--yes", "--id", "acme-mailer", "-o", str(out)], capsys)
    assert code == 0
    assert out.is_file()
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert validate(manifest).ok, validate(manifest).errors
    assert manifest["tool"]["id"] == "acme-mailer"
    assert "wrote" in err  # status goes to stderr


def test_init_default_output_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code, _out, _err = _run(["init", "--yes", "--id", "foo-bar"], capsys)
    assert code == 0
    assert (tmp_path / "foo-bar.json").is_file()


def test_init_stdout_is_pure_json(capsys):
    code, out, _err = _run(["init", "--yes", "--id", "baz-tool", "-o", "-"], capsys)
    assert code == 0
    manifest = json.loads(out)  # stdout must be parseable JSON, nothing else
    assert validate(manifest).ok
    assert manifest["tool"]["id"] == "baz-tool"


def test_init_refuses_overwrite(tmp_path, capsys):
    out = tmp_path / "exists.json"
    out.write_text("{}", encoding="utf-8")
    code, _out, err = _run(["init", "--yes", "--id", "my-tool", "-o", str(out)], capsys)
    assert code == 8
    assert "already exists" in err
    assert out.read_text(encoding="utf-8") == "{}"  # untouched


def test_init_force_overwrite(tmp_path, capsys):
    out = tmp_path / "exists.json"
    out.write_text("{}", encoding="utf-8")
    code, _out, _err = _run(
        ["init", "--yes", "--id", "my-tool", "-o", str(out), "--force"], capsys
    )
    assert code == 0
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert validate(manifest).ok


def test_init_invalid_id_fails_before_write(tmp_path, capsys):
    out = tmp_path / "x.json"
    code, _out, err = _run(["init", "--yes", "--id", "Bad_ID", "-o", str(out)], capsys)
    assert code == 3
    assert "invalid" in err.lower()
    assert not out.exists()


def test_init_no_flags_uses_valid_defaults(tmp_path, monkeypatch, capsys):
    """`init --yes` with no flags still produces a valid manifest at <default-id>.json."""
    monkeypatch.chdir(tmp_path)
    code, _out, _err = _run(["init", "--yes"], capsys)
    assert code == 0
    manifest = json.loads((tmp_path / "my-tool.json").read_text(encoding="utf-8"))
    assert validate(manifest).ok


class _FakeTTY:
    """Minimal stdin stand-in so cmd_init takes the interactive branch."""
    def isatty(self):  # noqa: D401
        return True


def test_init_interactive_prompts(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _FakeTTY())
    answers = iter([
        "widget-tool",            # id
        "Widget Tool",            # name
        "Does widget things.",    # summary
        "https://widget.example", # homepage
        "widget-pkg",             # package
        "Sam W.",                 # author
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    code, _out, _err = _run(["init"], capsys)  # no --yes -> interactive
    assert code == 0
    manifest = json.loads((tmp_path / "widget-tool.json").read_text(encoding="utf-8"))
    assert validate(manifest).ok
    assert manifest["tool"]["name"] == "Widget Tool"
    assert manifest["tool"]["summary"] == "Does widget things."
    assert manifest["tool"]["author"] == {"name": "Sam W."}
    assert manifest["runtime"]["install"]["package"] == "widget-pkg"
