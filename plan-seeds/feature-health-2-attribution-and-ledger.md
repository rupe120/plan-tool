# Plan seed: feature-health (2 of 2) — finding attribution + brittleness ledger

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/feature-health-2-attribution-and-ledger.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

> **Order:** this is **part 2 of 2**. Part 1 —
> [`feature-health-1-declaration-and-smell-checks.md` —
> **has shipped** (archived at
> `docs/implementation-plans/archive/2-feature-health-declaration-and-smell-checks.md`):
> the `Feature` model (`plan_tool/schema.py:59`), the `Plan.features` registry
> (`schema.py:185`), and the per-step `Step.features` tag (`schema.py:87`) all
> exist at HEAD, along with the author-time smell checks
> (`review.validate_feature_refs` / `detect_self_referential_features`). This
> part is the **payoff that was never built** — the convergence-gap layer: the
> registry today is a declared-and-lint-checked but otherwise **inert grouping
> key** (nothing attributes findings to it or tracks it across runs). This part
> delivers the original request: **detecting when a feature is a poor structural
> fit by tracking its findings across audits.**

---

## Overview

Give the completeness audit a **feature-level memory** so it can tell the
operator *which capability* a plan is struggling to express, and flag the
ones that are a poor structural fit before they churn the convergence loop
for hours. Two pieces, both building on part 1's `features:` declaration:
(1) **finding → feature attribution** so every audit finding carries the
`feature_id` it relates to; (2) a **brittleness ledger** that reads the
persisted `reports/` history, groups findings by feature across audits, and
surfaces the features showing the *escalation/fan-out* or
*persistent-recurrence* signatures that mark a capability that doesn't fit.

The feature is a **category** — a stable grouping key — and that is exactly its
job here: it survives the anchor-slug churn that defeats finding-level identity
(below). The whole point of the layer is to **trigger a human conversation**
("this capability keeps churning — revisit the request"), not to gate anything.

## Problem statement — grounded in a real case

The `merge-steps-executor` plan ran four completeness audits. A `type_impure`
concept escalated `HIGH → CRITICAL` and fanned out into three coordinated
sub-findings in a single audit, while spreading across three steps; it was
eventually cut. In parallel, a `_confirm_merge` non-TTY concept was flagged in
**all four** audits — never escalating, never dying — because the plan body
and the detail bundle kept contradicting each other.

Two distinct **brittleness signatures** emerge, and the tool surfaces neither
today:

- **Escalation + fan-out** (`type_impure`): rising severity *and* multiple
  concurrent sub-findings, with a growing step/file footprint. → the capability
  doesn't fit; the right move is **extract or cut**.
- **Persistent recurrence** (`_confirm_merge`): non-zero findings every audit,
  flat severity, because the concept is hard to specify consistently across
  surfaces. → **tighten the contract**, don't keep re-applying.

Neither is visible because the conceptual audit mints a **fresh anchor slug
every round** (`confirm-merge-wiring` → `merge-confirm-noninteractive` →
`confirm-merge-nontty-posture` → `confirm-merge-nontty-semantics`), so
recurrence cannot be tracked by anchor. A **stable key that survives
re-phrasing** is the missing primitive — and part 1's declared feature id is
exactly that key.

## Architecture

### Part A — finding → feature attribution

Add `feature_id: Optional[str] = None` to the `Recommendation` dataclass
(`plan_tool/review.py:279`), beside the existing `anchor` field
(`review.py:343`). It round-trips through the saved-report JSON exactly as
`anchor` does (`asdict` / `Recommendation(**r)`), so old reports without the
field still load (Optional default).

**Attribution is deterministic first, Claude-tagged only as a fallback.** This
is a sharper design than "let the audit name the feature": the finding→step link
the conceptual audit *already computes* makes most attribution free (mission
principle 3 — let code find the pattern). Resolve `feature_id` in this order,
stopping at the first that fires:

1. **Step-scoped finding (`step_id` present).** The candidate set is exactly that
   step's `step.features` tag — a *closed vocabulary*, one field lookup
   (ownership runs step → feature, no `features:`→step inversion).
   - `len(step.features) == 1` → attribute **deterministically**, zero Claude.
   - `len > 1` → Claude picks one id **from that closed set** (output validatable
     — must be one of the step's declared ids), so precision is high.
   - `len == 0` (untagged step) → fall to (3).
2. **Step-less conceptual finding that the audit already placed.** Crucially,
   `_parse_plan_audit_findings` **already back-fills a `step_id`** onto concept
   findings via `_attribute_concept_finding_step` (`review.py:3657`), which maps a
   finding's backticked path mentions through a `file_to_step` map built from DONE
   steps' `step.files` (`review.py:3772`, applied at `:3792`). So a finding that
   names a file isn't really step-less — it carries a derived step, and (1)
   applies to it for **free**. This covers a large share of "conceptual" findings
   with **no new Claude call**. (Note: `_attribute_concept_finding_step` keys on
   *DONE* steps; for a still-`planning` plan, generalize it — or add a sibling —
   to map against all steps' `step.files`/`creates`, since pre-execution audits
   are where the ledger earns its keep.)
3. **Genuinely unplaceable conceptual finding** (no backticked path, or no step
   owns the cited file) → Claude names the feature from the **registry**
   (`plan.features`). This is the *fallback*, not the primary path: only findings
   the file→step composition can't place reach it. Extend the conceptual-audit
   prompt (`check_plan_audit`, `review.py:4198`) to inject the registry and the
   existing slug contract so the finding emits a `feature: <id>` tag alongside its
   `[anchor-slug]`; parse it in `_parse_plan_audit_findings` (`review.py:4131`,
   where `anchor` is captured). The slug-feedback path already feeds accumulated
   anchor slugs back into later samples via `known_anchors` (`review.py:4025`) so
   a re-found concept reuses its slug — feed the feature ids back the **same way**
   so the fallback tag is stable across samples (the load-bearing primitive: a
   stable key that survives anchor re-phrasing).

A finding maps to **exactly one** `feature_id` (its primary feature) — keep it
a scalar, not a list, to match `anchor`'s shape and keep the ledger math simple.
A finding the audit cannot attribute (untagged step, or a conceptual finding
Claude leaves unlabeled) stays `None` and is reported under an `(unattributed)`
bucket — never dropped. Do **not** attempt post-hoc text→feature keyword
matching for the unattributed bucket; that reintroduces exactly the
keyword-precision problem part 1's smell checks fight, and attribution is only
reliable at the point of articulation.

### Part B — the brittleness ledger (across audit history)

The audit history is already persisted and already enumerated: completeness
reports live at `plan-details/<slug>/reports/<ts>-completeness.json`
(`cli/completeness_cmd.py:118`) and the dir is already globbed by
`p.name.endswith("-completeness.json")` (`completeness_cmd.py:165`). Read the
last N reports (filename timestamp = chronological order, the existing
convention), union each report's `recommendations[]`, and group by
`feature_id`. For each feature compute:

- **Recurrence** — the count of consecutive recent audits in which the feature
  has ≥1 finding. This is the per-feature, cross-*run* generalization of the
  existing within-loop `--max-stall-rounds` backstop (which only watches the
  aggregate open count inside one iterate loop). Tracking is at **feature
  granularity, not finding identity** — anchor churn makes finding-level
  identity unreliable, which is the whole reason `feature_id` exists.
- **Escalation** — max severity trend across audits (`medium → high →
  critical`) and whether the per-audit finding count is rising.
- **Fan-out** — number of *distinct concurrent* findings on the feature in a
  single audit (`type_impure` hit 3).
- **Footprint growth** — the feature's step set (the steps whose
  `step.features` tag includes this id) and, via those steps' `step.files`, its
  file set, expanding between audits — metastasis.

Combine into a severity-weighted score; when a feature crosses a threshold,
emit an advisory recommendation naming the signature and the action:

```
Feature health (last 4 audits)
✗ type-impurity   CRITICAL  1→3 findings↑  spans steps 2,4,5 (growing)  → EXTRACT or CUT
⚠ confirm-merge   MED ×4     persistent, never converged                → tighten body↔detail contract
✓ merge-transform  clean
```

Surface it as a new `plan-tool feature-health <plan>` subcommand (thin CLI
handler in `plan_tool/cli/`, wired through `parser.py`, with regenerated
`docs/cli/` reference) **and** as a short epilogue printed after a normal
`completeness-audit`. Advisory only: rc reflects completion, not findings
(exit-code convention) — `--fail-on-findings` is the existing opt-in to flip it.
Thresholds will need calibration; the only real-world dataset today is the
four `merge-steps-executor` reports, so seed the defaults from that case and
mark them tunable.

## Seam citations (verify at HEAD before building)

- `plan_tool/review.py:279` — `Recommendation` dataclass; `:343` the `anchor`
  field whose round-trip + prompt-feedback pattern `feature_id` mirrors.
- `plan_tool/review.py:3657` `_attribute_concept_finding_step` (derives a
  `step_id` for a concept finding from its backticked paths) and `:3772` the
  `file_to_step` map it reads (built from **DONE** steps' `step.files`), applied
  at `:3792` — **the deterministic finding→step link the free attribution path
  composes with `step.features`.** Generalize/extend this to non-DONE steps for
  pre-execution audits.
- `plan_tool/review.py:4131` `_parse_plan_audit_findings` (anchor parser, where
  the fallback `feature:` tag is parsed); `:4198` `check_plan_audit` (the
  conceptual prompt to extend); `:4025` `known_anchors` — the slug-feedback path
  the fallback feature ids ride. (Line numbers drift; re-grep before editing.)
- `plan_tool/cli/completeness_cmd.py` — the `reports/` path and the existing
  reports-dir glob (`endswith("-completeness.json")`) to reuse for history reads;
  confirm the current line and that `completeness_phases.py` is where the
  epilogue attaches.
- `plan_tool/convergence.py:200` `should_continue` — the whole-plan,
  finding-count-only convergence decision today (`converged`/`no_blocking`/
  `marginal`/`no_progress`); feature-blind. The cross-run recurrence signal is
  the per-feature generalization of its `--max-stall-rounds` within-loop stall
  backstop.
- `plan_tool/schema.py:59` `Feature`, `:185` `Plan.features`, `:87`
  `Step.features` — **shipped in part 1**; exist at HEAD. The deterministic path
  reads `step.features` directly; the registry supplies the id set injected into
  the fallback conceptual-audit prompt.

## Out of scope

- **The feature layer (registry + `step.features` tag) and the deterministic
  smell checks** — part 1
  ([`feature-health-1-declaration-and-smell-checks.md`).
  This part assumes the `Feature` model and `Step.features` tag already exist.
- **Auto-extracting or auto-cutting a brittle feature.** Recommend-only — the
  extract/cut decision (like the `type_impure` removal) stays the operator's,
  mirroring split/merge's recommend-only posture.
- **Retrofitting attribution onto pre-existing reports.** The ledger is
  forward-looking: reports written before `feature_id` existed contribute only
  where attribution can be reconstructed from `step_id`. State the gap; don't
  fabricate history.
- **A cross-plan feature-health view** (which features churn across the whole
  backlog) — start per-plan.

## Risks

- **Residual reliance on Claude for unplaceable findings.** The deterministic
  finding→step→feature composition covers findings that cite a path, but a purely
  abstract conceptual finding (no backticked path) still needs the `feature: <id>`
  fallback tag. Mitigation: the slug-feedback mechanism (already proven for
  `anchor`) stabilizes the tag across samples; unattributed findings are bucketed,
  never dropped, so a missed tag degrades gracefully rather than corrupting the
  ledger. The deterministic-first ordering keeps the Claude fallback to the
  genuinely path-less minority.
- **`_attribute_concept_finding_step` keys on DONE steps only.** The file→step
  map is built from completed steps, but the ledger's highest value is at
  *authoring/planning* time (pre-execution), where no step is DONE — so the free
  path would attribute nothing. Mitigation: generalize the map to all steps'
  `step.files`/`creates` (or add a planning-time sibling); without it, a
  still-`planning` plan falls almost entirely to the Claude fallback.
- **Forward-only history.** Severity: low/expected. The ledger needs a few
  audits of accumulated `feature_id` data before recurrence/escalation are
  meaningful; on a fresh plan it reports "insufficient history."
- **Scalar `feature_id` can misattribute** a genuinely cross-feature finding to
  one neighbor, diluting a signal. Severity: low. Chosen for ledger simplicity
  and `anchor`-shape parity; acceptable, but note it.
- **Threshold calibration on n=1.** Severity: tuning. Only one real churn case
  exists to calibrate against. Mitigation: seed defaults from the
  `merge-steps-executor` reports and keep them tunable; expect refinement as
  more plans accrue history.

## Acceptance criteria

- `Recommendation` gains `feature_id: Optional[str] = None` that round-trips
  through the saved-report JSON; reports lacking the field still load.
- Attribution resolves **deterministically first**: a finding with a `step_id`
  (including one back-filled by `_attribute_concept_finding_step` from its cited
  paths) is attributed from that step's `step.features` tag — zero Claude when the
  step tags exactly one feature, otherwise Claude picks from that closed set. Only
  a finding the file→step composition cannot place falls back to the audit's
  `feature: <id>` registry tag (fed back across samples like `anchor`); an
  unattributable finding is bucketed as `(unattributed)`, never dropped. A
  measurable share of step-less conceptual findings is attributed with **no new
  Claude call**.
- `plan-tool feature-health <plan>` reads the `reports/` history, groups
  findings by feature, and reports per-feature recurrence, max-severity trend,
  fan-out, and footprint growth, with an action recommendation (extract/cut vs.
  tighten-contract) for any feature crossing the threshold.
- The same per-feature summary prints as an epilogue after `completeness-audit`.
- On a plan with fewer than two audits of `feature_id` history, the ledger
  reports "insufficient history" rather than a spurious signal.
- Exit code reflects completion, not findings (exit-code convention);
  `--fail-on-findings` remains the only way to flip rc.
- `docs/cli/` (drift-guarded) is regenerated for the new subcommand.
- No new import cycles introduced.

## Deferred

- Wiring brittleness scores into `create`/`detail` as an up-front "this
  capability looks brittle" warning at authoring time.
- Auto-suggesting a `features:` decomposition for plans that lack one (infer
  from step clustering).

## References

- `plan_tool/review.py` — `Recommendation` attribution and audit-finding
  parsing seams cited by this seed.
- `plan_tool/convergence.py` — cross-audit history policy that supplies the
  feature-health trajectory context.
- `plan_tool/schema.py` — `Feature` and `Plan.features` model definitions.
