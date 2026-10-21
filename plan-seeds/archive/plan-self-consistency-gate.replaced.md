> **Replaced**: this file has been superseded by `docs/implementation-plans/2-plan-self-consistency-gate.md`.
> Preserved here for history; do not edit.

# Plan seed: deterministic plan self-consistency gate (claim-vs-delivery, orphaned deliverable, elevate suppression-shape)

Builds BACKLOG **#100**. Adds a **no-Claude, plan-altitude** dimension to the
`completeness-audit` deterministic well-formedness battery that checks a plan's
**internal consistency** — that every deliverable the plan *claims* maps to a step
that delivers it, that no step ships a deliverable with no in-scope consumer, and
that the existing brittle-shape signal can *block* rather than only advise. The
intent-consistency complement to #66's control-flow trace (#66 explicitly scopes
itself out of intent).

> **Motivating case (why this exists).** The shipped `prompt-budget-advisory`
> plan (#95) had a Risks table **claiming** a double-warn was suppressed while
> **no step delivered it**, and shipped a `note_prompt_budget_advised()` primitive
> whose only consumer was deferred (dead-on-arrival). `detect_suppression_shape`
> fired — but only as **INFO**, riding the advisory `smell_recs` bucket the
> blocking gate never reads — so nothing blocked, and the brittleness surfaced
> late in a budget-limited *conceptual* audit. All three are deterministically
> detectable at plan altitude *before* detail/execution.

> **Backlog reconciliation (required).** Derived from BACKLOG **#100**. The final
> docs/status step **must** mark #100 shipped / remove it and update its
> Quality/accuracy roll-up (`audit-coverage` facet) reference.

## The load-bearing constraint (design around this)

`_DeterministicReport.smell_recs` (`completeness_phases.py:51`) is the **advisory
bucket the blocking gate never reads**: `_completeness_has_blocking_findings`
(`completeness_cmd.py:2260`) takes explicit per-bucket keyword params and
`smell_recs` is **not one of them** — so a finding on `smell_recs` can *never*
block, no matter its severity. Therefore:

- A check that must be **blocking-capable** cannot ride `smell_recs`; it needs a
  **new `_DeterministicReport` field** that is **threaded as a new parameter into
  `_completeness_has_blocking_findings`** (mirroring how `data_contract_recs` /
  `audit_recs` block at `medium`+) plus a render block and a JSON group.
- Elevating `suppression-shape` therefore means **more than bumping severity**:
  its rec must move **off** `smell_recs` (where `collect_smell_findings` routes it,
  `review.py:2148`) **onto** the new gate-read bucket. Bumping `severity="info"`
  (`review.py:2043`) alone is inert.

## The three checks

1. **Claim-vs-delivery (advisory first — the fuzzy one; spike before wiring).**
   A deliverable named in `## Acceptance criteria` / `## Overview` prose that maps
   to **no step's declared footprint** (or maps only to a `## Deferred` /
   `## Out of scope` mechanism) → "you claim X, but X is deferred / undelivered."
   Template: `create.py:find_dropped_references` (4591 — references-not-pinned-to-
   Acceptance) and `review.py:check_files_coherence` (1339 — declared-vs-body). Emit
   as **advisory** (`smell_recs`, source `claim-vs-delivery`) until it proves
   precise; do **not** hard-block on prose-fuzzy matches.
2. **Orphaned deliverable / dead-on-arrival (crisp — blocking-capable).**
   A step declares a deliverable (a `creates:`/`files:` path, or a symbol its
   detail introduces) that **no in-scope step or claim references** *and* whose
   wiring the step itself defers → flag. Generalizes the existing orphan/dangling
   detectors from detail-files/feature-refs to **plan-declared deliverables**.
   Emit at `medium` on the new gate-read bucket, source `orphaned-deliverable`.
3. **Elevate `suppression-shape` (crisp — blocking-capable).** The detector
   (`review.py:1989`) already fires only when a step's deliverable
   suppresses/downgrades/bypasses an **existing audit gate** — so its trip
   condition already targets first-party gates. Bump `severity` to `medium` and
   route it onto the new gate-read bucket so it can block, instead of INFO on
   `smell_recs`.

## Resolved design decisions (ground the build on these)

