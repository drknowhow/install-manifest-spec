# Reference CLI — `install-manifest`

**Status:** v0.5.0 (2026-05-28) — read-only and prompt-only subcommands implemented (`validate`, `show`, `collect-env`, `lint`, `diff`). The validator dispatches automatically on the manifest's declared `manifest_version` and supports `0.1`, `0.2`, `0.3`, `0.3.1`, and `0.4` (all schemas bundled with the wheel for offline validation). Side-effecting subcommands (`install`, `smoke`, `revoke`) remain pseudocode + architecture below; they will land in subsequent versions, behind their own subcommands and gated by explicit flags.

v0.5 adds two new pre-publish workflows on top of `validate`: `lint` runs best-practice rules (kebab-case IDs, SemVer versions, https-only URLs, secret-input constraints, missing `verify`/`kill_switch`) and `diff` classifies changes between two same-version manifests into breaking / additive / cosmetic so publishers can hold themselves to upgrade-safety contracts.

v0.4 adds two manifest surfaces the validator now accepts: `runtime.install.method: "preinstalled"` (with a required `locator` of kind `python-module` / `binary-on-path` / `mcp-server-id`) for tools pre-baked into an agent's runtime image, and `data_boundary.transmits[].to_kind: "agent-supplied"` plus optional `to_constraint` for outbound destinations supplied by the calling agent at runtime. All v0.3.1 manifests validate unmodified against v0.4 — drop-in upgrade.

