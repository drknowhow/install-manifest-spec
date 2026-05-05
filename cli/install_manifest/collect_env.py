"""Collect env-var values from the host (interactive or non-interactive).

Source resolution order, per env spec:
  1. `env_overrides` (e.g., from `--env KEY=VAL` flags)
  2. existing process env var
  3. spec's `default`
  4. interactive prompt (only if not non-interactive)

Validation:
  * `validation_regex` is applied if present. In interactive mode, the
    user gets up to MAX_RETRIES retries; in non-interactive mode, a
    regex miss is fatal.
  * Empty strings are treated as "not provided" — required vars must
    have a non-empty value.

Secrets are not echoed at the prompt (uses getpass).
"""
from __future__ import annotations

import getpass
import os
import re
import sys
from typing import Iterable, Mapping, MutableMapping, Sequence

from .errors import EnvCollectionError

MAX_INTERACTIVE_RETRIES = 3


def collect_env(
    env_specs: Sequence[Mapping],
    *,
    non_interactive: bool = False,
    env_overrides: Mapping[str, str] | None = None,
    process_env: Mapping[str, str] | None = None,
    stdin=None,
    stdout=None,
) -> dict[str, str]:
    """Resolve a value for every entry in `env_specs`.

    Returns:
        dict mapping env var name -> resolved value.

    Raises:
        EnvCollectionError: if a required var has no value, or a regex
            mismatch is unrecoverable.
    """
    env_overrides = dict(env_overrides or {})
    process_env = dict(process_env if process_env is not None else os.environ)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    resolved: dict[str, str] = {}

    for spec in env_specs:
        name = spec.get("name")
        if not name or not isinstance(name, str):
            raise EnvCollectionError(f"env spec missing 'name': {spec!r}")

        required = bool(spec.get("required", True))
        secret = bool(spec.get("secret", False))
        default = spec.get("default")
        validation_regex = spec.get("validation_regex")
        prompt_text = spec.get("prompt") or _default_prompt_for(spec)
        obtain_url = spec.get("obtain_url")

        compiled_re = None
        if validation_regex:
            try:
                compiled_re = re.compile(validation_regex)
            except re.error as e:
                raise EnvCollectionError(
                    f"env spec {name}: validation_regex is not a valid regex: {e}"
                ) from e

        # 1. override
        value = env_overrides.get(name)
        # 2. process env
        if value is None or value == "":
            value = process_env.get(name)
        # 3. default
        if value is None or value == "":
            if default is not None:
                value = default

        if value is not None and value != "":
            if compiled_re is not None and not compiled_re.fullmatch(value):
                if non_interactive:
                    raise EnvCollectionError(
                        f"{name}: provided value does not match validation_regex"
                    )
                # Interactive: fall through to prompt loop, but seed with None
                # so we re-prompt rather than accept the bad value.
                value = None

        if value is None or value == "":
            if non_interactive:
                if not required:
                    # Optional with no value resolved: skip silently.
                    continue
                raise EnvCollectionError(
                    f"{name}: required and not provided in non-interactive mode"
                )
            value = _prompt_for(
                name=name,
                prompt_text=prompt_text,
                secret=secret,
                required=required,
                compiled_re=compiled_re,
                obtain_url=obtain_url,
                stdin=stdin,
                stdout=stdout,
            )
            if value is None:  # user skipped an optional
                continue

        resolved[name] = value

    return resolved


def _default_prompt_for(spec: Mapping) -> str:
    name = spec.get("name", "?")
    return f"Provide value for {name}: "


def _prompt_for(
    *,
    name: str,
    prompt_text: str,
    secret: bool,
    required: bool,
    compiled_re: re.Pattern | None,
    obtain_url: str | None,
    stdin,
    stdout,
) -> str | None:
    """Interactive prompt loop. Returns the value, or None for an optional skip."""
    suffix = ""
    if not required:
        suffix = " [optional, blank to skip]"
    if obtain_url:
        stdout.write(f"  obtain at: {obtain_url}\n")

    last_error: str | None = None
    for attempt in range(MAX_INTERACTIVE_RETRIES):
        if last_error:
            stdout.write(f"  ! {last_error}\n")
        full_prompt = f"{prompt_text}{suffix}: "

        if secret:
            try:
                value = getpass.getpass(full_prompt, stream=stdout)
            except (EOFError, KeyboardInterrupt):
                raise EnvCollectionError(f"{name}: prompt cancelled")
        else:
            stdout.write(full_prompt)
            stdout.flush()
            line = stdin.readline()
            if not line:
                raise EnvCollectionError(f"{name}: stdin closed")
            value = line.rstrip("\n").rstrip("\r")

        if value == "":
            if not required:
                return None
            last_error = "value is required"
            continue

        if compiled_re is not None and not compiled_re.fullmatch(value):
            last_error = f"value does not match expected pattern ({compiled_re.pattern})"
            continue

        return value

    raise EnvCollectionError(
        f"{name}: too many invalid attempts ({MAX_INTERACTIVE_RETRIES})"
    )
