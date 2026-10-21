> **Replaced**: this file has been superseded by `docs/implementation-plans/2-plan-self-consistency-gate.md`.
> Preserved here for history; do not edit.

## Overview

Builds BACKLOG **#100**. Adds a **no-Claude, plan-altitude** dimension to the `completeness-audit` deterministic well-formedness battery that checks a plan's **internal consistency**: that every deliverable a plan *claims* maps to a step that delivers it, that no step ships a deliverable with no in-scope consumer, and that the brittle-shape signal can *block* rather than only advise. It is the intent-consistency complement to #66's control-flow trace (#66 explicitly scopes itself out of intent). Three checks land: `claim-vs-delivery` (advisory on `smell_recs`), `orphaned-deliverable` (blocking-capable at `medium`), and an elevated `suppression-shape` (moved off `smell_recs` onto a new gate-read bucket at `medium`). All are deterministic and read no source files; a completed audit still exits 0, with the new blocking findings flipping rc **only under `--fail-on-findings`**.

## Problem statement

The blocking gate `_completeness_has_blocking_findings` (`completeness_cmd.py:2260`) takes explicit per-bucket keyword params, and `_DeterministicReport.smell_recs` (`completeness_phases.py:51`) is **not one of them** — so a finding routed to `smell_recs` can never block, no matter its severity. That gap let the shipped `prompt-budget-advisory` plan (#95) pass: its Risks table **claimed** a double-warn was suppressed while **no step delivered it**, and it shipped a `note_prompt_budget_advised()` primitive whose only consumer was deferred (dead-on-arrival). `detect_suppression_shape` fired, but only as **INFO** on the advisory `smell_recs` bucket the blocking gate never reads — so nothing blocked, and the brittleness surfaced late in a budget-limited *conceptual* audit. All three shapes are deterministically detectable at plan altitude *before* detail/execution.

## Architecture

The load-bearing constraint is that `smell_recs` (`completeness_phases.py:51`) is the advisory bucket the blocking gate never reads, so anything that must be blocking-capable cannot ride it. The plan adds **one** new `_DeterministicReport` field (e.g. `self_consistency_recs`) carrying the blocking-capable findings (`orphaned-deliverable` + the elevated `suppression-shape`), threaded through `_completeness_has_blocking_findings`, `_render_grouped_report` (`completeness_phases.py:974`, smells block `:1180`), and `_render_completeness_json` (`:829`, smells group `:932`) — mirroring how `data_contract_recs` / `audit_recs` block at `medium`+ via `convergence.is_blocking` / `BLOCKING_SEVERITIES` (`convergence.py:46`).

Three checks, wired into the battery `_run_deterministic_checks` (`completeness_phases.py:529`) with detectors lazy-imported from `review` (`:561`):

1. **Claim-vs-delivery** (fuzzy) — a deliverable named in `## Acceptance criteria` / `## Overview` prose that maps to no step's declared footprint (or maps only to a `## Deferred` / `## Out of scope` mechanism). Templated on `create.py:find_dropped_references` (`:4591`) and `review.py:check_files_coherence` (`:1339`); claims parsed via `split_body_sections` (`review.py:1105`) / `_extract_acceptance_criteria` (`:4081`), create-side twin `create.py:extract_h2_sections` (`:4502`). Emitted **advisory** on `smell_recs`, source `claim-vs-delivery`, until precision is proven.
2. **Orphaned deliverable / dead-on-arrival** (crisp) — a step declares a `creates:`/`files:` path or a detail-introduced symbol that no in-scope step or claim references and whose wiring the step itself defers. Generalizes existing orphan/dangling detectors to plan-declared deliverables. Emitted at `medium` on the new gate-read bucket, source `orphaned-deliverable`.
3. **Elevate `suppression-shape`** (crisp) — `detect_suppression_shape` (`review.py:1989`, severity literal `:2043`) already fires only when a step's deliverable suppresses/downgrades/bypasses an existing audit gate. Bump `severity` from `info` to `medium` and route it off `smell_recs` (where `collect_smell_findings` sends it, `review.py:2128`→`:2148`) onto the new bucket. Bumping severity alone is inert — the move is load-bearing.

Matching is anchored on **declared symbols / paths / step-ids, not free prose**: every match keys on `step.all_files` (`schema.py:126`), `extract_path_mentions` (`detail.py:1337`), and artifact/step-id tokens — never a bare English noun — because the dominant false-positive risk is prose naming a mechanism differently than the step that delivers it. Checks operate at plan altitude only: they compare the plan's declared prose and footprint against itself and open no source files. Distinct `source` tokens keep the report legible and let a future promotion move `claim-vs-delivery` across buckets without renaming. Findings use the `Recommendation` shape (`review.py:309`) and `_make_rec_id`.

## Out of scope

- **Reading source code to verify a deliverable actually works** — that is #66's control-flow trace; this check is intent/consistency at plan altitude only.
- **Relocating `find_dropped_references` create-side wiring** — reuse its *logic* as a template; do not move #95-era create-only wiring into completeness.

## Risks

- **Prose false positives** — prose naming a mechanism differently than the step that delivers it is the dominant false-positive risk; mitigated by anchoring every match on `step.all_files`, `extract_path_mentions`, and artifact/step-id tokens rather than English nouns, and by "when in doubt, don't flag." `claim-vs-delivery` stays advisory on `smell_recs` until its false-positive rate is measured, so a false positive never flips rc.
- **Inert elevation** — bumping `suppression-shape`'s `severity="info"` (`review.py:2043`) alone does nothing while it still routes through `collect_smell_findings` onto `smell_recs`; the rec must move onto the new gate-read bucket or it can never block.
- **Meta-case self-trip** — `suppression-shape` could flag the detector's own describing prose; the acceptance criteria require the meta-case still not trip and a plan that legitimately excuses a suppression still pass.

## Testing

All checks are deterministic — no invoker seam, no backend spawn. Unit tests for the new detectors land in `tests/test_review.py` next to `TestSuppressionShape` (`:9878`), `TestCheckBodyCompleteness`, and `TestSplitBodySections`; update `TestSuppressionShape`'s severity assertions. In `tests/cli/test_completeness_cmd.py`, extend `TestRunDeterministicChecks` (`:489`, the `_DeterministicReport` field-list assertion at `:528`), `TestCompletenessHasBlockingFindings` (`:228`), and the grouped-report / JSON group tests; add blocking-gate cases for `orphaned-deliverable` and the elevated `suppression-shape`. The tests asserting "smells never gate" (`test_completeness_cmd.py:1573`, `:3136`) must stay green (claim-vs-delivery on `smell_recs` is still non-blocking); the elevated suppression-shape moves out of those into new blocking-gate tests. Reproduce the motivating case with a #95-shaped brittle plan.

## Acceptance criteria

- A plan whose `## Acceptance criteria` claims a deliverable that no step declares (or only a `## Deferred` mechanism delivers) surfaces a `claim-vs-delivery` **advisory** finding that never flips rc; a test with the #95-shaped brittle plan reproduces it.
- A step declaring a `creates:` file / detail-introduced symbol that no in-scope step or claim references and whose wiring the step defers surfaces an `orphaned-deliverable` finding at `medium` on the new gate-read bucket, and it **blocks under `--fail-on-findings`**.
- `suppression-shape` now emits `medium` on the gate-read bucket (off `smell_recs`) and **blocks under `--fail-on-findings`**; the meta-case (the detector's own describing prose) still does not trip, and a plan that legitimately excuses a suppression still passes.
- The new gate-read bucket is a real `_DeterministicReport` field threaded through `_completeness_has_blocking_findings`, `_render_grouped_report`, and `_render_completeness_json`; `smell_recs` stays structurally non-blocking.
- All checks are no-Claude and read no source files beyond the sibling deterministic checks; a completed audit still exits 0 absent `--fail-on-findings`.
- The tests that assert "smells never gate" (`test_completeness_cmd.py:1573`, `:3136`) stay green; the elevated suppression-shape is covered by new blocking-gate tests.
- `BACKLOG.md` #100 is reconciled (shipped/removed) and its Quality/accuracy roll-up (`audit-coverage` facet) reference is updated in the final docs/status step.

## Deferred

- **Promoting `claim-vs-delivery` to blocking** — stays advisory until its false-positive rate is measured on real plans; a follow-up plan promotes it once precision is proven.
- **Running `find_dropped_references` at completeness time** (vs its current create-only use) — reuse its logic as a template now; relocating the wiring is deferred.
- **A first-party-gate vocabulary for `suppression-shape`** — not needed now (the detector's trip condition already targets gate suppression); add one only if a false-positive rate later demands it.