This document is the design plan for the full CLI. The shipped slice is described in [§ Implementation status](#implementation-status). Other implementations are welcome and encouraged — the schema is the spec; this is just one client.

## Implementation status

| Subcommand    | Shipped in 0.5.0 | Notes                                                                       |
|---------------|:----------------:|-----------------------------------------------------------------------------|
| `validate`    |        ✓         | fetch + JSON Schema validation against v0.1 / v0.2 / v0.3 / v0.3.1 / v0.4, exit 0/2/3. |
| `show`        |        ✓         | fetch + validate + render consent screen. Read-only.                        |
| `collect-env` |        ✓         | fetch + validate + render consent + prompt for env values. **No install.**  |
| `lint`        |        ✓         | fetch + validate + run best-practice rules. `--strict`, `--ignore`, `--json`. |
| `diff`        |        ✓         | fetch + validate two manifests + classify changes. `--upgrade-safe`, `--format`. |
| `install`     |        —         | Acquires artifacts, runs smoke, persists install record. Deferred.          |
| `verify`      |        —         | Re-runs smoke for an existing install. Deferred.                            |
| `revoke`      |        —         | Invokes `kill_switch`. Deferred.                                            |
| `list/status` |        —         | Inspection over the state directory. Deferred.                              |

### Install + run

```
pip install install-manifest
install-manifest validate    https://toolspace.yepgent.com/examples/gmail.v0.3.json
install-manifest show        https://toolspace.yepgent.com/examples/gmail.v0.3.json
install-manifest collect-env https://toolspace.yepgent.com/examples/gmail.v0.3.json --yes --non-interactive --env GOOGLE_REFRESH_TOKEN=test
install-manifest lint        https://toolspace.yepgent.com/examples/gmail.v0.3.json --strict
install-manifest diff        ./old.json ./new.json --upgrade-safe
```

## Lint

`install-manifest lint <url-or-path>` runs schema validation first, then a catalogue of best-practice rules. Severity is `warning` in v1; default exit is `0`, `--strict` makes any remaining finding return exit `6`. Findings are emitted on stderr in the form `warning LMxxx /json/pointer: message`; `--json` emits an array on stdout.

| Code  | Rule                                                                                                |
|-------|-----------------------------------------------------------------------------------------------------|
| LM001 | Missing `verify` block when `manifest_version >= 0.3`.                                              |
| LM002 | Missing `kill_switch` when `manifest_version >= 0.3`.                                               |
| LM003 | `data_boundary.transmits[]` entry with `to_kind=external` and no `to_constraint`.                   |
| LM004 | `data_boundary.transmits[]` entries with no `to_kind` (loose v0.3 — suggest upgrade to v0.4).        |
| LM005 | `actions[]` entry with missing or empty `docs.goal`.                                                |
| LM006 | `verify` block present but `verify.sla.p95_latency_ms` missing.                                     |
| LM007 | `tool.id` is not kebab-case (`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`).                                      |
| LM008 | `tool.version` is not SemVer 2.0.0.                                                                 |
| LM009 | Any `http://` URL anywhere in the manifest (recursive scan; suggest `https://`).                    |
| LM010 | `env[]` entry with `secret: true` and neither `regex`/`validation_regex` nor `min_length`.          |

Suppress individual codes with `--ignore LM001,LM004`.

## Diff

`install-manifest diff <a> <b>` validates both manifests, requires they declare the **same `manifest_version`** (v1 hard constraint — raises exit `3` otherwise), and classifies every change into one of three buckets:

- **breaking** — a consumer of `a` cannot transparently upgrade to `b`. Includes: removed actions / scopes / required env vars / `kill_switch`; stricter action input schemas (type changes, new `required`, new `enum`, `additionalProperties` true→false); new `to_kind=external` transmit destinations; same-version-body-changed (`version-mutation`).
- **additive** — `b` widens capability or guard-rails. New actions, new scope verbs, new optional env vars, newly-added `verify` or `kill_switch` blocks.
- **cosmetic** — text-only or version-only changes. `tool.docs.*`, `actions[].docs.*`, `tool.summary` edits, `tool.version` bumps where no other change occurred.

`--upgrade-safe` makes the command exit `7` if any breaking changes are detected — drop into a CI pipeline to fail publishers who break consumers without bumping a major version. `--format=json` emits a structured `{breaking: [...], additive: [...], cosmetic: [...]}` document for tooling.

Cross-version diffing is out of scope for v1. Normalize manually or upgrade the older publisher first.

Local development: `cd cli && pip install -e ".[test]" && pytest`.

### Why this slice first

Side-effecting subcommands (`install`, `smoke`, `revoke`) each have their own
risk surface — running shell commands as the user, writing credentials to
disk, calling DELETE endpoints with the user's tokens. Shipping them
behind the read-only slice gives the spec a chance to harden against
manifest authoring mistakes (caught in `validate`) and consent UX issues
(caught in `show`/`collect-env`) before any real bytes hit the system.

---

---

## 1. CLI Surface

```
install-manifest install <manifest_url> [--yes] [--non-interactive] [--state-dir DIR]
install-manifest verify <install_id>
install-manifest list [--state-dir DIR]
install-manifest revoke <install_id> [--yes]
install-manifest status <install_id>
```

- `install` — the primary command. Walks discovery → confirm → env collection → install → smoke → persist.
- `verify` — re-runs the smoke test for an existing install.
- `revoke` — invokes the manifest's `kill_switch` and removes local state.
- `list` / `status` — inspection; read-only.
- `--non-interactive` — every value must come from env or `--env KEY=VAL` flags; fails fast on any prompt that would block.
- `--yes` — skips the consent confirmation; does not skip env collection.
- `--state-dir` — defaults to `~/.local/share/install-manifest/` (XDG-compliant; equivalents on macOS/Windows).

The same binary works for both human-in-loop installs (interactive prompts) and agent-driven installs (`--non-interactive --env KEY=VAL`).

---

## 2. Module Layout

```
install_manifest/
  __init__.py
  __main__.py          # argparse dispatch
  fetch.py             # fetch_manifest(url) -> dict + raw_bytes
  validate.py          # validate(manifest) -> ValidationResult against schema
  consent.py           # render_consent(manifest) + collect_consent()
  collect_env.py       # collect_env(env_specs, ...) -> dict[str, str]
  install/
    __init__.py        # dispatch on runtime.install.method
    pip.py
    npm.py
    git.py
    container.py
    url.py             # download + sha256 verify
  runtime/
    __init__.py
    mcp_stdio.py       # spawn server, send tool-call, await response
    http.py
    shell.py
  smoke.py             # run_smoke(manifest, install_record)
  state.py             # InstallRecord persistence
  kill.py              # invoke kill_switch
  errors.py            # typed exceptions
```

Roughly 1500–2500 LOC for a clean v1. Pure stdlib for fetch (`urllib`); JSON Schema validation via `jsonschema` (only third-party dependency). Optional `keyring` for secret storage.

---

## 3. The `install` flow

```python
def cmd_install(manifest_url, *, yes, non_interactive, state_dir, env_overrides) -> int:
    # 1. Fetch
    try:
        manifest_dict, raw_bytes = fetch_manifest(manifest_url, timeout=30)
    except FetchError as e:
        print(f"error: could not fetch manifest at {manifest_url}: {e}", file=sys.stderr)
        return 2

    # 2. Validate against bundled schema
    validation = validate(manifest_dict)
    if not validation.ok:
        print(f"error: manifest invalid: {validation.summary}", file=sys.stderr)
        for path, msg in validation.errors:
            print(f"  {path}: {msg}", file=sys.stderr)
        return 3

    manifest = manifest_dict

    # 3. Consent
    print(render_consent(manifest))  # tool identity, scopes, cost, kill_switch summary
    if not yes:
        if non_interactive:
            print("error: --non-interactive requires --yes", file=sys.stderr)
            return 4
        if not collect_consent():
            print("install cancelled.")
            return 0

    # 4. Collect env
    try:
        env_values = collect_env(
            manifest.get("env", []),
            non_interactive=non_interactive,
            env_overrides=env_overrides,
        )
    except EnvCollectionError as e:
        print(f"error: env collection failed: {e}", file=sys.stderr)
        return 5

    # 5. Install (acquire artifacts)
    install_id = generate_install_id(manifest["tool"]["id"], manifest["tool"]["version"], raw_bytes)
    install_dir = state_dir / "installs" / install_id
    install_dir.mkdir(parents=True, exist_ok=True)

    try:
        install_result = do_install(manifest["runtime"]["install"], install_dir=install_dir)
    except InstallError as e:
        print(f"error: install failed: {e}", file=sys.stderr)
        cleanup(install_dir)  # best-effort
        return 6

    # 6. Persist record (BEFORE smoke, so failures are recoverable)
    record = InstallRecord(
        id=install_id,
        manifest_url=manifest_url,
        manifest_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        manifest=manifest,
        env_values_path=write_env_file(install_dir, env_values),
        install_dir=install_dir,
        installed_at=now(),
        smoke_status="pending",
    )
    save_record(state_dir, record)

    # 7. Smoke
    try:
        smoke_result = run_smoke(manifest, record, timeout_default=30)
    except SmokeError as e:
        record.smoke_status = "error"
        record.smoke_error = str(e)
        save_record(state_dir, record)
        print(f"error: smoke test errored: {e}", file=sys.stderr)
        offer_revoke(record)
        return 7

    if not smoke_result.ok:
        record.smoke_status = "failed"
        record.smoke_failure_reason = smoke_result.failure_reason
        save_record(state_dir, record)
        print(f"smoke failed: {smoke_result.failure_reason}", file=sys.stderr)
        offer_revoke(record)
        return 8

    record.smoke_status = "ok"
    save_record(state_dir, record)

    # 8. Done
    print(f"installed {manifest['tool']['name']} v{manifest['tool']['version']} ({install_id})")
    print(f"  smoke: ok")
    print(f"  revoke with: install-manifest revoke {install_id}")
    return 0
```

---

## 4. Failure-mode handling

| Step | Failure | Action |
|---|---|---|
| Fetch | network timeout, 404, TLS error | exit 2; nothing persisted |
| Fetch | content-type not application/json | exit 2; warn the URL may not be a manifest |
| Validate | schema violation | exit 3; print every JSON Pointer + error message |
| Validate | manifest_version unsupported | exit 3; user's CLI may be wrong version |
| Consent | --non-interactive without --yes | exit 4 |
| Consent | user declines | clean exit 0 |
| Env | regex mismatch (interactive) | reprompt up to 3 times; on 4th, exit 5 |
| Env | regex mismatch (non-interactive) | exit 5 immediately |
| Env | required var missing in non-interactive | exit 5 |
| Install | pip install error, git clone fail, sha256 mismatch | exit 6; cleanup install_dir best-effort |
| Smoke | tool process won't start | record saved with smoke_status=error; offer revoke |
| Smoke | http timeout / non-2xx | record saved with smoke_status=failed; offer revoke |
| Smoke | success criteria not met | record saved with smoke_status=failed + which assertion failed; offer revoke |
| Persist | filesystem error | exit 9; warn user that install may have happened but is untracked |

`offer_revoke(record)` prompts to invoke `kill_switch` immediately. Default is "revoke on failed smoke" — leaving credentials live for a tool we couldn't verify is the wrong default.

---

## 5. Env collection details

Source resolution order: `--env` override → existing env var → default → prompt.

Secrets get written to the host keychain (macOS Keychain / Linux Secret Service / Windows Credential Manager via `keyring`, optional dependency). If keyring unavailable, fall back to `~/.local/share/install-manifest/installs/<id>/.env` mode 0600 with a loud warning. Non-secret env vars always go to the `.env` file.

---

## 6. Smoke runner

For each smoke kind:

- `shell` — `subprocess_run(command, env=load_env(record), timeout=...)`, evaluate `success` against exit code + stdout regex.
- `http` — request with `${VAR_NAME}` expansion in URL/headers/body, evaluate against status + body regex + json_pointer.
- `mcp-tool-call` — spawn the MCP server using `runtime.entrypoint`, send a tool-call request via stdio, evaluate against the result.

Each `check_*_success` evaluates present fields in `success` as a logical AND. Returns `SmokeResult(ok=True)` or `SmokeResult(ok=False, failure_reason=...)` with the specific assertion that failed.

`expand_env_refs` does `${VAR_NAME}` substitution sourced from the install record's env. This is the only way an HTTP smoke can reference the user's API key without it being baked into the manifest.

---

## 7. State directory layout

```
~/.local/share/install-manifest/
  schema/
    install-manifest-v0.1.json     # bundled copy, read-only
    install-manifest-v0.2.json     # bundled copy, read-only
    install-manifest-v0.3.json     # bundled copy, read-only
    install-manifest-v0.3.1.json   # bundled copy, read-only
    install-manifest-v0.4.json     # bundled copy, read-only
  installs/
    <install_id>/
      manifest.json                 # snapshot of fetched manifest
      manifest.sha256               # checksum of fetched bytes
      record.json                   # InstallRecord
      .env                          # non-secret env values, mode 0600
      artifacts/                    # whatever do_install dropped here
  index.json                        # map install_id -> {tool_id, version, installed_at, smoke_status}
```

`install_id` is `<tool.id>-<tool.version>-<short-sha-of-manifest-bytes>`. Reinstalling the same manifest at the same version is a no-op (or idempotent re-verify). Reinstalling a new version of the same tool gets a new directory; the old install isn't touched until `revoke`.

---

## 8. Deferred to a future CLI release

- **Side-effecting subcommands.** `install`, `verify`, `revoke`, `list`, `status` are designed (§§ 3-7) but not yet shipped. The current wheel is read-only / prompt-only.
- **Manifest signing.** Fetch step does not currently verify a signature. The seller-trust model today is "the user trusted the URL they typed in." Sigstore-style signing is planned.
- **Manifest registry resolution.** Today the CLI takes a URL. A future release will accept a registry-relative ID like `gmail-yep@1.0.0`.
- **Upgrade path.** Once `install` + `revoke` ship, upgrade will initially be "revoke old, install new"; a later release will add `upgrade <install_id>` that diffs manifests.
- **Concurrent install protection.** Single-invocation-per-state-dir assumption today; lock file planned alongside `install`.
- **Health scheduler.** Smoke runs once at install time (when `install` ships); optional scheduled re-verification is planned.

---

## 9. Open implementation questions

1. **Bundled vs network-fetch schema.** Bundle for offline validation, or always fetch from a canonical URL? Current lean: bundle. Network is already used for the manifest itself; bundling avoids a second failure mode.
2. **Keychain dependency.** Bail if `keyring` unavailable, or fall back to plaintext `.env` with warning? Current lean: warn-and-fallback. Many environments don't have a keychain (Docker, CI, headless servers).
3. **Smoke-on-install vs smoke-deferred.** Offer `--skip-smoke`? Current lean: no, in v0.1. The whole point of smoke is to gate "install succeeded."
4. **Telemetry.** Report install/uninstall events to a registry API for inventory tracking? Current lean: opt-in only via `--report-to <url>`, off by default.
5. **Manifest URL pinning.** When saving the install record, record only the URL or also the contents hash? Current lean: both. The hash is the truth-anchor for "was the manifest the same when I installed as it is now?"

PRs welcome on any of these.
