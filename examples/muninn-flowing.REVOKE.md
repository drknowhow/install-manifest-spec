# Revoking muninn-flowing

flowing is a pure-compute Python framework. It has no credentials, no network access,
no persistent state, no server-side resources. There is genuinely nothing to revoke.

## What "uninstall" means

Remove the cloned source from your installed-tools tree. If you used the manifest's
`runtime.install` (git clone of `oaustegard/claude-skills` at the declared SHA, subpath
`flowing/scripts`), delete the cloned directory.

## What this kill switch cannot do

- It cannot undo Flows that have already run. If a consumer's `@task` bodies wrote to
  external systems (posted to social, called APIs, mutated databases), those side
  effects belong to the *consumer's* tools, not flowing. Each downstream manifest is
  responsible for its own kill switch.
- It cannot remove flowing's transitive presence in the user's other tooling. If a
  consumer Python package depends on flowing as a library, uninstalling flowing
  breaks that consumer; uninstall the consumer first.

## Why this file exists

install-manifest-spec v0.3 requires every manifest to declare a `kill_switch`. For a
stateless pure-compute framework, the spec's `kind: manual` with `instructions_url`
is the closest fit, but the actual instructions are a single sentence: "delete the
files." A future spec revision could add `kill_switch.kind: "stateless"` (or
`"none-needed"`) for tools whose only revocation is uninstall. Filed as a finding in
muninns-inbox discussion #1.
