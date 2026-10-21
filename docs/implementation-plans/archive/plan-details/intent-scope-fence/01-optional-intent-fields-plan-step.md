> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add optional intent fields to Plan and Step

## Summary

This step adds one optional field named `intent` to each of the two Pydantic models in `plan_tool/schema.py` — `Plan.intent` and `Step.intent` — plus a `TestIntent` class in `tests/test_parser.py`. The main design decision is that the schema does **no** checking beyond the type: an empty, whitespace-only, placeholder, very long, or multi-line intent all parse without complaint. Step 2 owns the advisory finding, and it checks presence only. Nothing else changes — no validator, no constant, no parser edit, no fixture edit. On green, a plan or step can carry a one-line `intent:` that survives a parse → write → parse round trip unchanged, while every plan already on disk parses and rewrites exactly as it does today.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the field has to exist before any of the four later steps can start.
- [Input](#input) — the round-trip and validation behavior in `parser.py` this step leans on but does not own.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited files, no new files.
- [Implementation](#implementation) — the two field declarations, the checks deliberately left out, and the rules that are not free to vary.
- [Tests](#tests) — the ~12 cases in `TestIntent` and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the pydantic and YAML docs behind the field and the multi-line case.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step, and the one place breaking them is tempting.
- [Deferred](#deferred) — what the later steps and the carved follow-up own, and why no doc changes here.

## Why

`extra="forbid"` on both models (`plan_tool/schema.py`, `Plan.model_config` and `Step.model_config`) means no plan file can carry an `intent:` key until the model declares it — a plan that tried would fail to parse with "unknown plan-level field". Every other step in this plan reads or writes that key: step 2's advisory check, steps 4–5's prompt rendering, and the carved follow-up's `create` authoring, split/merge rules, forward seeds, and docs. So this is the unblocking step, and it is small on purpose. It is also the step that mints the two names the rest of the plan and `PLAN_FORMAT.md` will use, so the names are settled here rather than falling out of whatever gets typed first.

## Input

This step relies on three behaviors it does not own, all in `plan_tool/parser.py`:

- **Absent optional fields are left out on rewrite.** `write_plan` and `render_plan_text` both dump with `model_dump(exclude_defaults=True, exclude_none=True)`, so a field left at `None` never appears in rewritten frontmatter. This is what makes "no plan on disk changes" true without writing any code for it — the same mechanism `status_note`, `registered_by`, and `enforce_test_authoring` already ride.
- **Key order in rewritten frontmatter follows field declaration order.** Both dumps pass `sort_keys=False` to `yaml.safe_dump`, so where the field sits in the model class decides where the key sits in the file. Nothing depends on that order; it is a readability choice only.
- **The allowed-field list in error messages is derived, not hand-written.** `parser.py:_explain_extra_field` builds it from `Plan.model_fields` / `Step.model_fields`, so the new name shows up in "unknown … field (allowed: …)" with no edit. Its misplacement hint (`; <field> belongs on a step`) fires only for a name defined on the *other* model — since `intent` lands on both, that branch never fires for it, exactly like `title`, `status`, and `features` today.

One pydantic behavior is also load-bearing: an `Optional[str]` field rejects a YAML int, list, or mapping on its own, with no custom validator. `tests/test_parser.py:TestStatusNote::test_status_note_rejects_non_string_types` passes at HEAD against a plain `status_note: Optional[str] = None`, which is the proof. Do not add a validator to get type rejection — it is already there.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/schema.py` — add `intent: Optional[str] = None` to `Plan` and to `Step`, each with a short comment stating the contract.
  - `tests/test_parser.py` — add a `TestIntent` class (~12 cases).

No test fixture is added or edited. `TestConceptOwnership` (via its `_concept_plan` helper) and `TestFeatures` (via the `_FEATURE_PLAN` module constant) both build plan text inline in `tests/test_parser.py` rather than adding a file under `tests/fixtures/`; follow that, which keeps the step inside its two declared files. Leaving every fixture untouched is also the plan's stated proof that no migration is needed.

## Implementation

**Add one field to each model, named `intent` on both.**

- Declare `intent: Optional[str] = None` on `plan_tool/schema.py:Plan` and on `plan_tool/schema.py:Step`.
- Use the same name on both. Sharing a field name across the two models is normal here — `title`, `status`, and `features` already do it — and one name is what lets a single rule be documented once, and steps 4–5 render both halves through one path.
- These names are this step's to mint, and step 2 reads them, so they are settled here. Do not rename them later in the plan.
- Put each declaration right after `title` on its model. "What it is" then "why it exists" reads best in the rewritten file, and nothing depends on the position (see [Input](#input)).
- Comment each field in the repo's terse style: one line stating it is a one-line note on why the plan or step exists, one line saying presence is advisory and checked in `plan_tool/review.py` (step 2), never at parse time — and that nothing anywhere checks an intent's length. The `plan_tool/schema.py:Feature` docstring is the stance to mirror — "types only … all semantic checks are advisory and live in `review.validate_feature_refs`, never at parse time".

**Ship no validator. The list of things that must still parse is the real contract of this step.**

The type annotation is the whole parse-time check. Each of the following must parse without raising, and each earns a test:

- `intent: ''` — empty string. Parses to `""`, and stays `""` on rewrite (`exclude_none` drops `None`, not `""`).
- `intent: '   '` — whitespace only. Parses untrimmed.
- `intent: TODO` — placeholder text. Not a parse error.
- A single line of several hundred characters. No cap anywhere in the schema.
- `intent: |` followed by an indented block — real newlines survive into the string, exactly as `tests/test_parser.py:TestStatusNote::test_status_note_literal_block_preserves_newlines` pins for `status_note`.

**Store what YAML hands over, unchanged.** No `.strip()`, no folding newlines into spaces, no turning `""` into `None`. Step 2 has to tell an empty intent from a whitespace-only one from a multi-line one to word its finding; normalizing here destroys the evidence that check needs and moves a rule into a second home. Worth knowing while writing the multi-line test: a plain (unquoted) multi-line YAML scalar is folded by YAML itself into one space-joined line, so a `|` literal block is the only way a newline reaches the field. That is YAML's line-folding rule, not anything this step does.

**The rejected alternative — a `field_validator` on `intent`.** The obvious version caps the length, or rejects an empty or multi-line value, mirroring `plan_tool/schema.py:Step._gate_entries_nonempty`. Reject it for three reasons: the plan's fence forbids making intent required at parse time; a hard cap turns a cosmetic style problem into an unparseable plan file, and `run`/`detail`/`jira` would then break on an artifact that is otherwise fine; and absence, placeholder, and over-length are one advisory finding class in step 2, so a schema-side length rule would split one rule across two homes. `_gate_entries_nonempty` exists because an empty gate command silently breaks the gate runner — nothing breaks on a bad intent.

**A second rejected alternative — a shared `Intent` model or a mixin.** It is one optional string on two models. `Feature` is its own model because it carries two fields that travel together; a lone string does not need that.

**Constraints that are not free to vary:**

- **Do not edit `plan_tool/parser.py`.** Round-tripping, elision, and the error-message field list all already work for a new optional field. If something there seems to need a change, that is a signal the field was declared differently than described above.
- **Do not mint a length constant here.** Nothing in this step reads it; step 2 owns the cap and its constant.
- **Do not touch `plan_tool/__init__.py`.** `Plan` and `Step` are already re-exported; a new field on an exported model needs no export change.
- **Leave every file under `tests/fixtures/` alone.** An edited fixture would weaken the no-migration proof.

## Tests

All cases go in `tests/test_parser.py`, in a new `TestIntent` class placed alongside `TestStatusNote` and modeled on it — that class is the closest sibling (an optional prose field on `Step`) and already covers the parse / default / round-trip / literal-block / non-string / not-introduced-on-write shape.

### Tests for this step

- `test_plan_and_step_intent_default_to_none` — parsing `tests/fixtures/well_formed.md` (which declares no intent) leaves `plan.intent is None` and every step's `intent is None`.
- `test_plan_intent_parses_when_present` — a plan-level `intent:` reaches `Plan.intent` as the exact string.
- `test_step_intent_parses_when_present` — a step-level `intent:` reaches that step's `Step.intent` as the exact string.
- `test_intent_round_trips_through_write_plan` — parse → `write_plan` → parse leaves both values unchanged, and the prose body is unchanged.
- `test_absent_intent_not_introduced_on_write` — rewriting `tests/fixtures/well_formed.md` produces no `intent:` line anywhere. This is the no-migration guard.
- `test_plan_intent_rejects_non_string_types` — parametrized over `42`, `[a, b]`, `{a: 1}`; each raises `ValidationError` naming `intent`.
- `test_step_intent_rejects_non_string_types` — same three values at step level, same expectation.
- `test_empty_intent_is_preserved_not_collapsed` — `intent: ''` parses to `""` (not `None`) and is still `""` after a round trip.
- `test_whitespace_only_intent_is_accepted_untrimmed` — `intent: '   '` parses and keeps its spaces; documented as step 2's finding, not a parse error.
- `test_placeholder_intent_is_accepted` — `intent: TODO` parses; documented as step 2's finding, not a parse error.
- `test_long_intent_is_accepted` — a single-line intent of ~500 characters parses; no cap exists anywhere, in this step or any other.
- `test_multi_line_intent_keeps_its_newlines` — an `intent: |` literal block arrives with newlines intact, and the parser neither joins nor trims them.
- `test_unknown_field_message_lists_intent_for_both_containers` — `format_validation_errors` on an `extra_forbidden` error names `intent` in the allowed list for the plan container *and* the step container. This is the cheap guard that the field really landed on both models.

**Green-before-done gate:** every case above passes, plus `uv run pytest tests/test_parser.py -q` with no existing case edited, plus the full suite `uv run pytest tests/ -q` with no file under `tests/fixtures/` modified.

## Acceptance criteria

- `Plan.model_fields["intent"]` and `Step.model_fields["intent"]` both exist, and each field's default is `None`.
- `rg 'intent' plan_tool/schema.py` shows only the two field declarations and their comments — no `field_validator`, no `model_validator`, no constant.
- `parse_plan_text` on a plan whose frontmatter carries `intent` at plan level and on a step returns both strings exactly as written, with no stripping.
- Parsing `tests/fixtures/well_formed.md` and writing it back with `write_plan` produces a file containing no `intent:` substring.
- `intent: ''` parses to `""` and is still `""` after a parse → write → parse cycle.
- `intent: 42` raises `ValidationError` whose message names `intent`, at both plan and step level.
- An `intent: |` literal block round-trips with its newlines intact.
- `git status` after the step shows exactly two changed files: `plan_tool/schema.py` and `tests/test_parser.py`.
- This step does **not** write this plan's own `intent:` values. The plan body forbids any step from owning that edit: the parent `run` process holds a pre-change `plan_tool.schema`, so `extra="forbid"` would strip the key at the end-of-step rewrite. Adoption belongs to a later invocation or a hand edit.
- `uv run pytest tests/ -q` is green.

## References

- [Fields — Pydantic v2](https://docs.pydantic.dev/latest/concepts/fields/) — the reference for declaring an optional field with a default on a `BaseModel`; the models here are pydantic, not stdlib dataclasses.
- [Serialization — Pydantic v2](https://docs.pydantic.dev/latest/concepts/serialization/) — what `exclude_defaults` and `exclude_none` do on `model_dump`, which is the mechanism that keeps an unset `intent` out of rewritten plan files.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_load` / `safe_dump`, scalar styles, and key ordering; the round-trip semantics that decide whether adding a frontmatter field rewrites existing plan files.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — the normative rules on scalar styles and line folding; read it for why a plain multi-line scalar arrives folded to one line while a `|` block keeps its newlines.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases, used for the non-string rejection sets at plan and step level.

## Applicable guardrails

- **Nothing becomes required at parse time, and no plan on disk is migrated.** This binds this step harder than any other, because this is the step that touches the schema. The field is `Optional` with a `None` default, and no fixture or plan file is edited. The tempting violation is a small `field_validator` capping the length or rejecting an empty value — that is a parse-time requirement, and it is refused here.
- **No step ships a check comparing an intent against prose or against a diff.** This step ships no check at all. Nothing in `plan_tool/schema.py` may read the plan body or a detail file.
- **Allowed behavior changes: two optional frontmatter fields.** This step ships exactly those two declarations and their tests. No constant, no helper function, no new export, no parser change.
- **Findings asking for a required intent, an agreement check, or wider propagation go to `BACKLOG.md`.** They are outside this plan's fence; do not apply them as expansion of this step.

## Deferred

- **The advisory check for a missing or placeholder intent** — step 2 owns it in `plan_tool/review.py`. No cap constant is minted here or anywhere: the plan's `## Scope guardrails` forbid validating an intent beyond its presence, so no length rule exists to consume one.
- **Rendering intent into any prompt** — steps 3, 4, and 5 own the shared fence renderer and the `detail` / `run` prompt seams.
- **`create` filling a plan's intent from the seed's `## Outcome`, and proposing a per-step intent** — the carved follow-up seed owns `plan_tool/create.py`.
- **What `split` and `merge` do with a step's intent** — the carved follow-up seed owns the rule. For grounding: both paths in `plan_tool/detail.py` build fresh steps with explicit keyword arguments (the replacement-`Step(...)` list in the split path, and the `merged = Step(...)` construction in the merge path), so with this step alone an intent is simply not carried onto a rebuilt step. Whether that stays the rule is the carved follow-up seed's call, not a defect of this step.
- **Carrying intent into the scope-out and reground forward seeds** — the carved follow-up seed owns `plan_tool/scope_out.py` and `plan_tool/reground.py`.
- **All documentation, including `PLAN_FORMAT.md`'s frontmatter schema block** — the carved follow-up seed owns it. This plan's own `intent` values are not written by any step — see the acceptance criteria.
- **A `DATA_CONTRACT.md` entry** — not needed and not written. That doc covers persisted runtime schemas, and the one plan-frontmatter field it documents (`steps[].concept_ids`) is there because it joins to the separate `concepts.json` record. `intent` joins to nothing outside the plan file, so `PLAN_FORMAT.md` is its only home. If a later audit disagrees, route it to reconcile rather than widening this step.
- **Any backfill of intent onto existing plans** — refused by the plan's fence, not merely deferred.
