# Install Manifests Well-Known Index v1 — Design Notes

**Status:** v1 design, drafted 2026-05-28.
**Schema:** `schema/well-known-index-v1.json`.
**Worked example:** `examples/install-manifests-index.muninn.json`.
**Sibling spec:** the install-manifest schemas (`schema/install-manifest-v0.*.json`). The well-known index references their URLs; it does not extend them.

---

## Why this exists

The install-manifest spec is vendor-neutral and registry-agnostic by
design. A manifest can be hosted at any URL; multiple registries can
index the same manifest; no single registry has authority over the
contract. That is the moat.

What was missing through v0.4: **how does a registry learn about a
publisher's manifests in the first place?** The toolspace.yepgent.com
registry has been ingesting Muninn's manifests by hand — Yep watches
oaustegard/muninn-utilities, sees a new manifest land, and opens a PR
on drknowhow/toolspace-site to mirror it into the registry's
`manifests.json`. That is a Yep-in-the-loop pipeline. It scales
linearly with attention. When 10 publishers ship in a week, the
registry lags days behind.

A vendor-neutral fix needs three pieces:

1. A **discovery format** — a JSON document a publisher hosts at a
   well-known location that lists their install-manifest URLs.
2. A **publisher identity model** that doesn't require every publisher
   to own a domain (many tool authors ship from a GitHub repo, a
   personal handle on the AT Protocol, or both).
3. A **trust gate** that keeps the discovery loop honest — registries
   only crawl publishers a maintainer has reviewed and added to an
   allowlist. The allowlist lives in the registry's own repo; this
   spec defines the document publishers host, not the allowlist
   format.

This document specifies piece (1) plus the identity-kind contract for
piece (2). Allowlist mechanics — file shape, review procedure, trust
tiers — are out of scope: they belong to each registry. drknowhow/
toolspace-site ships its allowlist as `publishers.json`; another
registry could ship a different shape and still consume the same
publisher indexes.

---

## What v1 is NOT

- **Not a registry API.** Publishers host static JSON at HTTP-fetchable
  URLs. Registries do an anonymous GET on a schedule. There is no
  push, no auth, no rate-limit handshake. The simplicity is load-
  bearing — it's why publishers can stand one up in fifteen minutes.
- **Not a manifest signing scheme.** Manifest signing is still
  deferred to a later install-manifest version. The well-known index
  inherits the install-manifest's current trust model: the registry
  verifies that the publisher claims the manifest and that the
  publisher controls the discovery location. Manifest content
  authenticity is a separate axis.
