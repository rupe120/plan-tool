> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the `orphaned-deliverable` detector plus its shared plan-footprint matcher and wire it onto the new bucket

## Summary

Add a new deterministic detector `detect_orphaned_deliverable` to `plan_tool/review.py` that flags a step which ships a `creates:`/`files:` path (or a path-derived symbol) that no other in-scope step or plan claim consumes and whose wiring the step itself defers — the dead-on-arrival shape from the #95 `prompt-budget-advisory` plan. Also add a shared, reusable `build_plan_footprint` helper in the same file that gathers the plan's declared deliverables and everything the plan references, so this detector and step 4's `claim-vs-delivery` detector both key on declared paths/symbols/step-ids rather than free English prose. Wire the detector into `plan_tool/cli/completeness_phases.py`'s `_run_deterministic_checks` so its findings land on step 1's blocking-capable `self_consistency_recs` bucket at `severity="medium"`. On green, a plan whose step declares an orphaned, deferred deliverable produces one `medium` `orphaned-deliverable` finding that renders under `### Self-consistency`, blocks under `--fail-on-findings`, and reads no source files. The detector is conservative — it only trips on the full conjunction (declared + unreferenced + self-deferred) so false positives stay near zero.

## Table of Contents

- [Why](#why) — the dead-on-arrival gap this closes
- [Input](#input) — the step-1 bucket this step feeds
- [Files (creates vs edits)](#files-creates-vs-edits) — two source files, two test files
- [Implementation](#implementation) — the footprint matcher, the detector, and the battery wiring
- [Tests](#tests) — detector trip/no-trip, footprint matcher, and blocking-gate cases
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the stdlib/contract docs that matter here
- [Deferred](#deferred) — the claim-vs-delivery producer and other steps' work

## Why

A plan can ship a deliverable nothing uses — a step introduces a primitive (a new function or a `creates:` file) whose only consumer is deferred to a later plan, so it lands dead on arrival — and no deterministic check catches that shape before execution. `check_files_coherence` (`plan_tool/review.py`) already compares a step's detail body against its own declared footprint, but it never asks the plan-wide question: does any *other* step or claim actually consume what this step delivers? This step adds that question as a no-Claude, plan-altitude check. It rides step 1's new `self_consistency_recs` bucket so it can block under `--fail-on-findings`, unlike the advisory `smell_recs` bucket the gate never reads.

## Input

- **`_DeterministicReport.self_consistency_recs`** — produced by step 1 (`plan_tool/cli/completeness_phases.py`). Step 1 declares the field, threads it into `_completeness_has_blocking_findings` (gate) with a `medium`+ blocking branch, renders it in `_render_grouped_report` (a `### Self-consistency` section) and `_render_completeness_json` (a `checks["self_consistency"]` group), and includes it in the grouped report's `has_any` all-clear check. This step only **appends** `orphaned-deliverable` recs to that field; it does not re-wire the gate or the renderers. Reference step 1's outcome, not its mechanism — if the field or gate branch changed name at implementation time, use whatever step 1 actually landed.
- **Step 2 also feeds the same bucket.** Step 2 moves the elevated `suppression-shape` rec onto `self_consistency_recs`. This step depends only on step 1, so do not assume step 2 has landed — append the orphaned recs to the bucket regardless of whether suppression-shape recs are already in it.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/review.py`
  - Add `build_plan_footprint` (and a small result type, e.g. a frozen `PlanFootprint`) — the shared matcher that both this detector and step 4 reuse. Place it near the other plan-altitude helpers (`_derive_file_path_symbols`, `split_body_sections`) so its imports stay leaf-level.
  - Add `detect_orphaned_deliverable(plan, repo_root, *, plan_name) -> list[Recommendation]`, next to `detect_suppression_shape` and `collect_smell_findings`. Source `"orphaned-deliverable"`, `severity="medium"`, `step_id=<step>`, id via `_make_rec_id`.
  - Optional: a module constant `ORPHANED_DELIVERABLE_SOURCE = "orphaned-deliverable"` so the detector and the completeness-side wiring key on one symbol.
- `plan_tool/cli/completeness_phases.py`
  - In `_run_deterministic_checks`, lazy-import `detect_orphaned_deliverable` in the existing `from plan_tool.review import (...)` block, call it, and append its recs to step 1's `self_consistency_recs` local before the `_DeterministicReport(...)` return.
- `tests/test_review.py`
  - Add unit tests for `build_plan_footprint` and `detect_orphaned_deliverable`, next to `TestSuppressionShape`.
- `tests/cli/test_completeness_cmd.py`
  - Extend `TestRunDeterministicChecks` (assert orphaned recs land on `self_consistency_recs`) and `TestCompletenessHasBlockingFindings` (a `medium` orphaned rec blocks).

## Implementation

**Foundational logic:** a plan-altitude, no-Claude check that answers "does any in-scope step or claim consume this step's deliverable?" and, when the answer is no *and* the step defers its own wiring, emits a blocking-capable `medium` finding. The core anti-false-positive rule: match only on declared paths, path-derived symbols, and step-ids — never a bare English noun.

**The shared footprint matcher (`build_plan_footprint`).**

- **Purpose:** one pass over the plan that produces both sides of the question — what each step *declares* and what the whole plan *references* — so a detector can ask "is deliverable X referenced anywhere outside its declaring step?" without re-walking the plan.
- **Declared side:** for each step, its `creates:` paths and `files:` paths (`plan_tool/schema.py` `Step.all_files`), plus the identifier tokens those paths imply via `plan_tool/review.py`'s `_derive_file_path_symbols`. Normalize paths to POSIX strings (mirror `check_files_coherence`'s comparison style — exact-string after normalization).
- **Referenced side:** the union across all steps of (a) path mentions in each step's detail body via `plan_tool/detail.py` `extract_path_mentions`, (b) other steps' declared paths (a file another step also lists is a consumer), and (c) tokens named in the plan's claim prose — `## Acceptance criteria` / `## Overview` sections pulled with `split_body_sections` (`plan_tool/review.py`) and, for detail bodies, `parse_detail_file_sections`.
- **Reuse constraint:** step 4 (`claim-vs-delivery`, `depends_on: 3`) reuses this same helper. Keep its signature and result shape stable and self-descriptive; do not fold step-3-only logic into it. One way: return a frozen dataclass with named sets (`declared_paths`, `declared_symbols`, `referenced_paths`, `referenced_symbols`) so both detectors read the field they need.
- **No source reads:** the matcher opens only plan and detail markdown (plan artifacts), never a `.py`/`.ts` source file — same boundary `check_files_coherence` respects. State this in the docstring.

**The detector (`detect_orphaned_deliverable`).**

- **Trip condition is a conjunction** — trip only when all hold, so the check stays crisp:
  1. A non-`done` step declares a deliverable: a `creates:`/`files:` path or a path-derived symbol (`_derive_file_path_symbols`) — the same declared tokens `build_plan_footprint`'s declared side produces, never a bare prose noun.
  2. No *other* in-scope step references that deliverable (via the footprint's referenced side).
  3. No plan claim (`## Acceptance criteria` / `## Overview`) references it.
  4. The step **defers its own wiring** — its detail `## Deferred` section (or the plan `## Deferred` / `## Out of scope`) names the deliverable's consumer/wiring as out of scope.
- **Skip `done` steps** — matches `check_files_coherence` and `heuristic_already_done`: a delivered step's wiring is the semantic review's job, not this pre-execution check.
- **"When in doubt, don't flag."** The deferred-wiring requirement (condition 4) is what separates a genuinely dead-on-arrival deliverable from a normal step whose consumer simply lands in a later step — a later step that consumes it satisfies condition 2 and the finding never fires. Prefer a false negative over nagging the operator.
- **Emit shape:** one `Recommendation` per orphaned deliverable — `source="orphaned-deliverable"`, `severity="medium"`, `step_id=<step>`, `id=_make_rec_id(step.id, "orphaned-deliverable", <fingerprint>)`, a `title` naming the step and deliverable, and a `body` explaining that the deliverable has no in-scope consumer and its wiring is deferred (confirm the deliverable is needed now, or move it to the step that wires it).

**Battery wiring (`_run_deterministic_checks`).**

- **Append to `self_consistency_recs`, not `smell_recs`.** Step 1 builds the `self_consistency_recs` local; this step calls `detect_orphaned_deliverable(plan, ctx.repo_root, plan_name=plan_name)` and extends that local. The `plan_name` threads through for stable rec ids, same as `collect_smell_findings`.
- **Stay out of `_det_total`.** The self-consistency bucket does not inflate the deterministic well-formedness count (step 1 kept it out); do not add orphaned recs to `_det_total`.
- **Lazy import.** Add `detect_orphaned_deliverable` to the existing body-local `from plan_tool.review import (...)` block in `_run_deterministic_checks` so the monkeypatch seam stays on the `plan_tool.review` domain module.
- **No auto-apply routing.** Leave the `_structural` next-steps router untouched — orphaned recs have no `apply_finding` path (they describe a structural plan gap), so they surface and gate but never auto-apply, exactly like the other self-consistency findings.

**Rejected alternative:** matching prose deliverable names by free-text similarity against source symbols. Rejected because the dominant false-positive risk is prose naming a mechanism differently than the step delivering it; anchoring every match on declared paths/symbols/step-ids keeps the check crisp enough to block.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add every test below **with** the implementation; all must be green before the step is considered done.

`tests/test_review.py` (next to `TestSuppressionShape`):

- `test_build_plan_footprint_collects_declared_paths_and_symbols` — footprint's declared side includes each step's `all_files` and their derived symbols.
- `test_build_plan_footprint_collects_references_from_detail_and_claims` — referenced side picks up detail-body path mentions and acceptance/overview prose tokens.
- `test_build_plan_footprint_opens_no_source_files` — passing a plan with real `.py` paths on disk reads no source (only plan/detail markdown).
- `test_orphaned_deliverable_trips_on_deferred_unconsumed_creates` — a step with a `creates:` path no other step/claim references and a `## Deferred` wiring note emits one `medium` finding, `source="orphaned-deliverable"`.
- `test_orphaned_deliverable_no_trip_when_consumer_step_exists` — another in-scope step referencing the deliverable suppresses the finding.
- `test_orphaned_deliverable_no_trip_when_claim_references_it` — an `## Acceptance criteria` claim naming the deliverable suppresses the finding.
- `test_orphaned_deliverable_no_trip_when_wiring_not_deferred` — deliverable unconsumed but not deferred → no finding (condition 4 unmet).
- `test_orphaned_deliverable_skips_done_steps` — a `done` step never trips.
- `test_orphaned_deliverable_reproduces_prompt_budget_shape` — a #95-shaped plan (primitive shipped, only consumer deferred) trips.

`tests/cli/test_completeness_cmd.py`:

- `TestRunDeterministicChecks::test_orphaned_deliverable_lands_on_self_consistency_recs` — the battery routes orphaned recs to `self_consistency_recs`, not `smell_recs`, and they don't change `_det_total`.
- `TestCompletenessHasBlockingFindings::test_orphaned_deliverable_medium_blocks` — a `medium` orphaned rec on `self_consistency_recs` flips the blocking gate.

## Acceptance criteria

- `detect_orphaned_deliverable` returns one `medium` / `source="orphaned-deliverable"` finding for a non-`done` step declaring a deliverable no other in-scope step or claim references and whose wiring the step defers; it returns `[]` when any of those four conditions fails.
- `build_plan_footprint` returns declared paths/symbols and referenced paths/symbols for a plan, opening no source files.
- `_run_deterministic_checks` places orphaned recs on `_DeterministicReport.self_consistency_recs` (step 1's bucket), and they render under `### Self-consistency` and in the `checks["self_consistency"]` JSON group.
- An orphaned-deliverable finding blocks under `--fail-on-findings`; a completed audit still exits 0 without that flag.
- The new detector reads no `.py`/source files — only plan and detail markdown.
- All new tests in `tests/test_review.py` and `tests/cli/test_completeness_cmd.py` pass; the existing "smells never gate" tests stay green (this step adds nothing to `smell_recs`).

## References

The key pointers for this step are the in-file sibling symbols it models — reuse their shape and boundaries rather than inventing new ones:

- `detect_suppression_shape` (`plan_tool/review.py`) — the sibling deterministic detector `detect_orphaned_deliverable` sits beside and mirrors: `Recommendation` shape, `_make_rec_id`, and the plan-altitude / no-source-read boundary.
- `collect_smell_findings` (`plan_tool/review.py`) — the `plan_name`-threading and rec-collection pattern the new detector and its battery call follow.
- `check_files_coherence` (`plan_tool/review.py`) — the "compare a step against its declared footprint" template this step generalizes to the plan-wide "does anything else consume this deliverable?" question, keeping the same plan/detail-markdown-only boundary.
- `_derive_file_path_symbols` (`plan_tool/review.py`) — derives the identifier tokens a path implies; the declared side of `build_plan_footprint` reuses it.
- `extract_path_mentions` (`plan_tool/detail.py`) — pulls path mentions from a detail body; the referenced side of `build_plan_footprint` reuses it.

Supporting stdlib/test docs:

- [difflib — Helpers for computing deltas (Python 3.13)](https://docs.python.org/3/library/difflib.html) — background only; this detector does **not** use `SequenceMatcher`/`get_close_matches` — it matches exclusively on declared paths/symbols/step-ids (exact-string after normalization), never free-text similarity (see the Rejected alternative). Fuzzy near-matching is step 4's `claim-vs-delivery` concern, not this step's.
- [re — Regular expression operations (Python 3.13)](https://docs.python.org/3/library/re.html) — for pulling path/symbol tokens from `## Acceptance criteria` / `## Overview` / `## Deferred` sections without opening source files.
- [The Python Standard Library — Text Processing / string methods](https://docs.python.org/3/library/stdtypes.html#string-methods) — `splitlines`/`partition`/`casefold` for normalizing declared tokens before comparison.
- [pytest — Full documentation](https://docs.pytest.org/en/stable/) — for the new detector and blocking-gate unit tests alongside `TestSuppressionShape` and `TestRunDeterministicChecks`.

## Deferred

- **`claim-vs-delivery` advisory detector** — step 4 (`depends_on: 3`) adds it on `smell_recs`, reusing `build_plan_footprint`. This step only ships `build_plan_footprint` and `orphaned-deliverable`.
- **Elevating `suppression-shape` onto `self_consistency_recs`** — step 2 owns that move.
- **The `self_consistency_recs` field, gate branch, and renderers** — step 1 owns them; this step only appends to the field.
- **Reconciling BACKLOG #100 and the audit-coverage roll-up** — step 5.
- **Reading source code to confirm a deliverable actually works** — that is #66's control-flow trace; this check is intent/consistency at plan altitude only.
- **Promoting `orphaned-deliverable` to `create`-time or relocating `find_dropped_references`** — reuse `find_dropped_references`/`check_files_coherence` only as templates; no create-side wiring moves here.