1. **Severity split: crisp blocks, fuzzy advises.** `orphaned-deliverable` and
   `suppression-shape` are crisp (keyed on declared paths/symbols and the
   detector's existing gate-suppression shape) → `medium`, on the new gate-read
   bucket, blocking-capable under `--fail-on-findings`. `claim-vs-delivery` is
   prose-fuzzy → stays **advisory** (`smell_recs`) until precision is proven; the
   entry's own risk note mandates this. A later plan can promote it once its
   false-positive rate is measured.
2. **Match on declared symbols / paths / step-ids, NOT free prose.** The dominant
   false-positive risk is prose naming a mechanism differently than the step that
   delivers it. Anchor every match on `step.all_files` (`schema.py:126`),
   `extract_path_mentions` (`detail.py:1337`), and artifact/step-id tokens — never
   on a bare English noun. When in doubt, don't flag.
3. **Plan altitude only — do not read code.** These checks compare the plan's
   **declared prose and footprint** against itself. They do not open source files
   or verify implementations (that is #66's control-flow trace). A deliverable is
   "declared" if it is in `step.all_files` or named in a detail body; "claimed" if
   it appears in `## Acceptance criteria` / `## Overview`. No Claude, no repo I/O
   beyond what the sibling deterministic checks already do.
4. **One new gate-read bucket, distinct source tokens.** Add a single
   `_DeterministicReport` field (e.g. `self_consistency_recs`) carrying the
   blocking-capable findings (`orphaned-deliverable` + the elevated
   `suppression-shape`), thread it through `_completeness_has_blocking_findings`,
   `_render_grouped_report`, and `_render_completeness_json`. Keep
   `claim-vs-delivery` on `smell_recs`. Distinct `source` tokens keep the report
   legible and let a future promotion move `claim-vs-delivery` across buckets
   without renaming.
5. **Exit-code convention unchanged.** A completed audit still exits 0; the new
   blocking findings flip rc **only under `--fail-on-findings`** (the existing
   `has_blocking_findings` → rc path). No new exit semantics.

## The seams (grounded — cite these)

- Battery: `_run_deterministic_checks` (`completeness_phases.py:529`); bundle
  `_DeterministicReport` (`:51`); detectors lazy-imported from `review` (`:561`).
- Blocking gate: `_completeness_has_blocking_findings` (`completeness_cmd.py:2260`,
  `medium`+ via `convergence.is_blocking` / `BLOCKING_SEVERITIES` `convergence.py:46`).
- Render / JSON: `_render_grouped_report` (`completeness_phases.py:974`, smells
  block `:1180`), `_render_completeness_json` (`:829`, smells group `:932`).
- Suppression-shape: `detect_suppression_shape` (`review.py:1989`, severity literal
  `:2043`), routed today via `collect_smell_findings` (`:2128`→`:2148`).
- Claims side: `split_body_sections` (`review.py:1105`) /
  `_extract_acceptance_criteria` (`:4081`) over `## Acceptance criteria` +
  `## Overview`; `create.py:extract_h2_sections` (`:4502`) is the create-side twin.
- Deliverables side: `step.all_files` (`schema.py:126`), `extract_path_mentions`
  (`detail.py:1337`). Sibling detectors: `check_files_coherence` (`review.py:1339`),
  `find_dropped_references` (`create.py:4591`).
- Finding shape: `Recommendation` (`review.py:309`), `_make_rec_id`.

## Deferred (out of scope)

- **Promoting `claim-vs-delivery` to blocking** — stays advisory until its
  false-positive rate is measured on real plans; a follow-up promotes it.
- **Reading source code to verify a deliverable actually works** — that is #66's
  control-flow trace; this check is intent/consistency at plan altitude only.
- **Running `find_dropped_references` at completeness time** vs its current
  create-only use — reuse its *logic* as a template; don't relocate #95-era
  create wiring in this plan.
- **A first-party-gate vocabulary** for suppression-shape — not needed (the
  detector's trip condition already targets gate suppression); add one only if a
  false-positive rate later demands it.

## Acceptance criteria (plan-level)

- A plan whose `## Acceptance criteria` claims a deliverable that **no step
  declares** (or only a `## Deferred` mechanism delivers) surfaces a
  `claim-vs-delivery` **advisory** finding (never flips rc); a test with the
  #95-shaped brittle plan reproduces it.
- A step declaring a `creates:` file / detail-introduced symbol that **no in-scope
  step or claim references** and whose wiring the step defers surfaces an
  `orphaned-deliverable` finding at `medium` on the new gate-read bucket, and it
  **blocks under `--fail-on-findings`**.
- `suppression-shape` now emits `medium` on the gate-read bucket (off
  `smell_recs`) and **blocks under `--fail-on-findings`**; the meta-case (the
  detector's own describing prose) still does not trip, and a plan that legitimately
  excuses a suppression still passes.
- The new gate-read bucket is a real `_DeterministicReport` field threaded through
  `_completeness_has_blocking_findings`, `_render_grouped_report`, and
  `_render_completeness_json`; `smell_recs` stays structurally non-blocking.
- All checks are **no-Claude** and read no source files beyond the sibling
  deterministic checks; a completed audit still exits 0 absent `--fail-on-findings`.
- The tests that assert "smells never gate" (`test_completeness_cmd.py:1573`,
  `:3136`) stay green (claim-vs-delivery on `smell_recs` is still non-blocking);
  the elevated suppression-shape moves out of those and is covered by new
  blocking-gate tests.
- `BACKLOG.md` #100 reconciled (shipped/removed; roll-up `audit-coverage` updated).

## Tests (where coverage lands)

- `tests/test_review.py` — the new detectors' unit tests next to
  `TestSuppressionShape` (`:9878`), `TestCheckBodyCompleteness`, and
  `TestSplitBodySections`; update `TestSuppressionShape`'s severity assertions.
- `tests/cli/test_completeness_cmd.py` — extend `TestRunDeterministicChecks`
  (`:489`, the `_DeterministicReport` field-list assertion at `:528`),
  `TestCompletenessHasBlockingFindings` (`:228`), and the grouped-report / JSON
  groups; add blocking-gate cases for `orphaned-deliverable` + elevated
  `suppression-shape`; keep the `smells_do_not_affect_has_blocking` tests green.
- Seam discipline: all deterministic — no invoker seam, no backend spawn.
