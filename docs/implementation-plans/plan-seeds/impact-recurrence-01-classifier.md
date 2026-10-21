# Impact-recurrence classifier — offline, no loop wiring (#158, part 1 of 2)

> **Superseded (2026-08-11):** do not author from this seed. Shipped in
> `docs/implementation-plans/2-convergence-non-severity-advisories.md` as a
> recommend-only advisory (`classify_impact_recurrence` in
> `plan_tool/convergence_diagnosis.py`, not a separate `impact_recurrence.py`
> module). Hard loop-terminating `structural_stop` was **withdrawn** with
> BACKLOG **#158** closed (2026-08-11) — soft pause + chat, not a machine stop.

Re-seed of `2-impact-recurrence-structural-stop.md`, which the audit loop
diagnosed as **spinning / structural** (2026-07-20): four regions recurred
across three passes and none of them resolved to a single step, because every
one of them is a **contract that straddles 3–4 steps**. This seed carries the
first half of BACKLOG **#158** at an altitude where each contract lands whole
inside one step.

## Why the previous decomposition failed (do not repeat it)

The replaced plan decomposed **by code artifact** — promote helpers → carry a
field → new module → renderer → `should_continue` → completeness → reconcile →
docs — so each *design contract* was spread across several steps and no audit
finding could ever localize. The recurring regions were:

- `reuse-audit-double-count` — **two independent mechanisms** each let one real
  audit fill two window slots, and the plan never stated a counting rule at all:
  (a) `_resolve_audit_reuse` in `plan_tool/cli/completeness_cmd.py` reuses a
  *saved* audit by default (only `--no-reuse-audit` opts out), so the current
  pass replays an older on-disk run that also stays in the history; (b) every
  completeness invocation persists **two** `kind="completeness"` sidecars
  (`write_pre_apply_audit_checkpoint` and the final `save_review`) carrying the
  same conceptual recs. Owned jointly by step 3 (window rule) and step 6
  (history builder) → unfixable in either.
- `unattempted-seam-evidence` — step 6 required "the seam was offered to
  `completeness-apply`, or has a non-open resolution annotation", which step 3's
  own eligibility (`resolved-in-newest` disqualifies) makes unsatisfiable — and
  `completeness-audit` writes no annotations at all.
- `step3` / result contract — step 4 read `convergence_diagnosis.RegionTrend`
  while step 3 forbade its producer; step 4's picker branched on "two or more
  distinct step numbers" while step 3 exposed at most one seam with one focus.
- `reconcile-window-scope` — reconcile's window fills from iterations *inside
  one invocation*, completeness's spans invocations; the plan asserted one
  three-pass rule and never named the asymmetry.

**The re-cut rule:** one plan owns the *evidence and verdict* end-to-end and
proves itself offline against synthetic histories; a second plan (part 2) owns
*loop integration*. Nothing in this plan changes any loop's behavior.

## Outcome

A public, deterministic `plan_tool/impact_recurrence.py` that, given a plan slug
and a caller-declared pass series, returns one frozen verdict record answering:
*has the same still-open high-impact seam recurred without shrinking across
three consecutive compatible passes, and what is the recommended remedy?* No
caller is wired to it; no loop behavior changes.

## Decisions this seed settles (the plan must not re-open them)

These are the questions the replaced plan left unmade; leaving them unmade is
what made it spin.

1. **A "pass" is one real audit, not one sidecar and not a replay.** One
   invariant, stated once, covering both double-count mechanisms: the window
   builder collapses each invocation's checkpoint/final sidecar pair into a
   single pass, **and** a pass whose recommendations are a replayed reused audit
   either excludes its on-disk origin run or does not extend the streak. The
   counting rule lives in the same step as the window rule — never in a caller.
2. **Openness is decided by eligibility alone.** A seam is eligible when it is
   present and unresolved in the newest pass. There is **no** "offered to
   apply" marker, and this plan does not introduce one; the replaced plan's
   `unattempted-seam-evidence` requirement is **dropped** as unsatisfiable.
3. **Provenance is derived on read, so the classifier is live immediately.**
   `Recommendation.impact` is already persisted (existing sidecars carry
   `"impact": "high"` rows). Do **not** claim a conservative ramp-in period —
   there is none. Conservatism comes from the three-pass window and the
   still-open + no-shrinkage conditions, and the plan's risk prose must say so.
4. **The classifier owns its own result type.** It does not consume, produce, or
   re-shape `convergence_diagnosis.RegionTrend`. Whatever the renderer needs is
   a field on the classifier's own frozen record.
