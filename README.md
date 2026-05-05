# install-manifest spec

**v0.2 — JSON manifests that let autonomous agents install, verify, drive, and revoke tools without a human in the loop.**

Every existing MCP tool directory is built for a human developer who browses, reads READMEs, clones repos, and manually configures credentials. This spec is the inversion: a structured contract that lets an *agent* (not a person) parse a manifest, prompt its human owner for exactly the env vars needed, install the tool, run a smoke test, and confirm — without a human in the install loop.

A manifest is a JSON document. An agent fetches it, validates it against the schema, surfaces scopes and cost to its human owner for consent, collects env values, installs the tool's artifacts, runs the declared smoke test, and persists the install record. Revocation runs in reverse via the manifest's `kill_switch`.

The spec is vendor-neutral. Manifests can be hosted at any URL — a public registry, a `.well-known` path, a raw GitHub file. Multiple registries can index the same manifests. The contract is the moat, not any single registry.

---

## Versions

| Version | Status | Schema | Design notes | What's new |
|---|---|---|---|---|
| **0.2** | current | [`schema/install-manifest-v0.2.json`](schema/install-manifest-v0.2.json) | [`design/v0.2-design-notes.md`](design/v0.2-design-notes.md) | adds top-level `actions[]` catalog so non-MCP tools (Python modules, shell binaries, HTTP endpoints, containers) can be driven structurally; new `smoke.kind = "action-call"`; raised `env[].prompt` cap to 800 |
| **0.1** | frozen | [`schema/install-manifest-v0.1.json`](schema/install-manifest-v0.1.json) | [`design/v0.1-design-notes.md`](design/v0.1-design-notes.md) | initial release — MCP-server-shaped contract |

v0.2 is **additive** to v0.1. v0.1 manifests stay valid against the v0.1 schema URL; v0.2 lives at its own URL. Agents that only support v0.1 must reject v0.2 manifests outright (forward compatibility via ignore-unknown is a footgun for security-relevant fields).

---

## Repo layout

```
schema/
  install-manifest-v0.1.json         # frozen
  install-manifest-v0.2.json         # current
design/
  v0.1-design-notes.md               # field-by-field rationale (frozen)
  v0.2-design-notes.md               # field-by-field rationale (current)
examples/
  gmail.json                         # v0.1 example (MCP-stdio Gmail tool)
  gmail.v0.2.json                    # v0.2 example (Python-module Gmail tool with actions[])
cli/                                 # reference Python CLI
  install_manifest/                  #   package — version-dispatch validator
  tests/                             #   pytest (covers both versions)
  scripts/sync_schema.py             #   mirrors schema/ into install_manifest/_data/
  pyproject.toml
LICENSE                              # MIT
```

---

## Quick start (for tool authors)

1. Read [`design/v0.2-design-notes.md`](design/v0.2-design-notes.md) — explains every v0.2 field.
2. Copy [`examples/gmail.v0.2.json`](examples/gmail.v0.2.json) and adapt for your tool.
3. Validate against [`schema/install-manifest-v0.2.json`](schema/install-manifest-v0.2.json) using any JSON Schema validator (`ajv`, `jsonschema`, `check-jsonschema`, etc.).
4. Host it at a public URL. Submit to a manifest-aware registry, or share the URL directly with agents.

If your tool is an MCP-stdio server and the protocol's own discovery is enough, v0.1 is still a perfectly valid choice; pin `manifest_version: "0.1"` and use the v0.1 schema.

## Quick start (for agent authors)

1. Read [`design/v0.2-design-notes.md`](design/v0.2-design-notes.md) and [`cli/README.md`](cli/README.md).
2. Implement: fetch manifest → validate → consent → collect env → install → smoke → persist + record. Revoke via `kill_switch`. For v0.2 manifests, drive operations via the `actions[]` catalog.
3. Try the reference Python CLI:
   ```
   cd cli && pip install -e ".[test]"
   install-manifest validate    ../examples/gmail.v0.2.json
   install-manifest show        ../examples/gmail.v0.2.json
   install-manifest collect-env ../examples/gmail.v0.2.json --yes --non-interactive --env GOOGLE_CLIENT_ID=...
   ```
   The CLI dispatches automatically on `manifest_version`. Other implementations (Node, Go, Rust) are welcome.

---

## Spec at a glance

A v0.2 manifest declares:

- **Identity** (`tool`) — id, version, name, summary, homepage.
- **Runtime** (`runtime`) — how to install (pip / npm / git / container / direct URL with sha256) and how to invoke (entrypoint command or HTTP endpoint).
- **Env** (`env`) — variables to collect from the human, each with prompt text, secret flag, optional regex validator and `obtain_url`.
- **Scopes** (`scopes`) — permission declarations (resource + actions + rationale) shown to the human as the consent screen.
- **Actions** (`actions`, **new in v0.2**) — catalog of operations the agent can call. Each entry declares its invocation method (subcommand / stdin-json / http / mcp-tool), input schema, output schema, side-effect severity (none / read / write / destructive), and idempotence. Required for non-MCP-stdio runtimes.
- **Smoke** (`smoke`) — required verification step (shell / http / mcp-tool-call / action-call) with structured success criteria.
- **Kill switch** (`kill_switch`) — required revocation path (url / shell / manual).
- **Cost** (`cost`) — optional billing model in cents, with `external` escape hatch for tools that bill via their own credentials.
- **Support** (`support`) — optional issues_url, security_email, docs_url.

`smoke` and `kill_switch` are non-negotiable. An agent that cannot verify install correctness or revoke a tool cannot recover from a compromised credential.

---

## Status

v0.2 is intentionally additive. Several known gaps remain deferred to v0.3:

- Manifest signing / author identity verification
- Cross-env dependency declarations (e.g., "obtain X only after Y is set")
- Tool-to-tool dependencies
- Versioning / upgrade flows beyond install + revoke
- Secrets-in-argv linter (v0.2 documents the rule; v0.3 should enforce it)

See [`design/v0.2-design-notes.md`](design/v0.2-design-notes.md#open-design-questions-v02--v03-backlog) for the open questions; PRs welcome.

## License

MIT — see [`LICENSE`](LICENSE).
