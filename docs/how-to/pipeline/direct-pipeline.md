# Direct pipeline verbs — `direct-jira` / `direct-run`

This document maps the design of the two **direct pipeline** verbs, which chain
the existing pipeline stages in one process instead of leaving them as separate
CLI invocations:

- **`direct-jira`** = `create → detail → jira`.
- **`direct-run`** = `create → detail → run --commit → reconcile-code`.

Both verbs **reuse the existing stage handlers** rather than reimplementing any
stage; the direct verbs are only the glue that threads one stage's result into
the next. Source-of-truth references are inline. This is the internal design
note — operator-facing catalog entries (README, `CAPABILITIES.md`,
`docs/how-to/use-cases.md`) live elsewhere.

## TL;DR

- The verbs live in a thin CLI leaf, `plan_tool/cli/direct_cmd.py` (created by
  **step 3**, extended for `direct-run` by **steps 4–5**, registered by
  **step 6**). It sits beside the sibling intent-group modules
  `plan_tool/cli/authoring.py`, `plan_tool/cli/run_cmd.py`, and
  `plan_tool/cli/jira_cmd.py`, and follows the same thin-handler pattern:
  wire args to the reused orchestrators, hold no business logic.
- **The key design decision is the namespace-sink hand-off.** Each stage
  today re-discovers the `create` result on disk; the direct verbs instead
  thread `create`'s in-process `CreateResult` straight into the next stage,
  with no disk round-trip. **Step 2** teaches `cmd_create` to write its result
  to a caller-supplied namespace sink; this doc describes the seam.
- A deterministic **size gate** (helper added by **step 3**) inspects the
  create result and stops — spending no Claude — when the plan is too large to
  chain safely, rather than silently one-shotting an over-large concept. The
  override is `-y` / non-TTY / `--force`, per the plan's size-gate decision.
- **Cross-cutting flags and the exit-code convention carry through each stage
  unchanged.** `--backend`, `--model`, and `--on-rate-limit` thread the same
  args namespace into the same handlers and the same invoker seam every stage
  already uses; a mid-chain failure surfaces that stage's standard non-zero
  exit with no chain-level rollback.
- **`direct-jira` ends in the normal paired Jira export.** Its terminal outputs
  are the regenerated story source and provenance-stamped developer handoff;
  they are not folded into the authoring commits made earlier in the chain.

## High-level flow

```
        plan-tool direct-jira <slug> ...        plan-tool direct-run <slug> ...
                    |                                        |
                    v                                        v
   cmd_direct_jira (step 4/6)                cmd_direct_run (step 5/6)
   [plan_tool/cli/direct_cmd.py]             [plan_tool/cli/direct_cmd.py]
                    |                                        |
                    +--------------------+-------------------+
                                         |
                                         v
            cmd_create (plan_tool/cli/authoring.py) with the args
            namespace carrying the optional sink attribute (step 2)
                                         |
                            create_plan (plan_tool/create.py)
                                         |
                                         v
                      CreateResult written back to the sink
                      (in-process; no disk re-discovery)
                                         |
                                         v
                    +-------- deterministic size gate --------+
                    | too large to chain safely?              |
                    |   yes -> stop, no Claude spent          |
                    |         (override: -y / non-TTY /        |
                    |          --force)                        |
                    |   no  -> continue                        |
                    +----+------------------------------+------+
                         |                              |
                (single-plan path)          (CreateResult.plan_path is None:
                         |                    multi-plan split short-circuit)
                         v                              |
              detail stage (reused handler)             v
                         |                    stop — no plan to chain
          +--------------+--------------+
          | direct-jira  | direct-run   |
          v              v
     jira stage     run --commit stage
     (reused)            |
                         v
                cmd_reconcile_code
                (plan_tool/cli/run_cmd.py) loop
```

## The namespace-sink hand-off

The direct verbs' central design decision is how `create`'s result reaches the
next stage. Standalone, each stage re-discovers the create result from disk (the
plan file and its manifest entry). The direct verbs instead thread the result
**in-process**, avoiding a disk round-trip and a re-parse between stages.

**The objects involved:**

- `cmd_create` in `plan_tool/cli/authoring.py` — the create stage's CLI handler.
- The `create_plan` call it makes (`plan_tool/create.py`) — the orchestrator
  that does the work.
- The `CreateResult` dataclass in `plan_tool/create.py` — the object handed off.
  It already carries `plan_path`, `split_proposal`, `distilled_seed`, and the
  collision / provenance fields, so the direct verb receives everything the next
  stage needs without touching disk.

**The rule the sink obeys.** The sink is an **optional attribute on the args
`Namespace`**. When present, `cmd_create` writes its `CreateResult` to it; when
absent, `cmd_create` behaves exactly as when run standalone — the standalone
CLI-entry contract is unchanged, and the mechanism is invisible to every caller
that does not set the attribute. **Step 2** owns this change to `cmd_create`;
this doc only describes the seam.

