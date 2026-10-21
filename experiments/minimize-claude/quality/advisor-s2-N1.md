# Step 2 — Fold detail's MIXED-STEP purity judgment into the granularity leaf as `granularity-split` (single path)

## Summary

Relocate `detail.py`'s LLM-judged mixed-step kernel — `_parse_purity_findings` plus its two regexes `_STRUCTURAL_BLOCK_RE` / `_MIXED_STEP_BULLET_RE` — into the new `plan_tool/granularity.py` leaf as a public `parse_mixed_step_findings`, and relabel the finding source `detail-purity` → `granularity-split` (the field **and** the `_make_rec_id` id-namespace argument). Both `detail.py` call sites and `granularity.assess_granularity(stage="detail")` funnel through that one relocated kernel, satisfying the plan's "single path, not forked" risk mitigation. The load-bearing decision: relocate the existing kernel (don't re-implement it behind the advisor) and keep `detail.py`'s `## Structural findings` defensive **strip** at its two sites by importing the single relocated `_STRUCTURAL_BLOCK_RE` — detection moves to the leaf, sanitization stays at the consumer. On green, a mixed-step authoring response yields a `source="granularity-split"` rec, `detail --split` Phase B consumes it byte-for-byte as before, and `review.triage_reason` still returns the "split into type-pure steps" message.

## Table of Contents

- [Why](#why) — what's scattered today and why the fold matters now
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files plus the required `review.py` relabel
- [Implementation](#implementation) — the relocation, the relabel, the single-path wiring, and the strip-stays split
- [Tests](#tests) — characterization tests to pin first, partitioned into pass-unchanged vs one-line-relabel buckets
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — import-system, dataclasses, typing docs for the leaf + Recommendation shape
- [Deferred](#deferred) — merge logic, escalation-bridge wiring, and the create/completeness stage adapters

## Why

Step-purity reasoning lives buried inside `detail.py` today: `_parse_purity_findings` parses the `## Structural findings` block from a detail-quality response into `source="detail-purity"` recs, and `detail --split` Phase B (`plan_tool/detail.py: if allow_split and mixed_steps and sys.stdin.isatty():`) is the sole consumer. The plan's **Architecture** section makes `plan_tool/granularity.py` the one stage-agnostic home for granularity findings; the plan's first **Risk** is exactly that purity logic could *fork* into two code paths if duplicated behind the advisor rather than folded. Step 1 ships the leaf with `assess_granularity` + deterministic signals but **not** the semantic kernel; this step moves the kernel in and relabels its source so every downstream consumer (Phase B now, the escalation bridge later) reads one `granularity-split` source from one implementation.

## Files (creates vs edits)

- **New files:** none. (`plan_tool/granularity.py` and `tests/test_granularity.py` are *created by step 1* and **edited** here — they exist once step 1 lands.)
- **Existing files (edits only):**
  - `plan_tool/granularity.py` — add `parse_mixed_step_findings(raw, step, plan_name)`; add the relocated module-level `_STRUCTURAL_BLOCK_RE` and `_MIXED_STEP_BULLET_RE`; wire the `assess_granularity(stage="detail")` branch to delegate to the kernel; top-level `from plan_tool.review import Recommendation, _make_rec_id`.
  - `plan_tool/detail.py` — delete `_parse_purity_findings`, `_STRUCTURAL_BLOCK_RE`, `_MIXED_STEP_BULLET_RE` and their preceding comment block; import `_STRUCTURAL_BLOCK_RE` and `parse_mixed_step_findings` from `plan_tool.granularity`; repoint both call sites (`collect_detail_quality_findings` and the `generate_detail` authoring-attempt loop).
  - `tests/test_detail.py` — move `TestParsePurityFindings` out to `tests/test_granularity.py`; flip the source literal in the surviving `collect_detail_quality_findings` tests; drop `_parse_purity_findings` from the `from plan_tool.detail import (...)` block.
  - `tests/test_granularity.py` — receive the moved kernel tests (import path + source literal flipped) and add the `assess_granularity(stage="detail")` delegation + shared-regex tests.
  - **`plan_tool/review.py` (required-but-undeclared edit).** `review.py: triage_reason` special-cases `if rec.source == "detail-purity":`. A source relabel that misses this branch silently regresses it to the generic "structural diagnostic" message and breaks the `"split" in triage_reason(rec).lower()` assertion. Update the literal and the message text. Add a mirror test in `tests/test_review.py`. Flag in the commit message as outside the declared `files:`.

## Implementation

### `plan_tool/granularity.py` (edit — receive the kernel)

- **Add the two regexes at module level**, relocated verbatim from `detail.py`:
  - `_STRUCTURAL_BLOCK_RE` — `^#{1,6}\s*Structural findings\s*$\n?(.*?)(?=^#{1,6}\s|\Z)` with `MULTILINE | DOTALL | IGNORECASE`.
  - `_MIXED_STEP_BULLET_RE` — `^\s*[-*]\s*(?:\*\*)?MIXED-STEP(?:\*\*)?\s*[:\-]\s*(.+?)\s*$` with `MULTILINE | IGNORECASE`.
  - These are now **single-sourced here**; `detail.py` imports `_STRUCTURAL_BLOCK_RE` for its own strip use (see the strip-stays split below), mirroring the leaf-owns-detection / consumer-owns-sanitization pattern.
- **Add `parse_mixed_step_findings(raw: str, step: Step, plan_name: str) -> list[Recommendation]`** — the relocated `_parse_purity_findings` body, byte-identical except the two relabels below:
  - `source="granularity-split"` (was `"detail-purity"`).
  - `id=_make_rec_id(step.id, "granularity-split", desc)` (was `"detail-purity"`). **Both must change together** — `review._make_rec_id` folds its 2nd arg into the id hash (`review.py: _make_rec_id`), so leaving the old literal there mints ids in the `detail-purity` namespace while the rec carries the new source, desyncing any id-keyed dedup/union map.
  - Keep the `if step.change_type == ChangeType.NON_CODE: return []` guard, the empty-`desc` skip, the `body` / `title` / `suggested_action` text unchanged.
  - **Relabel the relocated docstring prose too.** `_parse_purity_findings`'s docstring (`detail.py`, ~lines 788 & 795) hardcodes `source="detail-purity"` and "`detail-purity` is absent from `APPLY_ELIGIBLE_SOURCES`"; relocating it verbatim would leave `detail-purity` literals in `plan_tool/` and fail the `grep -rn "detail-purity" plan_tool/` → zero-hits criterion. Relabel both docstring mentions `detail-purity` → `granularity-split` as part of the move.
- **Drop the body-local lazy import.** The original used an in-body `from plan_tool.review import Recommendation, _make_rec_id` to dodge the `review↔detail` cycle. `granularity.py` is a leaf **below** `review`; `review.py` never top-imports `granularity` (confirm at HEAD — grep `review.py` for `import granularity`). So promote it to a normal module-top `from plan_tool.review import Recommendation, _make_rec_id`. Carrying the lazy form into the leaf would be dead defensiveness for a cycle that does not exist here.
- **Wire `assess_granularity(stage="detail")` to delegate to the kernel.** This is the "single path" payoff: the advisor's detail branch and `detail.py` both reach the same `parse_mixed_step_findings`.
  - **Pin to step 1's declared seam — step 1 is unimplemented at HEAD.** `granularity.py` does not exist on disk yet (`assess_granularity`, `GranularityEvidence`, the `Invoker` shape are defined in step 1's detail). Before wiring, confirm step 1's shipped signature `assess_granularity(plan, *, stage, evidence, invoker=...) -> list[Recommendation]` and the `GranularityEvidence` field that carries the authored detail prose. If step 1 shipped a different field name or arity, adapt the delegation to the real seam — do **not** author against field names that exist only in this prose.
  - **Delegation shape:** in the `stage == "detail"` branch, unpack the authored prose + step from `evidence` and `return parse_mixed_step_findings(<raw prose>, <step>, <plan name>)`. The kernel is the single implementation; `assess_granularity` is a thin entry wrapper over it.
- **Single-path framing (load-bearing):** the invariant is *one kernel implementation*, not *one entry wrapper*. `detail.py`'s two call sites call `parse_mixed_step_findings` **directly** with the simple `(raw, step, plan_name)` signature — they are **not** forced through `assess_granularity`, so the authoring loop stays decoupled from step 1's `GranularityEvidence` payload shape. `assess_granularity(stage="detail")` delegating to the same kernel is what makes the advisor the single home for step 3/step 4 consumers.

### `plan_tool/detail.py` (edit — consume from the leaf)

- **Delete** `_parse_purity_findings`, `_STRUCTURAL_BLOCK_RE`, `_MIXED_STEP_BULLET_RE`, and the preceding `# LLM-judged step-purity ...` comment block.
- **Add imports** from the leaf: `from plan_tool.granularity import _STRUCTURAL_BLOCK_RE, parse_mixed_step_findings`. No import cycle — `granularity` is a leaf below `detail`; `detail` already top-imports peers like `launcher`. (Do **not** also import `_MIXED_STEP_BULLET_RE` — `detail.py` never used it directly; only the kernel did.)
- **Repoint call site 1 — `collect_detail_quality_findings`:** the `purity = _parse_purity_findings(raw, step, plan_name)` call becomes `purity = parse_mixed_step_findings(raw, step, plan_name)`.
- **Repoint call site 2 — the `generate_detail` authoring-attempt loop:** the `purity_candidate = _parse_purity_findings(raw, step, plan_slug)` call becomes `purity_candidate = parse_mixed_step_findings(raw, step, plan_slug)`.
- **The `## Structural findings` strip STAYS in `detail.py`** — this is the leaf-detects / consumer-sanitizes boundary. Both `raw_for_findings = _STRUCTURAL_BLOCK_RE.sub("", raw)` (in `collect_detail_quality_findings`, before the `## Findings` parse) and the `raw = _STRUCTURAL_BLOCK_RE.sub("", raw)` in the `generate_detail` attempt loop (so the block never lands in the written file) remain in `detail.py`, now consuming the **imported** `_STRUCTURAL_BLOCK_RE`. The strip is a `detail`-only "never leak a structural bullet into a `claude` finding / the written body" concern; only detection (parse → finding) belongs in the leaf. Both the leaf's parse and `detail`'s strip use the one regex — no second copy.
- The Phase B block (`if allow_split and mixed_steps and sys.stdin.isatty():`) and `mixed_steps.append((step.id, pf))` are **untouched** — they consume `Recommendation` objects, which are source-agnostic at the consumption point.

### `plan_tool/review.py` (required edit — relabel the dispatch branch)

- **Update `triage_reason`'s special-case:** `if rec.source == "detail-purity":` → `if rec.source == "granularity-split":`, and update the returned string's `"detail-purity: structural — ..."` prefix to `"granularity-split: structural — ..."`. Keep the "the fix is to split it into type-pure steps, not an apply edit" tail so the `"split" in triage_reason(rec).lower()` contract holds.
- **`APPLY_ELIGIBLE_SOURCES` is a deliberate NON-edit.** `detail-purity` is absent from `review.py: APPLY_ELIGIBLE_SOURCES`; `granularity-split` must stay absent too — the finding remains advisory (structural, never dispatched to `apply_finding`). Adding it would flip mixed-step findings from advisory to mechanically-applied. State this in the detail/commit as the load-bearing non-edit.

### Foundational logic & shared-location scan

- **Foundational logic of this step:** *parse the `## Structural findings` MIXED-STEP block into a `granularity-split` Recommendation* — one kernel, one source string.
- **Confirmed full consumer set of the `detail-purity` literal at HEAD** (grep `detail-purity` across `plan_tool/`): exactly two production sites — the producer `detail.py: _parse_purity_findings` (relocated) and `review.py: triage_reason` (relabeled). No membership-set or other string-dispatch consumer exists. `is_structural` / an escalation router do **not** exist at HEAD (the `escalate-structural-findings-to-split.md` plan is unimplemented — confirm with `grep is_structural plan_tool/`), so there is no third literal site to update.
- **`scenario_capture.py: CATEGORY_MIXED_STEP = "mixed-step"`** is a *capture-category* token, **not** the rec `source` — leave it unchanged. It is a different axis (scenario capture vs finding source); do not conflate the relabel with it.

## Tests

Mirror convention: `plan_tool/granularity.py` → `tests/test_granularity.py`, `plan_tool/detail.py` → `tests/test_detail.py`, `plan_tool/review.py` → `tests/test_review.py`.

- **`tests/test_granularity.py`** (receives the moved kernel tests, import path + source literal flipped):
  - `test_mixed_block_yields_granularity_split_finding` — a `## Structural findings` / MIXED-STEP block → one rec with `source == "granularity-split"`, `severity == "medium"`, `step_id == step.id`, body carries the bullet text.
  - `test_granularity_split_is_not_apply_eligible` — `is_apply_eligible(rec) is False` and `"split" in triage_reason(rec).lower()`.
  - `test_no_structural_block_returns_empty` — a findings-only response → `[]`.
  - `test_non_code_step_drops_bullet` — `ChangeType.NON_CODE` step → `[]`.
  - `test_empty_bullet_skipped` — `- MIXED-STEP:   ` (whitespace desc) → `[]`.
  - `test_bold_token_and_heading_casing_tolerated` — `## Structural Findings` + `- **MIXED-STEP**:` → one rec, `source == "granularity-split"`.
  - `test_assess_granularity_detail_delegates_to_kernel` — `assess_granularity(plan, stage="detail", evidence=<mixed prose>)` returns the same single `granularity-split` rec the kernel does (single-path proof). *Pin the evidence construction to step 1's `GranularityEvidence`; adapt at HEAD.*
  - `test_detail_strip_and_kernel_share_one_regex` — assert `plan_tool.detail._STRUCTURAL_BLOCK_RE is plan_tool.granularity._STRUCTURAL_BLOCK_RE` (single-source guarantee — the strip and the parse cannot drift).
  - Carry the fixtures the moved tests need: `_STRUCTURAL_BLOCK_MIXED`, `_FINDINGS_BLOCK_NONE`, and a `_write_detail_plan`-equivalent (or import the shared helper).
- **`tests/test_detail.py`** (surviving live-path tests, literal flipped only):
  - `test_mixed_step_surfaces_and_defers_in_merged_findings` — `collect_detail_quality_findings` filter `r.source == "granularity-split"` (was `"detail-purity"`); still asserts no `claude` rec carries it.
  - `test_structural_block_never_leaks_into_findings` (both param ids) — purity filter flipped to `"granularity-split"`; the `MIXED-STEP not in claude[0].body` / `Structural findings not in claude[0].body` strip assertions stay byte-identical.
  - Remove `_parse_purity_findings` from the `from plan_tool.detail import (...)` block; `TestParsePurityFindings` no longer lives here.
- **`tests/test_review.py`:**
  - `test_triage_reason_granularity_split_message` — `triage_reason(rec)` for a `granularity-split` rec returns the split message and contains `"split"`.
  - `test_granularity_split_not_apply_eligible` — `granularity-split` absent from `APPLY_ELIGIBLE_SOURCES`.

### Test-creation order (refactor step)

This is a **behavior-preserving refactor + an intentional source-string relabel.** Write the characterization tests **first**, against the current `detail-purity` behavior, run them green, then perform the relocation/relabel. Partition them into two explicit buckets:

- **Bucket 1 — pass UNCHANGED (the relocation half).** These must stay byte-identical and green after the change; any edit to them signals unintended drift:
  - The two `detail.py` strip tests: `test_structural_block_never_leaks_into_findings` (both orderings) and the authoring-loop file-strip test (`Structural findings`/`MIXED-STEP` absent from the written file).
  - The Phase B split tests (`_split_is_safe` / `_confirm_split` / `_migrate_downstream_details_after_split` flows) — they consume `Recommendation`s, not the source literal.
- **Bucket 2 — expect EXACTLY a one-line edit (the relabel/relocation half).** The only allowed change per test is the source literal `detail-purity` → `granularity-split` and/or the import path `plan_tool.detail` → `plan_tool.granularity`:
  - The moved `TestParsePurityFindings` cases (import path + literal).
  - The `collect_detail_quality_findings` purity-filter tests (literal only).
  - `triage_reason` test (literal only).
- **Red flag:** any edit to a Bucket-1 test, OR any change beyond the single literal/import line in a Bucket-2 test, means behavior drifted — stop and reconcile.

## Acceptance criteria

- `plan_tool.granularity.parse_mixed_step_findings(raw, step, plan_name)` returns a rec with `source == "granularity-split"` and an id whose namespace segment is `granularity-split` for a MIXED-STEP block on a code step; `[]` for a `NON_CODE` step or an empty/absent block.
- `grep -rn "detail-purity" plan_tool/` returns **zero** hits in production code (only `docs/` plan files may still reference the old name).
- `plan_tool.detail._STRUCTURAL_BLOCK_RE is plan_tool.granularity._STRUCTURAL_BLOCK_RE` (the strip and the parse share one regex object).
- `review.triage_reason(rec)` for a `granularity-split` rec contains `"split"`; `is_apply_eligible(rec) is False`; `"granularity-split" not in review.APPLY_ELIGIBLE_SOURCES`.
- `assess_granularity(plan, stage="detail", evidence=<mixed prose>)` returns the same single `granularity-split` rec as the direct kernel call.
- `detail --split` Phase B still flags and splits a mixed step (its tests pass unchanged).
- `uv run pytest tests/test_granularity.py tests/test_detail.py tests/test_review.py -q` is green; the full suite (`uv run pytest -m "not integration" tests/ -q`) is green.
- `plan_tool.granularity` imports nothing from `plan_tool.detail` (leaf stays acyclic), and this step adds no import beyond `schema`/`review` to it (whatever else step 1 shipped stays).

## References

- [Python Language Reference — The import system (Python 3.13)https: — Confirms why `granularity.py` can top-import `review` (leaf below it) and why the body-local cycle-dodge is droppable on relocation.
- [dataclasses — Data Classes (Python 3.13)https: — Reference for the `Recommendation` shape the relocated kernel constructs.
- [typing — Support for type hints (Python 3.13)https: — Spec for the `parse_mixed_step_findings` / `assess_granularity` annotations and the keyword-only `stage`/`evidence` parameters.

## Deferred

- **`granularity-merge` source and merge smells** — advisory-only merge reasoning is step 1's/the plan's scope, with no executor; not produced by the detail stage. Out of this step.
- **`create` and `completeness` stage adapters** — steps 3 and 4 wire `assess_granularity(stage="create")` and `(stage="completeness")`. This step folds only the `detail` stage.
- **Escalation-bridge wiring (`is_structural` / `escalate_to_split` routing of `granularity-split`)** — the `escalate-structural-findings-to-split.md` plan is unimplemented at HEAD; its line 157 deferred the `detail-purity` → `granularity-split` rename "until the advisor lands" — this step performs that rename, but routing the renamed finding to the split engine remains that plan's job.
- **Consolidating `_make_rec_id` callers / a shared rec-builder** — not in scope; the kernel keeps its inline `Recommendation(...)` construction.
