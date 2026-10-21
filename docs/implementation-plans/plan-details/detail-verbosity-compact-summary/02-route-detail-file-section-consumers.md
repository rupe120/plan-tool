# Step 2 — Route detail-file section reads through step 1's alias table so compact headings read like legacy ones

## Summary

Teach `plan_tool/detail.py:parse_detail_file_sections` to fold the compact section aliases from step 1 (`intent`, `footprint`, `approach`, `done`) onto their legacy canonical keys (`summary`, `files`, `implementation`, `acceptance`) as it builds the `{token: body}` map. Because that parser is the single function every detail-file section reader already calls — `parse_acceptance_bullets` and two other reads in `detail.py`, plus `review.py`, `launcher.py`, and `bench.py` downstream — folding the aliases there reroutes all of them at once with no edits outside `detail.py`. The one code file touched is `plan_tool/detail.py`; tests land in `tests/test_detail.py`. This is behavior-preserving for every detail file on disk today (compact headings don't exist until step 3 emits them), so on green a legacy file parses byte-for-byte as before, and a `## Done when` / `## Intent` / `## Footprint` / `## Approach` file resolves under its legacy key.

## Table of Contents

- [Summary](#summary) — what the step ships and the observable result
- [Why](#why) — why route reads at the parser instead of per consumer
- [Input](#input) — the alias table step 1 owns and the section-token contract this reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the one code file and its test file
- [Implementation](#implementation) — fold aliases into the shared parser, reuse step 1's constant
- [Tests](#tests) — characterization-first, then the alias reads
- [Acceptance criteria](#acceptance-criteria) — CI-checkable behaviors
- [References](#references) — pytest docs for the added tests
- [Deferred](#deferred) — the write-side gate and non-aliased tokens left to later steps

## Why

Step 1 shipped the read-only summary cards and introduced the dual-token alias table, but its first-non-empty lookup lives only inside the card renderer (`plan_tool/detail.py:render_detail_summary`). Every other reader of a detail file's sections still asks for the legacy token only — `parse_acceptance_bullets` does `sections.get("acceptance")`, the launcher's deep verifier calls that, and `review.py`/`bench.py` read `sections.get("summary")` and friends. Once step 3 renames headings to the compact schema, all of those reads silently return empty on a compact file. This step closes that gap the cheap way: it teaches the one parser they all funnel through to speak both vocabularies, so no consumer needs a per-call edit and the alias vocabulary stays single-sourced in step 1's constant.

## Input

- **Step 1 owns the alias table.** Step 1 introduces a single named alias/pair constant in `plan_tool/detail.py` pairing each legacy token with its compact alias (`summary`|`intent`, `files`|`footprint`, `implementation`|`approach`, `acceptance`|`done`) and carries all four pairs even though its card displays a subset. This step consumes that constant; it must not fork a second copy. Cite it by name from HEAD when implementing — do not re-declare the pairs.
- **Section tokens are the lowercased first word of each `## ` heading.** `plan_tool/detail.py:_H2_HEADING_RE` (`^##\s+([A-Za-z]+)`) captures only the first word, so `## Done when` → `done`, `## Acceptance criteria` → `acceptance`, `## Footprint` → `footprint`. This first-word tokenization is exactly what makes a compact→legacy fold possible without a schema change.
- **`_REQUIRED_H2_TOKENS` stays the fixed seven** (`summary, table, why, files, implementation, tests, acceptance`). This step does not change the required set or the write-side gate that checks it (see Deferred).
- **Compact and legacy headings are mutually exclusive per file.** A real detail file is one schema or the other; none of the four compact aliases collides with any of the seven legacy tokens, so folding is unambiguous.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — in `parse_detail_file_sections`, after computing each heading's first-word `token`, map a compact alias to its legacy canonical key (derived from step 1's alias constant) before storing the body. Update the function's docstring to state that compact aliases resolve to their legacy key. No new public symbol required.
  - `tests/test_detail.py` — add characterization tests pinning today's legacy behavior, then tests for compact-alias resolution through `parse_detail_file_sections` and `parse_acceptance_bullets`.

## Implementation

- **Fold the aliases at the parser, not at each consumer.** The key decision: edit `plan_tool/detail.py:parse_detail_file_sections` so a compact-alias heading is stored under its legacy canonical key. Every reader — `parse_acceptance_bullets`, the launcher deep verifier that calls it, `review.py`, `bench.py` — already routes through this one function, so the single edit reroutes all of them and keeps this step inside its declared `files:` list. The rejected alternative is a per-consumer resolver (edit each `sections.get(...)` call site or add a `resolve_section` helper each reader must adopt): it needs edits in `review.py`/`bench.py` (out of this step's scope) to reach downstream readers and invites the alias logic to drift across sites. Route at the choke point instead.
- **Derive the alias→canonical direction from step 1's pair table; don't hand-write a second map.** Step 1's constant is pair-shaped (legacy paired with its alias). Invert it once to get `{compact_alias: legacy_token}` for the fold. One way: build the inverse dict from the same constant at module load. This keeps the vocabulary single-sourced, which is the whole point of step 1 carrying the unused pairs.
- **Preserve the parser's other guarantees.** Body slicing (from the line after the heading up to the next H2/H1/EOF, whitespace trimmed), optional-section retention (Input, References, Deferred still appear under their own tokens), and empty-input handling must stay exactly as they are. Only the key a compact heading lands under changes.
- **Handle the both-present edge deterministically even though real files won't hit it.** If a single file somehow carries both a legacy heading and its compact alias, prefer the legacy canonical content (first-non-empty, legacy wins) rather than letting dict-iteration order decide. Note this in a one-line comment; it is a guard, not an expected input.
- **Leave `parse_acceptance_bullets` untouched.** It calls `parse_detail_file_sections` then reads `sections.get("acceptance")`; once the parser folds `done` → `acceptance`, a `## Done when` file flows through it — and through the launcher deep verifier at `plan_tool/launcher.py` that calls it — with no edit to either. State this so a reviewer doesn't expect a second diff there.
- **Constraints that are not free to vary:**
  - The fold must be a no-op on legacy files. A file with only legacy headings must produce the identical `{token: body}` dict it produces today. This is the behavior-preserving invariant the characterization tests pin.
  - Do not change `_REQUIRED_H2_TOKENS`, `_H2_HEADING_RE`, or `parse_detail_response`'s required-section gate (it validates raw headings with its own regex, not this parser). Those belong to the schema/write change in a later step.
  - Non-aliased tokens (`tests`, `why`, `table`, `deferred`, `references`) pass through unchanged — step 1's table gives them no alias, so the two other `detail.py` reads (`sections.get("tests")` in the refactor-tests-after check, and the `.get("deferred")` read in the structured-deferral gate) are unaffected and need no edit.

## Tests

### Test-creation order (refactor step)

This is a behavior-preserving refactor for every file that exists today. Write the characterization tests **first**, confirm they pass against HEAD before touching `parse_detail_file_sections`, and keep them green **unchanged** after the fold. New-behavior tests are added after and only exercise compact inputs that don't exist on disk yet.

Characterization tests (write first; pin current behavior; must stay green unmodified):
- `test_legacy_seven_section_file_keys_unchanged` — a full legacy detail body yields exactly the seven legacy tokens with correct bodies; no extra keys.
- `test_legacy_acceptance_bullets_unchanged` — `parse_acceptance_bullets` on a `## Acceptance criteria` body returns the same bullet list as today.
- `test_optional_sections_still_retained` — Input/References/Deferred headings still appear under their own tokens.
- `test_empty_and_bodyless_headings_unchanged` — empty input returns `{}`; a heading at EOF with no body returns `""` (pins existing slicing).

New-behavior tests (add after the fold):
- `test_done_when_resolves_to_acceptance` — a body whose only acceptance-style heading is `## Done when` populates `sections["acceptance"]`.
- `test_done_when_flows_through_acceptance_bullets` — `parse_acceptance_bullets` on that same `## Done when` body returns its bullets.
- `test_intent_resolves_to_summary` — `## Intent` populates `sections["summary"]`.
- `test_footprint_resolves_to_files` — `## Footprint` populates `sections["files"]`.
- `test_approach_resolves_to_implementation` — `## Approach` populates `sections["implementation"]`.
- `test_non_aliased_tokens_pass_through` — `## Tests` stays keyed `tests`; a compact file's non-aliased headings are unchanged.
- `test_legacy_wins_when_both_headings_present` — a body with both `## Acceptance criteria` and `## Done when` resolves `acceptance` to the legacy heading's body.
- `test_alias_map_derived_from_step1_constant` — the compact→legacy mapping is built from step 1's alias table (guards against a forked copy drifting).

All live in `tests/test_detail.py` (add a class such as `TestParseDetailFileSectionsAliases`); they are pure, hermetic, and spawn no Claude.

## Acceptance criteria

- `parse_detail_file_sections` on a legacy seven-section body returns a dict with exactly the seven legacy tokens and their original bodies — byte-for-byte the pre-change output.
- `parse_detail_file_sections` on a body whose acceptance heading is `## Done when` returns a populated `sections["acceptance"]`.
- `parse_acceptance_bullets` returns the expected bullets for both a `## Acceptance criteria` body and a `## Done when` body.
- `## Intent` → `sections["summary"]`, `## Footprint` → `sections["files"]`, `## Approach` → `sections["implementation"]` all resolve.
- A body with both a legacy heading and its compact alias resolves the legacy content.
- The compact→legacy map is derived from step 1's alias constant, not a second literal in `parse_detail_file_sections`.
- The new and existing `tests/test_detail.py` cases pass under `uv run pytest tests/test_detail.py -q` with no Claude spawned.

## References

- [Fixtures reference — pytest documentationhttps: — reference for the `tmp_path`/parametrization used by the added parser tests.
- [How to use temporary directories and files in tests — pytest documentationhttps: — guidance for the hermetic detail-body fixtures.

## Deferred

- Renaming the emitted detail schema to the compact headings — step 3 owns emitting `## Intent`/`## Footprint`/`## Approach`/`## Done when`; this step only makes readers understand them.
- The write-side required-section gate — `plan_tool/detail.py:parse_detail_response` validates the seven required headings with its own `_H2_HEADING_RE` scan (not `parse_detail_file_sections`), so a compact file would still fail it. Loosening that gate to accept compact headings belongs with the schema change (step 3+), not here.
- Non-aliased sections (`tests`, `why`, `table`, `references`, `deferred`) — step 1's table gives them no compact alias, so they are out of scope for this reroute.
- Editing `review.py` / `bench.py` reads directly — unnecessary: they call `parse_detail_file_sections`, so the parser-level fold already reroutes them without an in-file edit.
