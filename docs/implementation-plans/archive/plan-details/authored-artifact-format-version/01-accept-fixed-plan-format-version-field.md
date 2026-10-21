> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Accept the fixed plan format_version field, reject an unsupported value before Plan.model_validate with `UnsupportedPlanFormatVersionError`, and distinguish it from annotate rough notes

## Summary

`Plan` gains a `format_version` field and two matching constants in `plan_tool/schema.py`; `plan_tool/parser.py:parse_plan_text` gains a check that reads the raw, still-untyped frontmatter mapping and refuses an unsupported declared value with the new `UnsupportedPlanFormatVersionError` — a `ValidationError` subtype — before `Plan.model_validate` ever runs. Running the check on the raw mapping, not inside the model, is the point: once the plan also carries an unrelated unknown key, `Plan.model_validate` raises on that key first and a version check inside the model would never fire. `plan_tool/annotate.py:_try_parse_plan` is the one other change: it currently treats *any* parse failure as "this is rough notes, not a plan" and swallows it; it now lets the new error through and turns it into an `AnnotateError` instead, so an unsupported-version plan is reported as a source failure rather than silently misjudged as freeform notes. `plan_tool/cli/annotate_cmd.py` needs no code change; `plan_tool/cli/inspect.py` owns the plan-format `validate` refusal and returns exit 1 independently of `--fail-on-findings`, while `plan_tool/cli/app.py` gives every other direct command the only safe recovery direction: use a build that supports the declared version. Step 3 extends `validate` only for the detail-format arm. On green, a plan with no `format_version` key or `format_version: 1` parses exactly as it does today; a plan declaring anything else refuses with a message naming the declared value and the supported set.

## Table of Contents

