# Step 3 — Make the compact Intent/Footprint/Approach/Done-when set the required detail schema and rewrite the authoring + quality prompts

## Summary

Flip `plan-tool detail`'s write contract from the legacy seven required H2s to the compact four — `## Intent`, `## Footprint`, `## Approach`, `## Done when` — and rewrite the two prompt templates that drive and grade authoring. The required-set rule lives in **two** modules at two read layers: `plan_tool/detail.py:_REQUIRED_H2_TOKENS` (the write gate in `parse_detail_response`, which reads raw headings) and `plan_tool/review.py:_REQUIRED_DETAIL_SECTION_NAMES` (the completeness/reconcile gate, which reads step-2-folded sections). Both change together — the write gate to the raw compact tokens, the completeness gate to the four folded legacy keys — so new files author compact while legacy seven-section files still pass every read audit. The key design decision is that the two constants stay separate token lists on purpose because they read at different layers (raw vs folded). On green: `render_detail_prompt` emits the compact structure, `parse_detail_response` accepts a compact body and rejects one missing 2+ compact sections, and `check_detail_body_completeness` passes both a compact and a legacy detail file.

## Table of Contents

- [Summary](#summary) — what the step ships and the observable result
- [Why](#why) — the structural verbosity this step removes
- [Input](#input) — the step 1 alias constant and step 2 fold this depends on
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files plus the required `review.py` addition
- [Implementation](#implementation) — the two required-set constants, the prompt rewrites, and the token-fold gotchas
- [Tests](#tests) — unit tests for the gate, the prompt shape, and legacy compatibility
- [Acceptance criteria](#acceptance-criteria) — CI-checkable behaviors
- [References](#references) — pytest docs for the added tests
- [Deferred](#deferred) — the complexity gate, sibling hygiene, docs, and constant consolidation left to later steps

## Why

`_REQUIRED_H2_TOKENS` in `plan_tool/detail.py` hard-requires seven sections, so even a one-line change authors ~70 lines and a dense step lands at 120–170. Table of Contents is ceremony on a short file, `## Why` retells `## Summary`, and `## Tests` is a separate H2 for what is really part of "done when." Steps 1 and 2 already made every detail-file **reader** speak both vocabularies (dual-token cards, then a compact→legacy fold in the shared parser), but the **write** side still forces seven sections and the prompts still teach them. This step is the pivot: change what `detail` requires and what the prompts ask for, so new files come out compact by default while nothing on disk is force-migrated.

## Input

This step depends on two upstream outcomes; cite them, don't re-specify them:

- **Step 1 produces the compact↔legacy alias constant** in `plan_tool/detail.py` — the single named pair table (`summary`|`intent`, `files`|`footprint`, `implementation`|`approach`, `acceptance`|`done`). This step does not re-declare it.
- **Step 2 folds those aliases in `parse_detail_file_sections`** so a `## Intent` heading resolves under the legacy `summary` key, `## Footprint`→`files`, `## Approach`→`implementation`, `## Done when`→`acceptance`. This fold is what lets `review.py`'s completeness gate keep checking legacy keys and still pass a compact file. **Correctness of this step's `review.py` change rests on that fold already being in place** (`depends_on: 2`).

Verify at authoring/implementation time that step 2 actually landed the fold in `parse_detail_file_sections` before relying on it — the write gate (`parse_detail_response`) reads **raw** headings and does not go through that fold, so the two gates are not symmetric (see Implementation).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only), declared:**
  - `plan_tool/detail.py` — retarget `_REQUIRED_H2_TOKENS` and `_REQUIRED_H2_DISPLAY` to the compact tokens; update the `parse_detail_response` and `parse_detail_file_sections` docstrings; make the refactor-tests-after lint read the Done-when body too; relocate the test-order directive block under Done when (docstring + placement).
  - `plan_tool/prompts/detail.md` — rewrite the "What to produce" required structure to the compact four, drop ToC/Why/Tests as required H2s, move the change-type test-order block under Done when, add the length caps in words.
  - `plan_tool/prompts/detail-quality.md` — retarget the grounding checks (over-prescription, Intent splitting back into a Why, Approach over caps) and change the `## Tests`-contradicts-change-type check to `## Done when`.
  - `DETAIL_FORMAT.md` — document the compact required set and that legacy files stay valid on read.
  - `docs/how-to/pipeline/detail.md` — update the "Required H2s" line to the compact set.
  - `tests/test_detail.py` — update seven-section fixtures to compact; add the gate/prompt/legacy tests.
- **Existing files (edits only), additions to the declared list — noted per the constraints, genuinely required:**
  - `plan_tool/review.py` — the required-detail-H2 rule is a **second copy** here (`_REQUIRED_DETAIL_SECTION_NAMES` + `check_detail_body_completeness`). Without this edit, completeness/reconcile flags every compact file as missing `table`/`why`/`tests`. This is a same-step requirement, **not** deferrable (deferring it ships the compact contract broken).
  - `tests/test_review.py` — cover the `review.py` change (mirror-module convention).
  - `tests/test_bench.py` — **likely** a fixture ripple only: `bench.py` imports `_REQUIRED_DETAIL_SECTION_NAMES` and divides by its length, so shrinking the constant from 7 to 4 changes the `required_h2` ratio; any test asserting a fixed ratio needs the new denominator. `plan_tool/bench.py` itself needs no source edit.

## Implementation

The behavior change is: `detail` requires and the prompts teach the compact schema; every read path keeps accepting legacy. Grounded specifics:

- **Retarget the write-gate constant.** `plan_tool/detail.py:_REQUIRED_H2_TOKENS` becomes the raw compact tokens `("intent", "footprint", "approach", "done")`. The write gate in `parse_detail_response` builds its `headings` set from `_H2_HEADING_RE.finditer` over the model's **raw** output (first word, lowercased), so it needs the raw compact tokens — `## Done when` tokenizes to `done`. Keep the existing leniency unchanged: exactly one missing token synthesizes a stub, two or more still returns `None`.

- **Keep `_REQUIRED_H2_DISPLAY` in lockstep.** Every token in `_REQUIRED_H2_TOKENS` must be a key in `_REQUIRED_H2_DISPLAY` (`intent`→`Intent`, `footprint`→`Footprint`, `approach`→`Approach`, `done`→`Done when`), because the one-missing-section path does `_REQUIRED_H2_DISPLAY[missing[0]]` and will `KeyError` on any token without a display entry. This pairing is the invariant that is not free to vary.

- **Retarget the completeness-gate constant at the folded layer.** `plan_tool/review.py:_REQUIRED_DETAIL_SECTION_NAMES` reads sections through `parse_detail_file_sections`, which step 2 **folds** compact→legacy. So this constant stays in the **legacy** vocabulary — drop the three sections the compact schema removes and keep the four canonical keys both schemas share after folding: `("summary","Summary")`, `("files","Files")`, `("implementation","Implementation")`, `("acceptance","Acceptance criteria")`. A compact file passes (folded keys present); a legacy file passes (it has those keys plus the now-optional table/why/tests). Update `check_detail_body_completeness`'s docstring: it no longer verifies "seven non-empty H2s."

- **The two constants are deliberately different token lists — do not unify them.** The write gate reads **raw** tokens (`intent`/`footprint`/`approach`/`done`); the completeness gate reads **folded** tokens (`summary`/`files`/`implementation`/`acceptance`). They encode the same contract at two layers. The main alternative — routing `parse_detail_response` through the folded `parse_detail_file_sections` so both gates share one list — is rejected here: the write gate must inspect the model's raw headings to drive `_REQUIRED_H2_DISPLAY` stub synthesis before anything is folded or written, and folding pre-write would hide which heading the model actually emitted. State this asymmetry in a comment next to each constant so a future reader doesn't "fix" the drift.

- **Write path is compact-only; read path stays dual.** After this step a model that emits the seven legacy headings fails the write gate (the compact tokens are absent) — that is intended, and the rewritten `detail.md` only ever asks for compact. Legacy files already on disk are never rewritten and still pass every reader.

- **Keep the refactor-tests-after lint working on compact files.** The lint in `plan_tool/detail.py` (the `sections.get("tests", "")` read guarded on `change_type == REFACTOR`, near `_REFACTOR_TESTS_AFTER_PHRASES`) currently reads only the `tests` token. Compact refactor steps put their tests under `## Done when`, so read both: one way is `sections.get("tests") or sections.get("acceptance")` (step 2's fold maps `done`→`acceptance`), so the lint fires on a legacy `## Tests` and on a compact `## Done when`.

- **Relocate the test-order directive under Done when.** `_format_tests_order_directive` (single wording source for both prompts) emits a `### Test-creation order` sub-heading — a `### `, not an H2, so it does not touch the token gate. In `detail.md`, move the `${change_type_directive_block}` placement from the Tests guidance into the Done-when guidance, and update the builder's docstring reasoning from "within `## Tests` … `parse_detail_file_sections(...).get("tests")`" to the Done-when section. `render_detail_prompt` and `render_detail_quality_prompt` keep feeding the same block from `_format_tests_order_directive`, so the author-vs-reviewer anti-drift contract holds.

- **Rewrite `detail.md`'s required structure** to: `## Intent` (2–4 sentences merging today's Summary + Why — what changes, why it matters, the main design choice), `## Footprint` (Creates/Edits, one line per file naming the symbol or change), `## Approach` (≤8 bullets — invariants, real anchors, constraints/gotchas, load-bearing rejected alternatives; no call-site inventories unless the inventory *is* the constraint), `## Done when` (CI-checkable acceptance bullets plus representative `Tests:` lines). Keep `## Input`, `## References`, `## Deferred` optional with unchanged semantics; keep the deferral envelope, the "codebase audit first" block, and the "intent over mechanics" stance. State the caps as words (Intent ≤4 sentences, Approach ≤8 bullets) — but the complexity-conditional **enforcement** of those caps is step 4's job (see Deferred), so do not add complexity branching here.

- **Rewrite `detail-quality.md`'s checks** to grade the compact shape: flag over-prescription, an `## Intent` that splits back into a separate Why, and an `## Approach` that runs past the caps; keep "an open *how* is fine." Change the "`## Tests` section that contradicts the step's declared type" check to target `## Done when` (that is where the test-creation directive now lands).

- **Docs.** In `DETAIL_FORMAT.md`, replace the "Required H2s (seven)" block with the compact required four and a note that legacy seven-section files stay valid on read via the step-1/2 dual-token fold. In `docs/how-to/pipeline/detail.md`, update the "Required H2s (`_REQUIRED_H2_TOKENS`): Summary, Table of Contents, …" line to the compact set.

## Tests

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add these unit tests **with** the implementation; every one must be green before the step is done, and update the existing seven-section fixtures in `tests/test_detail.py` to compact in the same change.

In `tests/test_detail.py`:
- `test_required_tokens_are_compact` — `_REQUIRED_H2_TOKENS == ("intent","footprint","approach","done")`.
- `test_display_covers_every_required_token` — every token in `_REQUIRED_H2_TOKENS` is a key in `_REQUIRED_H2_DISPLAY` (guards the stub-synthesis `KeyError`).
- `test_parse_detail_response_accepts_compact` — a body with the four compact H2s parses and returns non-`None`.
- `test_parse_detail_response_stubs_one_missing` — a body missing exactly one compact section returns a body with a synthesized stub under that section's display name.
- `test_parse_detail_response_rejects_two_missing` — a body missing two compact sections returns `None`.
- `test_parse_detail_response_rejects_legacy_headings` — a legacy seven-section body (no compact tokens) returns `None`, pinning the compact-only write path.
- `test_refactor_tests_after_fires_on_compact` — a refactor-step compact body whose `## Done when` Tests lines describe after-the-change testing produces the refactor-tests-after finding.
- `test_render_detail_prompt_compact_structure` — the rendered `detail.md` prompt names `## Intent`/`## Footprint`/`## Approach`/`## Done when`, does not require `## Table of Contents`/`## Why`/`## Tests`, and places the `### Test-creation order` block under Done when.

In `tests/test_review.py`:
- `test_completeness_passes_compact_detail` — `check_detail_body_completeness` reports no missing-section issue for a compact detail file.
- `test_completeness_passes_legacy_detail` — same for a legacy seven-section file.
- `test_required_detail_section_names_drop_toc_why_tests` — `_REQUIRED_DETAIL_SECTION_NAMES` no longer contains `table`, `why`, or `tests`.

In `tests/test_bench.py`: update any fixture asserting a fixed `required_h2` ratio to the new 4-section denominator.

## Acceptance criteria

- `plan_tool.detail._REQUIRED_H2_TOKENS == ("intent","footprint","approach","done")`, and every token is a key in `_REQUIRED_H2_DISPLAY`.
- `parse_detail_response` returns a non-`None` body for a compact Intent/Footprint/Approach/Done-when input, synthesizes a stub for exactly one missing compact section, and returns `None` for two-or-more missing.
- `parse_detail_response` returns `None` for a legacy seven-section body that has none of the compact tokens.
- `review.check_detail_body_completeness` reports no missing-section issue for a compact file **and** none for a legacy seven-section file; `_REQUIRED_DETAIL_SECTION_NAMES` contains exactly `summary`, `files`, `implementation`, `acceptance`.
- The refactor-tests-after lint fires on a compact refactor detail whose `## Done when` Tests lines describe after-the-change testing.
- `render_detail_prompt` output contains `## Intent`, `## Footprint`, `## Approach`, `## Done when`, and does not require `## Table of Contents`, `## Why`, or `## Tests`; the change-type test-order block renders under Done when.
- The `detail-quality.md` prompt references `## Done when` for the change-type contradiction check and no longer references a required `## Tests` H2.
- `grep -n "seven" DETAIL_FORMAT.md docs/how-to/pipeline/detail.md` returns no stale "seven required / seven-section" claim about the authoring contract.
- `uv run pytest tests/test_detail.py tests/test_review.py tests/test_bench.py -q` is green.

## References

- [How to use temporary directories and files in tests — pytest documentationhttps: — `tmp_path` for the hermetic gate/completeness unit tests.
- [Fixtures reference — pytest documentationhttps: — fixtures/markers for the added unit tests.

## Deferred

- Complexity gate (low-complexity steps stay compact-only; medium/high may expand only the Approach) — step 4 owns it (`depends_on: 3`). This step states the caps in prompt wording but adds no complexity branching.
- Sibling prompt hygiene (prefer compact siblings; strip/truncate ToC/Why from legacy siblings fed into the authoring prompt) — step 5 owns it.
- Docs and backlog bookkeeping beyond `DETAIL_FORMAT.md`/`DETAIL_FLOW.md` — CAPABILITIES.md, USE_CASES.md, RUNBOOK.md, and BACKLOG #149/#49 — step 6 owns it.
- Consolidating the two required-set constants (`detail._REQUIRED_H2_TOKENS` raw + `review._REQUIRED_DETAIL_SECTION_NAMES` folded) into one alias-table-derived source — a later cleanup; the plan keeps the legacy read mapping "until a later cleanup." Route to reconcile/backlog, not this step.
- Auto-migrating historical seven-section detail files to compact — out of scope for the whole plan.
