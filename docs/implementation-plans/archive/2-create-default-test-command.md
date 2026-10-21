> **Archived:** this completed plan moved here on 2026-08-20 after all steps reached `done`.

---
title: Create Default Test Command
intent: New plans receive a non-empty `test_command` only when fixed, local markers
  nominate one candidate and its create-time preflight succeeds, or an interactive
  operator supplies a concrete command in that create invocation. This lets the existing
  run gate keep a green step from hiding a red suite without guessing executable commands.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Correct the test-command field contract
  intent: Removes the stale runtime claim that contradicts the existing guidance to
    pair test-authoring enforcement with a suite-pass gate.
  files:
  - PLAN_FORMAT.md
  complexity: low
  change_type: non-code
  detail: docs/implementation-plans/plan-details/create-default-test-command/01-correct-test-command-field-contract.md
  status: done
- id: 2
  title: Qualify the one UV pytest candidate
  intent: Uses fixed local markers to nominate one candidate, then emits it automatically
    only after its exact create-time preflight succeeds; every other repository remains
    unknown.
  creates:
  - plan_tool/runner_detect.py
  - tests/test_runner_detect.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/create-default-test-command/02-qualify-one-uv-pytest-candidate.md
  status: done
- id: 3
  title: Resolve a new plan's test command without guessing
  intent: Writes the preflight-qualified command, otherwise accepts one concrete interactive
    answer for this create invocation or safely omits the field. Its detail defines
    the placeholder-normalization policy.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/create-default-test-command/03-resolve-new-plan-test-command-without.md
  status: done
- id: 4
  title: Publish the new default and reconcile BACKLOG
  intent: Updates only documents that claim there is no code-emitted default, then
    records the two delivered levers and leaves cost bounding deferred.
  files:
  - PLAN_FORMAT.md
  - docs/BENCHMARK_DESIGN.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/create-default-test-command/04-publish-new-default-reconcile-backlog.md
  status: done
---
# Create Default Test Command

## Overview

`create` writes `enforce_step_tests: true` on every new plan but does not write
`test_command`. A step can therefore satisfy the test-authoring gate while the
suite remains red. This plan gives `create` one narrow, deterministic way to
nominate a candidate: a repository with `pytest` and `pytest-xdist` in
`dependency-groups.dev`, `testpaths = ["tests"]` in its pytest configuration,
`uv.lock`, and a root `tests/` directory nominates `uv run pytest tests/ -q -n
auto`. `create` writes that command automatically only after an exact
successful preflight; otherwise the repository remains unknown. An interactive
operator can supply a concrete command for that invocation, while `--yes` and
non-TTY invocations omit the field with one stderr note.

## Problem statement

The `enforce_step_tests` field already says to pair it with `test_command` when
the suite must pass, yet no new plan receives that field. Observed on
2026-08-05: commit `08e672ae` changed tests in four modules while leaving two
assertions red in an untouched module, then advanced as green. A test command
would make the existing post-step gate stop that advancement.

`PLAN_FORMAT.md` also says a 24-minute suite run is impractical, although this
repository's parallel suite measured 46 seconds and its serial suite 184
seconds. The stale claim suppresses the pairing the next paragraph recommends.

## Architecture

**Candidate, then proof.** A new leaf reads only the fixed local conditions
listed in the overview. Together they establish that the explicit `tests/`
argument is the repository's intended pytest suite and nominate `uv run pytest
tests/ -q -n auto`; no other condition combination nominates a command. Before
`create` writes that candidate, it runs the exact command successfully with the
same 600-second deadline and repository context the later `run` gate will use.
A missing condition or a failed/timed-out preflight is unknown, not a default.
The rule does not inspect CI, Makefiles, or README files; it does not score
evidence, scan the repository, or call a model. Adding another ecosystem is
future backlog work with its own rule and tests.

**Resolve unknown input in the current invocation.** If qualification is
unknown, interactive `create` prompts once. Only a concrete operator answer can
become the plan's `test_command`; placeholder input, blank input, and
whitespace-only input omit it. Step 3 detail defines the complete placeholder
normalization policy. Under `--yes` or non-TTY stdin, `create` omits the field
and writes one stderr note while still exiting successfully. The answer is not
checkpointed, resumed, or replayed in a later invocation.

**Keep the observable small.** A newly authored plan has a non-empty
`test_command` only after preflight proves the one fixed candidate or its
current interactive operator supplies a concrete answer. Placeholder input
never becomes an executable command. The existing `run` gate executes that
value. This item does not attribute a test failure to the current step and does
not change gate semantics.

## Steps

The machine-readable step list lives in the frontmatter `steps:` block.

## In scope

- One strict marker rule, including the configured `tests/` suite condition,
  and successful exact preflight for the documented UV/pytest-xdist candidate.
- `create` frontmatter assembly and its immediate interactive/unattended choice.
- The stale field description, its direct benchmark claim, and BACKLOG #234.

## Out of scope

- Changes to `run`, including test-failure attribution or retry behavior.
- A retained prompt answer, resume behavior, or a new checkpoint format.
- Heuristic or model-selected commands, broader repository inspection, and a
  second test ecosystem.
- A plan-level enumeration of placeholder spellings; step 3 detail owns that
  normalization policy.
- Retrofitting existing plans, CI adoption, and #234's last-attempt cost bound.

## Risks

- A pre-existing red suite will now block the first step of a plan with a
  configured command. That is the expected gate behavior; this item does not
  try to determine whether the failure predates the step.
- A matching repository spends about 46 seconds on its create-time preflight,
  in addition to the existing per-step gate cost. A failing preflight takes the
  safe unknown path rather than attaching a command that will block later work.
- A wrong default is worse than no default, so automatic qualification must
  fail closed.

## Testing

Prove the marker rule nominates the exact command only with all fixed
conditions, including `testpaths = ["tests"]`. Prove `create` serializes it
only after that exact preflight succeeds within 600 seconds and omits it when a
condition is absent or the preflight fails or times out. Prove an unknown
repository accepts a concrete interactive answer only for that invocation and
omits blank, whitespace-only, or placeholder input according to step 3 detail;
also prove the `--yes` and non-TTY paths. Verify the two direct documents no
longer claim there is no code-emitted default and keep the field-pairing advice.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verify the field contract directly.
- step 2 (feature) — unit-test marker nomination and successful/failed
  preflight qualification.
- step 3 (feature) — test plan frontmatter and interactive/unattended outcomes.
- step 4 (non-code) — verify direct documentation claims and backlog status.

## Acceptance criteria

- A matching repository's newly created plan declares
  `test_command: uv run pytest tests/ -q -n auto` only after the exact
  preflight succeeds within 600 seconds.
- Any missing required condition, failed preflight, or timed-out preflight
  produces no automatic command.
- An unknown interactive repository accepts a concrete answer only for that
  create invocation; blank, whitespace-only, and placeholder input omit it.
- An unknown `--yes` or non-TTY invocation exits successfully, omits the field,
  and emits one stderr note.
- `PLAN_FORMAT.md` and `docs/BENCHMARK_DESIGN.md` describe the code-emitted
  default accurately, and BACKLOG #234 retains only the deferred cost bound.

## Deferred

Running the suite only on a step's last attempt; any additional ecosystem;
CI adoption.

## References

- `PLAN_FORMAT.md` — Defines the `enforce_step_tests` and `test_command` field contract.
- `docs/BENCHMARK_DESIGN.md` — Records the suite-duration evidence that bounds the default.
- `BACKLOG.md` #234 — Tracks the remaining deferred cost-bound work.
