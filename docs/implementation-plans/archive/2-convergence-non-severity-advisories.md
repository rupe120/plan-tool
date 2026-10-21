> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Convergence Non Severity Advisories
intent: '`plan-tool convergence` (and a matching completeness stderr note after `finalize_completeness_run`
  when a run-grade sidecar was written — audit-only or `--iterate`) prints **two recommend-only
  advisories** that stop operators from treating severity-clean as the only exit signal:
  1. **Impact-recurrence** — the same still-open, explicit-`impact=high` seam has
  recurred without shrinkage across three consecutive compatible completeness passes;
  name the seam and a conservative next action for discussion. 2. **Edit-drift / self-seeded
  rate** — across ≥3 compatible completeness reports, a strict majority of *new edit-drift-eligible*
  findings match the prior-apply set (binary observable below); name those findings
  and note that further hand-apply may not be addressing the conceptual problem. Neither
  advisory flips iterate `stop_reason`, `--fail-on-findings`, or exit code. Neither
  mutates plan structure. Neither revives `spinning` / `FORK_*` / region-trending.
  ---'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Carry impact field through RunFinding
  intent: Make explicit-impact=high evidence available to the downstream impact-recurrence
    classifier without changing any existing diagnostic or rendering behavior.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/convergence-non-severity-advisories/01-carry-impact-field-through-runfinding.md
  status: done
- id: 2
  title: Persist audit_stage, reuse-collapse correlator, and advisory result types
  intent: Make the compatible-pass window readable from history and shared by both
    classifiers. Persist an explicit audit_stage on every completeness sidecar at
    save time (unconditionally — not jira-grade-gated like detail_bundle_fingerprint),
    document it on SavedReview in DATA_CONTRACT.md, and build a correlator that (a)
    keeps completeness kind only, (b) groups by that persisted stage so a bare→detail
    change starts a new window, (c) collapses adjacent finals with identical finding-id
    sets (reuse-audit replays), and (d) exposes frozen result types. Checkpoint/final
    pairing stays load_report_history's job — do not re-implement it.
  files:
  - plan_tool/review_persistence.py
  - plan_tool/completeness_report.py
  - plan_tool/convergence_diagnosis.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_review_persistence.py
  - tests/test_completeness_report.py
  - tests/test_data_contract.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/convergence-non-severity-advisories/02-persist-audit-stage-reuse-collapse.md
  status: done
- id: 3
  title: Add impact-recurrence classifier
  intent: Detect when the same still-open explicit-impact=high seam recurs without
    shrinkage across three or more consecutive compatible completeness passes, so
    operators treating a severity-clean audit as the sole exit signal are warned about
    persistent high-impact seams. When several seams qualify, pick exactly one by
    deterministic tie-break (most passes present, then largest newest matched count,
    then lowest seam key from the first-seen finding’s source/anchor-or-step/title_slug).
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: RunFinding.impact field the classifier reads.
    2: Persisted stage + correlator pass sequence and the ImpactRecurrenceAdvisory
      result type.
  detail: docs/implementation-plans/plan-details/convergence-non-severity-advisories/03-impact-recurrence-classifier.md
  status: done
- id: 4
  title: Add edit-drift classifier
  intent: Detect when a strict majority of new edit-drift-eligible findings match
    the prior-apply set across three or more compatible reports, signaling that the
    audit loop is predominantly finding its own conceptual edits rather than the original
    artifact. Edit-drift-eligible findings use is_blocking_finding with the window's
    persisted audit_stage (same bar as _open_medium_plus) — not plain is_blocking,
    and not material_new/is_blocking_impact. Window is the newest three compatible
    reports. A finding is new only if `_matches` finds no match in the immediately
    prior pass. Zero eligible new findings never fires. Reuse-collapse targets --reuse-audit
    with --iterate (audit-only reuse skips the sidecar write at HEAD).
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Persisted stage + correlator pass sequence and the EditDriftAdvisory result
      type.
  detail: docs/implementation-plans/plan-details/convergence-non-severity-advisories/04-edit-drift-classifier.md
  status: done
