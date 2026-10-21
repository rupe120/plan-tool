# Step 2 — Fold detail's MIXED-STEP purity kernel into the granularity leaf as `granularity-split`

## Summary

Relocate detail's MIXED-STEP purity detector — `plan_tool/detail.py:_parse_purity_findings` plus its two regexes (`_STRUCTURAL_BLOCK_RE`, `_MIXED_STEP_BULLET_RE`) — into the step-1 leaf `plan_tool/granularity.py` as `parse_mixed_step_findings`, and relabel its finding source `detail-purity → granularity-split` (both the `source=` field **and** the `_make_rec_id` argument, since the id folds the source in). Both existing `detail` call sites **and** `assess_granularity(stage="detail")` funnel through that one relocated kernel — the load-bearing invariant is *one kernel implementation*, not one entry wrapper. `plan_tool/detail.py` keeps its defensive `## Structural findings` strip but imports the now-single-sourced `_STRUCTURAL_BLOCK_RE` from `granularity` so the strip and the parse provably cannot drift. This is a **behavior-preserving relocation + deliberate source relabel**: on green, mixed-step detection, the file strip, the stderr heads-up, `detail --split` Phase B, and `triage_reason`'s "split into type-pure steps" message all behave exactly as before — now sourced `granularity-split` — and `grep -rn detail-purity plan_tool/` returns zero.

## Table of Contents

