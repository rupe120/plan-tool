> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a `depends_on_notes` field to `Step` and reject a key that isn't in `depends_on`

## Summary

This step adds an optional `depends_on_notes: dict[int, str]` field to `Step` in `plan_tool/schema.py`, giving each `depends_on` edge an optional place to name what the dependent step consumes. Parse-time validation is structural only: every note key must appear in that same step's `depends_on` list; note text is never checked. Plans that omit the field keep parsing and rewriting unchanged — empty defaults are dropped by the existing `exclude_defaults` write path in `plan_tool/parser.py:render_plan_text`. Tests land in `tests/test_parser.py` (parse, reject, round-trip, backward compat) and `tests/test_fingerprint.py` (purity-cache stability plus a never-graded reference sweep). No `plan_tool/fingerprint.py` edit is required: the field stays out of `compute_purity_cache_key` by omission, and a test pins that.

## Table of Contents

- [Summary](#summary) — what ships and where it lives
- [Table of Contents](#table-of-contents) — section index
- [Why](#why) — the gap this step closes
- [Input](#input) — existing contracts this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — field shape, validator, and boundaries
- [Tests](#tests) — cases and green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — external docs worth reading
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly not this step

## Why

Today a step's `depends_on` list names ordering edges but gives no structured place to say what each edge delivers. Downstream work (create authoring, split/merge threading, cohesion grounding) needs that slot in the schema first. This step adds the field and the one parse rule that keeps keys aligned with declared edges, without touching any existing plan file or grading note content.

## Input

- **`plan_tool/schema.py:Step`** — the field lands here, next to `depends_on`. Follow the comment style used for `intent` and `concept_ids`: note that content checks live elsewhere (nowhere, by design) and that empty values are left out on rewrite.
- **`plan_tool/schema.py:Plan`** — its after-validator (`_validate_graph`) already rejects unknown ids in `depends_on`, self-deps, and cycles. It does **not** inspect `depends_on_notes`; the new key-in-`depends_on` rule belongs on `Step`, not on the plan-level graph walk.
- **`plan_tool/parser.py:render_plan_text` / `write_plan`** — round-trip serialization uses `plan.model_dump(exclude_defaults=True, exclude_none=True)` then `yaml.safe_dump` via `_coerce_enums`. No parser edit is expected: an empty `depends_on_notes` dict should disappear from rewritten frontmatter the same way an empty `concept_ids` list does.
- **PyYAML int-key mapping** — frontmatter will use YAML block mappings with integer keys (e.g. `depends_on_notes:\n  1: consumes the schema type`). Keys must round-trip as Python `int`, not strings.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/schema.py` — add `depends_on_notes` to `Step`; add a `@model_validator(mode="after")` that rejects note keys not in `depends_on`.
  - `tests/test_parser.py` — new test class covering parse, reject, partial coverage, round-trip, elision, and backward compat on existing fixtures.
  - `tests/test_fingerprint.py` — purity-cache stability when only `depends_on_notes` changes; never-graded reference sweep.

## Implementation

### Field shape

- Add **`depends_on_notes: dict[int, str] = Field(default_factory=dict)`** on `Step`, immediately after `depends_on`.
- **Rejected alternative:** restructuring `depends_on` into a list of `{id, note}` objects. The plan chose a sibling dict so `depends_on` semantics, ordering, and every existing consumer stay untouched.
- Omitting the field and supplying `{}` must behave the same: parsed steps expose an empty dict; rewritten plans with no notes omit the key entirely.

### Cross-field validator (existence only)

- Add a **`Step`-level `@model_validator(mode="after")`** (one way: `_depends_on_notes_keys_valid`) that computes `{d for d in self.depends_on}` and rejects any key in `self.depends_on_notes` that is not a member.
- **Report every bad key in one error**, naming the step id and the offending key(s) — same spirit as the plan-level graph validator's `"step {id} depends_on references unknown id(s): …"` message.
- **Do not** validate note content: empty strings, placeholders, multi-line text, and implausible wording all parse. Empty-string values are a parse-time courtesy only (content is never graded) — **authoring paths in steps 3–4 must never write `{id: ""}`**; silent edges omit the key. Prefer documenting that distinction in the field comment so later steps do not treat empty string as the canonical "asked and silent" representation.
- **Do not** require a note for every `depends_on` entry. Partial coverage (notes for some edges only) is valid.

### Parse-time checks this step deliberately does not add

List these in tests as "parses without raising" cases — they define what later steps own:

- **Note content** — no length, plausibility, or truth checks (the plan's content-validation fence).
- **Full edge coverage** — missing notes for declared `depends_on` ids are allowed.
- **Direct plan-level id resolution for note keys** — membership in `depends_on` is enough; the existing plan-level graph validator already ensures those ids exist.

### Serialization and callers

- **No `plan_tool/parser.py` change expected.** `render_plan_text` re-validates via `Plan.model_validate` after dump; a round-trip test is the guard.
- **`plan_tool/fingerprint.py:compute_purity_cache_key`** — do **not** add `depends_on_notes` to `PurityKeyComponents` or the combined digest. It belongs with the deliberately excluded `title`/`complexity` set (metadata about rationale, not verdict inputs). Exclusion is by omission; `tests/test_fingerprint.py` pins it.
- **Caller sweep at HEAD:** no production module reads `depends_on_notes` yet. After this step, the only allowed reference under `plan_tool/` should be `plan_tool/schema.py` until later plan steps add consumers.

### Never-graded regression sweep

- Add a coarse test (likely in `tests/test_fingerprint.py` or a dedicated case in `tests/test_parser.py`) that scans `plan_tool/**/*.py` for the token `depends_on_notes`.
- **At step 1 landing, the allowlist is `{plan_tool/schema.py}` only.** Later steps (2–6) extend the allowlist when they add legitimate readers/carriers; the test must never be deleted — it is the guard against wiring the field into scoring or gating later.
- Document in the test comment that `plan_tool/create.py` authoring paths join the allowlist in step 3, and transform paths in steps 2 and 4.

## Tests

Every test below must be green before this step is done.

### Tests for this step

**`tests/test_parser.py`** (new `TestDependsOnNotes` class, helper `_depends_on_notes_plan(...)` mirroring `_concept_plan`):

- `test_depends_on_notes_absent_defaults_empty` — a plan with no field parses; `step.depends_on_notes == {}`.
- `test_depends_on_notes_parses_valid_mapping` — YAML block mapping with int keys and string values round-trips through `parse_plan_text`.
- `test_depends_on_notes_rejects_key_not_in_depends_on` — e.g. `depends_on: [1]` plus `depends_on_notes: {2: "…"}` raises `ValidationError` naming the bad key.
- `test_depends_on_notes_allows_partial_coverage` — `depends_on: [1, 2]` with a note only for `1` parses.
- `test_depends_on_notes_accepts_empty_string_value` — `{1: ""}` parses (content not graded). Document in the test comment that this is **not** the authoring representation of silence — steps 3+ omit the key instead.
- `test_depends_on_notes_round_trips_through_write_plan` — parse → `write_plan` → re-parse preserves the mapping; body unchanged.
- `test_empty_depends_on_notes_elided_on_write` — after write, frontmatter contains no `depends_on_notes:` key.
- `test_existing_well_formed_fixture_unchanged` — `parse_plan(tests/fixtures/well_formed.md)` still succeeds with no `depends_on_notes` on any step.

**`tests/test_fingerprint.py`:**

- `test_purity_cache_key_stable_when_depends_on_notes_changes` — same plan/step/disk state, only `depends_on_notes` edited → `compute_purity_cache_key` digest unchanged (parallel to `test_purity_cache_key_stable_when_title_or_complexity_changes`).
- `test_depends_on_notes_references_confined_to_allowlist` — every `depends_on_notes` mention under `plan_tool/` is in the step-1 allowlist (`schema.py` only).

## Acceptance criteria

- `Step` exposes `depends_on_notes: dict[int, str]` defaulting to `{}`.
- A note key not present in the same step's `depends_on` list raises a validation error naming the step id and offending key(s).
- Valid partial notes parse; empty string values parse; note content is never validated.
- Plans without `depends_on_notes` (including `tests/fixtures/well_formed.md`) parse unchanged.
- `write_plan` drops an empty `depends_on_notes` from frontmatter.
- A note-only edit leaves `compute_purity_cache_key` output unchanged.
- The never-graded sweep passes with references only in `plan_tool/schema.py`.
- All new tests in `tests/test_parser.py` and `tests/test_fingerprint.py` pass.

## References

- [Pydantic v2 — Fields](https://docs.pydantic.dev/latest/concepts/fields/) — `Field(default_factory=dict)` and optional-field defaults for `dict[int, str]`.
- [Pydantic v2 — Validators](https://docs.pydantic.dev/latest/concepts/validators/) — `@model_validator(mode="after")` for the key-in-`depends_on` cross-field check.
- [Pydantic v2 — Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) — how `exclude_defaults` keeps absent notes out of rewritten frontmatter.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — int-key mapping behavior in frontmatter.
- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — mapping-key scalar resolution for bare integer keys.
- [Python typing — dict](https://docs.python.org/3/library/typing.html) — `dict[int, str]` annotation style matching `plan_tool/schema.py`.

## Applicable guardrails

- **Plan fence (structural key membership only)** — this step may add structural key-in-`depends_on` membership validation; it must not require notes on edges, gate on note presence/absence, or check note wording, length, or truth. Silent = absent key.
- **Plan "## Out of scope", gates and grading** — no gate, exit-code flip, refusal-to-advance, or severity change keyed on note presence or absence; no content scoring.
- **Plan "## Out of scope", existing plans** — do not rewrite corpus plans to add notes; backward compat is required.
- **Plan "## Out of scope", `depends_on` semantics** — do not change `depends_on` validation, ordering rules, self-reference handling, or cycle detection in `plan_tool/schema.py:Plan`'s graph validator.

## Deferred

- **`PLAN_FORMAT.md` documentation** — step 6 owns the human-facing field contract.
- **`plan_tool/create.py` authoring and interactive review** — steps 3–4 thread notes through proposal, wizard, and review UI.
- **Split / merge / scope-out note threading** — step 2 carries notes through transforms and remaps keys with `depends_on`.
- **Note content validation of any kind** — permanently out of scope per the plan fence.
- **Requiring notes on all edges** — out of scope; silence stays valid.
- **Expanding the never-graded allowlist** — steps 2–6 update the sweep test when they add legitimate consumers; not part of this step's code changes beyond documenting the extension point in the test.