- id: 5
  title: Wire both advisories into diagnose_convergence and render_diagnosis
  intent: Make both advisories visible on plan-tool convergence output alongside existing
    verdict, churn, and structural-recurrence information — without altering the headline
    verdict or any gate.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: Impact-recurrence classifier function to call from diagnose_convergence.
    4: Edit-drift classifier function to call from diagnose_convergence.
  detail: docs/implementation-plans/plan-details/convergence-non-severity-advisories/05-wire-both-advisories-diagnose.md
  status: done
- id: 6
  title: Surface advisories on completeness-audit stderr when history is sufficient
  intent: Let operators see impact-recurrence and edit-drift advisory signals during
    completeness-audit without requiring a separate plan-tool convergence invocation
    — loading history from disk is cheap and spends no Claude. The window includes
    the just-completed pass as newest so the advisory can fire on the run that completes
    a three-pass pattern.
  files:
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_completeness_cmd.py
  complexity: low
  change_type: feature
  depends_on:
  - 5
  depends_on_notes:
    5: Advisory fields on ConvergenceDiagnosis and the classifier + render infrastructure
      they depend on.
  detail: docs/implementation-plans/plan-details/convergence-non-severity-advisories/06-surface-advisories-on-completeness.md
  status: done
- id: 7
  title: Update BACKLOG entries and convergence policy docs
  intent: 'Record BACKLOG #158 closed as the recommend-only impact-recurrence
    pause advisory (hard loop-terminating recurring_high_impact_seam /
    structural_stop withdrawn — soft pause + chat, not a machine stop), record
    #248 edit-drift thin-advisory portion as shipped with hard exit still deferred
    to #231, archive or rewrite the blocked seeds docs/implementation-plans/plan-seeds/impact-recurrence-01-classifier.md
    and impact-recurrence-02-loop-stop.md as superseded by this plan, and update CLAUDE.md''s
    convergence policy boundary to name the two new non-blocking advisories.'
  files:
  - BACKLOG.md
  - CLAUDE.md
  - docs/implementation-plans/plan-seeds/impact-recurrence-01-classifier.md
  - docs/implementation-plans/plan-seeds/impact-recurrence-02-loop-stop.md
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/convergence-non-severity-advisories/07-update-backlog-entries-convergence.md
  status: done
---
# Convergence Non Severity Advisories

## Overview

This plan adds two recommend-only advisories to `plan-tool convergence` (and optional completeness stderr when evidence is already loaded — audit-only or `--iterate`) that alert operators when severity-clean convergence is not the only exit signal. The first, impact-recurrence, fires when the same still-open seam tagged with an explicit `impact=high` triage value on persisted recommendations has recurred without shrinkage across three consecutive compatible completeness passes. The second, edit-drift, fires when a strict majority of new edit-drift-eligible findings match the prior-apply set across ≥3 compatible reports. Neither advisory flips iterate `stop_reason`, `--fail-on-findings`, or exit code, and neither mutates plan structure or revives retired `spinning` / `FORK_*` / region-trending vocabulary.

## Problem statement

Today `plan-tool convergence` diagnoses convergence state using severity and finding counts, but two important non-severity signals go unreported: a seam whose persisted recommendations carry an explicit `impact=high` triage tag and that persists across passes without shrinking (not severity- or `is_blocking_impact`-driven recurrence), and an edit-drift pattern where new findings predominantly match prior-apply edits rather than the original artifact. Operators treating a severity-clean audit as the sole exit signal miss both patterns — continuing to hand-apply self-seeded findings or overlooking a recurring explicit-high-impact seam that warrants discussion. These are the non-severity signals the `#251` retirement of region-trending left unaddressed. Backlog sources: `#158` (impact-recurrence, rewritten post-`#251`), `#248` edit-drift exit (thin advisory only), related `#231` (hard-exit provenance — dependency named, not implemented here).

## Architecture

Both advisories are deterministic classifiers over persisted **completeness** report history — no Claude spend. They share a correlator that builds a logical pass sequence for both advisories.

**Compatible passes.** A pass is eligible only when `SavedReview.kind` is completeness (never detail-reconcile / run-reconcile) and every pass in the window shares the same **persisted** audit stage (`STAGE_BARE` or `STAGE_DETAIL`). Step 2 writes that stage onto every completeness sidecar at save time (unconditionally). Legacy sidecars without the field are excluded from advisory windows (insufficient evidence), not coerced from the live plan’s current bundle. A bare→detail stage change starts a new window; it must not read as seam shrinkage or resolution.

