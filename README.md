# install-manifest spec

**v0.3.1 — JSON manifests that let autonomous agents install, verify, drive, and revoke tools without a human in the loop.**

Every existing MCP tool directory is built for a human developer who browses, reads READMEs, clones repos, and manually configures credentials. This spec is the inversion: a structured contract that lets an *agent* (not a person) parse a manifest, prompt its human owner for exactly the env vars needed, install the tool, run a smoke test, and confirm — without a human in the install loop.

A manifest is a JSON document. An agent fetches it, validates it against the schema, surfaces scopes and cost to its human owner for consent, collects env values, installs the tool's artifacts, runs the declared smoke test, and persists the install record. Revocation runs in reverse via the manifest's `kill_switch`.

The spec is vendor-neutral. Manifests can be hosted at any URL — a public registry, a `.well-known` path, a raw GitHub file. Multiple registries can index the same manifests. The contract is the moat, not any single registry.

---

## Versions

| Version | Status | Schema | Design notes | What's new |
|---|---|---|---|---|
| **0.3.1** | current | [`schema/install-manifest-v0.3.1.json`](schema/install-manifest-v0.3.1.json) | [`design/v0.3.1-design-notes.md`](design/v0.3.1-design-notes.md) | additive fixes from four community consumer manifests: `kill_switch.kind: "none"` (stateless tools), inline `kill_switch.manual.instructions` (no wrapper file required for short checklist-form revocation), optional `tool.namespace` + canonical_id derivation, `runtime.install.layout` enum (package \| skill-bundle \| raw), `smoke.success.json_pointer_in` (set-membership) and `smoke.success.json_pointer_present` (non-null non-empty). All v0.3 manifests validate against v0.3.1 unmodified — drop-in upgrade |
| **0.3** | superseded by 0.3.1 | [`schema/install-manifest-v0.3.json`](schema/install-manifest-v0.3.json) | [`design/v0.3-design-notes.md`](design/v0.3-design-notes.md) | adds top-level `verify` (suite + sla + schedule), top-level `data_boundary` (reads / transmits / persists / retention, required when `scopes[]` touches private user data), optional `actions[].docs` (concise per-field-capped agent docs, per EASYTOOL), and reserved `actions[].runtime_telemetry` opaque object for v0.5 |
| **0.2** | frozen | [`schema/install-manifest-v0.2.json`](schema/install-manifest-v0.2.json) | [`design/v0.2-design-notes.md`](design/v0.2-design-notes.md) | adds top-level `actions[]` catalog so non-MCP tools (Python modules, shell binaries, HTTP endpoints, containers) can be driven structurally; new `smoke.kind = "action-call"`; raised `env[].prompt` cap to 800 |
| **0.1** | frozen | [`schema/install-manifest-v0.1.json`](schema/install-manifest-v0.1.json) | [`design/v0.1-design-notes.md`](design/v0.1-design-notes.md) | initial release — MCP-server-shaped contract |

v0.3.1 is **strictly additive** to v0.3: every v0.3 manifest validates against the v0.3.1 schema unmodified, and the only narrowing is a validator constraint specific to the new `kill_switch.kind: "none"` variant (it requires env empty + persists empty — both honesty checks for what `"none"` actually claims). v0.3 manifests stay valid against the v0.3 schema URL; v0.3.1 lives at its own URL. Agents that only support v0.3 should treat v0.3.1 manifests as readable when the new fields are absent, but should reject them outright if any new field is present (forward compatibility via ignore-unknown is dangerous for security-relevant fields). The earlier v0.3 narrowing (`data_boundary` required when `scopes[]` touches the private-data prefix list — gmail / calendar / drive / contacts / messages / sms / files / photos / location / health / finance / payments / stripe / plaid) carries forward unchanged.

---

## Repo layout

```
schema/
  install-manifest-v0.1.json         # frozen
  install-manifest-v0.2.json         # frozen
  install-manifest-v0.3.json         # superseded by 0.3.1
  install-manifest-v0.3.1.json       # current
design/
  v0.1-design-notes.md               # field-by-field rationale (frozen)
  v0.2-design-notes.md               # field-by-field rationale (frozen)
  v0.3-design-notes.md               # field-by-field rationale (superseded by 0.3.1)
  v0.3.1-design-notes.md             # field-by-field rationale (current)
examples/
  gmail.json                         # v0.1 example (MCP-stdio Gmail tool)
  gmail.v0.2.json                    # v0.2 example (Python-module Gmail tool with actions[])
  gmail.v0.3.json                    # v0.3 example (adds verify + data_boundary + actions[].docs) — validates unmodified against v0.3.1
  muninn-flowing.v0.3.json           # community attestation (Muninn) — validates unmodified against v0.3.1
  muninn-verify-patch.v0.3.json      # community attestation (Muninn) — validates unmodified against v0.3.1
  muninn-perch-publish.v0.3.json     # community attestation (Muninn) — validates unmodified against v0.3.1
cli/                                 # reference Python CLI
  install_manifest/                  #   package — version-dispatch validator
  tests/                             #   pytest (covers all three versions)
  scripts/sync_schema.py             #   mirrors schema/ into install_manifest/_data/
  pyproject.toml
LICENSE                              # MIT
```

---

## Quick start (for tool authors)

