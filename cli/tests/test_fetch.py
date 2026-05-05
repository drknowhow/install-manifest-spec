"""Tests for install_manifest.fetch."""
from __future__ import annotations

import json
import pytest

from install_manifest.fetch import fetch_manifest, MAX_MANIFEST_BYTES
from install_manifest.errors import FetchError


def test_fetch_local_path(tmp_path, minimal_manifest):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(minimal_manifest), encoding="utf-8")

    manifest, raw = fetch_manifest(str(p))
    assert manifest == minimal_manifest
    assert json.loads(raw.decode("utf-8")) == minimal_manifest


def test_fetch_file_url(tmp_path, minimal_manifest):
    p = tmp_path / "m.json"
    p.write_text(json.dumps(minimal_manifest), encoding="utf-8")

    url = p.as_uri()  # produces file:// URL portably
    manifest, _raw = fetch_manifest(url)
    assert manifest == minimal_manifest


def test_fetch_missing_file(tmp_path):
    with pytest.raises(FetchError) as exc:
        fetch_manifest(str(tmp_path / "nope.json"))
    assert "not found" in str(exc.value).lower()


def test_fetch_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(FetchError) as exc:
        fetch_manifest(str(p))
    assert "not valid json" in str(exc.value).lower()


def test_fetch_non_object_top_level(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(FetchError) as exc:
        fetch_manifest(str(p))
    assert "object" in str(exc.value).lower()


def test_fetch_empty_url():
    with pytest.raises(FetchError):
        fetch_manifest("")


def test_fetch_unsupported_scheme():
    with pytest.raises(FetchError) as exc:
        fetch_manifest("ftp://example.com/m.json")
    assert "scheme" in str(exc.value).lower()


def test_fetch_oversized_local(tmp_path):
    p = tmp_path / "huge.json"
    # Build something obviously valid JSON-shaped that exceeds the cap.
    payload = '{"k":"' + ("a" * (MAX_MANIFEST_BYTES + 1024)) + '"}'
    p.write_text(payload, encoding="utf-8")
    with pytest.raises(FetchError) as exc:
        fetch_manifest(str(p))
    assert "exceeds" in str(exc.value).lower() or "limit" in str(exc.value).lower()


def test_fetch_real_example(example_manifest_path):
    manifest, raw = fetch_manifest(str(example_manifest_path))
    assert manifest["manifest_version"] == "0.1"
    assert raw  # bytes returned
