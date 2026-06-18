# Changelog

All notable changes to the **`install-manifest`** reference CLI are recorded
here. The format follows [Keep a Changelog](https://keepachangelog.com/), and
the package follows [Semantic Versioning](https://semver.org/).

Entries track [PyPI releases](https://pypi.org/project/install-manifest/) of
the CLI. The manifest **schema** is versioned independently — see `schema/`
and the design notes; the CLI bundles every supported schema version for
offline validation and dispatches on the manifest's declared
`manifest_version`.

## [0.6.0] — 2026-06-18

### Added
- **`install-manifest init`** — scaffold a new, schema-valid v0.4 manifest
  (an `mcp-stdio` + `pip` starter) pre-filled with `TODO:` placeholders, so
  authoring no longer starts from a blank file or the schema. Interactive
  prompts when run in a terminal; `--yes` takes defaults for scripts/CI.
  Flags: `--id`, `--name`, `--summary`, `--homepage`, `--package`,
  `--author`, `-o/--output` (`-` streams to stdout), `--force`. The
  generated manifest passes `validate` immediately; `lint` then flags what
  to harden next.
- `build_manifest()` exported from the package for programmatic scaffolding.

### Notes
- New exit code `8`: `init` refused to overwrite an existing output file
  (pass `--force`).

## [0.5.0] — 2026-05-28

### Added
- **`install-manifest lint`** — best-practice rules (LM001–LM010) layered on
  top of schema validation. `--strict` (exit `6`), `--ignore`, `--json`.
- **`install-manifest diff`** — classify changes between two same-version
  manifests as breaking / additive / cosmetic. `--upgrade-safe` (exit `7`),
  `--format`.
- v0.4 schema support: `runtime.install.method: "preinstalled"` (with a
  required `locator`) and `data_boundary.transmits[].to_kind:
  "agent-supplied"` plus optional `to_constraint`. All v0.3.1 manifests
  validate unmodified against v0.4.

## [0.4.1] — 2026-05-28

### Changed
- Description-only release. PyPI re-renders the project description only on a
  new version (versions can't be reused), so this bump carries a README
  refresh and an author email — no code changes.

## [0.4.0] — 2026-05-28

### Added
- First PyPI release of the reference CLI: `validate`, `show`, and
  `collect-env` (read-only / prompt-only). Bundles schemas v0.1, v0.2, v0.3,
  v0.3.1, and v0.4 for offline validation.

[0.6.0]: https://github.com/drknowhow/install-manifest-spec/releases/tag/v0.6.0
[0.5.0]: https://github.com/drknowhow/install-manifest-spec/releases/tag/v0.5.0
[0.4.1]: https://github.com/drknowhow/install-manifest-spec/releases/tag/v0.4.1
[0.4.0]: https://github.com/drknowhow/install-manifest-spec/releases/tag/v0.4.0
