"""argparse dispatch for the install-manifest CLI.

v0.5.0 subcommands (read-only / prompt-only):
  validate <url-or-path>            — fetch + validate against schema
  show     <url-or-path>            — fetch + validate + render consent screen
  collect-env <url-or-path>         — fetch + validate + render consent + prompt env
  lint     <url-or-path>            — fetch + validate + run best-practice lint rules
  diff     <url-a> <url-b>          — fetch + validate both + classify changes

Side-effecting subcommands (install / smoke / persist / revoke) are
intentionally not exposed; they will land in subsequent versions.

Exit codes:
  0  ok
  1  unhandled error (bug)
  2  fetch failed
  3  validation failed (or unsupported diff: cross-version)
  4  consent declined or non-interactive without --yes
  5  env collection failed
  6  lint --strict found findings
  7  diff --upgrade-safe found breaking changes
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .collect_env import collect_env
from .consent import collect_consent, render_consent
from .diff import DiffError, diff as run_diff
from .errors import EnvCollectionError, FetchError, SchemaError, ValidationError
from .fetch import fetch_manifest
from .lint import lint as run_lint
from .validate import validate


def _parse_kv_list(values: Sequence[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for v in values or []:
        if "=" not in v:
            raise SystemExit(f"--env requires KEY=VAL form, got {v!r}")
        k, val = v.split("=", 1)
        if not k:
            raise SystemExit(f"--env key is empty in {v!r}")
        out[k] = val
    return out


def _parse_ignore(value: str | None) -> set[str]:
    if not value:
        return set()
    return {code.strip() for code in value.split(",") if code.strip()}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="install-manifest",
        description="Reference CLI for the install-manifest spec.",
    )
    p.add_argument("--version", action="version", version=f"install-manifest {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Fetch and validate a manifest.")
    p_validate.add_argument("source", help="URL or local path to the manifest.")
    p_validate.set_defaults(func=cmd_validate)

    p_show = sub.add_parser(
        "show",
        help="Fetch, validate, and render the consent screen (read-only preview).",
    )
    p_show.add_argument("source", help="URL or local path to the manifest.")
    p_show.set_defaults(func=cmd_show)

    p_env = sub.add_parser(
        "collect-env",
        help="Fetch, validate, render consent, then prompt for env values. Does NOT install.",
    )
    p_env.add_argument("source", help="URL or local path to the manifest.")
    p_env.add_argument("--yes", action="store_true", help="Skip the consent prompt.")
    p_env.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail rather than prompt; values must come from --env or process env.",
    )
    p_env.add_argument(
        "--env",
        action="append",
        metavar="KEY=VAL",
        help="Provide an env var without prompting. May be repeated.",
    )
    p_env.set_defaults(func=cmd_collect_env)

    p_lint = sub.add_parser(
        "lint",
        help="Fetch, validate, then run best-practice lint rules.",
    )
    p_lint.add_argument("source", help="URL or local path to the manifest.")
    p_lint.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any findings remain after --ignore.",
    )
    p_lint.add_argument(
        "--ignore",
        metavar="CODE,CODE",
        help="Comma-separated list of rule codes to suppress (e.g. LM001,LM004).",
    )
    p_lint.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as a JSON array on stdout.",
    )
    p_lint.set_defaults(func=cmd_lint)

    p_diff = sub.add_parser(
        "diff",
        help="Fetch and validate two manifests at the same version, then classify changes.",
    )
    p_diff.add_argument("source_a", help="URL or local path to the older manifest.")
    p_diff.add_argument("source_b", help="URL or local path to the newer manifest.")
    p_diff.add_argument(
        "--upgrade-safe",
        action="store_true",
        help="Exit non-zero if any breaking changes are found.",
    )
    p_diff.add_argument(
        "--format",
        choices=["human", "json"],
        default="human",
        help="Output format (default: human).",
    )
    p_diff.set_defaults(func=cmd_diff)

    return p


def _print_validation_failure(source: str, result) -> None:
    print(f"error: manifest at {source} is invalid: {result.summary}", file=sys.stderr)
    for ptr, msg in result.errors:
        print(f"  {ptr}: {msg}", file=sys.stderr)


def _fetch_and_validate(source: str):
    """Shared prelude for validate/show/collect-env/lint/diff.

    Returns `(exit_code, manifest)` — manifest is None when exit_code != 0.
    """
    try:
        manifest, _raw = fetch_manifest(source)
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2, None

    result = validate(manifest)
    if not result.ok:
        _print_validation_failure(source, result)
        return 3, None

    return 0, manifest


def cmd_validate(args: argparse.Namespace) -> int:
    code, manifest = _fetch_and_validate(args.source)
    if code:
        return code
    tool = manifest.get("tool", {})
    print(f"ok: {tool.get('name', '?')} v{tool.get('version', '?')} — manifest valid")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    code, manifest = _fetch_and_validate(args.source)
    if code:
        return code
    sys.stdout.write(render_consent(manifest))
    return 0


def cmd_collect_env(args: argparse.Namespace) -> int:
    code, manifest = _fetch_and_validate(args.source)
    if code:
        return code

    sys.stdout.write(render_consent(manifest))

    if not args.yes:
        if args.non_interactive:
            print("error: --non-interactive requires --yes", file=sys.stderr)
            return 4
        if not collect_consent():
            print("install cancelled.")
            return 4

    try:
        overrides = _parse_kv_list(args.env)
    except SystemExit as e:
        print(f"error: {e}", file=sys.stderr)
        return 5

    try:
        values = collect_env(
            manifest.get("env") or [],
            non_interactive=args.non_interactive,
            env_overrides=overrides,
        )
    except EnvCollectionError as e:
        print(f"error: env collection failed: {e}", file=sys.stderr)
        return 5

    env_specs = manifest.get("env") or []
    secret_names = {e["name"] for e in env_specs if e.get("secret")}

    print()
    print("collected:")
    for name, value in values.items():
        if name in secret_names:
            print(f"  {name}: <secret, {len(value)} chars>")
        else:
            print(f"  {name}: {value}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    code, manifest = _fetch_and_validate(args.source)
    if code:
        return code

    ignore = _parse_ignore(args.ignore)
    findings = [f for f in run_lint(manifest) if f.code not in ignore]

    if args.json:
        json.dump([f.as_dict() for f in findings], sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        for f in findings:
            print(f"{f.severity} {f.code} {f.path}: {f.message}", file=sys.stderr)
            if f.suggestion:
                print(f"  suggestion: {f.suggestion}", file=sys.stderr)
        if not findings:
            tool = manifest.get("tool", {})
            print(f"ok: {tool.get('name', '?')} v{tool.get('version', '?')} — no lint findings")

    if args.strict and findings:
        return 6
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    code_a, manifest_a = _fetch_and_validate(args.source_a)
    if code_a:
        return code_a
    code_b, manifest_b = _fetch_and_validate(args.source_b)
    if code_b:
        return code_b

    try:
        result = run_diff(manifest_a, manifest_b)
    except DiffError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    if args.format == "json":
        json.dump(result.as_dict(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        _print_diff_human(result)

    if args.upgrade_safe and result.breaking:
        return 7
    return 0


def _print_diff_human(result) -> None:
    if result.is_empty():
        print("ok: manifests are byte-equivalent — no changes.")
        return

    def section(title: str, changes) -> None:
        print(f"{title} ({len(changes)}):")
        for c in changes:
            print(f"  [{c.kind}] {c.path}: {c.message}")

    section("breaking", result.breaking)
    section("additive", result.additive)
    section("cosmetic", result.cosmetic)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SchemaError as e:
        print(f"internal error: {e}", file=sys.stderr)
        return 1
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