**Reuse collapse (not checkpoint/final pairing).** `load_report_history` already drops checkpoint roles before `RunSnapshot` construction (`docs/AUDIT_FLOW.md`). The remaining hazard is **`--reuse-audit` combined with `--iterate`**: each iterate acceptance still writes a new timestamped final sidecar with no replay marker (plain audit-only `--reuse-audit` sets `skip_sidecar_write` and does not grow history). Three identical reused finals under iterate would look like three confirming passes. The correlator collapses **adjacent final completeness passes whose finding-id sets are identical** into one logical pass. On collapse, keep the newer snapshot’s findings/`created_at`/`audit_stage`, and **merge `annotations` by finding id** for every id in either map: any terminal disposition under `_is_resolved_in_run` (applied or decline-close) from **either** merged raw final beats any non-terminal annotation; only when both sides are non-terminal or both terminal does the newer pass win. A fresh reuse replay that defaults `annotations={}` (or that writes explicit non-terminal/`open` markers) must not erase older terminal dispositions. Both advisories read only that collapsed sequence. Persisting an explicit reuse marker is allowed later but not required for this plan.

**Finding identity (shared).** Both classifiers match findings across passes with the existing convergence report-history matcher `_matches` in `plan_tool/convergence_diagnosis.py` (same id / source / title-ratio fallbacks it already implements — including `TITLE_SIMILARITY_CUTOFF`). Do **not** add a separate “≥2 shared significant title tokens” tier beside or under `_matches`; that would duplicate and drift from the live matcher. Risks that say “both classifiers” mean this shared `_matches` call. Tier-1 step-focus matching (same resolved `step_id` / `step<N>` anchor token) can conflate distinct sources or anchors on one step — accepted conservative tradeoff of reusing `_matches`, named in Risks.

**Impact-recurrence** tracks explicit-`impact=high` findings by that identity across the **newest three** consecutive compatible passes, firing when the same seam is still open in the newest pass with **no shrinkage**. Shrinkage is a drop in the **count of `impact=high` findings matched to that seam** — **open or closed**, the same `matched_count` step 3 uses for tie-break `newest_matched_count` — relative to the prior pass in the window; not severity, not step-span, and not open-only membership. A finding that remains in the pass after disposition still counts; removing it from the pass (or losing the `impact=high` tag) can shrink. Missing or legacy-unknown impact is insufficient — not a trigger. Names at most one seam plus an optional step focus; when several seams qualify, pick by **most passes present → largest newest matched count → lowest seam key**, where the seam key is the first-seen finding’s `(source, anchor_or_step, title_slug)` tuple with `anchor_or_step = step_id` when set, else `anchor` if set, else `""` (not a raw content-hash id — those are unstable across restatements).

**Edit-drift binary observable.** Over the **same fixed trailing window of the newest three** consecutive compatible reports (not the full history), a finding in the newest pass is *new* only if `_matches` finds no match in the immediately prior pass. The **prior-apply set accumulates only inside that three-pass window**: every finding whose disposition in any window pass is terminal hand work under `_is_resolved_in_run` (**`status == "applied"` or decline-close** — `_is_decline_close`: `status == "skip"` with empty `halt_reason`), union every finding present in pass *i* with no `_matches` hit in pass *i+1* for each adjacent pair inside the window. Match to the prior-apply set uses `_matches`. **Edit-drift-eligible** findings (deliberately not named “material” — that word means `material_new` / `is_blocking_impact` elsewhere) are those for which `is_blocking_finding(rec, stage=<window's persisted audit_stage>, classify_domain=...)` is true — the same stage-aware bar `_open_medium_plus` uses — evaluated over **sidecar-persisted** recommendations (`sidecar_recs` in `completeness_phases._persist_and_present_report`: correctness, conceptual, data-contract, concept-coverage, and medium `granularity-split` only). At bare stage that means medium `plan-completeness` is excluded while medium `data-contract` / `concept-coverage` / medium `granularity-split` rows in `sidecar_recs` remain eligible when `is_blocking(severity)` is true. Deterministic well-formedness findings (deps/file-check/detail-coverage and the rest of the no-Claude battery) are excluded because they are **not written into completeness JSON**, not because `classify_edit_drift` filters by source. `diagnose_convergence` always forwards a domain classifier into `classify_edit_drift` (default `lambda f: getattr(f, "domain", None) or "unknown"` when the caller omits it) so detail-stage demotion does not depend on live `audit_stage` resolution succeeding. Fires when a strict majority of new eligible findings match; **zero new eligible findings never fires**. No Claude; never grade prose quality.

