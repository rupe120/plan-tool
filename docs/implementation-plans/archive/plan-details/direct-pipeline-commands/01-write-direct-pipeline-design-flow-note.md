> **Auto-archived**: this plan was swept on 2026-07-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Write the direct-pipeline design and flow note

## Summary

This step creates one new doc, `docs/DIRECT_PIPELINE_FLOW.md`, that maps the two direct pipeline verbs the plan adds — `direct-jira` (chains `create → detail → jira`) and `direct-run` (chains `create → detail → run --commit → reconcile-code`). It is a **non-code** step: it writes no production code and edits no existing file. The most important thing the doc pins down is the **namespace-sink hand-off** — how `cmd_create` hands its `CreateResult` back to the direct verb in-process so the next stage acts on it without a disk round-trip — plus the deterministic **size gate** and how cross-cutting flags and exit codes carry through each chained stage. On green, the doc exists, its internal and cross-doc links resolve, and its symbol references match HEAD (or name later steps by id for symbols they create).

## Table of Contents

- [Summary](#summary) — what the step ships and the observable result on green.
- [Why](#why) — why the pipeline's composition needs to live in a doc, not shell history.
- [Files (creates vs edits)](#files-creates-vs-edits) — the single new doc; no edits.
- [Implementation](#implementation) — what the doc must cover and the anchors it should cite.
- [Tests](#tests) — this is a non-code step; verification instead of unit tests.
- [Acceptance criteria](#acceptance-criteria) — checkable facts about the doc.
- [References](#references) — the plan-level links relevant to this doc.
- [Deferred](#deferred) — what the doc does not cover.

## Why

The pipeline stages exist only as separate CLI invocations (`create`, then `detail`, then `jira` or `run --commit`). The plan adds two verbs that chain them in one process, and that chaining introduces a new seam — the in-process `CreateResult` hand-off — plus a size gate and flag/exit-code threading rules that a reader can't infer from any single stage's handler. The rest of the plan's flows already carry a doc each (`docs/CREATE_FROM_EXISTING_FLOW.md`, `docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, `docs/AUDIT_FLOW.md`); the direct verbs need the same so the chained design is written down where reviewers and future agents find it. This step lands that doc first (every other step lists it as `depends_on: 1`) so the later code steps have a design note to build against.

## Files (creates vs edits)

- **New files:**
  - `docs/DIRECT_PIPELINE_FLOW.md` — the direct-pipeline design and flow note.
- **Existing files (edits only):** none.

## Implementation

Write `docs/DIRECT_PIPELINE_FLOW.md` as a design-and-flow note in the same shape as its sibling flow docs. Match `docs/CREATE_FROM_EXISTING_FLOW.md`'s structure: a short intro line naming the verbs, a `## TL;DR` bullet block, a `## High-level flow` ASCII diagram, then sections that name the real source-of-truth symbols inline. Keep it forward-looking: describe the intended design, not a history of the change.

**What the doc must cover:**

- **The two chains, named explicitly.**
  - `direct-jira` = `create → detail → jira`.
  - `direct-run` = `create → detail → run --commit → the reconcile-code loop`.
  - State that both reuse the existing stage handlers rather than reimplementing them, and that the new verbs live in a thin CLI leaf `plan_tool/cli/direct_cmd.py` (created by step 3, extended by steps 4–5). Cite the sibling intent-group modules the leaf sits beside — `plan_tool/cli/authoring.py`, `plan_tool/cli/run_cmd.py`, `plan_tool/cli/jira_cmd.py` — as the pattern it follows.

- **The namespace-sink hand-off (the key design decision).**
  - Explain that today each stage re-discovers the create result on disk, and the direct verbs instead thread `create`'s result in-process.
  - Name the real symbols: `cmd_create` in `plan_tool/cli/authoring.py`, the `create_plan` call it makes (in `plan_tool/create.py`), and the `CreateResult` dataclass in `plan_tool/create.py` that is the object handed off. `CreateResult` already carries `plan_path`, `split_proposal`, `distilled_seed`, and the collision/provenance fields — the doc should note that `plan_path` is `None` only on the multi-plan split short-circuit, since the direct verbs must handle that case.
  - State the rule the sink obeys: it is an **optional attribute on the args `Namespace`** that, when present, receives the `CreateResult`; when absent, `cmd_create` behaves exactly as when run standalone. Attribute the mechanism to **step 2** ("step 2 teaches `cmd_create` to write its result to a caller-supplied namespace sink") rather than restating step 2's code — step 2 owns that change.
  - Note why the sink is chosen over changing `cmd_create`'s return type: it leaves the standalone CLI-entry contract unchanged and is invisible to every caller that does not set the attribute.

- **The size gate.**
  - Describe it as a deterministic check on the create result that flags a plan too large to chain safely, spends no Claude, and stops with an explicit message instead of silently one-shotting an over-large concept. Attribute the helper to **step 3** (`plan_tool/cli/direct_cmd.py`), and note that `-y`/non-TTY/`--force` is the intended override, per the plan's size-gate decision.
  - The doc may name the deterministic signals the gate keys off — a small step-count cap, `plan_tool/granularity.py:assess_granularity` `granularity-split` findings, and `create`'s multi-plan `SplitProposal` path (`plan_tool/cli/authoring.py:_emit_split_proposal`) — as design intent, framed as "the gate reuses existing detectors," not as a spec of step 3's code.

- **Cross-cutting flags and exit codes carry through unchanged.**
  - State that `--backend`, `--model`, `--on-rate-limit` (and the rate-limit policy) thread the same args namespace into the same handlers and the same invoker seam every stage already uses, so no stage sees a different backend when driven from a direct verb.
  - State the exit-code rule the chain preserves: subcommands exit non-zero only on failure-to-complete, and a mid-chain stage failure surfaces that stage's standard non-zero exit with no chain-level rollback.

- **The reconcile-code tail for `direct-run`.**
  - Name `plan_tool/cli/run_cmd.py:cmd_reconcile_code` as the handler the loop drives, and note the `run --commit` step precedes it. Point at `docs/RUN_FLOW.md` for the run stage's own gates rather than restating them — keep this doc about the *chain*, and cite the owning docs for each stage's internals.

**Constraints and gotchas:**

- **Reference sibling-step mechanisms by step id, never restate them.** Steps 2–6 are authored but not yet built when this doc lands; a restated mechanism goes stale the moment the owner is edited. Cite "step 2 adds the sink," "step 3 adds the gate helper," "step 6 registers the verbs" and stop there.
- **Cite symbols by name, not line number.** `cmd_create`, `create_plan`, `CreateResult`, `cmd_reconcile_code`, `assess_granularity`, `_emit_split_proposal` — all resolve at HEAD today; verify each still exists before citing.
- **Keep cross-doc links relative and working.** Link `docs/RUN_FLOW.md`, `docs/DETAIL_FLOW.md`, `docs/CREATE_FROM_EXISTING_FLOW.md`, and `docs/AUDIT_FLOW.md` with plain relative paths (e.g. `[RUN_FLOW.md](RUN_FLOW.md)`), matching how the sibling docs cross-link.
- **This is the tone-setter.** No sibling detail files exist yet for this plan; the section conventions here set the pattern later siblings follow.

## Tests

### Verification (non-code step)

This step changes no production code, so verify the artifact rather than run unit tests:

- **File exists** — `docs/DIRECT_PIPELINE_FLOW.md` is on disk after the step.
- **Both chains documented** — the doc names `create → detail → jira` and `create → detail → run --commit → reconcile-code` verbatim.
- **Namespace-sink hand-off documented** — the doc describes the optional-attribute sink and attributes the code change to step 2.
- **Symbol accuracy** — every symbol cited without a step-id caveat (`cmd_create`, `create_plan`, `CreateResult`, `cmd_reconcile_code`, `assess_granularity`, `_emit_split_proposal`) is greppable at HEAD; symbols created by later steps (`cmd_direct_jira`, `cmd_direct_run`, `direct_cmd.py`, the size-gate helper) are named with a step-id reference.
- **Links resolve** — every relative cross-doc link (`RUN_FLOW.md`, `DETAIL_FLOW.md`, `CREATE_FROM_EXISTING_FLOW.md`, `AUDIT_FLOW.md`) points at a file that exists under `docs/`.
- **No drift-guard suite applies** — this doc is not registered with any drift guard, so accuracy is checked by reading, not by a test. Note there is no `tests/` file to add for this step.

## Acceptance criteria

- `docs/DIRECT_PIPELINE_FLOW.md` exists.
- The doc documents both the `create → detail → jira` and `create → detail → run --commit → reconcile-code` chains.
- The doc describes the namespace-sink hand-off between `cmd_create` and the direct verbs, and describes the deterministic size gate.
- The doc states that `--backend`, `--model`, `--on-rate-limit` and the non-zero-only-on-failure exit-code convention carry through each chained stage unchanged.
- Every relative cross-doc link in the file resolves to an existing file under `docs/`.
- Symbols cited without a step-id caveat exist at HEAD; symbols later steps create are named with their owning step id.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — for describing how each stage's args `Namespace` (and the optional sink attribute) is threaded into the reused handlers.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — for the `--backend`/`--model`/`--on-rate-limit` cross-cutting flags the doc says carry through each chained stage.
- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — background for the `direct-run` `run --commit` + reconcile-code tail, which relies on clean-tree gating; cite the owning `docs/RUN_FLOW.md` for the mechanism.

## Deferred

- **Building the `direct_cmd.py` verbs, the namespace sink, and the size-gate helper** — this step only documents the design; the code lands in steps 2–6.
- **Generated per-verb CLI reference (`docs/cli/direct-jira.md`, `docs/cli/direct-run.md`)** — those are produced by step 6's CLI-reference regeneration, not this design note.
- **Operator-facing catalog updates (README, CAPABILITIES, USE_CASES)** — step 7 owns those surfaces; this doc is the internal design/flow note.
