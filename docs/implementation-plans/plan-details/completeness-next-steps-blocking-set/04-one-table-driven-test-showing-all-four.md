# Step 4 — Add one table-driven test showing all four readers agree, plus the parent, Integration bare-plan, and advisory-only cases

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one parametrized test in `tests/test_completeness_report.py` that feeds the same audit state to the plan's four readers (`suggested_next_steps`, `suggested_next_step_commands`, `console_summary`, and `_render_grouped_report`'s next-steps block, whose rows live in `tests/cli/test_completeness_cmd.py`) plus their shared fallback `next_stage_command`, and asserts they agree. The table spans stage (step-less, bare, partially detailed, detailed), grade (run, jira), finding kind (blocking correctness, blocking completeness, blocking deterministic, advisory-only), and verdict state (`set` blocking, `set` empty, `incomplete`, `absent`). A smaller set in `tests/cli/test_completeness_cmd.py` pins the `detail` / `split` / `merge` parents, which must follow the tail's verdict. The key design decision is that the table asserts agreement by **one shared predicate** (does any reader offer a stage transition or "no gaps"?) and not by each reader's exact wording, so rewording one reader does not redden the table. On green, a reader added or missed later fails the table, and the original "no gaps remain while a blocking gap is open" message cannot return unnoticed.

## Table of Contents