Sibling `finding_churn` on `plan-tool convergence` still keys `_open_medium_plus` with `diagnose_convergence`’s **live** `audit_stage` for every snapshot; the two new classifiers use each pass’s **persisted** `audit_stage` inside the compatible window. After a bare→detail transition those bars can disagree on the same history — operators must not treat churn as the same eligibility bar as edit-drift.

A new leaf module may house correlator/classifier product logic if that keeps `convergence_diagnosis.py` free of `#158` product sprawl; no drive-by folder moves. Both advisories produce their own frozen result type — they do not consume, produce, or reshape retired `RegionTrend` / `recurring_regions` / `classify_fork` / `VERDICT_SPINNING`.

The `self-seeded-finding` entry in the audit-shapes registry stays `judgment_only` — this advisory raises the cost of a silent override but is not a gate. Both advisories render on `plan-tool convergence`; completeness stderr (step 6) surfaces them after any successful run-grade sidecar write from `finalize_completeness_run` — **audit-only and `--iterate` alike** — when the evidence is already loaded (no second Claude spend). Carve-outs: `--json` early-return, jira-grade, and `skip_sidecar_write`.

## Input

Consumes persisted completeness report history (saved sidecars from `completeness-audit`). Relies on: stable finding identity via `_matches` on `RunFinding` objects produced by `load_report_history`’s flatten path (`_finding_from_recommendation` copies the persisted `Recommendation` fields — including `impact` after step 1); disposition/applied markers when present; finding-id sets on consecutive final sidecars for reuse collapse; and — **after step 2 lands** — a persisted `audit_stage` on each completeness sidecar (step 2 adds the field to `SavedReview` / `DATA_CONTRACT.md`; it is not present on HEAD until that step). `review_persistence` / completeness report writers own sidecar I/O.

## References

- `plan_tool/convergence_diagnosis.py` — existing convergence diagnostic; the module both advisories extend (or call from a leaf).
- `plan_tool/convergence.py` — `is_blocking_finding` / `is_blocking_impact` and iterate stop-reason vocabulary the advisories must not alter; edit-drift eligibility uses `is_blocking_finding` with the window stage (same as `_open_medium_plus`), never plain `is_blocking` and never `material_new`.
- `plan_tool/review_persistence.py` — sidecar I/O for completeness report history and disposition markers.
- `plan_tool/audit_shapes.py` — the `self-seeded-finding` registry entry that stays `judgment_only`; edit-drift advisory complements but does not gate on it.
- `DATA_CONTRACT.md` — persisted `SavedReview.audit_stage` plus `Recommendation` schema including `impact`, finding identity, and disposition fields the classifiers consume.
- `docs/AUDIT_FLOW.md` — completeness-audit flow; checkpoint exclusion and where stderr advisory output (step 6) integrates.
- `BACKLOG.md` `#158` — impact-recurrence entry (rewritten post-`#251`); this plan ships it.
- `BACKLOG.md` `#248` — edit-drift exit note; this plan ships the thin advisory portion.
- `BACKLOG.md` `#231` — hard-exit provenance; named as the follow-up, not implemented here.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Reviving `spinning`, `FORK_*`, `recurring_regions`, or widening structural recurrence to conceptual sources (`#172` / `#251` settled).
- Loop-terminating stop reasons, exit-code flips, `--fail-on-findings` changes.
- Automatic split / scope-out / re-seed (`#159` / `#160` / `#168` / `#116` — re-premise separately).
- Hard edit-drift exit or durable apply→finding provenance (`#231`).
- Changing stage bars (`#91` / `#248` core shipped); reporting polish `#260`; four-loop consistency `#261`.
- Arm-clustering changes; Stage 5 / `#255` chat surface.
- Re-weighting severity assignment; pass-count reduction.
- Re-implementing checkpoint/final filtering already owned by `load_report_history`.

## Risks

