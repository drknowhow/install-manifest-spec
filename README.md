# install-manifest spec

**v0.1 — JSON manifests that let autonomous agents install, verify, and revoke tools without a human in the loop.**

Every existing MCP tool directory is built for a human developer who browses, reads READMEs, clones repos, and manually configures credentials. This spec is the inversion: a structured contract that lets an *agent* (not a person) parse a manifest, prompt its human owner for exactly the env vars needed, run a smoke test against the tool, and confirm install — without a human in the install loop.

A manifest is a JSON document. An agent fetches it, validates it against the schema, surfaces scopes and cost to its human owner for consent, collects env values, installs the tool's artifacts, runs the declared smoke test, and persists the install record. Revocation runs in reverse via the manifest's `kill_switch`.

The spec is vendor-neutral. Manifests can be hosted at any URL — a public registry, a `.well-known` path, a raw GitHub file. Multiple registries can index the same manifests. The contract is the moat, not any single registry.

---

## Repo layout

```
schema/install-manifest-v0.1.json    # JSON Schema (Draft 2020-12)
design/v0.1-design-notes.md          # field-by-field rationale + open questions
examples/gmail.json                  # example manifest for a Gmail MCP tool
cli/                                 # reference Python CLI (v0.1.0: validate, show, collect-env)
  README.md                          #   surface + design + status table
  install_manifest/                  #   package
  tests/                             #   pytest
  pyproject.toml
LICENSE                              # MIT
```

---

## Quick start (for tool authors)

1. Read [`design/v0.1-design-notes.md`](design/v0.1-design-notes.md) — explains every field.
2. Copy [`examples/gmail.json`](examples/gmail.json) and adapt for your tool.
3. Validate against [`schema/install-manifest-v0.1.json`](schema/install-manifest-v0.1.json) using any JSON Schema validator (`ajv`, `jsonschema`, `check-jsonschema`, etc.).
4. Host it at a public URL. Submit to a manifest-aware registry, or share the URL directly with agents.

## Quick start (for agent authors)

1. Read [`design/v0.1-design-notes.md`](design/v0.1-design-notes.md) and [`cli/README.md`](cli/README.md).
2. Implement: fetch manifest → validate → consent → collect env → install → smoke → persist + record. Revoke via `kill_switch`.
3. Try the reference Python CLI:
   ```
   cd cli && pip install -e ".[test]"
   install-manifest validate    ../examples/gmail.json
   install-manifest show        ../examples/gmail.json
   install-manifest collect-env ../examples/gmail.json --yes --non-interactive --env GOOGLE_CLIENT_ID=...
   ```
   v0.1.0 ships read-only and prompt-only subcommands; `install`/`smoke`/`revoke` land in 0.2.0. Other implementations (Node, Go, Rust) are welcome.

---

## Spec at a glance

A manifest declares:

- **Identity** (`tool`) — id, version, name, summary, homepage.
- **Runtime** (`runtime`) — how to install (pip / npm / git / container / direct URL with sha256) and how to invoke (entrypoint command or HTTP endpoint).
- **Env** (`env`) — variables to collect from the human, each with prompt text, secret flag, optional regex validator and `obtain_url`.
- **Scopes** (`scopes`) — permission declarations (resource + actions + rationale) shown to the human as the consent screen.
- **Smoke** (`smoke`) — required verification step (shell / http / mcp-tool-call) with structured success criteria.
- **Kill switch** (`kill_switch`) — required revocation path (url / shell / manual).
- **Cost** (`cost`) — optional billing model in cents, with `external` escape hatch for tools that bill via their own credentials.
- **Support** (`support`) — optional issues_url, security_email, docs_url.

`smoke` and `kill_switch` are non-negotiable. An agent that cannot verify install correctness or revoke a tool cannot recover from a compromised credential.

---

## Versioning

`manifest_version` is pinned (`"0.1"`). Agents that support v0.1 should reject v0.2 manifests outright rather than silently dropping unknown fields. v0.2 will be a separate schema at a new URL.

## Status

v0.1 is intentionally minimal. Several known gaps are deferred to v0.2:

- Manifest signing / author identity verification
- Cross-env dependency declarations (e.g., "obtain X only after Y is set")
- Tool-to-tool dependencies
- Versioning / upgrade flows beyond install + revoke

See [`design/v0.1-design-notes.md`](design/v0.1-design-notes.md#open-design-questions-v01--v02-backlog) for the open design questions; PRs welcome.

## License

MIT — see [`LICENSE`](LICENSE).
