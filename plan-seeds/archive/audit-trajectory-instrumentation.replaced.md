> **Replaced**, and the plan it produced was **withdrawn 2026-08-08** — its
> premise did not survive measurement. See
> `docs/implementation-plans/archive/2-audit-trajectory-instrumentation.withdrawn.md`
> for the disproof, and BACKLOG #172 for the re-premised remainder.
> **This seed is a known-bad example, kept deliberately:** its opening claim
> ("two co-dependent gaps share one substrate") asserted a coupling that was a
> shared *data source*, not shared implementation — the exact error BACKLOG #249
> tightens `create`'s split decision against. Preserved here for history; do not
> edit, and do not re-run it.

# Audit-trajectory instrumentation: infer hand-resolutions from report diffs, and trend on stable finding identity

## Outcome

A finding a session closes by hand (the mandated #85 hand-apply path) becomes
visible to calibration as a resolution event, and `plan-tool convergence`
stops reporting `spinning` for a plan whose finding *identities* all close
round over round — even when several distinct findings land on the same
step.

## Overview

Two co-dependent gaps share one substrate: the sequence of saved completeness
sidecars for a plan. **Hand-resolution inference** records, at audit-save
time, that a finding present in the previous saved sidecar and absent from
this one was resolved — the mandated Claude-session-driven hand-apply path
(CLAUDE.md § "Distinguish a Claude-session-driven run...") produces zero
`apply-verdict` telemetry, so today every hand-closed finding is invisible to
the calibration pipeline that tunes materiality thresholds from outcomes.
**Identity-aware convergence trends** fix the diagnostic's region-matching:
`convergence_diagnosis._matches` keys primarily on step focus
(`_finding_step_focus` — `step_id`, then an anchor's `step<N>` token), so two
*distinct* findings landing on the same step merge into one recurring
region. A dense step where finding A closes and finding B opens reads as one
region that never shrinks — `spinning`, when the truth is two closed-out
findings and normal churn.

Both fixes read the same saved-sidecar sequence; hand-resolution inference is
also what feeds identity-aware trending its closure evidence (a `RunFinding`
whose id vanished between saves is exactly the "closed" state the trend
needs and today infers only from an `Annotation`, which a hand-apply never
writes).

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
plan/code fingerprint capture), load the **immediately prior** saved
completeness sidecar for the same plan (`review_persistence.list_saved_reviews`,
newest-first, skip the one about to be written). For every `Recommendation.id`
present in that prior sidecar's `plan-correctness`/`plan-completeness`
findings and **absent** from the current save's findings, with at least one
commit landed between the two saves' timestamps (a same-commit re-audit is
not evidence of a hand-apply — nothing could have changed), record one new
`DecisionEvent`: kind `"hand-resolution"`, decision `"inferred"`, the
resolved finding's stable id and `step_id`/`anchor` as join context, tagged
distinctly from `APPLY_VERDICT_KIND` so `telemetry_analysis.py`'s calibration
can weight inferred evidence differently from an observed apply verdict (an
inference is weaker evidence — BACKLOG #172's own risk note). Wire it into
`resolve_decision_inline`'s evidence map alongside the existing
`apply-verdict` / `escalate-split` / `granularity` branches so it flows
through the existing `resolve_decisions` → `aggregate_decisions` pipeline
with no second calibration path.

An id absent because a *different* finding now occupies the same anchor/step
(a re-audit surfacing new prose at an old location) must not be misread as a
resolution of the old one — the id equality is the whole test; nothing about
anchor or step_id substitutes for it.

### Identity-aware convergence trends

`recurring_regions`/`_matches` (`convergence_diagnosis.py`) must stop letting
step focus alone merge two findings with different stable ids into one
region. Findings that carry the same id across consecutive runs are
definitively the same recurring finding; findings on the same step with
*different* ids are evidence of two things happening at once, not one thing
recurring, and the region-building must split them accordingly. Keep the
existing three-tier fallback (step focus → anchor → fuzzy title) for the
cases id-continuity cannot decide — a finding whose wording changed enough to
mint a new id while remaining "the same issue" in substance is a real,
named limitation, not a case to paper over with a fuzzy id-distance match.

Region *closure* additionally consults hand-resolution inference: a region
whose last-run finding id was recorded as hand-resolved (this seed's other
half) counts as closed for the round it disappeared, the same way an
`Annotation`-resolved finding already does in `_is_resolved_in_run`.

## In scope

`plan_tool/convergence_diagnosis.py` (region-building identity keys,
closure), `plan_tool/cli/completeness_phases.py` (the audit-save diff against
the immediately prior sidecar), `plan_tool/telemetry.py` (the new
`DecisionEvent` kind), `plan_tool/telemetry_analysis.py` (the new evidence
branch in `resolve_decision_inline`), `DATA_CONTRACT.md`, `tests/`.

### Scope contract

- **Binary observable, in one sentence:** a `Recommendation.id` present in
  the immediately prior saved completeness sidecar for this plan and absent
  from the current save, with at least one commit landed between the two
  saves' timestamps, is recorded as exactly one `hand-resolution` decision
  event naming that id. Presence/absence over two persisted id sets plus a
  commit count — nothing about *why* the id disappeared.
- **Allowed behavior changes:** the new `hand-resolution` telemetry kind and
  its `resolve_decision_inline` branch; the convergence diagnostic's region
  boundaries and closure verdict on identity-stable trajectories. Nothing
  about finding content, severity, or the audit loop's applied set.
- **Allowed reorganization:** none.
- **Verification:** § Testing.
- **Stop / defer:** § Deferred, and anything the iteration loop surfaces
  outside this fence goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied
  as plan expansion.

### Not allowed — enumerated, because stating the principle does not hold it

Per CLAUDE.md § "Validating a semantic property you cannot observe". Each of
these is a finding that is **invalid, not deferrable**:

- judging whether a hand-resolution was a *correct* fix, only whether the id
  disappeared with a commit between saves;
- inferring hand-resolution from anything but exact id equality — no
  anchor-only, step-only, or fuzzy-title substitute for the id check;
- treating an inferred `hand-resolution` event as equal-weight to an
  observed `apply-verdict` event anywhere in calibration — it is distinctly
  tagged and stays distinctly weighted;
- any new operator-facing bookkeeping verb (an explicit `resolve --anchor` is
  named and explicitly deferred below);
- any gate, exit-code change, or refusal to advance keyed on the diagnostic's
  new verdict — `plan-tool convergence` remains advisory, exactly as today;
- changing `completeness-apply`'s dispatch, the fork classifier's remedy
  selection, or any severity/materiality threshold.

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
  commit-between-saves gate already requires *some* change landed; a
  same-commit re-audit records nothing. A prompt-revision-driven mass id
  churn is a known residual risk, not eliminated by this design — name it in
  the saved event context (which decision context fields are new is #171/#4
  territory) so calibration can later discount a burst.
- **Id-stability assumption across schema versions** — a legacy sidecar
  saved before a finding-id scheme change may not carry a comparably-stable
  id. Verify id stability across the report versions this repo has shipped
  before trending on it (named directly in BACKLOG #172).
- **Region-splitting regressions** — tightening region identity from
  step-focus to id-primary risks *under*-merging a genuinely recurring
  finding whose id drifted for cosmetic reasons, turning a real spin into
  several short-lived regions that never trip the recurrence window. Guard
  with the fuzzy-title fallback tier, retained per Architecture above, and
  a fixture pinning the drift-tolerant case in § Testing.

## Testing

- **Hand-resolution inference:** an id present in sidecar N and absent from
  sidecar N+1 with a commit between → one `hand-resolution` event naming
  that id; the same pair with **no** commit between → none; an id absent
  because it never existed in sidecar N → none (only disappearance counts).
- **Calibration integration:** replay the `jira-grade-01-detail-instrument`
  sidecar history as a fixture — 23 `hand-resolution` events must be
  inferred, and `resolve_decisions` must resolve them as acted-on evidence
  distinct from `apply-verdict` rows.
- **Region identity, by mutation:** two findings with different stable ids
  on the same step across two runs → two regions, not one; the same finding
  id recurring across runs, same step → one region (unchanged from today);
  a finding whose id changes but title stays near-identical → still one
  region via the fuzzy-title fallback tier.
- **Convergence verdict:** the `jira-grade-01-detail-instrument` fixture
  must report `converging` (or the severity-aware low-yield equivalent), not
  `spinning`, once both fixes are wired; a fixture with a genuinely
  recurring same-id finding across the window must still report `spinning`.
- **Id-stability:** a fixture spanning the report schema versions this repo
  has shipped confirms stored ids compare equal across versions for an
  otherwise-unchanged finding.

## Acceptance criteria

- A finding closed by hand between two completeness audits is recorded as
  one `hand-resolution` decision event, distinctly tagged from
  `apply-verdict`, and reachable through the existing `resolve_decisions`
  calibration pipeline.
- Two distinct findings sharing a step across audit rounds no longer merge
  into one recurring region; each is tracked, and closes, independently.
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
