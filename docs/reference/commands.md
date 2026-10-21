# Command guide

*Back to the [README task routes](../../README.md#start-here).*

This is the everyday cheat sheet: the commands you'll reach for, the
placeholders they use, the global flags, and the `run` modes. Keep it
open in a tab. For every flag and default, see the generated
[CLI reference](../cli/README.md).

## Choose a command family

Start with the task, then use the syntax block and flag notes below for the
exact invocation. The [common workflows](../how-to/common-workflows.md) guide
owns the ordered pipeline and recovery decisions.

| Task | Commands | Read next |
| --- | --- | --- |
| Stage a project-sized concept | `roadmap` | [Roadmap walkthrough](../how-to/roadmap.md) |
| Author a plan and details | `create`, `detail`, `annotate` | [Common workflows](../how-to/common-workflows.md) |
| Audit an authored plan or re-ground a stale one | `completeness-audit`, `reconcile-plan` | [Audit guide](../how-to/pipeline/audit.md) |
| Execute or protect plan work | `suggest-gates`, `run`, `verify-all` | [Run guide](../how-to/pipeline/run.md) |
| Export or inspect state | `jira`, `list`, `status`, `validate`, `register`, `deregister`, `checkpoint`, `lessons` | Generated [CLI reference](../cli/README.md) |

## CLI usage

The block below covers the common invocations. For the exhaustive
per-subcommand reference — every flag, default, and subaction, generated
straight from the parser — see the generated [CLI reference](../cli/README.md).

```bash
# Roadmap — stage a project-sized concept brief into architecture artifacts, one rung above create.
plan-tool roadmap <slug> [--from-existing <concept.md>]                  # four-stage first run, resumable; publishes one version
plan-tool roadmap <slug> --compare [--comparison-base VERSION_ID] [--comparison-target VERSION_ID] [--comparison-output {cards,patch,json}] # read-only two-snapshot review
plan-tool roadmap <slug> --submit-feedback ITEM_ID --feedback-target <artifact>:<kind>[:ROW_ID] --feedback-request TEXT # add one ledger item
plan-tool roadmap <slug> --reopen-ledger-feedback ITEM_ID                # reopen one retained ledger item
plan-tool roadmap <slug> --propose-candidate                             # snapshot eligible ledger items into an inert candidate
plan-tool roadmap <slug> --materialize [PLAN_ID]                         # rebuild draft seeds
plan-tool roadmap <slug> --refresh-seeds                                 # refresh all draft seeds
plan-tool roadmap <slug> --apply [-y]                                    # promote seeds to plan-seeds/
plan-tool roadmap <slug> --accept-seed PLAN_ID                           # accept a directly edited draft
plan-tool roadmap <slug> --view {summary,walk,ledger,index,seeds,html} [--mode {current,review}] [--id ROW_ID] [--output PATH]   # read-only artifact views

# Author — create a plan, then draft per-step detail files.
plan-tool create [slug] [--from <description> | --from-existing <path>] [--no-synthesize-body] [--no-fetch-docs] [--output-dir <dir>] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]   # slug is optional; root safety checks
plan-tool detail <name> [--step N] [--force] [--dry-run] [--no-resume] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]

# Annotate — judge old plans against current code; emit forward seeds for the next create.
plan-tool annotate <path-or-glob>... [--output-dir <dir>] [--report-dir <dir>] [--seed-dir <dir>] [--report <path>] [--seed <path>] [--archive] [--iterate | --no-iterate]   # --iterate is rejected: annotate is single-pass today

# Audit — judge the plan's design/coverage, then reconcile drift (reconcile-plan is mainly for older/stale plans, or a supplement).
plan-tool completeness-audit <name> [--json] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]
plan-tool completeness-apply <name> [--id STEM] [--anchor SLUG] [--rewalk] [--include-info]   # DEPRECATED, going away (BACKLOG #376) -- read the saved report and make a session-directed edit instead
plan-tool data-contract-apply <name> [--id STEM] [--anchor SLUG] [--rewalk] [--include-info]   # interactive walk for saved DATA_CONTRACT.md drift findings
plan-tool reconcile-plan <name> [--step N | --all] [--dry-run] [--refresh] [--no-heuristic] [--no-allow-missing-parent]   # --all is the default; --refresh is cheap

# Execute — lock in built work with gates, then run steps.
plan-tool suggest-gates <name> [-y] [--all-steps]   # propose gate: commands
plan-tool run <name> [--step N | --all [--max-steps N]] [--mode M] [--dry-run] [--allow-missing-parent] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS]

# Verify finished (done) steps before merge.
plan-tool verify-all --rollup <name> [--max-steps N] [--dry-run] [--deep]
plan-tool verify-all <name> --mode <m> [--max-steps N] [--dry-run]

# Export — hand off to external systems.
plan-tool jira <name> [--max-hours N] [--format markdown|json] [--output PATH] [--handoff-output PATH] [--adopt-existing] [--no-write] [--stdout]
plan-tool jira <name> --lint [--format markdown|json]          # lint the conventional jira-stories artifact without invoking Claude
plan-tool jira --lint --input <path>                           # lint an existing markdown/json export directly

# Direct pipeline — DEPRECATED, going away (BACKLOG #376); drive create/detail/run/jira as separate, developer-reviewed steps instead.
plan-tool direct-jira [slug] [--from <description> | --from-existing <path>] [--output-dir <dir>] [--iterate | --no-iterate] [-y]   # create → detail → apply → jira
plan-tool direct-run  [slug] [--from <description> | --from-existing <path>] [--output-dir <dir>] [--iterate | --no-iterate] [-y]   # create → detail → apply → run → reconcile

# Inspect & manage state.
plan-tool list
plan-tool list --status [--report-dir DIR] [--format text|md]  # roll up cached annotate reports for active plans
plan-tool status <name>
plan-tool validate <name>   # frontmatter-schema check only
plan-tool root              # report the resolved repo root
plan-tool register <path-or-slug>
plan-tool deregister <path-or-slug>
plan-tool checkpoint {list | show <slug>/<checkpoint> | clear [<slug> | --all]}
plan-tool lessons consolidate [--apply] [--dry-run] [--plan SLUG] [--min-confidence FLOAT] [--no-resume] [--ignore-recurrence] [-y]
```

### Flag notes

A few of the flags above pack in more than a short comment can hold.
Here's what they do, grouped the same way as the cheat sheet above.

#### Roadmap

- The first `roadmap` run on a slug holds each gate-clean stage — domain,
  constraints, components, roadmap — in a resume directory, then publishes
  one immutable version and the accepted head, plus draft seeds. A rerun
  with the same brief resumes from the first stage that is missing or fails
  its re-gate; a changed brief is refused with its remedy, and a roadmap
  that already has an accepted head refuses a stage run. See
  [`docs/how-to/roadmap.md`](../how-to/roadmap.md).
- `--compare` uses the accepted head as its default base and the active
  candidate as its default target; with no active candidate it needs
  `--comparison-target`. Either side can instead name a stored immutable
  version. Cards and JSON explain Git's complete patch, while
  `--comparison-output patch` prints it. For a candidate target whose direct
  predecessor is the base, cards and JSON also show its verified row-linked
  prose amendments (`bound`). A directly bound candidate that stored no
  operation evidence reports `no-operation-evidence`; other pairs report
  `not-applicable` or `not-directly-bound`. The raw patch remains unchanged.
  The exclusive comparison route is read-only and never accepts, promotes,
  settles, or repairs a snapshot.
- `--submit-feedback ITEM_ID --feedback-target <artifact>:<kind>[:ROW_ID]
  --feedback-request TEXT` adds one reviewer ledger item;
  `--reopen-ledger-feedback ITEM_ID` reopens one retained item and invokes no
  backend. `--propose-candidate` snapshots the eligible `open` items into one
  inert candidate.
- `--materialize [PLAN_ID]` regenerates every recoverable draft seed, or
  just one named row, through the standalone seed materializer — no
  roadmap stages run.
- `--refresh-seeds` regenerates every source-order draft seed against
  current code through that same standalone materializer, and writes a
  diff report.
- `--apply [-y]` is apply-only: it promotes the draft seeds into
  `plan-seeds/` with no brief, backend call, or stages, previewing and
  asking for confirmation unless you pass `-y`. A seed the seed state
  records as published is skipped and named, with a warning when its draft
  is no longer current. An unpublished seed whose destination already exists refuses the
  whole promotion, since `--apply` never overwrites a file it did not write.
- `--accept-seed PLAN_ID` accepts one validated, directly edited draft as
  current — again, no backend call and no stages.
- `--view {summary,walk,ledger,index,seeds,html}`
  (with `--mode {current,review}`, `--id ROW_ID`, `--output PATH`) is
  read-only. It can render a compact review summary, the traceability
  walk, the decision ledger, the reverse citation index, the draft-seed
  state report, a self-contained print-formatted HTML page of every
  artifact row (`<roadmap-dir>/review.html` by default — `--output PATH`
  picks a different destination, `--output -` prints it instead). None of these call Claude or touch the canonical
  roadmap.

#### Author

- `create`'s `[slug]` is optional. Leave it out and plan-tool suggests
  one from `--from` or `--from-existing`; confirm or edit it at the
  prompt, or take it as-is under `-y`.
- If the discovered plan root isn't the current working directory
  (`cwd`), `create` warns and lets you keep that root, switch to the
  current directory, or abort. Under `-y` or a non-TTY session it keeps
  the discovered root; `--repo-root` pins the root directly and skips
  the prompt.
- `--iterate` is on by default for `create`; pass `--no-iterate` to skip
  the post-write convergence loop.

#### Audit

- On `reconcile-plan`, `--all` explicitly selects the plan-wide audit
  that's already the default. `--refresh` is a cheap fingerprint gate
  that skips the Claude call unless the code has actually drifted.

#### Execute

- `suggest-gates` proposes `gate:` commands for the remaining steps,
  grounded in what's already built. Confirm each one, or pass `-y` to
  just report them without writing. `--all-steps` proposes speculative
  gates even when nothing has been built yet.

#### Direct pipeline

**Deprecated, going away (BACKLOG #376).** Both commands exist only to chain
`completeness-apply`'s gap-by-gap apply, which is retiring for the same
reason: it's slower than a whole-report review, and the slow pace obscures
whether the plan is actually converging. Drive the stages separately by
hand instead.

- `direct-jira` chains `create` → `detail` → `completeness-apply` →
  `jira`. If `create` produces an over-large or split plan, it stops
  with exit code 0 and steers you toward the full pipeline instead.
- `direct-run` chains `create` → `detail` → `completeness-apply` →
  `run --all --commit` → `reconcile-code`, committing the authoring
  artifacts and each green step as it goes. It needs a clean working
  tree to start.

#### Inspect

- `validate` is niche — it's a frontmatter-schema check only. Reach for
  `completeness-audit` for authoring audits, or `reconcile-plan` for
  plan-vs-code drift.
- `root` reports the repo root as resolved from where you're standing —
  its source and the manifest path — and flags it when that root isn't
  the current working directory.

### Placeholders

The angle-bracket placeholders above carry consistent meaning across
every subcommand:

| Placeholder | Meaning | Where it appears |
| --- | --- | --- |
| `<name>` | **Existing** registered plan, resolved by slug (`my-feature`), filename stem (`1-my-feature`), or filename (`my-feature.md`). Priority prefixes are tried automatically. | `status`, `validate`, `run`, `reconcile-plan`, `reconcile-plan-walk`, `verify-all`, `completeness-audit`, `completeness-apply`, `data-contract-apply`, `jira`, `detail` |
| `<slug>` | Canonical lowercase-dashes plan slug (no priority prefix, no `.md` suffix). Used when there's no other form to resolve from — either the plan doesn't exist yet, or the on-disk directory is keyed by slug. | `create <slug>`, `checkpoint clear <slug>`, `runs clear <slug>`, `--slug` filter on `runs list` / `runs profile` |
| `<slug>/<checkpoint>` | Checkpoint identifier. `<slug>` is the plan slug; `<checkpoint>` is the per-plan name shown in the `name` column of `plan-tool checkpoint list` (e.g. `detail-step-02`, `create-initial-steps`). | `checkpoint show` |
| `<slug>/<run_id>` | Run identifier. `<slug>` is the plan slug; `<run_id>` is the timestamp-derived id shown by `plan-tool runs list` (e.g. `2026-05-14T12-34-56-9f3a1c`). | `runs show`, `runs diff` |
| `<path>` | Filesystem path, absolute or repo-relative. | `register <path-or-slug>`, `create --from-existing <path>`, `annotate <path>`, `--output <path>` |

### `plan-tool detail`

Drafts per-step implementation markdown (Why / Files / Implementation /
Tests / Acceptance criteria / Deferred) and wires up the step's
`detail:` pointer automatically. Output is **a draft** — read and edit
it before running the step; the tool proposes, you decide.

This section is also where the global flags, the options shared by
every subcommand, and the interactive walk shortcuts live — not just
`detail` itself.

#### Global flags

These go before the subcommand, and apply no matter which one follows:

- `--version`: print the plan-tool version and exit. In a source checkout it
  reads `pyproject.toml`, so a version bump shows in an editable install
  without reinstalling; an installed wheel reads its package metadata
  ([`docs/RELEASING.md`](../RELEASING.md)).
- `--plans-dir <path>`: scan a directory for plans (overrides `PLAN_TOOL_PLANS_DIR`).
- `--manifest <path>`: use an explicit manifest JSON file in manifest mode.
- `--repo-root <path>`: pin the repo root explicitly (overrides
  `PLAN_TOOL_REPO_ROOT`). Use this when walk-up to `.git` finds the wrong
  directory — e.g. plan-tool's own folder is a nested git repo, the skill
  is installed somewhere other than `.agents/`, or the checkout has no
  `.git`.
- `--backend <name>`: pick the subprocess backend for all backend-invoking
  calls in this process. It overrides model-family inference and
  `PLAN_TOOL_BACKEND`; default `claude`.
- `--model <name>`: pick the model passed to the selected backend. Without an
  explicit `--backend`, OpenAI GPT/ChatGPT/o/Codex models select Codex, Claude models
  select Claude, and Gemini models select the provisional Gemini backend.
- `--on-rate-limit wait|switch|stop|ask`: choose the default response for an
  ordinary recoverable short rate limit (overrides `PLAN_TOOL_ON_RATE_LIMIT`;
  default `wait`). A confirmed terminal plan quota bypasses these actions.
  `switch` requires `--fallback-backend <name>` or `PLAN_TOOL_FALLBACK_BACKEND`.
- `--fallback-backend <name>`: backend to retry an ordinary rate-limited call
  with when `--on-rate-limit switch` is active (overrides
  `PLAN_TOOL_FALLBACK_BACKEND`).
- `--no-wait-on-rate-limit`: legacy alias for `--on-rate-limit stop`; do not
  combine it with `--on-rate-limit`.

If no overrides are provided, plan discovery uses `.plan-tool/plans.json`
and the repo root is resolved by walking upward from `cwd` to the nearest
ancestor containing a `.git` **or** a `.plan-tool` directory — so a
checkout with no git history, or whose plan root sits below the git
root, still resolves where the manifest lives. When neither marker is
found, it defaults to `cwd`. The override precedence is `--repo-root` →
`PLAN_TOOL_REPO_ROOT` → walk-up. Run `plan-tool root` to see what gets
resolved from the current directory; `create` warns and lets you keep
that root, switch to the current directory, or abort when the
discovered root isn't `cwd`.

#### Shared options

Available on every subcommand, passed after it.

`-y` / `--yes` — auto-accept confirmation prompts. Useful for
scripted / unattended / chat-driven runs (see
[Running headlessly](../../README.md#running-headlessly)).

- **Skips every Y/N gate:** the `create` split-proposal "save?" prompt,
  `reconcile-plan` / `detail --reconcile` "walk saved review instead?" prompts, the
  apply-finding "keep these changes?" prompt, and `jira config`'s
  epic-removal confirmation.
- **In walks** (`reconcile-plan`, `reconcile-plan-walk`, `detail --reconcile`):
  equivalent to typing `aa` (apply-all) at the first prompt — every
  remaining recommendation auto-applies and every apply-finding diff
  auto-keeps.
- **In `create`:** also default-accepts free-text wizard prompts
  (output dir, title, lessons path) — every prompt with a
  declared default resolves to that default. The interactive
  step-by-step fallback (when Claude can't propose parseable steps)
  is replaced with a fail-fast `CreateError`, so the wizard never
  spins against a no-input source.
- **Caveat:** free-text prompts without a default (epic name, plan
  path, etc.) still block on other subcommands.

#### Walk shortcuts

These apply during an interactive walk — `reconcile-plan`,
`reconcile-plan-walk`, or `detail --reconcile`:

- `aa` (or `apply-all` / `all`) at the per-recommendation prompt: apply
  this rec and auto-apply every remaining rec in the walk without
  re-prompting. Also silences the apply-finding "keep these changes?"
  confirmation for the rest of the session. Equivalent to retroactively
  enabling `--yes` mid-walk.
- `a` (or `all`) at the apply-finding "Keep these changes? [Y/n/a=all]"
  prompt: keep this diff and auto-keep every subsequent applied diff in
  the walk. Useful when you trust Claude's edits across the remaining
  findings and don't want to confirm each one.

## Modes

- **`run` (default)** — mutating. It executes a step and advances plan
  state on success. When the step declares a `change_type`, the prompt
  appends a test directive: both code types (refactor and feature) are
  asked for tests covering the behavior the step changes, green before it
  completes; non-code / unclassified steps get no directive. (The former
  per-type *ordering* contract was withdrawn 2026-07-30; see CLAUDE.md.) The post-flight
  `test_command` gate is unchanged. See
  [`PLAN_FORMAT.md`](../../PLAN_FORMAT.md) for the field.
- **Read-only modes** — render alternate prompts; they never modify plan
  state: `check`, `optimize`, `document`, `test`, `security`,
  `lint`.
- **Reconcile** — two subcommands:
  `plan-tool detail <name> --reconcile` (code-is-truth) and
  `plan-tool run <name> --reconcile` (plan-is-truth).
- **`--dry-run`** — renders the prompt and prints it without
  invoking Claude.