- **Finding-identity instability across reports.** Both classifiers assume `_matches` can correlate findings across runs; if titles drift below `TITLE_SIMILARITY_CUTOFF`, classifiers produce false positives or negatives. Medium. Mitigated by using the single shared `_matches` implementation (no parallel token tier), but not fully eliminated.
- **`_matches` tier-1 step-focus conflation.** Distinct findings that share only a resolved step focus (`step_id` or `step<N>` anchor token) match regardless of title, source, or anchor slug — so unrelated findings on the same step can merge into one impact-recurrence seam or inflate edit-drift matches. Medium. Accepted conservative tradeoff of reusing `_matches`; operators should treat same-step advisories as discuss-first, not proven identity.
- **Edit-drift title-ratio over-matches.** `_matches`'s fuzzy title fallback can conflate unrelated findings, inflating the match count and producing a spurious edit-drift advisory. Low. Mitigated by the strict-majority threshold absorbing some noise.
- **Prior-apply set inference is lossy when disposition markers are absent.** The closed-between-passes proxy cannot distinguish an applied finding from one resolved by unrelated artifact change, inflating the prior-apply set. Low. Mitigated by the strict-majority threshold; the fallback is documented as approximate. Decline-close (`skip` + empty `halt_reason`) **does** join the prior-apply set via `_is_resolved_in_run`, parallel to applied — so a restated finding after an operator decline can still match.
- **Reuse-collapse under- or over-collapses.** Identical finding-id sets on adjacent finals under `--reuse-audit --iterate` may collapse a genuine second audit that happened to emit the same ids, or fail to collapse a reuse whose ids drifted slightly. Medium. Mitigated by step 2 tests of identical-set collapse and non-identical retention; an explicit reuse marker remains a future hardening, not this plan’s requirement. **Collapse must merge annotations** with terminal-beats-non-terminal precedence (see Architecture): a reuse replay that writes empty or explicit non-terminal annotations must not drop older applied/decline-close markers step 4’s prior-apply set and step 3’s open/resolved checks need.
- **Legacy sidecars lack `audit_stage`.** Pre-step-2 history cannot enter a compatible window. Low. Documented as insufficient evidence; operators re-audit after ship to build a staged window.
- **Save-time `audit_stage` vs conceptual-audit time.** Step 2 stamps `audit_stage` from bundle state at **persist** (`write_completeness_report` derive-at-write). Conceptual findings on an `--iterate` run are produced once at loop start — if apply rounds move bare→detail before the final sidecar is written, that pass’s persisted stage can disagree with the bar those findings were generated under (recommend-only false negative/positive on edit-drift eligibility only). Low. Mitigated by accepting save-time stage as the durable window key; operators re-audit after a bare→detail transition rather than trusting a mid-iterate stage flip.
- **Advisory noise desensitizes operators.** If the ≥3 pass minimum or strict-majority threshold fires too often on legitimate convergence patterns, operators learn to ignore the channel. Low. Both thresholds are conservative by design; the advisory is recommend-only with no gate, so a false fire costs attention, not correctness.

## Testing

