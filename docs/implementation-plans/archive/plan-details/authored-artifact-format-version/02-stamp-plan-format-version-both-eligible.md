> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Stamp the plan format version in both eligible plan serializers (write_plan and render_plan_text), keeping write_plan's whole-file overwrite, byte-preserved body, and compare-and-swap guard unchanged

## Summary

`write_plan` and `render_plan_text` in `plan_tool/parser.py` each stamp the current plan format declaration (`PLAN_FORMAT_VERSION`, imported from `plan_tool.schema`) into every plan they serialize, closing the gap `model_dump(exclude_defaults=True, exclude_none=True)` would otherwise leave: a field whose value equals its model default — which is exactly what `format_version` is on every ordinary current plan — is silently omitted from the dump. A small shared helper checks that the plan's effective `format_version` equals `PLAN_FORMAT_VERSION` and refuses to serialize otherwise. Step 1's parser assigns raw absence the explicit legacy value `1`, so after a future current-version bump a raw absent plan reaches this refusal just like a declared current-minus-one plan; direct post-construction mutation remains a second test seam. Both functions call the same helper at the same relative point — right after their existing `Plan.model_validate(dumped)` re-validation, before the enum-coerce-and-dump tail — so `write_plan`'s file read, `_split_frontmatter` call, and compare-and-swap hash comparison are untouched: this step's diff to that half of the function is zero lines. `PLAN_FORMAT.md` gains the field's schema entry, a field-semantics paragraph covering both the read-side gate (shipped by step 1) and this step's write-side contract, a new numbered validation rule for the gate's ordering guarantee, and the accepted one-way bootstrap note. On green, every eligible plan `write_plan` or `render_plan_text` touches — including the concept-sync publish path — carries an explicit `format_version: 1` line, while either an effective legacy plan or a hand-mutated ineligible plan refuses with a `ValidationError` naming both values instead of silently writing something stale or nothing at all.

## Table of Contents

