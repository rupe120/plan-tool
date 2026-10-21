# Plan seed: minimize Claude round-trips in `create`

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/minimize-claude-in-create.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition; the author then runs
`plan-tool detail` per step.

---

## Evidence (baseline measurement — 2026-06-17)

Measured against the three plans created from the granularity/split/merge
seeds (un-instrumented current code; run logs under
`.plan-tool/runs/<slug>/`, analyzed with `scripts/analyze_run_log.py`):

| Plan | Claude calls | Claude wall-clock | Re-proposal cost (Opp 3) |
| --- | --- | --- | --- |
| merge-steps-executor | 6 | 465s | **188s (40%)** |
| escalate-structural-findings-to-split | 6 | 503s | **200s (40%)** |
| step-granularity-advisor | 4 | 486s | 0s (did not iterate) |

What the data changed:

- **Opp 3 is the dominant prize, not the risky afterthought.** Re-proposing
  steps + references every iteration is ~40% of Claude wall-clock. In these
  runs the iteration was triggered by a `## Deferred` body-prose fill that
  cannot change the step graph or references — so the re-proposal was pure
  waste. **Promoted to primary — and A/B-VALIDATED (2026-06-17):** across 3
  seeds × 2 treatment runs the skip fired 6/6, eliminated ~2 Claude calls
  per run, ~halved total Claude wall-clock (~45–52%), with zero quality
  regression (0 placeholders, all sections present, Deferred substantive).
  Step-count ±1 is re-roll noise on unchanged input, not lost refinement.
  See `experiments/minimize-claude/LESSONS.md`. **SHIPPED** as
  `--no-skip-prose-reproposal` (default: skip on).