- Synthetic fixture histories for impact-recurrence: fire case; multi-seam tie-break; each disqualifier (missing impact, shrinkage of matched high-impact count, resolved, <3 compatible passes, reuse-collapse of identical adjacent finals); plus an explicit **partial-close** fixture where one of two matched high-impact rows is disposition-closed but still present in the pass — `matched_count` does not drop, so no-shrinkage still holds if the seam remains open.
- Synthetic fixture histories for edit-drift: fire on strict-majority match inside the newest-three window; restated finding (new id, `_matches` hit) is not “new”; no fire on minority match, <3 samples, empty prior-apply set, **zero new eligible findings**, churn that fails `is_blocking_finding` (including rows never present in `sidecar_recs`), bare-stage medium `plan-completeness` excluded while bare-stage medium `data-contract` / `concept-coverage` / medium `granularity-split` in `sidecar_recs` remain eligible when `is_blocking(severity)` is true (pin with at least one non-`plan-completeness` fixture), or mixed kind/stage windows; long-history fixture proves prior-apply entries older than the trailing three drop out; **decline-close** disposition joins prior-apply the same way applied does.
- Compatible-window fixtures: reconcile kinds excluded; bare→detail persisted stage change breaks the window; missing `audit_stage` excludes the pass.
- Non-interference (step 6): a synthetic `completeness-audit --iterate` **and** an audit-only control whose saved history would fire both advisories keep the same `stop_reason` (iterate only), process exit code, and `--fail-on-findings` outcome as otherwise-identical runs with advisory stderr stubbed/empty — no feature-flag disable switch.
- Step 6 evaluates a window that **includes the just-completed pass** as newest (in-memory / post-save), so the advisory can fire on the run that completes the three-pass pattern.
- Mutation (step-owned): deleting the advisory render goes red (**step 5**); classifiers do not import retired fork/region APIs (**steps 3–4**).
- Existing suites in `tests/` must remain green.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- `plan-tool convergence` prints an impact-recurrence advisory when the same still-open, explicit-`impact=high` seam recurs without shrinkage (matched-seam finding count) across the newest three consecutive compatible completeness passes; multi-seam ties use most-passes → largest newest count → lowest first-seen seam key `(source, step_id-if-set-else-anchor, title_slug)`; render includes conservative discuss-first next-action language (no split / scope-out / re-seed commands — step 5).
- Compatible means completeness `kind` only and the same **persisted** `audit_stage` for every pass in the window (legacy missing stage → excluded).
- Every new completeness sidecar save writes `audit_stage` unconditionally once step 2 ships (documented in `DATA_CONTRACT.md`).
- `plan-tool convergence` prints an edit-drift advisory when a strict majority of new edit-drift-eligible findings (`is_blocking_finding` at the window’s persisted stage) match the prior-apply set inside the newest-three compatible window; “new” uses `_matches`; zero new eligible never fires; eligibility is not `material_new`; prior-apply includes applied **and** decline-close dispositions via `_is_resolved_in_run`; render cites majority counts (`matched_count` / `new_eligible_count`), names at least one matched finding, and includes hand-apply-may-not-help recommend-only language (no hard-exit / provenance claims — step 5).
- Completeness stderr after `finalize_completeness_run` (step 6 — audit-only and `--iterate` alike) includes the just-completed pass as the newest window member (carve-outs: `--json`, jira-grade, `skip_sidecar_write`).
- Neither advisory flips iterate `stop_reason`, `--fail-on-findings`, or exit code — proven for the completeness finalize surface (step 6) by the non-interference fixture.
- Neither advisory mutates plan structure.
- Neither advisory consumes, produces, or reshapes retired region-trending / fork vocabulary (do not revive `spinning` / `FORK_*` / `recurring_regions` / `RegionTrend` / `classify_fork`).
- Adjacent final completeness passes with identical finding-id sets collapse to one logical pass so reused-audit replays do not confirm a seam or edit-drift streak.
- Missing or legacy-unknown impact does not trigger impact-recurrence.
- Edit-drift match is fully deterministic — no Claude, no prose-quality grading; both classifiers share `_matches` (no parallel token-overlap tier).
- Optional completeness stderr (step 6) surfaces advisories after any successful run-grade sidecar write from `finalize_completeness_run` — audit-only and `--iterate` alike — when evidence is already loaded, without a second Claude spend — **except** the `--json` early-return path (no sidecar), jira-grade, and `skip_sidecar_write`.
- Final docs/status step records BACKLOG `#158` as **closed** (recommend-only
  pause advisory shipped; hard loop-terminating structural stop **withdrawn**
  2026-08-11 — soft pause + chat, not a machine stop), `#248` edit-drift thin
  advisory as shipped with hard exit deferred to `#231`, and archives/rewrites
  the blocked `impact-recurrence-0*` seeds as superseded.

## Deferred

- Hard edit-drift exit or remedy-causation provenance → `#231`.
- Hard impact-recurrence iterate stop (`structural_stop`) — **withdrawn with
  `#158` closed 2026-08-11**; do not re-open. Stronger pause / chat handoff →
  Stage 5 `interactive-chat-surface` seed if needed.
- Explicit on-disk reuse marker as an alternative to identical-id collapse → backlog if collapse proves insufficient.
- Re-seed actuation after a named seam → `#159` / `#160` / `#168` after their own re-premise.
- `docs/AUDIT_FLOW.md` prose for completeness-iterate stderr advisory lines (step 6 ships the emission; flow-doc update is post-ship doc work, deliberately not in step 7’s footprint).
- Valid out-of-scope findings surfaced during implementation → `BACKLOG.md` / `BUG_BACKLOG.md`, never plan expansion.
