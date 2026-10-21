> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Fold detail's MIXED-STEP purity kernel into the advisor as `granularity-split` (one kernel)

## Summary

Move detail's MIXED-STEP purity parser out of `plan_tool/detail.py` and into the step-1 leaf `plan_tool/granularity.py` as the public `parse_mixed_step_findings`, carrying the two regexes (`_STRUCTURAL_BLOCK_RE`, `_MIXED_STEP_BULLET_RE`) with it. The relocated kernel emits `source="granularity-split"` (was `detail-purity`); both `detail.py` call sites call the kernel directly, and `assess_granularity(stage="detail")` also delegates to it — one kernel, no fork. Behavior is preserved except the deliberate source rename: `detail --split` Phase B keeps consuming the same `(step_id, Recommendation)` pairs unchanged. On green, `grep -rn "detail-purity" plan_tool/` returns zero, `plan_tool.detail._STRUCTURAL_BLOCK_RE is plan_tool.granularity._STRUCTURAL_BLOCK_RE`, and the relabeled finding still routes through the generic structural triage text (the dedicated `detail-purity` branch in `plan_tool/review.py` is removed).

## Table of Contents

- [Summary](#summary) — what moves, what gets renamed, the observable result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the split-only purity check this fold unifies under the advisor.
- [Files (creates vs edits)](#files-creates-vs-edits) — the relocation + relabel set of files, including the required `review.py` cleanup.
- [Implementation](#implementation) — kernel relocation, single-path wiring, source relabel, the dead triage branch.
- [Tests](#tests) — characterization-first buckets and the new single-sourcing pins.
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — write-first list and the pass-unchanged gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — Python 3.13 re / import-system docs.
- [Deferred](#deferred) — stage adapters, merge executor, verb tuning.

## Why

Detail's mixed-refactor-plus-feature judgment lives in `plan_tool/detail.py: _parse_purity_findings` and emits `source="detail-purity"` — a one-stage, split-only signal with no shared home. Step 1 created `plan_tool/granularity.py` as the cycle-free advisor leaf and reserved `source="granularity-split"` for exactly this signal, but left the prose kernel where it was. This step finishes that fold: relocate the one kernel into the leaf so detail's MIXED-STEP check, `detail --split` Phase B, and the future escalation bridge all read one implementation under one source — never two that can drift. It is a behavior-preserving relocation plus a deliberate source rename; no new granularity logic is added here.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/granularity.py` — add the relocated kernel `parse_mixed_step_findings`, the two regexes `_STRUCTURAL_BLOCK_RE` / `_MIXED_STEP_BULLET_RE`, and the `assess_granularity(stage="detail")` delegation over `GranularityEvidence.detail_bodies`. The kernel emits `source=GRANULARITY_SPLIT_SOURCE` (the step-1 constant `"granularity-split"`).
  - `plan_tool/detail.py` — delete `_parse_purity_findings`, `_STRUCTURAL_BLOCK_RE`, `_MIXED_STEP_BULLET_RE` and their comment block; import `parse_mixed_step_findings` and `_STRUCTURAL_BLOCK_RE` from `plan_tool.granularity`; repoint both call sites in `collect_detail_quality_findings` and `generate_detail`.
  - `plan_tool/review.py` — **required set-of-files addition** (not in the plan's `files:`). The relabel orphans the `if rec.source == "detail-purity":` branch in `triage_reason`; remove it so `granularity-split` routes through the generic structural-diagnostic text (matching step 1's posture for the deterministic granularity recs) and so `grep -rn "detail-purity" plan_tool/` is zero. No new import is added to `review.py` — `granularity` imports `review`, never the reverse, so the leaf stays acyclic.
  - `tests/test_granularity.py` — move the kernel detection cases here (the kernel now lives in `granularity.py`); flip the source literal to `"granularity-split"`.
  - `tests/test_detail.py` — flip the import path and the merged-findings source filters; add the `is`-identity single-sourcing pin; leave the strip/leak and Phase-B tests unchanged in behavior.

## Implementation

### `plan_tool/granularity.py` — host the one kernel

- **Add `parse_mixed_step_findings(raw: str, step: Step, plan_name: str) -> list[Recommendation]`.** This is `detail.py: _parse_purity_findings` relocated verbatim in logic — same `## Structural findings` block search, same `MIXED-STEP` bullet scan, same `non_code` drop, same body/title/`suggested_action` strings. Two changes only:
  - `source` and the `_make_rec_id` source argument become `GRANULARITY_SPLIT_SOURCE` (the step-1 constant `"granularity-split"`), never a stray literal.
  - **Drop the body-local import.** The old kernel did `from plan_tool.review import Recommendation, _make_rec_id` inside the function body to dodge the review↔detail cycle. `granularity.py` already top-imports those (step 1: `from plan_tool.review import Recommendation, _make_rec_id, Invoker`) and `review.py` never top-imports `granularity`, so there is no cycle here — use the module-top names and delete the in-body import.
- **Keep `severity="medium"` on the kernel's recs** — preserve the existing behavior. This deviates from step 1's `_GRANULARITY_SEV="info"` default for the deterministic split detectors: the prose MIXED-STEP judgment is a higher-confidence signal than the title/area heuristics. Severity does not gate apply here — `granularity-split` is excluded from `review.py: APPLY_ELIGIBLE_SOURCES` (structural exclusion is the primary non-apply guarantee), so both `info` and `medium` granularity-split recs are non-apply-eligible. State this divergence in the kernel docstring.
- **Move the two regexes** `_STRUCTURAL_BLOCK_RE` (the `## Structural findings` block matcher) and `_MIXED_STEP_BULLET_RE` (the `MIXED-STEP:` bullet matcher) into `granularity.py` as module constants, with the explanatory comment that currently precedes them in `detail.py`. `_STRUCTURAL_BLOCK_RE` is single-sourced here and imported back by `detail.py` for its defensive strip — the strip consumer and the parse kernel must read the same object.
- **Wire `assess_granularity(stage="detail")` to delegate to the kernel.** For the `"detail"` stage, iterate `evidence.detail_bodies` (the `Mapping[int, str]` forward-contract field step 1 declared) and, for each `(step_id, body)`, call `parse_mixed_step_findings(body, plan.step_by_id(step_id), plan.title)`; concatenate with the deterministic split/merge battery and return. This consumes `GranularityEvidence.detail_bodies` for the first time and satisfies the single-path invariant: there is exactly **one** kernel implementation, reached both by the advisor's stage branch and by detail's direct callers.
- **`assess_granularity` still never calls `invoker` on this path.** The MIXED-STEP signal is a deterministic lift of prose Claude already authored (the model emits the `## Structural findings` block during authoring); the kernel is pure regex. The `invoker` seam stays present-but-unused, exactly as in step 1 — pin it with the existing `test_deterministic_path_never_calls_invoker` style negative test extended to the `"detail"` stage.

### `plan_tool/detail.py` — call the relocated kernel, keep the consumer contract

- **Delete** `_parse_purity_findings`, `_STRUCTURAL_BLOCK_RE`, `_MIXED_STEP_BULLET_RE`, and the comment block above them (the `# LLM-judged step-purity …` paragraph).
- **Add a module-top import:** `from plan_tool.granularity import parse_mixed_step_findings, _STRUCTURAL_BLOCK_RE`. This is acyclic — `detail` already sits above `granularity` conceptually, `granularity` imports only `schema` and `review`, and `review` imports `detail` only lazily (call-time), so the load graph stays a tree.
- **Repoint both call sites** (no other change to surrounding logic):
  - In `collect_detail_quality_findings`: `_parse_purity_findings(raw, step, plan_name)` → `parse_mixed_step_findings(raw, step, plan_name)`; the `_STRUCTURAL_BLOCK_RE.sub("", raw)` strip now uses the imported regex (same object).
  - In `generate_detail`: the per-attempt `purity_candidate = _parse_purity_findings(raw, step, plan_slug)` → `parse_mixed_step_findings(...)`; the following `_STRUCTURAL_BLOCK_RE.sub("", raw)` strip uses the imported regex.
- **Preserve the consumer contract.** `step_purity_findings` and the `mixed_steps` list (each entry `(step.id, Recommendation)`) keep the same shape; the `tool(f"mixed-step detected — {pf.body}", …)` warn string is unchanged because the body text is unchanged. Phase B (`if allow_split and mixed_steps and sys.stdin.isatty():` → `_split_is_safe` / `_propose_step_split` / `_confirm_split` / `_apply_step_split`) does **not** filter on `rec.source`, so it consumes the relabeled recs unchanged. No Phase-B edit.
- **Leave `CATEGORY_MIXED_STEP` alone.** `detail.py` imports `CATEGORY_MIXED_STEP` (`"mixed-step"`) from `plan_tool/scenario_capture.py` — a capture-category token on a different axis than the rec `source`. It shares the "mixed-step" word but is not part of this relabel; flagged as a deliberate non-edit.

### `plan_tool/review.py` — remove the orphaned triage branch

- **Delete the `if rec.source == "detail-purity":` branch** in `triage_reason` (the `"detail-purity: structural — step mixes refactor + feature; …"` text). After the relabel nothing emits `detail-purity`, so the branch is dead.
- **Consequence:** `granularity-split` recs fall through to the generic `not is_apply_eligible(rec)` branch (`"… : structural diagnostic — not auto-fixable by an apply pass; resolve directly …"`), the same text step 1's deterministic granularity recs already get. This is an intentional change to the triage *text* for these recs — apply-eligibility is unchanged (still `False`).
- **Do not add `granularity-split` to `APPLY_ELIGIBLE_SOURCES`** — it must stay structurally excluded so `apply_finding` never tries to edit prose for a finding whose only fix is a step split.
- **Coordination obligation (cross-plan).** This `detail-purity` → `granularity-split` rename re-seeds an external dependency: the `escalate-structural-findings-to-split.md` bridge (`status: planning`) is seeded entirely on the `detail-purity` literal — its `review.is_structural` predicate, convergence-loop routing, and acceptance criteria all key on that string, and that plan's own Deferred postpones the rename until this advisor lands. Landing this step obligates re-seeding that bridge on `granularity-split` (cross-referencing its postponed-rename deferral), or its classifier matches nothing the advisor emits.

## Tests

Test files: `tests/test_granularity.py` (kernel unit cases) and `tests/test_detail.py` (integration: strip/leak, merged-findings, Phase B, single-sourcing).

In `tests/test_granularity.py` (moved from `test_detail.py`'s `TestParsePurityFindings`, retargeted at `parse_mixed_step_findings`):

- `test_mixed_block_yields_split_finding` — a `## Structural findings` block with a `MIXED-STEP:` bullet on a refactor step yields one rec; `source == "granularity-split"`, `severity == "medium"`, `step_id == step.id`, body names the bullet text.
- `test_split_finding_is_not_apply_eligible` — `review.is_apply_eligible(rec)` is `False` and `review.triage_reason(rec)` returns the generic structural-diagnostic text (asserts `"structural diagnostic"` / `"not auto-fixable"`, **not** the old `"split"`-text assertion).
- `test_no_structural_block_returns_empty` — a response with no `## Structural findings` block yields `[]`.
- `test_non_code_step_drops_bullet` — a `non-code` step yields `[]` even with a MIXED-STEP bullet.
- `test_empty_bullet_skipped` — a `MIXED-STEP:` bullet with only whitespace yields `[]`.
- `test_bold_token_and_heading_casing_tolerated` — `## Structural Findings` + `- **MIXED-STEP**:` still parses to one `granularity-split` rec.
- `test_detail_stage_delegates_to_kernel` — `assess_granularity(plan, stage="detail", evidence=GranularityEvidence(detail_bodies={id: block}))` returns the kernel's `granularity-split` recs for the seeded body. The deterministic split/merge detectors also emit `source="granularity-split"`, so isolate the kernel's recs rather than filtering on source alone — either build the plan/step so no deterministic split predicate trips (no title conjunction, single coherent `files` area, single `change_type`) so every returned rec is the kernel's, or filter to `severity == "medium"` (the kernel's severity; the deterministic detectors default `info`). Assert the body names the bullet text so the test is falsifiable against a no-op delegation.
- `test_detail_stage_never_calls_invoker` — pass an invoker stub that raises; `assess_granularity(stage="detail", …)` returns findings without invoking it.

In `tests/test_detail.py`:

- `test_structural_block_never_leaks_into_findings` (both `structural-before-findings` / `structural-after-findings` params) — **behavior unchanged**: exactly one `claude` finding and one mixed-step finding, and the `claude` body never absorbs the `MIXED-STEP` / `Structural findings` text. The only edited line is the filter literal `r.source == "granularity-split"`.
- `test_mixed_step_surfaces_and_defers_in_merged_findings` (class `TestQualityFindingsIncludePurity`) — `collect_detail_quality_findings` returns one `granularity-split` rec and no `claude` rec for a MIXED-STEP-only response (filter literal flipped).
- `test_detail_strip_and_kernel_share_one_regex` — **new:** `plan_tool.detail._STRUCTURAL_BLOCK_RE is plan_tool.granularity._STRUCTURAL_BLOCK_RE` (identity, not equality — proves the strip consumer and the kernel cannot drift to two copies).
- Phase-B split tests (`_split_is_safe`, `_confirm_split`, `_migrate_downstream_details_after_split`, the interactive split flow) — **unchanged, no edit**; they exercise the consumer contract that this relocation preserves.

### Test-creation order (refactor step)

This is a **refactor** step — behavior-preserving except the declared source rename. Write/confirm the characterization tests **first**, in two buckets, before moving any code:

- **Bucket 1 — pass UNCHANGED (the relocation half):**
  - `test_structural_block_never_leaks_into_findings` (both params) — pins that the strip still removes the block from the `## Findings` parse regardless of block position.
  - The Phase-B split tests — pin that `mixed_steps` still drives the interactive refactor-then-feature split.
  - Any edit to these beyond the single `source` filter literal in the leak test is the red flag of unintended behavior drift.
- **Bucket 2 — expect EXACTLY a one-line edit (the rename half):**
  - The kernel detection cases (now in `test_granularity.py`) — flip the `source` literal `detail-purity` → `granularity-split` and the import path (`from plan_tool.granularity import parse_mixed_step_findings`). The one exception is `test_split_finding_is_not_apply_eligible`, whose triage assertion legitimately changes from the old `"split"` text to the generic structural-diagnostic text (a consequence of removing the dead `review.py` branch — name it as the allowed extra edit).
  - The merged-findings filter literals in `test_detail.py` (`test_mixed_step_surfaces_and_defers_in_merged_findings`, class `TestQualityFindingsIncludePurity`).

**Pass-unchanged gate:** after the relocation, every Bucket-1 test stays green with no edit, and `uv run pytest tests/test_detail.py tests/test_granularity.py tests/test_review.py -q` is green.

## Acceptance criteria

- `plan_tool/granularity.py: parse_mixed_step_findings(raw, step, plan_name)` exists and returns `source="granularity-split"`, `severity="medium"` recs for a MIXED-STEP block on a code step; `[]` for a `non-code` step or a block-less response.
- `assess_granularity(plan, stage="detail", evidence=GranularityEvidence(detail_bodies={…}))` returns the kernel's `granularity-split` recs, with no `invoker` call.
- `plan_tool/detail.py` no longer defines `_parse_purity_findings`, `_STRUCTURAL_BLOCK_RE`, or `_MIXED_STEP_BULLET_RE`; it imports `parse_mixed_step_findings` and `_STRUCTURAL_BLOCK_RE` from `plan_tool.granularity`.
- `plan_tool.detail._STRUCTURAL_BLOCK_RE is plan_tool.granularity._STRUCTURAL_BLOCK_RE` (same object).
- `grep -rn "detail-purity" plan_tool/` returns zero hits (only `docs/` and plan files may still reference the old name).
- `review.triage_reason` has no `detail-purity` branch; a `granularity-split` rec returns the generic structural-diagnostic text and `review.is_apply_eligible` is `False`.
- `detail --split` Phase B still produces the same interactive split from a MIXED-STEP finding — the Phase-B tests pass unmodified.
- `uv run pytest tests/test_detail.py tests/test_granularity.py tests/test_review.py -q` is green.

## References

- [re — Regular expression operations (Python 3.13)](https://docs.python.org/3.13/library/re.html) — for relocating `_STRUCTURAL_BLOCK_RE` / `_MIXED_STEP_BULLET_RE` (the `MULTILINE | DOTALL | IGNORECASE` flags and `finditer`) unchanged into the leaf.
- [Python Language Reference — The import system (Python 3.13)](https://docs.python.org/3.13/reference/import.html) — confirms `detail → granularity → review` stays acyclic given `review`'s lazy import of `detail`.

## Deferred

- **Stage adapters for `create` and `completeness`** — feeding decompose-time evidence (step 3) and the cross-step audit (step 4) import this leaf separately; not wired here.
- **Merge executor** — the `plan-tool merge` executor has landed; `granularity-merge` stays advisory-only because no auto-escalation bridge routes a merge finding to it, so the operator hand-runs `plan-tool merge`.
- **TESTING.md neutralization row** for the granularity invoker seam — the seam is reachable as of this step, but TESTING.md is outside this step's `files:`; route the row to reconcile.
- **Verb-list / area-heuristic tuning** — broadening the step-1 deterministic detectors' recall is follow-up tuning, untouched here.