**Why a sink, not a changed return type.** Threading the result through an
optional namespace attribute leaves `cmd_create`'s existing return type (its
process exit code) untouched, so no existing caller — CLI entry, tests, or other
handlers — sees a different contract. Changing the return type would ripple to
every call site; the sink ripples to none.

**The `plan_path is None` case.** `CreateResult.plan_path` is `None` **only** on
the multi-plan split short-circuit — when the distill first-pass determines the
seed describes several independent plans, `create_plan` returns a split proposal
and writes no plan (see
[CREATE_FROM_EXISTING_FLOW.md](create-from-existing.md)). The direct verbs
must handle that case: there is no plan to chain, so they stop after the create
stage rather than feeding a `None` path into detail.

## The size gate

Before chaining past `create`, the direct verbs run a **deterministic** size
gate over the `CreateResult`. It flags a plan too large to chain safely, spends
**no Claude**, and stops with an explicit message instead of silently
one-shotting an over-large concept through the remaining stages. The gate helper
is added by **step 3** in `plan_tool/cli/direct_cmd.py`.

The gate **reuses existing detectors** rather than inventing new heuristics. Its
design intent keys off deterministic signals already in the codebase:

- a small **step-count cap** on the created plan;
- `granularity-split` findings from
  `plan_tool/granularity.py:assess_granularity` (a step too big / mixing
  concerns); and
- `create`'s multi-plan `SplitProposal` path
  (`plan_tool/cli/authoring.py:_emit_split_proposal`), which already signals
  that a seed spans several plans.

The override is `-y` / non-TTY / `--force`, matching the plan's size-gate
decision: an operator who has seen the size and still wants to chain can force
past it, and headless runs are not silently blocked.

## Cross-cutting flags and exit codes

The direct verbs do **not** re-interpret cross-cutting behavior — they pass it
straight through:

- **Backend / model / rate-limit.** `--backend`, `--model`, and
  `--on-rate-limit` (and the resolved rate-limit policy) thread the same args
  namespace into the same handlers and the same invoker seam that every stage
  already uses. No stage sees a different backend when driven from a direct
  verb than it would standalone.
- **Exit codes.** The chain preserves the project's convention: subcommands exit
  non-zero only on failure-to-complete, never on findings or verdicts. A
  mid-chain stage failure surfaces **that stage's** standard non-zero exit, and
  there is **no chain-level rollback** — the stages that already completed keep
  their on-disk effects (the created plan, the committed run steps).

## The reconcile-code tail (`direct-run`)

`direct-run`'s final stage is the reconcile-code loop. After the `run --commit`
stage runs the plan step by step (committing each green step — see
[RUN_FLOW.md](run.md) for the run stage's own gates), the loop drives
`plan_tool/cli/run_cmd.py:cmd_reconcile_code` to land the plan-canonical edits
the code still needs to fully cover the plan. The `run --commit` step precedes
`cmd_reconcile_code`; this doc stays about the *chain* and cites
[RUN_FLOW.md](run.md) for the run stage's internals rather than restating
them.

## Related flow docs

Each chained stage has its own owning flow doc, cited here for its internals:

- [CREATE_FROM_EXISTING_FLOW.md](create-from-existing.md) — the create
  stage, including the distill first-pass and the multi-plan split short-circuit
  that leaves `plan_path` as `None`.
- [DETAIL_FLOW.md](detail.md) — the detail stage.
- [RUN_FLOW.md](run.md) — the `run --commit` stage's gates and the
  reconcile-code tail's mechanics.
- [AUDIT_FLOW.md](audit.md) — the audit machinery the pipeline stages share.

## Source map

| Concern                                | Where                                                    |
|----------------------------------------|----------------------------------------------------------|
| Direct-verb CLI leaf                   | `plan_tool/cli/direct_cmd.py` (step 3; steps 4–5 extend)  |
| Verb registration                      | step 6 (registers `direct-jira` / `direct-run`)           |
| Namespace sink on the create handler   | `cmd_create` in `plan_tool/cli/authoring.py` (step 2)     |
| Create orchestrator                    | `create_plan` in `plan_tool/create.py`                    |
| Handed-off result object               | `CreateResult` in `plan_tool/create.py`                   |
| Size-gate helper                       | `plan_tool/cli/direct_cmd.py` (step 3)                     |
| Size-gate detectors reused             | `plan_tool/granularity.py:assess_granularity`; `plan_tool/cli/authoring.py:_emit_split_proposal` |
| Reconcile-code tail (`direct-run`)     | `cmd_reconcile_code` in `plan_tool/cli/run_cmd.py`        |
| Sibling intent-group leaves            | `plan_tool/cli/authoring.py`, `plan_tool/cli/run_cmd.py`, `plan_tool/cli/jira_cmd.py` |