1. Read [`design/v0.3.1-design-notes.md`](design/v0.3.1-design-notes.md) — covers the v0.3.1 additive deltas and links back to v0.3 / v0.2 / v0.1 for unchanged surfaces.
2. Copy [`examples/gmail.v0.3.json`](examples/gmail.v0.3.json) and adapt for your tool. Bump `manifest_version` to `"0.3.1"` if you adopt any new field (`tool.namespace`, `runtime.install.layout`, `kill_switch.kind: "none"`, inline `kill_switch.manual.instructions`, `smoke.success.json_pointer_in`, `smoke.success.json_pointer_present`); otherwise keep `"0.3"`.
3. Validate against [`schema/install-manifest-v0.3.1.json`](schema/install-manifest-v0.3.1.json) using any JSON Schema validator (`ajv`, `jsonschema`, `check-jsonschema`, etc.).
4. Host it at a public URL. Submit to a manifest-aware registry, or share the URL directly with agents.

If your tool is an MCP-stdio server and the protocol's own discovery is enough, v0.1 is still a perfectly valid choice; pin `manifest_version: "0.1"` and use the v0.1 schema.

## Quick start (for agent authors)

1. Read [`design/v0.3.1-design-notes.md`](design/v0.3.1-design-notes.md) and [`cli/README.md`](cli/README.md).
2. Implement: fetch manifest → validate → consent → collect env → install → smoke → persist + record. Revoke via `kill_switch`. For v0.2 manifests, drive operations via the `actions[]` catalog.
3. Try the reference Python CLI:
   ```
   cd cli && pip install -e ".[test]"
   install-manifest validate    ../examples/gmail.v0.3.json
   install-manifest show        ../examples/gmail.v0.3.json
   install-manifest collect-env ../examples/gmail.v0.3.json --yes --non-interactive --env GOOGLE_CLIENT_ID=...
   ```
   The CLI dispatches automatically on `manifest_version`. Other implementations (Node, Go, Rust) are welcome.

---

## Spec at a glance

A v0.3.1 manifest declares everything v0.3 declared, plus the additive deltas listed in the version table. The surfaces below are unchanged from v0.3 unless flagged:

- **Identity** (`tool`) — id, version, name, summary, homepage.
- **Runtime** (`runtime`) — how to install (pip / npm / git / container / direct URL with sha256) and how to invoke (entrypoint command or HTTP endpoint).
- **Env** (`env`) — variables to collect from the human, each with prompt text, secret flag, optional regex validator and `obtain_url`.
- **Scopes** (`scopes`) — permission declarations (resource + actions + rationale) shown to the human as the consent screen.
- **Actions** (`actions`, **new in v0.2**) — catalog of operations the agent can call. Each entry declares its invocation method (subcommand / stdin-json / http / mcp-tool), input schema, output schema, side-effect severity (none / read / write / destructive), and idempotence. Required for non-MCP-stdio runtimes.
- **Verify** (`verify`, **new in v0.3**) — optional ongoing-verification contract: a JSONL eval suite, an SLA (p50/p95/error rate), and a re-run schedule. Distinct from `smoke` (one-shot install gate).
- **Data boundary** (`data_boundary`, **new in v0.3**, required when `scopes[]` touches private user data) — declares what private resources the tool reads, what it transmits to third parties (with controlled `third_party_retention` enum), what it persists, and retention windows.
- **Smoke** (`smoke`) — required verification step (shell / http / mcp-tool-call / action-call) with structured success criteria. **v0.3.1** adds `json_pointer_in` (set-membership) and `json_pointer_present` (non-null + non-empty) success predicates alongside the existing `json_pointer_equals` / `json_pointer_exists`.
- **Kill switch** (`kill_switch`) — required revocation path. v0.3 shapes: `url` / `shell` / `manual`. **v0.3.1** adds `none` (stateless tools — validator enforces empty `env` and empty `data_boundary.persists`) and inline `kill_switch.manual.instructions` (≤2000 chars, mutually exclusive with `instructions_url`).
- **Cost** (`cost`) — optional billing model in cents, with `external` escape hatch for tools that bill via their own credentials.
- **Support** (`support`) — optional issues_url, security_email, docs_url.

`smoke` and `kill_switch` are non-negotiable. An agent that cannot verify install correctness or revoke a tool cannot recover from a compromised credential.

---

## Status

v0.3.1 is strictly additive on top of v0.3, surfacing six community-driven gaps and two design notes (frameworks-shouldn't-publish-manifests, smoke-as-permission-check) without breaking any v0.3 manifest. The v0.3 narrowing carries forward: `data_boundary` is required when `scopes[]` touches private user data. Several known gaps remain deferred to v0.4 / v0.5:

- Manifest signing / author identity verification
- Cross-env dependency declarations (e.g., "obtain X only after Y is set")
- Tool-to-tool dependencies (unblocked by v0.3.1's `tool.namespace` + `tool.id` two-field identity — open as [`issue #?`])
- Variable-target outbound transmits (open as [`issue #4`](https://github.com/drknowhow/install-manifest-spec/issues/4))
- `runtime.install` method `"preinstalled"` for tools baked into the agent's runtime image (open as [`issue #5`](https://github.com/drknowhow/install-manifest-spec/issues/5))
- Versioning / upgrade flows beyond install + revoke
- Secrets-in-argv linter (documented since v0.2; still a v0.4 candidate)
- A standardized eval-suite runner (v0.3 declares `verify.suite.ref` and `format`; v0.4 should ship the runner)
- `actions[].runtime_telemetry` shape (reserved opaque in v0.3; v0.5 fills it in for adaptive tool routing)
- `runtime.install.layout` Shape B — structured layout-with-validation beyond v0.3.1's informational hint

See [`design/v0.3.1-design-notes.md`](design/v0.3.1-design-notes.md) for v0.3.1 rationale, and [`design/v0.3-design-notes.md`](design/v0.3-design-notes.md#open-design-questions-v03--v04-backlog) for the older open questions; PRs welcome.

## License

MIT — see [`LICENSE`](LICENSE).
