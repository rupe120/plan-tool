> **Withdrawn 2026-08-08 — the motivating premise is false.** Measured by
> replaying the real archived `jira-grade-01-detail-instrument` sidecar history
> through `diagnose_convergence` at every point in its history: HEAD reports
> `converging` on **0 of 24** prefixes as `spinning`, never once, with zero
> recurring regions throughout — so the `spinning` verdict this plan exists to
> fix does not reproduce. Worse, the plan's own remedy *causes* the symptom:
> widening `recurring_regions` to conceptual sources spins **15 of 24**
> prefixes, and the id-primary split changes no verdict anywhere (identical
> prefixes with and without it). The two halves are also coupled the inverse of
> this plan's claim — `_freeze_region` derives `closed` solely from annotations,
> which the hand-apply path never writes, so the widening is unsafe *until*
> closure evidence exists. Full measurement:
> `.tmp/audit-trajectory-instrumentation.premise-measurement.md`; forward work
> re-premised in BACKLOG #172. Preserved here for history; do not edit.

---
title: Audit Trajectory Instrumentation
intent: 'A finding a session closes by hand (the mandated #85 hand-apply path) becomes
  visible to calibration as a resolution event, and `plan-tool convergence` stops
  reporting `spinning` for a plan whose finding *identities* all close round over
  round — even when several distinct findings land on the same step.'
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a `hand-resolution` telemetry event kind, its recorder, and its reader
  intent: Gives the pipeline a decision-event kind that is visibly distinct from `apply-verdict`,
    so an inferred resolution can never be counted as an observed one. Two functions,
    mirroring the existing `escalate-split`/`step-provenance` kinds' shape exactly —
    `record_hand_resolution(repo_root, *, plan_slug, resolved_id, anchor, plan_fingerprint=...)`
    (a thin `record_decision` wrapper, like `record_escalate_split`) and
    `read_hand_resolved_ids(repo_root, plan_slug) -> set[str]` (a read-only aggregation
    over `read_decisions`, like `read_step_provenance_titles` — step 5's only
    mechanical route to "was this id ever recorded as hand-resolved"; nothing else
    in the codebase exposes a per-id telemetry lookup, so without this reader step 5
    has nothing concrete to call).
  files:
  - plan_tool/telemetry.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Add a sidecar content-diff helper (plan/code fingerprint comparison)
  intent: Supplies the 'something actually landed between the two saves' gate by
    comparing already-captured `plan_fingerprint`/`code_fingerprint` digests —
    scoped to the plan's own watched files, unlike a repo-wide commit count —
    mirroring the existing `_code_drifted_since_prior` pattern, including its
    `code_fingerprint_present` gate — `SavedReview.code_fingerprint` alone is
    never enough (per `_code_drifted_since_prior`'s own docstring, "never dict
    truthiness" — a computed-but-empty map, `code_fingerprint_present=True`,
    is real evidence a docs-only plan's code footprint didn't change; an
    uncomputed one, `code_fingerprint_present=False`, is not evidence of
    anything and both can serialize as `{}`). Compare `code_fingerprint` only
    when both sides have `code_fingerprint_present=True`; when either side
    never computed it, `code_fingerprint` contributes no signal either way
    and the gate falls back to `plan_fingerprint` alone. Satisfied when
    **either** digest differs, not both — the plan's own primary, pre-code
    scenario (a hand-apply editing plan/detail prose) only ever changes
    `plan_fingerprint`; requiring both would silently refuse to record a
    hand-resolution for exactly that case.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: low
  change_type: feature
- id: 3
  title: Add the sidecar-to-sidecar finding-id diff that infers hand-resolutions
  intent: Puts the 'present in the prior sidecar, absent from this one' rule in one
    testable place, keyed on exact `Recommendation.id` equality and nothing else —
    with a bridging rule so a same-content, different-classification id change
    (the finding's fingerprint suffix unchanged, only its `plan-correctness`/
    `plan-completeness` prefix moved) is never misread as a resolution.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
