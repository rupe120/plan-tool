# Step 1 — Build arm-clustering consensus targets from saved audit history

## Summary

This step teaches plan-tool to remember a plan-audit finding's step attribution and to recognize when the same finding keeps recurring across separate `completeness-audit` runs. It adds a new `audit_step_target` field to `Recommendation` (`plan_tool/review.py`) and `RunFinding` (`plan_tool/convergence_diagnosis.py`), populated from the `[audit-step:N]` tag the plan-audit prompt already emits and `_split_audit_step_evidence` already parses, but which today is thrown away after one call. On top of that persisted history, it adds a new pure function in `plan_tool/convergence_diagnosis.py` that matches findings across the newest same-stage completeness passes (reusing the existing `_matches` tiering, `build_collapsed_completeness_passes`, and the windowing helper `classify_impact_recurrence`/`classify_edit_drift` already use), checks materiality on the newest round only, and resolves a single agreed, still-current step target per finding — producing the `consensus_targets` / `material_finding_ids` pair `evaluate_arm_clustering` (`plan_tool/audit_shapes.py`) needs but that today only a same-execution multi-pass audit can supply. The step deliberately stops short of calling `evaluate_arm_clustering` itself or touching `ConvergenceDiagnosis`/its render — see Implementation for why that boundary is drawn here rather than folded into this step. On green, a plan with two qualifying `--audit-passes 1` completeness reports has a tested, ready-to-call evidence builder, even though nothing renders yet.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — existing contracts this step reads and must fit
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the persistence edit, the new function, and the design decision behind the step boundary
- [Tests](#tests) — test roster
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

`evaluate_arm_clustering` already accepts a plain `consensus_targets: Mapping[str, int]` — nothing about its logic is same-execution-specific. But today the only caller that builds that mapping is `review.py`'s same-execution path inside `audit_plan_until_stable`, which needs at least two passes from *one* `completeness-audit` invocation (`--audit-passes N > 1`). At `--audit-passes 1` — the setting this repo's own stopping-rule convention recommends for scope-contract-bound audits — the advisory goes dark, exactly on the audits it exists to help decide. The plan-audit prompt already emits a per-finding `[audit-step:N]` tag and `_split_audit_step_evidence` already parses it inside `_parse_plan_audit_findings_with_evidence`, but the parsed value is diverted into the transient `_AuditTagObservation` there, and into `observations_by_id` only across multiple passes inside `audit_plan_until_stable` (`check_plan_audit`, the single-pass caller, neither builds `observations_by_id` nor constructs these objects itself) — and never reaches the saved `Recommendation`. Persisting it, and reusing the cross-run finding-identity machinery `impact_recurrence` / `edit_drift` already rely on (`_matches`, `build_collapsed_completeness_passes`), is what makes a round-over-round consensus computable without inventing a second identity scheme.

## Input

- **The `[audit-step:N]` tag contract** — emitted by the plan-audit prompt, parsed by `_split_audit_step_evidence` (`plan_tool/review.py`) into `(target: Optional[int], without_tag: str)`. A malformed, repeated, adjacent-without-separator, or prose-positioned token yields `target=None`, but the tag itself is always stripped from the body regardless. Today `target` reaches only `_AuditTagObservation.target_step_id` inside one `audit_plan_until_stable` call; it never attaches to the `Recommendation` that call returns.
- **`evaluate_arm_clustering`'s parameter contract** (`plan_tool/audit_shapes.py`) — this step's output must be shaped to feed it, even though this step does not call it. `declared_step_ids: Sequence[int]`, `material_finding_ids: Sequence[str]`, `consensus_targets: Mapping[str, int]`: every id in `material_finding_ids` must resolve, in `consensus_targets`, to a value present in `declared_step_ids`, or the whole call returns `None` — nothing partial. Any finding this step's function can't fully resolve must be dropped from both outputs, never passed through with a placeholder.
- **The existing cross-round machinery in `plan_tool/convergence_diagnosis.py`, reused read-only** — `ReportHistory` / `RunSnapshot` / `RunFinding` (the flattened saved-report model), `CompatiblePass` / `build_collapsed_completeness_passes` (same-`audit_stage` reuse-collapsed passes), `_matches` (the three-tier step-focus → concept-slug anchor → fuzzy-title finding-identity match), and `_impact_recurrence_trailing_window` (the newest-N-same-stage-passes windowing `classify_impact_recurrence` / `classify_edit_drift` already use — its name is recurrence-specific but its logic is generic windowing).
- **`is_blocking_finding(rec, *, stage, classify_domain=None)`** (`plan_tool/convergence.py`) — the audit-stage-bar materiality check `classify_edit_drift`'s `_edit_drift_eligible` already applies to `RunFinding` objects. This step reuses only that stage-bar half, not `_edit_drift_eligible`'s separate annotation-based exclusion (see Implementation).

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/review.py` — add `audit_step_target: Optional[int] = None` to `Recommendation`; populate it at the one place `_parse_plan_audit_findings_with_evidence` already computes the value.
- `plan_tool/convergence_diagnosis.py` — add `audit_step_target: Optional[int] = None` to `RunFinding` (plus a docstring sentence); populate it in `_finding_from_recommendation`; add `Mapping, Sequence` to the existing `typing` import; add a new top-level `from plan_tool.schema import StepStatus` import (the module does not import it today — `convergence_diagnosis.py`'s current top-level imports are `convergence`, `granularity`, `locator`, `review`, `review_persistence`, none of which re-export the name into this module's namespace, so the classifier's `StepStatus.DONE` comparison and its `Mapping[int, StepStatus]` type annotation both need this explicit import, not just a dependency-graph argument for why adding it is safe); add the new window constant, evidence dataclass, and classifier function described below.
- `DATA_CONTRACT.md` — new `audit_step_target` row in the `Recommendation` table.
- `tests/test_review.py` — extend the existing `[audit-step:N]` parsing tests to assert the new field.
- `tests/test_convergence_diagnosis.py` — extend the `_finding_from_recommendation` field-copy tests; add the new classifier's test class.
- `tests/test_data_contract.py` — no edit needed; its `test_contract_registry_discovers_dataclass_fields` reads `Recommendation`'s fields dynamically via `dataclasses.fields`, so it picks up `audit_step_target` with zero changes. Declared here only because the plan lists it — leave the file untouched and say so, rather than adding a no-op edit to make the diff match the file list.
- `tests/test_review_persistence.py` **(addition to the plan's declared file list)** — a `save_review` / `load_review` round-trip test for `audit_step_target`, mirroring the existing `test_round_trips_purity_verdict_provenance`. This is the one file that already tests exactly this shape of round-trip for a sibling `Recommendation` field; `tests/test_review.py` and `tests/test_data_contract.py` don't cover on-disk JSON round-tripping. Adding it is genuinely required to satisfy the plan's own Testing point 1 ("round-trips onto a saved `Recommendation` via `save_review`/`resolve_saved_review`").

## Implementation

### 1. Persist the tag onto `Recommendation` and `RunFinding`

Two separate edit sites — not one:

- **`plan_tool/review.py`** — add the field to `Recommendation` (after `target_signature`, following the existing one-field-per-comment style). Populate it in `_parse_plan_audit_findings_with_evidence`, at the `Recommendation(...)` construction that already sits inside the per-bullet loop: pass `audit_step_target=target`, reusing the `target` local that `_split_audit_step_evidence` already computed a few lines earlier in the same iteration. This is the only call site that needs to change; `Recommendation`'s generic `asdict` / `Recommendation(**r)` round-trip (`review_persistence.save_review` / `load_review`) already carries any new field with a default, the same way `target_signature` and `purity_verdict_provenance` do.
- **`plan_tool/convergence_diagnosis.py`** — add the field to `RunFinding`, with a docstring sentence next to how `step_id` / `anchor` / `impact` are already documented there. Populate it in `_finding_from_recommendation` alongside the other one-at-a-time field copies (the module's own docstring calls this a deliberate "persisted-field whitelist", never a generic `asdict`). Missing this site is the failure mode the plan's own Risks section calls out: every cross-round consumer this step (and step 2) builds reads `RunFinding`, not `Recommendation`, so a copy left only on the first site leaves the field permanently `None` on everything this work actually consumes.

Document both in the same edit, not deferred: `Recommendation.audit_step_target` gets a `DATA_CONTRACT.md` row (it round-trips through the saved-review sidecar); `RunFinding.audit_step_target` is documented only in `RunFinding`'s own docstring, matching that `DATA_CONTRACT.md` documents persisted schemas and `RunFinding` isn't one (none of `convergence_diagnosis.py`'s other dataclasses have a `DATA_CONTRACT.md` entry either).

### 2. Where this step's scope ends, and why

**Key decision:** this step produces round-over-round consensus *evidence* — a `consensus_targets` / `material_finding_ids` pair shaped exactly to `evaluate_arm_clustering`'s parameters — but it does not call `evaluate_arm_clustering`, and it does not add a `plan_tool.audit_shapes` import to `convergence_diagnosis.py`.

**Alternative considered and rejected:** having this step's function call `evaluate_arm_clustering` directly and return the resulting `AuditShapeAdvisory`, which would have made "the classifier function" a single self-contained call. Rejected because step 2 of this plan ("Add the cross-round arm-clustering advisory to the convergence diagnosis and its render") states its own intent as adding "the new `audit_shapes` import" to this module, in the same edit as correcting the module's "cycle-free leaf" docstring paragraph. `audit_shapes.py` is a pure leaf with no first-party imports of its own, so nothing about cycle-avoidance forces that import into step 2 specifically — it's a scope line the plan draws on purpose. Step 2's own dependency note frames step 1 as producing something `diagnose_convergence` *calls* and the render *reads fields off*, i.e. a finished input, not a finished advisory. Keep this step's new function pure over already-loaded `ReportHistory` data — no `plan_path`/`repo_root`, no filesystem access, no `audit_shapes` import — and hand step 2 exactly what it needs to build and render the advisory.

### 3. The new classifier function

One reasonable shape (naming is a recommendation, not a requirement — keep the sibling-verb style if you pick different names):

```python
CROSS_ROUND_CONSENSUS_WINDOW: int = 2  # distinct from WINDOW_SIZE = 3 (sized for a different, 3-point claim)

@dataclass(frozen=True)
class ArmClusteringConsensusEvidence:
    """Round-over-round consensus targets shaped to feed evaluate_arm_clustering.

    Not an AuditShapeAdvisory itself — assembling and rendering that is the
    next step's job. This only prepares its two identity-sensitive inputs.
    """
    window_audit_stage: str
    rounds_used: int
    consensus_targets: dict[str, int]
    material_finding_ids: tuple[str, ...]


def classify_arm_clustering_consensus(
    history: ReportHistory,
    *,
    declared_step_ids: Sequence[int],
    step_statuses: Mapping[int, StepStatus],
    window: int = CROSS_ROUND_CONSENSUS_WINDOW,
    classify_domain: Optional[Callable[[RunFinding], str]] = None,
) -> Optional[ArmClusteringConsensusEvidence]:
    ...
```

`declared_step_ids` and `step_statuses` are two independent parameters — mirror `evaluate_arm_clustering`'s own bare `Sequence[int]` for the former, and never let the function assume `declared_step_ids` carries status information it doesn't. A plain `id → StepStatus` map is one reasonable shape for `step_statuses`. `StepStatus` must be imported explicitly (`from plan_tool.schema import StepStatus`, see Files) — `plan_tool.review`, which this module already imports, pulls `plan_tool.schema` into the *dependency graph* without adding the name `StepStatus` to *this module's namespace*, so the import graph being acyclic is not a substitute for the explicit import the type annotation and the `StepStatus.DONE` comparison both need; the plan's own wording ("the plan's parsed `Step` objects, or an id→status map") leaves this open. Real values for both only arrive at the CLI layer in step 4 — this step's tests supply fixture data directly, and the function must not depend on step 4 existing.

What the function must do, in order:

1. **Window selection.** `passes = build_collapsed_completeness_passes(history)`, then take the trailing same-`audit_stage` window via `_impact_recurrence_trailing_window(passes, window=window)` — return `None` immediately when that's `None` (fewer than `window` compatible passes). Reusing this helper as-is is what makes "never mix bare and detail history in one window" true for free — it already refuses to cross an `audit_stage` boundary.
2. **Cross-round match.** For each finding in the newest pass, require at least one `_matches` hit against every *other* pass in the window (match each earlier pass's findings directly against the newest finding, not a hop-by-hop chain). **More than one finding in a single earlier pass can match the newest finding** — this is a real, routine case, not a corner case: `_matches` tier 1 fires on a shared leading `step<N>` anchor alone (see the "known, accepted limitation" below), and one completeness round commonly emits several findings anchored to the same step. Collect **every** matching finding in each pass, not a single "representative" per pass — the next point resolves target agreement over that whole collected set. A finding with no match in some pass of the window is not consensus-eligible this round.
3. **Materiality — newest round only.** For a fully-matched finding, call `is_blocking_finding(newest_finding, stage=window_audit_stage, classify_domain=classify_domain)` on the *newest* round's copy alone — never an older round's, never a mix, even when severity/impact differs between matched rounds. Reuse only this stage-bar half of `_edit_drift_eligible`; do not also reuse its `_is_resolved_in_run(annotations.get(...))` exclusion — a finding an operator declined in an earlier round must still be eligible here (Out of scope: this mechanism checks recurrence only).
4. **Target agreement.** Collect `audit_step_target` from the newest finding and from **every** matched finding across the other window passes (the full set point 2 collected — never a single per-pass "representative" when several findings in one pass matched). Drop the finding unless every one of those collected values is non-`None` and they all reduce to exactly one agreed value — the same fail-closed shape as the same-execution path's `len(target_ids) != 1` check, now applied over the union rather than assuming one match per pass. `Counter` or a plain `set` over the collected values is a natural fit here.
5. **Currency.** Drop the (now single, agreed) target unless it is present in the caller's current `declared_step_ids` *and* `step_statuses.get(target) is StepStatus.PENDING or step_statuses.get(target) is StepStatus.CURRENT` (i.e. present as a key **and** explicitly not `DONE`) — never write this as `step_statuses.get(target) is not StepStatus.DONE`: when `target` is absent as a *key* from `step_statuses`, `.get(target)` returns `None`, and `None is not StepStatus.DONE` is `True`, silently treating an unresolved status as "confirmed not done" — exactly the "never guess a target and never pass an unresolved one through" failure this same Architecture point exists to prevent. A target present in `declared_step_ids` but with no corresponding key in `step_statuses` must be dropped as unresolved, not passed as if its status were known. These are two independently-required checks — a target can be missing from `declared_step_ids` (deferred, `wont_do`, deleted, renumbered away) without its status being `done`, and a still-committed step can be `done` — plus this third failure mode (status unknown) that collapses to the same drop outcome.
6. **Assemble.** Findings that survive steps 2–5 populate `consensus_targets[newest_finding.id] = target` and are collected into `material_finding_ids` (recommended: preserve the newest pass's finding order — not required by `evaluate_arm_clustering`, but it's what the same-execution path already does via `by_id.values()` order, and it makes the printed evidence order stable). Return `None` when nothing survives (matching `classify_edit_drift` / `classify_impact_recurrence`'s "nothing to report → `None`" convention), rather than an evidence object with empty collections — `evaluate_arm_clustering`'s own `< 3` floor is not this function's job to pre-empt or duplicate (Out of scope: don't touch its arm math), but there's no reason to hand step 2 a value with nothing in it either.

**A known, accepted limitation to respect, not "fix":** `_matches` tier 1 matches purely on a leading `step<N>` / `step-<N>` anchor token — for `plan-correctness` / `plan-completeness` findings (`step_id` is always `None` for these sources), that collapses tier 1 to exactly "same leading anchor token," with no check that the rest of the anchor or the title agree. Two genuinely different findings anchored `step5-...` in different rounds will match at tier 1. This is the plan's own stated Risk, explicitly not a defect this step introduces or should try to close — `_matches` is reused unchanged (Applicable guardrails). What *does* protect against fabricating a false consensus in the common case is step 4 above (target agreement): two differently-worded findings sharing a `step5-...` anchor but disagreeing on (or missing) their `[audit-step:N]` tags produce no resolved target, not because `_matches` refused the pairing, but because the target-agreement check drops it. That guard does **not** cover the case where the two mismatched findings happen to carry the *same* tag value — that residual misattribution risk stays, by design, exactly as the plan's Risks section describes it.

## Tests

### Tests for this step

`tests/test_review.py`:

- `test_plan_audit_accepts_only_the_literal_audit_step_tag_slot` (extend) — asserts `[rec.audit_step_target for rec in recs]` matches the existing `[1, None, None, None, None]` observation-target sequence, so the persisted field and the transient observation never disagree.
- `test_audit_tag_consensus_keeps_recommendations_unattributed` (extend) — asserts the recs `audit_plan_until_stable` returns carry `audit_step_target == 1/2/3` in addition to the existing `step_id is None` / `advisory_out[0].arm_step_ids` checks.

`tests/test_review_persistence.py`:

- `test_round_trips_audit_step_target` (new, mirrors `test_round_trips_purity_verdict_provenance`) — a `Recommendation` with `audit_step_target=3` survives `save_review` → `load_review` unchanged; a `Recommendation` without it loads as `None`.

`tests/test_convergence_diagnosis.py`:

- `test_finding_from_recommendation_carries_audit_step_target` (new, mirrors `test_finding_from_recommendation_carries_impact`) — `_finding_from_recommendation` copies a non-`None` `audit_step_target` from `Recommendation` to `RunFinding`.
- `test_finding_from_recommendation_audit_step_target_none_when_absent` (new) — absent on the `Recommendation` → `None` on the `RunFinding`.
- New `TestArmClusteringConsensusClassifier` class (mirrors `TestEditDriftClassifier` / `TestImpactRecurrenceClassifier`):
  - `test_consensus_resolves_when_target_agrees_across_two_rounds` — a matched finding with the same `audit_step_target` in both window passes, material, current, and not `done` → returns evidence with that id mapped to the agreed target.
  - `test_consensus_drops_when_target_disagrees_across_rounds` — matched finding, different `audit_step_target` per round → dropped from both `consensus_targets` and `material_finding_ids`, not returned as a partial/`None`-target entry.
  - `test_consensus_drops_when_target_missing_on_one_round` — matched finding, tag present in one round's response and absent in the other → dropped.
  - `test_consensus_materiality_uses_only_newest_round_copy` — a finding whose severity/impact differs between the two matched rounds is judged solely on the newest round's copy (construct a case where using the older round's copy would flip the eligibility verdict).
  - `test_consensus_ignores_declined_annotation` — a finding an operator marked `skip` in an earlier round is still eligible for consensus (proves the `_edit_drift_eligible`-style annotation exclusion was deliberately not reused).
  - `test_consensus_no_fire_when_fewer_than_window_compatible_passes` — one same-stage pass only → `None`.
  - `test_consensus_no_fire_on_stage_boundary` — newest pass is `detail`, prior compatible pass is `bare` → window unsatisfiable → `None` (proves reusing `_impact_recurrence_trailing_window` gets stage-mixing protection for free).
  - `test_consensus_drops_target_absent_from_current_declared_step_ids` — agreed target step no longer in the current `declared_step_ids` (deferred/`wont_do`/deleted/renumbered) → dropped, not a `None`-returning whole-function failure.
  - `test_consensus_drops_target_whose_current_status_is_done` — agreed target step present in `declared_step_ids` but its current status is `StepStatus.DONE` → dropped.
  - `test_consensus_drops_target_absent_from_step_statuses` — agreed target step present in `declared_step_ids` but its id is **not a key** in `step_statuses` at all → dropped as unresolved status, not treated as "confirmed not done" (the exact `.get(target) is not StepStatus.DONE` bug this step's Currency rule must avoid).
  - `test_consensus_matched_representatives_pool_across_multiple_findings_per_pass` — an earlier pass contributes **two** findings that each `_matches` the newest finding (both anchored `step5-...`), carrying the same agreed `audit_step_target` → still resolves one consensus target (pooling, not picking one arbitrarily). A sibling case with the two same-pass matches carrying *disagreeing* targets → dropped, not resolved by picking either one.
  - `test_consensus_shared_step_token_anchor_with_disagreeing_targets_not_treated_as_recurring` — two findings sharing a `step5-...`-prefixed anchor across rounds (so `_matches` tier 1 fires, unmodified) but carrying disagreeing `[audit-step:N]` tags → no resolved consensus target, and the test asserts this via the target-agreement drop, not by asserting `_matches` itself declined the pairing.
  - `test_consensus_evidence_feeds_evaluate_arm_clustering` — end-to-end feasibility check: feed a returned `ArmClusteringConsensusEvidence`'s `consensus_targets` / `material_finding_ids` straight into a real `evaluate_arm_clustering(...)` call inside the test (not in production code this step ships) and assert it produces a non-`None` advisory on a constructed 3+-finding majority-arm fixture. Proves the shapes actually line up without waiting for step 2.
  - `test_consensus_classifier_imports_no_retired_fork_apis` (mirrors the sibling classifiers' own guard) — greps the new function's source for `RegionTrend` / `classify_fork` / `recurring_regions` and asserts none appear.

Every test above must be green before this step is considered finished.

## Acceptance criteria

- `Recommendation.audit_step_target` and `RunFinding.audit_step_target` both exist, default to `None`, and the plan-audit's `[audit-step:N]` tag reaches both — `Recommendation` via the one parse-site edit, `RunFinding` via the one `_finding_from_recommendation` edit.
- `Recommendation.audit_step_target` has a `DATA_CONTRACT.md` row under the `Recommendation` table; `RunFinding.audit_step_target` is documented in `RunFinding`'s own docstring. Neither is deferred to a later step.
- The new classifier function returns a resolved consensus target only when: the finding matches (via unmodified `_matches`) in every pass of the window (pooling **every** matching finding in a pass, not a single representative, when more than one matches), materiality passes `is_blocking_finding` on the newest round's copy alone, every matched finding's `audit_step_target` across the pooled set agrees and is non-`None`, the agreed target is in the current `declared_step_ids`, and `step_statuses` has that target as a key **and** its value is not `StepStatus.DONE` — a target absent as a key from `step_statuses` is dropped as unresolved, never treated as confirmed-not-done. Any finding failing one of these is dropped from both `consensus_targets` and `material_finding_ids` together — never left half-resolved.
- The function never combines passes from different `audit_stage` values in one window.
- The function takes `declared_step_ids` and step-status data as caller-supplied parameters (fixture data in this step's own tests) and does not depend on step 4 (the real CLI wiring) to exist or be tested.
- The same-execution consensus path in `plan_tool/review.py` (`observations_by_id`, `consensus_targets` inside `audit_plan_until_stable`) and `evaluate_arm_clustering`'s own signature/math are unmodified.
- `plan_tool/convergence_diagnosis.py` gains no `plan_tool.audit_shapes` import and no call to `evaluate_arm_clustering` in this step.
- A returned `ArmClusteringConsensusEvidence`'s `consensus_targets` / `material_finding_ids` are directly usable as `evaluate_arm_clustering`'s corresponding arguments, proven by a test that makes the call.

## References

- [difflib — Helpers for computing deltas (Python 3 Standard Library)https: — `SequenceMatcher.ratio()`'s `[0, 1]` semantics behind `_matches`' tier-3 fuzzy-title leg, reused unchanged by the new function.
- [collections.abc — Abstract Base Classes for Containershttps: — the `Mapping` contract `consensus_targets: dict[str, int]` satisfies, matching `evaluate_arm_clustering`'s own parameter type.
- [collections — Container datatypes (Counter, defaultdict, deque)https: — a natural fit for tallying each matched finding's per-round `audit_step_target` values when enforcing the single-agreeing-target check.
- [dataclasses — Data Classeshttps: — field defaults for the new `audit_step_target` field on both `Recommendation` and `RunFinding`, and for the new `ArmClusteringConsensusEvidence` result type.

## Applicable guardrails

The plan's `## Out of scope` section binds this step on several points:

- No change to `evaluate_arm_clustering`'s signature or arm math — this step's edits stay entirely outside `plan_tool/audit_shapes.py`.
- No change to the existing same-execution (`--audit-passes N > 1`) consensus path in `plan_tool/review.py` — the `review.py` edit here is purely additive (one new field, one populate site); `observations_by_id` / `consensus_targets` inside `audit_plan_until_stable` are untouched.
- No new blocking gate, exit-code flip, or apply-dispatch keyed on the new evidence — the classifier function is pure and unconsumed by any gate; nothing in this step changes what blocks convergence or iteration.
- No reviving the retired region-trending diagnostic's vocabulary — the new names in this step must not resemble `spinning` / `FORK_*` / `recurring_regions`.
- `build_collapsed_completeness_passes`, `_matches`, and `_impact_recurrence_trailing_window` are consumed read-only — this step calls them, never edits their bodies.
- No backfilling consensus for history predating this change, and no mixing of `audit_stage` values in one window — both are structural properties of reusing `_impact_recurrence_trailing_window` as specified above, not separate work.
- `Recommendation.step_id` / `RunFinding.step_id` stay `None` for these sources — `audit_step_target` is a new, separate field, never a repurposing of `step_id`.
- Cross-round materiality must not be made to agree with same-execution materiality (`is_blocking_impact` / `build_low_impact_demotion_lookup`) — the new function uses `is_blocking_finding` deliberately instead, and that divergence is intentional, not a gap to close.
- Cross-round consensus must not be gated on any evidence that a fix was attempted between matched rounds (a changed fingerprint, a resolved annotation) — this step's function checks recurrence only, which is why the annotation-based half of `_edit_drift_eligible` is deliberately not reused.

## Deferred

- Calling `evaluate_arm_clustering` with this step's evidence, wrapping the result, wiring it onto `ConvergenceDiagnosis`, and rendering it — step 2, which also adds the `plan_tool.audit_shapes` import this step deliberately withholds and corrects this module's "cycle-free leaf" docstring paragraph.
- Threading real `declared_step_ids` and real per-step status from a parsed plan at the CLI layer — step 4. This step's tests use fixture status data only.
- Updating CLAUDE.md, `docs/ARCHITECTURE.md`, `docs/how-to/pipeline/audit.md`, and closing out `BACKLOG.md` #264 — step 5.
- The residual `_matches` tier-1 misattribution risk (two unrelated findings sharing a `step<N>` anchor token *and* the same `[audit-step:N]` tag value) — an accepted, inherent property of reusing `_matches` unchanged, per the plan's own Risks section, not something this step (or any step in this plan) closes.
