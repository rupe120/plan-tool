# Step 1 — Add the `stack` collection to `02-constraints.md` parsing and rendering

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Adds an optional `stack` collection to `ConstraintsArtifact` in `plan_tool/roadmap_artifacts.py`: a new frozen row type, a parse helper beside `_parse_hosting_rows`, and a render branch in `render_constraints_artifact`.
- The key design decision is that **a missing collection (`None`) is different from an empty one (`()`)**. A missing `stack` key parses to `None` and renders with no `stack` key at all. A present `stack: []` parses to `()` and renders back as `stack: []`.
- On green, every `02-constraints.md` that has no `stack` key parses as "stack not recorded" and re-renders byte-for-byte as before. A stack-bearing artifact round-trips through `parse_constraints_artifact` and `render_constraints_artifact` unchanged.
- This step is shape-only. Totality, unknown-concern, and duplicate-id checks belong to the gates step.

## Table of Contents

- [Summary](#summary) — what the step does and the observable result
- [Why](#why) — the compatibility problem the missing-versus-empty split solves
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — row shape, parse and render rules, and what must not change
- [Tests](#tests) — the cases that pin the behavior
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading for this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs to later steps

## Why

- Stack facts have no typed home today. Hosting rows hold coarse categories, store rows hold an optional `product`, and language/runtime is recorded nowhere.
- Accepted versions are stored and digested as rendered text, and they are never rewritten. A parser that reads a missing collection as an empty one, or a renderer that always emits `stack: []`, changes the bytes of every existing version.
- The risk is real because `render_constraints_artifact` always emits `hosting: []` when `artifact.hosting` is empty. Copying that pattern for `stack` would be the wrong default.
- Later steps need to tell "stack not recorded" apart from "stack present but incomplete". The gate in the next step binds the second case and not the first, so that difference has to exist in the parsed type.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py`:
    - add the stack row type and the concern vocabulary constant;
    - add a `stack` field to `ConstraintsArtifact`;
    - add a `_parse_stack_rows` helper and call it from `parse_constraints_artifact`;
    - add a conditional `stack` entry to the mapping built in `render_constraints_artifact`.
  - `tests/test_roadmap_artifacts.py`: add the cases under Tests, and adjust only the existing assertions that a stack-bearing fixture would break.

## Implementation

**Row type.** Add a frozen dataclass, for example `StackRow`, next to `HostingRow`.
- Fields:
  - `id: str`
  - `concern: str`
  - `choice: Optional[str] = None`
  - `open: bool = False`
- A stack row carries exactly one of `choice` (non-empty text) or `open: true`. The parser accepts any combination, and step 2's `stack-row-state` gate owns the rule. This keeps `open` an explicit marker rather than an empty value, and it avoids storing a "pending" flag. Pending-ness is derived from decisions anchored to the row's id and is never stored on the row.
- The implementer owns the exact field names. Whatever lands is what the later steps and the format docs cite.

**Concern vocabulary.** Add a constant in the style of `HOSTING_FACETS`, for example `STACK_CONCERNS`, naming the three required concerns (deployment platform, store engine, language/runtime).
- The parser must not enforce membership. An unknown concern parses fine and is the gate's report. This is the same split the module docstring states ("shape is checked here; relations are not").
- The gates step imports this constant. Defining it here keeps one source for the spelling.

**Field on `ConstraintsArtifact`.** Add `stack: Optional[tuple[StackRow, ...]] = None`.
- Keep the default `None`, placed after `hosting` and before `feedback`, so every existing positional and keyword construction still works.
- `None` means "not recorded". `()` means "present and empty". Never use `()` as the default.

**Parse rules** (`_parse_stack_rows`, beside `_parse_hosting_rows`):
- Key absent from the frontmatter: return `None`.
- Key present as a list (including `[]`): return a tuple of rows in source order. Do not dedupe or sort. Duplicate ids must survive for the duplicate-id gate.
- Key present as `null`: recommended to read as absent (`None`), matching how `_iter_rows` treats a null collection. Pin the choice with its own test.
- Key present as a non-list, a non-mapping row, a missing `id`, `concern` or both state fields, or a wrong-typed value: raise `RoadmapArtifactError`. Reuse `_iter_rows`, `_row_id` and `_row_text`.
- A row with both `choice` and `open: true`, or with neither, is a shape error, because the row's own two states contradict or are absent.
- `_iter_rows` cannot make the missing-versus-empty split on its own, so check `"stack" in frontmatter` before calling it.
- Keep the schema open: an unknown key on a stack row is ignored, as everywhere else in the module.

**Render rules** (`render_constraints_artifact`):
- Emit the `stack` key only when `artifact.stack is not None`. Do not use truthiness, or `stack: []` would be dropped and the parse of the rendered text would no longer equal the original.
- Place the key after `hosting`. Do not reuse the `_review_mappings` omit-when-empty path, because that path omits empty collections and this one must keep them.
- Render `choice` only when it is set, and `open` only when it is true (the same omit-rather-than-null habit as the `product` fields).

**Constants and shared surfaces that must not change.**
- Do not add `"stack"` to `CONSTRAINTS_ROW_KEYS`. Existing tests assert that a rendered constraints artifact's keys equal that tuple exactly (`tuple(rendered_frontmatter) == CONSTRAINTS_ROW_KEYS`), and a stack-less artifact must keep rendering exactly those keys. The prompt-pinning tests in `tests/test_roadmap.py` and `tests/test_roadmap_format.py` read the same tuple.
- Recommended approach: put the optional key in a separate constant (for example `CONSTRAINTS_OPTIONAL_ROW_KEYS = ("stack",)`), and let the prompt and docs steps decide how to pin it.
- Leave `stage_row_collections`, `design_row_collections`, `StageRow` and `_STAGE_ROW_OPERATION_POLICIES` alone. Feedback targets and candidate operations are a later step.

**Other places that touch the same logic** (the parse/render of the constraints artifact):
- `plan_tool/roadmap_gates.py` consumes `ConstraintsArtifact` and `HOSTING_FACETS`. The totality, unknown-concern and duplicate-id gates, and the anchor union, are the next step's work.
- Any code that builds `ConstraintsArtifact(...)` directly (grep `ConstraintsArtifact(` in `plan_tool/` and `tests/`) stays valid because of the defaulted field. Confirm that by running the suite rather than editing those sites.

**Rejected alternatives.**
- Always emitting `stack: []` for a stack-less artifact: rejected because it changes the bytes and digests of every existing version.
- Defaulting the field to `()` so that absent and empty are the same value: rejected because it makes "stack not recorded" and "empty stack" indistinguishable. The gate step needs that difference.

## Tests

All cases go in `tests/test_roadmap_artifacts.py` (unit tests, no backend seam). Approx. 12 cases.

- `test_constraints_without_stack_key_parses_to_none` — a fixture with no `stack` key yields `artifact.stack is None`, not `()`.
- `test_constraints_with_empty_stack_list_parses_to_empty_tuple` — `stack: []` yields `()`, which is different from `None`.
- `test_stack_null_is_read_as_not_recorded` — `stack:` with a null value yields `None`, pinning the chosen null reading.
- `test_stackless_constraints_render_has_no_stack_key` — rendering an artifact whose `stack` is `None` produces frontmatter with no `stack` key.
- `test_stackless_constraints_text_rerenders_byte_identically` — parse then render of the existing `CONSTRAINTS_TEXT` fixture (and a hosting-bearing one) returns the same text. This is the version-compatibility guard.
- `test_empty_stack_survives_round_trip_as_present` — an artifact with `stack=()` renders `stack: []`, and re-parsing gives `()`. This proves render does not use truthiness.
- `test_stack_rows_round_trip_choice_and_open` — one chosen row and one `open` row satisfy `parse(render(x)) == x`, and the rendered YAML holds plain strings and bools.
- `test_stack_row_with_choice_and_open_is_a_shape_error` — a row carrying both raises `RoadmapArtifactError` naming the row id.
- `test_stack_row_with_neither_choice_nor_open_is_a_shape_error` — a row carrying neither raises, naming the row id.
- `test_stack_wrong_types_raise` (parametrized) — a non-list `stack`, a non-mapping row, a missing `concern`, and a non-string `choice` each raise.
- `test_unknown_concern_and_duplicate_ids_parse_without_raising` — an unknown concern and two rows sharing an id both parse and stay in source order. Both are gate findings and not parse errors.
- `test_stack_rows_keep_source_order_without_collapsing` — duplicate ids survive as separate rows, so the later duplicate-id gate has something to detect.

### Tests for this step

- Every case above must be green before this step is finished.
- The existing `CONSTRAINTS_ROW_KEYS` key-order assertions must stay green unchanged for stack-less fixtures. This is the check that `CONSTRAINTS_ROW_KEYS` was left alone.
- The tests cover only the behavior this step changes: the missing-versus-empty split, the shape rules, and the round trip.

## Acceptance criteria

- `parse_constraints_artifact` returns `stack is None` for text with no `stack` key, `()` for `stack: []`, and a source-ordered tuple of the new row type otherwise.
- `render_constraints_artifact` output contains no `stack` key when `artifact.stack is None`, and the `stack` key (including `stack: []`) when it is not.
- Parsing and re-rendering any existing stack-less `02-constraints.md` fixture reproduces its text exactly.
- `parse_constraints_artifact(render_constraints_artifact(x)) == x` for artifacts with `stack` as `None`, `()`, and populated.
- A row with both or neither of `choice` and `open`, or a wrong-typed field, raises `RoadmapArtifactError` naming the row id.
- Unknown concerns and duplicate ids parse without raising.
- `CONSTRAINTS_ROW_KEYS` is unchanged, and the full `tests/test_roadmap_artifacts.py`, `tests/test_roadmap.py`, `tests/test_roadmap_format.py` and `tests/test_roadmap_gates.py` pass.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — read for frozen dataclasses and defaulted fields when adding the row type and the new `ConstraintsArtifact` field.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — read for how `safe_load` reads a null value and an empty list, so the missing, null and empty cases stay distinct.
- [YAML Ain't Markup Language (YAML) Version 1.2.2](https://yaml.org/spec/1.2.2/) — read for how `open: true` and `null` are typed, so `open` is never confused with a missing value.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — read for the parametrized wrong-type cases.

## Applicable guardrails

- **The plan's "## Out of scope", the fifth-artifact item:** the collection lives inside `02-constraints.md`. This step adds no new artifact file, filename constant, or path helper.
- **The plan's "## Out of scope", concerns beyond those the plan names and a closed vendor vocabulary:** the concern constant lists only the plan's concerns, and `choice` is free text with no product vocabulary.
- **The plan's "## Out of scope", regenerating or rewriting accepted versions:** this step reads and renders old text unchanged. It writes no migration and rewrites nothing on disk.
- **The plan's "## Out of scope", judging a choice and approval blocks:** the parser checks shape only. It does not compare a stack row with a hosting or store `product`, and it adds no refusal.

## Deferred

- Totality, unknown-concern and duplicate-id gates, and stack ids joining the anchor union and the identity rows — the gates step, since relations are the gates' work and not the parser's.
- Making stack rows feedback targets and adding their candidate operation policy (`stage_row_collections`, `_STAGE_ROW_OPERATION_POLICIES`) — the feedback and candidate step.
- Restating the field names and the `open` spelling in the constraints prompt — the prompt step. That step also decides how its pinning test reads the optional key.
- The stack summary module and the first-run, `INDEX.md` and candidate-review callouts — the summary and review-callout steps.
- Seed rendering and the `ROADMAP_FORMAT.md` documentation — the seed and documentation steps.
