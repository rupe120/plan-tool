> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add the `claim-vs-delivery` advisory detector on `smell_recs`, reusing the footprint matcher

## Summary

Add a new deterministic detector `detect_claim_vs_delivery` to `plan_tool/review.py` that flags a deliverable named in the plan's `## Acceptance criteria` prose (with `## Overview` read only as corroboration) that no step actually delivers — the inverse of step 3's `orphaned-deliverable` (which asks "does anything consume this deliverable?"; this asks "does any step deliver this claim?"). It reuses step 3's `build_plan_footprint` for the "what's declared/delivered" side and parses the claim prose itself, then fuzzy-matches each artifact-shaped claim token against the declared paths/symbols. The key design decision: this finding stays **advisory** (`severity="info"` on `smell_recs`, source `claim-vs-delivery`) because fuzzy prose matching is the main false-positive risk, so it must never block — it rides the existing `collect_smell_findings` fan-out, unlike `orphaned-deliverable` which rides the blocking-capable `self_consistency_recs` bucket. On green, a `#95`-shaped plan that claims a mechanism in prose with no delivering step surfaces one `info` `claim-vs-delivery` finding that renders under `### Smells (advisory)`, never flips rc, and reads no source files.

## Table of Contents

- [Why](#why) — the claimed-but-undelivered gap this closes
- [Input](#input) — step 3's `build_plan_footprint` this step reuses
- [Files (creates vs edits)](#files-creates-vs-edits) — one detector, one wiring/prose edit, two test files
- [Implementation](#implementation) — the claim parse, the fuzzy match, and the advisory wiring
- [Tests](#tests) — trip / no-trip, fuzzy tolerance, and advisory-routing cases
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the in-file siblings and stdlib docs that matter here
- [Deferred](#deferred) — promotion to blocking and other steps' work

## Why

A plan can **claim** a deliverable in its prose that no step ever delivers. The `#95` `prompt-budget-advisory` plan named a mechanism in its `## Acceptance criteria` while no step's declared footprint delivered it — the claim read as satisfied, but the deliverable was never built. `create.py:find_dropped_references` catches a version of this at **create** time over the distilled seed, but nothing catches it at **completeness** time over the authored plan-plus-detail. Step 3 added the "does anything consume this deliverable?" question (`orphaned-deliverable`); this step adds the opposite one — "does any step deliver this claim?" — as a no-Claude, plan-altitude check. It stays advisory because prose naming a mechanism differently than the step that delivers it is the dominant false-positive risk; keeping it on `smell_recs` means a false positive surfaces for a human but never flips rc.

## Input

- **`build_plan_footprint`** — produced by step 3 (`plan_tool/review.py`, `depends_on: 3`). Step 3 ships this shared matcher returning a frozen result with named sets for the plan's **declared** side (`declared_paths`, `declared_symbols`) and its **referenced** side (`referenced_paths`, `referenced_symbols`). This step reuses the **declared** side as the "what's delivered" set to test claims against. Reference step 3's outcome, not its mechanism — if a field was renamed at implementation time, use whatever step 3 actually landed. Do **not** add a new field to `build_plan_footprint` for this step; parse the claim prose here (see Implementation).
- **Limit on verification:** the footprint reads only plan and detail markdown, never source files. This detector must honor the same boundary — it can confirm a claim maps to a *declared* deliverable, not that the deliverable *works* (that is `#66`'s job).

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/review.py`
  - Add `detect_claim_vs_delivery(plan, repo_root, *, plan_name) -> list[Recommendation]`, next to `detect_suppression_shape` and step 3's `detect_orphaned_deliverable`. Source `"claim-vs-delivery"`, `severity="info"`, `step_id=None` (plan-altitude claim), id via `_make_rec_id`.
  - Add `detect_claim_vs_delivery` to the `collect_smell_findings` fan-out so its recs flow onto `smell_recs` (the same channel `validate_feature_refs` / `detect_suppression_shape` use). Update `collect_smell_findings`'s docstring to name the new advisory detector.
  - Optional: a module constant `CLAIM_VS_DELIVERY_SOURCE = "claim-vs-delivery"` so the detector and any downstream keying share one symbol.
- `plan_tool/cli/completeness_phases.py`
  - Add `claim-vs-delivery` to the two advisory-smell enumerations that name the bucket's members: the `### Smells (advisory)` description block in `_render_grouped_report` and the `"smells"` JSON-group comment in `_render_completeness_json`. Add it to the **current** member list — step 2 may have removed `suppression-shape` from these; do not restate step 2's removal, just insert `claim-vs-delivery`.
- `tests/test_review.py`
  - Add unit tests for `detect_claim_vs_delivery`, next to `TestSuppressionShape`.
- `tests/cli/test_completeness_cmd.py`
  - Extend `TestRunDeterministicChecks` (assert claim recs land on `smell_recs`, not `self_consistency_recs`, and don't change `_det_total`) and add an advisory-routing case (a claim-vs-delivery rec on `smell_recs` never blocks).

## Implementation

**Foundational logic:** a plan-altitude, no-Claude check that answers "does any step deliver what the plan's prose claims?" — extract artifact-shaped tokens from the claim sections, and for each one with no declared match (even fuzzy), emit one advisory finding. The core anti-false-positive rule mirrors step 3: anchor every match on declared paths / path-derived symbols, never a bare English noun.

**Parsing the claim tokens.**

- **Treat `## Acceptance criteria` as the sole deliverable-pinning section** — pull it with `split_body_sections` (`plan_tool/review.py`) over the plan body, following `_extract_acceptance_criteria`'s pattern. **`## Overview` is read only as corroboration, never as a standalone claim source:** a token that appears *only* in `## Overview` and not in `## Acceptance criteria` is never flagged. This mirrors `create.py:find_dropped_references`, which pins deliverables from `## Acceptance criteria` alone and reads other sections only to corroborate — `## Overview` routinely names pre-existing/context symbols the plan builds on but does not deliver (e.g. a backtick-quoted `apply_finding` or `collect_smell_findings`), and those are code-shaped, backtick-quoted, and match no step's declared footprint, so flagging an Overview-only token would trip on essentially every normal plan and break the detector's "stays quiet on normal plans" guarantee.
- **Extract only artifact-shaped tokens.** Pull backtick-quoted path mentions via `extract_path_mentions` (`plan_tool/detail.py`) and backtick-quoted identifier-shaped tokens (e.g. snake_case / CamelCase / dotted — reuse `create.py:_looks_like_code` directly rather than reimplementing, since its code-shape test also admits other forms such as digit-bearing and `@$`-punctuated tokens, and keying only on the three named shapes would diverge from it). **Never treat a plain English word as a claim** — that is the whole false-positive guard. One way: require the token to be backtick-quoted *and* carry identifier/path punctuation.
- **When in doubt, don't flag.** A token that is ambiguous between prose and code should be skipped. Prefer false negatives — this check earns its keep only if it stays quiet on normal plans.

**Testing each claim against the declared footprint.**

- **Build the footprint once** via step 3's `build_plan_footprint`, and use its declared side (`declared_paths` + `declared_symbols`) as the delivered set.
- **A claim token is "delivered" when it matches a declared path or symbol** — exact match after normalization, **or** a fuzzy near-match via `difflib.SequenceMatcher(...).ratio() >= <threshold>`. `check_files_coherence`'s `_NEAR_MISS_RATIO` near-miss logic (`plan_tool/review.py`) is the template for the fuzzy path/symbol match; reuse its ratio convention rather than inventing a new threshold. The fuzzy step is what lets a claim naming a declared symbol with minor variance (`foo_widgets` vs declared `foo_widget`) count as delivered.
- **A claim token with no declared match — even fuzzy — is flagged.** Optionally refine: a token whose only match sits under `## Deferred` / `## Out of scope` prose is still "not delivered here" and may be flagged too; keep this refinement conservative and skip it if it raises the false-positive rate. The primary, testable rule is "no declared match at all."
- **Emit shape:** one `Recommendation` per claimed-but-undelivered token — `source="claim-vs-delivery"`, `severity="info"`, `step_id=None`, `id=_make_rec_id(None, "claim-vs-delivery", <token>)`, a `title` naming the claimed deliverable, and a `body` explaining that the plan's prose claims it but no step's declared footprint delivers it (confirm a step delivers it, or drop the claim).

**Advisory wiring (`collect_smell_findings`).**

- **Route through `collect_smell_findings`, not `_run_deterministic_checks` directly.** `claim-vs-delivery` is a genuine advisory plan smell, so it belongs in the `collect_smell_findings` fan-out beside `validate_feature_refs` / `detect_suppression_shape` / `detect_self_referential_features`. The battery already assigns `smell_recs = collect_smell_findings(...) + granularity_recs`, so the new detector reaches `smell_recs` with no change to `_run_deterministic_checks` itself.
- **`inspect.py` picks it up for free.** `collect_smell_findings` is shared with `plan_tool/cli/inspect.py:cmd_inspect_smells`; adding an advisory smell there surfaces it on the inspect smells display too. That is correct for an advisory smell — **no `inspect.py` edit is needed or in scope.**
- **Stays out of the gate and the count.** Because it rides `smell_recs`, it never enters `_completeness_has_blocking_findings` and never inflates `_det_total` — both already exclude `smell_recs`. Nothing to wire; this is the reason it lands on `smell_recs` rather than step 1's `self_consistency_recs`.
- **Stays out of the `--iterate` apply loop.** `collect_smell_findings` is deliberately *not* wired into `review.collect_deterministic_findings`, so `claim-vs-delivery` never reaches `apply_finding` — a prose editor could not fix a claimed-but-undelivered deliverable anyway.

**Rejected alternative:** matching claim prose against **source** symbols by free-text similarity. Rejected for the same reason as step 3 — the dominant false-positive risk is prose naming a mechanism differently than the step delivering it, and opening source would blur this into a semantic review and cross into `#66`'s territory. Anchoring on declared paths/symbols with a fuzzy tolerance, over plan/detail markdown only, keeps the check cheap and quiet enough to stay advisory.

**One gotcha to respect:** `detect_claim_vs_delivery` and step 3's `detect_orphaned_deliverable` each build their own footprint (one runs via `collect_smell_findings`, the other appends to `self_consistency_recs` in the battery), so `build_plan_footprint` runs twice per audit. Both passes are cheap and read no source files, so the duplicate is acceptable; consolidating to one shared footprint pass is noted in Deferred.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add every test below **with** the implementation; all must be green before the step is considered done.

`tests/test_review.py` (next to `TestSuppressionShape`):

- `test_claim_vs_delivery_trips_on_claimed_undelivered_symbol` — an `## Acceptance criteria` claim naming a backtick-quoted symbol no step declares emits one `info` finding, `source="claim-vs-delivery"`, `step_id=None`.
- `test_claim_vs_delivery_no_trip_when_step_declares_it` — a step whose `files:`/`creates:` footprint delivers the claimed path/symbol suppresses the finding.
- `test_claim_vs_delivery_fuzzy_match_tolerates_minor_variance` — a claim naming a near-variant of a declared symbol (small edit distance) does not trip.
- `test_claim_vs_delivery_ignores_bare_prose_nouns` — a plain-English claim ("the workflow runs end to end") with no code-shaped token never trips.
- `test_claim_vs_delivery_overview_alone_does_not_trip` — a claim token that appears *only* in `## Overview` (not in `## Acceptance criteria`) does not trip; `## Overview` is corroboration only.
- `test_claim_vs_delivery_opens_no_source_files` — a plan with real `.py` paths on disk reads no source (only plan/detail markdown).
- `test_claim_vs_delivery_is_info_severity` — the emitted rec is `severity="info"` (advisory).
- `test_claim_vs_delivery_reproduces_prompt_budget_shape` — a `#95`-shaped plan (mechanism claimed in prose, no delivering step) trips.

`tests/cli/test_completeness_cmd.py`:

- `TestRunDeterministicChecks::test_claim_vs_delivery_lands_on_smell_recs` — the battery routes claim-vs-delivery recs to `smell_recs` (not `self_consistency_recs`), and they don't change `_det_total`.
- `TestCompletenessHasBlockingFindings::test_claim_vs_delivery_on_smell_recs_never_blocks` — an `info` claim-vs-delivery rec on `smell_recs` leaves `has_blocking_findings` False (the "smells never gate" contract holds).

## Acceptance criteria

- `detect_claim_vs_delivery` returns one `info` / `source="claim-vs-delivery"` finding for a claim naming an artifact-shaped token no step's declared footprint delivers (exact or fuzzy), and returns `[]` when a step delivers it, when the token is a plain English noun, or when a near-variant is declared.
- The detector reuses step 3's `build_plan_footprint` declared side and opens no `.py`/source files — only plan and detail markdown.
- `_run_deterministic_checks` places claim-vs-delivery recs on `_DeterministicReport.smell_recs` (via `collect_smell_findings`), they render under `### Smells (advisory)`, and they do not change `_det_total`.
- A claim-vs-delivery finding never blocks under `--fail-on-findings` (it rides `smell_recs`); the existing "smells never gate" tests stay green.
- `emitted rec.step_id is None` and `rec.severity == "info"`.
- All new tests in `tests/test_review.py` and `tests/cli/test_completeness_cmd.py` pass.

## References

The key pointers are the in-file siblings this step models — reuse their shape and boundaries rather than inventing new ones:

- `detect_suppression_shape` and step 3's `detect_orphaned_deliverable` (`plan_tool/review.py`) — the sibling deterministic detectors this one sits beside: `Recommendation` shape, `_make_rec_id`, and the plan-altitude / no-source-read boundary.
- `build_plan_footprint` (`plan_tool/review.py`, step 3) — the shared matcher; this step reads its declared side.
- `collect_smell_findings` (`plan_tool/review.py`) — the advisory fan-out onto `smell_recs` this detector joins; also feeds `inspect.py:cmd_inspect_smells`.
- `check_files_coherence` and its near-miss helper (`plan_tool/review.py`) — the `SequenceMatcher` / `_NEAR_MISS_RATIO` fuzzy path-matching template for deciding a claim token matches a declared entry.
- `create.py:find_dropped_references` (`plan_tool/create.py`) — the create-side twin catching claimed-but-unpinned artifacts; reuse its logic as a template only (relocating it is out of scope).
- `split_body_sections` / `_extract_acceptance_criteria` (`plan_tool/review.py`) and `extract_path_mentions` (`plan_tool/detail.py`) — parse claim sections and pull path/token mentions without opening source.

Supporting stdlib/test docs:

- [difflib — Helpers for computing deltas (Python 3.13)](https://docs.python.org/3/library/difflib.html) — `SequenceMatcher.ratio()` / `get_close_matches` for the fuzzy claim-vs-declared match.
- [re — Regular expression operations (Python 3.13)](https://docs.python.org/3/library/re.html) — for pulling code/path-shaped tokens from `## Acceptance criteria` / `## Overview` sections.
- [The Python Standard Library — Text Processing / string methods](https://docs.python.org/3/library/stdtypes.html#string-methods) — `splitlines`/`partition`/`casefold` for normalizing tokens before comparison.
- [pytest — Full documentation](https://docs.pytest.org/en/stable/) — for the new detector and advisory-routing unit tests alongside `TestSuppressionShape` and `TestRunDeterministicChecks`.

## Deferred

- **Promoting `claim-vs-delivery` to blocking** — stays advisory on `smell_recs` until its false-positive rate is measured on real plans; a follow-up plan moves it onto the gate-read bucket once precision is proven. Owned by the plan's Deferred list, not this step.
- **The blocking-capable `self_consistency_recs` bucket, its gate branch, and renderers** — step 1 owns them; `orphaned-deliverable` and the elevated `suppression-shape` ride that bucket, not this detector.
- **`build_plan_footprint` itself and the `orphaned-deliverable` detector** — step 3 owns them; this step only reuses the footprint's declared side.
- **Consolidating the two footprint passes into one shared build** — `detect_orphaned_deliverable` and `detect_claim_vs_delivery` each build their own footprint; folding both onto one pass is a cross-detector refactor left for reconcile, since both passes are cheap and read no source files.
- **Relocating `find_dropped_references` to run at completeness time** — reuse its logic as a template only; moving the create-side wiring is out of scope (plan Out of scope).
- **Reading source to confirm a claimed deliverable actually works** — that is `#66`'s control-flow trace; this check is intent/consistency at plan altitude only.
- **Reconciling BACKLOG `#100` and the audit-coverage roll-up** — step 5.
