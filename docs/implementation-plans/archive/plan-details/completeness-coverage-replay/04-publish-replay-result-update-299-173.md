# Step 4 — Publish the replay result and update #299 and #173 without changing audit behavior

> **Withdrawn 2026-08-20 (user-confirmed).** This detail remains provenance only,
> not an implementation instruction. Do not execute it; a future measurement
> requires a new, bounded design after measured operational audit cost.

## Summary

Publish the completed corpus replay as `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json` and its human-readable rendering as `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md`. Update `BACKLOG.md` so BACKLOG #299 records the dated measured outcome and BACKLOG #173 either becomes available for separate re-scoping or remains explicitly deferred. Treat the step 2 evaluator’s structured result as the only decision source; do not rerun audits or add a cache path. On green, the two published artifacts and every current-status reference in `BACKLOG.md` agree on one result.

## Table of Contents

- [Summary](#summary) — Reviewer-level description of the published evidence and backlog decision.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why the replay needs a durable decision record.
- [Input](#input) — The completed corpus and replay outputs this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Published artifacts and bounded backlog edits.
- [Implementation](#implementation) — Publication rules, outcome handling, and audit-behavior boundary.
- [Tests](#tests) — Existing deterministic suites that validate the inputs and replay.
- [Acceptance criteria](#acceptance-criteria) — Observable publication and backlog-state requirements.
- [References](#references) — Canonical JSON guidance for the published result.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this a decision record.
- [Deferred](#deferred) — Work that remains outside the publication step.

## Why

The corpus and replay do not affect operators until their result is published as evidence that can be checked later. A hand-written conclusion or a stale backlog status could make BACKLOG #173 appear ready without a loss-free cadence, or leave it blocked after the precondition is met. This step makes the evaluator’s fail-closed result the visible decision gate while leaving the existing audit path untouched.

## Input

- **Step 1 corpus contract:** Read the completed `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md` and `benchmarks/corpus/completeness-coverage/manifest.json` through the landed corpus loader. Preserve the contract version, ordered schedules, case identities, exclusions, and canonical serialization rules; do not repair incomplete evidence during publication.

- **Step 2 replay output:** Consume the structured result and deterministic report renderer that step 2 lands in `plan_tool/completeness_coverage_replay.py`. Use the landed public API and its actual result shape rather than reimplementing schedule selection or report formatting here.

- **Step 3 captured evidence:** Evaluate the completed `benchmarks/corpus/completeness-coverage/cases.json` and `benchmarks/corpus/completeness-coverage/fixtures.bundle`, including the complete eligible-case universe, confirmed fresh-label evidence, candidate-independent policy facts, raw-output-backed label assignments, candidate interval witnesses, and explicit exclusions. They are the complete measurement input; do not read current repository state, audit reports, recommendation ids, anchors, or finding prose to fill gaps.

- **Audit behavior boundary:** `plan_tool/review.py:check_plan_audit`, `plan_tool/review.py:audit_plan_until_stable`, `plan_tool/review.py:render_plan_audit_prompt`, and `plan_tool/completeness_report.py:resolve_reusable_audit` remain unchanged. Their current reports and reuse behavior are not publication input.

## Files (creates vs edits)

- **New files:**
  - `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json` — Store the canonical machine-readable projection of the completed replay result and its corpus provenance.
  - `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md` — Store the deterministic human-readable rendering of that same result.

- **Existing files (edits only):**
  - `BACKLOG.md` — Update the `#299` and `#173` entries and their current-status references under `## Priority (mission-grounded)`, including the `Ready seeds` and `Parked / defer` rows where the completed measurement changes their meaning.

## Implementation

- **Foundational logic: publish one evidence-bound replay decision.** Validate the completed corpus, run the step 2 evaluator once over it, and publish its structured result without adding interpretation. The preferred approach is to use the landed evaluator and renderer directly, so the JSON artifact and Markdown report cannot drift into separate conclusions.

- **Keep the result reproducible.** Derive `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json` only from the validated manifest, cases, and replay result. Retain the corpus version and input identities the landed contract exposes. Do not add a wall-clock value to the deterministic result unless that value is already part of the evaluator’s result contract; record the publication date in the BACKLOG #299 provenance handoff instead.

- **Preserve every replay outcome.** Publish the terminal result, candidate order, fixed observation policy, each candidate’s derived policy decisions and interval witnesses, complete per-candidate eligible-case universe, label-registry provenance, exclusions, unresolved comparisons, and discovery losses exactly as the evaluator reports them. A selected cadence must retain its declared full-discovery and terminal-confirmation requirements. `insufficient-evidence` and `no-safe-cadence` must remain explicit outcomes, not empty selections or manually softened conclusions.

- **Render, do not summarize by hand.** Write `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md` from the step 2 renderer’s result for the same input. Preserve its ordering and complete problem rows; do not sort, trim, or turn an unresolved comparison into prose-only rationale.

- **Complete #299 regardless of the terminal outcome.** In `BACKLOG.md`’s `#299` entry, replace the ready-to-author state with a dated handoff that names the two published artifacts and the exact replay outcome. A published negative result completes the measurement just as a selected cadence does.

- **Make #173 follow the result, not a preference.** When the result selects a cadence, update `BACKLOG.md`’s `#173` precondition and status to permit a separately scoped follow-up that uses the published cadence. When the result is `insufficient-evidence` or `no-safe-cadence`, keep #173 deferred and state that this measured result does not permit authoring or implementation.

- **Sweep active backlog summaries.** Update each current-status mention of #299 and the #173 prerequisite state, including the priority narrative and status-table rows. Keep unrelated #173 references that describe other entries’ ownership or dependencies unless the publication changes their stated fact.

- **Do not change audit behavior.** Do not edit `plan_tool/review.py`, `plan_tool/completeness_report.py`, saved-review artifacts, prompts, CLI wiring, or test configuration. Do not run a fresh completeness audit, create a cache, add a re-check lane, or make the selected cadence active behavior.

## Tests

This non-code step adds no test module. Reuse the landed deterministic suites before publishing.

- `tests/test_completeness_coverage_corpus.py` — Validates the manifest and captured cases before they become publication input.

- `tests/test_completeness_coverage_replay.py` — Validates the replay’s terminal-result precedence, loss reporting, ordering, and backend-free behavior.

### Verification (non-code step)

1. Run `uv run pytest tests/test_completeness_coverage_corpus.py tests/test_completeness_coverage_replay.py -q` against the completed corpus and evaluator.

2. Parse `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json` and confirm its result, per-candidate derived policy decisions and interval witnesses, complete per-candidate eligible-case universe, label provenance, candidate ordering, exclusions, unresolved comparisons, and losses match a fresh deterministic evaluation of the committed corpus and fixture bundle.

3. Regenerate the Markdown through the landed step 2 renderer and confirm it matches `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md` for the same replay result.

4. Inspect the report and JSON together: every candidate and every reported problem appears in both views without a changed terminal result.

5. Search `BACKLOG.md` for `#299`, `#173`, and `completeness-coverage-replay`; confirm no active summary still calls the measurement a ready seed or calls #173 pending a replay that has already been published.

6. Inspect the step diff and confirm it changes only `BACKLOG.md`, `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json`, and `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md`.

## Acceptance criteria

- `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json` is valid JSON and records the deterministic replay result with the corpus provenance needed to identify its input.

- `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md` is the renderer-produced view of the same result and retains every candidate, its derived policy decisions, interval witness, complete eligible-case universe, every exclusion, unresolved comparison, and discovery loss.

- Re-evaluating unchanged committed corpus inputs produces the same result content and report text without an audit or model call.

- A selected cadence retains its declared discovery and final-confirmation requirements; a non-selected result remains explicitly `insufficient-evidence` or `no-safe-cadence`.

- BACKLOG #299 records the dated published outcome and points readers to both result artifacts.

- BACKLOG #173 is available only for separate re-scoping after a selected result; otherwise its deferred status names the published result as the reason it remains blocked.

- `uv run pytest tests/test_completeness_coverage_corpus.py tests/test_completeness_coverage_replay.py -q` passes.

- No audit behavior, cache behavior, saved-report semantics, or CLI surface changes in this step.

## References

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use stable JSON handling when publishing the structured replay result.

- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Preserve deterministic JSON ordering and representation for reproducible evidence.

## Applicable guardrails

- **The plan’s “## Plan intent”, evidence-bound result:** Publish the measured decision only; do not turn it into active audit behavior.

- **The plan’s “## Step intent”, #173 decision gate:** Let the published terminal result determine whether #173 can be re-scoped or stays deferred.

- **The plan’s “## Out of scope”, audit and CLI behavior:** Keep all completeness execution, prompts, budgets, gates, exit behavior, saved-report semantics, and command surfaces unchanged.

- **The plan’s “## Out of scope”, matching and decision policy:** Do not infer labels, add a new cadence, or expand the corpus while preparing the publication.

## Deferred

- BACKLOG #173 cache and re-check implementation — A selected result permits a separately scoped follow-up; this step does not create or activate it.

- Additional corpus collection after `insufficient-evidence` or `no-safe-cadence` — Keep the measured result intact; any expanded evidence set needs separate scope.

- Audit execution, report persistence, and CLI changes — These remain outside the publication-only file set.
