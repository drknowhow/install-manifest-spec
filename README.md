# install-manifest spec

**v0.4 — JSON manifests that let autonomous agents install, verify, drive, and revoke tools without a human in the loop.**

Every existing MCP tool directory is built for a human developer who browses, reads READMEs, clones repos, and manually configures credentials. This spec is the inversion: a structured contract that lets an *agent* (not a person) parse a manifest, prompt its human owner for exactly the env vars needed, install the tool, run a smoke test, and confirm — without a human in the install loop.

A manifest is a JSON document. An agent fetches it, validates it against the schema, surfaces scopes and cost to its human owner for consent, collects env values, installs the tool's artifacts, runs the declared smoke test, and persists the install record. Revocation runs in reverse via the manifest's `kill_switch`.

The spec is vendor-neutral. Manifests can be hosted at any URL — a public registry, a `.well-known` path, a raw GitHub file. Multiple registries can index the same manifests. The contract is the moat, not any single registry.

---

## Versions

| Version | Status | Schema | Design notes | What's new |
|---|---|---|---|---|
| **0.4** | current | [`schema/install-manifest-v0.4.json`](schema/install-manifest-v0.4.json) | [`design/v0.4-design-notes.md`](design/v0.4-design-notes.md) | closes two structural gaps surfaced by Muninn's consumer tests: `runtime.install.method: "preinstalled"` with required `locator` (kinds: python-module \| binary-on-path \| mcp-server-id) for tools pre-baked into the agent's runtime image (issue [#5](https://github.com/drknowhow/install-manifest-spec/issues/5)); `data_boundary.transmits[].to_kind: "agent-supplied"` plus optional `to_constraint` prose for outbound destinations supplied by the calling agent at runtime (issue [#4](https://github.com/drknowhow/install-manifest-spec/issues/4)). All v0.3.1 manifests validate against v0.4 unmodified — drop-in upgrade |
| **0.3.1** | superseded by 0.4 | [`schema/install-manifest-v0.3.1.json`](schema/install-manifest-v0.3.1.json) | [`design/v0.3.1-design-notes.md`](design/v0.3.1-design-notes.md) | additive fixes from four community consumer manifests: `kill_switch.kind: "none"` (stateless tools), inline `kill_switch.manual.instructions` (no wrapper file required for short checklist-form revocation), optional `tool.namespace` + canonical_id derivation, `runtime.install.layout` enum (package \| skill-bundle \| raw), `smoke.success.json_pointer_in` (set-membership) and `smoke.success.json_pointer_present` (non-null non-empty) |
| **0.3** | superseded by 0.3.1 | [`schema/install-manifest-v0.3.json`](schema/install-manifest-v0.3.json) | [`design/v0.3-design-notes.md`](design/v0.3-design-notes.md) | adds top-level `verify` (suite + sla + schedule), top-level `data_boundary` (reads / transmits / persists / retention, required when `scopes[]` touches private user data), optional `actions[].docs` (concise per-field-capped agent docs, per EASYTOOL), and reserved `actions[].runtime_telemetry` opaque object for v0.5 |
| **0.2** | frozen | [`schema/install-manifest-v0.2.json`](schema/install-manifest-v0.2.json) | [`design/v0.2-design-notes.md`](design/v0.2-design-notes.md) | adds top-level `actions[]` catalog so non-MCP tools (Python modules, shell binaries, HTTP endpoints, containers) can be driven structurally; new `smoke.kind = "action-call"`; raised `env[].prompt` cap to 800 |
| **0.1** | frozen | [`schema/install-manifest-v0.1.json`](schema/install-manifest-v0.1.json) | [`design/v0.1-design-notes.md`](design/v0.1-design-notes.md) | initial release — MCP-server-shaped contract |

v0.4 is **strictly additive** to v0.3.1 (and therefore to v0.3): every v0.3.1 manifest validates against the v0.4 schema unmodified. The only new structural rule is at the `data_boundary.transmits[]` item level — `to` and `to_kind` are now mutually exclusive (one is required, both is rejected); v0.3.1 manifests that omitted `to_kind` entirely continue to satisfy the same shape. v0.3.1 manifests stay valid against the v0.3.1 schema URL; v0.4 lives at its own URL. Agents that only support v0.3.1 should treat v0.4 manifests as readable when the new fields are absent, but should reject them outright if any new field is present (forward compatibility via ignore-unknown is dangerous for security-relevant fields like `to_kind`). The earlier narrowings (`data_boundary` required when `scopes[]` touches the private-data prefix list; `kill_switch.kind: "none"` requires env-empty + persists-empty) carry forward unchanged.

---

## Federation discovery (well-known index)

The install-manifest spec is registry-agnostic by design: a manifest lives at any URL, and any registry can index it. Through v0.4, the question *"how does a registry learn about a publisher's manifests in the first place?"* was answered by hand — registry maintainers manually mirrored URLs into their indexes when new manifests shipped.

The **well-known index** is a sibling spec that closes that gap. A publisher hosts one JSON document at a kind-specific discovery location listing the install-manifest URLs they claim authorship of. A registry crawls each allowlisted publisher's index on its own schedule and resolves the listed URLs to canonical manifests.

| Artifact | Path |
|---|---|
| Schema | [`schema/well-known-index-v1.json`](schema/well-known-index-v1.json) |
| Design notes | [`design/well-known-index-v1-design-notes.md`](design/well-known-index-v1-design-notes.md) |
| Example | [`examples/install-manifests-index.muninn.json`](examples/install-manifests-index.muninn.json) |

The index supports three publisher identity kinds — `github` (owner/repo), `https` (domain with DNS or `.well-known/` challenge), and `atproto` (DID + signed PDS record) — so independent tool authors don't need to own a domain to be federation-discoverable. The trust gate (which publishers a given registry crawls) lives in each registry's own allowlist; this spec defines the publisher-hosted document, not the allowlist format.

The well-known index is **versioned independently** of the install-manifest schema: index v1 references install-manifest v0.1 / v0.2 / v0.3 / v0.3.1 / v0.4 URLs without coupling to any single version. Future install-manifest releases extend the index's `manifest_version` enum additively.

**Pre-publish check.** Before announcing your index to a registry, run `install-manifest validate <path>` on every manifest URL it points at. The reference CLI uses the same bundled schemas downstream registries use, so a CLI pass is the canonical guarantee that federation sync won't skip your entries. Registries SHOULD also validate fetched manifest bodies against the canonical schema (not just the well-known index surface) — `install-manifest>=0.4.0` exposes `install_manifest.validate.validate(doc)` as a library function for that purpose.

Beyond schema validity, `install-manifest>=0.5.0` adds `install-manifest lint <path> [--strict]` — ten best-practice rules covering missing `verify` / `kill_switch`, weak `data_boundary` declarations, non-HTTPS URLs, loose secret acceptance, non-kebab-case `tool.id`, non-SemVer `tool.version`, missing per-action `docs.goal`, and unbounded `verify.sla`. Default exit is `0` with stderr warnings; `--strict` exits non-zero for CI gating. See [`cli/README.md`](cli/README.md) for the full rule catalog.

---

## Repo layout

```
schema/
  install-manifest-v0.1.json         # frozen
  install-manifest-v0.2.json         # frozen
  install-manifest-v0.3.json         # superseded by 0.3.1
  install-manifest-v0.3.1.json       # superseded by 0.4
  install-manifest-v0.4.json         # current
  well-known-index-v1.json           # federation discovery index (sibling spec)
design/
  v0.1-design-notes.md               # field-by-field rationale (frozen)
  v0.2-design-notes.md               # field-by-field rationale (frozen)
  v0.3-design-notes.md               # field-by-field rationale (superseded by 0.3.1)
  v0.3.1-design-notes.md             # field-by-field rationale (superseded by 0.4)
  v0.4-design-notes.md               # field-by-field rationale (current)
  well-known-index-v1-design-notes.md  # federation discovery index design notes
examples/
  gmail.json                         # v0.1 example (MCP-stdio Gmail tool)
  gmail.v0.2.json                    # v0.2 example (Python-module Gmail tool with actions[])
  gmail.v0.3.json                    # v0.3 example (adds verify + data_boundary + actions[].docs) — validates unmodified against v0.4
  muninn-flowing.v0.3.json           # community attestation (Muninn) — validates unmodified against v0.4
  muninn-verify-patch.v0.3.json      # community attestation (Muninn) — validates unmodified against v0.4
  muninn-perch-publish.v0.3.json     # community attestation (Muninn) — validates unmodified against v0.4
  install-manifests-index.muninn.json # example well-known index (kind=github, 4 manifests)
cli/                                 # reference Python CLI
  install_manifest/                  #   package — version-dispatch validator
  tests/                             #   pytest (covers all five versions)
  scripts/sync_schema.py             #   mirrors schema/ into install_manifest/_data/
  pyproject.toml
LICENSE                              # MIT
```

---

## Quick start (for tool authors)

1. Read [`design/v0.4-design-notes.md`](design/v0.4-design-notes.md) — covers the v0.4 additive deltas and links back to v0.3.1 / v0.3 / v0.2 / v0.1 for unchanged surfaces.
2. Copy [`examples/gmail.v0.3.json`](examples/gmail.v0.3.json) and adapt for your tool. Bump `manifest_version` to `"0.4"` if you adopt any new field (`runtime.install.method: "preinstalled"` + `locator`, `data_boundary.transmits[].to_kind: "agent-supplied"`, optional `to_constraint`); otherwise stay on `"0.3"` or `"0.3.1"`.
3. **Validate before publishing.** Run the reference CLI against your manifest — it dispatches on `manifest_version` and uses the same bundled schemas registries use, so passing the CLI means downstream registries (including toolspace.yepgent.com's federation sync) won't reject your manifest.
   ```
   pip install install-manifest
   install-manifest validate path/to/your-tool.v0.4.json
   install-manifest lint     path/to/your-tool.v0.4.json   # best-practice warnings (0.5.0+)
   ```
   Any JSON Schema validator (`ajv`, `jsonschema`, `check-jsonschema`) works equivalently for `validate` if you prefer not to install the CLI — point it at [`schema/install-manifest-v0.4.json`](schema/install-manifest-v0.4.json). `lint` is CLI-only.
4. Host it at a public URL. Submit to a manifest-aware registry, or share the URL directly with agents.

If your tool is an MCP-stdio server and the protocol's own discovery is enough, v0.1 is still a perfectly valid choice; pin `manifest_version: "0.1"` and use the v0.1 schema.

## Quick start (for agent authors)

1. Read [`design/v0.4-design-notes.md`](design/v0.4-design-notes.md) and [`cli/README.md`](cli/README.md).
2. Implement: fetch manifest → validate → consent → collect env → install → smoke → persist + record. Revoke via `kill_switch`. For v0.2+ manifests, drive operations via the `actions[]` catalog. For v0.4 `method: "preinstalled"`, skip acquisition and probe the `locator` before `smoke`.
3. Try the reference Python CLI:
   ```
   cd cli && pip install -e ".[test]"
   install-manifest validate    ../examples/gmail.v0.3.json
   install-manifest show        ../examples/gmail.v0.3.json
   install-manifest collect-env ../examples/gmail.v0.3.json --yes --non-interactive --env GOOGLE_CLIENT_ID=...
   install-manifest lint        ../examples/gmail.v0.3.json                              # best-practice warnings (0.5.0+)
   install-manifest diff        ../examples/gmail.v0.3.json <upgraded-url> --upgrade-safe # breaking-change detector (0.5.0+)
   ```
   The CLI dispatches automatically on `manifest_version`. `diff` requires both manifests to declare the same `manifest_version`. Other implementations (Node, Go, Rust) are welcome.

---

## Spec at a glance

A v0.4 manifest declares everything v0.3.1 declared, plus the additive deltas listed in the version table. The surfaces below are unchanged from v0.3.1 unless flagged:

- **Identity** (`tool`) — id, version, name, summary, homepage. Optional `namespace` since v0.3.1.
- **Runtime** (`runtime`) — how to install and how to invoke (entrypoint command or HTTP endpoint). v0.3 methods: `pip` / `npm` / `git` (with v0.3.1 `layout` hint) / `container` / `url`+sha256. **v0.4** adds `preinstalled` with a required `locator` (kinds: `python-module` / `binary-on-path` / `mcp-server-id`) for tools baked into the agent's runtime image.
- **Env** (`env`) — variables to collect from the human, each with prompt text, secret flag, optional regex validator and `obtain_url`.
- **Scopes** (`scopes`) — permission declarations (resource + actions + rationale) shown to the human as the consent screen.
- **Actions** (`actions`, **new in v0.2**) — catalog of operations the agent can call. Each entry declares its invocation method (subcommand / stdin-json / http / mcp-tool), input schema, output schema, side-effect severity (none / read / write / destructive), and idempotence. Required for non-MCP-stdio runtimes.
- **Verify** (`verify`, **new in v0.3**) — optional ongoing-verification contract: a JSONL eval suite, an SLA (p50/p95/error rate), and a re-run schedule. Distinct from `smoke` (one-shot install gate).
- **Data boundary** (`data_boundary`, **new in v0.3**, required when `scopes[]` touches private user data) — declares what private resources the tool reads, what it transmits to third parties (with controlled `third_party_retention` enum), what it persists, and retention windows. **v0.4** adds `transmits[].to_kind: "agent-supplied"` (mutually exclusive with `to`) plus optional `to_constraint` prose for outbound destinations supplied by the calling agent at runtime.
- **Smoke** (`smoke`) — required verification step (shell / http / mcp-tool-call / action-call) with structured success criteria. v0.3.1 added `json_pointer_in` (set-membership) and `json_pointer_present` (non-null + non-empty) alongside the existing `json_pointer_equals` / `json_pointer_exists`.
- **Kill switch** (`kill_switch`) — required revocation path. v0.3 shapes: `url` / `shell` / `manual`. v0.3.1 added `none` (stateless tools — validator enforces empty `env` and empty `data_boundary.persists`) and inline `kill_switch.manual.instructions` (≤2000 chars, mutually exclusive with `instructions_url`).
- **Cost** (`cost`) — optional billing model in cents, with `external` escape hatch for tools that bill via their own credentials.
- **Support** (`support`) — optional issues_url, security_email, docs_url.

`smoke` and `kill_switch` are non-negotiable. An agent that cannot verify install correctness or revoke a tool cannot recover from a compromised credential.

---

## Status

v0.4 is strictly additive on top of v0.3.1, closing the two largest structural gaps that v0.3.1 left open: variable-target outbound transmits (issue [#4](https://github.com/drknowhow/install-manifest-spec/issues/4)) and `runtime.install.method: "preinstalled"` for tools baked into the agent's runtime image (issue [#5](https://github.com/drknowhow/install-manifest-spec/issues/5)). The earlier narrowings carry forward: `data_boundary` is required when `scopes[]` touches private user data; `kill_switch.kind: "none"` requires env-empty + persists-empty. Remaining gaps deferred to v0.5+:

- Manifest signing / author identity verification
- Cross-env dependency declarations (e.g., "obtain X only after Y is set")
- Tool-to-tool dependencies (unblocked by v0.3.1's `tool.namespace` + `tool.id` two-field identity — dependency shape still open)
- Versioning / upgrade flows beyond install + revoke
- Secrets-in-argv linter (documented since v0.2; still a candidate)
- A standardized eval-suite runner (v0.3 declares `verify.suite.ref` and `format`; runner still pending)
- `actions[].runtime_telemetry` shape (reserved opaque in v0.3; v0.5 fills it in for adaptive tool routing)
- `runtime.install.layout` Shape B — structured layout-with-validation beyond v0.3.1's informational hint

See [`design/v0.4-design-notes.md`](design/v0.4-design-notes.md) for v0.4 rationale, [`design/v0.3.1-design-notes.md`](design/v0.3.1-design-notes.md) for v0.3.1, and [`design/v0.3-design-notes.md`](design/v0.3-design-notes.md#open-design-questions-v03--v04-backlog) for the older open questions; PRs welcome.

## License

MIT — see [`LICENSE`](LICENSE).
