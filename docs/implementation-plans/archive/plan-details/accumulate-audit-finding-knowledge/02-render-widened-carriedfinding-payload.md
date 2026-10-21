> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Render the widened `CarriedFinding` payload into later audit prompts

## Summary

Replace the audit loop's identity-only `known_anchors` carry-forward with the full `CarriedFinding` set (step 1's record) end-to-end into `plan_tool/prompts/plan-audit.md`. Add a sibling renderer `_format_carried_findings_block` in `plan_tool/review.py` beside the retiring `_format_known_findings_block`, swap the `known_anchors` parameter on `render_plan_audit_prompt`/`check_plan_audit` for `carried_findings: Sequence[CarriedFinding]`, and have `audit_plan_until_stable` pass the assembled `carried` list straight through. The key design call: the widened block keeps the existing slug-reuse instruction sentence **verbatim** and the `` - `[slug]` `` line shape so the union-by-id dedup contract can't regress, while adding severity, a body excerpt, and a non-`open` resolution per finding, and a count cap so the block can't balloon the prompt. On green: later passes see each prior finding's severity/excerpt/resolution, the slug-reuse set fed forward is unchanged **at ≤`_CARRIED_BLOCK_MAX_FINDINGS` anchored findings**, and the rendered block never exceeds `_CARRIED_BLOCK_MAX_FINDINGS` findings. Above the cap the fed-forward slug set is a strict (highest-severity-first) subset, so the cap trades a bounded dedup-regression risk — a later pass re-finding a dropped lowest-severity concept no longer sees its slug — against prompt cost.

## Table of Contents

