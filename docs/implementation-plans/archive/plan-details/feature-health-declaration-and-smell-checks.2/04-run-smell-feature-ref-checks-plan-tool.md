> **Auto-archived**: this plan was swept on 2026-06-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Run the advisory smell/feature-ref checks from `plan-tool validate` (after the `OK:` print, before any Claude spend)

## Summary

Wires step 2's `collect_smell_findings` into `plan_tool/cli/inspect.py:cmd_validate` so a structurally-valid plan also gets the no-Claude advisory smell/feature-ref pass. The single behavior change: capture the parsed plan on the valid path (`plan = parse_plan(path)` instead of discarding the result), then call `collect_smell_findings(plan, ctx.repo_root, plan_name=args.name)` **after** `print(f"OK: {path}")` and render any findings as a dismissible advisory block, ending with the existing `return 0`. The `except (ParseError, ValidationError)` arm — the sole reader of `--fail-on-findings` — stays unchanged, which structurally guarantees a smell can never flip the exit code and never runs against a schema-invalid plan. On green, validating a plan that trips a suppression-shape / self-referential / feature-ref smell prints `OK:` plus an advisory smell section and still exits 0; `--fail-on-findings` continues to flip rc only on an `INVALID:` verdict. The collector import is body-local so the split-proof cli tests can patch `plan_tool.review.collect_smell_findings`.

## Table of Contents