5. **At most one seam, one optional step focus.** The recommendation has exactly
   two arms: a resolved focus → recommend a localized `plan-tool split` /
   `plan-tool scope-out`; no resolved focus → recommend conservative
   re-decomposition. There is no multi-step arm.
6. **The series scope is a caller-supplied input, not an inference.** The
   classifier is told which report kind and which invocation-vs-iteration scope
   its passes come from; it never guesses. This is what keeps completeness's
   cross-invocation window and reconcile's within-invocation window from being
   one unstated rule (part 2 declares each).
7. **Helper promotion is pulled, not pushed.** Any `convergence_diagnosis.py`
   helper this classifier needs is made public **in the step that consumes it**,
   with the consumer's call site landing in the same step. There is no
   speculative promote-ten-helpers step authored before the consumers exist.

## In scope

- `plan_tool/impact_recurrence.py` (new) — window/series builder with pass
  de-duplication, eligibility, recurrence + no-shrinkage trend, the frozen
  verdict record, and the recommend-only next-action rendering.
- Whatever narrow, consumer-driven public promotion of
  `plan_tool/convergence_diagnosis.py` history/matching helpers the above
  requires — landing with its consumer.
- `plan_tool/telemetry.py` — the `structural-stop` decision family constants
  only, if the verdict record is what part 2 will record. No recording call
  site here.
- `tests/test_impact_recurrence.py`, plus any characterization test needed to
  pin a promoted helper's unchanged behavior.

## Out of scope / non-goals

- **Any loop wiring** — `plan_tool/convergence.py:should_continue`,
  `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`,
  `plan_tool/cli/reconcile.py` are untouched. That is part 2.
- Changing `recurring_regions`, `diagnose_convergence`, or `classify_fork`
  semantics for the existing severity/decomposition classifier — it keeps its
  current verdicts unchanged for the same histories.
- Extending `convergence.is_blocking_impact` or the calibrated impact policy to
  any new caller (see the convergence policy boundary in `CLAUDE.md`).
- Any structural mutation — no split, scope-out, merge, re-ground, or re-seed is
  applied; the verdict is recommend-only.
- A resolution-annotation or "offered to apply" marker on conceptual findings
  (decision 2 above) — file it separately if it is ever wanted.
- Fuzzy identity matching for a seam whose region identity drifts, measured
  region-size shrinkage, backfilling provenance onto historical rows, an
  operator-tunable pass threshold, a second telemetry/evidence store, and any
  `--jobs`/parallel surface.
- Unifying this verdict with the offline `convergence_diagnosis.py` spinning
  verdict — the two stay distinct and may disagree.

## Allowed behavior changes

None. This plan adds an unreferenced module and, at most, makes existing private
helpers public without changing what they compute. No command's output, exit
code, or convergence behavior changes.

## Allowed reorganization

Only the consumer-driven privacy change in decision 7 — a helper becomes public
because a named new call site needs it, in that call site's step. No moves, no
re-homing, no `convergence_diagnosis.py` restructuring.

## Verification

Synthetic persisted histories drive every case, with no Claude and no loop:

- The trigger: three consecutive compatible passes, same region, explicit
  `impact=high` in each, still open in the newest, not shrinking.
- Each near-miss continues normally: two passes, a non-consecutive gap, an
  incompatible series, a shrinking count, resolved-in-newest,
  declined-in-newest, missing/legacy impact, and an uncorrelatable row.
- The **double-count** cases, one test each: a history containing both the
  checkpoint and final sidecar of the same invocation collapses to one pass; and
  a reused/replayed audit does not manufacture a second pass. In both, the
  trigger does **not** fire a pass early.
- **Anchor-less history:** a pass whose findings carry no `anchor` (see the
  `_PLAN_AUDIT_KEY_RE` defect in `BUG_BACKLOG.md`) degrades to the weaker
  matching tier without crashing, and does not silently *extend* a streak it
  cannot confirm.
- Both recommendation arms, including that the printed command carries its
  placeholder caveat when it is not runnable as printed.
- The existing severity/decomposition classifier returns byte-identical verdicts
  for every one of those histories.

## Stop / defer

Out-of-scope discoveries become `BACKLOG.md` / `BUG_BACKLOG.md` entries, not
plan expansion. They block this plan only if current supported behavior cannot
otherwise be preserved.

## Backlog reconciliation

BACKLOG **#158** is **closed**: the classifier/advisory pause signal shipped in
`docs/implementation-plans/2-convergence-non-severity-advisories.md`
(`classify_impact_recurrence` in `plan_tool/convergence_diagnosis.py`). Hard
loop-stop integration was **withdrawn** with that closure — do not author from
this seed.
