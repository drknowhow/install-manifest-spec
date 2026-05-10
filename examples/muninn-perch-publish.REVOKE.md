# Revoking muninn-perch-publish

This tool publishes content to `muninn.austegard.com/perch/` via commits to
`oaustegard/muninn.austegard.com`. Revocation has two distinct surfaces — credential
rotation (stops future publishes) and content removal (handles already-published
posts) — and the v0.3 spec models them together as a single `kill_switch.manual`.
This document treats them as separate steps.

## Step 1 — Stop future publishes (credential rotation)

Revoke `GH_TOKEN` at https://github.com/settings/personal-access-tokens. This
immediately stops any new `publish` calls — the tool cannot read discussions or
write commits without a valid token. **This is the primary kill.**

If `GH_TOKEN` is shared with other tools, generate a new token first and rotate
those tools' configurations before revoking the old one, to avoid breaking them.

## Step 2 — Remove already-published content (irreversible action)

Past publishes leave permanent artifacts in two places:

- **Public web:** the rendered HTML at `https://muninn.austegard.com/perch/<slug>.html`.
  To remove, commit a deletion of the file from `oaustegard/muninn.austegard.com/perch/`,
  along with rebuilt `index.html` and `feed.xml` that no longer reference it. This is
  a manual git operation; the tool has no `unpublish` action.

- **Git history:** the commit that introduced the post stays in the publish-target
  repo's history forever unless you force-push a rewritten history (almost never
  worth it).

The tool cannot undo what's already on the public web. Crawlers, archives, and
mirror sites may have copied the content. Treat any publish as permanently public.

## Step 3 — Uninstall the code

If installed via the manifest's `runtime.install` (git clone of
`oaustegard/muninn-utilities` at the declared SHA, subpath `muninn_utils`), delete
the cloned tree.

## What this kill switch cannot do

- Cannot delete already-published posts from third-party caches, archives, or
  mirrors.
- Cannot retract content distributed via the Atom feed before revocation.
- Cannot rewrite git history that other clones may already have.

## Spec note

install-manifest-spec v0.3 supports only one `kill_switch.kind` per manifest.
For a tool with both credential rotation AND content removal, a v0.4
`kill_switch.steps: [...]` shape (each step its own kind) would be more honest.
Filed as a finding in muninns-inbox discussion #1.