- **Not a publisher onboarding flow.** Onboarding (how a publisher
  gets onto a given registry's allowlist) is per-registry. This
  spec assumes the allowlist already contains the publisher; it
  describes what the registry fetches once that's true.
- **Not a federation protocol between registries.** Two registries
  that both crawl the same publishers will see the same content
  and arrive at independent indexes. Registry-to-registry
  reconciliation is its own design problem and is out of scope.

---

## Shape

A publisher hosts one JSON document at a kind-specific discovery
location:

```json
{
  "version": "1",
  "publisher": {
    "kind": "github",
    "id": "oaustegard/muninn-utilities",
    "display_name": "Muninn Utilities",
    "homepage": "https://github.com/oaustegard/muninn-utilities",
    "contact": "oskar@example.com"
  },
  "generated_at": "2026-05-28T00:00:00Z",
  "manifests": [
    {
      "id": "muninn-bsky-card",
      "manifest_url": "https://raw.githubusercontent.com/oaustegard/muninn-utilities/main/manifests/bsky-card/muninn-bsky-card.v0.4.json",
      "manifest_version": "0.4",
      "status": "active",
      "summary": "Render a Bluesky external embed card for a URL.",
      "tags": ["bluesky", "embed", "social"]
    }
  ]
}
```

Required fields: `version`, `publisher`, `generated_at`, `manifests`.
`manifests` MAY be empty (a publisher whose tools are all temporarily
quarantined still publishes a well-formed index).

---

## Identity kinds

The single most opinionated decision in v1 is that the publisher
identity is a tagged union of three kinds, not a single canonical
form. Forcing every publisher to own a domain (the obvious choice for
a `.well-known/` spec) would gate independent tool authors out of
federation. The kinds:

| Kind | `id` shape | Discovery location | Ownership proof |
|------|-----------|--------------------|-----------------|
| `github` | `<owner>/<repo>` | `https://raw.githubusercontent.com/<owner>/<repo>/main/.well-known/install-manifests.json` | Repo write access — proven implicitly by the file existing on `main`. |
| `https` | bare hostname | `https://<host>/.well-known/install-manifests.json` | DNS TXT record at `_toolspace-challenge.<host>` OR file at `https://<host>/.well-known/toolspace-challenge.txt` matching a maintainer-issued token. |
| `atproto` | `did:plc:...` or `did:web:...` | PDS record at lexicon `app.toolspace.installManifests`, key `self`, referenced by `publisher.atproto_record_uri` | DID resolves to a PDS; the record at the named at-uri is signed by the DID's signing key per AT Protocol's normal record-authority rules. |

A publisher MAY register under multiple kinds — the registry's
allowlist links them. The schema treats each kind as an independent
identity; one entry per index.

### Why each kind earned its place

#### `github`

The largest population of current install-manifest authors lives on
GitHub. Asking them to register a domain or stand up a PDS to be
discoverable is a friction wall. A raw-content URL on `main` is
something they already publish for free.

The tradeoff: there is no cryptographic ownership proof beyond "the
file is on `main`." A repo takeover or a malicious push from a
collaborator would produce a valid-looking publisher. The mitigation
sits in the registry's allowlist (trust gate) and in `manifest_url`
SHAs (publishers SHOULD prefer commit-pinned URLs over `main` raw for
the manifests themselves, even when the index itself sits on `main`).

#### `https`

The classic `.well-known/` shape, for publishers who do control a
domain — typically organizations with a project site or established
service. The challenge mechanism (DNS TXT or a static file with a
maintainer-issued token) prevents drive-by claims against a domain
the publisher doesn't actually control.

The mechanism is intentionally lightweight: registries that want
stronger guarantees (signed challenges, ACME-style proof-of-control)
can layer them on top of the same `id` shape without an index-schema
bump.

#### `atproto`

Some agents — Muninn included — already have a primary identity on
the AT Protocol. Forcing those publishers into a GitHub or DNS proxy
for federation purposes is a poor fit for their actual identity
graph. A PDS record at `app.toolspace.installManifests/self` is the
AT-native form.

`atproto` is the only kind that requires an extra top-level field:
`publisher.atproto_record_uri`. Registries fetch the record at the
at-uri (which is signed by the DID's authority key) and compare its
contents against the index served at any public mirror. If a mirror
serves a different document than the at-uri's record, the registry
SHOULD trust the at-uri.

v1 ships the schema-level surface for `atproto`. Registries are
expected to ship support for `github` and `https` first; `atproto`
support tracks publisher demand.

### Pattern enforcement

Per-kind `id` patterns are enforced via top-level `allOf` blocks. This
mirrors the install-manifest's `data_boundary`-required-when-private-
scopes pattern. A single shared `id` field with conditional patterns
keeps the schema close to one-place-to-edit while still rejecting
mismatched ids at validate time.

---

## `manifests[]` field-by-field rationale

### `id`

Globally unique tool id. Same `^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$`
pattern as install-manifest's `tool.id`. The constraint that this
matches the fetched manifest's `tool.id` is the cheapest possible
publisher-equivocation check: a publisher cannot list a manifest
under id X whose actual manifest declares id Y. Registries reject
on mismatch.

### `manifest_url`

URL to the install-manifest. SHOULD be commit-pinned for git hosts
(`/raw.githubusercontent.com/<owner>/<repo>/<sha>/path.json`). MAY
be a `main`-branch raw URL for active development. MUST be
anonymously fetchable — no auth required, no cookie gating, no
JavaScript-rendered redirects. Registries will pull this URL on
their crawl cadence.

### `manifest_version`

Declared install-manifest schema version of the document at
`manifest_url`. Required because it lets the registry route to the
correct validator before fetching: a v0.4 manifest fails differently
than a v0.3 manifest, and the registry's cost of getting it wrong is
indexing-pipeline error logs rather than user-visible failures.

The enum (`0.1` / `0.2` / `0.3` / `0.3.1` / `0.4`) is bounded by
which install-manifest versions exist at v1 freeze. Each new
install-manifest minor version is an additive enum extension to this
schema. Adding `0.5` is a one-line schema change — index-schema
version 1 carries through.

### `status`

Lifecycle state:

- `active` — current, supported, registry-listable.
- `deprecated` — still works, but the publisher recommends an
  alternative tool (named in `deprecated_in_favor_of`).
- `broken` — publisher acknowledges the URL 404s or fails validation.
  Surfaced to the registry as a hint to avoid the fetch.
- `quarantined` — registry-set state propagated back here for
  legibility. Publishers SHOULD NOT self-assign this status;
  registries set it when an active manifest fails repeated fetch
  or validation. Self-acknowledged failures use `broken`.

Required field. Default `active` would be tempting but is rejected:
status carries action consequences (a registry crawl skips
quarantined entries), and an absent status is a worse default than
forcing the publisher to make the claim explicit.

`deprecated_in_favor_of` is required when status is `deprecated` —
the deprecation hint is the entire reason for the lifecycle state.

### `summary` and `tags`

Optional but recommended. Same caps and patterns as install-manifest's
`tool.summary` and `tool.tags`. The point: a registry that wants to
build a search index over all published manifests should be able to
do so without fetching every manifest_url. For a publisher with 50
manifests, the registry pulls one index document instead of 51 to
build the search corpus. The full manifests are still fetched for
install — the well-known index is search metadata, not the source of
truth for behavior.

A publisher MAY also omit these and force registries that want
search metadata to fetch each manifest. The schema is permissive on
purpose; some publishers prefer one source of truth at the cost of
registry traffic.

---

## What the well-known index deliberately does NOT carry

- **Cost or pricing.** Lives in the install-manifest's `cost` block,
  per-tool, not at the publisher level. A single publisher MAY ship
  free and paid tools simultaneously.
- **Author / maintainer detail.** Lives in the install-manifest's
  `tool.author`. The publisher block here is about who controls the
  discovery location, which is a different (and weaker) claim than
  who authored a given tool inside that publisher's catalog.
- **Health metrics.** A publisher's runtime uptime, SLA compliance,
  and verify-suite pass rate belong to the registry's own per-
  manifest health surface, derived from `verify` blocks. Putting
  them in the index would invite stale self-reports.
- **License.** Lives in the install-manifest. The well-known index
  is permissively-licensed JSON (the publisher publishes it because
  they want it crawled), but the tool licenses are per-manifest.

---

## Registry behavior expected

A registry that consumes well-known indexes does, per crawl cycle:

1. Read its own publisher allowlist (out of scope for this spec).
2. For each allowlisted publisher, build the discovery URL from
   `(kind, id)`.
3. Fetch the URL. On 404 or fetch error, surface to the maintainer
   and skip.
4. Validate the fetched document against `schema/well-known-index-v1.json`.
   Reject indexes that fail schema validation.
5. For each `manifests[]` entry:
   - Verify `id` matches a pattern-acceptable tool id.
   - Fetch `manifest_url`.
   - Validate against the install-manifest schema for the declared
     `manifest_version`.
   - Verify the fetched manifest's `tool.id` matches the index's
     declared `id`.
   - On any mismatch: surface as a quarantine candidate, do not
     index.
6. Persist accepted manifests into the registry's own indexes.

The registry is free to do this on whatever cadence makes sense
for its users. drknowhow/toolspace-site will run daily.

---

## Open design questions (v1 → v2 backlog)

1. **Signed indexes.** v1 ships ownership proofs for the discovery
   location only (DNS TXT, `.well-known` file, AT Protocol record).
   The index document itself is unsigned. A future version may
   add a `signature` block (likely a JWS over the canonical-JSON
   form) so that out-of-band copies can be re-verified against the
   publisher's identity. Deferred until cross-registry caching
   surfaces an actual MITM concern.

2. **Manifest content hash.** Adding `manifest_sha256` per entry
   would let registries pin a specific manifest content rather than
   trust the URL's stability. Deferred because commit-pinned URLs
   already provide this and most v0.4 publishers (including Muninn)
   use them. Revisit if a non-git publisher class emerges.

3. **Soft delete semantics.** Removing a manifest from `manifests[]`
   between crawls is functionally a delete. v1 doesn't distinguish
   "publisher rotated catalog" from "publisher deleted historically
   indexed tool." Registries currently MAY infer the prior state
   from their own history. v2 may add an explicit `removed[]` list
   for cross-registry consistency.

4. **Per-kind multi-document indexes.** A publisher with 200+
   tools might want to shard the index across multiple files. v1
   caps `manifests[]` at 256 entries (a soft ceiling; the schema's
   `maxItems`). v2 may add an `includes[]` field referencing
   additional index documents. Deferred until any real publisher
   approaches the cap.

5. **Trust tier vocabulary.** Registries' allowlists carry trust
   tiers (toolspace's `publishers.json` ships `standard | trusted |
   verified`). A future revision may standardize the vocabulary so
   tiered tools can be cross-registry-comparable. v1 leaves the
   vocabulary entirely registry-private.

6. **Atproto lexicon publication.** `app.toolspace.installManifests`
   needs to be published to the AT Protocol's lexicon registry
   before `atproto` kind is operational. v1 reserves the name in
   the schema; the lexicon ships with the first registry that
   implements atproto support.

---

## Migration & compatibility

There is no prior version of this index. v1 is the first revision;
publishers and registries adopt it from scratch.

Forward-compat discipline mirrors install-manifest: future versions
that add fields will bump the top-level `version` const. A v1
registry must reject v2 documents outright (the const enforces this).
Additive changes to enums (e.g. extending `manifest_version` when
install-manifest v0.5 ships) do not require a v2 — they're additive
within v1.

---

## Drift caution

The well-known index v1 is a small spec. The temptation will be to
fold more into it — cost, ratings, telemetry, signing, federation
metadata. Each addition makes the spec heavier and the publisher
overhead higher. The principle is: anything that's per-tool belongs
in the install-manifest, not here. Anything that's per-registry
belongs in the registry's own data, not here. The well-known index
exists to answer one question only: *what URLs should the registry
fetch?*

Tightness is the design. Resist scope creep.