- [Why](#why) — the elision gap this step closes and the writer-eligibility rule it adds ahead of it
- [Input](#input) — the step 1 contract this step depends on
- [Files (creates vs edits)](#files-creates-vs-edits) — every file this step touches
- [Implementation](#implementation) — the shared helper, its two call sites, and the `PLAN_FORMAT.md` additions
- [Tests](#tests) — the parser and concept-sync test cases this step adds
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan-level docs this step's design follows
- [Applicable guardrails](#applicable-guardrails) — which plan-level fences bind this step
- [Deferred](#deferred) — what later steps, and unrelated existing gaps, own instead

## Why

`write_plan` and `render_plan_text` both serialize via `plan.model_dump(exclude_defaults=True, exclude_none=True)` — a field is only written back when its value differs from the model's declared default. Step 1 gives `Plan.format_version` a default of `PLAN_FORMAT_VERSION`, which is also the *only* value a fresh or current plan will ever carry — so on every ordinary plan, the dump elides the field for the same reason it elides `complexity` or `detail` when unset. Step 1 alone therefore only teaches the tool to *read* a version; nothing on disk would ever declare one, because nothing stamps it. This is the plan's own named Risk: "A field added with a model default is elided by `write_plan` and produces plans that declare nothing, while every test that constructs a `Plan` in-process still passes" — the in-process tests pass because they check the parsed field, not the written bytes.

The writer also needs a rule the reader doesn't: a reader accepts current *and* current-minus-one, but a writer must emit current only — relabeling an older-but-still-supported plan as current on rewrite would silently discard the fact that it needs its explicit upgrade first. At version 1 this distinction has no live effect (the supported set and the current version are both `{1}`), but the check has to exist now, because the only way it could ever *not* exist by the time version 2 ships is if nobody adds it. A plan hand-mutated to an ineligible `format_version` is the one way to observe this today, and it's the same class of in-memory state `write_plan`'s existing re-validation guard was built to catch for other fields — except `Plan.model_validate` re-running pydantic's validators doesn't catch it here, because step 1 deliberately gives `format_version` no field-level validator (see step 1's `## Implementation`), so this step needs its own explicit check rather than relying on the re-validation that already runs.

## Input

This step reads two names step 1 (`docs/implementation-plans/plan-details/authored-artifact-format-version/01-accept-fixed-plan-format-version-field.md`) adds to `plan_tool/schema.py`:

- `Plan.format_version: int` — a plain, defaulted field (default `PLAN_FORMAT_VERSION`) with no field-level validator. Every `Plan` instance, however constructed, always carries a concrete `int` here. For disk input, step 1 injects raw absence as explicit legacy value `1` before model validation, rather than allowing a later model default to relabel that raw legacy input as current.
- `PLAN_FORMAT_VERSION` — the int constant naming the version this build currently writes and reads by default.

Step 1's parse-time gate in `plan_tool/parser.py:parse_plan_text` forecloses ever reading an unsupported *declared* `Plan.format_version` value from disk. The writer nevertheless has two ineligible inputs to defend: a direct post-construction attribute mutation (mirroring `TestRoundTrip::test_write_rejects_invalid_mutation`'s existing technique for a different field), and a raw absent plan parsed after a later current-version bump, whose effective version stays `1` by step 1's explicit parser injection.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/parser.py` — add `PLAN_FORMAT_VERSION` to the existing `from plan_tool.schema import Plan, Step` import; add a shared private helper that checks eligibility and injects the declaration; call it from `write_plan` and from `render_plan_text`; add one clarifying line to each function's docstring.
- `PLAN_FORMAT.md` — add `format_version` to the frontmatter schema block, add its field-semantics paragraph, add a numbered validation rule for the gate's ordering guarantee, and add one clause to the `### Defaults` section's closing paragraph.
- `tests/test_parser.py` — extend step 1's `TestFormatVersion` class with the write-side coverage below.
- `tests/test_concept_sync.py` — add one case proving the concept-sync publish path carries the declaration.

## Implementation

**1. Import the constant.**

Add `PLAN_FORMAT_VERSION` to the existing `from plan_tool.schema import Plan, Step` import.

**2. One shared helper, called from both serializers.**

Both `write_plan` and `render_plan_text` need the identical rule the plan's Architecture states: "Both serializers first require the plan's effective version to be current, then inject the current declaration into their serialized mapping after the model dump." Write it once:

```python
def _stamp_current_format_version(plan: Plan, dumped: dict[str, Any]) -> None:
    if plan.format_version != PLAN_FORMAT_VERSION:
        raise ValidationError(
            f"cannot serialize a plan with effective format_version="
            f"{plan.format_version!r}; this build writes only "
            f"format_version={PLAN_FORMAT_VERSION} — the plan needs its "
            f"explicit raw-format upgrade before it can be rewritten"
        )
    dumped["format_version"] = PLAN_FORMAT_VERSION
```

This is a starting point, not a mandate on exact wording or on mutating `dumped` in place versus returning a new one — what matters:

- **Reuse `ValidationError` itself; don't add a new subclass.** Both functions already raise plain `ValidationError` today for their existing re-validation failure. Every caller that tolerates or catches that already tolerates or catches this new refusal reason identically, with zero caller-side change — confirmed by grepping `write_plan`'s other call sites (`create.py`, `detail.py`, `cli/review_actions.py`, `cli/completeness_phases.py` all already catch `plan_tool.parser.ValidationError` generically near their calls; `scope_out.py`, `reground.py`, `launcher.py`, `cli/gates_cmd.py` don't, but that's true today, unrelated to this step). A dedicated subclass (paralleling step 1's `UnsupportedPlanFormatVersionError`) isn't wrong, but nothing here needs it, and it would be the first place this step outgrows "the smallest thing that satisfies the acceptance criteria."
- **Compare against `PLAN_FORMAT_VERSION`, not membership in `SUPPORTED_PLAN_FORMAT_VERSIONS`.** A writer emits current only, never a current-minus-one value a *reader* would still accept. At version 1 the two sets are identical, so this has no live effect yet — it's future-proofing — but checking against the supported set would silently do the wrong thing once version 2 ships.
- **The message names both the plan's actual value and the current version** — the same shape `UnsupportedPlanFormatVersionError`'s message already uses.

**3. Call it from `write_plan`.**

Insert the call right after the existing `Plan.model_validate(dumped)` try/except — that block, and everything above it (the file read, `_split_frontmatter`, the compare-and-swap hash comparison), stays exactly as it is today:

```python
dumped = plan.model_dump(exclude_defaults=True, exclude_none=True)
try:
    Plan.model_validate(dumped)
except PydanticValidationError as exc:
    raise ValidationError(str(exc), errors=exc.errors()) from exc
_stamp_current_format_version(plan, dumped)          # new
dumped = _coerce_enums(dumped)
```

An ineligible plan is rejected before `p.write_text(...)` runs later in the function, so a refused write leaves the on-disk file untouched — the same "no partial write" property the CAS guard already gives every other refusal path in this function, worth its own test. Checking eligibility even earlier — before the file read, as a pure fail-fast on the in-memory `plan` object — is an equally valid placement if the implementer prefers avoiding the wasted read/CAS-comparison on a plan that's going to be refused anyway; either placement leaves the CAS guard's own lines unedited.

**4. Call it from `render_plan_text`.**

Same relative position — right after its `Plan.model_validate(dumped)` try/except, before the `yaml.safe_dump` call:

```python
def render_plan_text(plan: Plan, body: str) -> str:
    dumped = plan.model_dump(exclude_defaults=True, exclude_none=True)
    try:
        Plan.model_validate(dumped)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc), errors=exc.errors()) from exc
    _stamp_current_format_version(plan, dumped)        # new
    new_fm = yaml.safe_dump(
        _coerce_enums(dumped), default_flow_style=False, sort_keys=False,
        allow_unicode=True,
    )
    return f"{_FENCE}\n{new_fm}{_FENCE}\n{body}"
```

**5. Key position in the rendered YAML is cosmetic, but worth getting right.** A plain `dumped["format_version"] = PLAN_FORMAT_VERSION` assignment appends the key at the *end* of the mapping (it was never present in `dumped` on the eligible path — `exclude_defaults=True` elided it, which is the whole problem this step fixes), so `yaml.safe_dump(..., sort_keys=False)` would render `format_version:` as the last top-level key, after `steps:`. One way to put it first instead, where a version declaration reads naturally: build the stamped mapping as `{"format_version": PLAN_FORMAT_VERSION, **dumped}` rather than a trailing assignment. Position has no parsing consequence — `parse_plan_text` reads frontmatter through `yaml.safe_load` into a plain mapping, so key order round-trips identically either way — this is purely for a human skimming the file.

**6. Docstrings.** `write_plan`'s docstring states "Fields unset in the model (defaults) are elided…" — add one line naming `format_version` as the deliberate exception (always stamped explicitly, never left to elision, because eliding it is exactly the bug this step closes). Give `render_plan_text`'s one-line docstring the same one-clause addition.

**7. `PLAN_FORMAT.md`.** Step 1 didn't touch this file — the whole `format_version` doc surface belongs to this step. Add:

- A `format_version: int` entry to the `## Frontmatter schema` code block, positioned first (before `title`), with an inline comment stating the default and refusal — matching the block's existing per-field inline-comment style.
- A `**`format_version`**` paragraph in `### Field semantics`, covering: the carrier (top-level plan frontmatter key), raw-absent-means-legacy-version-1 (which coincides with current at version 1), `UnsupportedPlanFormatVersionError` on an unsupported *declared* value (step 1's gate, already shipped by the time this step's code runs), and this step's writer contract — `write_plan`/`render_plan_text` always stamp the current version and refuse to serialize a plan whose effective version isn't current.
- One sentence in that paragraph recording the accepted one-way bootstrap result: a plan this build writes is not parseable by a plan-tool build that predates `format_version`, because that older `Plan` model has no such field and rejects unknown keys — point at the doc's own rule 8 for why.
- A new item in `### Validation rules`'s numbered list (currently 1–9) naming the version gate and its ordering guarantee ahead of rule 8 — the exact trap the plan's Testing section calls out ("a plan carrying an unknown key and an unsupported version is refused for the version, not the key").
- One clause on the `### Defaults` section's closing paragraph: `format_version` is optional in raw frontmatter, but the parser assigns a missing key legacy version `1` before model validation rather than borrowing a later current-version model default; version 1 is current in this release, unlike every other field that paragraph lists.

Don't touch `## Example`, `## Smell checks (advisory)`, or the canonical-step-layout sections — none describe frontmatter fields, and `format_version` doesn't participate in any of them.

**8. Blast radius beyond this step's two code files.** `write_plan` has roughly a dozen other callers (`create.py`, `scope_out.py`, `reground.py`, `launcher.py`, `detail.py`, `cli/gates_cmd.py`, `cli/review_actions.py`, `cli/completeness_phases.py`) whose contract with `write_plan` doesn't change — they still get back whatever `write_plan` serializes; only the bytes change. A repo-wide grep for a test asserting *exact* frontmatter text (rather than a parsed field) after `write_plan`/`render_plan_text` found none outside `tests/test_parser.py` and `tests/test_concept_sync.py` at HEAD. The plan's own `test_command: uv run pytest tests/ -q -n auto` is the backstop if that grep missed something — run the full suite, not only this step's two declared test files, before calling the step done.

## Tests

`tests/test_parser.py` — extend step 1's `TestFormatVersion` class (styled like the existing `TestRiskProfile`, which already mixes parse-time and round-trip cases for one field in one class, rather than splitting into a second class):

- `test_absent_format_version_round_trips_through_write_plan` — a plan with no `format_version` key, parsed then `write_plan`'d; reparsing shows `format_version == PLAN_FORMAT_VERSION`, and the on-disk text now contains an explicit `format_version:` line where none existed before — pins the exact case the plan's Risks section warns would otherwise silently keep declaring nothing.
- `test_raw_absent_plan_refuses_serialization_after_a_future_current_version_bump` — temporarily advance the relevant current-version/support-window constants in the parser fixture, parse raw frontmatter with no `format_version`, and assert the effective value remains `1` and both serializers refuse until the raw upgrader runs. This is the regression test that prevents the `Plan` field default from silently relabeling raw absence as future current.
- `test_declared_current_format_version_round_trips_through_write_plan` — same, starting from a plan that already declares `format_version: 1`.
- `test_write_plan_stamps_the_current_declaration_in_rendered_text` — asserts the literal written frontmatter contains `format_version: {PLAN_FORMAT_VERSION}`, mirroring `test_explicit_risk_profile_renders_and_reloads`'s substring-assertion style.
- `test_render_plan_text_stamps_the_current_declaration` — same assertion directly against `render_plan_text`'s return value, no file I/O.
- `test_write_plan_refuses_a_hand_mutated_ineligible_format_version` — parse a plan, then `plan.format_version = 0` by raw attribute assignment — a second in-memory refusal seam alongside raw legacy absence — mirrors `test_write_rejects_invalid_mutation`'s exact technique for a different field; asserts `pytest.raises(ValidationError)` with a message naming both `0` and `PLAN_FORMAT_VERSION`.
- `test_write_plan_refusal_leaves_the_file_on_disk_untouched` — same setup; asserts `target.read_text()` is unchanged after the raise, proving the refusal fires before any write rather than mid-write.
- `test_render_plan_text_refuses_a_hand_mutated_ineligible_format_version` — the same mutation fed directly to `render_plan_text`; asserts the same `ValidationError`, with no filesystem involved.
- `test_stamped_plan_is_rejected_by_a_pre_declaration_strict_fixture` — the plan's Testing section names this explicitly: define a minimal local pydantic model in the test (`extra="forbid"`, no `format_version` field, just enough required fields to construct), feed it the `yaml.safe_load`-parsed frontmatter mapping `write_plan` just wrote, and assert it raises pydantic's own validation error naming `format_version` as the unrecognized field — proves the one-way bootstrap result rather than asserting and hoping.

`tests/test_concept_sync.py` — one new case, styled like the existing `test_sync_renders_decisions_preserves_markdown_and_maps_steps`:

- `test_synchronized_plan_carries_the_current_format_version_declaration` — run the file's existing `_write_plan` / `_tree` / `_persist_tree` fixture setup through `synchronize_concepts`; on `SyncStatus.SUCCESS`, reparse the published plan and assert `format_version == PLAN_FORMAT_VERSION`, proving the declaration survives `render_plan_text`'s concept-sync publish path — the one other in-repo caller this step's Architecture names by name.

### Tests for this step

The eight `tests/test_parser.py` cases plus the one `tests/test_concept_sync.py` case above (nine total) must all be green before this step is done. They cover exactly the behavior this step changes — the shared eligibility check, its refusal message, the injection into both serializers' output, and the one other in-repo caller that exercises `render_plan_text` — and deliberately leave the parse-time gate's own coverage (already green from step 1) and the detail-file marker (step 3/4's artifact class) untouched.

## Acceptance criteria

- `write_plan` and `render_plan_text` each write an explicit `format_version: <PLAN_FORMAT_VERSION>` line into every plan whose effective format version is current — including a raw absent plan while version 1 is current.
- `write_plan`'s file-read, `_split_frontmatter` call, and compare-and-swap frontmatter-hash comparison are unchanged: same lines, same order, same `ConcurrentModificationError` behavior on a concurrent edit.
- `write_plan`'s prose-body preservation is unchanged: `tests/test_parser.py::TestRoundTrip::test_body_preserved_byte_for_byte` and its siblings keep passing unmodified.
- A `Plan` whose effective `format_version` differs from `PLAN_FORMAT_VERSION` — by direct attribute assignment or by parsing raw absence after a future current-version bump — raises `plan_tool.parser.ValidationError` from both `write_plan` and `render_plan_text`, naming the plan's actual value and the current version; `write_plan` writes no file in that case.
- The first future release that makes a previously supported live on-disk plan or detail representation reach a reader or writer refusal ships an operator route for the affected class and adds a shared compatibility preflight at every affected mutating command boundary before its first step-status, lesson, seed, archive, or plan mutation; it does not rely on a late serializer refusal after partial work. That release tests upgrade-then-rerun without partial state.
- The concept-sync publish path (`concept_sync.py:synchronize_concepts` → `render_plan_text`) produces plan text that, reparsed, carries `format_version == PLAN_FORMAT_VERSION` on success.
- `PLAN_FORMAT.md` documents the `format_version` frontmatter field (schema block entry, field-semantics paragraph, defaults note), the writer-side refusal contract, the parse-time gate's ordering guarantee ahead of the unknown-field rule, and the accepted one-way bootstrap result.
- The full suite (`uv run pytest tests/ -q -n auto`, the plan's own `test_command`) passes, not only the two test files this step declares — the writer-behavior change is observable from every existing `write_plan`/`render_plan_text` caller in the repo.

## References

- `DATA_CONTRACT.md` § "Version-evolution policy" — the fail-closed policy this step's writer refusal follows for the plan class: refuse rather than relabel an ineligible version as current.
- `PLAN_FORMAT.md` § "Validation rules" — rule 8, the unknown-field rejection this step's new validation-rule item is ordered against.
- `plan_tool/parser.py:write_plan`, `plan_tool/parser.py:render_plan_text`, `plan_tool/schema.py:208` (`Plan`'s `extra="forbid"` config) — the seams this step's helper sits next to, and the mechanism behind the one-way bootstrap result.

## Applicable guardrails

- **The plan's "## Scope guardrails," binary-observable rule.** This step's writer check asserts exactly one thing — the plan's in-memory `format_version` equals the version this build currently writes — and nothing about the rest of the plan's content. It must not grow into a check of whether the plan's other fields or body match what that version implies.
- **The plan's "## Scope guardrails," not-allowed list.** Two of its five items bind a writer as much as a reader and apply directly here: no advisory or warning for an *eligible* (current) version — this step's check is silent on the ordinary path — and no inferring, repairing, or upgrading a version as a side effect of serializing — an ineligible plan is refused outright, never silently relabeled as current or rewritten around. The remaining three items (the run-grade-body fallback, content-conformance checking, and emitting a finding/advisory for a supported version) describe the detail-reader class this step doesn't touch and impose no additional constraint here.

## Deferred

- `plan_tool/concept_sync.py`'s exception handling around its `render_plan_text` call — `synchronize_concepts`'s `except (InvalidConceptTreeError, ValueError, TypeError)` doesn't catch `plan_tool.parser.ValidationError` and never has: `render_plan_text` already raises that type today for its pre-existing `Plan.model_validate` re-validation failure, unrelated to this step. This step's refusal reuses the same exception type, so it neither creates nor worsens the gap, and `plan_tool/concept_sync.py` isn't in this step's `files:` — named here so it isn't mistaken for a regression later.
- Whether `write_plan`'s other callers outside `concept_sync.py` (`create.py`, `scope_out.py`, `reground.py`, `launcher.py`, `detail.py`, `cli/gates_cmd.py`, `cli/review_actions.py`, `cli/completeness_phases.py`) need dedicated handling for this refusal — none are in this step's `files:`, and the refusal reuses `write_plan`'s existing `ValidationError` type, so each caller's existing tolerance (or lack of it) for that type is unchanged in kind by this step.
- An explicit CLI-facing diagnosis/recovery message for refusal of a previously supported live representation, the way step 3's Architecture describes a typed `plan_tool/cli/app.py` handler for `DetailFormatError` — version 1 has no such route because it newly refuses no previously supported representation. The first release that makes one reachable must ship the affected class's operator-invocable raw-upgrade route in the same bump.
- The future mutating-command preflight this refusal requires — no version-1 command can encounter the refusal from parsed disk input, so this step neither changes current command ordering nor names a shared helper. The version that makes refusal reachable owns the preflight and tests it before its first mutation.
- The explicit raw-artifact upgrade entry point — step 6, which the plan's `depends_on` graph places after this step. Version 1 exposes it as a library API; no error message implies an already-available operator command.
- `DATA_CONTRACT.md`'s class-specific version-evolution entry for the plan format constants — step 5.
- `DETAIL_FORMAT.md` and the detail body marker — step 3/4's artifact class, untouched by this step.
