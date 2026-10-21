> **Replaced**: this file has been superseded by `docs/implementation-plans/2-bare-plan-correctness-apply-route.md`.
> Preserved here for history; do not edit.

# Plan seed: route a bare plan's conceptual gaps to the right remedy

> **Status: ready.** No BACKLOG id yet — file one when creating, or fold into
> an existing fence/apply entry if one fits. Measured refinement of the bare-plan
> apply fence (post-#61): split correctness vs completeness apply routing and
> fix the BLOCKED→`detail` remedy. Supersedes cut `bare-plan-audit-grounding.md`.

This file is a `plan-tool create` input. Use it via:

```
plan-tool create bare-plan-apply-routing --from-existing plan-seeds/bare-plan-apply-routing.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Supersedes `bare-plan-audit-grounding.md` (cut 2026-08-03).** That seed
> proposed a three-part effort; measuring it against this repo's 370 saved
> completeness reports refuted its motivating premise and showed two of its
> three decisions were unbuildable or unnecessary. The refusals and their
> numbers are recorded under `## Out of scope` so they are not re-proposed.

---

## Outcome

On a bare or partially-detailed plan, conceptual-**correctness** gaps get an
apply route they can actually use, and the `BLOCKED` verdict that route newly
exposes points the operator at `plan-tool detail` rather than at
`plan-tool split`.

## In scope

- The bare-plan apply fence in `completeness_report.py` — the
  `unappliable = bare_plan or jira_grade` computation shared by
  `suggested_next_steps` and its console sibling `suggested_next_step_commands`.
- The BLOCKED remedy renderer in the same module (`_blocked_next_step`,
  `_blocked_split_targets`).
- The bare-step conditioning the audit prompt already carries
  (`review.py:_format_detail_bundle_status_block`).

## Overview

A completeness audit already computes `is_bare` per run and conditions the
audit prompt on it. It then uses that same flag for a second purpose it does
not fit: withholding the `completeness-apply` route from **both** conceptual
axes at once. The two axes do not have the same grounding needs. A correctness
gap — unsound design, internal contradiction, conceptual ordering hazard —
targets the plan body, step titles, and acceptance criteria, all of which exist
on a bare plan. A completeness gap leans on the detail bundle that has not been
authored. Splitting the fence by axis restores the route to the half that can
use it, and is most valuable exactly where it is currently refused: before N
detail calls are spent on a decomposition that a correctness finding would have
corrected.

Opening that route exposes a latent defect, so the two ship together.

## Problem statement

**The fence is one flag doing two jobs.** `unappliable = bare_plan or jira_grade`
collapses "there is no sidecar to replay" (jira grade) with "some steps lack
detail files" (bare). The second reason does not apply to correctness gaps.
`prompts/apply-finding.md` edits the plan file "and/or the step's detail file
**if applicable**" and emits `BLOCKED` only when a finding genuinely needs a
missing detail file — so the apply path already handles a plan-body-only edit,
and the fence refuses it anyway. The operator is routed to a hand-fix for
findings the machinery would have applied.

**The BLOCKED renderer contradicts the apply prompt, latently.** When apply
cannot proceed for want of a detail file, the prompt instructs the model to say
so and name `plan-tool detail`. The tool's own rendering ignores that:
`_blocked_next_step` frames *every* BLOCKED as "apply can't add or restructure
steps" and emits a `plan-tool split --step N` command per flagged step. So a
finding whose real remedy is "author the detail file" prints as "split this
step" — a structural remedy for a plan that simply has not been detailed. This
is inert today only because the bare-plan fence means the walk never runs there.
Splitting the fence makes it live, which is why it is in scope rather than a
follow-up: **the rule this seed adds obliges the fix.**

## Architecture

Three decisions. Two of them are refusals with measurements behind them; those
live under `## Out of scope`.

**1. Split the fence by axis, at plan altitude.** On a bare plan,
conceptual-correctness gaps keep the `completeness-apply` route; conceptual-
completeness gaps stay unappliable. Jira grade keeps its current behavior for
its own, unrelated reason — it writes no sidecar, so nothing can replay there.
The split is by **axis**, never by per-finding detail coverage; see the refusal
below for why the finer version is not available.

**2. The BLOCKED remedy becomes coverage-aware — at plan altitude, for the same
reason.** When the plan is bare, the BLOCKED bullet leads with
`plan-tool detail <name>` and keeps the `split` command as the secondary
option; on a fully-detailed plan the bullet is unchanged. Deliberately *not*
keyed on whether the individual finding targets a bare step: that requires
resolving a finding to a step, which the data does not support.

**3. Narrow the edge-case recast, and claim only what it is.** For a bare step,
a "missing edge-case concept" finding is admissible when its remedy is a step or
an acceptance criterion — a decomposition gap, which is what a bare-plan audit
should catch — and inadmissible when the remedy is "specify it in the detail",
which is the `detail` stage's job. This is a **small** delta: the shipped
conditioning block already says to judge bare steps "solely on the plan body's
concepts and the code at HEAD". Bare audits average **8.7** conceptual findings
per run against **5.1** for detailed audits (n=19 bare of 370 completeness
reports, measured 2026-08-03) — a real elevation, **not** saturation. Do not
restate it as saturation.

**The binary observable, and nothing beyond it:** `is_bare`, already computed
deterministically per run. This effort routes on that existing fact. It asserts
no new measurement, judges no artifact's quality, and compares no two prose
artifacts.

## Out of scope

Three refusals, each with the evidence that produced it. Treat these as settled
(2026-08-03); a finding proposing one is invalid unless it brings new data.

- **Per-finding coverage routing — refused as unbuildable.** Only **6.0%** of
  conceptual findings resolve to a step (116 of 1,933 across the saved corpus;
  `plan-completeness` 4.5%, `plan-correctness` 8.1%). They carry `step_id=None`
  and a step is recoverable only from a `step<N>` anchor prefix, while
  `prompts/plan-audit.md` directs the auditor to anchor on the **concept**
  (`[cache-invalidation]`), not the step. A conservative fallback classifies 94%
  as ungrounded, so the "graded" fence collapses to the binary it was meant to
  replace while adding machinery that does nothing. Rule 5: a high false-positive
  rate means kill, not tune.
- **Excluding bare runs from the convergence spinning series — refused as
  unmotivated.** The premise was that bare conceptual findings cannot shrink
  because no apply route is offered. That is false: they are closed **by hand**,
  which is the documented Claude-session workflow. Measured on the two plans in
  this repo with the heaviest bare history — `plan-tool-annotate-feedback`
  (7 of 8 completeness runs fully bare) trends 15→14→11→9→9→5→5→5 and diagnoses
  `converging` with fork `none`; `parallel-plan-worktrees` (3 of 6 bare) also
  `converging`. The harm is undemonstrated and the best natural experiments
  available point the other way.
- **A new persisted detail-coverage field — refused as unnecessary.**
  `compute_detail_bundle_fingerprint` already records the state: a bare step
  "contributes none — its absence *is* the bare-state signal", so
  empty-and-`present` is an unambiguous fully-bare marker and all 370 reports
  were classified with zero schema change. A `(detailed, total)` pair would buy
  only the partial gradient, which the 6% measurement shows no consumer can use.

Also out: any new gate, exit-code flip, blocking severity, or refusal-to-advance;
`convergence.is_blocking_impact` and the calibrated policy (CLAUDE.md
§ "Convergence policy boundary" scopes that separately); jira-grade behavior;
`#85`'s read-only-audit split; and anything `detail` itself does. BACKLOG **#224**
is a sibling with a live plan (`docs/implementation-plans/2-audit-shape-registry.md`)
— do not reach into it.

## Allowed behavior changes

Only these: a bare-plan audit offers `completeness-apply` for correctness gaps;
a BLOCKED bullet on a bare plan leads with `plan-tool detail`; bare-step
edge-case findings narrow per decision 3. A fully-detailed plan's audit and a
jira-grade audit are unchanged end to end.

## Allowed reorganization

None. Both code changes land in `completeness_report.py`, which already owns the
fence and the renderer.

## Risks

- Opening the apply route raises BLOCKED volume on bare plans. If decision 2 is
  incomplete, the operator is pointed at `split` for a detailing problem — the
  defect this seed exists to prevent, which is why decision 2 is not optional and
  not deferrable.
- Decision 3 is a prompt directive, so it is **delivered, not verified**; nothing
  machine-checks that the auditor honored it. That is the intended line. The
  acceptance criteria must not grow a conformance check for it.
- The two next-step renderers describe one run and must stay in step; drift
  between the report prose and the console block is itself a reporting defect.

## Testing

What would prove the Outcome:

- A bare-plan audit names `completeness-apply` for its correctness gaps and does
  not name it for its completeness gaps — in both the report prose and the
  console block.
- A BLOCKED finding on a bare plan leads with `plan-tool detail`; the same
  finding on a fully-detailed plan still leads with `plan-tool split`.
- A fully-detailed plan's next-steps output is unchanged, and a jira-grade audit
  is unchanged.

## Acceptance criteria

- A bare plan's conceptual-correctness gaps have a named apply route; its
  conceptual-completeness gaps do not.
- No BLOCKED bullet recommends `split` as the lead remedy on a bare plan.
- The audit prompt admits a bare-step edge-case finding only when its remedy is a
  step or an acceptance criterion.
- Fully-detailed plans and jira-grade audits behave exactly as before.

## Deferred

- **Where out-of-scope discoveries go.** Things the code does wrong go to
  `BUG_BACKLOG.md`, forward-looking work to `BACKLOG.md`, per BACKLOG.md's
  decision rule. Anything touching audit-shape detection or `insufficient-history`
  routing is appended to **#224** rather than filed fresh.
- The three refusals above are deferred permanently, not pending — reopening one
  requires new measurement, not a new argument.
