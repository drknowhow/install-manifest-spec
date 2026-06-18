"""Tests for the manifest scaffold builder (`install_manifest.init`)."""
from __future__ import annotations

from install_manifest.init import _module_from_id, _name_from_id, build_manifest
from install_manifest.validate import validate


def test_default_scaffold_validates():
    m = build_manifest()
    result = validate(m)
    assert result.ok, result.errors
    assert m["manifest_version"] == "0.4"
    assert m["tool"]["id"] == "my-tool"


def test_custom_fields_flow_through():
    m = build_manifest(
        tool_id="acme-mailer",
        name="Acme Mailer",
        summary="Sends mail.",
        homepage="https://acme.example/mailer",
        package="acme-mailer-pkg",
        author="Jane D.",
    )
    assert validate(m).ok, validate(m).errors
    assert m["tool"]["id"] == "acme-mailer"
    assert m["tool"]["name"] == "Acme Mailer"
    assert m["tool"]["summary"] == "Sends mail."
    assert m["tool"]["homepage"] == "https://acme.example/mailer"
    assert m["runtime"]["install"]["package"] == "acme-mailer-pkg"
    assert m["tool"]["author"] == {"name": "Jane D."}
    # entrypoint module derives from the id (hyphens -> underscores)
    assert m["runtime"]["entrypoint"]["command"] == ["python", "-m", "acme_mailer.server"]


def test_name_and_package_default_from_id():
    m = build_manifest(tool_id="my-cool-tool")
    assert m["tool"]["name"] == "My Cool Tool"
    assert m["runtime"]["install"]["package"] == "my-cool-tool"


def test_author_omitted_when_absent():
    m = build_manifest()
    assert "author" not in m["tool"]


def test_summary_falls_back_to_placeholder():
    m = build_manifest(tool_id="x-tool", summary=None)
    assert m["tool"]["summary"].startswith("TODO:")


def test_scaffold_does_not_force_data_boundary():
    """The example scope is non-private, so data_boundary stays optional —
    keeping the scaffold both minimal and valid."""
    m = build_manifest()
    assert "data_boundary" not in m
    assert validate(m).ok


def test_helpers():
    assert _module_from_id("my-tool") == "my_tool"
    assert _name_from_id("my-tool") == "My Tool"
    assert _name_from_id("foo_bar-baz") == "Foo Bar Baz"
