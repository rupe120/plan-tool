# Gates and reconcile

*Back to [correctness gates in the README](../README.md#correctness-gates).*

What stops a bad step before it lands, how each command reconciles a plan
with the code — in the right direction — and what the completeness audit
checks. For which gates fire on every run, see [`RUN_FLOW.md`](how-to/pipeline/run.md).

## Choose a check or reconcile route

| If you need to… | First command | Then read |
| --- | --- | --- |
| Stop an invalid plan step before or after execution | `plan-tool run <name>` | [Correctness gates](#correctness-gates) |
| Check an authored plan's design and detail coverage | `plan-tool completeness-audit <name> --iterate` | [Completeness gates](#completeness-gates) |
| Re-ground an unexecuted plan after code has changed | `plan-tool reconcile-plan <name>` | [Per-subcommand reconcile](#per-subcommand-reconcile) |
| Reconcile delivered code to an executed plan | `plan-tool reconcile-code <name> --all` | [Per-subcommand reconcile](#per-subcommand-reconcile) |
| Verify completed work in CI | `plan-tool verify-all --rollup <name>` | [Correctness gates](#correctness-gates) |

## Correctness gates

A correctness gate is what stops a bad step, or a malformed response, before
it does any damage. They live as shared validation primitives in
`review.py`, and every claude-invoking subcommand runs them. With
`--iterate` on, `create`, explicitly requested detail authoring, and
`completeness-audit` loop their supported gates. Reconciliation uses separate
invocations, without `--iterate`. Each authoring loop
runs the checks, hands any findings to `apply-finding`, and re-audits — see
[Iterating to convergence](ITERATION.md).

- **`run` pre-flight** — checks paths before claude is even invoked, in
  every mode, including read-only review modes. It refuses to continue on
  any `MISSING_PARENT` path or a plan-wide path-style mismatch. This one
  bites people whose step legitimately creates files under a brand-new
  directory — pass `--allow-missing-parent` for that case, and the check
  steps aside.
- **`run` post-flight** — checks the other direction, after the call, and
  only in mutating mode. It warns if the response is missing a `## Summary`
  section (the plan still advances), and it **blocks** when none of the
  step's declared files changed content: the step exits 1 as "no edits
  applied" and is not advanced. A step that declares no files is exempt.
- **Review-mode result summarization** — every review prompt (`check`,
  `reconcile-plan`, `optimize`, `document`, `test`, `security`, `lint`) has
  to answer with a `## Findings` block tagged by severity: `CRITICAL`,
  `HIGH`, `MEDIUM`, or `NIT`. `run --mode <review>` and `verify-all` print a
  verdict line per step. Here's the part that trips people up: a completed
  audit exits 0 even when it found critical problems — the verdict lines
  carry the result, not the exit code. Need CI to fail on a critical
  finding? Pass `--fail-on-findings` to `verify-all` and it will exit
  non-zero instead.
- **`jira` parser hardening** — validates the stories claude proposes for a
  jira export. It requires:
  - a positive `estimate_hours` on every story (an advisory size —
    `--max-hours` is a soft target, not a hard cap);
  - unique `S<N>` ids;
  - `depends_on` references that resolve within the same response; and
  - full plan-step coverage — every plan step has to show up in at least
    one story's `steps`.

  A missing file path only gets a soft warning on stderr, not a rejection —
  claude may have a genuine reason to propose a new file.
- **`detail` response gate** — every detail file needs all seven mandatory
  H2 sections (that's shorthand for a `##`-level markdown heading):
  Summary, Table of Contents, Why, Files, Implementation, Tests, and
  Acceptance criteria. It also warns when fewer than half of the step's
  `step.files` get mentioned in the body. Summary and Table of Contents
  exist for the human reviewer, not the tool — they let you get your
  bearings before diving into the implementation walkthrough.
- **`create` hardening** — three checks around plan creation:
  - it re-parses the plan it just wrote from disk before reporting
    success;
  - it validates that the lessons path lives inside the repo root; and
  - when the source is file-backed, it always routes through preflight, a
    direct assessment, or one visible preparation result — never a
    size-based fallback to the raw source.
- **`plan-tool verify-all --rollup <name>`** — runs the reconcile prompt
  across every `done` step and rolls the result up into one `[OK]`,
  `[WARN]`, or `[FAIL]` line per step (plain `verify-all` just dumps the
  raw output instead). If there are no done steps yet, it prints
  `nothing to verify` and exits 0.

The two lists below are follow-ups the shipped work explicitly deferred —
they live in the **Deferred** sections of the progress-reporting work and
the correctness-checks plan, and neither was in scope for the initial
implementation.

### Progress reporter (shipped, follow-ups deferred)

- `--quiet` / `--no-progress` flag for the progress reporter.
- `PLAN_TOOL_HEARTBEAT_SECONDS` env var to tune the tick interval; TTY
  detection for overwrite-in-place output; adaptive heartbeat cadence.
- Aggregate `Total: M/M done in Xs` summary line at end of multi-step
  runs.

### Correctness checks (shipped, follow-ups deferred)

- A `--strict-post-flight` flag that promotes `run` post-flight warnings
  to errors.
- `plan-tool doctor` — a unified pre-everything gate that runs every
  correctness check at once.
- Auto-fix suggestions for jira stories that aren't atomic PRs — for
  example, proposing a consolidation or an independently-shippable split.
- Cross-step coherence checks — e.g. step 3 deletes a symbol that step
  7's review still references. Sequential per-step audits remain the
  design.
- Backporting `verify-all` failures into plan state — e.g. flipping a
  `done` step back to `pending` on reconcile failure. Output stays
  read-only; mutating done state is reserved for the user.

## Per-subcommand reconcile

Reconcile splits along the **direction of truth**: which side — the plan
or the code — gets treated as correct. The subcommand *is* the direction
declaration — no per-finding gate, no runtime allow-list. Each side has
its own prompt, persistence kind, and apply path.

| Subcommand | Truth source | Findings produce | Persistence kind |
| --- | --- | --- | --- |
| `plan-tool detail <name> --reconcile` | Code on disk | Plan / detail edits (`step.files`, status flips, body updates) | `detail-reconcile` |
| `plan-tool reconcile-code <name>` (legacy: `run --reconcile`) | Plan | Code edits (inline via Claude Edit/Write under `--permission-mode acceptEdits`) | `run-reconcile` |

Persistence path:
`<plan-dir>/plan-details/<plan-slug>/reports/<ts>-<kind>.json`.

### `plan-tool detail <name> --reconcile` — code-is-truth

```bash
plan-tool detail my-feature --reconcile --step 3
plan-tool detail my-feature --reconcile --all
```

The prompt behind this is `prompts/detail-reconcile.md`. The walk — that's
plan-tool's term for stepping through findings one at a time — dispatches
each finding through `apply_finding` (the same helper that backs
`plan-tool review`).

`--all` sweeps the per-step audit across every step **not yet `done`** —
one claude call per step — and is mutually exclusive with `--step`. A few
things worth knowing about the sweep:

- Done steps are skipped by design: their detail files are historical
  records of delivered work, so re-auditing them against code that has
  since moved on produces churn, not signal. The valuable targets are the
  remaining steps, whose details may have drifted from the evolving
  codebase before they execute.
- The plan is re-parsed between steps, so a step that flips to `done`
  mid-sweep gets skipped too.
- The sweep halts on the first per-step failure and passes that exit code
  along.
- Unlike `run --all`, `-y` is **not** implied. On a TTY you walk each
  step's findings interactively — pass `-y` yourself for unattended,
  apply-everything runs.

### `plan-tool reconcile-code <name>` — plan-is-truth

The code-side counterpart to `reconcile-plan`. You'll also see it written
as `run --reconcile` — that's the legacy form, and it still works.

```bash
plan-tool reconcile-code my-feature --step 3
plan-tool reconcile-code my-feature --all
```

The prompt is `prompts/run-reconcile.md`. There's no walk here — code
edits land inline as the audit runs.

`--all` sweeps every plan step in order, including `done` steps, skipping
only steps declared explicit `non-code`, and stops at the first step whose
audit fails to *complete* — that's different from finding a problem: a
redirect or a critical finding does not halt the sweep, so read each
step's printed verdict rather than trusting the exit status alone. It's
mutually exclusive with `--step` and with `--reuse-id` — a pinned save
can't mean anything sensible across every step.

### The `## Redirect` sub-block

When `run --reconcile` turns up a finding whose root cause is actually in
the plan, not the code, claude doesn't force a code edit. Instead it emits
a per-finding `## Redirect` sub-block:

- CLI parses the redirect (`review.py: parse_redirect_block`).
- Surfaces it on stderr as `[REDIRECT] step N — see detail --reconcile`.
- The audit exits 0 whether or not a redirect was emitted — act on the
  `[REDIRECT]` line, not the exit code.

The mirror holds for `detail --reconcile`: a finding rooted in the code is
the wrong subcommand for it — switch to `run --reconcile`.

## Completeness gates

Correctness gates check *structural* well-formedness — paths, dependencies,
response shapes. Completeness gates check *coverage* — is anything
missing? Both apply on three axes, distinguished by what is compared
against what:

- **Coverage** (`detail`) — does the plan cover the existing code?
  (plan ⊇ code)
- **Fulfillment** (`run` / `verify-all`) — do the code changes cover the
  plan? (code ⊇ plan)
- **Conceptual** (`completeness-audit`) — are the plan's own concepts correct
  and complete, grounded in the per-step detail bundle and the code at
  HEAD? (plan ⊨ its own problem)

Within each axis there are two layers:

- **Deterministic** — no claude calls (path/dep/section/coverage
  checks).
- **Semantic** — claude calls. `completeness-audit` samples the conceptual
  audit until findings run dry (typically 2-3 calls; tune with
  `--audit-samples` / `--audit-dry-rounds`); `reconcile-plan` and
  `verify-all` make theirs per the table below. Under `--iterate`,
  `create`, `detail`, and `completeness-audit` re-audit until
  findings converge. See [Iterating to convergence](ITERATION.md).

The audit verbs split by lifecycle phase:

| Verb | When | Asks | Claude? |
| --- | --- | --- | --- |
| `completeness-audit` | Pre-handoff | Deterministic: any authoring gaps (sections, detail files, lessons)? Then a conceptual audit: are the plan's own concepts correct and complete, grounded in the detail bundle + code at HEAD? | Yes (sampled until dry, typically 2-3 calls — the conceptual audit) |
| `reconcile-plan` | Stale plans / supplement | Does the plan still match code that may have drifted since it was written? | Yes (one call) |
| `verify-all` | Post-implementation | Did each done step actually do what it claimed? | Yes (one call per done step) |
| `verify --deep` | Post-implementation | Does each acceptance bullet on each done step hold? | Yes (one call per bullet) |

`validate` checks frontmatter schema only — it's niche, since every other
subcommand already re-validates on load.

Findings produced by these checks:

- **Body section completeness** — flags a required H2 section that's
  either missing or still just a `_(TODO)_` placeholder. The required
  sections: Overview, Problem statement, Architecture, Steps, Out of
  scope, Risks, Testing, Acceptance criteria, and Deferred. To suppress
  the check for one section on purpose, add
  `<!-- completeness:skip <Section> -->` inside that section's body.
- **Detail file coverage** — two checks, both skipped once a step is
  `done` (a detail file's job is briefing the work before it happens,
  which is moot once the step is implemented):
  - a step with no `step.detail` set at all is `info`-severity, unless
    it's a pure-analysis step with empty `files:` and low or null
    complexity — those are exempt;
  - a step that declares a detail file but the file is actually missing
    is `medium`-severity.
- **Detail body completeness** — for every detail file on disk, the same
  seven required H2 sections (Summary, Table of Contents, Why, Files,
  Implementation, Tests, Acceptance criteria) must exist with real,
  non-placeholder content. Summary and Table of Contents are there for
  the reviewer, not the tool — they let a person auditing the file get
  oriented before reading the implementation walkthrough. Skipped for
  `done` steps: a thin detail body is a pre-execution authoring gap, and
  it's moot once the step is implemented.
- **Files coherence** — checks for drift between the paths a detail body
  cites in backticks and the step's recognized path set
  (`step.files ∪ step.allowed_mentions`). Skipped for `done` steps —
  coherence is a pre-execution authoring signal, and code-vs-plan
  divergence on an implemented step is the semantic review's and
  `verify-all`'s job instead.

  A detail body legitimately cites plenty of *context* files — ones it
  reads but doesn't edit — so the check only flags (`info`) a cited path
  that **looks like a near-miss of a declared path**:
  - the same basename in a different directory (the canonical
    `packages/web/Foo.tsx` declared vs `apps/web/src/Foo.tsx` cited is
    drift), or
  - a near-identical full path — a typo in the basename.

  An ubiquitous basename (`index.ts`, `__init__.py`, …) doesn't match on
  name alone. A citation bearing no resemblance to a declared path is
  treated as a context reference and produces **no finding**. A genuine
  near-miss that's actually an intentional citation can be endorsed by
  adding the path to the step's `allowed_mentions:` list. The reverse
  case — `files:` declares a path the detail body doesn't mention — is a
  `nit`. Neither severity fails `plan-tool completeness-audit`; both are
  advisory.
- **Lessons coverage** — when `plan.lessons` is set, every `done` step
  should have an entry naming `step <id>:` in the log. A missing log file
  or missing entries both surface as warnings.
- **Test-strategy alignment** (`test-strategy` findings) — emitted only
  when some steps declare `change_type`; a plan with no classified steps
  produces none of them. See
  [`PLAN_FORMAT.md`](../PLAN_FORMAT.md#field-semantics) for the
  classification. Two checks:
  - a plan-level `info` nudge when some steps are classified and
    siblings aren't;
  - a per-step `medium` when a `non-code` step's `files`/`creates`
    include a production source path.

  The sampled `plan-audit` adds a **purity probe** on top, flagging a
  code step that mixes behavior-preserving restructuring with new
  behavior in the same step (docs/config riding along is not mixing; the
  fix is splitting it into type-pure steps). All of these render as
  advisory structural diagnostics.
- **`plan-tool completeness-audit <name>`** — aggregates the five
  deterministic checks above plus a conceptual audit into a single
  grouped report.

  The conceptual audit (`prompts/plan-audit.md`) samples until findings
  run dry and unions the results by stable anchor id — a finding's
  persistent identifier, so the same issue turning up across multiple
  samples merges into one entry (`--audit-samples` /
  `--audit-dry-rounds`). It reads the plan grounded in the per-step
  detail bundle, and may also Read/Grep the repo at HEAD — which is how
  it avoids re-flagging a gap a detail file already specifies. It emits
  two finding lists: *correctness* (unsound or contradictory concepts)
  and *completeness* (orphaned concepts, uncovered risks, dangling
  acceptance criteria, missing edge cases).

  `--json` emits a CI-friendly object with a `plan_audit` array, each
  entry tagged `axis: correctness|completeness`. In the ordinary
  (non-JSON) report, correctness findings — deterministic (path-style,
  dep validation) and conceptual alike — render under a "Correctness (run
  these first)" header above the completeness groups, so you always see
  blockers ahead of coverage gaps. The conceptual coverage findings
  render under "Conceptual completeness".

  Every non-JSON ordinary final run writes a markdown report to
  `plan-details/<slug>/reports/<ts>-completeness.md` and a structured
  sidecar `plan-details/<slug>/reports/<ts>-completeness.json` for review and reuse. One exception: a non-JSON terminal
  Cursor plan-quota stop still saves the readable markdown report, but
  withholds that reusable final findings sidecar — resolve the provider
  condition and run a fresh audit to get one.

  Under `--iterate` the terminal shows only a concise summary plus the
  report path; the conceptual-completeness gaps are advisory inside the
  audit's iterate loop (chasing every new gap would never converge), and
  the report explains how to address them through judged edits and re-audit.
  Read the saved report, verify and judge the findings, edit the appropriate plan or detail text, commit bounded corrections, and re-run `completeness-audit --iterate --commit` against the changed snapshot.

- **`plan-tool data-contract-apply <name>`** — also paired with
  `completeness-audit`, but scoped to saved `DATA_CONTRACT.md` drift. It
  walks only fresh structured `data-contract` payloads saved by the
  audit, annotates the same saved-review sidecar, and leaves conceptual
  gaps for judged edits. Stale payload fingerprints require a
  fresh audit before applying.
- **`plan-tool verify-all --rollup <name> --deep`** — extends
  `verify-all` with a per-acceptance-bullet check. For each done step, it
  parses the detail file's `## Acceptance criteria` bullets and asks
  claude to verify each one individually via `prompts/reconcile-deep.md`.
  The per-step rollup then follows a simple rule: any FAIL rolls up to
  fail; a mix of PASS and UNKNOWN rolls up to warn; all PASS rolls up to
  pass.

### Completeness gates (shipped, follow-ups deferred)

- `plan-tool plans-doctor` — cross-plan rollup of completeness
  findings across the whole manifest.
- `validate --strict-body` — promote body-completeness warnings to
  errors. Today they're advisory only.
- Auto-fill of missing sections via claude.
- Suppression markers for non-body completeness checks (the
  body-section skip marker is the only one today).
- Backporting `verify --deep` results into plan state.