- [Why](#why) — what `validate` is missing and why smells belong on its valid path.
- [Files (creates vs edits)](#files-creates-vs-edits) — the one source file and its test file.
- [Implementation](#implementation) — the valid-path capture, the body-local collector call, the advisory render, and the untouched `INVALID:` arm.
- [Tests](#tests) — the `TestCmdValidate` cases to add and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — pydantic docs relevant to the advisory-not-parse-fatal posture this step preserves.
- [Deferred](#deferred) — surfaces and checks left to other steps.

## Why

`plan-tool validate` is the cheapest plan-health verb — schema-only, no Claude — and is the natural place to surface the step 2 smell/feature-ref findings **before** any operator pays for a `completeness-audit` Claude pass (step 3's surface). Today `cmd_validate` parses the plan only to learn whether parsing raised, then discards the `Plan`; nothing reads the new `features` registry or the brittle-shape heuristics. This step gives the advisory layer a second, cheaper home: the valid path now keeps the parsed `Plan` and runs the no-Claude collector, printing dismissible findings. Keeping all of this on the valid path (after the `OK:` print) is the whole point — the `INVALID:` arm and its `--fail-on-findings` rc expression stay untouched, so a smell is reported but can never gate CI and can never run against a plan that failed schema validation.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/inspect.py` — in `cmd_validate`: change `parse_plan(path)` to `plan = parse_plan(path)`; after `print(f"OK: {path}")` add a body-local `from plan_tool.review import collect_smell_findings`, call it with `(plan, ctx.repo_root, plan_name=args.name)`, render any findings as an advisory block, then keep the existing `return 0`. Leave the `except (ParseError, ValidationError)` arm unchanged.
  - `tests/cli/test_inspect_cmds.py` — add cases under the existing `TestCmdValidate` class for: a smell-tripping plan still exits 0 and prints the advisory block, a clean plan prints `OK:` with no advisory block, and `--fail-on-findings` does not flip rc on a smell-only (otherwise-valid) plan. Patch `plan_tool.review.collect_smell_findings`, never a `plan_tool.cli.inspect` global.

## Implementation

### `plan_tool/cli/inspect.py` — `cmd_validate`

- **Capture the parse result on the valid path.** Change the single statement `parse_plan(path)` (inside the `try`) to `plan = parse_plan(path)`. The `except` arm never references `plan`, so it stays unchanged; only the fall-through valid path gains a `Plan` to hand the collector. This mirrors the prior-art note: validate parsed-and-discarded; now it parses-and-keeps on success only.

- **Call the collector after the `OK:` print, before `return 0`.** Insert between `print(f"OK: {path}")` and `return 0`:
  - `from plan_tool.review import collect_smell_findings` — **body-local**, placed inside `cmd_validate` at the call site, not module-top.
  - `smells = collect_smell_findings(plan, ctx.repo_root, plan_name=args.name)` — `ctx` is already in scope from `ctx = _load_context(args)` at the top of `cmd_validate`; `ctx.repo_root` is the resolved repo root (same field `cmd_list` reads). `args.name` is the plan slug the operator passed.
  - **Confirm `collect_smell_findings`'s arity / keyword-only `plan_name` at HEAD** once step 2 lands before wiring this call — the body states the call form (`plan_name` passed by keyword) but the exported signature is a cross-step contract, so verify the landed signature matches.

- **Why the import is body-local — state the real reason and deny the false one:**
  - **Primary: test-monkeypatch reach.** The `tests/cli/` split-proof convention (see `tests/cli/test_inspect_cmds.py` header and `tests/cli/test_package_surface.py`) forbids `monkeypatch.setattr` on any `plan_tool.cli` module global. A module-top `from plan_tool.review import collect_smell_findings` would bind the name into the `plan_tool.cli.inspect` namespace, leaving only the cli global patchable — which the convention bans. Importing in-body keeps the lookup pointed at `plan_tool.review.collect_smell_findings`, the attribute the tests patch.
  - **Secondary: cost fence.** `validate`'s headline contract is "no Claude, cheap." Keeping the import (and thus the `review` module's heavier transitive surface) off the module-top path keeps the read-only inspection module's import graph light.
  - **Explicit non-reason — no cycle.** `plan_tool/review.py` imports nothing from `plan_tool.cli.*`, so there is **no import cycle** here. Do **not** cite cycle-breaking as the justification — a later refactor that "preserves a cycle break" would be correcting a problem that never existed.

- **Render findings as an advisory block, then `return 0` unchanged.** When `smells` is empty, print nothing extra (the `OK:` line stands alone — keep the clean-plan output unchanged). When non-empty:
  - Print a short header (e.g. `  smells (advisory):`) once, then one line per `Recommendation` carrying its `title` and `source` (and `body` if you keep it terse), reading the `plan_tool/review.py:Recommendation` fields `title` / `body` / `source` / `severity`. The findings are `severity="info"` and dismissible — the wording must read as advisory, not as a gate.
  - Keep the final statement `return 0` exactly as today. Do **not** route `smells` into any rc expression; the only rc flip in this function lives in the `except` arm.

- **Leave the `except (ParseError, ValidationError)` arm unchanged.** It still prints `INVALID:`, the `format_validation_errors` lines (or the raw `exc`), and returns `1 if getattr(args, "fail_on_findings", False) else 0`. This arm is the only `--fail-on-findings` reader, so the advisory smells on the valid path are structurally outside the rc-flipping path.

- **Foundational logic / shared call sites.** The core behavior this step adds is "surface `collect_smell_findings` on an author-time, no-Claude surface." The same collector is wired into the post-loop completeness battery by step 3 (`plan_tool/cli/completeness_phases.py:_run_deterministic_checks`). These are the **two intended consumers** of the collector (the plan's Part B: "the deterministic layer of `completeness-audit` … and `plan-tool validate`"). Do **not** add `collect_smell_findings` to `plan_tool/review.py:collect_deterministic_findings` — that is the broadcast fan-out feeding the `--iterate` apply loop, and routing smells there would dispatch them to `apply_finding` (a prose editor that cannot fix a structural shape). This step touches only the `validate` surface; step 3 owns the completeness surface.

## Tests

All new cases go in `tests/cli/test_inspect_cmds.py` under the existing `class TestCmdValidate`, driven through `main(argv)` against the `tmp_repo` / `registered_plan` conftest fixtures. Stub the collector by patching `plan_tool.review.collect_smell_findings` (the body-local import resolves to that attribute) — never a `plan_tool.cli.inspect` global. Construct a stub `Recommendation` (import from `plan_tool.review` / `plan_tool.schema` as the sibling tests do) with `severity="info"` and `source` one of `feature-ref` / `suppression-shape` / `self-referential`.

### Test-creation order (feature step)

This is a **feature** step. Add these unit tests **with** the implementation; every one must be green before the step is considered finished.

- `test_valid_plan_with_smells_prints_advisory_block_and_exits_0` — patch `collect_smell_findings` to return one info `Recommendation`; assert rc 0, output starts with `OK:`, and the advisory smell line (title + `smells (advisory)` header) appears.
- `test_valid_plan_without_smells_prints_only_ok` — patch `collect_smell_findings` to return `[]`; assert rc 0, output starts with `OK:`, and no advisory header is printed (clean-plan output unchanged).
- `test_smell_only_plan_with_fail_on_findings_still_exits_0` — otherwise-valid plan, `collect_smell_findings` returns a finding, run `validate <name> --fail-on-findings`; assert rc 0 (a smell on the valid path never flips rc — only an `INVALID:` verdict does).
- `test_invalid_plan_does_not_call_smell_collector` — schema-invalid plan with a `collect_smell_findings` stub rigged to raise (or a spy asserting zero calls); assert rc 0, output starts with `INVALID:`, and the collector was never invoked (the `except` arm never reaches the valid-path call).

Existing `TestCmdValidate` cases (`test_valid_plan_prints_ok_and_exits_0`, `test_invalid_plan_prints_invalid_but_exits_0_by_default`, `test_invalid_plan_with_fail_on_findings_exits_1`, `test_unparseable_plan_validate_prints_invalid`, `test_unparseable_plan_fail_on_findings_exits_1`) must stay green unchanged — the `registered_plan` fixture's single step ("Only step", no detail body) doesn't trip the suppression-shape proximity predicate (which step 2's `detect_suppression_shape` runs on a bare step even with no `features:` block), so `collect_smell_findings` returns `[]` and `test_valid_plan_prints_ok_and_exits_0` still sees `OK:`-only output. The green gate rests on the fixture step's title/body, not on the absence of a `features` registry.

## Acceptance criteria

- `cmd_validate` assigns `plan = parse_plan(path)` on the valid path and passes that `plan` to `collect_smell_findings(plan, ctx.repo_root, plan_name=args.name)` after `print(f"OK: {path}")` and before `return 0`.
- The `collect_smell_findings` import in `cmd_validate` is body-local (inside the function), not at module top.
- A valid plan tripping a smell prints `OK:` plus an advisory smell block and exits 0; the same plan with `--fail-on-findings` still exits 0.
- A valid plan with no smells prints only the `OK:` line (no advisory block) and exits 0.
- The `except (ParseError, ValidationError)` arm is unchanged: it prints `INVALID:` and returns `1 if fail_on_findings else 0`; the collector is never called on a schema-invalid plan.
- `collect_smell_findings` is **not** added to `plan_tool/review.py:collect_deterministic_findings` (smells never enter the `--iterate` apply loop from this step).
- New `TestCmdValidate` cases pass, and the existing `TestCmdValidate` / `TestCmdList` / `TestCmdStatus` / `TestCmdRoot` suites stay green.

## References

- [Validators (model_validator / field_validator) — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — confirms why the feature-ref/smell checks stay advisory functions called here rather than parse-time validators, so `validate` (and `run`/`jira`/`detail`) never raise on a drifted feature block.
- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — reference for the `Plan` object `cmd_validate` now captures and hands to the collector.

## Deferred

- **Completeness-audit surfacing** — the second consumer of `collect_smell_findings` (the post-loop deterministic battery + the three render surfaces) is step 3's, not this step's; this step only wires `validate`.
- **Apply-loop routing** — smells stay out of `collect_deterministic_findings` and `apply_finding` by design (step 2 / step 3 guarantee); not revisited here.
- **Unfalsifiable-feature check** — deferred plan-wide (plan Part B) pending a `[feature-id]` acceptance-criteria tagging convention; not surfaced by `validate`.
- **`--json` / machine-readable smell output for `validate`** — `validate` emits human-readable `OK:`/`INVALID:` lines only; a structured payload for smells lives on the completeness `--json` surface, not here.
