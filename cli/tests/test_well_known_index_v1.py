"""Tests for the well-known-index v1 schema.

The well-known index is a sibling spec to install-manifest — it tells
registries which install-manifest URLs a publisher claims, but is NOT
itself an install-manifest version. It therefore lives outside the
install_manifest CLI's version-dispatch surface and is validated here
directly against the bundled schema using jsonschema.

These tests pin the v1 contract: identity-kind id patterns, the
deprecated-without-target rejection, the manifest_version enum, the
top-level const on `version`, and additionalProperties on every object.
Drift in any of them would silently widen the contract for downstream
publishers and registries.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "well-known-index-v1.json"
EXAMPLE_PATH = REPO_ROOT / "examples" / "install-manifests-index.muninn.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture
def example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def _errors(validator, doc):
    return list(validator.iter_errors(doc))


# ---- Happy path ------------------------------------------------------------


def test_schema_is_valid_draft_2020_12(schema):
    Draft202012Validator.check_schema(schema)


def test_example_validates(validator, example):
    errors = _errors(validator, example)
    assert not errors, [(list(e.path), e.message) for e in errors]


# ---- Top-level constraints -------------------------------------------------


def test_version_const(validator, example):
    bad = copy.deepcopy(example)
    bad["version"] = "2"
    assert _errors(validator, bad), "non-1 version must be rejected"


def test_top_level_additional_properties_rejected(validator, example):
    bad = copy.deepcopy(example)
    bad["extra_field"] = "nope"
    assert _errors(validator, bad)


def test_required_fields_missing(validator, example):
    for field in ("version", "publisher", "generated_at", "manifests"):
        bad = copy.deepcopy(example)
        bad.pop(field)
        assert _errors(validator, bad), f"missing {field} must be rejected"


def test_empty_manifests_is_legal(validator, example):
    """A publisher with no current tools still publishes a well-formed index."""
    doc = copy.deepcopy(example)
    doc["manifests"] = []
    assert not _errors(validator, doc)


# ---- Identity-kind id patterns --------------------------------------------


def test_github_kind_requires_owner_repo(validator, example):
    bad = copy.deepcopy(example)
    bad["publisher"]["id"] = "nope-no-slash"
    assert _errors(validator, bad)


def test_https_kind_rejects_owner_repo_shape(validator, example):
    bad = copy.deepcopy(example)
    bad["publisher"]["kind"] = "https"
    bad["publisher"]["id"] = "oaustegard/muninn-utilities"
    assert _errors(validator, bad)


def test_https_kind_accepts_bare_hostname(validator, example):
    doc = copy.deepcopy(example)
    doc["publisher"]["kind"] = "https"
    doc["publisher"]["id"] = "muninn.example.com"
    assert not _errors(validator, doc)


def test_atproto_kind_requires_did_pattern(validator, example):
    bad = copy.deepcopy(example)
    bad["publisher"]["kind"] = "atproto"
    bad["publisher"]["id"] = "not-a-did"
    bad["publisher"]["atproto_record_uri"] = "at://did:plc:abcdefghijklmnopqrstuvwx/app.toolspace.installManifests/self"
    assert _errors(validator, bad)


def test_atproto_kind_requires_record_uri(validator, example):
    bad = copy.deepcopy(example)
    bad["publisher"]["kind"] = "atproto"
    bad["publisher"]["id"] = "did:plc:abcdefghijklmnopqrstuvwx"
    bad["publisher"].pop("atproto_record_uri", None)
    assert _errors(validator, bad)


def test_atproto_kind_happy_path(validator, example):
    doc = copy.deepcopy(example)
    doc["publisher"]["kind"] = "atproto"
    doc["publisher"]["id"] = "did:plc:abcdefghijklmnopqrstuvwx"
    doc["publisher"]["atproto_record_uri"] = "at://did:plc:abcdefghijklmnopqrstuvwx/app.toolspace.installManifests/self"
    assert not _errors(validator, doc)


def test_atproto_did_web_form(validator, example):
    doc = copy.deepcopy(example)
    doc["publisher"]["kind"] = "atproto"
    doc["publisher"]["id"] = "did:web:example.com"
    doc["publisher"]["atproto_record_uri"] = "at://did:web:example.com/app.toolspace.installManifests/self"
    assert not _errors(validator, doc)


# ---- manifests[] item constraints -----------------------------------------


def test_tool_id_pattern_rejects_uppercase(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["id"] = "BadID"
    assert _errors(validator, bad)


def test_tool_id_pattern_rejects_underscore(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["id"] = "bad_id_with_underscore"
    assert _errors(validator, bad)


def test_manifest_version_enum_rejects_unknown(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["manifest_version"] = "0.99"
    assert _errors(validator, bad)


def test_manifest_version_enum_accepts_all_current(validator, example):
    for v in ("0.1", "0.2", "0.3", "0.3.1", "0.4"):
        doc = copy.deepcopy(example)
        doc["manifests"][0]["manifest_version"] = v
        errs = _errors(validator, doc)
        # Some prior-version manifests in deprecated state would still need
        # deprecated_in_favor_of; only verify here that the enum itself accepts.
        assert not any("manifest_version" in str(e.path) for e in errs), (v, [e.message for e in errs])


def test_status_enum(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["status"] = "experimental"
    assert _errors(validator, bad)


def test_deprecated_requires_in_favor_of(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["status"] = "deprecated"
    bad["manifests"][0].pop("deprecated_in_favor_of", None)
    assert _errors(validator, bad)


def test_deprecated_in_favor_of_pattern(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["status"] = "deprecated"
    bad["manifests"][0]["deprecated_in_favor_of"] = "BadID"
    assert _errors(validator, bad)


def test_tags_pattern_lowercase_hyphen_only(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["tags"] = ["BadTag"]
    assert _errors(validator, bad)


def test_summary_max_280(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["summary"] = "x" * 281
    assert _errors(validator, bad)


def test_manifest_item_additional_properties_rejected(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0]["extra"] = True
    assert _errors(validator, bad)


# ---- Required-when-absent cases -------------------------------------------


def test_manifest_url_required(validator, example):
    bad = copy.deepcopy(example)
    bad["manifests"][0].pop("manifest_url")
    assert _errors(validator, bad)


def test_publisher_display_name_required(validator, example):
    bad = copy.deepcopy(example)
    bad["publisher"].pop("display_name")
    assert _errors(validator, bad)


def test_publisher_display_name_cap_80(validator, example):
    bad = copy.deepcopy(example)
    bad["publisher"]["display_name"] = "x" * 81
    assert _errors(validator, bad)


def test_generated_at_is_datetime(validator, example):
    """format=date-time is advisory in 2020-12 by default — at minimum the
    schema must not reject a well-formed timestamp."""
    doc = copy.deepcopy(example)
    doc["generated_at"] = "2026-05-28T00:00:00Z"
    assert not _errors(validator, doc)
