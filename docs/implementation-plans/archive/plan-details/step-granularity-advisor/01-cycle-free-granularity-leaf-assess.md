> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the cycle-free granularity advisor leaf (`plan_tool/granularity.py`)

## Summary

Create `plan_tool/granularity.py`, a new acyclic leaf that exposes the stateless `assess_granularity` contract, the `GranularityEvidence` evidence envelope, and the no-Claude deterministic split/merge detectors. The leaf imports only `plan_tool/schema.py` (`Plan`, `Step`, `ChangeType`) and `plan_tool/review.py`'s finding primitives (`Recommendation`, `_make_rec_id`, `Invoker`) — never CLI or orchestrator modules — so it sits below `create`/`detail`/`completeness`, which will import it in later steps. The key design decision: deterministic signals read only the `Plan` and never shell out; the `invoker` seam stays present but unused in step 1 and is consumed when the semantic prose judgment is folded in (step 2). On green, `assess_granularity` returns `list[Recommendation]` for each stage, split smells emit `source="granularity-split"` and merge smells `source="granularity-merge"`, both advisory (`severity="info"`, never apply-eligible), with all work covered by the new `tests/test_granularity.py`.

## Table of Contents

- [Summary](#summary) — what the leaf adds and the observable result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the scattered, split-only granularity reasoning this leaf unifies.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files; no edits.
- [Implementation](#implementation) — the contract, evidence envelope, detectors, sources, and import discipline.
- [Tests](#tests) — the unit cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — Python 3.13 docs for dataclasses, typing, and the import system.
- [Deferred](#deferred) — what later steps own (semantic fold, adapters, merge executor).

## Why

Granularity reasoning today is scattered and split-only. `create` leaves step count entirely to Claude's decomposition prompt, `detail` runs a MIXED-STEP purity self-check buried in its prompt template (parsed by `plan_tool/detail.py: _parse_purity_findings` via `_STRUCTURAL_BLOCK_RE`, emitted as `source="detail-purity"`), and `completeness` does no granularity reasoning at all. No merge reasoning exists anywhere, and there is no shared contract for "this step should be split / these steps should be merged." This step lays the reusable foundation — one stateless function and one finding shape — so steps 2–4 can feed each stage's own evidence into a single advisor instead of re-deriving granularity per stage. It is a pure-addition foundational step: it adds new behavior in a new file and changes nothing existing.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/granularity.py` — the advisor leaf: `assess_granularity`, `GranularityEvidence`, the deterministic split/merge detectors, source/severity constants.
  - `tests/test_granularity.py` — unit tests for the contract, both detector families, the no-Claude guarantee, rec shape, and import purity.
- **Existing files (edits only):** none. Do **not** edit `plan_tool/review.py`, `plan_tool/detail.py`, or `plan_tool/schema.py` in this step — granularity-`*` sources stay out of `review.py: APPLY_ELIGIBLE_SOURCES` and need no `triage_reason` special-case (see Implementation). TESTING.md's neutralization row for the new seam lands when the seam first becomes reachable (step 2), not here, and is outside this step's `files:`.

## Implementation

### `plan_tool/granularity.py` (new)

**Imports — keep the leaf acyclic.** Top-import only:
- `from plan_tool.schema import Plan, Step, ChangeType`
- `from plan_tool.review import Recommendation, _make_rec_id, Invoker`
- stdlib only otherwise: `from __future__ import annotations`, `from dataclasses import dataclass, field`, `from collections.abc import Mapping`, `from typing import Optional`, `import re`, `from pathlib import PurePosixPath`.
- **Do not** `import` anything from `plan_tool/shell.py`, `plan_tool/cli/*`, `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/launcher.py`, or `plan_tool/completeness_report.py`. The acceptance criterion "imports only schema and review" is authoritative; `review.py` never top-imports `granularity`, so importing its finding primitives is acyclic (review sits below the leaf).

**`GranularityEvidence` — the per-stage evidence envelope.**
- Declare as `@dataclass(frozen=True)` mirroring `review.py: Recommendation`'s frozen-dataclass style.
- One field for now: `detail_bodies: Mapping[int, str] = field(default_factory=dict)` — maps `step_id` → that step's authored implementation prose (the `## Structural findings` block detail emits).
- **Step 1's deterministic path does not read `detail_bodies`.** It is the forward contract surface the semantic fold (step 2) consumes. Declared now so steps 2–4 do not have to change the public signature. State this in the docstring so a reviewer does not read the empty consumption as a bug.

**`assess_granularity` — the stateless contract.**
- Signature:
  ```python
  def assess_granularity(
      plan: Plan,
      *,
      stage: str,
      evidence: GranularityEvidence,
      invoker: Optional[Invoker] = None,
  ) -> list[Recommendation]:
  ```
- **`invoker` defaults to `None`, not a real-CLI shell-out** — this deviates from the plan body's `invoker: Invoker = ...` sketch on purpose, to satisfy the strict "imports only schema and review" criterion (a real default would force a `plan_tool/shell.py` import). The adapters in `create`/`detail`/`completeness` inject the concrete invoker (e.g. `review.py: shell_review_invoker`, shape `Callable[[str], tuple[int, str]]`) when a stage needs prose judgment. The `Invoker` type alias is reused from `review.py` (`Callable[[str], tuple[int, str]]`) — do not re-declare it locally.
- **Validate `stage`** against `_VALID_STAGES = frozenset({"create", "detail", "completeness"})`; raise `ValueError` on anything else. `stage` does not branch the deterministic output in step 1 (the same split+merge battery runs for every stage because both read only plan structure); it is validated now and reserved for semantic dispatch later.
- Body: concatenate `_split_findings(plan)` + `_merge_findings(plan)` and return the list. The `invoker` is **never called** on the deterministic path — pin this with a negative test (see Tests).

**Sources and severity (module constants).**
- `GRANULARITY_SPLIT_SOURCE = "granularity-split"`, `GRANULARITY_MERGE_SOURCE = "granularity-merge"`.
- `_GRANULARITY_SEV = "info"` — advisory, matching `review.py: _TEST_STRATEGY_INCONSISTENT_SEV`. Severity is the belt-and-suspenders rc-0 guarantee; the **primary** guarantee is structural — steps 2–4 never pass granularity-`*` recs into a blocking gate. This step only mints the recs.
- **Keep both sources out of `review.py: APPLY_ELIGIBLE_SOURCES`** (do not edit that file). `review.py: is_apply_eligible` then returns `False` for them, and `review.py: triage_reason` falls through to its generic "structural diagnostic — not auto-fixable" branch with no new special-case — the same posture step 2 used for `suppression-shape`/`self-referential`, and unlike `detail-purity`'s dedicated branch.
- Mint every id with `_make_rec_id(step_id, source, fingerprint)` — it folds the source into the id, so the source argument must be the exact `GRANULARITY_SPLIT_SOURCE`/`GRANULARITY_MERGE_SOURCE` constant, never a stray literal.

**Deterministic split detectors (per step → `granularity-split`).** The foundational rule this step adds is "flag a single step that carries two concerns." It is the no-Claude sibling of detail's prose MIXED-STEP judgment (`plan_tool/detail.py: _parse_purity_findings`); step 2 folds that prose kernel behind the same `granularity-split` source so the two never fork. Implement as small named predicates, each independently testable:
- `_title_mixes_refactor_and_feature(step)` — title contains a verb from `_REFACTOR_VERBS` (e.g. `refactor`, `extract`, `move`, `rename`, `consolidate`, `inline`, `relocate`) **and** one from `_FEATURE_VERBS` (e.g. `add`, `implement`, `introduce`, `create`, `build`, `wire`). Precision over recall — require both present. **Non-trip anchor:** this plan's own step-1 title ("Add … contract, GranularityEvidence, and deterministic split/merge signals") carries a feature verb ("Add") but no refactor verb, so it must not trip. Pin both a trip and this non-trip case in tests and the docstring.
- `_title_conjoins_two_clauses(step)` — split the title on `" and "`/`"; "` and trip only when **both** sides independently begin with an action verb (the union of the two verb sets). A comma-led noun enumeration ("…, and deterministic split/merge signals") has no verb on the right side, so step 1's title does not trip — pin it as the non-trip anchor. Mark precision over recall in the docstring.
- `_step_spans_unrelated_areas(step)` — over `step.all_files` (not `step.files` — `creates` must count), derive each path's "area" via `PurePosixPath` (top two segments; fold a `tests/...` mirror back to its source area). Trip only when ≥2 distinct **non-test** areas remain, so the ordinary impl+test pairing does not false-positive.
- Each tripped predicate yields one `Recommendation(source=GRANULARITY_SPLIT_SOURCE, severity=_GRANULARITY_SEV, step_id=step.id, …)` with a fingerprint naming the predicate (e.g. `f"split:mixed-verbs:{step.id}"`), a short `title`, a `body` naming the smell and the offending titles/files, and a `suggested_action` ("Consider splitting step N …"). De-duplicate so one step tripping multiple predicates does not emit redundant ids.

**Deterministic merge detectors (pairwise / plan-level → `granularity-merge`).** Iterate `plan.steps`:
- `_merge_signal_identical_file_sets(plan)` — two `depends_on`-adjacent steps (the later directly depends on the earlier) whose `frozenset(step.all_files)` are equal and non-empty → merge smell.
- `_merge_signal_trivial_refactor_feeding_one_feature(plan)` — a `ChangeType`-refactor step with a small footprint whose **only** dependent in the plan is exactly one feature step → merge smell. Compare against `schema.py: ChangeType` members; use `Step.change_type`.
- A merge `Recommendation` describes two steps but `Recommendation.step_id` is a single `Optional[int]` — set it to the lower member id and encode both ids in the fingerprint and `body` (e.g. `_make_rec_id(lo_id, GRANULARITY_MERGE_SOURCE, f"merge:{lo_id}+{hi_id}")`). `suggested_action`: "Consider merging steps N and M".

## Tests

Test file: `tests/test_granularity.py`. Build `Plan`/`Step` instances directly from `plan_tool.schema` (mirror the inline-construction style of `tests/test_parser.py`); no fixture `.md` files. Stub invokers inline; never spawn a real backend (`tests/conftest.py`'s autouse gate raises otherwise).

- `test_returns_recommendations_for_each_stage` — `assess_granularity` returns `list[Recommendation]` for `stage` in `"create"`, `"detail"`, `"completeness"`.
- `test_invalid_stage_raises` — an unknown `stage` raises `ValueError`.
- `test_mixed_refactor_feature_title_yields_split` — a step titled with both a refactor and a feature verb yields one `source="granularity-split"` rec.
- `test_title_conjunction_yields_split` — a title joining two verb clauses with "and" yields a split rec.
- `test_unrelated_file_span_yields_split` — a step whose `creates`/`files` touch two non-test areas yields a split rec.
- `test_step1_self_title_does_not_trip_split` — the plan's own step-1-style title (single feature verb + comma enumeration) yields **no** split rec (the non-trip anchor).
- `test_single_concern_step_yields_no_split` — a clean, single-area step yields nothing.
- `test_identical_file_sets_adjacent_yields_merge` — two `depends_on`-adjacent steps with equal `all_files` yield one `source="granularity-merge"` rec.
- `test_trivial_refactor_feeding_one_feature_yields_merge` — a small refactor step feeding exactly one feature step yields a merge rec.
- `test_non_adjacent_or_distinct_files_no_merge` — unrelated steps yield no merge rec.
- `test_deterministic_path_never_calls_invoker` — pass an invoker stub that raises on call; assert deterministic findings still return and the stub is never invoked (proves the no-Claude guarantee structurally).
- `test_rec_shape_and_sources` — emitted recs use exactly `"granularity-split"`/`"granularity-merge"`, `severity="info"`, ids minted via `_make_rec_id`; `review.is_apply_eligible(rec)` is `False` and `review.triage_reason(rec)` returns the generic structural text.
- `test_ids_are_stable` — assessing the same plan twice yields identical rec ids (content-addressed via `_make_rec_id`).
- `test_import_purity` — parse `plan_tool/granularity.py`'s AST (or inspect its imports) and assert every `from plan_tool.* import` targets only `plan_tool.schema` or `plan_tool.review` — no `cli`, `create`, `detail`, `launcher`, `completeness_report`, or `shell`.

### Test-creation order (feature step)

This is a **feature** step. Write each test above alongside the implementation of the predicate/contract it covers, smallest first: the contract guards (`stage` validation, return type), then split detectors, then merge detectors, then the no-Claude negative test, rec-shape, and import-purity. **Green-before-done gate:** every test in `tests/test_granularity.py` must pass (`uv run pytest tests/test_granularity.py -q`) before this step is considered finished.

## Acceptance criteria

- `plan_tool/granularity.py` exists and imports only from `plan_tool.schema` and `plan_tool.review` (plus stdlib) — verifiable by the import-purity test / an acyclicity check.
- `assess_granularity(plan, stage=…, evidence=…)` returns `list[Recommendation]` for each of `"create"`, `"detail"`, `"completeness"`; an unknown stage raises `ValueError`.
- A step with a refactor+feature title, a two-clause title conjunction, or an unrelated `files`/`creates` span yields a `source="granularity-split"` rec **with no invoker call**.
- Two `depends_on`-adjacent steps with identical file sets, or a trivial refactor feeding exactly one feature step, yield a `source="granularity-merge"` rec.
- Granularity recs carry `severity="info"`, are not in `review.py: APPLY_ELIGIBLE_SOURCES` (`is_apply_eligible` returns `False`), and rely on the generic `triage_reason` branch (no `review.py` edit).
- Rec ids are deterministic across repeated assessments of the same plan.
- `uv run pytest tests/test_granularity.py -q` is green.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — for declaring `GranularityEvidence` as a frozen dataclass with a `field(default_factory=dict)` default, mirroring `review.Recommendation`.
- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3.13/library/typing.html) — for the keyword-only contract annotations and the reused `Invoker = Callable[[str], tuple[int, str]]` shape.
- [Python Language Reference — The import system (Python 3.13)](https://docs.python.org/3.13/reference/import.html) — for keeping `granularity.py` an acyclic leaf importing only `schema` and `review`.

## Deferred

- **Semantic prose judgment** — folding `plan_tool/detail.py: _parse_purity_findings` behind the advisor's `granularity-split` source (so detail's MIXED-STEP check and the escalation bridge share one path) lands in step 2, which also wires consumption of `GranularityEvidence.detail_bodies` via deterministic parsing, leaving the `invoker` seam unused.
- **Stage adapters** — feeding `create`'s decompose-time evidence (step 3) and `completeness`'s cross-step audit (step 4) are separate steps that import this leaf.
- **TESTING.md neutralization row** for the granularity invoker seam — added when the seam first becomes reachable (step 2); TESTING.md is outside this step's `files:`.
- **Merge execution** — the `plan-tool merge` executor has landed; `granularity-merge` stays advisory-only because no auto-escalation bridge routes a merge finding to it, so the operator hand-runs `plan-tool merge`.
- **Verb-list / area-heuristic tuning** — the `_REFACTOR_VERBS`/`_FEATURE_VERBS` sets and the file-area predicate are deliberately precision-first; broadening recall is left to follow-up tuning once real-plan false-positive rates are observed.
