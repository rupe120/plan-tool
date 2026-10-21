# Step 3 — Parse the plan once in cmd_convergence instead of inside _current_audit_stage

## Summary

This step hoists the `parse_plan(path)` call that today lives inside `_current_audit_stage` up into its only caller, `cmd_convergence`, in `plan_tool/cli/convergence_cmd.py`. `_current_audit_stage` stops parsing the plan itself and instead takes the already-parsed `Plan` (or `None`, when parsing failed) as a new parameter, and its bare/detail/jira-grade stage logic stays exactly as it is today. The only files touched are `plan_tool/cli/convergence_cmd.py` and its test module, `tests/cli/test_convergence_cmd.py`. The key design decision is where the parse-failure fallback lives: the broad `except Exception` that swallows a bad parse inside `_current_audit_stage` today moves to `cmd_convergence`, producing a local `plan = None` on any failure, so `_current_audit_stage`'s own fallback shrinks to a one-line `if plan is None: return None` and the command's documented always-exits-0 contract holds unchanged. On green, `cmd_convergence` parses the plan exactly once per invocation and holds the parsed `Plan` in a local variable, ready for a later step to read without a second parse.

## Table of Contents

- [Why](#why) — the gap this step closes
- [Input](#input) — the existing parse/classify contracts this step must preserve
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the hoist, the new signature, and what must not change
- [Tests](#tests) — test roster
- [Acceptance criteria](#acceptance-criteria)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

`_current_audit_stage` calls `parse_plan(path)` (`plan_tool/parser.py`) on every `cmd_convergence` invocation, entirely inside its own body — the parsed `Plan` never reaches its caller. The plan's Step intent for this step is to make that parsed `Plan` reachable from `cmd_convergence` itself: step 4 needs the plan's committed step ids and statuses, read off that same `Plan`, to build the `declared_step_ids` / `step_statuses` arguments that `classify_arm_clustering_consensus` (step 1, `plan_tool/convergence_diagnosis.py`) and `evaluate_arm_clustering` (`plan_tool/audit_shapes.py`) need. Without this hoist, step 4 would have to either add a second `parse_plan(path)` call inside `cmd_convergence` — a redundant parse plus a second copy of the same best-effort try/except — or reach past `_current_audit_stage`'s return value for something it was never built to expose. Doing the hoist as its own step keeps it a small, low-risk mechanical move: no new behavior, no new caller, nothing for step 4 to get wrong about the fallback semantics.

## Input

- **`parse_plan(path) -> Plan`** (`plan_tool/parser.py`) — the parse entry point this step relocates. It raises `ParseError` (invalid YAML, non-mapping frontmatter, a malformed `---` fence) or `ValidationError` (a schema violation caught from Pydantic) — both plain `Exception` subclasses with no shared base beyond `Exception` itself — plus ordinary stdlib exceptions such as `FileNotFoundError` when the file can't be read. `_current_audit_stage` today catches all of these with one blanket `except Exception`; this step must preserve that same breadth at the new call site rather than narrowing it to specific types.
- **`audit_detail_bundle_status(plan, plan_path, repo_root, *, detail_grade=...)`** (`plan_tool/review.py`) — already takes a parsed `Plan` as its first positional argument, not a path. `_current_audit_stage` already builds and passes this call; nothing about the call itself changes, only where the `Plan` it's handed comes from.
- **`_current_audit_stage`'s existing fallback contract** — documented in its own docstring and pinned today by `tests/cli/test_convergence_cmd.py::test_current_audit_stage_falls_back_to_none_on_unparseable_plan`: any failure anywhere in the parse-and-classify path returns `None`, and `cmd_convergence` reads `audit_stage is None` as the signal to call `diagnose_convergence(history)` with none of the stage-aware keyword arguments. This step must reproduce that exact `None`-on-failure outcome from the new call site, just triggered from a different function.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/convergence_cmd.py`:
    - In `cmd_convergence`, add a `parse_plan(path)` call (imported locally inside the function) wrapped in `try/except Exception`, producing a local `plan: Plan | None`.
    - Change `_current_audit_stage`'s signature to take that parsed `plan` as a parameter instead of importing and calling `parse_plan` itself; drop the now-unused `from plan_tool.parser import parse_plan` import from inside `_current_audit_stage`.
    - Update the call site inside `cmd_convergence` to pass `plan` through to `_current_audit_stage`.
    - Adjust both functions' docstrings to describe the new split — who parses, who classifies.
    - Fix the inline comment directly above the `record_convergence(` call ("No parsed Plan here, so no map") — this step's hoist puts a parsed `Plan` (or `None`) in scope at exactly that point, making the comment's premise false the moment this step lands. Reword it to say a parsed `Plan` is now available in this function but is deliberately not used to build a `code_fingerprint` map here (this step does not change what `record_convergence` telemeters — see "What must not change"), rather than leaving a now-false claim in place.
  - `tests/cli/test_convergence_cmd.py`:
    - Update the four tests that call `_current_audit_stage` directly (`test_current_audit_stage_bare_with_no_detail_files`, `test_current_audit_stage_detail_when_step_has_detail_file`, `test_current_audit_stage_detail_at_jira_grade_when_run_grade_is_bare`, `test_current_audit_stage_falls_back_to_none_on_unparseable_plan`) to parse the plan themselves and pass the result into the new signature.
    - Add one end-to-end case driving a genuinely broken plan file through `main(...)` to pin `cmd_convergence`'s own new fallback — the guarantee the old unit test covered indirectly before the hoist.

## Implementation

**What moves, and where it lands:**

- `cmd_convergence` becomes the single place that calls `parse_plan(path)`. Call it right after `path = resolve_plan_for_context(ctx, args.name)` and before computing `audit_stage`, inside `try: plan = parse_plan(path) / except Exception: plan = None` — the same breadth `_current_audit_stage` uses today. Don't narrow the catch to `ParseError`/`ValidationError`; today's code doesn't discriminate between them (see Input — they share no common base besides `Exception`), and narrowing it is a separate, out-of-scope behavior decision.
- `_current_audit_stage` gains a parameter carrying that result. One reasonable order, keeping the smallest diff: `_current_audit_stage(ctx, path, plan, *, detail_grade: str)`. Its first line becomes `if plan is None: return None`, replacing today's `parse_plan(path)` call and its import. The rest of the function is unchanged: it still builds `audit_detail_bundle_status(plan, path, ctx.repo_root, detail_grade=detail_grade)` and returns `derive_audit_stage(bundle_status)`, and it still wraps that pair of calls in its own `try/except Exception: return None` — they can fail for reasons unrelated to parsing (for example `audit_detail_bundle_status` walking a bad detail path), and today's code treats that failure identically to a parse failure. Keep it that way.
- Keep the `parse_plan` import local to `cmd_convergence` (a lazy `from plan_tool.parser import parse_plan` inside the function body), matching this file's existing style — `cmd_convergence` already does two more local imports (`slug_from_filename`, `record_convergence`) instead of adding to the module's top-level import block. `derive_audit_stage` and `audit_detail_bundle_status` stay as local imports inside `_current_audit_stage`, unchanged.
- Store the parsed `plan` as an ordinary local variable in `cmd_convergence`. This step does not read `plan.steps`, does not add a keyword argument to `diagnose_convergence`, and does not change what gets printed or what `record_convergence` telemeters. Its only consumer inside this step is the `_current_audit_stage` call — the plan's Step intent ("so the next step can read its committed steps") is satisfied by the variable existing and being in scope, not by this step reading it further.

**Rejected alternative:** passing `path` alone into `_current_audit_stage` and having it accept a caught exception object, or a sentinel string, instead of `plan: Plan | None`. Rejected because `None` is already the value `_current_audit_stage` treats as "stage unknown" today (its existing early-return path), so reusing it needs no new vocabulary — and it is the type step 4 will want in `cmd_convergence` anyway (`plan.steps` when `plan` is not `None`).

**What must not change:**

- `cmd_convergence`'s documented contract — "Always returns 0 ... An unresolvable name still surfaces a non-zero error from name resolution upstream" — holds unchanged after the move. `resolve_plan_for_context` (called before the new `parse_plan`) is what can still raise and produce the non-zero rc; a bad plan body must never propagate past the new `try/except`.
- `compute_plan_fingerprint(path)`, called later in `cmd_convergence`, is unrelated — it hashes file bytes, not the parsed model, and already has its own independent `try/except`. Don't fold it into the new `plan = ...` handling or share one `except` block between them; they guard different failures for different reasons (telemetry safety vs. stage lookup).
- `audit_detail_bundle_status`'s and `derive_audit_stage`'s own signatures are untouched — only what supplies their first argument moves.
- `_current_audit_stage`'s return type (`str | None`) and its two returned stage values (`STAGE_BARE`, `STAGE_DETAIL` from `plan_tool/convergence.py`) stay exactly as today.

## Tests

### Tests for this step

- `test_current_audit_stage_bare_with_no_detail_files` — updated to parse the fixture plan itself and pass the resulting `Plan` as `_current_audit_stage`'s new parameter; still asserts `STAGE_BARE`.
- `test_current_audit_stage_detail_when_step_has_detail_file` — same update; still asserts `STAGE_DETAIL` once a detail file exists.
- `test_current_audit_stage_detail_at_jira_grade_when_run_grade_is_bare` — same update; this test already calls `parse_plan` to build the jira detail path via `derive_jira_detail_path`, so the change reuses that existing call instead of adding a second one. Still asserts the run-grade/jira-grade disagreement (`STAGE_BARE` at run grade, `STAGE_DETAIL` at jira grade).
- `test_current_audit_stage_falls_back_to_none_on_unparseable_plan` — rewritten to assert the short-circuit directly: call `_current_audit_stage(ctx, path, None, detail_grade=GRADE_RUN)` and assert `None`. A genuinely unparseable file no longer reaches this function's own parsing, because it no longer parses.
- `test_convergence_exits_zero_with_unparseable_plan_file` (new, alongside the other `main(...)`-driven cases near the top of the file) — writes an invalid plan body to the fixture's plan file, drives `convergence` through `main(...)`, and asserts `rc == 0`. This pins the behavior the old unit test covered indirectly before the hoist: `cmd_convergence`'s own new `try/except` around `parse_plan` is what now carries that guarantee end to end.
- Existing tests that already exercise `_current_audit_stage` indirectly through `main(...)` — `test_no_history_exits_zero`, `test_converging_exits_zero`, `test_convergence_agrees_with_completeness_audit_detail_stage_demotion`, `test_convergence_prints_impact_recurrence_advisory`, `test_convergence_prints_edit_drift_advisory`, and `test_convergence_parse_failure_still_passes_classify_domain` (which monkeypatches `_current_audit_stage` itself with `lambda *a, **k: None`, so it tolerates the new parameter unchanged) — rerun unmodified as regression coverage; none of their assertions depend on `_current_audit_stage`'s signature.

Every test above, new and updated, must be green before this step is done; the unmodified regression cases must stay green throughout.

## Acceptance criteria

- `plan_tool/cli/convergence_cmd.py` calls `parse_plan(` exactly once, inside `cmd_convergence` — `_current_audit_stage` no longer imports or calls it.
- The "No parsed Plan here, so no map" comment above `record_convergence(` no longer claims no parsed `Plan` is available — it names the actual reason (deliberately not building a `code_fingerprint` map here) rather than a premise this step's own hoist makes false.
- `_current_audit_stage(ctx, path, None, detail_grade=...)` returns `None` for every `detail_grade` value, with no parsing attempted.
- `plan-tool convergence <name>` (through `main(...)`) still exits `0` when the target plan file's frontmatter or body fails to parse — `test_convergence_exits_zero_with_unparseable_plan_file` passes.
- All four updated `_current_audit_stage`-direct tests pass against the new signature, still asserting the same `STAGE_BARE` / `STAGE_DETAIL` outcomes they asserted before the hoist.
- Every currently-green test in `tests/cli/test_convergence_cmd.py` stays green.
- `uv run pytest tests/cli/test_convergence_cmd.py -q` passes.

## Applicable guardrails

- **The plan's Step intent** — the hoisted `parse_plan` call must keep degrading to `diagnose_convergence`'s pre-stage-bar blanket-blocking defaults on a parse failure or missing plan, matching `_current_audit_stage`'s current try/except outcome. This bounds the step to a behavior-preserving move: for every existing input (a parseable plan, an unparseable plan, a missing plan), `cmd_convergence`'s observable output and return code must be identical before and after this change.
- **The plan's "Out of scope" bullet on new blocking gates and exit-code flips** — bars this step from letting the hoist introduce any new exit-code path. `cmd_convergence` keeps returning `0` unconditionally except for the pre-existing name-resolution failure that already precedes this step's code.

## Deferred

- Reading `plan.steps` to build `declared_step_ids` / `step_statuses` and passing them into `diagnose_convergence` — step 4's job (`plan_tool/cli/convergence_cmd.py` is one of the callers step 4 wires, per step 2's Summary); this step only makes the parsed `Plan` reachable in `cmd_convergence`, it does not consume it beyond the existing `_current_audit_stage` call.
- Narrowing `cmd_convergence`'s new `except Exception` (or `_current_audit_stage`'s remaining one) to specific exception types such as `ParseError` or `ValidationError` — out of scope; this step preserves today's blanket-catch behavior exactly.
- Threading the parsed `Plan` into `plan_tool/cli/completeness_cmd.py` or any other caller of `diagnose_convergence` — this step's declared files scope it to `plan_tool/cli/convergence_cmd.py` and its test module only.
- Any change to `evaluate_arm_clustering`, `classify_arm_clustering_consensus`, or the arm-clustering advisory itself — owned by steps 1, 2, and 4.
