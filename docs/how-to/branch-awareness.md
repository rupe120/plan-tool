# Branch-awareness — bind a plan to its own branch (opt-in)

Branch-awareness lets a registered plan own a git branch, so `run` can
nudge you onto the right branch before executing a step. It is disabled by
default; enable it explicitly when you want plan-specific branch guidance.

## The derived branch name

A registered plan's branch is **derived from its slug**:
`<primary-prefix><slug>`, default `plan/<slug>`. The prefix set is the
configurable `branch_prefixes` list (default `["plan/"]`,
project-over-user precedence):

- the **primary** (first) prefix names the branch `create` makes;
- **all** configured prefixes are accepted when matching/enforcing, so a
  dev who used `feature/<slug>` is still recognized.

## Ad-hoc overrides

A plan can carry an optional untracked ad-hoc override:

```bash
plan-tool attach-branch <name> <branch>   # store an override (machine-local git config, never committed)
plan-tool detach-branch <name>            # clear it
```

When a plan's expected branch differs from the one you're on, `run`
nudges you toward it. `run <name> --switch-branch` creates-if-missing and
switches on a clean tree.

## Enabling it

Enable per-repo in `.plan-tool/config.json`:

```json
{ "branch_awareness": { "enabled": true } }
```

or set `PLAN_TOOL_BRANCH_AWARENESS=1`. The enabled flag resolves:
`PLAN_TOOL_BRANCH_AWARENESS` env → project `.plan-tool/config.json` →
user `~/.plan-tool/config.json` → `false`.

## Disambiguating a colliding branch

When `create` disambiguates a colliding branch it cuts the new branch
from the default branch, resolved via `origin/HEAD` (or
`PLAN_TOOL_DEFAULT_BRANCH` when set). On a local-only repo where the
default is undeterminable, disambiguation is skipped with an info note;
setting `PLAN_TOOL_DEFAULT_BRANCH` restores it.