- [Why](#why) — why a single agreement test is needed after steps 1–3
- [Input](#input) — what steps 1–3 land and what this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two test files
- [Implementation](#implementation) — table axes, the agreement predicate, the named cases
- [Tests](#tests) — the roster, with the invariant each case pins
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — pytest and dataclass docs
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

- Steps 1–3 each carry their own tests, written against one reader or one parent. Each suite is green on its own side of a boundary and says nothing about whether the readers agree with each other.
- The defect this plan closes was a disagreement: the report said "no plan-level gaps remain" while the finalize gate held a blocking gap. A per-reader test cannot fail when a *new* reader is missed.
- One table over all four readers turns "every reader honors the verdict" into a checkable fact. Adding a fifth reader, or a call site that omits the verdict, shows up as a failing row.

## Input

- **Steps 1, 2, 3 (outcomes):** step 1 lands the blocking verdict type (states `set`, `incomplete`, `absent`) in `plan_tool/completeness_report.py` and gives the four readers an optional keyword to carry it. Step 2 builds it from the finalize gate's own values. Step 3 carries it on `_CompletenessTailOutcome` in `plan_tool/cli/authoring.py` and gates the `plan-tool run` entry in the `detail` / `split` / merge blocks. **Read the landed names off those modules; the landed names win over any spelling in this file.** At the time of writing, none of these symbols exist at HEAD (grep for `BlockingVerdict` finds nothing).
- **Reader inputs the table must vary:** `bundle_status` (bare vs detailed; `is_bare`), `detail_grade` (`GRADE_RUN` / `GRADE_JIRA` from `plan_tool/jira_grade.py`), `correctness`, `advisory_conceptual`, and the verdict keyword. `_actionable_conceptual_gaps` demotes completeness gaps on a bare plan or at jira grade; the table must cover that demotion, because it is where a blocking gap was previously dropped.
- **Stage source:** `derive_audit_stage` in `plan_tool/cli/completeness_phases.py` decides the stage, upstream of the verdict. The test builds the verdict from canned ids and deterministic findings and does not derive a stage itself; it varies `bundle_status` across the four stages to prove the readers ignore it for the blocking decision.
- **Limit:** canned recommendations prove the wiring and agreement. They do not prove the model's findings are correct.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `tests/test_completeness_report.py` — add the table-driven agreement test, its small case-builder helper, and the advisory-only and Integration bare-plan cases. Reuse the existing `_rec` and `_steps` / `_cmds` helpers instead of adding a second recommendation factory.
  - `tests/cli/test_completeness_cmd.py` — add the parent cases for `detail`, `split`, and merge (see Tests), using the same stubbed `app.cmd_completeness` sink idiom this file already uses for `_final_qualified_result_sink`.

## Implementation

**Agreement predicate (one helper, used by every row)**
- Collect each reader's output into text, then compute two booleans: *offers a transition or "no gaps"* (contains the `run` / `jira` / `detail` command from `next_stage_command`, or a "no gaps" / "no plan-level gaps remain" phrase) and *names a blocking id*.
- Assert the booleans match across all four readers for the row, and match the row's expected values. Do not compare full strings; wording belongs to each reader's own tests.
- Compare on command **names and ids**, not on prose words ("assert keys, not words").

**Table axes (recommended: one `pytest.param` per row with a readable id)**
- Stage × grade: step-less, bare, partially detailed, and detailed, each at run and jira grade. The readers no longer derive a stage, so the step-less and partially detailed rows pin that a `bundle_status` whose `is_bare` disagrees with `derive_audit_stage` changes nothing a reader says; the parked direct fix failed review on exactly those two stages.
- Finding kind: a blocking `plan-correctness` finding, a blocking `plan-completeness` finding, a blocking deterministic finding with no conceptual id (a missing `intent:`), and an advisory-only finding set.
- Verdict state: `set` with ids, `set` empty, `incomplete`, `absent`.
- Expected outcome by state: `set` with ids, `incomplete`, and `absent` offer **no** transition and end with the re-audit command; `set` empty offers the stage transition for that stage and grade; an advisory finding is listed but never withholds the transition when the verdict is an empty `set`.
- Do not build the full cross product. Pick rows so each axis value appears at least once and the demotion cases (completeness gap on bare plan, any gap at jira grade) each have a blocking row.

**Named cases outside the product**
- **Advisory-only:** empty `set` verdict plus advisory findings. Readers list the advisory gap and still offer the stage; none says "blocked".
- **Integration bare-plan:** a bare plan with a blocking `plan-correctness` finding where the old code printed "no plan-level gaps remain — author the detail bundle". Assert no reader offers `detail` and all four name the open gap and the re-audit.
- **Parents (in `tests/cli/test_completeness_cmd.py`):** for each of `detail`, `split`, merge, drive the parent with a stubbed completeness tail that fills the verdict sink with each of `set`-empty, `set`-with-ids, `incomplete`, and absent. Assert `plan-tool run` (and, in the `detail` block, `plan-tool jira`) appears in the merged `Next steps:` block only for the empty `set`, and that the leading re-audit command is kept in every other state.

**Constraints**
- Build the verdict through step 1's constructor, never by re-testing ids in the test. Re-deriving blocking here would make the test agree with itself and miss the gate.
- Keep fixtures as in-memory objects; no real backend. The `tests/conftest.py` autouse gate already forbids spawning a backend binary.
- Do not change reader or parent code in this step. If a row fails, the defect belongs to step 1, 2, or 3; fix it there.

## Tests

`tests/test_completeness_report.py`

- `test_four_readers_agree_on_transition_and_blocking_ids` — parametrized over the table; asserts all four readers give the same "offers transition" and "names blocking id" answers and that they match the row.
- `test_blocking_completeness_gap_on_bare_plan_is_named_not_demoted_to_no_gaps` — a blocking `plan-completeness` gap on a bare plan is named by every reader; demotion of the *action* must not drop the *blocking* fact.
- `test_jira_grade_blocking_gap_withholds_stage_transition` — same invariant at jira grade, where correctness gaps are withheld from the findings sidecar.
- `test_incomplete_verdict_never_offers_a_stage` — an `incomplete` verdict (audit did not finish) offers no transition even with no ids.
- `test_absent_verdict_reads_as_not_cleared` — an omitted verdict ends with the re-audit and no stage, so a caller that forgets to pass it fails safe.
- `test_advisory_only_findings_are_listed_but_hold_back_no_stage` — empty `set` plus advisory findings lists them and still offers the stage.
- `test_integration_bare_plan_blocking_correctness_gap_does_not_offer_detail` — the Integration bare-plan case above.

`tests/cli/test_completeness_cmd.py`

- `test_detail_parent_offers_run_only_for_empty_blocking_set` — parametrized over the four verdict states.
- `test_split_parent_offers_run_only_for_empty_blocking_set` — same for split.
- `test_merge_parent_offers_run_only_for_empty_blocking_set` — same for merge.
- `test_parent_keeps_leading_reaudit_command_when_run_is_withheld` — the re-audit stays first when `run` is dropped.

### Tests for this step

Every test listed above must be green before this step is finished. Verify the table by mutation: make one reader ignore the verdict (or have a parent re-add `run` unconditionally) and confirm the matching row goes red. The roster covers only the behavior steps 1–3 change; it does not re-test the stage bar, `--json`, or exit codes.

## Acceptance criteria

- One parametrized test in `tests/test_completeness_report.py` runs all four readers per row and fails if any reader's answer differs from the others or from the row's expectation.
- Rows cover bare and detailed stages, run and jira grades, correctness, completeness, and advisory findings, and all three verdict states including an empty `set`.
- The Integration bare-plan case and the advisory-only case each have a named test.
- The `detail`, `split`, and merge parents each have a test showing `plan-tool run` is offered only for an empty `set`.
- Making any one reader ignore the verdict makes at least one row fail (checked by mutation).
- The step changes no file under `plan_tool/`.

## References

- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — read for stacked parametrization and `pytest.param` ids when building the table.
- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — read for `capsys` and `monkeypatch` when capturing console output and stubbing the tail.
- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — read for frozen dataclass construction when building verdicts in fixtures.

## Applicable guardrails

- **The plan's "## Out of scope", the blocking stage bar:** the test builds verdicts from canned ids and must not add a second blocking predicate or derive the stage from `bundle_status.is_bare`.
- **The plan's "## Out of scope", the loop-stop banner:** the `open_findings=` banner is not one of the four readers; the table must not assert on it.
- **The plan's step intent for this step:** prove agreement and parent behavior; do not widen into new reader behavior or production edits.

## Deferred

- Fixing any reader or parent that a row exposes — belongs to the step that owns that reader (steps 1–3), not this test-only step.
- Real-backend or end-to-end `completeness-audit` runs against a Integration plan — the suite stays hermetic; the Integration case is a canned reproduction of its shape.
- Changes to `--json`, `--fail-on-findings`, or exit codes — unchanged by this plan and not asserted here beyond what existing tests pin.
