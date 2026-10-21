# Step 4 — Publish the new default and reconcile BACKLOG

## Summary

Publish the conditional create-time `test_command` behavior in `PLAN_FORMAT.md` and `docs/BENCHMARK_DESIGN.md`, then update `BACKLOG.md` #234 to reflect the delivered work. The key decision is to distinguish the optional `Plan.test_command` field from a universal default: `create` writes a command only through the authorized outcomes from step 3. Keep the benchmark’s hidden-test command under benchmark control. On green, the three documents describe the same behavior, and #234 retains only the deferred cost-bound follow-up.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation and backlog update.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The stale publication claims this step removes.
- [Input](#input) — The completed field and creation contracts this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation files this step changes.
- [Implementation](#implementation) — Required documentation and backlog reconciliation rules.
- [Tests](#tests) — Non-code verification and related creation coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Contract and benchmark sources.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this documentation-only step.
- [Deferred](#deferred) — The remaining cost-bound follow-up.

## Why

`docs/BENCHMARK_DESIGN.md` and `BACKLOG.md` still state that no code emits a `test_command`, while step 3 makes conditional creation behavior available. Leaving that wording in place makes the field contract, benchmark design, and backlog status disagree about whether new plans can receive a suite-pass gate. This step publishes the narrow behavior that ships and removes completed work from #234’s active queue without treating the remaining cost question as delivered.

## Input

- **Field contract:** `plan_tool/schema.py:Plan` defines `test_command` as optional, and absence remains a valid `null`/omitted value. This step must not describe a schema-level or universal default.

- **Step 1 outcome:** Step 1 supplies the corrected suite-pass role for `test_command` in `PLAN_FORMAT.md`.

- **Step 3 outcome:** Step 3 supplies the only authorized create-time outcomes: its qualified fixed candidate, a concrete interactive operator command, or omission. Document those observable outcomes without redefining its qualification or placeholder rules.

- **Benchmark contract:** `docs/BENCHMARK_DESIGN.md`’s `### Implementation family — run_step + hidden tests + scope guard` gives the benchmark its own hidden-test command. That command remains an explicit benchmark input rather than a result of normal plan creation.

- **Backlog status surface:** `BACKLOG.md` repeats #234 and `create-default-test-command` in its quality roll-up, queue, authored-plan table, next-pick guidance, execution order, and the `#234` entry. Reconcile every matching status claim, not only the entry body.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — Clarify the difference between the optional field default and conditional create-time emission under `### Defaults` and `### Field semantics`.
  - `docs/BENCHMARK_DESIGN.md` — Update the benchmark note under `### Implementation family — run_step + hidden tests + scope guard` so it describes the shipped creation behavior while preserving the benchmark-owned hidden-test command.
  - `BACKLOG.md` — Record #234’s two delivered levers, retain the cost-bound follow-up, and remove or update stale queue and authored-plan references.

## Implementation

- **Foundational logic:** publish a conditional create-time command without turning it into a universal plan default.

- **Keep the plan-field default distinct:** In `PLAN_FORMAT.md`’s `### Defaults`, retain the fact that an absent `test_command` is optional and reads as `null`. In `### Field semantics`, explain that `plan_tool/create.py:_prepare_create_plan` can populate the field for a newly created plan only through step 3’s authorized outcomes.

- **Describe the automatic path precisely:** State that `uv run pytest tests/ -q -n auto` is written only after the fixed candidate qualifies and its required preflight succeeds. Do not describe every repository as receiving that command.

- **Keep safe omission visible:** State that an unknown unattended creation leaves `test_command` out of frontmatter, while an interactive operator can provide a concrete command for that invocation. Do not call an operator-supplied command a default, and do not imply existing plans are retrofitted.

- **Keep benchmark ownership separate:** Update `docs/BENCHMARK_DESIGN.md` so its hidden-test command remains explicitly supplied for the benchmark’s scratch repository. The benchmark must not rely on or score the normal creation default, and the normal candidate must not replace the hidden-test command.

- **Reconcile #234 as delivered work plus one deferral:** In `BACKLOG.md`’s `#234` entry, record the conditional emission and `PLAN_FORMAT.md` correction as delivered. Preserve only the last-attempt suite-cost bound as deferred work, along with the measurement context needed to evaluate it.

- **Sweep repeated backlog status claims:** Search `BACKLOG.md` for both `#234` and `create-default-test-command`. Update the quality roll-up, working-set queue, authored-plan table, next-pick guidance, and recommended order so none directs a future session to execute work this plan has completed.

- **Keep this documentation-only:** Do not change `plan_tool/create.py`, `plan_tool/runner_detect.py`, `plan_tool/launcher.py`, test behavior, command selection, or retry behavior. Do not widen #234 into a new runner policy while reconciling its remaining cost follow-up.

## Tests

This `non-code` step does not trigger the plan’s test-authoring gate and does not add or modify a test file. Use step 3’s completed coverage in `tests/test_create.py` as the behavior evidence for the published contract.

### Verification (non-code step)

1. `test_create_plan_uses_preflight_qualified_test_command` — Re-run the step 3 case in `tests/test_create.py`; confirm the documented fixed candidate matches the command serialized after successful qualification.

2. `test_create_plan_unknown_test_command_omits_without_prompt_under_yes` — Re-run the step 3 case in `tests/test_create.py`; confirm the documentation preserves safe omission for an unknown unattended invocation.

3. `test_plan_format_distinguishes_optional_field_from_create_emission` — Confirm `PLAN_FORMAT.md` keeps an absent `test_command` optional while describing only conditional creation-time population.

4. `test_benchmark_hidden_command_is_explicit` — Confirm `docs/BENCHMARK_DESIGN.md` states that the benchmark supplies its hidden-test command and does not present it as the normal creation result.

5. `test_backlog_234_records_only_remaining_cost_work` — Search `BACKLOG.md` for `#234` and `create-default-test-command`; confirm delivered work is not listed as ready to execute and the cost bound remains deferred.

6. `test_step_four_changes_only_documentation` — Confirm the implementation diff changes only `PLAN_FORMAT.md`, `docs/BENCHMARK_DESIGN.md`, and `BACKLOG.md`.

## Acceptance criteria

- `PLAN_FORMAT.md` states that `test_command` remains optional when absent and that `create` emits it only through the authorized conditional paths.

- `PLAN_FORMAT.md` names `uv run pytest tests/ -q -n auto` only as the qualified automatic candidate, not as a universal default.

- `docs/BENCHMARK_DESIGN.md` keeps the hidden-test command explicit and separate from normal plan creation.

- `BACKLOG.md` #234 records the conditional emission and documentation correction as delivered, with only the cost-bound follow-up deferred.

- No `BACKLOG.md` queue, authored-plan, next-pick, or execution-order reference directs a future session to execute `create-default-test-command`.

- The related step 3 cases in `tests/test_create.py` pass, and the documentation edit changes no production or test code.

## References

- [PLAN_FORMAT.md](../../../../PLAN_FORMAT.md) — Defines the `test_command` and `enforce_step_tests` contract that this step publishes.

- [docs/BENCHMARK_DESIGN.md](../../../BENCHMARK_DESIGN.md) — Defines the hidden-test benchmark path that must remain separate from normal creation behavior.

- [BACKLOG.md #234](../../../../BACKLOG.md) — Holds the delivered levers and the remaining cost-bound follow-up.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Document only the authorized command sources and safe omission behavior; do not imply guessed commands can reach frontmatter.

- **The plan’s “## Step intent”** — Limit edits to the documents that state no code-emitted default and to #234’s delivery status.

- **The plan’s “## Out of scope”** — Do not expand this documentation pass into runtime, retry, checkpoint, command-selection, existing-plan, CI, or cost-control changes.

## Deferred

- Last-attempt test-command cost bound — Keep this as the sole remaining follow-up in `BACKLOG.md` #234.
