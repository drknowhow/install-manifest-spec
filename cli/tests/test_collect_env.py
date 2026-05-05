"""Tests for install_manifest.collect_env."""
from __future__ import annotations

import io

import pytest

from install_manifest.collect_env import collect_env
from install_manifest.errors import EnvCollectionError


def _spec(name, *, secret=False, required=True, default=None, regex=None, prompt=None):
    s = {"name": name, "prompt": prompt or f"Enter {name}", "secret": secret, "required": required}
    if default is not None:
        s["default"] = default
    if regex is not None:
        s["validation_regex"] = regex
    return s


def test_override_wins():
    out = collect_env(
        [_spec("FOO")],
        non_interactive=True,
        env_overrides={"FOO": "value-from-flag"},
        process_env={"FOO": "value-from-env"},
    )
    assert out == {"FOO": "value-from-flag"}


def test_process_env_used_when_no_override():
    out = collect_env(
        [_spec("FOO")],
        non_interactive=True,
        env_overrides={},
        process_env={"FOO": "value-from-env"},
    )
    assert out == {"FOO": "value-from-env"}


def test_default_used_when_no_override_or_env():
    out = collect_env(
        [_spec("FOO", default="dflt", secret=False)],
        non_interactive=True,
        env_overrides={},
        process_env={},
    )
    assert out == {"FOO": "dflt"}


def test_required_missing_non_interactive_raises():
    with pytest.raises(EnvCollectionError) as exc:
        collect_env(
            [_spec("FOO")],
            non_interactive=True,
            env_overrides={},
            process_env={},
        )
    assert "FOO" in str(exc.value)
    assert "required" in str(exc.value).lower()


def test_optional_missing_non_interactive_skipped():
    out = collect_env(
        [_spec("FOO", required=False)],
        non_interactive=True,
        env_overrides={},
        process_env={},
    )
    assert out == {}


def test_regex_match_passes():
    out = collect_env(
        [_spec("TOKEN", regex=r"^tok_[a-f0-9]+$")],
        non_interactive=True,
        env_overrides={"TOKEN": "tok_deadbeef"},
        process_env={},
    )
    assert out == {"TOKEN": "tok_deadbeef"}


def test_regex_mismatch_non_interactive_raises():
    with pytest.raises(EnvCollectionError) as exc:
        collect_env(
            [_spec("TOKEN", regex=r"^tok_[a-f0-9]+$")],
            non_interactive=True,
            env_overrides={"TOKEN": "wrong-format"},
            process_env={},
        )
    assert "TOKEN" in str(exc.value)


def test_invalid_regex_raises():
    with pytest.raises(EnvCollectionError):
        collect_env(
            [_spec("X", regex=r"[unclosed")],
            non_interactive=True,
            env_overrides={"X": "anything"},
            process_env={},
        )


def test_empty_string_treated_as_missing():
    """An override of "" must NOT count as a provided value."""
    with pytest.raises(EnvCollectionError):
        collect_env(
            [_spec("FOO")],
            non_interactive=True,
            env_overrides={"FOO": ""},
            process_env={"FOO": ""},
        )


def test_missing_name_raises():
    with pytest.raises(EnvCollectionError):
        collect_env(
            [{"prompt": "x", "secret": False}],
            non_interactive=True,
            env_overrides={},
            process_env={},
        )


def test_interactive_prompt_accepts_value():
    stdin = io.StringIO("hello\n")
    stdout = io.StringIO()
    out = collect_env(
        [_spec("FOO", secret=False)],
        non_interactive=False,
        env_overrides={},
        process_env={},
        stdin=stdin,
        stdout=stdout,
    )
    assert out == {"FOO": "hello"}


def test_interactive_prompt_retries_on_regex_miss():
    # First answer fails regex, second passes.
    stdin = io.StringIO("badbad\ntok_abc\n")
    stdout = io.StringIO()
    out = collect_env(
        [_spec("TOK", secret=False, regex=r"^tok_[a-z]+$")],
        non_interactive=False,
        env_overrides={},
        process_env={},
        stdin=stdin,
        stdout=stdout,
    )
    assert out == {"TOK": "tok_abc"}
    assert "does not match" in stdout.getvalue()


def test_interactive_optional_skip_with_blank():
    stdin = io.StringIO("\n")
    stdout = io.StringIO()
    out = collect_env(
        [_spec("MAYBE", required=False, secret=False)],
        non_interactive=False,
        env_overrides={},
        process_env={},
        stdin=stdin,
        stdout=stdout,
    )
    assert out == {}
