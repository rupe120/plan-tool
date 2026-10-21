> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add an advisory `carried_findings` kwarg to `apply_finding`, rendered into `apply-finding.md` without widening the scope-guard edit set

## Summary

Give `plan_tool/launcher.py:apply_finding` an optional `carried_findings: Sequence[CarriedFinding] = ()` kwarg (step 1's record) and render it as a clearly-advisory block in `plan_tool/prompts/apply-finding.md`, so the apply pass can see what the iterate loop already surfaced and tried — without gaining permission to edit anything new. The block is built by a new `_format_carried_context_block` in `launcher.py`, mirroring the existing `_format_targeted_fix_block` / `_format_feedback_block` injected-block pattern (pre-built string, `""` when empty, keeps the prompt a plain `string.Template`); it is a **separate** renderer from step 2's `review.py:_format_carried_findings_block`, by design — different prompt, different scope-guard exposure. The default-empty kwarg leaves every existing `apply_finding` caller and test unchanged. On green: a supplied `carried_findings` renders an advisory "already surfaced this run" section, the prompt's stay-inside-plan/detail scope rule is unchanged verbatim, and `apply_finding`'s own tracked/snapshot path set is identical with and without `carried_findings`.

## Table of Contents

- [Why](#why) — what the apply pass can't see about loop history today
- [Files (creates vs edits)](#files-creates-vs-edits) — one source edit, one prompt edit, tests
- [Implementation](#implementation) — the kwarg, the advisory renderer, the prompt placeholder
- [Tests](#tests) — render/advisory-framing/cap/determinism + the scope-set invariant
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — prompt-cache + sorting docs
- [Deferred](#deferred) — what step 4 and reconcile own

## Why

`plan_tool/launcher.py:apply_finding` renders the full plan, the target step, and the single finding being applied — it has no view of the *other* findings the `--iterate` loop surfaced or resolved this run. The loop already prevents the *same* finding from being re-attempted across rounds (`completeness_cmd.py` adds every dispatched `rec.id` to `applied_fingerprints` regardless of verdict, and `open_findings` filters those ids out). The gap is **cross-finding**: when a new finding's remedy resembles one a sibling finding already established won't land, the apply pass re-proposes the same dead end — with the "what the loop learned" context living only in the operator's head. Step 1 built the `CarriedFinding` record and `assemble_carried_findings`; step 2 rendered it into the *audit* prompt. This step is the apply-side consumer: thread that accumulated context into the *apply* prompt as strictly advisory text. The key constraint — `apply_finding`'s scope guard is deliberately narrow (the carried context informs, it must not expand what apply may write) — is realized two ways: the kwarg never touches `apply_finding`'s `tracked` snapshot/revert surface, and the prompt frames the block as context-only beside the unchanged "stay inside the plan/detail surface" rule. Step 4 wires the real accumulated set from the convergence loop into both call sites; this step only adds and renders the seam.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/launcher.py` — add `Sequence` to the `from typing import …` line; add `CarriedFinding`, `_carried_severity_rank`, and `CARRIED_RESOLUTION_OPEN` to the existing `from plan_tool.review import (…)` block; add the `_CARRIED_APPLY_MAX_FINDINGS` cap and `_format_carried_context_block`; add the `carried_findings: Sequence[CarriedFinding] = ()` kwarg to `apply_finding` and inject `carried_findings_block` into its `extra_vars`.
  - `plan_tool/prompts/apply-finding.md` — add a `${carried_findings_block}` substitution after `${operator_feedback_block}`, before `## What to do`. No change to the "What to do" scope rule.
  - `tests/test_launcher.py` — renderer tests (in/near `TestApplyFindingDryRun`), the advisory-framing test, the cap/determinism tests, and the scope-set-unchanged invariant test.

## Implementation

### `plan_tool/launcher.py`

- **Imports.**
  - Add `Sequence` to `from typing import TYPE_CHECKING, Callable, Optional` (line 24) → `… Callable, Optional, Sequence`.
  - Add `CarriedFinding`, `_carried_severity_rank`, and `CARRIED_RESOLUTION_OPEN` to the existing `from plan_tool.review import (…)` block (the one importing `FileCheck`, `Recommendation`, `_make_rec_id`, …). This is the same top-level import direction `launcher` already uses; `review.py` imports `launcher` only lazily (`read_lessons_step_ids` inside a function), so there is no module-load cycle. **Confirm at HEAD** that `CarriedFinding` / `_carried_severity_rank` / `CARRIED_RESOLUTION_OPEN` exist in `plan_tool/review.py` before importing — they land in step 1 (`depends_on: 1`); if absent, step 1 has not landed yet.

- **Add `_CARRIED_APPLY_MAX_FINDINGS = 20`** near the other apply-finding block helpers (`_format_targeted_fix_block`, `_format_feedback_block`). This is the apply block's own whole-set cap — distinct from step 2's `review._CARRIED_BLOCK_MAX_FINDINGS = 30` (the audit block's cap). The apply prompt already carries full plan content, so keep the advisory tail modest.

- **Add `_format_carried_context_block(carried: Sequence[CarriedFinding], *, max_findings: int = _CARRIED_APPLY_MAX_FINDINGS) -> str`** — the advisory renderer, modeled on `_format_targeted_fix_block` (returns a `## …` section string, or `""` when there is nothing to show, so the template stays a plain `string.Template`):
  - **Return `""` for empty/None input** so the `${carried_findings_block}` line collapses to nothing — every existing caller (which passes no `carried_findings`) renders an unchanged prompt.
  - **Select within the cap deterministically.** Sort by `key=lambda c: (_carried_severity_rank(c.severity), c.resolution != CARRIED_RESOLUTION_OPEN, c.anchor or "", c.title)` and take the first `max_findings` — highest-severity first, unresolved before resolved within a band, then a stable `(anchor, title)` tiebreak. The input already arrives sorted from step 1's `assemble_carried_findings`, but sorting here makes the cap selection deterministic regardless of caller order (the property a size cap silently regresses on). Reuse step 1's `_carried_severity_rank` (which reuses `review._SEVERITY_BANNER_ORDER`); do **not** reach for `convergence_diagnosis.py:_SEVERITY_RANK` — it is the separate medium+-only scale and `KeyError`s on `nit`/`info`.
  - **Do not render the slug.** A slug is the audit loop's dedup identity; it means nothing on the apply side. Render each finding as `` - (<SEVERITY>[, <resolution>[: <reason>]]) <title>`` — `<SEVERITY>` is `c.severity.upper()`; append `, <resolution>` only when `c.resolution != CARRIED_RESOLUTION_OPEN`, and `: <reason>` only when `c.resolution_reason` is non-empty. Add an indented continuation line carrying `c.body_excerpt`, omitted when the excerpt is empty.
  - **Append a non-silent truncation note** when the cap dropped findings — e.g. `… N more lower-priority finding(s) not shown (cap 20).` — and omit it when nothing was dropped (the repo's no-silent-caps rule).
  - **Frame the section as advisory, context-only.** Lead with a heading and one sentence stating these are findings the iterate loop already surfaced/tried this run, given so the apply avoids re-proposing an already-blocked remedy, and that this block **does not expand what may be edited** — apply only the finding(s) above and stay inside the plan/detail surface. Example shape:
    ```
    \n## Already surfaced this run (advisory — context only, do not act on these)\n\n
    These findings were raised earlier in this iterate loop, with what
    happened to each. Use them to avoid re-proposing a remedy a prior
    finding already established won't land. This is context only — it does
    NOT widen what you may edit. Apply only the finding(s) above.\n\n
    - (HIGH, blocked: needs a new file) step 3 detail missing acceptance bullet
      …excerpt…
    ```

- **Add the kwarg to `apply_finding`.** Insert `carried_findings: Sequence[CarriedFinding] = ()` in the keyword-only block (e.g. after `operator_feedback`). Default empty so every current caller is unchanged. Add the wiring in the existing `extra_vars` dict assembled before `render_prompt(... mode="apply-finding" ...)`, beside `finding_fix_block` / `operator_feedback_block`:
  - `"carried_findings_block": _format_carried_context_block(carried_findings)`.
  - Because the renderer uses `safe_substitute`, `carried_findings_block` **must** always be supplied (`""` when empty) or the literal `${carried_findings_block}` token would leak into the prompt. The other injected blocks follow this same always-present rule.
- **Do not touch `tracked` / `pre_snapshot`.** The `carried_findings` kwarg feeds only `extra_vars`; the `tracked` list (plan + every step's detail file) that drives snapshot, diff, and revert is built before and independent of it. This is the in-`apply_finding` half of the scope invariant — apply's editable/revertible surface does not grow. Update `apply_finding`'s docstring with one line naming `carried_findings` as advisory prompt context that never widens the tracked set.

#### Foundational logic and shared call sites

- **Core behavior added:** render the accumulated `CarriedFinding` set as advisory context in the apply prompt. The parallel render site is step 2's `review.py:_format_carried_findings_block` → `prompts/plan-audit.md` (the audit loop's carry-forward). The two are kept **separate on purpose** — different prompt, different audience, different scope-guard exposure (the audit block carries a key slug-reuse dedup contract the apply block must not). Do not reuse `_format_carried_findings_block` here.
- **Severity ordering** stays single-sourced on `review._carried_severity_rank` (→ `_SEVERITY_BANNER_ORDER`). Both carried renderers now key on it.
- **Consolidating the two carried renderers** (`launcher._format_carried_context_block` and `review._format_carried_findings_block`) into one shared block builder is a behavior-preserving cross-module refactor `detail` cannot mint — routed to `## Deferred` for reconcile, not pulled into this step's set of files. They answer different prompts today, so the duplication is deliberate, not accidental.
- **The two `apply_finding` callers** that will pass the real accumulated set — `cli/review_actions.py:_dispatch_apply_finding` and the per-iteration apply call in `cli/completeness_cmd.py` (`_run_iterate_convergence_loop`) — are **step 4's** edit, not this step's. This step only adds the parameter and the renderer; nothing in `plan_tool/cli/` changes here.

### `plan_tool/prompts/apply-finding.md`

- **Add the placeholder.** The `## Finding(s) to apply` block currently ends:
  ```
  > ${finding_body}
  ${finding_fix_block}${operator_feedback_block}
  ## What to do
  ```
  Change the middle line to `${finding_fix_block}${operator_feedback_block}${carried_findings_block}`. The helper returns a leading-`\n` section (or `""`), so spacing before `## What to do` stays correct whether or not a block renders — same shape as the targeted-fix and operator-feedback blocks.
- **No other prose change.** The rendered block carries its own advisory framing. The `## What to do` rule **5** ("Do NOT modify code outside the plan/detail files … post-apply scope guard … Stay inside the plan/detail surface") and the `## Output contract` verdict list stay unchanged — the carried context must not read as new permission.

## Tests

All renderer tests use `dry_run=True` (returns the rendered prompt, invokes no Claude) and construct `CarriedFinding` objects directly — no real backend, no integration marker. Add them in `tests/test_launcher.py`, in or beside `TestApplyFindingDryRun` (which already houses `test_targeted_fix_injected_into_prompt` and `test_structural_verdict_option_gated`). Use the existing `_write_plan_for_apply(tmp_path)` helper.

- `test_carried_findings_default_empty_renders_no_block` — without `carried_findings`, the prompt contains no advisory section heading and no unexpanded `${carried_findings_block}` / `carried_findings_block` token.
- `test_carried_findings_rendered_when_supplied` — a supplied anchored `CarriedFinding` renders its `<SEVERITY>` and title on a bullet; the advisory section heading is present.
- `test_carried_block_advisory_framing` — the rendered block states it is context-only and does **not** widen what may be edited (assert on the "do NOT" / "context only" phrasing), and the existing scope rule ("Stay inside the plan/detail surface") is still present verbatim.
- `test_carried_findings_resolution_token` — `resolution=open` renders no resolution token; `applied` renders `(SEVERITY, applied)`; `blocked` with a reason renders `(SEVERITY, blocked: <reason>)`; `skipped` likewise.
- `test_carried_findings_excerpt_line` — a non-empty `body_excerpt` renders on the indented continuation line; an empty excerpt renders no continuation line.
- `test_carried_apply_block_caps_findings` — more than `_CARRIED_APPLY_MAX_FINDINGS` anchored findings render exactly the cap, highest-severity first, plus the `… N more … not shown (cap 20)` note.
- `test_carried_apply_block_deterministic` — two renders of the same over-cap input return equal strings (the order/selection a cap silently regresses on).
- `test_carried_findings_scope_set_unchanged` — call `apply_finding` (dry-run) with and without `carried_findings`; assert `set(result.pre_snapshot.keys())` is identical across the two — the carried context does not grow `apply_finding`'s tracked/snapshot surface (the in-`apply_finding` scope invariant).
- `test_carried_findings_coexist_with_targeted_fix` — supplying `targeted_fix` **and** `carried_findings` renders both the `## Targeted fix` block and the advisory block; the carried block sits after the feedback/fix blocks and before `## What to do`.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add each test with the implementation it covers: the kwarg + renderer with the render/empty/framing tests; the cap with the cap/determinism tests; the `extra_vars` wiring with the scope-set-unchanged and coexist tests. Green-before-done gate: every new test must pass and the existing `tests/test_launcher.py` apply-finding suite (`TestApplyFindingDryRun`, `TestParseApplyVerdict`, and the non-dry-run apply tests) must stay green — they pass no `carried_findings`, so they must render byte-for-byte unchanged prompts.

## Acceptance criteria

- `apply_finding` accepts `carried_findings: Sequence[CarriedFinding] = ()`; with it empty, the rendered apply prompt is unchanged and every existing caller/test is unaffected.
- `_format_carried_context_block` returns `""` for empty input, renders each finding as `- (<SEVERITY>[, <resolution>[: <reason>]]) <title>` with an indented excerpt line when present, omits the resolution token when `resolution == open`, and caps at `_CARRIED_APPLY_MAX_FINDINGS` with a non-silent `… N more … not shown` note.
- Two renders of identical over-cap input produce equal strings (deterministic cap selection).
- The rendered advisory block states it is context-only and does not widen the edit set; `plan_tool/prompts/apply-finding.md`'s `## What to do` scope rule and verdict list are unchanged.
- `set(result.pre_snapshot.keys())` from `apply_finding` is identical with and without `carried_findings` — the kwarg never enlarges the tracked/revert surface.
- No unexpanded `${carried_findings_block}` token leaks for an empty block.

## References

- [Prompt caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — confirm the advisory carried block sits where its growth reads as `cache_read` rather than re-billing `cache_creation`, bounding the plan's medium token-cost risk.
- [Sorting Techniques — Python 3 documentation](https://docs.python.org/3/howto/sorting.html) — `sorted()` key functions and stability, the basis for the deterministic cap-selection key `(severity, unresolved, anchor, title)`.
- [string.Template — Python 3 documentation](https://docs.python.org/3/library/string.html#template-strings) — `safe_substitute` behavior, why an always-present `carried_findings_block` value is required so no `${…}` token leaks.

## Deferred

- Wiring the real accumulated set (and `carried_resolution_from_annotations`) from the convergence loop into the two `apply_finding` callers (`cli/review_actions.py:_dispatch_apply_finding`, the per-iteration apply call in `cli/completeness_cmd.py`), where `CARRIED_RESOLUTION_APPLIED` / `BLOCKED` / `SKIPPED` are populated from live apply verdicts — **step 4**. Only then does this renderer's resolution token render non-`open` in practice; step-3 tests pass synthetic `CarriedFinding` objects.
- The caller-level scope-guard invariant — asserting `scope_guard.compute_in_scope_paths` is identical with vs without `carried_findings` — belongs to **step 4** (the caller owns the scope guard; `apply_finding` does not call it). Step 3 asserts only `apply_finding`'s own `pre_snapshot` surface.
- Consolidating `launcher._format_carried_context_block` and `review._format_carried_findings_block` into one shared block builder — a behavior-preserving cross-module refactor for `reconcile`, not this step (the two prompts/exposures differ today).
- A persisted cross-run carried-finding store and any `--json` surface — out of scope per the plan (within-run loop memory only); the advisory block is rendered prompt text, never serialized, so `DATA_CONTRACT.md` is unaffected.
