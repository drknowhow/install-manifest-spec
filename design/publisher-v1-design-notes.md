# Publisher Identity (`publisher` block) — Design Notes

**Status:** additive to v0.4, drafted 2026-06-25. **Held** pending upstream
ARD §5.1 wording (see below).
**Schema:** `schema/install-manifest-v0.4.json` (optional top-level `publisher`).
**Upstream companion:** [ards-project/ard-spec#47](https://github.com/ards-project/ard-spec/issues/47)
/ [PR #49](https://github.com/ards-project/ard-spec/pull/49).

---

## Why this exists

A v0.4 install-manifest carries no in-document publisher identity. The
strongest publisher signal a consumer has today is the URL the manifest was
fetched from (the *host*, not necessarily the *publisher*) and `tool.namespace`
(a collision-avoidance handle, explicitly informal). For a publisher with no
DNS root — identity rooted in a [W3C DID](https://www.w3.org/TR/did-core/) and a
signed personal data store — neither signal lets a consumer cryptographically
verify *"this manifest was published by the entity that controls DID X."*

That gap is upstream of install-manifest (it is ARD's discovery/identity layer),
but it has a direct mirror here: the manifest is the install-time consent
envelope, and an unsigned envelope from a domainless publisher is
unauthenticated. The optional `publisher` block closes it without touching any
existing field.

## Shape

Optional top-level object alongside `tool`. Manifests without it remain valid
(additive; existing v0.3.x / v0.4 manifests are unaffected).

| Field | Req | Meaning |
| :-- | :-- | :-- |
| `did` | yes | Publisher DID. Initial method set **`did:plc`, `did:web` only**, mirroring ARD PR #49; further methods deferred. |
| `signature` | yes | Detached JWS (RFC 7515 §A.5) over the **JCS-canonicalized (RFC 8785)** manifest bytes with `publisher.signature` removed. |
| `did_kid` | no | Selects a `verificationMethod` in the resolved DID Document; default = first compatible. |
| `fqdn` | no | Hybrid publishers controlling both a domain and a DID; MUST equal the serving host. |

## Verification (consumer side)

1. Resolve the DID Document — `did:plc` → `https://plc.directory/<did>`,
   `did:web` → `https://<host>/.well-known/did.json`.
2. Select the `verificationMethod` (by `did_kid`, else first compatible with the
   JWS `alg`).
3. Reconstruct the signed payload: manifest bytes with `publisher.signature`
   removed, **JCS-canonicalized (RFC 8785)**.
4. Validate the detached JWS against the verification key.
5. Accept the manifest as bound to that DID.

The host is no longer the trust signal; control of the DID is. This is the exact
mirror of ARD's §5.1.1 resolution path — by design, the same canonicalization
(JCS) and the same method set, so a registry that resolves an ARD entry and a
consumer that installs the linked manifest run one signing model, not two.

## Decisions and open questions

- **Canonicalization = JCS, pinned.** Not implementation-defined. Locked to match
  ARD §5.1.1 (per maintainer guidance on #47). `c14n` was considered and rejected
  for the same single-mental-model reason.
- **Method set held to `did:plc` + `did:web`.** Mirrors the upstream initial set.
  `did:key` / `did:peer` and path-bearing `did:web` are deferred to a follow-up
  once the resolution machinery is validated against the small set.
- **`did` vs `identity` vs a nested `trust` block** — naming still open to
  bikeshed; the shape is settled.
- **CLI support is out of scope here.** Resolving `publisher.did` and validating
  the signature lands in the reference CLI as a later `>=0.7.0` feature with its
  own tests and CHANGELOG entry — not in this additive-schema change. Until then
  `validate` SHOULD warn (not fail) on a missing `publisher` block, mirroring the
  Content-Type warning pattern in #36.

## Why held

The JWS canonicalization choice was gated on ARD settling its §5.1 normative
wording. The maintainer confirmed JCS on #47; this companion is drafted in
lockstep but **should not merge until ARD PR #49's §5.1 / Appendix C text is
approved by @rvguha**, so the two specs cannot drift. If upstream revises the
resolution path in review, this note and the schema follow it before merge.
