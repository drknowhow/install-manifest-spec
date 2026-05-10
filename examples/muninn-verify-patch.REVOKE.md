# Revoking muninn-verify-patch

This tool has no server-side state. Revocation is a checklist of credential rotations and a Python uninstall.

## Primary kill — stops all verify calls immediately

1. **Revoke `ANTHROPIC_API_KEY`** at https://console.anthropic.com/settings/keys.
   The tool cannot run any `verify` action without this key. This is the only mandatory step.

## Conditional steps

2. **If you configured Cloudflare AI Gateway proxying:**
   Revoke `CF_API_TOKEN` at https://dash.cloudflare.com/profile/api-tokens.
   This stops the gateway proxy path; direct calls to api.anthropic.com are already blocked by step 1.

3. **If you configured tracking** (TURSO_TOKEN / TURSO_URL set, `track=true` used,
   or you ran `review` / `stamp`):
   - To stop **future** tracking writes: revoke `TURSO_TOKEN` at https://app.turso.tech/.
   - The tracking memories already in your Turso DB are **yours** and persist until you delete
     them. Neither this tool nor any of the above key rotations remove them. To delete:
     query rows tagged `verify-patch-tracking` and remove via your DB tool of choice.

## Uninstall the code

4. If installed via the manifest's `runtime.install` (git, oaustegard/muninn-utilities,
   subpath `muninn_utils`), remove the cloned tree from your installed-tools directory.
   If you bypassed the manifest and pip-installed the parent package, run:

   ```
   pip uninstall muninn-utilities
   ```

## What this kill switch cannot do

- It cannot revoke past calls. If `verify` already sent your patch text to Anthropic, that
  request is in their logs subject to whatever retention applies to your account.
- It cannot delete tracking memories already written to your Turso DB (step 3 above).
- It cannot stop a parallel installation that has its own copy of the env vars.

This file exists because install-manifest-spec v0.3's `kill_switch.manual` only accepts an
`instructions_url`, not inline text. Filed as a finding in muninns-inbox discussion #1.
