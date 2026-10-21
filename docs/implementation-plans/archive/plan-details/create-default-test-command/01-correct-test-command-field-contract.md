# Step 1 — Correct the test-command field contract

## Summary

Correct `PLAN_FORMAT.md` so its `test_command` guidance describes the field as the plan-wide suite-pass gate. Keep the documented runtime behavior aligned with `plan_tool/schema.py:Plan` and `plan_tool/launcher.py:run_step`. The key decision is to remove advice that steers authors toward a narrow test filter when that cannot prove the suite remains green. On green, the adjacent `test_command` and `enforce_step_tests` entries describe complementary checks without changing production behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation correction.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The contradiction this edit removes.
- [Input](#input) — Existing runtime contract the documentation must reflect.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single documentation file this step changes.
- [Implementation](#implementation) — Required field-contract wording and boundaries.
- [Tests](#tests) — Non-code verification for the documentation change.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Contract and evidence sources.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Work owned by later steps or backlog items.

## Why

`PLAN_FORMAT.md` currently discourages a suite-wide `test_command` while its adjacent `enforce_step_tests` contract says that test-file detection does not prove tests pass and must be paired with `test_command`. That contradiction leaves authors with a gate that can accept a changed test file while an unrelated regression remains red. This step makes the reference contract tell one consistent story before later steps add a narrowly qualified default.

## Input

- **Plan field shape:** `plan_tool/schema.py:Plan` keeps `test_command` optional and `enforce_step_tests` optional; this documentation edit must not imply a new parser rule or a universal default.
- **Run ordering:** `plan_tool/launcher.py:run_step` performs the test-authoring check before the plan-level test command, and runs per-step `gate` commands only after the plan-level command passes.
- **Test-command behavior:** `plan_tool/launcher.py:_run_test_gate` runs the configured shell command in the repository root with its existing timeout and returns a failure that prevents step advancement. The documentation must continue to describe that behavior accurately.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — Revise the `test_command` entry under `### Field semantics` so it states the field’s suite-pass role, then confirm the adjacent `enforce_step_tests` entry continues to state the complementary test-authoring role.

## Implementation

- **Foundational logic:** `test_command` is the post-step suite-pass gate that complements the test-authoring check.

- **Correct the `test_command` guidance:** Update `PLAN_FORMAT.md`’s `test_command` entry under `### Field semantics` to remove the claim that a full-suite run is impractical and the advice to use a single-test or `-k` command as the default gate shape. Describe the command as the plan-level check that should establish the intended suite still passes.

- **Keep the execution contract unchanged:** Preserve the documented facts that `plan_tool/launcher.py:_run_test_gate` executes the command after a successful Claude call, before advancement, in the repository root, and that a non-zero result leaves the step unadvanced with a failure note. Keep the shell-command security warning because this field remains executable input.

- **Make the field pair explicit:** Keep `PLAN_FORMAT.md`’s `enforce_step_tests` entry clear that it proves only a test file changed. Its pairing with `test_command` must state that the latter supplies the pass/fail suite check; neither entry should suggest that test-file detection alone proves meaningful or passing tests.

- **Do not describe future authoring behavior yet:** Keep `test_command` optional in this step’s documentation. Steps 2 and 3 own qualification and emission, while step 4 owns documentation of the resulting create-time default.

- **Leave adjacent contracts alone:** Do not change the frontmatter schema, `steps[].gate` contract, parser defaults, launcher behavior, or examples unrelated to the stale recommendation.

## Tests

This is a documentation-only step; do not add or modify automated test files.

### Verification (non-code step)

1. `test_test_command_contract_matches_run_step` — Compare `PLAN_FORMAT.md` with `plan_tool/launcher.py:_run_test_gate` and `plan_tool/launcher.py:run_step`; confirm optional execution, ordering, failure blocking, repository-root execution, timeout, and security warnings remain accurate.
2. `test_enforce_step_tests_pairing_is_explicit` — Confirm `PLAN_FORMAT.md` says `enforce_step_tests` checks that a test file changed, while `test_command` supplies the suite-pass check.
3. `test_stale_full_suite_discouragement_is_absent` — Confirm `PLAN_FORMAT.md` no longer calls a full-suite run impractical or directs authors to narrow the plan-level gate to a single test or `-k` filter.
4. `test_step_one_changes_only_plan_format` — Confirm the diff changes only `PLAN_FORMAT.md` and does not alter `plan_tool/launcher.py`, `plan_tool/schema.py`, or `tests/test_launcher.py`.

## Acceptance criteria

- `PLAN_FORMAT.md`’s `test_command` entry no longer contains the stale full-suite duration claim or guidance that conflicts with a suite-pass gate.
- `PLAN_FORMAT.md` states that `test_command` is the plan-level command used to check the intended suite passes before advancement.
- `PLAN_FORMAT.md` keeps `test_command` optional and accurately preserves its existing runtime and security behavior.
- `PLAN_FORMAT.md` explicitly preserves the complementary roles of `enforce_step_tests` and `test_command`.
- The step’s diff modifies only `PLAN_FORMAT.md`.

## References

- [PLAN_FORMAT.md](../../../../PLAN_FORMAT.md) — Read the `test_command` and `enforce_step_tests` entries together when revising the contract.
- [docs/BENCHMARK_DESIGN.md](../../../BENCHMARK_DESIGN.md) — Use the benchmark’s test-command context without changing this step’s documentation scope.
- [BACKLOG.md #234](../../../../BACKLOG.md) — Use the recorded stale-claim evidence and deferred cost-bound work as scope context.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Make the field contract support a reliable suite-pass gate without inventing a broader command-selection policy.
- **The plan’s “## Step intent”** — Limit this step to removing the stale documentation claim and reconciling the adjacent field guidance.
- **The plan’s “## Out of scope”** — Do not alter run behavior, create-time behavior, checkpoint handling, command-selection rules, placeholder handling, or cost controls.

## Deferred

- Code-emitted `test_command` documentation — Step 4 owns the reference updates that follow the implementation in steps 2 and 3.
- Runtime and test changes in `plan_tool/launcher.py` and `tests/test_launcher.py` — This step only documents their existing contract.
- Test-command cost bounding — Remains tracked by `BACKLOG.md` #234.