- [Why](#why) — what the slug+title-only block can't tell a later pass
- [Files (creates vs edits)](#files-creates-vs-edits) — one source edit, one prompt edit, tests
- [Implementation](#implementation) — the sibling renderer, the seam param swap, the prompt substitution
- [Tests](#tests) — renderer field/cap/dedup tests + the updated prompt-seam tests
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — prompt-cache + token-counting + sorting docs
- [Deferred](#deferred) — what steps 3–4 and reconcile own

## Why

`audit_plan_until_stable` feeds later passes only `[(c.anchor, c.title) for c in carried if c.anchor]` (step 1's derivation), which `_format_known_findings_block` renders as slug + title lines so Claude re-uses an established slug and the union-by-id merge collapses rephrasings. A later pass cannot see a prior finding's severity, a sketch of its body, or whether it was already applied/skipped — so it cannot say "already surfaced as HIGH, applied; if it recurs that's a spin signal." Step 1 already built the richer `CarriedFinding` record and `assemble_carried_findings`; this step is the first consumer — it renders that record into the next audit prompt without changing what the audit finds, how it samples, or the convergence stop logic. The slug-reuse dedup path stays correct and becomes one field of a wider block **so long as the carried set fits the cap**: at ≤`_CARRIED_BLOCK_MAX_FINDINGS` anchored findings the rendered slug set equals step 1's `[(c.anchor, c.title) for c in carried if c.anchor]`, so dedup does not regress. Above the cap the rendered slug set is a strict subset (lowest-severity findings dropped first), and a later pass that re-finds a dropped concept no longer sees its slug — re-introducing the semantic duplicate the block exists to prevent. This is a deliberate, bounded trade: the cap bounds prompt cost at the price of dedup coverage for the lowest-severity findings beyond 30, which the truncation note surfaces rather than hiding.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `_format_carried_findings_block` and the `_CARRIED_BLOCK_MAX_FINDINGS` cap; swap `known_anchors` for `carried_findings` on `render_plan_audit_prompt` and `check_plan_audit`; pass the assembled `carried` straight through from `audit_plan_until_stable`; remove the now-dead `_format_known_findings_block`.
  - `plan_tool/prompts/plan-audit.md` — rename the `${known_findings_block}` substitution to `${carried_findings_block}` (same position) and widen the intro that describes what is listed (two wrapped lines at HEAD).
  - `tests/test_review.py` — new renderer tests; update the two prompt-seam tests (`test_prompt_lists_known_anchors_for_slug_reuse`, `test_prompt_omits_slug_reuse_block_without_known_anchors`) to the new parameter and rendered shape.

## Implementation

### `plan_tool/review.py`

- **Add `_CARRIED_BLOCK_MAX_FINDINGS = 30`** near `_CARRIED_BODY_EXCERPT_CHARS` (step 1's per-finding cap). This is the whole-*set* cap — the maximum number of findings the block renders. Step 1's char cap bounds each finding's excerpt; this count cap bounds how many findings appear. 30 anchored findings × (~280-char excerpt + a slug/severity/title line) ≈ 12 KB — a deliberate upper bound on the carried block's prompt cost.

- **Add `_format_carried_findings_block(carried: Sequence[CarriedFinding], *, max_findings: int = _CARRIED_BLOCK_MAX_FINDINGS) -> str`** — the sibling renderer, modeled on `_format_known_findings_block` (same `list[str]` + `"\n".join` shape, same `""`-on-empty contract):
  - **Filter to anchored findings only** (`[c for c in carried if c.anchor]`). A sluggless finding has no slug to re-use, so it stays out of the carry-forward block exactly as today — this keeps the rendered slug set equal to step 1's `[(c.anchor, c.title) for c in carried if c.anchor]`, so dedup does not regress. Return `""` when nothing is anchored (first pass, or no slugged findings yet) so the template line collapses to a blank, matching the old behavior.
  - **Select within the cap deterministically.** Sort the anchored list by `key=lambda c: (_carried_severity_rank(c.severity), c.resolution != CARRIED_RESOLUTION_OPEN, c.anchor or "", c.title)` and take the first `max_findings`. Severity is primary (highest first, reusing step 1's `_carried_severity_rank`); the `resolution != open` tiebreaker prefers unresolved findings within a severity band. During the audit loop every finding is `open`, so this reduces to the assembled severity order; the unresolved preference is forward-looking for any caller that supplies resolutions. Render in this same order — never dict/iteration order.
  - **Preserve the slug-reuse instruction sentence verbatim.** Keep the load-bearing dedup sentence unchanged: `re-use its exact \`[anchor-slug]\` verbatim — your wording may differ; the slug is the identity. Mint a new slug only for a genuinely new concept.` Only the intro lines that *describe what is listed* widen (two wrapped lines at HEAD, not a single line — mention severity, resolution, and a short excerpt now ride alongside the slug). The dedup contract is the instruction sentence; it does not change.
  - **Render each finding** as a parent line plus an optional excerpt line:
    - `` - `[<slug>]` (<SEVERITY>[, <resolution>[: <reason>]]) — <title>`` — `<SEVERITY>` is `c.severity.upper()` (the stored severity is lowercase, mapped via `_CLAUDE_SEVERITY_MAP` in `_parse_plan_audit_findings`). Append `, <resolution>` only when `c.resolution != CARRIED_RESOLUTION_OPEN`, and `: <reason>` only when `c.resolution_reason` is non-empty. `open` renders nothing extra, keeping the audit-loop block lean (every finding is `open` there).
    - An indented continuation line carrying `c.body_excerpt`, omitted when the excerpt is empty.
  - **Append a truncation note when the cap dropped findings** — e.g. `… N more lower-priority finding(s) not shown (cap 30).` — so truncation is never silent (mirrors the audit loop's "coverage budget-limited" warning and the repo's no-silent-caps rule). Omit the note when nothing was dropped.

- **Swap the seam parameter from `known_anchors` to `carried_findings`** on both prompt-facing functions:
  - `render_plan_audit_prompt(plan, plan_path, *, repo_root, carried_findings: Sequence[CarriedFinding] = ())` — substitute `carried_findings_block=_format_carried_findings_block(carried_findings)`.
  - `check_plan_audit(plan, plan_path, *, repo_root, invoker=None, log_file=None, carried_findings: Sequence[CarriedFinding] = ())` — forward `carried_findings` to `render_plan_audit_prompt`. Update each function's docstring to describe the widened block.

- **Pass the assembled set straight through in `audit_plan_until_stable`.** Step 1 already builds `carried = assemble_carried_findings(by_id.values())` before the `check_plan_audit` call and derives `known_anchors` from it. Drop that derivation line and pass `carried_findings=carried` to `check_plan_audit`. This is the completion of step 1's single-source-of-truth handoff: the assembled list is now the *only* carry-forward input, not a slug subset of it.

- **Remove `_format_known_findings_block`.** It is superseded by `_format_carried_findings_block` and, after the seam swap, has no caller. It is internal to `review.py` (no other module or test imports it), so removal breaks no import. The two tests that exercised the old slug-reuse block move to the new renderer/param (below).

#### Foundational logic and shared call sites

- **Core behavior added:** render the accumulated `CarriedFinding` set as the audit prompt's carry-forward block, preserving slug-reuse dedup under a size cap. The only carry-forward render site in the app is this block (`plan_tool/prompts/plan-audit.md` ← `_format_carried_findings_block`). The apply path's carried-context render is a **separate** renderer against `prompts/apply-finding.md` — owned by step 3, not reused here, because it answers a different prompt with different scope-guard exposure.
- **Severity ordering** stays single-sourced on step 1's `_carried_severity_rank` (which reuses `_SEVERITY_BANNER_ORDER`). Do not reach for `convergence_diagnosis.py:_SEVERITY_RANK` — it is the separate medium+-only scale and `KeyError`s on `nit`/`info`. Consolidating the two severity scales remains a reconcile-only refactor (step 1's Deferred).

### `plan_tool/prompts/plan-audit.md`

- **Rename the substitution.** The `${known_findings_block}` line (between the `[anchor-slug]` slug-pick paragraph that ends `keep it short and deterministic.` and the `Severity guidance:` list) becomes `${carried_findings_block}`. Keep it on its own line so an empty block collapses to a single blank line, as today.
- **No other prose change** is required — the rendered block carries its own intro and the verbatim slug-reuse instruction. The surrounding `## Findings format (machine-parsed …)` section and the severity/triage/`→ fix:` guidance are untouched.

## Tests

All renderer tests construct `CarriedFinding` objects directly (no `tmp_path`, no invoker, no integration marker) — `_format_carried_findings_block` is pure. In `tests/test_review.py`:

- `test_carried_block_renders_severity_and_title` — an anchored `CarriedFinding` renders `` - `[slug]` (SEVERITY) — title``; the slug token and title appear verbatim.
- `test_carried_block_renders_excerpt_line` — a non-empty `body_excerpt` renders on the indented continuation line; an empty excerpt renders no continuation line.
- `test_carried_block_renders_resolution_only_when_not_open` — `resolution=open` renders no resolution token; `applied` renders `(SEVERITY, applied)`; `skipped` with a reason renders `(SEVERITY, skipped: <reason>)`.
- `test_carried_block_preserves_slug_reuse_instruction` — the verbatim sentence `re-use its exact` … `the slug is the identity` … `Mint a new slug only for a genuinely new concept.` is present after whitespace-normalizing the rendered block (the renderer line-wraps the sentence via `"\n".join`, so `the slug is` and `the identity` land on separate lines — assert against `" ".join(block.split())`, not the raw text, or assert the wrapped fragments individually). (dedup contract intact)
- `test_carried_block_omits_sluggless_findings` — a `CarriedFinding` with `anchor=None` produces no line; the rendered slug set equals the anchored inputs.
- `test_carried_block_empty_for_no_anchored` — empty input, or all-sluggless input, returns `""`.
- `test_carried_block_caps_findings` — more than `_CARRIED_BLOCK_MAX_FINDINGS` anchored findings render exactly the cap, highest-severity first, plus the `… N more … not shown (cap 30)` note.
- `test_carried_block_cap_is_deterministic` — two renders of the same over-cap input return equal strings (the order/selection a cap silently regresses on).
- `test_carried_block_prefers_unresolved_within_severity` — at the cap boundary, two same-severity findings differing only in resolution keep the `open` one and drop the resolved one.

Prompt-seam tests (updated from the retired `known_anchors` shape, same `TestCheckPlanAudit` slug-reuse group):

- `test_prompt_lists_known_anchors_for_slug_reuse` — pass `carried_findings=[CarriedFinding(anchor=…, title=…, severity=…, body_excerpt=…), …]`; assert each slug + title renders and the slug-reuse instruction appears. **Update** the old `known_anchors=` call and the exact `` - `[slug]` — title`` assertions to the widened line; the instruction-sentence assertion stays.
- `test_prompt_omits_slug_reuse_block_without_known_anchors` — with no `carried_findings`, the block is absent and no unexpanded `carried_findings_block` template token leaks. **Update** the `"known_findings_block" not in prompt` assertion to `"carried_findings_block"`.

Loop-level regression (drives `audit_plan_until_stable` with the `_sampling_invoker` fake in `TestAuditPlanUntilStable`, matching `test_unions_across_samples_and_stops_on_dry_round`):

- `test_audit_loop_carries_widened_block` — across two passes where the second re-finds a concept, assert on the **second pass's captured prompt** (`calls[1]`): it carries the first pass's `[anchor-slug]` token and the widened block (a `(SEVERITY)` token on the carried line), confirming `audit_plan_until_stable` now threads the full `carried` set, not the slug subset. Assert on the captured prompt because dedup keys on `rec.id` parsed from the fake response (`_parse_plan_audit_findings`), so a final-rec-set assertion is tautological.
- **Step 1's `test_audit_loop_slug_reuse_set_unchanged` must stay green.** It asserts the second pass's prompt still carries the first pass's slug + re-use instruction; both are preserved verbatim by `_format_carried_findings_block`. If that test pinned the *old intro sentence* wording ("listed below with their anchor slugs"), update only that one assertion in lockstep to the widened intro — the dedup re-use instruction it really guards is unchanged.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add each renderer test with the renderer, each seam test with the parameter swap, and the loop regression with the `audit_plan_until_stable` rewire. Green-before-done gate: every new and updated test must pass and the full `tests/test_review.py` suite must stay green before the step is finished.

## Acceptance criteria

- `_format_carried_findings_block` renders an anchored `CarriedFinding` as `` - `[slug]` (SEVERITY) — title`` with the excerpt on an indented line, and the resolution token only when `resolution != open`.
- The verbatim slug-reuse instruction sentence is present in the rendered block once whitespace is normalized (the renderer line-wraps it across lines); at ≤`_CARRIED_BLOCK_MAX_FINDINGS` anchored findings the anchored slug set equals step 1's `[(c.anchor, c.title) for c in carried if c.anchor]` (sluggless findings excluded), so rephrased-duplicate dedup still collapses. Above the cap the rendered slug set is a strict highest-severity-first subset — a bounded dedup-regression for the dropped lowest-severity findings, accepted in exchange for prompt cost and made visible by the truncation note.
- The block renders at most `_CARRIED_BLOCK_MAX_FINDINGS` findings, highest-severity first, with a non-silent `… N more … not shown` note when truncated; two renders of identical input are equal.
- `render_plan_audit_prompt` and `check_plan_audit` take `carried_findings: Sequence[CarriedFinding] = ()` (no `known_anchors`); `audit_plan_until_stable` passes `assemble_carried_findings(by_id.values())` through unchanged.
- `plan_tool/prompts/plan-audit.md` substitutes `${carried_findings_block}` in the old block's position; no unexpanded template token leaks for an empty block.
- `_format_known_findings_block` is removed and unreferenced; the full `tests/test_review.py` suite is green.

## References

- [Prompt caching - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — confirm the widened carried block sits before a stable cache breakpoint so its growth reads as `cache_read` rather than re-billing `cache_creation` each pass (the plan's medium token-cost risk).
- [Token counting - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/token-counting) — `/v1/messages/count_tokens` for sizing the rendered block when tuning `_CARRIED_BLOCK_MAX_FINDINGS` / `_CARRIED_BODY_EXCERPT_CHARS`.
- [Sorting Techniques — Python 3 documentation](https://docs.python.org/3/howto/sorting.html) — `sorted()` key functions and stability, the basis for the deterministic cap-selection key `(severity, unresolved, anchor, title)`.

## Deferred

- The `carried_findings` kwarg on `apply_finding` and its `prompts/apply-finding.md` rendering — step 3 (a separate renderer against a separate prompt with separate scope-guard exposure; do not reuse `_format_carried_findings_block`).
- Wiring the accumulated set + `carried_resolution_from_annotations` from the convergence loop into both apply call sites, where `CARRIED_RESOLUTION_BLOCKED`/`APPLIED`/`SKIPPED` are populated from live apply verdicts — step 4. Only then does this renderer's resolution token render non-`open` in practice.
- Consolidating `review._SEVERITY_BANNER_ORDER` and `convergence_diagnosis._SEVERITY_RANK` into one severity scale — a behavior-preserving cross-module reconcile refactor (step 1's Deferred).
- A persisted cross-run carried-finding store and any `--json` surface — out of scope per the plan (within-run loop memory only); the carried block is rendered prompt text, never serialized, so `DATA_CONTRACT.md` is unaffected.