- id: 4
  title: Record inferred hand-resolutions when a completeness audit saves its sidecar
  intent: Makes the mandated hand-apply path leave a trace, so a finding a session
    closes by hand stops being invisible to calibration. `list_saved_reviews`
    returns paths, not loaded sidecars, so finding the prior two completeness
    saves mirrors `completeness_report.resolve_reusable_audit`'s own walk
    exactly rather than a one-shot filter — pre-filter the returned paths by
    filename suffix `-completeness.json` (cheap, no I/O), then iterate loading
    each via `review_persistence.load_review`, checking
    `is_reusable_audit_sidecar` (`kind == "completeness" and
    is_pre_apply_checkpoint is False` — the full predicate, not just its
    checkpoint half) on each successfully loaded candidate, and take the first
    two eligible ones as the immediately-prior and second-most-prior sidecars.
    A `detail-reconcile`/`run-reconcile`/`review` sidecar between two
    completeness audits fails the filename pre-filter and is skipped, never
    silently treated as one of the two. A malformed sidecar raises
    `review_persistence.ReviewLoadError` on `load_review` — mirror
    `resolve_reusable_audit`'s own per-candidate handling exactly — catch it
    and continue to the next candidate (the walk keeps searching further back
    for two eligible sidecars), never abort the whole lookup on one bad file
    the way an unqualified no-op would. Hand-resolution inference degrades to
    recording nothing only when the walk exhausts available sidecars without
    finding two eligible ones — it never raises out of the hook, which the
    surrounding `_persist_and_present_report` save block's own guard (`except
    OSError` only) would not catch — so the enclosing `completeness-audit`
    call always completes and saves its own report regardless.
    `telemetry.record_decision`'s write side already swallows its own
    exceptions and needs no change. Requires two consecutive absences, not
    one, before recording — the fingerprint-diff gate alone is satisfied by
    *any* edit anywhere in the plan/detail bundle, so a session fixing one
    finding and re-auditing would otherwise validate every id that vanished
    that round — including one that simply wasn't re-surfaced by that single
    audit pass, not one that was actually resolved (see Risks). For every
    `Recommendation.id` present in the second-most-prior sidecar's findings
    and absent from both the immediately-prior save's findings and the
    current save's findings, call `telemetry.record_hand_resolution` (step 1);
    an id merely absent from the current save alone (not yet confirmed by a
    second absence) is not recorded this round, becoming a candidate for
    confirmation at the *next* save instead. A plan with fewer than two
    eligible prior completeness sidecars has no second-most-prior to check,
    so records nothing yet, unchanged from today.
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
- id: 5
  title: Feed hand-resolution events into analyze_finding_drift's calibration evidence
  intent: Wires hand-resolution into the pipeline that actually computes calibration
    — `telemetry_analysis.analyze_finding_drift` / `build_low_impact_demotion_lookup`
    — not `resolve_decisions`/`aggregate_decisions`, which is a separate,
    materiality-blind telemetry surface `analyze_finding_drift` never reads.
    `analyze_finding_drift`'s only existing outcome path (`_selected_outcome`)
    requires a *later* `run-reconcile` snapshot for the same `step_id` and
    otherwise marks the finding `unresolved` — exactly the plan's own measured
    case (23 hand-closed findings, no intervening `run-reconcile`). Adds a
    second, independent outcome path, keyed on the origin's own stable
    `Recommendation.id` — not on `step`/`identity` (`_resolved_step`/
    `_origin_identity`, the run-reconcile path's own grouping keys) — the
    existing loop discards a finding as `unresolved` whenever `step is None`,
    before any hand-resolution check could run, and `step` is `None` for
    every `plan-correctness`/`plan-completeness` finding whose anchor isn't
    itself `step<N>`-prefixed — the audit prompt's own examples encourage
    plain concept slugs (`[cache-invalidation]`) with no step number, so this
    is the *common* case, not an edge case, for exactly the findings this
    plan hand-resolves. `Recommendation.id` has no such gap (`_make_rec_id`
    guarantees a non-empty id regardless of anchor shape), so the new path is
    keyed on `origin.id` throughout — independent of `step`/`identity` — and
    triggers whenever `drift_confirmed` is `False`, not merely whenever
    `selected is None` — `_selected_outcome` pairs purely by step number and
    timing, never by finding identity, so *any* later same-step
    `run-reconcile` — even about a wholly unrelated concern — claims the
    pairing slot for every finding anchored to that step, sending it through
    `drift_confirmed`/`_outcome_valid` instead of ever reaching the
    `selected is None` branch; the plan's own measured case shows this lands
    on `unresolved` (`outcome_evidence_valid=None`) for its own two named
    examples. So hand-resolution is checked at the point `drift_confirmed`
    is `False` — whether because no pairing exists at all, or one exists but
    doesn't confirm this exact finding — checking `origin.id` against
    `telemetry.read_hand_resolved_ids` (step 1) before falling through to
    `_outcome_valid`; a match there is `cleared`, taking precedence over the
    weaker `_outcome_valid` fallback. `drift_confirmed` itself is untouched —
    a finding a paired reconcile genuinely still shows stays `confirmed`
    regardless of any hand-resolution event. Grouped, never per occurrence,
    in both cases — keyed on `(finding_class, origin.id)`, keeping only the
    latest occurrence, mirroring the existing `(finding_class, step,
    identity, outcome_index)` grouping's own latest-wins rule — emits
    exactly one `cleared` observation per resolved id, not one per sidecar
    it survived before resolving. Updates `analyze_finding_drift`'s own
    docstring — quoted verbatim by this plan's Architecture as "intentionally
    independent of decision telemetry" — to name this one narrow, deliberate
    exception, so the claim stays true once this step lands.
  files:
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
- id: 6
  title: Widen recurring_regions to conceptual sources and split by finding id
  intent: Two independent fixes to `recurring_regions()` alone — never the shared
    `is_structural_source` function or the `_matches` helper it feeds
    (`telemetry_analysis._sidecar_outcome` calls `is_structural_source` directly
    to resolve `escalate-split`/`code-reveals-split` decisions, and `_matches`
    with a synthetic id that must keep matching on step-focus; widening either
    shared function would quietly widen that unrelated consumer too). First, add
    a new condition local to `recurring_regions`'s own scoping filter — `f.source
    in {"plan-correctness", "plan-completeness"}`, OR'd alongside the existing
    `is_structural_source(f.source)` check, never edited into
    `is_structural_source` or `STRUCTURAL_SOURCES` themselves — since those
    conceptual sources are exactly what this plan's measured case hand-resolves
    and `recurring_regions` drops today. Second, `recurring_regions` gets its
    own join predicate for the case both the candidate and an existing
    region's representative resolve a step focus — it cannot call `_matches`
    unmodified there, since `_matches`'s step-focus tier returns as soon as
    both sides agree on focus and never looks at `.id`, so two distinct
    same-step findings would still merge regardless of id. The new predicate —
    join iff ids are equal (post the id-reclassification bridge's
    fingerprint-suffix normalization from step 3, so an axis-only id change
    still joins) **or** titles clear the existing fuzzy-title cutoff; split
    into a new region only when both disagree. Reserve unmodified `_matches`
    (all three of its own tiers, untouched) for every other case — neither
    side resolves a step focus, *or* exactly one does (the "mixed" case — a
    region's representative carries a step-token anchor like `step3-ordering`
    while a later occurrence of the same issue is re-anchored with a plain
    concept slug, or the reverse — `_matches`'s own tier 1/tier 2 conditions
    both already require *both* sides to agree on focus-presence, so an
    unmodified call already falls through to its tier-3 fuzzy-title check for
    this case with no separate handling needed). This split alone delivers the "tracked and excluded from
    `spinning`, independently" acceptance criterion — once a region is keyed
    on a vanished id rather than a step, a hand-resolved finding's id never
    recurs in a later run, so
    `_region_spins`'s existing `latest_run_index in trend.run_indices` gate
    already excludes it from spinning — no separate closure mechanism is
    needed (see Architecture; a dedicated hand-resolution-closure step was
    dropped as a provable no-op). Third, disambiguates the split's own
    display — `_normalized_focus` (feeding both `RegionTrend.key` and
    `.focus`) derives purely from step, ignoring id, so two id-split regions
    sharing a step still collide on `focus`/`key`, and `_spinning_trend_lines`
    prints only `region.focus` as the sole region-identifying text in the
    `spinning` render — splitting the data model without this leaves the
    operator staring at two identical `step3` bullets, unable to tell which
    recurring concern is which, defeating the Problem statement's own
    complaint. Whenever more than one region built for the same series shares
    a `focus`, append a distinguishing suffix (representative id's
    fingerprint suffix, or its anchor) to that colliding set's `focus`/`key`
    only — a series with exactly one region per step keeps rendering plain
    `step<N>`, unchanged.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
- id: 7
  title: Replay the real jira-grade-01 sidecar history (test_convergence_diagnosis.py)
    as a fixture and check id stability across schema versions
  intent: Proves the plan's headline claim on the measured case — 23 hand-resolutions
    inferred, cleared via the hand-resolution-direct path added in step 5 (none
    of them pair with a `run-reconcile` snapshot in the fixture) as exactly 23
    `cleared` observations, not inflated by how many sidecars any of them
    survived before resolution — and `converging`, not `spinning` — confirms
    ids really do compare equal across the report versions this repo has
    shipped before anything trends on them, confirms the id-reclassification
    case (step 3) is not misread as a resolution, and confirms
    `telemetry_analysis._sidecar_outcome`'s escalate-split/code-reveals-split
    resolution (step 6's synthetic-id caller) still matches after the
    region-scope widening.
  files:
  - tests/test_convergence_diagnosis.py
  - tests/test_telemetry_analysis.py
  creates:
  - tests/fixtures/convergence/jira-grade-01-hand-resolution-history.json
  - tests/fixtures/convergence/id-stability-schema-versions.json
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  - 6
- id: 8
  title: 'Update the architecture and flow docs and close out BACKLOG #172'
  intent: Keeps the shipped region-identity and inference rules discoverable where
    readers already look, and removes the backlog entry this plan was authored from.
  files:
  - docs/ARCHITECTURE.md
  - docs/AUDIT_FLOW.md
  - CLAUDE.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 7
---
# Audit Trajectory Instrumentation

## Overview

Two co-dependent gaps share one substrate: the sequence of saved completeness
sidecars for a plan. **Hand-resolution inference** records, at audit-save
time, that a finding present in the previous saved sidecar and absent from
this one was resolved — the mandated Claude-session-driven hand-apply path
(CLAUDE.md § "Distinguish a Claude-session-driven run...") produces zero
`apply-verdict` telemetry, so today every hand-closed finding is invisible to
the calibration pipeline that tunes materiality thresholds from outcomes.
**Identity-aware convergence trends** fix `recurring_regions`'s region
grouping (never the shared `_matches` helper itself — see Architecture for
why): today it scopes to structural sources only, so the conceptual findings
this plan cares about never reach it, and when it does apply, `_matches`
keys primarily on step focus (`_finding_step_focus` — `step_id`, then an
anchor's `step<N>` token), so two *distinct* findings landing on the same
step merge into one recurring region. A dense step where finding A closes
and finding B opens reads as one region that never shrinks — `spinning`,
when the truth is two closed-out findings and normal churn.

Both fixes read the same saved-sidecar sequence and the same id-presence
signal: hand-resolution inference (steps 1, 3, 4) detects a finding id
present in one completeness sidecar and absent from the next; identity-aware
trending (steps 3, 6) uses that same id-continuity to stop two distinct
findings on one step from merging into a single recurring region. Splitting
regions by id alone already gives a resolved finding's region independent,
automatic exclusion from `spinning` once its id stops recurring — no
separate hand-resolution-triggered closure step is needed (see Architecture).

## Problem statement

Measured 2026-07-22 on `jira-grade-01-detail-instrument`: 23 conceptual
findings were closed by hand across audit rounds 2–4, and **no finding
survived a round** — materiality decayed monotonically round over round.
`plan-tool convergence` reported `spinning` anyway and recommended a
destructive re-seed, because `recurring_regions` conflated distinct closed
findings on steps 3 and 7 into two regions that never emptied, and
hand-applies record no apply verdict for calibration to read.
`plan-tool telemetry` confirmed the blindness directly: 44/44 apply-verdict
events resolved (from other work in the same window) vs. **every** calibration
row `insufficient-evidence` and 9/9 convergence diagnoses still `open`. The
better an operator follows the mandated session-driven policy, the blinder
both instruments get — a structural inversion, not noise. Full evidence:
`.tmp/jira-grade-01-detail-instrument.audit-process-handoff.md`.

## Architecture

### Hand-resolution inference

At the point `plan-tool completeness-audit` saves a new sidecar
(`cli/completeness_phases.py`'s persist path, alongside the existing
plan/code fingerprint capture), find the **immediately prior** and
**second-most-prior** saved completeness sidecars for the same plan.
`review_persistence.list_saved_reviews` returns paths, not loaded sidecars —
`.kind`/`.is_pre_apply_checkpoint` only exist after `load_review` — so this
mirrors `completeness_report.resolve_reusable_audit`'s own walk exactly
rather than a one-shot filter: pre-filter the newest-first paths by filename
suffix `-completeness.json` (cheap, no I/O — `list_saved_reviews` returns
every saved sidecar for the plan regardless of kind, since
`review`/`detail-reconcile`/`run-reconcile`/`completeness` share one reports
directory), skip the one about to be written, then iterate loading each via
`load_review`, checking `is_reusable_audit_sidecar` (`kind == "completeness"
and is_pre_apply_checkpoint is False` — the full predicate, not just its
checkpoint half) on each successfully loaded candidate, and take the first
two eligible ones. A `detail-reconcile`/`run-reconcile`/`review` sidecar
landing between two completeness audits — normal sequencing in this repo's
own detail→run→completeness-audit workflow — fails the filename pre-filter
and is skipped, never silently treated as one of the two. A pre-apply
checkpoint is crash-recovery evidence written moments before the run's own
final save and carries the same findings, so treating it as a distinct prior
or current audit would fabricate churn (`load_report_history` excludes
checkpoints from region history via `_is_final_report_role` for the same
reason). A malformed sidecar raises `review_persistence.ReviewLoadError` on
`load_review` — mirror `resolve_reusable_audit`'s own per-candidate handling
exactly: catch it and continue to the next candidate, searching further back
for two eligible sidecars, rather than aborting the whole lookup on one bad
file.

**Two-consecutive-absence corroboration.** A single vanished id is not, by
itself, strong enough evidence: the fingerprint-diff gate below is satisfied
by *any* edit anywhere in the plan/detail bundle, so a session that fixes
one finding and re-audits would validate every id that vanished that same
round — including one that simply wasn't re-surfaced by that one audit
pass, not one genuinely resolved (see Risks). So the diff spans the
second-most-prior sidecar found above too. For every `Recommendation.id`
present there and **absent from both** the immediately-prior save's findings
**and** the current save's findings — two consecutive absences, not one —
with **either** of the second-most-prior and current sidecars'
`plan_fingerprint` or `code_fingerprint` genuinely differing — not both
required, since the plan's own primary pre-code scenario only ever changes
`plan_fingerprint` (step 2's helper — reusing the digests both saves already
capture, not a repo-wide commit count: an unrelated commit elsewhere in an
active shared repo must not satisfy this gate, the fingerprints are already
scoped to the plan's own watched files, and `code_fingerprint` is compared
only when both sides have `code_fingerprint_present=True` — never dict
truthiness, mirroring `_code_drifted_since_prior`'s own gate exactly — so an
uncomputed capture on either side never masquerades as "unchanged"), call
`telemetry.record_hand_resolution` (step 1) with the resolved finding's
stable id and `anchor` as join context (`step_id` is always `None` on a
`plan-correctness`/`plan-completeness` `Recommendation` — the extractor
stamps it that way unconditionally, so `anchor` is the only real join
signal; record `step_id` anyway for schema symmetry with other decision
kinds, understanding it never carries information here), tagged distinctly
from `APPLY_VERDICT_KIND`. An id absent only from the current save (not yet
confirmed against a second-most-prior sidecar) records nothing this round —
it becomes a candidate re-checked at the *next* save, once a genuine
second-most-prior comparison is available for it. A plan with fewer than
two eligible prior completeness sidecars has no second-most-prior to check
yet and records nothing, unchanged from today.

**Id-reclassification bridge.** `Recommendation.id` splices the finding's
axis (`plan-correctness` vs `plan-completeness`) into the id string itself
(`_make_rec_id`, `review.py`), so a finding that is re-audited and reclassified
from one axis to the other — same underlying issue, same fingerprint suffix,
different id prefix — looks exactly like the old id resolving and a new
finding appearing. Before recording a resolution, check whether the current
save's finding set contains an id sharing the *same fingerprint suffix* as
the vanished id but a different axis prefix; if so, this is a reclassification,
not a resolution, and no `hand-resolution` event is recorded for it. Step 6's
fuzzy-title fallback tier is a *separate* mechanism (region identity, not
resolution inference) and does not substitute for this check — a title
staying similar across a reclassification is coincidental, not guaranteed.

**Where hand-resolution evidence actually goes** (step 5, not the
`resolve_decisions` pipeline — see below): `analyze_finding_drift`'s only
existing route to `confirmed`/`cleared` pairs an origin finding with a
*later* `run-reconcile` snapshot for the same `step_id` (`_selected_outcome`)
— but that pairing is by step number and timing alone, never by finding
identity, so *any* later same-step `run-reconcile` — even about a wholly
unrelated concern — claims the pairing slot for every finding anchored to
that step. The paired snapshot is then checked for `drift_confirmed` (does
it still contain this exact finding, via `_strict_finding_match`, excluding
any `redirect_present` match); when it doesn't — the ordinary case for an
unrelated reconcile — resolution falls to `_outcome_valid(outcome)` alone,
which the plan's own measured `jira-grade-01-detail-instrument` history
shows lands on `unresolved` for its own two named examples
(`step3-authority-grep-criterion`, `step7-test-review-declaration`): both
are hand-resolved well before an unrelated same-step `run-reconcile` lands
with `outcome_evidence_valid=None`. Step 5 makes hand-resolution the check
that runs at exactly this point — **whenever `drift_confirmed` is `False`**,
whether because no run-reconcile pairing exists at all (`selected is None`)
or because one exists but doesn't confirm this finding — checking
`origin.id` against `telemetry.read_hand_resolved_ids` (step 1) before
falling through to `_outcome_valid`; a match there is `cleared` on the
matching `FindingClassDriftSignal`, taking precedence over the weaker
`_outcome_valid` fallback. `drift_confirmed` itself is untouched: a finding
a paired reconcile genuinely still shows stays `confirmed` regardless of any
hand-resolution event, since it demonstrably hasn't gone away. Grouped, not
per-occurrence, in both cases: whether an origin lands in the
`selected is None` branch or the paired-but-not-confirmed branch, the check
groups every origin occurrence sharing `(finding_class, origin.id)` and
keeps only the latest one before emitting a single observation — mirroring
how the existing `(finding_class, step, identity, outcome_index)` grouping
already avoids over-counting a paired finding — so one real resolution
yields exactly one `cleared` observation, never one per sidecar it survived
before resolving. `resolve_decision_inline`/`resolve_decisions` is *not*
touched — see the note below on why.

An id absent because a *different* finding now occupies the same anchor/step
(a re-audit surfacing new prose at an old location) must not be misread as a
resolution of the old one — the id equality (past the reclassification bridge
above) is the whole test; nothing about anchor or step_id substitutes for it.

### Why calibration evidence goes to `analyze_finding_drift`, not `resolve_decisions`

The plan's diagnosed blindness — "every calibration row `insufficient-evidence`"
— is `analyze_finding_drift`'s own `FindingDriftAnalysis.calibration` output,
which feeds `build_low_impact_demotion_lookup` (the mechanism
CLAUDE.md's "Convergence policy boundary" names as what actually "tunes
materiality thresholds from outcomes"). That function's own docstring states
it is "intentionally independent of decision telemetry" — it matches
`RunFinding`s straight off saved sidecar history via `_strict_finding_match`
and never reads a `DecisionEvent`. `resolve_decisions`/`aggregate_decisions`
is a real, useful pipeline (it is how `apply-verdict`/`escalate-split`/
`granularity` decisions get resolved and reported), but it is not the
materiality-calibration surface, and wiring hand-resolution into it — as an
earlier draft of this plan did — would leave `plan-tool telemetry`'s
`calibration:` section exactly as blind as the Problem statement describes,
even after every other step here lands.

### Identity-aware convergence trends

Two independent fixes, both inside `recurring_regions()`'s own logic
(`convergence_diagnosis.py`) — **never inside the shared `_matches` helper**.
`_matches` has a second, structurally different consumer:
`telemetry_analysis._sidecar_outcome` calls it with a synthetic `RunFinding`
carrying a hardcoded `id="decision-focus"` (`_decision_focuses`) to resolve
`escalate-split`/`code-reveals-split` decisions by step focus alone; that id
can never equal a real `Recommendation.id`, so gating `_matches` itself on id
agreement would permanently break that resolution path. Both fixes below
therefore live in the scoping/grouping logic `recurring_regions` owns, not in
`_matches`.

**Scope widening.** `recurring_regions` filters every run's findings to
`is_structural_source(f.source) and is_blocking(f.severity)` before matching,
and `is_structural_source` (`STRUCTURAL_SOURCES = {"granularity-split",
"structural-split"}` plus the legacy `detail-purity` alias) never includes
`plan-correctness` or `plan-completeness` — so the 23 conceptual findings this
plan's own measured case hand-resolves never reach `recurring_regions` today,
and no change to region-matching alone can make that fixture replay as
`converging`. Widen *only* a new condition local to `recurring_regions`'s own
scoping filter — `f.source in {"plan-correctness", "plan-completeness"}`,
OR'd alongside the existing `is_structural_source(f.source)` check — and do
**not** edit `is_structural_source` itself or the `STRUCTURAL_SOURCES`
constant it wraps: `is_structural_source` is also called directly by
`telemetry_analysis._sidecar_outcome` to resolve `escalate-split`/
`code-reveals-split` decisions (the exact consumer this plan's own Testing
section requires to keep matching by step focus, unchanged, after this
change), and `STRUCTURAL_SOURCES` separately gates `review.is_structural`.
Widening either shared name would quietly widen that unrelated consumer too.
`recurring_regions` has exactly one caller chain (`build_region_trends` →
`diagnose_convergence`), so this widening's effect is contained to
convergence diagnosis and fork classification — which is the intended,
direct effect: `plan-tool convergence` starts trending on recurring
conceptual findings the same way it already trends on recurring structural
ones, consistent with how CLAUDE.md's own "spinning"/`FORK_*` guidance
already assumes a conceptual finding can be the thing that's recurring.

**Id-primary region identity.** Within that widened scope, two findings that
carry the same stable id across consecutive runs are definitively the same
recurring finding; two findings on the same step with *different* ids are
evidence of two things happening at once, not one thing recurring, and
region-building must split them accordingly instead of merging on step focus
alone. `recurring_regions` needs its **own** join predicate for this, not a
call to `_matches` unmodified: `_matches`'s tier 1 returns as soon as both
sides resolve the same step focus (`c_focus == r_focus`) without ever
consulting `.id`, so calling it unmodified would still merge two distinct
same-step findings regardless of id — `_matches` itself stays untouched
(`telemetry_analysis._sidecar_outcome`'s synthetic `id="decision-focus"`
resolution still needs its unmodified step-focus tier). The new predicate,
for the case both the candidate and an existing region's representative
resolve a step focus: join iff their ids are equal — comparing *post* the
id-reclassification bridge's fingerprint-suffix normalization above, so an
axis-only id change still joins — **or** their titles clear the existing
`_title_ratio`/`TITLE_SIMILARITY_CUTOFF` fuzzy check; split into a new
region only when both the id and the fuzzy-title check disagree. This is
what keeps the fuzzy-title fallback reachable at all for a same-step pair:
every `plan-correctness`/`plan-completeness` `Recommendation` carries a
non-empty id (`_make_rec_id`), so a plain "id decides, full stop" rule would
never let the fuzzy-title tier fire for exactly the case it exists to
protect — a finding whose wording changed enough to mint a new id while
remaining "the same issue" in substance (a real, named limitation, see
Risks). Reserve unmodified `_matches` (all three of its own tiers) for every
other case — neither side resolves a step focus, or exactly one does (the
"mixed" case: one occurrence of a finding carries a step-token anchor,
a later occurrence of the same underlying issue is re-anchored with a plain
concept slug, or the reverse). `_matches`'s own tier 1 and tier 2 both
already require *both* sides to agree on focus-presence before either
fires, so an unmodified call already falls through to its tier-3
fuzzy-title check for the mixed case with no separate handling needed —
only the both-resolve case needs the new predicate above.

**Display disambiguation.** The split above is a data-model fix only; the
render needs a matching one or it is invisible to the operator.
`_normalized_focus` (feeding both `RegionTrend.key` and `.focus`) derives
purely from step focus and ignores id, so two id-split regions on the same
step both compute the identical `focus`/`key` (e.g. both `step3`), and
`_spinning_trend_lines` prints only `region.focus` as the sole
region-identifying text in the `spinning` render — the Problem statement's
own complaint (conflated, unreadable regions) for the one surface a human
actually triages from. After building a series' regions, whenever more than
one shares a `focus`, append a distinguishing suffix (the representative's
id fingerprint suffix, or its anchor) to that colliding set's `focus`/`key`
only; a series with one region per step keeps rendering plain `step<N>`,
unchanged.

Region *closure* needs no additional hand-resolution consultation. `_freeze_region`
computes `RegionTrend.closed` from `_is_decline_close` (a deliberate WONTFIX
annotation) plus an "every match in the region's last occupied run was
applied" check — not from `_is_resolved_in_run`, which feeds a separate pair
of advisories and is never called from `_freeze_region`. What actually keeps
a hand-resolved finding's region out of `spinning` is presence, not `closed`
— `_region_spins`'s own docstring says the `closed` check runs *first*, but
the verdict is order-independent (`and` of independent booleans): a
hand-resolved finding is by definition absent from the run that resolved
it, so `latest_run_index in trend.run_indices` fails regardless of `closed`'s
value. Once regions are split by id (above) rather than by step, a resolved
id's region simply stops recurring in `run_indices` from that point on and
fails the presence check on its own — independent, automatic exclusion from
spinning, with no dedicated closure mechanism required.

## References

- [Python difflib — Helpers for computing deltas](https://docs.python.org/3/library/difflib.html) — SequenceMatcher.ratio() and get_close_matches(word, possibilities, n, cutoff) are the standard-library basis for the retained fuzzy-title fallback tier in convergence_diagnosis._matches, including the cutoff semantics the drift-tolerant fixture pins.
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Field defaults, default_factory, frozen instances, and asdict() — the mechanics for adding the new hand-resolution DecisionEvent kind and its join-context fields without breaking existing serialization of telemetry rows.
- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — load/dump, custom default= encoders and object_hook decoders, and sort_keys for byte-stable output — relevant to reading prior saved completeness sidecars and appending the new event kind in a way DATA_CONTRACT.md's drift guard can compare.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- An explicit `resolve --anchor` verb for operator-confirmed resolution —
  inference must work with zero operator bookkeeping; an explicit verb is a
  independent follow-up (§ Deferred).
- Weighting inferred `hand-resolution` events in calibration policy beyond
  "distinctly tagged" — the weighting curve is its own entry once evidence
  accumulates.
- The severity-aware low-yield stopping rule, the arm-clustering advisory,
  and every other judgment-only audit shape in CLAUDE.md's registry table —
  untouched by this seed.
- Any change to how `completeness-audit --iterate` applies findings.

## Risks

- **False resolutions from an id churn unrelated to the fix** — a finding's
  wording changed for reasons other than being resolved (e.g. an upstream
  detector prompt revision minted new ids repo-wide). Mitigation: the
  fingerprint-diff gate (step 2) already requires the plan's own watched
  content to have genuinely changed; an unrelated repo-wide commit no longer
  satisfies it (tightened from the original commit-count design specifically
  because it did not have this property). A prompt-revision-driven mass id
  churn *within* the plan's own watched files remains a known residual risk,
  not eliminated by this design — name it in the saved event context so
  calibration can later discount a burst.
- **Id-reclassification churn** — a finding's id changes because its axis
  (`plan-correctness` ⇄ `plan-completeness`) was reclassified on re-audit,
  not because it resolved; `_make_rec_id` splices the axis into the id
  itself, so this is a distinct, structural churn mode from wording drift
  above. Mitigation: the fingerprint-suffix bridge in Architecture, pinned by
  a fixture reproducing the exact observed `jira-grade-01` case (a finding's
  id moving from a `plan-plan-correctness-*` to a `plan-plan-completeness-*`
  form with its fingerprint suffix unchanged).
- **Id-stability assumption across schema versions** — a legacy sidecar
  saved before a finding-id scheme change may not carry a comparably-stable
  id. Verify id stability across the report versions this repo has shipped
  before trending on it (named directly in BACKLOG #172).
- **Region-splitting regressions** — tightening region identity from
  step-focus to id-primary risks *under*-merging a genuinely recurring
  finding whose id drifted for cosmetic reasons, turning a real spin into
  several short-lived regions that never trip the recurrence window. Guarded
  by the fuzzy-title check running alongside (not merely a distant fallback
  behind) id equality per Architecture above, and a fixture pinning the
  drift-tolerant case in § Testing.
- **Region-scope widening changes convergence behavior for every plan, not
  just this one** — `recurring_regions` widening to conceptual sources is a
  shared-function change (single caller chain, but that chain is
  `plan-tool convergence`'s entire diagnosis for every plan). A plan whose
  conceptual findings recur for legitimate reasons (e.g. a genuinely
  unresolved design question repeatedly re-surfaced) will now be visible to
  `spinning`/`FORK_*` classification where it previously was not — this is
  the intended effect, not a side effect, but it is a behavior change beyond
  this plan's own fixture and should be called out in step 8's docs update.
- **Batch-edit masking** — the fingerprint-diff gate is satisfied by *any*
  edit anywhere in the plan/detail bundle, not by an edit to the content the
  vanished finding was about. A session that fixes one finding and re-audits
  changes `plan_fingerprint` for every id that vanished that round,
  including one that simply wasn't re-surfaced by that single audit pass —
  distinct from the id-churn/reclassification risks above, since no
  replacement id of any kind appears here for those mitigations to catch.
  An inflated `cleared` count skews `confirmed_rate` toward
  `build_low_impact_demotion_lookup`'s low-impact-demotion threshold in
  exactly the wrong direction: a finding class that keeps recurring for real
  reasons could read as reliably self-clearing. Mitigation: step 4's
  two-consecutive-absence corroboration (Architecture) — a single round of
  absence is never sufficient on its own. Residual risk: two consecutive
  audit passes both missing the same real finding is rarer but not
  impossible; not eliminated by this design, only reduced.
- **Final-round gap** — the two-consecutive-absence design (Architecture,
  "Two-consecutive-absence corroboration") only records a hand-resolution
  once a third sidecar (N+2) confirms an id is still absent after N+1. A
  plan whose auditing stops right after the round that actually resolved a
  finding — the id vanishes at N+1 and no N+2 completeness audit ever runs
  — never gets that resolution corroborated or recorded, unlike the other
  residual risks above this hits exactly the tail of a plan's history where
  hand-resolutions cluster once a plan nears done. Not mitigated by this
  design; accepted as a structural tradeoff of requiring corroboration at
  all (see the Batch-edit masking risk above for why a single-absence
  design isn't the alternative).

## Testing

- **Hand-resolution inference:** an id present in sidecar N, absent from
  sidecar N+1, and *still* absent from sidecar N+2 (two consecutive
  absences), with *either* `plan_fingerprint` or `code_fingerprint` of N and
  N+2 genuinely differing (including the plan's own primary case — only
  `plan_fingerprint` differs, `code_fingerprint` identical, no code written
  yet) → one `hand-resolution` event naming that id, recorded at N+2's save
  (not N+1's); **both** fingerprints identical → none; `code_fingerprint`
  never computed on one side (`code_fingerprint_present=False`) with
  `plan_fingerprint` also identical → none — an uncomputed capture must not
  read as "unchanged code" or "changed code," it contributes no signal
  either way; an id absent from
  N+1 but *reappearing* in N+2 → none, and it is never recorded later either
  (its single-round absence was not real); an id absent because it never
  existed in sidecar N → none (only disappearance counts); either sidecar
  being a pre-apply checkpoint → none (checkpoints are excluded from every
  side of the diff); a `detail-reconcile`/`run-reconcile`/`review` sidecar
  saved between two completeness audits → fails the `-completeness.json`
  filename pre-filter and is skipped, so the window still spans two genuine
  eligible prior completeness sidecars, not an interleaved one; fewer than
  two eligible prior completeness sidecars in the plan's history → none yet.
- **Malformed-sidecar skip, by mutation:** the immediately-prior candidate
  raising `ReviewLoadError` on `load_review` → that candidate is skipped
  (not treated as absent evidence), the walk continues to an older eligible
  sidecar for the second-most-prior slot, and a hand-resolution is still
  recorded if two eligible, non-raising sidecars are found further back;
  every remaining candidate raising → hand-resolution inference records
  nothing this round (not enough eligible sidecars), and the enclosing
  `completeness-audit` call still completes and saves its own report rather
  than raising.
- **Batch-edit false-positive, by mutation:** an id present in sidecar N,
  absent from N+1 (because that pass simply didn't re-surface it, not
  because it resolved), with an *unrelated* finding's fix in the same round
  changing `plan_fingerprint` → no `hand-resolution` event recorded at N+1's
  save; the same id reappearing in N+2 → confirms it was never resolved,
  and no event is recorded at N+2's save either — the single-pass miss
  never produces a false positive regardless of how many unrelated edits
  land in between.
- **Id-reclassification bridge, by mutation:** a finding's id moving from
  one axis prefix to the other with the same fingerprint suffix → no
  `hand-resolution` event recorded for the old id, and the new-axis id is
  not treated as a brand-new finding either; the same id truly vanishing
  with no same-suffix replacement on any axis → one event, as normal.
- **Calibration integration:** replay the `jira-grade-01-detail-instrument`
  sidecar history as a fixture — 23 `hand-resolution` events must be
  inferred, and each must land as `cleared` evidence on its matching
  `FindingClassDriftSignal` in `analyze_finding_drift`'s output via the new
  hand-resolution-direct path (none of these 23 findings pair with a
  `run-reconcile` snapshot in the fixture, so the existing `_selected_outcome`
  path alone must *not* be what clears them) — not as a
  `resolve_decisions`/`aggregate_decisions` row, which this plan does not
  wire hand-resolution into. The `cleared` total these events contribute
  must equal 23, not the number of sidecar occurrences summed across them.
- **Cleared-count multiplicity, by mutation:** a finding present in three
  consecutive completeness sidecars before being hand-resolved → exactly one
  `cleared` observation on its `FindingClassDriftSignal`, not three; the same
  finding present in only one sidecar before resolution → still exactly one;
  an occurrence with no run-reconcile pairing and no hand-resolution event →
  still `unresolved`, unchanged from today.
- **Non-step-anchor clearing:** a hand-resolved finding whose anchor is a
  plain concept slug (`[cache-invalidation]`, no `step<N>` token, so
  `_resolved_step` returns `None`) → still `cleared`, not `unresolved` —
  the hand-resolution path must not require `step`/`identity` to resolve.
- **Unrelated-run-reconcile precedence, by mutation:** a step-anchored
  hand-resolved finding whose step later gets a `run-reconcile` snapshot
  about a *different* concern (`_selected_outcome` still pairs on step
  number and timing alone, so `selected` is not `None`, but
  `drift_confirmed` is `False` since the paired snapshot's own findings
  don't match this one) → still `cleared` via the hand-resolution check, not
  `unresolved` via `_outcome_valid`; the same finding when the paired
  reconcile's findings *do* still show it (`drift_confirmed` is `True`) →
  stays `confirmed`, hand-resolution event or not — a paired reconcile that
  actually confirms the finding is never overridden.
- **Region identity, by mutation:** two findings with different stable ids
  and dissimilar titles on the same step across two runs → two regions, not
  one; the same finding id recurring across runs, same step → one region
  (unchanged from today); two findings with different ids but near-identical
  titles on the same step → still one region, via the fuzzy-title check
  overriding the id mismatch; a region whose representative resolves a step
  focus matched against a candidate that doesn't (or the reverse) → joins or
  splits purely on unmodified `_matches`'s fuzzy-title tier, the same as the
  neither-resolves case.
- **Region display disambiguation:** two id-split regions sharing a step →
  their `RegionTrend.focus`/`.key` differ (not both literal `step<N>`), and
  the printed `spinning` render (`_spinning_trend_lines`) shows two visibly
  distinct bullets for them, not two identical `step<N>` lines; a series with
  only one region on a given step still renders that region's `focus` as
  plain `step<N>`, unchanged from today.
- **Region-scope widening:** a `plan-correctness`/`plan-completeness`
  finding recurring across runs on the same step, with no structural
  finding present, now appears as a region (verifiably absent before this
  plan); a `granularity-split`/`structural-split` finding's region behavior
  is unchanged.
- **`_matches` shared-consumer regression guard:** `_sidecar_outcome`'s
  synthetic `id="decision-focus"` resolution of an `escalate-split`/
  `code-reveals-split` decision still matches by step focus after the
  region-scope widening — `_matches` itself is unchanged; only
  `recurring_regions`'s own scoping/grouping moved.
- **Convergence verdict:** the `jira-grade-01-detail-instrument` fixture
  must report `converging` (or the severity-aware low-yield equivalent), not
  `spinning`, once both fixes are wired; a fixture with a genuinely
  recurring same-id finding across the window must still report `spinning`.
- **Id-stability:** a fixture spanning the report schema versions this repo
  has shipped confirms stored ids compare equal across versions for an
  otherwise-unchanged finding.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A finding closed by hand between two completeness audits is recorded as
  one `hand-resolution` decision event, distinctly tagged from
  `apply-verdict`, and lands as `cleared` evidence in
  `analyze_finding_drift`'s `FindingClassDriftSignal` output — the pipeline
  that actually feeds `build_low_impact_demotion_lookup` — not merely
  resolved through `resolve_decisions`.
- A hand-resolved finding is cleared even when its step later gets an
  unrelated `run-reconcile` snapshot that claims the pairing slot without
  confirming the finding — hand-resolution is checked whenever
  `drift_confirmed` is `False`, not only when no pairing exists at all.
- A finding's id changing only because its axis was reclassified
  (`plan-correctness` ⇄ `plan-completeness`) is never recorded as a
  hand-resolution.
- A single malformed prior-sidecar candidate (`ReviewLoadError`) is skipped,
  not treated as an absent-sidecar dead end — the walk continues to an older
  eligible sidecar, mirroring `resolve_reusable_audit`'s own per-candidate
  handling; hand-resolution inference records nothing only once eligible
  candidates are exhausted, and it never raises out of the
  `completeness-audit` save path, which must complete and save its own
  report regardless.
- A hand-resolved finding whose anchor carries no `step<N>` token is cleared
  the same as one that does — hand-resolution never depends on `step`/
  `identity` resolving.
- `analyze_finding_drift`'s docstring no longer unconditionally claims
  independence from decision telemetry once step 5 lands; it names the
  `hand-resolution` exception explicitly.
- `recurring_regions` tracks recurring `plan-correctness`/`plan-completeness`
  findings the same way it already tracks structural ones; two distinct
  findings sharing a step across audit rounds no longer merge into one
  recurring region — each is tracked, and excluded from `spinning`,
  independently once its own id stops recurring in `run_indices`.
- `_matches`'s synthetic-id consumer (`telemetry_analysis._sidecar_outcome`,
  resolving `escalate-split`/`code-reveals-split` decisions) is unaffected —
  `_matches` itself is not modified.
- Two id-split regions sharing a step render as visibly distinct lines in
  `plan-tool convergence`'s `spinning` output — `RegionTrend.focus`/`.key`
  never collide for two regions in the same series; a step with only one
  region still renders plain `step<N>`.
- The `jira-grade-01-detail-instrument` sidecar history replays as
  `converging`, not `spinning`, with 23 hand-resolution events inferred.
- A genuinely recurring same-identity finding across the recurrence window
  still reports `spinning` — the fix narrows false spins, it does not
  suppress true ones.
- `plan-tool convergence`'s exit-code behavior and its apply-or-recommend
  gate (`--apply-split` / `--apply-scope-out`) are unchanged.

## Deferred

- An explicit `resolve --anchor` operator verb.
- Weighting curves for inferred vs. observed resolution evidence in
  calibration.
- Any second consumer of the `hand-resolution` event kind beyond the
  convergence diagnostic and calibration.
- Extending identity-aware trending to the reconcile-kind series
  (`detail-reconcile` / `run-reconcile`) beyond whatever falls out of the
  shared `_matches` change — a reconcile series's own trajectory behavior is
  unmeasured and not this seed's claim to fix.
