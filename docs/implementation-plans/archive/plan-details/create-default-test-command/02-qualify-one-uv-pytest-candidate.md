# Step 2 — Qualify the one UV pytest candidate

## Summary

Add `plan_tool/runner_detect.py` as a small, deterministic qualifier for the one supported UV/pytest command, with unit coverage in `tests/test_runner_detect.py`. It reads only fixed repository markers, then runs the exact candidate in the repository root before returning it. The key decision is fail-closed behavior: a missing marker or any preflight failure returns unknown rather than a guessed executable command. On green, the module returns `uv run pytest tests/ -q -n auto` only for a repository that proves it can run that command.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new qualification seam.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing proof before automatic command selection.
- [Input](#input) — Repository markers and runtime context the qualifier reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files this step creates.
- [Implementation](#implementation) — Qualification rule, preflight behavior, and module boundary.
- [Tests](#tests) — Unit coverage for marker matching and failure handling.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Contract and evidence sources.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this step.
- [Deferred](#deferred) — Work owned by later steps or backlog items.

## Why

`plan_tool/create.py:create_plan` currently enables test-authoring enforcement without proving a suite command exists, so a new plan can lack the gate that catches an unrelated red test. A fixed command is safe to attach only when local evidence nominates it and an immediate run proves it works in the same repository context the later gate will use. This step creates that proof boundary without treating a repository that merely resembles this one as supported.

## Input

- **Marker contract:** Read only root `pyproject.toml`, `uv.lock`, and `tests/`. `pyproject.toml` must have a `[dependency-groups]` `dev` group that declares both `pytest` and `pytest-xdist`, and `[tool.pytest.ini_options]` must set `testpaths = ["tests"]`; version constraints do not change the required package names. The exact one-element `testpaths` value establishes that the explicit command argument covers this repository's intended pytest suite.

- **Candidate command:** The sole automatic result is `uv run pytest tests/ -q -n auto`. The required pytest `testpaths`, `uv.lock`, and root `tests/` show the matching local shape in this repository.

- **Runtime context:** `plan_tool/launcher.py:_run_test_gate` executes a configured `test_command` through the shell in the repository root with a 600-second timeout. The preflight must prove the same command can run under that deadline in that directory before a later step writes it into a plan.

- **Ownership split:** Step 3 integrates the qualified optional result into `plan_tool/create.py:create_plan` and `plan_tool/create.py:write_new_plan`; this step only provides the deterministic qualification seam.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/runner_detect.py` — Define the fixed marker rule and exact-command preflight.
  - `tests/test_runner_detect.py` — Cover qualification outcomes without running a real suite.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** fixed-marker nomination plus exact-command preflight.

- **Keep the candidate table closed:** `plan_tool/runner_detect.py` recognizes exactly one combination: a usable `pyproject.toml` whose development dependency group names both required packages and whose pytest configuration has exactly `testpaths = ["tests"]`, plus `uv.lock` and a root `tests/` directory. Do not inspect CI configuration, Makefiles, README files, or other test ecosystems.

- **Match package names, not substrings:** Treat `pytest` and `pytest-xdist` as distinct dependency requirements. Related entries such as `pytest-cov` must not satisfy the `pytest` marker, and a missing, malformed, or differently shaped dependency group must produce unknown.

- **Return only a qualified command:** Expose a small API that returns the exact candidate string on success and `None` for every unknown outcome. Keep raw marker evidence, scores, alternates, and partially matched candidates out of the result surface so Step 3 has no value it could accidentally serialize as a command.

- **Preflight the exact later command:** Run `uv run pytest tests/ -q -n auto` unchanged, from the supplied repository root, using the same shell-based command form and 600-second deadline the runtime gate uses. A zero exit status before that deadline is the only successful qualification result. Define the deadline locally in this leaf rather than importing the launcher, and keep its numeric value visibly coupled to the documented runtime contract.

- **Fail closed on execution problems:** A non-zero exit status, timeout, missing executable, or other process error means unknown and must not escape as a create-time failure. Capture enough process behavior to make the result testable, but do not add failure attribution or retry policy.

- **Keep a leaf boundary:** Make `plan_tool/runner_detect.py` stdlib-only and independent of `plan_tool/create.py` and `plan_tool/launcher.py`. Do not reuse `plan_tool/launcher.py:_run_test_gate`: its failure-tail interface serves post-step advancement, while this module needs a simple create-time qualified-or-unknown result.

## Tests

### Tests for this step

Every case below must be green before this feature step is finished.

- `test_uv_pytest_candidate_requires_every_fixed_marker` — Returns no candidate unless the required dependency declarations, exact pytest `testpaths`, `uv.lock`, and root `tests/` all exist.
- `test_pytest_dependency_marker_requires_exact_package_names` — Does not treat related package names such as `pytest-cov` as proof that `pytest` is installed.
- `test_unreadable_or_malformed_pyproject_is_unknown` — Treats an unreadable or invalid project file as unknown without raising.
- `test_qualified_uv_pytest_candidate_is_the_exact_command` — Returns only `uv run pytest tests/ -q -n auto` when markers and preflight both succeed.
- `test_preflight_runs_the_exact_command_from_repo_root` — Captures the process request and proves the unchanged command, supplied repository root, and 600-second deadline are used.
- `test_failed_timeout_or_spawn_error_preflight_is_unknown` — Returns no command for a non-zero result, timeout at the 600-second deadline, or process-launch failure.
- `test_runner_detect_is_stdlib_only_leaf` — Proves importing `plan_tool/runner_detect.py` does not load first-party `plan_tool` dependencies.

## Acceptance criteria

- A repository with all fixed markers, including exact `testpaths = ["tests"]`, and a successful preflight produces exactly `uv run pytest tests/ -q -n auto`.
- Any missing, invalid, or incomplete marker set produces `None`.
- A failed, timed-out at 600 seconds, or unlaunchable preflight produces `None` without raising a create-time error.
- The preflight runs the exact candidate through the shell with the supplied repository root as its working directory.
- `plan_tool/runner_detect.py` has no first-party runtime imports.
- `tests/test_runner_detect.py` passes with all qualification cases green.

## References

- [PLAN_FORMAT.md](../../../../PLAN_FORMAT.md) — Read the `test_command` contract and its runtime execution context.
- [docs/BENCHMARK_DESIGN.md](../../../BENCHMARK_DESIGN.md) — Use the suite-run evidence that supports the fixed candidate.
- [BACKLOG.md #234](../../../../BACKLOG.md) — Read the settled command-selection decision and remaining cost-bound follow-up.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Return an automatic command only after fixed local evidence and a successful preflight; leave all other command selection to the plan’s later path.

- **The plan’s “## Step intent”** — Limit this module to the one supported candidate and make every other repository unknown.

- **The plan’s “## Out of scope”** — Do not change `run`, add an interactive surface, retain input, widen repository inspection, or introduce another test ecosystem.

## Deferred

- Integration with `plan_tool/create.py:create_plan` and `plan_tool/create.py:write_new_plan` — Step 3 owns plan-frontmatter emission and the interactive fallback.
- Placeholder normalization and unattended operator messaging — Step 3 owns that input policy.
- Test-command cost bounding — Remains tracked by `BACKLOG.md` #234.
- Additional runner ecosystems and broader repository detection — Require a separate fixed rule and test set.
