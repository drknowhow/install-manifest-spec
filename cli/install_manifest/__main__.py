"""argparse dispatch for the install-manifest CLI.

v0.1.0 subcommands (read-only / prompt-only):
  validate <url-or-path>            — fetch + validate against schema
  show     <url-or-path>            — fetch + validate + render consent screen
  collect-env <url-or-path>         — fetch + validate + render consent + prompt env

Side-effecting subcommands (install / smoke / persist / revoke) are
intentionally not exposed in 0.1.0; they will land in subsequent versions.

Exit codes:
  0  ok
  1  unhandled error (bug)
  2  fetch failed
  3  validation failed
  4  consent declined or non-interactive without --yes
  5  env collection failed
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__
from .collect_env import collect_env
from .consent import collect_consent, render_consent
from .errors import EnvCollectionError, FetchError, SchemaError, ValidationError
from .fetch import fetch_manifest
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


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="install-manifest",
        description="Reference CLI for the install-manifest v0.1 spec.",
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

    return p


def _print_validation_failure(source: str, result) -> None:
    print(f"error: manifest at {source} is invalid: {result.summary}", file=sys.stderr)
    for ptr, msg in result.errors:
        print(f"  {ptr}: {msg}", file=sys.stderr)


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        manifest, _raw = fetch_manifest(args.source)
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    result = validate(manifest)
    if not result.ok:
        _print_validation_failure(args.source, result)
        return 3

    tool = manifest.get("tool", {})
    print(f"ok: {tool.get('name', '?')} v{tool.get('version', '?')} — manifest valid")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    try:
        manifest, _raw = fetch_manifest(args.source)
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    result = validate(manifest)
    if not result.ok:
        _print_validation_failure(args.source, result)
        return 3

    sys.stdout.write(render_consent(manifest))
    return 0


def cmd_collect_env(args: argparse.Namespace) -> int:
    try:
        manifest, _raw = fetch_manifest(args.source)
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    result = validate(manifest)
    if not result.ok:
        _print_validation_failure(args.source, result)
        return 3

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

    # Print a recap of NON-secret values; never print secret values.
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
