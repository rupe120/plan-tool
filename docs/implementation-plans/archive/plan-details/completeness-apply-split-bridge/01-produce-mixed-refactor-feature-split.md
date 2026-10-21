> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Produce the medium mixed refactor+feature split finding in the completeness audit

## Summary

Today the completeness audit only produces `info`-severity `granularity-split` findings — the deterministic title/area heuristics in `plan_tool/granularity.py:_split_findings`. It never produces the higher-confidence `medium` MIXED-STEP finding (a step that fuses a behavior-preserving refactor with new behavior), because that judgment is Claude-judged and is not run anywhere in the completeness lane. This step wires a per-step purity judgment into `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` so a `medium` `source="granularity-split"` recommendation (with `step_id` set) is produced for each mixed code step and folded into the report's advisory smell bucket. The finding is surfaced in the audit output only — persisting it to the saved sidecar is step 2, and dispatching it to the split bridge is steps 3–4. On green, a completeness audit of a plan whose step mixes refactor + feature shows a `medium` mixed-step split finding beside the existing `info` ones.

## Table of Contents

- [Why](#why) — the gap this closes and why it matters now
- [Input](#input) — the finding contract this step produces and reuses
- [Files (creates vs edits)](#files-creates-vs-edits) — what this step touches
- [Implementation](#implementation) — how to produce the medium finding and where it must land
- [Tests](#tests) — unit cases added with the implementation
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the docs worth reading for this step
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

The plan's whole point is to route the `medium` MIXED-STEP `granularity-split` finding through the shipped `escalate_to_split` bridge in the `completeness-apply` walk. But that walk replays the saved sidecar, and the sidecar is built from findings the completeness audit actually produces. Right now the completeness audit produces no `medium` mixed-step finding at all: `_run_deterministic_checks` calls `plan_tool/granularity.py:assess_granularity` with `stage="completeness"` and `invoker=None`, which runs only the deterministic `info` split/merge detectors — the Claude-judged prose kernel (`parse_mixed_step_findings`) never fires in this lane. The finding a mixed step deserves exists only during `plan-tool detail` authoring, and even there it is stripped from the detail file on disk (`plan_tool/detail.py` removes the `## Structural findings` block before writing). So the completeness audit — the operator-facing readiness gate — is blind to mixed steps at the `medium` altitude. This step makes the completeness audit produce that finding; the later steps persist and dispatch it.

## Input

- **Produces / reuses the `granularity-split` finding contract.** The `medium` recommendation this step emits must match what `plan_tool/granularity.py:parse_mixed_step_findings` already returns: `source="granularity-split"` (the `GRANULARITY_SPLIT_SOURCE` constant), `severity="medium"`, and `step_id=step.id`. Downstream steps key on exactly these fields — step 3's dispatch predicate keys on `source` + `step_id`, and step 4's split targets `step_id`.
- **Depends on a Claude-judged purity signal, not a plan-structure heuristic.** The `info` deterministic detectors (`plan_tool/granularity.py:_split_findings`) read only the plan and title; the `medium` signal is a language-model judgment of the authored detail body. This step's producer must be the Claude-judged path, not a promotion of the `info` detector.
- **Reads each pending code step's detail body via Claude.** The on-disk detail files never carry a `## Structural findings` block (it is stripped at author time), so the `medium` finding cannot be recovered by re-parsing files — it requires re-judging the body with Claude. `plan_tool/detail.py:collect_detail_quality_findings` is the one existing producer that renders the detail-quality prompt, invokes Claude, and lifts the block via `parse_mixed_step_findings`. Its quiet probe stops early — returns `[]` before any Claude call when a step has no detail pointer or the file is missing — the contract limit that bounds cost.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — in `_run_deterministic_checks`, run a per-step Claude purity judgment, keep only the `medium` `granularity-split` MIXED-STEP recs, and fold them into `smell_recs` (or a sibling bucket also handed to the render/persist tail) alongside the existing `info` granularity recs. Gate the purity pass off a dedicated flag (not `quiet`) so it does not re-fire from the function's second call site, `write_pre_apply_audit_checkpoint` — see the "fire at most once per audit" constraint below. Update the phase's `no claude` framing (the `[1/2] deterministic well-formedness checks … no claude` banner and the docstring) so it reflects that a Claude purity call now runs. Leave the existing `assess_granularity(stage="completeness", invoker=None)` deterministic call unchanged.
  - `tests/cli/test_completeness_cmd.py` — add cases for the new producer and extend/counter the existing granularity folds test.

## Implementation

**What changes.** `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` gains a Claude-judged per-step purity pass that produces `medium` `granularity-split` MIXED-STEP recommendations and folds them into the advisory smell bucket so the report renders them. The deterministic `info` split/merge detectors are untouched.

**Key design decision — reuse the one Claude purity producer, filter to the `medium` signal.** The recommended approach: for each pending code step, call `plan_tool/detail.py:collect_detail_quality_findings(plan_path, step, repo_root=…, plan_name=…, invoker=shell_detail_invoker)` and keep only the recs where `rec.source == GRANULARITY_SPLIT_SOURCE and rec.severity == "medium"`. That function already renders the detail-quality prompt, invokes Claude through a patchable seam, and lifts the `## Structural findings` block via `parse_mixed_step_findings` — so reusing it single-sources the mixed-step judgment instead of re-implementing the prompt+lift here. The alternative — re-render `render_detail_quality_prompt`, invoke, and call `parse_mixed_step_findings` inline in `completeness_phases.py` — duplicates the purity slice of `collect_detail_quality_findings` and is not preferred. Import `detail` body-locally inside the phase (matching how this module already body-locally imports `plan_tool.review`); `plan_tool/detail.py` does not import `completeness_phases`/`completeness_cmd`, so the edge stays acyclic.

**Where the finding must land — the smell bucket is the only channel that reaches step 2 without touching the orchestrator.** The completeness orchestrator `plan_tool/cli/completeness_cmd.py:cmd_completeness` hands `_persist_and_present_report` its buckets as explicit keyword args, and it passes `smell_recs=det.smell_recs`. It also filters the conceptual audit's recs to `source=="plan-completeness"` / `source=="plan-correctness"`, which would drop a `granularity-split` rec. So a `granularity-split` `medium` rec can only reach step 2's sidecar assembly if it rides the `smell_recs` bucket — neither step 1 nor step 2 is scoped to edit `completeness_cmd.py`. Fold the `medium` recs into `det.smell_recs` (the same bucket the `info` granularity recs already join). Step 2 then adds the `medium` `granularity-split` subset of `smell_recs` to `sidecar_recs` inside `_persist_and_present_report`.

**Constraints and gotchas that are not free to vary:**
- **Keep the `info` detectors report-only and unchanged.** The existing `assess_granularity(plan, stage="completeness", invoker=None)` call stays no-Claude and its `info` recs keep folding into `smell_recs`. Do not promote a deterministic `info` detector to `medium` — the plan forbids firing structural mutation off a low-confidence title heuristic.
- **The `medium` recs must carry `source="granularity-split"`, `severity="medium"`, and `step_id=step.id`.** These come free from `parse_mixed_step_findings`; do not re-mint them. Step 3's dispatch and step 4's split key on `source` + `step_id`.
- **Do not spend Claude when there is nothing to judge.** `collect_detail_quality_findings` returns `[]` before any Claude call for a step with no detail pointer or a missing/empty file — rely on that quiet-probe stop-early rather than adding a second gate. Non-code steps are dropped inside `parse_mixed_step_findings`, so a mixed-step rec can never be produced against one.
- **Fire the purity pass at most once per audit — gate it off the pre-apply checkpoint call site, not `quiet`.** `_run_deterministic_checks` runs at two call sites in `plan_tool/cli/completeness_phases.py`: the main audit (`_persist_and_present_report`, `quiet=budget.enabled`) and `write_pre_apply_audit_checkpoint` (the pre-apply crash-recovery checkpoint, `quiet=True`), which exists only to persist the already-computed conceptual audit before the `--iterate` apply loop. If the new per-step purity pass runs unconditionally inside `_run_deterministic_checks`, an `--iterate` run fires the full per-step detail-quality Claude review twice — once just to write the checkpoint. **`quiet` cannot be the discriminator:** under `--iterate` (the mode this plan targets) `budget.enabled` is true, so the main audit is *also* `quiet=True` — gating on `not quiet` would suppress the purity pass on exactly the run that needs it and still fail to tell the two call sites apart. Instead add a **dedicated flag** (e.g. `run_purity: bool`) to `_run_deterministic_checks` that the main audit passes true and the checkpoint passes false, **or** thread the main audit's already-computed `medium` recs into `write_pre_apply_audit_checkpoint` so the checkpoint re-uses that result rather than re-running the pass — either way the purity pass spends Claude on the main audit only, keeping the "no claude"/cost framing honest.
- **Do not persist or dispatch here.** The `medium` rec must appear in the report but must not yet be in the saved sidecar (step 2) and must not be routed to the split bridge (steps 3–4). `granularity-split` stays out of `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` and in `STRUCTURAL_SOURCES`; this step does not touch either.
- **The advisory-count invariant holds.** The `_det_total` deterministic-finding count in `_run_deterministic_checks` must keep excluding granularity recs (advisory), and `smell_recs` must stay out of `_completeness_has_blocking_findings` — a `medium` mixed-step finding surfaces without inflating the well-formedness count or flipping the exit code.
- **Update the `no claude` framing.** The `[1/2] deterministic well-formedness checks … no claude` banner and the phase docstring now overstate the phase's purity — reword them to name the per-step purity call, or clearly separate the purity pass from the deterministic banner.

## Tests

All cases live in `tests/cli/test_completeness_cmd.py`. Stub the purity producer (patch `plan_tool.detail.collect_detail_quality_findings` or the `shell_detail_invoker` seam) so the conftest autouse gate never sees a real backend spawn.

- `test_run_deterministic_checks_produces_medium_mixed_step_finding` — with a stubbed producer returning a `medium` `granularity-split` rec (`step_id` set), `_run_deterministic_checks` folds it into `report.smell_recs`; assert `source`, `severity="medium"`, and `step_id`.
- `test_medium_mixed_step_finding_surfaces_in_grouped_report` — the produced `medium` rec renders in the report's advisory smells section via `_render_grouped_report`.
- `test_medium_mixed_step_finding_in_json_smells` — the `medium` rec appears in the `--json` `smells` array (`_render_completeness_json`), keyed on `source`.
- `test_purity_pass_short_circuits_without_detail_bundle` — a plan whose steps have no detail files produces no `medium` finding and spawns no real Claude (quiet probe returns `[]` before any Claude call).
- `test_purity_pass_uses_patchable_invoker_seam` — the producer routes through the patched seam; no `@pytest.mark.allow_real_claude`, and the conftest backend gate confirms nothing spawned.
- `test_pre_apply_checkpoint_does_not_refire_purity_pass` — `write_pre_apply_audit_checkpoint` (the checkpoint call site) does not re-run the per-step purity producer; assert the stubbed `collect_detail_quality_findings` seam is invoked only by the main audit, not a second time for the checkpoint. Drive this under `--iterate` (so the main audit runs `quiet=True` too) to pin that the discriminator is the dedicated flag, not `quiet`.
- `test_non_code_step_yields_no_mixed_step_finding` — a non-code step never yields a `medium` mixed-step rec (dropped inside `parse_mixed_step_findings`).
- `test_info_split_detectors_stay_report_only_and_unchanged` — the deterministic `info` `granularity-split` recs still fold into `smell_recs` unchanged; the `medium` rec is an addition, not a replacement.
- `test_medium_mixed_step_finding_not_in_sidecar_yet` — the produced `medium` rec is absent from the saved sidecar (pins the step 1 / step 2 boundary; sidecar persistence is step 2).
- `test_granularity_recs_still_excluded_from_deterministic_count` — the `medium` mixed-step rec does not inflate the deterministic finding count (still `0 finding(s)` for an otherwise-clean plan).
- Extend/counter `test_run_deterministic_checks_folds_granularity_into_smells` (≈699) so it accounts for the new `medium` producer, and re-confirm `test_run_deterministic_checks_passes_completeness_stage_and_no_invoker` still holds — the deterministic `assess_granularity` call stays `invoker=None`; the new purity pass is a separate seam.

### Test-creation order (feature step)

This is a feature step — new behavior. Add the tests above alongside the implementation. Suggested order: first the producer/fold cases (`…produces_medium…`, `…short_circuits…`, `…patchable_invoker…`), then the surface cases (`…grouped_report`, `…json_smells`), then the boundary/guard cases (`…not_in_sidecar_yet`, `…info_split_detectors…`, `…excluded_from_deterministic_count`, `…non_code…`), then reconcile the two existing granularity tests. **Green-before-done gate:** every new test must pass, and the full `tests/cli/test_completeness_cmd.py` suite must be green, before this step is finished.

## Acceptance criteria

- A completeness audit of a plan whose code step mixes a refactor with a feature produces a recommendation with `source="granularity-split"`, `severity="medium"`, and `step_id` set, folded into `_run_deterministic_checks`'s `smell_recs`.
- That `medium` finding renders in both the grouped report and the `--json` `smells` output.
- A plan with no detail bundle (or only non-code steps) produces no `medium` mixed-step finding and spawns no real backend process.
- On an `--iterate` run the per-step purity pass fires once per audit, not again from `write_pre_apply_audit_checkpoint` — gated by a dedicated flag rather than `quiet` (which is `True` for the main audit too under `--iterate`), so the "no claude"/cost framing stays honest.
- The deterministic `info` `granularity-split` detectors and their recs are unchanged; the deterministic finding count and `has_blocking_findings` flag are unaffected by the new `medium` finding.
- The `medium` finding is present in the report but not in the saved sidecar (step 2 owns persistence) and is not dispatched (steps 3–4).
- `tests/cli/test_completeness_cmd.py` passes, including the new cases and the reconciled existing granularity tests.

## References

- `plan_tool/detail.py:collect_detail_quality_findings` — the one existing Claude purity producer this step reuses: renders the detail-quality prompt, invokes Claude through a patchable seam, lifts the `## Structural findings` block, and its quiet probe stops early — returns `[]` (no Claude) when a step has no detail pointer or a missing/empty file. Read its signature and quiet-probe contract before wiring the per-step pass.
- `plan_tool/granularity.py:parse_mixed_step_findings` — defines the `medium` MIXED-STEP finding contract this step must match: `source="granularity-split"` (`GRANULARITY_SPLIT_SOURCE`), `severity="medium"`, `step_id=step.id`, non-code steps dropped. Downstream steps 3–4 key on `source` + `step_id`, so do not re-mint these fields.
- `plan_tool/prompts/plan-audit.md` (the **Mixed step (type impurity)** rule, ≈38) — the canonical definition of a mixed refactor+feature step (behavior-preserving refactor fused with new behavior), the invariant the `medium` finding encodes; `plan_tool/prompts/detail-quality.md` renders it in the purity producer's prompt.
- [pytest — Working with custom markers](https://docs.pytest.org/en/stable/how-to/mark.html) — how the conftest `allow_real_claude` opt-out works; this step's unit tests must stay unmarked so the autouse gate blocks any real backend spawn.

## Deferred

- **Persisting the `medium` finding to the saved sidecar** — step 2 (`sidecar_recs` + `DATA_CONTRACT.md` + its drift guard).
- **Dispatching the finding to `escalate_to_split`** — steps 3 (dispatch predicate + walk wiring) and 4 (`--apply-structural` gate).
- **Promoting the `info` deterministic detectors to dispatchable** — they stay report-only advisory; only the `medium` Claude-judged signal is in play.
- **Adding MIXED-STEP judgment to `plan-audit.md` / the conceptual audit** — out of scope; this step reuses the existing detail-quality purity producer rather than changing the conceptual audit prompt.
- **`create`-side structural dispatch** — deferred per CLAUDE.md; this plan is completeness-apply only.
