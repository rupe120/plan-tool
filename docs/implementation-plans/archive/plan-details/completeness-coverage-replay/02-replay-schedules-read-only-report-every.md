# Step 2 — Replay schedules read-only and report every exclusion and missed label

> **Withdrawn 2026-08-20 (user-confirmed).** This detail remains provenance only,
> not an implementation instruction. Do not execute it; a future measurement
> requires a new, bounded design after measured operational audit cost.

## Summary

Build `plan_tool/completeness_coverage_replay.py` as a deterministic, read-only evaluator for the versioned corpus that step 1 supplies. It will replay every predeclared schedule, preserve every exclusion, unresolved comparison, and missed fresh label in a structured result, then render that result without writing files or calling an audit backend. Add fixture-driven component coverage in `tests/test_completeness_coverage_replay.py` and document the pure-test and architecture boundaries in `TESTING.md` and `docs/ARCHITECTURE.md`. On green, a later publication step can consume one reproducible result: a selected pre-ranked candidate, `no-safe-cadence`, or `insufficient-evidence`.

## Table of Contents

- [Summary](#summary) — Reviewer-level description of the replay evaluator and its observable output.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why schedule selection needs a complete, fail-closed replay record.
- [Input](#input) — The validated corpus and schedule contract this step consumes from step 1.
- [Files (creates vs edits)](#files-creates-vs-edits) — New evaluator, fixture, tests, and bounded documentation edits.
- [Implementation](#implementation) — Replay rules, result precedence, reporting requirements, and isolation boundary.
- [Tests](#tests) — Fixture-driven component cases that prove every schedule branch and terminal result.
- [Acceptance criteria](#acceptance-criteria) — Checkable results required before the step is done.
- [References](#references) — JSON and pytest references for deterministic replay coverage.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this a measurement rather than a cache feature.
- [Deferred](#deferred) — Capture, publication, and cache work owned outside this step.

## Why

A candidate cadence is safe only when its observed labels cover every authoritative fresh label in the complete eligible corpus. The manifest's diversity floor is not a smaller selection set. A summary that hides an ineligible case, an eligible case outside a candidate's evaluation, unresolved reuse, or a later missed label can make incomplete evidence look safe. This step turns the captured evidence from step 1 into one complete, repeatable decision record without re-running completeness audits or changing their behavior.

## Input

- **Validated corpus and schedules:** Depend on step 1’s `plan_tool/completeness_coverage_corpus.py` loader and validator, `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md`, and `benchmarks/corpus/completeness-coverage/manifest.json`. Consume their validated cases, exclusions, ordered trajectories, raw-output-backed label registry assignments, candidate-independent policy facts, corpus diversity floor, complete eligible evidence universe, always-fresh control, candidate interval witnesses, and ranked candidate schedules; do not recreate their parsing or admission rules.

- **Observation identity:** Use the whole-fresh-audit pre-run reuse key and ordered attempt trace that step 1 preserves. The key contains static model-visible inputs available before discovery; the trace captures carried/retry inputs that arise while the fresh audit runs. A replay may compare only declared labels and captured identities; it must not read `plan_tool/review_persistence.py:SavedReview`, current repository files, step attribution, or finding prose to fill a gap.

- **Component fixture:** Create `tests/fixtures/completeness_coverage_replay/labelled-cases.json` as a small, static corpus input that exercises every declared replay branch. Keep it as test data only; step 3 owns real disposable-worktree captures.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/completeness_coverage_replay.py` — Provide the read-only schedule evaluator, structured replay result, and deterministic report renderer.
  - `tests/test_completeness_coverage_replay.py` — Cover replay semantics, terminal-result precedence, reporting completeness, and the no-side-effects boundary.
  - `tests/fixtures/completeness_coverage_replay/labelled-cases.json` — Supply labelled trajectories for the component replay matrix.

- **Existing files (edits only):**
  - `TESTING.md` — Add the replay evaluator to the pure component-test guidance under `## What writing tests should look like`, including the fixture-driven and no-backend expectation.
  - `docs/ARCHITECTURE.md` — Add a `## Completeness coverage replay` section that places the corpus contract, read-only evaluator, and later publication in their separate layers.

## Implementation

- **Foundational logic: deterministic schedule replay over ordered trajectories.** Create a public evaluator, such as `plan_tool/completeness_coverage_replay.py:replay_schedules`, that accepts the validated step-1 corpus and returns a structured result. Keep evaluation separate from file publication so step 4 can choose where and how to persist the result.

- **Treat the corpus as immutable evidence.** Read only the validated records supplied by `plan_tool/completeness_coverage_corpus.py`. Do not repair missing identity, assign a label from a recommendation ID or prose, alter a case’s eligibility, or write a normalized corpus beside the source fixture.

- **Evaluate every declared schedule against every eligible case.** Report the always-fresh control and every candidate in manifest priority order. The ordered complete eligible corpus is each candidate's evidence universe; the diversity floor proves breadth but cannot remove a case from an evaluation. Mark the control as non-selectable even when it has complete coverage; select only the first ranked candidate whose comparison for every eligible case resolves without a discovery loss.

- **Model discovery and reuse explicitly.** At each ordered snapshot, record current fresh labels when the schedule chooses full discovery. Carry the predecessor's whole observed label set only for an unchanged, reuse-eligible whole fresh-audit pre-run key with an eligible predecessor; a changed key must not inherit old labels. The completed predecessor trace supports the carried result but does not divide the whole audit into reusable scans.

- **Derive the declared observation policy once per candidate.** Snapshot zero is full discovery. At a later snapshot, terminal confirmation is full discovery; otherwise a changed pre-run key is full discovery, then an interval-due unchanged snapshot is full discovery, and only an unchanged non-terminal non-due snapshot reuses its eligible predecessor. Derive that result for every candidate from the captured ordered position, terminal flag, and pre-run reuse key; do not read one stored policy result. The evaluator reports missing or contradictory source facts as unresolved and never silently chooses reuse.

- **Reject unexercised selectable schedules.** Require every selectable candidate interval to be at least two and to have eligible ordered witness evidence of an unchanged non-terminal reuse plus a later unchanged non-terminal interval-due full discovery at that exact interval. Keep the always-fresh control non-selectable and report it separately. A candidate without either witness returns `insufficient-evidence` even if its shorter trajectories show no loss.

- **Keep labels on discovery and carry paths.** Full discovery introduces or refreshes its authoritative whole-unit label set. A valid reuse carries that complete predecessor set into the observed union; it never drops labels because their finding was plan-level or step-attributed.

- **Compare declared labels, not model wording.** Use a label only when the validated case links it to a manifest registry entry and raw fresh output at a recorded attempt. The same declared label id is the sole cross-snapshot equality relation. An undeclared, ambiguous, or output-unlinked assignment remains unresolved; no recommendation id, anchor, or prose comparison repairs it.

- **Report gaps instead of stopping early.** Emit every case exclusion with its case identity and contract-provided reason. Emit every unresolved comparison and every discovery loss with enough context to locate the candidate, trajectory, snapshot, whole-fresh-audit observation, and label. Emit a separate unresolved record if an eligible case has no evaluation for a candidate. Continue evaluating later candidates and snapshots after the first problem.

- **Use the fresh-label comparison as the only loss rule.** A fresh label absent from the schedule’s observed union is a discovery loss. An excluded or non-authoritative current series, a missing whole-unit key, or reuse without an eligible predecessor remains unresolved rather than becoming a carried label or an inferred miss.

- **Make terminal outcomes ordered and fail closed.** Return `insufficient-evidence` when a candidate lacks its own required witnesses, an eligible case is absent from a candidate evaluation, or any eligible comparison is unresolved, even if other candidates also lose labels. Return `no-safe-cadence` only when every candidate has been evaluated over the complete eligible corpus and no selectable candidate is loss-free. Otherwise return the first ranked loss-free candidate.

- **Render from the structured result.** Provide a deterministic renderer, such as `plan_tool/completeness_coverage_replay.py:render_replay_report`, for step 4 to use. Preserve manifest rank and trajectory order, and use the corpus contract’s canonical ordering for repeated records so identical input produces the same report.

- **Keep the module off the audit path.** Do not import or invoke `plan_tool/review.py:check_plan_audit`, `plan_tool/review.py:audit_plan_until_stable`, or backend helpers. Do not reuse `plan_tool/scenario_capture.py:capture_scenario`; it records opt-in telemetry and permits provenance states that the step-1 corpus intentionally excludes.

- **Document the boundary.** In `docs/ARCHITECTURE.md`, state that the evaluator consumes captured evidence and reports a decision record only. In `TESTING.md`, state that `tests/test_completeness_coverage_replay.py` remains an unmarked component suite with no invoker seam because replay never calls a backend.

## Tests

### Tests for this step

- `test_labelled_cases_fixture_exercises_discovery_reuse_changed_input_periodic_and_terminal_branches` — Asserts `tests/fixtures/completeness_coverage_replay/labelled-cases.json` contains the branch coverage the replay contract requires.

- `test_snapshot_zero_changed_interval_and_terminal_policy_is_derived_per_candidate` — Asserts the evaluator derives the declared observation order separately from candidate-independent capture facts and reports contradictory facts rather than selecting an alternate interpretation.

- `test_always_fresh_control_is_reported_but_never_selected` — Asserts the control appears in the report with its coverage result but cannot become the selected cadence.

- `test_replay_selects_the_first_ranked_loss_free_candidate` — Asserts multiple safe candidates select the lowest declared rank.

- `test_replay_reports_every_missed_label_without_stopping` — Asserts losses later in a trajectory and in later candidates remain present after an earlier loss.

- `test_reuse_carries_labels_only_from_an_unchanged_eligible_whole_audit` — Asserts a valid reuse observation includes only the latest eligible observation for that unchanged whole fresh-audit pre-run key.

- `test_changed_whole_audit_key_cannot_reuse_prior_labels` — Asserts a changed whole fresh-audit pre-run key blocks carrying stale labels and follows its declared discovery path.

- `test_reuse_without_an_eligible_predecessor_is_reported_unresolved` — Asserts the report names the unresolved comparison instead of treating it as covered or silently skipped.

- `test_reuse_carries_the_complete_predecessor_label_set` — Asserts reuse retains every label from its authoritative predecessor regardless of plan-level or step attribution.

- `test_non_authoritative_or_unkeyed_series_is_reported_unresolved` — Asserts an incomplete, failed, malformed, skipped, budget-limited, unconfirmed, or unkeyed series remains unresolved and is never matched against finding text.

- `test_unconfirmed_fresh_series_is_reported_unresolved` — Asserts a fresh series without `confirmed-dry` or `confirmed-low-yield` cannot supply comparison labels.

- `test_output_unlinked_or_ambiguous_label_is_reported_unresolved` — Asserts a label without one declared registry entry and recorded raw-response evidence cannot become coverage.

- `test_excluded_case_names_its_reason_and_cannot_count_as_coverage` — Asserts every ineligible case remains visible in the report and cannot satisfy required evidence.

- `test_periodic_full_discovery_refreshes_the_observed_label_set` — Asserts a scheduled periodic discovery uses that snapshot’s fresh labels rather than carrying an older set.

- `test_selectable_interval_below_two_is_rejected_before_replay` — Asserts an interval that cannot exercise the required reuse branch is not a candidate.

- `test_candidate_without_a_nonterminal_interval_due_witness_returns_insufficient_evidence` — Asserts a large candidate interval cannot select from a short trajectory that never reaches its periodic refresh.

- `test_missing_terminal_confirmation_leaves_required_evidence_incomplete` — Asserts a candidate without its required terminal confirmation cannot be selected.

- `test_missing_required_comparison_returns_insufficient_evidence` — Asserts absent required evidence yields the fail-closed terminal result.

- `test_unresolved_required_comparison_returns_insufficient_evidence` — Asserts an unresolved required branch has the same fail-closed result.

- `test_every_eligible_case_is_in_every_candidate_evidence_universe` — Asserts the manifest's diversity floor cannot omit an otherwise eligible trajectory from a candidate.

- `test_eligible_case_without_a_candidate_evaluation_returns_insufficient_evidence` — Asserts a missing candidate/case result remains visible and blocks selection.

- `test_loss_outside_the_diversity_floor_prevents_selection` — Asserts a missed label in any eligible trajectory rejects a candidate even when the minimum required trajectories are loss-free.

- `test_incomplete_evidence_precedes_no_safe_cadence` — Asserts unresolved or absent required evidence wins over losses when choosing the terminal result.

- `test_complete_lossy_candidates_return_no_safe_cadence` — Asserts complete evidence with no loss-free candidate returns `no-safe-cadence`.

- `test_replay_is_deterministic_read_only_and_backend_free` — Asserts identical corpus input produces the same structured and rendered results, leaves the fixture unchanged, and uses no backend or write path.

Every test above must be green before this step is considered complete.

## Acceptance criteria

- `plan_tool/completeness_coverage_replay.py:replay_schedules` returns a result for the always-fresh control and every declared candidate without invoking an audit or model backend.

- Each replay result exposes every exclusion, unresolved comparison, omitted eligible candidate/case evaluation, and missed fresh label with the case and schedule context needed to inspect it.

- The replay uses the manifest's snapshot-zero, changed-input, interval, and terminal policy in that precedence order, derives it separately for each candidate from candidate-independent capture facts, and reports a missing or contradictory source fact as unresolved.

- A selectable candidate has an interval of at least two plus its own eligible reuse and non-terminal interval-due witness, and reuse carries its authoritative predecessor's complete label set without attribution-based filtering.

- Cross-snapshot label equality is limited to the declared registry id backed by raw output in the recorded fresh attempt; recommendation ids, anchors, and prose never decide equality.

- A reused observation carries labels only when its whole fresh-audit pre-run identity is unchanged and it has an eligible predecessor; its complete prior attempt trace is provenance, and step attribution never permits partial reuse.

- A missing candidate witness or unresolved eligible candidate/case comparison returns `insufficient-evidence` before candidate losses can produce `no-safe-cadence`; the diversity floor never limits a candidate's evidence universe.

- Complete evidence over every eligible case selects only the first ranked loss-free candidate; complete evidence with no such candidate returns `no-safe-cadence`.

- Replaying `tests/fixtures/completeness_coverage_replay/labelled-cases.json` twice produces the same structured result and rendered report without changing the fixture.

- `uv run pytest tests/test_completeness_coverage_replay.py -q` passes.

- `TESTING.md` and `docs/ARCHITECTURE.md` describe the evaluator as fixture-driven, read-only, deterministic, and separate from audit execution and result publication.

## References

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use stable JSON handling for fixture input and any deterministic structured rendering.

- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Review canonical JSON rules when preserving replay output order and reproducibility.

- [pytest — Parametrizing Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Build the candidate, branch, and terminal-result matrix without duplicate test logic.

- [pytest — Monkeypatching Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Guard the read-only, no-backend boundary in component tests.

## Applicable guardrails

- **The plan’s “## Plan intent”, evidence-bound measurement:** Keep this step limited to evaluating captured evidence. It must not create a cache, re-check lane, or changed audit behavior.

- **The plan’s “## Step intent”, explicit observation relation:** Apply the declared fresh-versus-reuse relation and fail closed when the corpus cannot support it.

- **The plan’s “## Out of scope”, audit and CLI behavior:** Do not change completeness prompts, pass budgets, gates, exit codes, saved-report semantics, or add a command surface.

- **The plan’s “## Out of scope”, label and decision policy:** Do not infer labels from content, choose an undeclared cadence, or expand the measurement to another benchmark.

## Deferred

- Real labelled captures in `benchmarks/corpus/completeness-coverage/cases.json` — Step 3 owns disposable-worktree evidence collection and source-history preservation.

- Durable replay-result files and BACKLOG status updates — Step 4 owns publication after it combines this evaluator with the captured corpus.

- BACKLOG #173 cache and re-check behavior — Remains outside this measurement until the later published result justifies a scoped follow-up.