- [Summary](#summary) — what relocates, the relabel, the single-kernel invariant.
- [Why](#why) — the per-stage scatter the fold removes.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files plus the required `review.py` edit.
- [Implementation](#implementation) — file-by-file: the kernel move, the relabel, the two call-site rewires, the `triage_reason` flip.
- [Tests](#tests) — kernel tests move to `test_granularity.py`; the relabel + identity gates.
- [Acceptance criteria](#acceptance-criteria) — checkable post-conditions.
- [References](#references) — Python typing/dataclasses docs for the kernel signature.
- [Deferred](#deferred) — what stays forked or out of footprint.

## Why

Step-purity reasoning lives buried inside `detail`'s authoring layer: `_parse_purity_findings` (the LLM-judged refactor-vs-feature mixing check) is detail-only, while step 1 just shipped `plan_tool/granularity.py` as the single reusable place to decide granularity from each stage's evidence. Leaving the detail kernel forked means `create` (step 3) and `completeness` (step 4) would either re-implement the same MIXED-STEP judgment or reach back into `detail` — re-creating exactly the per-stage scatter the advisor exists to kill. Folding the existing kernel into the leaf (relocate, do not re-implement) gives every stage one `granularity-split` source while keeping detail's two call sites and `detail --split` Phase B working byte-for-byte.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/granularity.py` — add `parse_mixed_step_findings(raw, step, plan_name)` (the relocated kernel) + the two module-level regexes `_STRUCTURAL_BLOCK_RE` and `_MIXED_STEP_BULLET_RE`; top-import `Recommendation, _make_rec_id` from `plan_tool.review`; wire `assess_granularity`'s `stage == "detail"` branch to delegate to the kernel.
  - `plan_tool/detail.py` — delete `_parse_purity_findings`, `_MIXED_STEP_BULLET_RE`, and the local `_STRUCTURAL_BLOCK_RE` definition (with the explanatory comment block above them); import `_STRUCTURAL_BLOCK_RE` and `parse_mixed_step_findings` from `plan_tool.granularity`; rewire the two call sites (the iterate collect pass in `collect_detail_quality_findings`, and the authoring attempt loop in `generate_detail`).
  - `tests/test_detail.py` — move the kernel-detection class (`TestParsePurityFindings`) out to `tests/test_granularity.py`; flip the `detail-purity → granularity-split` literal in the two integration collect-pass filters; drop the `_parse_purity_findings` import from the `plan_tool.detail` import block.
  - `tests/test_granularity.py` — receive the relocated kernel-detection tests, retargeted to `from plan_tool.granularity import parse_mixed_step_findings` and the `granularity-split` source; add the shared-regex identity test.
  - **Required-but-undeclared edit — `plan_tool/review.py`:** `triage_reason` special-cases `if rec.source == "detail-purity":` to return the "split into type-pure steps" message. A relabel that misses this falls through to the generic "structural diagnostic" branch and regresses the `"split" in triage_reason(rec).lower()` assertion. Flip the literal to `"granularity-split"`. `review.py` is outside this step's declared `files:` — naming it explicitly.

## Implementation

### `plan_tool/granularity.py`

- **Relocate the two regexes as module-level constants** — copy them verbatim from `plan_tool/detail.py`; they become the single source:
  - `_STRUCTURAL_BLOCK_RE` — `^#{1,6}\s*Structural findings\s*$\n?(.*?)(?=^#{1,6}\s|\Z)` with `MULTILINE | DOTALL | IGNORECASE`.
  - `_MIXED_STEP_BULLET_RE` — `^\s*[-*]\s*(?:\*\*)?MIXED-STEP(?:\*\*)?\s*[:\-]\s*(.+?)\s*$` with `MULTILINE | IGNORECASE`.
  - `detail.py` imports `_STRUCTURAL_BLOCK_RE` for its strip; `_MIXED_STEP_BULLET_RE` is kernel-internal (detail never used it directly).
- **Add `parse_mixed_step_findings(raw: str, step: Step, plan_name: str) -> list[Recommendation]`** — the relocated body of `_parse_purity_findings`, unchanged except for the relabel:
  - `step.change_type == ChangeType.NON_CODE` → `[]` (a `non-code` step is never mixed).
  - `_STRUCTURAL_BLOCK_RE.search(raw)`; no block → `[]`.
  - For each `_MIXED_STEP_BULLET_RE` hit with a non-empty `desc`, build the same `body` / `title` / `suggested_action` strings and emit a `Recommendation` with **`source="granularity-split"`** and **`id=_make_rec_id(step.id, "granularity-split", desc)`** — relabel *both*. `_make_rec_id` folds its second arg (the source) into the fingerprint (`plan_tool/review.py: _make_rec_id`), so leaving the old literal in the id mints ids in the `detail-purity` namespace and defeats same-source dedup. `severity="medium"`, `step_id=step.id` unchanged.
- **Top-import `from plan_tool.review import Recommendation, _make_rec_id`** — the original used a body-local lazy import to dodge the `review ↔ detail` cycle. `granularity` is a leaf and `review.py` never top-imports it, so that cycle does not exist here: **drop the lazy form for an ordinary module-top import.**
- **Wire the `stage == "detail"` branch of `assess_granularity` to delegate** to `parse_mixed_step_findings` over the authored prose carried on `GranularityEvidence`. This satisfies the "single path through the advisor" directive without forcing detail's own call sites through the `assess_granularity` wrapper (which would couple the detail authoring loop to step 1's still-settling `GranularityEvidence` shape for no benefit — the kernel already lives in the leaf).
  - **Confirm the seam at HEAD before wiring.** Step 1 authored `assess_granularity(plan, *, stage, evidence, invoker=...)` and `GranularityEvidence` per the plan's Architecture section, but `granularity.py` was not on disk when this detail was drafted — the shipped shape may differ. Grep `granularity.py` at HEAD for the `assess_granularity` signature and the `GranularityEvidence` field carrying the authored detail prose; if step 1 shipped a different shape, adapt the delegation to the real seam rather than this prose. Pull the raw response/body off whatever field step 1 named (e.g. `evidence.detail_body` / `evidence.raw_response`) and pass it as the kernel's `raw`, plus the `step` and `plan_name`.

### `plan_tool/detail.py`

- **Delete** `_parse_purity_findings`, the `_MIXED_STEP_BULLET_RE` definition, and the local `_STRUCTURAL_BLOCK_RE` definition (including the comment block above them describing the strip-before-`## Findings` rationale — relocate the *parse* rationale to the kernel's docstring; keep the *strip* rationale at the strip site).
- **Import** `from plan_tool.granularity import _STRUCTURAL_BLOCK_RE, parse_mixed_step_findings`. `detail` already top-imports other leaves; `granularity` is a leaf below it, so this is an ordinary module-top import (no cycle, no lazy form).
- **Keep the `## Structural findings` defensive strip in `detail.py`** — a detail-only sanitization concern ("the block must never land in the written file / never leak past `## Findings`"), a different owner than the leaf's "parse → finding" detection. The strip stays at the consumer and consumes the imported `_STRUCTURAL_BLOCK_RE`. Both `_STRUCTURAL_BLOCK_RE.sub("", raw)` sites stay.
- **Rewire both call sites** from `_parse_purity_findings(...)` to `parse_mixed_step_findings(...)` — identical arity `(raw, step, plan_name)`:
  - The iterate collect pass in `collect_detail_quality_findings` — `purity = parse_mixed_step_findings(raw, step, plan_name)` feeding the `_merge_findings(...)` call.
  - The authoring attempt loop in `generate_detail` — `purity_candidate = parse_mixed_step_findings(raw, step, plan_slug)` computed before `parse_detail_response`; the Phase-B accumulation `mixed_steps.append((step.id, pf))` is unchanged.
- **Phase B is untouched and behavior-preserving.** The `if allow_split and mixed_steps and sys.stdin.isatty():` block in `generate_detail` iterates `mixed_steps` as `(step_id, finding)` tuples and never matches on `rec.source` — so the recs now carrying `granularity-split` flow through `_propose_step_split` / `_apply_step_split` exactly as the `detail-purity` recs did. No edit; cited as the relocation's behavior gate.

### `plan_tool/review.py` (required-but-undeclared)

- **Flip `triage_reason`'s `if rec.source == "detail-purity":` to `if rec.source == "granularity-split":`.** This is a string-keyed dispatch branch — the most dangerous relabel consumer, because a missed flip *silently falls through* to the generic "structural diagnostic" message with no error. Also flip the returned message's literal prefix in the full string `"detail-purity: structural — step mixes refactor + feature; the fix is to split it into type-pure steps, not an apply edit"` (`review.py:2979`) to `"granularity-split: structural — step mixes refactor + feature; the fix is to split it into type-pure steps, not an apply edit"`; leaving the prefix unchanged keeps a `detail-purity` literal in `plan_tool/` and breaks this step's `grep -rn "detail-purity" plan_tool/` gate. Only the `detail-purity → granularity-split` prefix changes; the post-prefix text is unchanged.
- **`detail-purity` / `granularity-split` is absent from `APPLY_ELIGIBLE_SOURCES` — leave that set byte-unchanged.** The source stays advisory (report-only / Phase-B-only); the relabel must not flip apply-eligibility.

### Deliberate non-edits (look-alike tokens / different axis)

- **`plan_tool/scenario_capture.py:CATEGORY_MIXED_STEP = "mixed-step"`** — a capture-*category* token on a different semantic axis than the rec `source`. The relabel grep surfaces it; leave it untouched.
- **The `## Structural findings` / `MIXED-STEP` prompt copy** — the wire format the kernel parses is unchanged; only the rec `source` string changes. No prompt edit.

## Tests

### Test-creation order (refactor step)

This is a **behavior-preserving relocation + a deliberate source relabel**. Partition the characterization tests into two buckets and write/relocate them **FIRST**, before touching the implementation:

**Bucket 1 — pass-UNCHANGED (the relocation half).** These pin behavior that must not move; any edit beyond an import retarget is the red flag of unintended drift:
- `tests/test_detail.py: test_purity_block_stripped_from_file_and_surfaced` — the authoring strip test (`## Structural findings` block stripped from the written file; "Structural findings"/"MIXED-STEP" absent from `written`; the `"mixed-step detected"` stderr heads-up reached `capsys.err`) stays byte-identical; it asserts the stderr warning, not the surfaced rec's `source`, so no relabel edit applies here.
- `tests/test_detail.py` — the `generate_detail` Phase-B `_MIXED_AUTHORING` split tests stay byte-identical (Phase B never matched on `rec.source`).
- `tests/test_detail.py` — the SPLIT-vs-purity prompt-shape tests (`"Step purity self-check" in prompt`, `"MIXED-STEP" in prompt`) stay unchanged (prompt copy is untouched).

**Bucket 2 — expect-EXACTLY-the-relabel edit (the rename half).** The only allowed changes are the `detail-purity → granularity-split` source/literal flip, the import path retarget, and the prescribed test-method renames (`test_mixed_block_yields_detail_purity_finding → …granularity_split_finding`, `test_detail_purity_is_not_apply_eligible → test_granularity_split_is_not_apply_eligible`, `test_no_structural_block_returns_empty → …yields_nothing`, `test_non_code_step_drops_bullet → …drops_block`, `test_empty_bullet_skipped → test_empty_desc_bullet_skipped`); anything beyond those is drift. Move the `TestParsePurityFindings` class from `tests/test_detail.py` into `tests/test_granularity.py`, retargeted to `from plan_tool.granularity import parse_mixed_step_findings`. The moved tests reference the module-level fixtures `_STRUCTURAL_BLOCK_MIXED` and `_FINDINGS_BLOCK_NONE` (`tests/test_detail.py:_STRUCTURAL_BLOCK_MIXED`, `tests/test_detail.py:_FINDINGS_BLOCK_NONE`), which stay defined in `test_detail.py` for the `collect_detail_quality_findings` integration filter — **copy** both constants into `tests/test_granularity.py` (do not move them) so the relocated tests resolve them locally; a bare class move leaves them undefined → `NameError` and fails the `pytest tests/test_granularity.py` acceptance criterion:
- `test_mixed_block_yields_granularity_split_finding` — a `## Structural findings` MIXED-STEP block on a refactor step yields one rec; `source == "granularity-split"`, `severity == "medium"`, `step_id == step.id`, body carries the bullet desc.
- `test_granularity_split_is_not_apply_eligible` — `is_apply_eligible(rec)` is `False` and `triage_reason(rec)` contains `"split"` (case-insensitive); imports `is_apply_eligible, triage_reason` from `plan_tool.review`. This is the test that pins the `review.py:triage_reason` flip.
- `test_no_structural_block_yields_nothing` — a body with `## Findings` but no `## Structural findings` returns `[]`.
- `test_non_code_step_drops_block` — a MIXED-STEP block on a `non-code` step returns `[]`.
- `test_empty_desc_bullet_skipped` — `- MIXED-STEP:   ` (blank desc) returns `[]`.
- `test_bold_token_and_heading_casing_tolerated` — `## Structural Findings` + `- **MIXED-STEP**:` still parses to one `granularity-split` rec.
- `tests/test_detail.py` integration collect-pass filters — flip the literal in both `purity = [r for r in recs if r.source == "detail-purity"]` sites (in the live `collect_detail_quality_findings` integration tests) to `"granularity-split"`.

**New test (single-sourcing gate), in `tests/test_granularity.py`:**
- `test_detail_strip_and_kernel_share_one_regex` — `plan_tool.detail._STRUCTURAL_BLOCK_RE is plan_tool.granularity._STRUCTURAL_BLOCK_RE` (identity, not equality — an `==` test stays green if a future edit reintroduces a byte-identical second copy).

**Pass-unchanged-after gate:** every Bucket-1 test must stay green, unmodified beyond its import line, after the restructuring. The `granularity-split` source assertions in Bucket 2 are the only intended behavioral diffs.

## Acceptance criteria

- `parse_mixed_step_findings(_STRUCTURAL_BLOCK_MIXED, refactor_step, "orch")[0].source == "granularity-split"`, and its `id` is minted in the `granularity-split` namespace (`_make_rec_id(step.id, "granularity-split", desc)`).
- `plan_tool.detail._STRUCTURAL_BLOCK_RE is plan_tool.granularity._STRUCTURAL_BLOCK_RE` is `True`.
- `triage_reason(rec)` for a `granularity-split` rec contains `"split"` (case-insensitive); `is_apply_eligible(rec)` is `False`.
- `grep -rn "detail-purity" plan_tool/` returns zero hits (docs/plan files under `docs/` may still cite the old name — scope the gate to the package dir).
- `plan_tool/detail.py` no longer defines `_parse_purity_findings` or `_MIXED_STEP_BULLET_RE`; both `_STRUCTURAL_BLOCK_RE.sub("", raw)` strip sites remain.
- `detail --split` Phase B still proposes/applies splits for MIXED-STEP findings (the relocated split tests pass unchanged).
- `uv run pytest tests/test_detail.py tests/test_granularity.py -q` passes.

## References

- [typing — Support for type hints (Python 3.13)https: — keyword-only argument annotations and the `Callable[[str], str]` invoker/return shapes used by `parse_mixed_step_findings` and the `assess_granularity` delegation.
- [dataclasses — Data Classes (Python 3.13)https: — the `Recommendation` shape the kernel emits and the `GranularityEvidence` container the detail-stage delegation reads from.

## Deferred

- **Forcing detail's two call sites through `assess_granularity`'s wrapper** — intentionally not done; the single-path invariant is satisfied at the kernel, and routing the authoring loop through the wrapper would couple it to step 1's `GranularityEvidence` shape for no benefit.
- **The `granularity-merge` source and any merge reasoning** — out of scope; this step folds only the existing split/purity kernel. Merge advice is advisory-only and lands with the completeness audit (step 4); merge *execution* lives in `merge-steps-executor.md`.
- **Consolidating other single-sourcing patterns** (e.g. the `_atomic_write_text` copies) — unrelated; this step single-sources only `_STRUCTURAL_BLOCK_RE` between `detail` and `granularity`.
- **Removing the `## Structural findings` self-check from the authoring prompt** — the authoring prompt no longer requests it, but a model may still volunteer the block, so the defensive strip + parse stays.
