---
title: Scope Out Executor
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add carved-region seed emitter in scope_out.py (run-state carried into create
    --from-existing seed)
  creates:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Add policy-free narrow primitive (drop step + contiguous renumber + detail
    migration) with dry-run preview and apply-or-rollback atomicity
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
- id: 3
  title: Add gated scope_out executor (seed-first ordering, strictly-downstream orphaning
    gate, empty-plan refusal, opt-in + interactive confirm, frozen EscalateResult-style
    outcome)
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
- id: 4
  title: Wire plan-tool scope-out subcommand (handler + app/parser/__init__ registries
    + generated cli reference + package-surface golden)
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  creates:
  - plan_tool/cli/scope_out_cmd.py
  - tests/cli/test_scope_out_cmd.py
  - docs/cli/scope-out.md
  complexity: medium
  change_type: feature
  depends_on:
  - 3
- id: 5
  title: Flip convergence scope-out sub-arm from prose-only to runnable plan-tool
    scope-out command (add _scope_out_command in render_diagnosis)
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
- id: 6
  title: Document scope-out across README / RUNBOOK / CLAUDE / both SKILL routers
    (sequenced after the vocabulary plan's RUNBOOK/CLAUDE edits)
  files:
  - README.md
  - RUNBOOK.md
  - CLAUDE.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
---
# Scope Out Executor

## Overview

Adds the gated `plan-tool scope-out <plan> --step N [--yes]` executor — the actuating half of the structural-remedy work, carved out of `structural-remedy-vocabulary` (which ships the advisory arms). Scope-out splits at the plan-scope altitude: it carves a spinning region out of a plan into a `create --from-existing` forward-seed (carrying the carved step's run state) and narrows the surviving plan. The executor is opt-in + interactive-confirm; the default/unattended path recommends only, spends no Claude, and performs no mutation. It depends on `structural-remedy-vocabulary` landing first and then flips that plan's prose-only convergence recommendation into a runnable command.

## Problem statement

When a region of a plan is spinning — recurs + no-shrinkage at `max_severity ≥ high` with a non-decreasing first→last severity trend (the "patches backfire" signature the `convergence` diagnostic detects) — the right remedy is to carve that region out so the rest of the plan can converge, and land the carved work somewhere durable and resumable. The advisory arms (`scope-out` source token, triage wiring, the `convergence` recommendation, the reconcile finding) ship in `structural-remedy-vocabulary`, but there is no executor that *acts on* the recommendation: the convergence diagnostic renders the scope-out remedy prose-only, with no runnable command behind it. A deep 5-pass audit of the combined plan put 5 of 6 HIGH/structural findings on this executor — it is not compose-existing for its narrowing half, and it was gated on a run-state question (now resolved).

## Architecture

`plan-tool scope-out <plan> --step N` performs two mutations, **seed-first**:

1. **Emit a `create --from-existing` forward-seed** for the carved step(s) under `plan-seeds/<plan>-carved-<slug>.md`, carrying the carved step's run state (status + progress) so the work is resumable in the next iteration.
2. **Narrow the plan**: drop the carved step(s) from `steps:`, renumber the survivors to contiguous `1..N`, and migrate downstream detail files to their new ids.

**Seed-first ordering is the atomicity contract**: a crash after the seed write leaves a harmless re-runnable orphan seed (carved work captured); a crash before it leaves the plan untouched. Never narrow before the carved region is durably written.

**Resolved design decisions (ground the build on these):**

1. **Run-state → carry into the seed.** Scope-out exists to carve a step that *has* run state, so the executor must **not** reuse the PENDING-only safety gate verbatim (`merge_steps` / `split_step` / `escalate_to_split` all refuse a run-started *target*), and must not silently discard run state. The emitted seed records the carved step's status + progress. The gate that *does* apply is the downstream-orphaning one, not a refuse-if-worked gate on the target. (fixes `scope-out-carved-step-runstate`)
2. **The narrow is a NEW primitive — not `merge` or `split`.** No existing executor *drops* a step: `split_step` is one→many; `merge_steps` folds many→one survivor at `min(merge_ids)` and never removes content. **Reuse** the renumber + detail-migration machinery (`create._apply_step_merge`'s contiguous-renumber logic and `detail._migrate_downstream_details_after_merge`'s downstream-id rename), but the drop-and-renumber-around-the-hole narrowing is genuinely new code — do not claim compose-existing for this half. (fixes `narrow-drop-primitive`)
3. **Intra-narrow atomicity.** The narrow is multi-step (rewrite frontmatter `steps:` + renumber + rename detail files); a crash mid-narrow can leave frontmatter and detail files inconsistent. Compute the full new-plan + file-rename plan in memory (a dry-run preview, as `merge_steps(dry_run=True)` does), validate, then apply with rollback on failure — never a partial on-disk state. (fixes `narrow-atomicity`)
4. **Empty-plan guard.** Carving the only surviving step would produce a `steps: []` plan. **Refuse** when the carve would empty the plan, pointing the operator at a full re-seed (`create --from-existing`) — a plan with nothing left is a re-seed, not a scope-out. (fixes `scope-out-last-step-empty-plan`)
5. **Carved-region seed emitter — adapt, don't force-reuse.** `annotate_render.render_create_seed(annotation: PlanAnnotation, *, report_path)` consumes a whole-plan `PlanAnnotation` (from `annotate.classify_plan_implementation`) and writes beside the source — its input contract does not match a carved step-subset written under `plan-seeds/`. Build a focused carved-region seed renderer (or a thin adapter synthesizing the minimal seed from the carved `Step`s + their detail bodies + run state) rather than manufacturing a `PlanAnnotation`. No Claude needed — the emit is deterministic serialization. (fixes `scope-out-seed-emission-reuse`)
6. **Gating mirrors `escalate_to_split` (`launcher.py`).** The mutation applies only when **safe** (no downstream non-PENDING/run-started step would be orphaned by the renumber) **+ opt-in** flag **+ interactive confirm `yes`**. Every other path (unattended, unsafe, non-TTY, declined) recommends only, spends no Claude, performs no mutation. Return a frozen result mirroring `EscalateResult` (an `outcome` like `applied` / `recommended` / `unsafe` / `step-missing`; only `applied` mutates), and re-parse the plan from disk on entry.

**Dependency on `structural-remedy-vocabulary`.** That plan introduces the `scope-out` source token (kept out of `APPLY_ELIGIBLE_SOURCES`), the per-source triage message, and renders the `convergence` scope-out recommendation prose-only. This plan flips that: once `plan-tool scope-out` exists, update `convergence_diagnosis.py:render_diagnosis` (alongside `_split_command` / `_reseed_command`) to render the runnable `plan-tool scope-out <plan> --step N` command for the scope-out sub-arm. No forward-ref — the command is rendered only after its executor ships.

**Layering.** New thin handler `plan_tool/cli/scope_out_cmd.py` wired via `app.py` (dispatch) + `parser.py` (argparse); the real work in a new `plan_tool/scope_out.py` leaf, mirroring the thin-handler / orchestrator split. Run-state fields come from `plan_tool/schema.py` (`Plan` / `Step` / `StepStatus`).

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Official reference for @dataclass and frozen=True, needed to build the immutable EscalateResult-style outcome value the executor returns.
- [os — Miscellaneous operating system interfaces: os.replace](https://docs.python.org/3/library/os.html#os.replace) — Documents os.replace's atomic, cross-platform overwrite semantics — the primitive for the seed-first / apply-or-rollback atomicity contract on the frontmatter and detail-file rewrites.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Reference for adding the new `scope-out <plan> --step N [--yes]` subcommand and flags in parser.py, including subparser dispatch and store_true confirm flags.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Library guide for safe_load/dump used to re-parse the plan's YAML frontmatter from disk and rewrite the narrowed `steps:` block.
- [pytest documentation](https://docs.pytest.org/en/stable/) — Authoritative pytest guide for the unit/integration tests (markers, tmp_path, monkeypatch) covering run-state carry, rollback, gate paths, and the convergence-render assertion.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A new split/merge algorithm for the **step** altitude — reuse `split_step` / `merge_steps`.
- **Auto-mutating structure unattended** — every actuating path stays opt-in + interactive-confirm; default recommends only, spends no Claude.
- A **BACKLOG.md writer** or an **in-plan `DEFERRED`** disposition — the carved part is a forward-seed, full stop (settled in the vocabulary plan).
- The advisory arms themselves (token, triage, convergence *recommendation*, reconcile *finding*) — those ship in `structural-remedy-vocabulary`.

## Risks

- **Run-state fidelity in the seed** — the carried status/progress must round-trip so `create --from-existing` resumes correctly; test the carry explicitly.
- **Partial on-disk state** — mitigated by the dry-run-preview-then-apply + rollback narrow (Resolved decision 3) and the seed-first ordering.
- **Renumber orphaning** — the safety gate must catch a downstream non-PENDING step whose id would shift; mirror `merge_steps`'s unsafe-set refusal for *downstream* (not target) steps.
- **Doc double-write** — this plan and the vocabulary plan both touch RUNBOOK/CLAUDE docs; sequence them so a watched-file drift guard does not halt mid-run.

## Testing

Default to unit tests (`@pytest.mark.integration` only for cross-module wiring, per `TESTING.md`). Cover: the run-state carry round-trips through the emitted seed so `create --from-existing` resumes correctly (explicit test); the narrow is atomic — a forced mid-narrow failure rolls back to no partial frontmatter/detail-file state; the empty-plan carve is refused with the re-seed hint; the downstream-orphaning safety gate refuses an unsafe renumber (downstream non-PENDING step whose id would shift) while permitting a run-started *target*; each gate path (unattended / unsafe / non-TTY / declined / confirmed-safe) yields the correct frozen `EscalateResult`-style outcome with only `applied` mutating. Add an integration test driving `plan-tool scope-out` end-to-end (seed-first emit → narrow → detail-file migration) and one asserting `plan-tool convergence` renders the runnable command after the executor ships. Existing `escalate_to_split` / `merge_steps` / `convergence` suites must still pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool scope-out <plan> --step N` (opt-in + interactive confirm, on a safe plan) emits a `create --from-existing` forward-seed carrying the carved step's run state, then narrows the plan (drop + renumber + migrate detail files) — seed-first, never dropping the carved work.
- A carved step with **live run state** is carried into the seed (status + progress preserved, resumable) — **not** refused, **not** silently discarded.
- The narrow is **atomic** (dry-run preview + apply-or-rollback); no partial frontmatter/detail-file state on crash.
- Carving the plan's **only** surviving step is **refused** with a re-seed hint (never a `steps: []` plan).
- The default / unattended / unsafe / non-TTY / declined paths **recommend only**, spend **no Claude**, and perform **no mutation**; the result is a frozen `EscalateResult`-style value where only `applied` mutated.
- `plan-tool convergence` renders the **runnable** `plan-tool scope-out … --step N` command for the scope-out sub-arm (flipped from the vocabulary plan's prose-only).

## Deferred

- **Multi-region carve in one invocation** — `--step N` carves a single step per run; carving several spinning steps (a multi-step region) in one pass is postponed until the single-step carve proves out.
- **Reconcile → scope-out actuation bridge** — the vocabulary plan ships the reconcile structural *finding* (kept out of `APPLY_ELIGIBLE_SOURCES`); auto-routing it to this executor (à la the escalate-to-split bridge) is left for later, so the operator hand-runs the command for now.
- **Scope-out decision telemetry** — recording a `scope-out` `DecisionEvent` via `telemetry.py` (extending Phase 1's granularity / audit-coverage / convergence decisions) is deferred to telemetry Phase 2.