- [Why](#why) — the gap this step closes and why the check has to run outside `Plan.model_validate`
- [Files (creates vs edits)](#files-creates-vs-edits) — every file this step touches, including two that get tests only
- [Implementation](#implementation) — the constants, the gate, and the annotate change
- [Tests](#tests) — the parser, annotate, and CLI test cases this step adds
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan-level docs this step's design follows
- [Applicable guardrails](#applicable-guardrails) — which plan-level fences bind this step
- [Deferred](#deferred) — what later steps own instead

## Why

`Plan` sets `model_config = ConfigDict(extra="forbid", ...)` (`plan_tool/schema.py:208`), and `PLAN_FORMAT.md`'s validation rule 8 rejects any unrecognized frontmatter key. A plan written by a newer `plan-tool` build is therefore a hard parse rejection on an older one today, and the rejection message reads like a typo report ("unknown field") with nothing telling the operator the real cause is a format the older build has never heard of. Fixing that requires the older reader to be able to recognize a version it does not support — which this step ships as the read side of the contract, ahead of any writer stamping a declaration (step 2) so no artifact on disk can carry a version this build cannot already read.

The check has to live outside `Plan.model_validate` for the same reason the confusing error exists in the first place: pydantic surfaces every field error together, and an unrelated unknown key on a newer plan raises before any in-model check on `format_version` would run. `plan_tool/parser.py:parse_plan_text` already holds the raw YAML mapping (via `yaml.safe_load`) before it calls `Plan.model_validate`, which is the one place a version check can run first, unconditionally.

`plan_tool/annotate.py` adds a second wrinkle: it accepts both real plans and freeform rough notes, and today treats every `parse_plan_text` failure — malformed YAML, a schema violation, anything — as proof the input is notes rather than a plan. An unsupported-version plan is a real, structured plan that the operator or a newer build authored on purpose; annotate should say so, not fold it into the same bucket as a grocery list.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/schema.py` — add the plan format-version constants and the `Plan.format_version` field.
- `plan_tool/parser.py` — add `UnsupportedPlanFormatVersionError` and the pre-validation gate; call the gate from `parse_plan_text` before `Plan.model_validate`.
- `plan_tool/annotate.py` — change `_try_parse_plan` so it re-raises the new error (converted to `AnnotateError`) instead of swallowing it into the rough-notes fallback; update its docstring and `AnnotateError`'s docstring to say so.
- `plan_tool/cli/annotate_cmd.py` — **no code change.** `_annotate_one`'s existing `except (CreateError, AnnotateError)` around its `classify_plan_implementation` call already catches the converted error and records it as a per-source batch failure without extra code. Listed here so this step's `tests/cli/test_annotate_cmd.py` addition has a declared home.
- `plan_tool/cli/inspect.py` — `cmd_validate` keeps the existing `INVALID:` rendering for the new `ValidationError` subtype but returns exit 1 specifically for `UnsupportedPlanFormatVersionError`, independently of `--fail-on-findings`; ordinary schema-invalid plans retain their existing flag-controlled outcome. Update its docstring and the `--fail-on-findings` help to state the named-format-refusal carve-out. `plan_tool/locator.py:collect_plan_entries` remains unmodified and keeps its `MALFORMED` row.
- `plan_tool/cli/app.py` — catch `UnsupportedPlanFormatVersionError` before the generic parse/schema handler, preserve its diagnosis, return exit 1, and point to a build that supports the declared version. Do not offer an in-build command: the older binary cannot safely read or upgrade this plan.
- `RUNBOOK.md` — update `## Malformed frontmatter` so ordinary `INVALID:` remains exit 0 by default while a named format refusal exits 1 even without `--fail-on-findings`.
- `docs/cli/validate.md` — regenerate or update the checked-in CLI reference so the flag description names the same named-format-refusal carve-out.
- `tests/test_parser.py` — new test class covering the constants, the gate, and the ordering-before-`model_validate` guarantee.
- `tests/test_annotate.py` — new test(s) proving `classify_plan_implementation` raises `AnnotateError` (not a silent rough-notes fallback) for an unsupported-version source.
- `tests/cli/test_annotate_cmd.py` — new batch test proving one unsupported-version source fails independently while sibling sources in the same batch still annotate.
- `tests/cli/test_inspect_cmds.py` — new `list`/`validate` tests proving an unsupported-version plan renders exactly like any other schema-invalid plan.
- `tests/cli/test_app.py` — new top-level command-boundary test for the declared-version diagnosis and newer-build direction.

## Implementation

**1. The two constants and the field, in `plan_tool/schema.py`.**

Add, near `class Plan` (the roadmap subsystem's `plan_tool/roadmap_source_identity.py:BASELINE_FORMAT_VERSION` is a same-repo naming precedent for this shape, though it versions a different artifact and is out of scope to touch or import):

- `PLAN_FORMAT_VERSION = 1` — the only version this build currently writes.
- `SUPPORTED_PLAN_FORMAT_VERSIONS = frozenset({PLAN_FORMAT_VERSION})` — the set a reader accepts. Kept as its own name (not derived ad hoc at the call site) because step 6's coverage test and step 5's data-contract record both need a single symbol to point at.

Add a field to `Plan`: `format_version: int = PLAN_FORMAT_VERSION`. A plain `int` with a default is enough — do not add a `field_validator` that re-checks membership in `SUPPORTED_PLAN_FORMAT_VERSIONS` on the model itself. That check belongs solely in the pre-validation gate below; duplicating it as a model-level validator would not fire on the case that matters (a plan that also carries an unrelated unknown key — pydantic collects field errors, including `extra_forbidden`, and does not run `@model_validator(mode="after")` hooks when any field failed). The raw gate must overwrite this current-build model default with effective version `1` when the raw key is absent, so a version-2 build still treats an old declaration-free file as legacy version 1.

One side effect worth knowing rather than treating as a surprise: `plan_tool/parser.py:_explain_extra_field` builds its "allowed fields" list from `Plan.model_fields`, so `format_version` starts appearing there automatically for any "unknown plan-level field" message. No code change follows from this — `tests/test_parser.py::TestFormatValidationErrors::test_extra_plan_field_names_allowed_fields` only checks that specific known field names are present, not the complete list.

**2. The gate and the error type, in `plan_tool/parser.py`.**

Add `UnsupportedPlanFormatVersionError` as a subclass of the existing `ValidationError` (not `ParseError` — the step title names this exact class and the plan's Architecture section requires the subclass relationship so every existing `except ValidationError` / `except (ParseError, ValidationError)` site keeps working with no changes). Leave its `errors` list empty (the default) — `cmd_validate` and `locator.collect_plan_entries` (outside this step's files) both already fall back to printing `str(exc)` directly whenever `.errors` is empty, which is exactly the crafted message this error should show.

Add a function that reads the raw frontmatter mapping and raises when the declared (or defaulted) version is not supported, for example:

```python
def _require_supported_plan_format_version(raw: dict[str, Any]) -> int:
    declared = raw.get("format_version", 1)
    if type(declared) is not int or declared not in SUPPORTED_PLAN_FORMAT_VERSIONS:
        raise UnsupportedPlanFormatVersionError(
            f"plan declares format_version={declared!r}, which this build "
            f"does not support (supported: {sorted(SUPPORTED_PLAN_FORMAT_VERSIONS)})"
        )
    return declared
```

This is a starting point, not a mandate on naming — the constraints that matter are:

- **Absence defaults to legacy version 1**, applied inside this function (not left to `Plan`'s own field default). Assign that returned effective value into the raw mapping before `Plan.model_validate`; otherwise a later `Plan` default would relabel a declaration-free legacy file as current.
- **`type(declared) is not int` (not `isinstance`)** — YAML's `true`/`false` parse to Python `bool`, and `bool` is an `int` subclass, so `isinstance(True, int)` is `True` and would let a boolean declaration slip through as "version 1." Using `type(...) is not int` rejects booleans, strings, floats, and `None` alike, which is what "a non-integer plan value... fail[s] closed" in the plan's Testing section requires.
- **The message names both the declared value and the full supported set** — required by this step's and the plan's acceptance criteria, and it has to read sensibly for a malformed (non-int) declared value too, not only for an out-of-range int.

Call this function from `parse_plan_text`, right after the existing `isinstance(raw, dict)` check and before the existing `Plan.model_validate(raw)` call; store its effective version into `raw["format_version"]` before validation. That ordering is non-negotiable: it keeps the check from going inert behind an unrelated unknown-key error and preserves legacy absence once the model default advances.

**3. Distinguishing this from rough notes, in `plan_tool/annotate.py`.**

`_try_parse_plan` (used by both `_load_step_specs` and `_resolved_detail_paths`, both called near the top of `classify_plan_implementation` before any prompt is built or Claude is invoked) currently does:

```python
try:
    return parse_plan_text(source_text)
except Exception:
    return None
```

Add a specific clause ahead of the broad one so the new error is converted rather than swallowed:

```python
except UnsupportedPlanFormatVersionError as exc:
    raise AnnotateError(str(exc)) from exc
except Exception:
    return None
```

`_load_step_specs` runs before `_resolved_detail_paths` in `classify_plan_implementation`, so this raises once, before either helper's caller does anything else — no Claude call happens for a source that fails this way, which is the concrete, testable difference between "distinguished from rough notes" and "silently treated as rough notes" (a genuine rough-notes input reaches the invoker; this one does not). Import `UnsupportedPlanFormatVersionError` alongside the existing `parse_plan_text` import from `plan_tool.parser`. Update `_try_parse_plan`'s docstring (it currently describes only the swallow-into-`None` path) and `AnnotateError`'s docstring (it currently only mentions Claude-response failures) to mention this new raise reason.

Do not touch `_load_step_specs` or `_resolved_detail_paths` themselves — they call `_try_parse_plan` and propagate whatever it does; the fix belongs at the one shared call site.

**4. The direct-command recovery direction, in `plan_tool/cli/app.py`.**

Add a typed `except UnsupportedPlanFormatVersionError as exc:` clause before
the existing generic `(ParseError, ValidationError)` handler. It prints the
existing declared-and-supported message, returns `1`, and emits one `Try:`
line directing the operator to run a `plan-tool` build that supports the
declared format version. No command invocation belongs in that line: this
binary cannot interpret the plan well enough to perform an upgrade. The
generic handler remains unchanged for malformed YAML and ordinary schema
errors, including its `validate` and `list` suggestions. Step 3 later adds the
parallel detail-only handler; it does not catch or test this plan-format arm.

**5. The deliberate `validate` exit-code exception.**

The existing `cmd_validate` docstring, its `--fail-on-findings` help, the
checked-in `docs/cli/validate.md` reference, and `RUNBOOK.md`'s malformed-
frontmatter guidance all describe `INVALID:` as an exit-0 verdict. Update all
four to distinguish ordinary schema-invalid input from a named plan- or
detail-format refusal: the former keeps the flag-controlled exit code, while
the latter exits 1 unconditionally because this build cannot safely interpret
the declared artifact. This is the plan's one deliberate operator-visible
widening beyond its seed; do not describe a generic `INVALID:` as failing CI.

## Tests

For every invariant named above with a reason it must hold this way (not just a behavior it happens to produce), name the test after the invariant, not the code path, per this repo's testing convention.

### Tests for this step

`tests/test_parser.py` (new `TestFormatVersion` class, styled like the existing `TestRiskProfile`):

- `test_absent_format_version_parses_as_legacy_one_and_unchanged` — a plan with no `format_version` key parses to effective version `1` and retains today's semantic result. Temporarily advance the current default/support window in the fixture to prove this is not accidentally borrowing the current constant.
- `test_declared_current_version_parses_identically` — `format_version: 1` parses with no error and `plan.format_version == 1`.
- `test_declared_unsupported_version_is_refused_by_name` — `format_version: 999` raises `UnsupportedPlanFormatVersionError`; the message contains `"999"` and the supported-set literal.
- `test_unsupported_format_version_error_is_a_validation_error_subtype` — `isinstance(exc, ValidationError)` — pins the subclass relationship every existing `except ValidationError` site depends on, so a future refactor can't quietly detach it.
- `test_gate_fires_before_unknown_field_rejection` — a plan carrying both `format_version: 999` and an unrelated unknown top-level key raises `UnsupportedPlanFormatVersionError`, never the generic `extra_forbidden` error — the "refused for the version, not the key" trap named in the plan's Testing section, and the test that would catch a regression to checking the version inside `Plan.model_validate`.
- `test_non_integer_declared_values_fail_closed` (parametrized over a quoted string, `true`, `1.5`, and explicit `null`) — each raises `UnsupportedPlanFormatVersionError` rather than being treated as absent or as version 1; states that a malformed declaration refuses, it does not default.
- `test_format_version_default_is_a_supported_version` — `PLAN_FORMAT_VERSION in SUPPORTED_PLAN_FORMAT_VERSIONS`; guards against the two constants drifting apart, which would make every fresh plan unreadable by its own build.

`tests/test_annotate.py` (near the existing rough-notes / `_try_parse_plan` coverage):

- `test_unsupported_plan_format_version_is_reported_not_treated_as_rough_notes` — write a source with valid frontmatter declaring `format_version: 999` plus a `steps:` block; `classify_plan_implementation` raises `AnnotateError` whose message contains `"999"`; a recording stub invoker records zero calls, proving the Claude round trip a genuine rough-notes fallback would take never happens.

`tests/cli/test_annotate_cmd.py` (styled like the existing `test_batch_continues_past_per_file_failure_and_summarizes`):

- `test_batch_continues_past_an_unsupported_plan_format_version` — a batch of three sources where the middle one declares `format_version: 999`; `cmd_annotate` returns `1`; the two valid sources' `.annotated.md`/`.seed.md` are still written; the batch summary shows a `FAIL` row for the bad source; the recording invoker was called exactly twice (once per valid source).

`tests/cli/test_inspect_cmds.py` (styled like the existing `test_malformed_plan_marks_row_and_points_at_validate` and `test_validate_reports_invalid_risk_profile`, using a new `_FORMAT_VERSION_INVALID_PLAN` fixture constant alongside the existing `_SCHEMA_INVALID_PLAN` / `_RISK_PROFILE_INVALID_PLAN`):

- `test_unsupported_format_version_plan_renders_malformed_row` — `plan-tool list` shows a `MALFORMED` row and the "failed to validate" footer for a registered plan declaring an unsupported `format_version`, exactly as it does for any other schema-invalid plan.
- `test_validate_reports_unsupported_format_version` — `plan-tool validate` prints `INVALID: <path>` with the declared-and-supported message and exits `1` with or without `--fail-on-findings`; the existing invalid-risk-profile fixture remains the control proving ordinary schema-invalid input still honors that flag.

`tests/cli/test_app.py`:

- `test_unsupported_plan_format_version_has_a_supporting_build_direction` — driving `main()` through a plan-reading command with `format_version: 999` returns `1`, prints the declared-and-supported diagnosis plus one direction to use a build that supports it, and prints neither a traceback nor the generic `validate`/`list` suggestions.

`tests/cli/test_inspect_cmds.py` documentation assertion (or the existing
CLI-reference generation test, if one owns that path):

- `test_validate_format_refusal_docs_distinguish_the_exit_one_carve_out` — the
  `cmd_validate` docstring, generated validate reference, and malformed-
  frontmatter runbook text preserve ordinary `INVALID:` exit-0 behavior and
  name the named format-refusal exit-1 exception.

Every test above must be green before this step is considered finished. They cover exactly the behavior this step changes — the gate, its ordering, and the annotate distinction — and deliberately do not pad the roster with cases (e.g. write-side stamping, the detail-file marker) that later steps own.

## Acceptance criteria

- A plan with no `format_version` key parses to the same semantic result as before this effort and carries effective legacy version `1`, even after a future current-version default advances.
- A plan declaring `format_version: 1` parses with no error.
- A plan declaring any other integer, or a non-integer value in that key (a string, a boolean, a float, or explicit `null`), raises `UnsupportedPlanFormatVersionError` with a message naming the declared value and the complete supported-version set.
- `UnsupportedPlanFormatVersionError` is a subclass of `plan_tool.parser.ValidationError`.
- The refusal fires before `Plan.model_validate` runs, demonstrated by a plan that declares an unsupported version and also carries an unrelated unknown top-level key: the raised error is `UnsupportedPlanFormatVersionError`, not a generic extra-field error.
- `plan_tool.annotate.classify_plan_implementation` raises `AnnotateError` (converted from `UnsupportedPlanFormatVersionError`) for a source with an unsupported declared plan format version, and never invokes its Claude seam for that source.
- `plan-tool list` retains the existing `MALFORMED` row. `plan-tool validate` prints the same `INVALID:` verdict for an unsupported format version but treats this named format refusal as exit-1 independently of `--fail-on-findings`, matching the run-grade detail-format contract; ordinary schema-invalid plans retain their existing flag-controlled behavior.
- Every direct plan-reading command that reaches `main()` reports an unsupported plan version as a typed exit-1 refusal and directs the operator to a build supporting the declared version; it does not offer an impossible in-build upgrade or the generic malformed-plan suggestions.
- `cmd_validate`'s docstring and `--fail-on-findings` help, `docs/cli/validate.md`, and `RUNBOOK.md` distinguish the named-format-refusal exit-1 carve-out from ordinary `INVALID:` exit-0 behavior; the plan records that as its deliberate operator-visible widening.
- `plan-tool annotate` run against a batch containing one unsupported-format-version source and other valid sources continues past that source, writes no `.annotated.md`/`.seed.md` for it, and still writes both artifacts for the valid sources.

## References

- `PLAN_FORMAT.md` § "Validation rules" — rule 8, the unknown-field rejection this step's gate has to run ahead of.
- `DATA_CONTRACT.md` § "Version-evolution policy" — the fail-closed reading rule ("readers fail closed; they never guess a version") this step's gate follows for the plan class.
- `plan_tool/parser.py:parse_plan_text`, `plan_tool/schema.py:208` (`Plan`'s `extra="forbid"` config) — the seams this step's gate and field sit next to.
- `plan_tool/cli/app.py:main` — the typed command boundary that owns the plan class's supporting-build recovery direction.
- `plan_tool/roadmap_source_identity.py:BASELINE_FORMAT_VERSION` — an in-repo naming precedent for a format-version constant (a different subsystem and artifact; not imported or modified by this step).

## Applicable guardrails

- **The plan's "## Scope guardrails" binary-observable rule** — this step's gate checks exactly one thing (is the declared value one this build supports); it must not grow into a check of whether the rest of the plan's content matches what that version implies.
- **The plan's "## Scope guardrails" not-allowed list** — this step must not emit any warning or advisory for a *supported* declaration, must not infer or repair a version at read time (a malformed or unsupported value always refuses, never defaults), and must not give plan-reading commands a fallback path around the refusal — `list`/`validate`/`detail`/etc. keep using their existing malformed-plan handling exactly as it exists today.
- **The plan's "## Out of scope" carve-outs** — this step must not relax `Plan`'s `extra="forbid"` config, must not add any version other than 1 to the supported set, and must not touch the four staged roadmap artifacts or `roadmap_source_identity.py`'s unrelated `CanonicalSourceIdentity.format_version` field (tracked separately under `BACKLOG.md` #362).

## Deferred

- Stamping `format_version` into `write_plan` / `render_plan_text` output, and documenting the field in `PLAN_FORMAT.md` — step 2, which depends on this step's constant and gate.
- The run-grade detail file's body marker, its shared parser, and routing every semantic detail reader through a refusal — step 3.
- Making `detail.py` the sole writer of the detail marker — step 4.
- The `data_contract.py` version-only registry entry and the class-specific rules in `DATA_CONTRACT.md` — step 5, which names this step's constants.
- The explicit absent-to-1 upgrade entry point and its coverage test — step 6.
- Removing `BACKLOG.md` #356 and updating `CLAUDE.md`'s format-doc bullets — step 7.
- Any version 2 of the plan format, a migration engine, or content revision/lineage tracking — out of scope for the whole plan, per its own "## Out of scope" section.