- **`## Deferred` is NOT boilerplate — Opp 1 over-claimed.** The Claude fill
  produced substantive, plan-specific Deferred content (300–590 chars) in
  all three plans. A `None.` sentinel would be a quality regression.
  **Refined: deterministic fill only when a section has no synthesis AND no
  seed source — which rarely fires for real seeds (`## Out of scope` is
  already seed-derived, Testing's per-step block is already deterministic).**
- **Apply-fill cost is small and currently unlogged.** The baseline logs
  omit apply calls (the create loop didn't pass `run_logger` — now fixed by
  instrumentation). The one observed `## Deferred` fill was ~27s (~6% of a
  465s run) — an order of magnitude below Opp 3. Precise sizing comes from
  the instrumented A/B re-run.

## Guiding principle

**Spend Claude only where judgment is required; fill the rest
deterministically.** Today `create` already pays for body synthesis once
(`propose_body_sections`), yet sections that synthesis declines fall to a
`_(TODO)_` placeholder, and the iteration loop then spends a *second*,
per-section Claude `apply_finding` call to fill each one — even for
boilerplate like `## Deferred` whose correct content is "None." The
detection of a placeholder is already deterministic; only the fill burns
Claude. Close that gap, and trim two other avoidable round-trips.

> **Behavior-preserving for semantic sections.** Overview, Problem
> statement, Architecture, and Acceptance criteria stay Claude-authored —
> they encode judgment. This work only stops paying Claude to write
> content that is derivable or a fixed sentinel.

## Opportunity 1 — deterministic fill for derivable sections — LARGELY DISCARDED

> **Refined to near-nothing by the evidence (2026-06-17).** `## Deferred`
> and the other "derivable" sections turned out substantive and
> plan-specific, not boilerplate — a sentinel default would regress
> quality. Deterministic fill is justified only for a section with NO
> synthesis AND NO seed source, which almost never fires (`## Out of scope`
> is seed-derived; Testing's per-step block is already deterministic). Not
> worth implementing on its own; Opp 3 already removes the downstream cost
> this was chasing. Original rationale retained below.

Classify the `PLAN_BODY_SECTIONS` (`create.py:122`) into:

- **Semantic** (keep Claude): Overview, Problem statement, Architecture,
  Acceptance criteria.
- **Derivable** (fill without Claude): Deferred, Out of scope, References,
  and the Testing per-step enumeration (already deterministic at
  `create.py:4246` — only its intro prose is prose).

Add a deterministic fill pass in `_render_plan_body` (`create.py:4165`)
that runs *after* the existing synth → seed precedence but *before* a
`_(TODO)_` placeholder is emitted, for derivable sections only:

- **Deferred / Out of scope:** if neither synthesis nor a seed H2 section
  supplied content, write a sentinel (`None.`) instead of `_(TODO)_`.
  (The observed 27s `apply-finding` call for `## Deferred` disappears.)
- **References:** default to a derivable line when no `references` arg /
  seed links exist, rather than a placeholder.
- **Testing:** keep the deterministic per-step block as the floor; only
  the intro paragraph may remain Claude-authored.

Result: only **semantic** sections can still surface as `_(TODO)_`, so
the loop's `apply_finding` fills shrink to the sections that actually
need judgment.

## Opportunity 2 — route derivable placeholder findings away from Claude

`check_body_completeness` (`review.py:1030`) already detects placeholders
deterministically. Tag each emitted finding with whether its section is
derivable; in the create iteration loop (`create.py:5355`), resolve
derivable findings via the Opportunity-1 deterministic fill rather than
`apply_finding`. Semantic-section placeholders continue to route to
Claude. (Belt-and-suspenders: if Opportunity 1 fills at render time,
these findings should rarely arise — but the loop is the backstop for
re-introduced placeholders.)

## Opportunity 2b — surface deterministic resolution distinctly from a Claude apply — DISCARDED

> **Determined not valuable (2026-06-17).** This opportunity presupposes a
> deterministic-fill path (Opp 1), which the evidence rejected — `##
> Deferred` fills are substantive, not boilerplate. With no deterministic
> resolution to distinguish, the `mechanism` label was a constant; the
> field added during the experiment has been removed. Left here for the
> record; do not implement. The remainder of this section is the original
> (now moot) rationale.

Independent of *whether* a fill uses Claude: a deterministic resolution
must not be **reported** as an `apply-finding`. Today every resolution
wears the same badge — `launcher.py:2393` emits
`apply-finding step {id}: {finding}` unconditionally — so a free,
deterministic fill looks identical to a Claude round-trip in the progress
output and run log. `apply-finding` connotes a non-deterministic Claude
edit; deterministic resolution should read differently.

- Give deterministic resolution its own progress label / phase (e.g.
  `auto-fill step {id}: ## Deferred (deterministic)`), distinct from the
  Claude `apply-finding` label.
- Record the resolution **mechanism** (`deterministic` vs `claude-apply`)
  in the run log / `RunLogWriter` phase so logs and any findings report
  can distinguish "resolved for free" from "spent a Claude call."
- Apply the same distinction anywhere a verdict/summary is rendered
  (`cli/review_actions.py:433`), so a deterministic fill never prints an
  `APPLIED`/`BLOCKED` Claude-style verdict.

This is the general rule the whole seed serves: **deterministic
application logic is presented differently from a non-deterministic
finding.**

## Opportunity 3 — don't re-propose steps/references when nothing structural changed — SHIPPED

> **Shipped & A/B-validated (2026-06-17).** Implemented as
> `create._reproposal_is_skippable` + the loop gate, exposed as
> `--no-skip-prose-reproposal` (default: skip). Halves create's Claude cost
> with no quality regression. The original design rationale follows.

The loop re-runs `propose_steps_from_claude` (`create.py:5481`) and
`propose_references_from_claude` (`create.py:5496`) every iteration — 2
Claude calls/round — regardless of what the round applied. Gate the
re-proposal on whether the round applied a **step-affecting** finding
(source/anchor that can change the step graph); a round whose only
applied findings were body-prose edits cannot have changed steps, so skip
the re-proposal. Conservative default: when unsure, re-propose (preserve
today's behavior). This is the riskiest item — scope it behind the
classification and add a regression test that a body-only round skips the
re-proposal while a step-touching round still re-proposes.

## Opportunity 4 — default slug deterministically

`suggest_slug` (`create.py:777`) is a Claude call with a deterministic
`slugify` fallback already present. When a slug is derivable from the
seed title without ambiguity, use the deterministic path by default and
reserve the Claude suggestion for the genuinely ambiguous case (or make
it opt-in). Smallest win; include only if cheap.

## Do not regress

- **Semantic sections stay Claude-authored.** No deterministic prose for
  Overview / Problem statement / Architecture / Acceptance criteria.
- **Pre-write completeness gate still passes.** Sentinels (`None.`) are
  not placeholders — confirm `_BODY_PLACEHOLDER_RE` (`review.py:1014`)
  does not match `None.` so the gate at `create.py:~5111` stays green
  without `--iterate`.
- **Convergence semantics unchanged.** Opportunity 3 must never drop a
  re-proposal that today catches a real step change — default to
  re-proposing when the classifier is unsure.
- **Exit-code convention / concise docs** per repo norms.

## Out of scope

- The `detail` process — covered by
  [`minimize-claude-in-detail.md`](minimize-claude-in-detail.md).
- Changing what the semantic sections contain or how synthesis prompts.
- Removing `--iterate`; this reduces *calls per run*, not the loop.
