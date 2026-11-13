# Iterating to convergence (`--iterate`)

*Back to [iteration guidance in the README](../README.md#iterating-to-convergence---iterate).*

`--iterate` turns a one-shot write into a loop: write → audit →
`apply-finding` (the step that edits the plan to close a finding) →
re-audit — and it keeps going until no new findings turn up or the
budget runs out.

**Why convergence matters.** Convergence isn't just a loop mode — it's
the plan's correctness signal. A plan that converges under audit →
apply is sound: the loop ran out of things to fix because there was
genuinely nothing left to fix.

A plan that *won't* converge is telling you something different. Watch
for these signs:

- the same region gets re-flagged every pass
- the finding count stops shrinking
- the body just keeps growing

That means the plan is the wrong **shape** — an over-packed step, two
concerns merged into one, a branch with no live scenario. `apply_finding`
only edits prose. It can fix under-specification, but it can never fix
over-complexity or a bad decomposition, so patching it again just grows
the plan and hands the next audit more surface to flag.

The fix is to **re-decompose** — re-split the step, or re-seed the plan
— not to patch it a fourth time. One gotcha to know about:
`no-blocking-findings` means "nothing left the loop may auto-touch," not
"sound." A plan whose remaining problems are all structural reports
converged prematurely.

See [RUNBOOK.md → When repeated audit/apply doesn't converge](../RUNBOOK.md#when-repeated-auditapply-doesnt-converge--re-decompose-dont-keep-patching).

## Choose an iteration route

| If you need to… | First command or action | Then read |
| --- | --- | --- |
| Let a supported authoring route converge | Add `--iterate` | [When to use `--iterate`](#when-to-use-iterate) |
| Check why a plan's structure is under pressure | `plan-tool split-criteria <name>` | [See a plan's split criteria](#see-a-plans-split-criteria-plan-tool-split-criteria) |
| Carve an over-packed step into follow-up work | `plan-tool scope-out <name> --step N` | [Carve an over-packed step out](#carve-an-over-packed-step-out-plan-tool-scope-out) |
| Understand why a loop stopped | Read the saved report and its terminal state | [How the loop terminates](#how-the-loop-terminates) |
| Run unattended within a bounded budget | Set the iteration flags deliberately | [Headless](#headless) |

## Carve an over-packed step out (`plan-tool scope-out`)

A step (or a contiguous band of steps) can keep re-flagging at high
severity and refuse to shrink under audit/apply. At that point,
re-splitting it a third time only backfires — carve it out of the plan
instead of patching again:

- `plan-tool scope-out <name> --step N` lifts the over-packed step into
  a `create --from-existing` forward-seed and narrows the plan, so the
  rest of the plan converges and the carved-out work gets re-planned on
  its own.
- **Recommend-only by default**: nothing changes until you pass
  `--apply` plus confirm at a TTY prompt (an interactive terminal — `-y`
  is the deliberate non-interactive opt-in for scripts). It is also
  **seed-first** — the forward-seed lands in `plan-seeds/` before the
  plan is narrowed — and it spends no claude.
- `plan-tool convergence <name>` won't recommend or trigger this carve
  for you. It's a read-only loop/structure signal — you pick the step
  (or range) yourself.

See [RUNBOOK.md → Carve an over-packed step out of a plan](../RUNBOOK.md#carve-an-over-packed-step-out-of-a-plan-plan-tool-scope-out)
for the full gate: the four refusal blockers, the seed-first ordering,
and the post-carve history caveat.

## See a plan's split criteria (`plan-tool split-criteria`)

`plan-tool split-criteria [<name>]` answers "why is this plan shaped
this way?" It shows the structural-split axis the tool reasons over —
the read-only companion to `plan-tool convergence`. It has two modes:

- **No argument** → the plan-independent **legend**: every split
  criterion the tool applies, across all three altitudes, plus the
  remedy vocabulary (re-split / scope-out / merge / re-seed).
- **A plan argument** → the per-plan **breakdown**: which criteria fire
  for that plan, on which steps, each with a one-line reason.

Like `plan-tool convergence` and `plan-tool status`, this is a
read-only "tell me the state" diagnostic. It spends no claude, mutates
nothing, writes no run-log entry, and always exits 0.

## Defaults

These are the knobs that keep an unattended apply-loop bounded — set
them once, and the loop runs itself within the fence you drew.

| Flag | Default | Source | Effect |
| --- | --- | --- | --- |
| `--iterate` / `--no-iterate` | `create`: `--iterate` (on). `detail`, `completeness-audit`: `--no-iterate` (off). | `BooleanOptionalAction` + per-subparser `default=True` on `create`, `default=False` on `detail` | Master switch. Off ⇒ `IterativeBudget(enabled=False)` ⇒ `should_continue` short-circuits with `"disabled"` on the first call. |
| `--max-iterations N` | `3` | `convergence.DEFAULT_MAX_ITERATIONS` | Maximum iterations after the initial write. `--max-iterations 0` is rejected by `_resolve_iterative_budget`. |
| `--iteration-budget SECONDS` | `1800` | `convergence.DEFAULT_ITERATION_BUDGET_SECONDS` | Debounced no-progress deadline: fires only after SECONDS pass with zero forward progress. It resets on every round and every `apply_finding` call, so a single 15-20+ minute claude call never trips it — this is not a cap on total loop wall-clock (see `--time-budget` for that). |
| `--time-budget SECONDS` | off (`0`); falls back to `PLAN_TOOL_TIME_BUDGET` | `convergence.IterativeBudget.hard_budget_seconds` | Cooperative total-elapsed cap: stops the loop at the next round boundary once SECONDS of total command time pass, even while still converging, and exits 0 with a resume hint. Shared across `detail` steps; it does not interrupt a model call in flight. Ignored under `--no-iterate`. |
| `--max-stall-rounds N` | `2` | `convergence.DEFAULT_MAX_STALL_ROUNDS` | Stop after N consecutive rounds whose open-finding **count** doesn't shrink. It's an ID-agnostic backstop for a subjective audit that re-phrases the same findings each round (fresh ids would otherwise defeat the `marginal` / `converged` checks). `0` disables. |

- **On by default:** `create`. Pass `--no-iterate` to skip the
  post-write loop.
- **Off by default:** `detail` and `completeness-audit`. Pass `--iterate`
  explicitly for completeness audits. Keep detail authoring one-shot unless
  the user explicitly requests its quality loop.
- **Reconciliation:** neither `detail --reconcile` nor `run --reconcile`
  supports `--iterate`; both reject it with exit 2. Detail reconciliation
  also rejects `--no-iterate`. Standalone `reconcile-plan` and `reconcile-code`
  do not accept iteration flags. Use saved reports and session-directed
  corrections followed by a new invocation. Plan-side reconciliation is
  pre-execution only; after execution, keep the plan canonical with
  `reconcile-code`.
- **Other unsupported routes:** `annotate`, `verify-all`.
  `annotate --iterate` exits 2 before writing anything, because
  `annotate` is a single classification pass plus deterministic
  renderers, not a loop. The convergence step happens on the next run:
  `create --from-existing <seed> --iterate`.

## When to use `--iterate`

### Reach for `--iterate` when

- You're authoring a brand-new plan with `create` and want the
  deterministic completeness primitives (body sections, detail
  coverage, references) to drive 2–3 author-fix-reaudit passes before
  you hand it to a developer.
- You explicitly request iterative detail authoring with `detail` and want the
  `detail-quality.md` review to drive 2–3 quality revisions on the
  just-written body — citations tightened, vague prose pinned to real
  line ranges, generic bullets replaced with code-checkable ones.
- You want supported deterministic authoring fixes to run headlessly
  (`-y < /dev/null`). Conceptual audit gaps still need session-directed
  judgment; headless mode does not turn them into automatic applies.

### Skip `--iterate` when

- You only want a report: use `verify-all`, or pre-execution
  `reconcile-plan --no-walk` to save findings without applying them.
  (`completeness-audit --iterate` converges only its deterministic findings
  and leaves conceptual gaps for session-directed edits.)
- You're debugging a claude regression and need iteration-1 state to
  inspect before iteration 2 overwrites it. Pass `--no-iterate`
  explicitly for `create`, where omitting the flag opts you INTO the
  loop. `detail` already writes once unless you pass `--iterate`.
- You're in CI with a hard wall-clock cap and one extra claude call per
  iteration is too expensive (or pass `--max-iterations 1` for exactly
  one pass — see tiebreakers below).
- You want a single authoring pass: use `create --no-iterate` or plain
  `detail`. Do not add iteration flags to reconciliation commands.

**Tiebreakers:**

- **`--max-iterations 1` is *not* the same as `--no-iterate`.** Both
  stop after one claude apply pass, but `--no-iterate` short-circuits
  the loop entirely — no `apply-finding` call at all, no deterministic
  re-audit. `--max-iterations 1` runs the loop once: write → audit →
  apply once → stop. Choose `--no-iterate` for "I want the old
  behavior"; choose `--max-iterations 1` for "I want exactly one fix
  pass."
- **Per-step vs. per-plan scope.** `detail`'s budget is *per step* (the
  loop wraps each detail-file write independently). `create`'s budget
  is *per plan* (one loop around the post-`write_new_plan` reaudit).
  When you iterate across multiple steps with `detail` (no `--step`
  argument), each step gets its own fresh iteration and no-progress budget —
  one step exhausting its budget doesn't block the next. `--time-budget` is
  shared across the whole command.

## How the loop terminates

- **Converged.** `finding_set_delta` returns an empty introduced-set.
  Exit code 0.
- **Budget exhausted.** The iteration count hit `--max-iterations`, no
  forward progress was made for `--iteration-budget` seconds (a debounced
  no-progress deadline, not a cap on total time; `--time-budget` is the total
  cap), or `--time-budget` was reached. Exit code 0 — the loop
  completed; any findings still open are in the report (and, for
  `completeness-audit --json`, the `has_blocking_findings` flag), which CI /
  aggregation scripts inspect instead of the exit code. For
  `completeness-audit`, add `--fail-on-findings` to turn "budget exhausted
  with medium+ findings still open" into a non-zero exit a CI step can
  gate on.
- **Marginal stagnation.** Iteration N introduced no *new* findings
  relative to iteration N-1 (the intersection equals the prior set).
  The loop halts cleanly with exit code 0 — it's making no further
  progress, but the artifact is no worse than the prior iteration.

## Checkpoint interaction

`create` includes the iteration index in
`_initial_steps_input_hash` / `_references_input_hash` — so iteration
N+1's claude call is **not** served the cached body from iteration N
when you resume. Each completed iteration's payload caches at its own
slot, and a resumed run replays them in order.

`detail` does *not* extend its hash keys. `detail` relies on `apply_finding` mutating the file
in place between iterations, and `run` doesn't go through the
checkpoint module at all. When you resume an interrupted `create
--iterate` run, the cache replays each completed iteration; only the
in-flight iteration re-invokes claude.

## Headless

See [Iterating headlessly](OPERATIONS.md#iterating-headlessly) for the
full `-y` × `--iterate` interaction: the `apply-all` default, and how a
completed loop exits 0 with any open findings still carried in the
report for CI gates to inspect.

## Operational recipes

See [RUNBOOK.md → Workflow: drive an authoring task to convergence](../RUNBOOK.md#workflow-drive-an-authoring-task-to-convergence---iterate)
for end-to-end recipes against each subcommand.
