# Plan seed: classify audit findings as stale-spec vs design-gap

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/audit-finding-staleness-classification.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

> **Scope boundary — the prose half already shipped.** The conceptual-audit
> prompt (`plan_tool/prompts/plan-audit.md`) was already extended to make the
> auditor *say in the finding body* when the plan body merely lags an
> already-decided detail file ("name the direction", "surface the resolving
> constraint", "quote both sides"). That guidance changes what the auditor
> *writes*, not what the tool can *route on*. This plan is the **machine-
> readable** half: a parsed classification dimension the report, the walk, and
> the convergence gate can act on. Do not re-do the prose guidance here.

---

## Overview

Give every conceptual-audit finding a parsed **kind**: is it a *stale-spec*
mismatch (the plan body lags a deliberate decision a detail file already
documents — the remedy is a one-line prose fix in a known direction) or a
genuine *design-gap* (a concept that is missing, unsound, or undecided — the
remedy needs author judgment)? Today both wear the same `SEVERITY` token and
the same triage chrome, so a one-sentence body fix stalls the operator with
the same weight as a real gap. Carry the distinction as a first-class field
so the **report groups it**, the **walk surfaces it**, and the **convergence
triage gate can stop treating a stale-spec drift as a blocking finding**.

## Problem statement — grounded in real cases

The `feature-health-declaration-and-smell-checks` audit surfaced
`[suppression-cooccurrence-signal]` as a **MEDIUM** completeness finding: the
plan body said the suppression check "should weight a co-occurring signal to
raise match confidence", but step 2's detail had already deliberately scoped
that signal to "rationale enrichment, not a gate" — and the check has a single
`info` severity with a binary match, so there is *no confidence dimension to
weight*. The finding was therefore a **closed question**: the only coherent
remedy was a one-line edit to the stale body. Yet it presented as a live
MEDIUM conflict ("reconcile the body and step 2"), indistinguishable in weight
from `[self-referential-dogfood]` (a genuine coverage gap) sitting two bullets
above it. The operator had to read both the body and the detail file to
discover the finding was already decided. A machine-readable `kind` would have
let the tool collapse that finding's weight and route it straight to a
known-direction prose apply.

A second case (`login-with-quickbooks`, 2026-09-01, sibling repo) is
adjacent rather than identical, and is recorded here because it shows the
same underlying gap — "nothing marks a finding resolved" — surfacing one
lifecycle stage earlier. A bare-plan (Gate 1) CRITICAL finding said a step
couldn't distinguish "same person" from "different person" without a new
identity column, and named that addition in its own `Fix:` line. `detail`
later resolved the identical concern with a different mechanism — an
existing global-uniqueness constraint — that the finding's framing never
anticipated. Gate 2 correctly didn't re-flag it, but nothing said so; the
only way to know was grepping the finding's own vocabulary through the
detail bundle by hand and cross-checking that Gate 2's report stayed silent
on it. Had the finding's own suggested fix been applied mechanically instead
of hand-triaged, it would have added a needless schema migration for a
problem `detail` was already capable of solving without one.

**This case is not itself a `stale-spec` instance** — `kind` classifies a
plan/detail mismatch both artifacts already contain at one audit's snapshot;
this finding was live and correct at Gate 1, and only became resolved by a
`detail` decision that hadn't happened yet, so no single audit pass ever saw
both sides to classify. It corroborates the problem this plan targets
(findings need a legible resolution signal) without being solved by this
plan's mechanism — the tool still has no way to say "Gate 1 finding X was
closed by Gate 2, here's how" across separate invocations. That's a
narrower, distinct follow-on worth a maintainer's separate judgment call,
not a reason to widen this plan's scope.

## Why the prose guidance alone is insufficient

The shipped prompt guidance makes the auditor *describe* staleness in words.
But the tool can't grep prose for "this is stale" reliably, and three consumers
need a structured signal, not a sentence:

- The **convergence iterate loop** (`plan_tool/convergence.py`,
  `auto_reconcile.py`) decides what blocks on `BLOCKING_SEVERITIES`
  (`{"medium","high","critical"}`). A stale-spec MEDIUM should not hold the
  loop open the way a real MEDIUM gap does.
- The **report** (`plan_tool/completeness_report.py`) groups findings by
  section/severity; stale-spec drifts deserve their own low-friction bucket
  ("the spec lagged a decision — apply to resync"), not burial among design
  gaps.
- The **walk** (`plan_tool/review_walk.py`) triages each finding interactively;
  it should label a stale-spec finding and offer the known-direction apply
  without the operator decoding the conflict.

## Design

### The new dimension

Add a finding `kind` with (at least) two values:

- `stale-spec` — the plan body / a detail file lags a decision the *other*
  artifact already documents; the remedy is a directional prose fix (resync the
  lagging side). Direction is knowable from the audit.
- `design-gap` — a concept that is genuinely missing, unsound, internally
  contradictory, or undecided; the remedy needs author judgment. **This is the
  default** for every existing finding and any finding emitted without the new
  token.

Keep the value set small and closed; treat any unrecognized/absent value as
`design-gap` (the conservative "needs judgment; don't auto-collapse" default),
mirroring how `_triage_level` maps unknown impact/complexity to `-1` ("no
signal; don't skip").

### Where it is produced and parsed

- **Prompt** (`plan_tool/prompts/plan-audit.md`): extend the machine-parsed
  triage tag the auditor already emits — today `(impact=<l>, complexity=<l>)`
  — to carry the kind, e.g. `(impact=low, complexity=low, kind=stale-spec)`.
  Instruct the auditor to emit `kind=stale-spec` **only** when a detail file or
  the code at HEAD already documents the decision the body lags (it must cite
  which) — otherwise `kind=design-gap`. Keep the tag the *last* element so the
  existing "keep these two sections last" / machine-parse contract holds.
- **Parser** (`plan_tool/review.py:_split_triage_tags` and the `check_plan_audit`
  path around the `Recommendation` build): parse the optional third token,
  default missing → `design-gap`, tolerate the legacy two-token tag unchanged.
  Add `kind` to the `Recommendation` dataclass (`review.py:279`) beside
  `impact`/`complexity` as `Optional[str]`.

### Where it is consumed (the payoff)

- **Convergence gate** (`plan_tool/convergence.py`): a stale-spec finding does
  not count toward `is_blocking` even at MEDIUM — its remedy is mechanical and
  directional, so it should auto-apply (or be excluded from the blocking set),
  not hold the iterate loop open. Preserve the exit-code convention: this never
  flips rc; `--fail-on-findings` stays the only opt-in.
- **Report** (`plan_tool/completeness_report.py`): give stale-spec findings a
  distinct, low-friction grouping/label so the disposition summary separates
  "spec lagged a decision (resync)" from "design gaps (your judgment)".
- **Walk** (`plan_tool/review_walk.py`): surface the kind on the finding's meta
  line (alongside the impact/complexity pair already shown) and, for stale-spec,
  present the known-direction apply plainly. `apply_finding` is a prose editor
  and resyncing a lagging body is exactly a prose edit, so stale-spec stays
  apply-eligible without new machinery.

## Out of scope

- **Re-doing the prompt's prose guidance** (name-the-direction / surface-the-
  constraint / quote-both-sides) — already shipped.
- **The interactive meta-line impact/complexity display** — already shipped.
- **Auto-applying design-gap findings** — those still need author judgment; only
  stale-spec gets the collapsed-weight / known-direction treatment.
- **New finding sources or detector heuristics** — this reclassifies existing
  conceptual-audit findings; it adds no new check.

## Risks

- **Auditor over-tags `stale-spec`.** Severity: correctness/UX. A finding
  mislabeled stale-spec would dodge the blocking gate and auto-resync prose that
  actually needed judgment. Mitigation: require the auditor to *cite the detail
  file / HEAD evidence* that already documents the decision before it may emit
  `kind=stale-spec`; default everything else to `design-gap`; keep it advisory
  (never flips rc).
- **Backward-compatible parse.** Severity: correctness. Saved reports and
  legacy two-token triage tags must parse unchanged. Mitigation: the third
  token is optional; absent → `design-gap`; add a parser test pinning the
  legacy tag.
- **Blocking-gate behavior change.** Severity: scoping. Excluding stale-spec
  from `BLOCKING_SEVERITIES` changes when the iterate loop converges.
  Mitigation: scope the exclusion to `kind=stale-spec` only; design-gap MEDIUM
  still blocks exactly as today; cover with a convergence test.

## Acceptance criteria

- The conceptual-audit triage tag carries an optional `kind=` token; the
  auditor emits `kind=stale-spec` only with cited evidence that the lagging side
  is already decided, else `kind=design-gap`.
- `Recommendation` gains a `kind` field; `_split_triage_tags` / `check_plan_audit`
  parse it, default missing → `design-gap`, and parse a legacy two-token tag
  byte-identically to today.
- A `stale-spec` finding is excluded from the convergence blocking set (does not
  hold the iterate loop open) while a `design-gap` MEDIUM blocks as before; the
  exit-code convention is preserved (rc reflects completion, not findings).
- The completeness report groups/labels stale-spec findings distinctly from
  design gaps.
- The walk surfaces the finding kind and offers the known-direction apply for
  stale-spec.
- No new import cycle; `convergence.py` stays a leaf below `review.py`.

## References

- `plan_tool/prompts/plan-audit.md` — source prompt that emits the audited
  finding tags this seed classifies.
- `plan_tool/convergence.py` — current blocking policy that consumes finding
  severity during convergence.
</content>
</invoke>
