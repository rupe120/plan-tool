> **Replaced**: this file has been superseded by `docs/implementation-plans/2-code-reveals-a-split-detector.md`.
> Preserved here for history; do not edit.

## Overview

Add a new deterministic, code-grounded split detector to the `reconcile` lane. It emits an advisory `granularity-split` recommendation for a single non-`DONE` step whose `heuristic_already_done` hits reveal it fuses two separable concerns (part already built across multiple files, part not) and should split along the built/un-built seam. This is the **inverse** of the existing code-grounded merge producer `_reground_already_built_recommendation` and completes the **last open arm** of BACKLOG **#70** ("Code-reveals-a-split detection"). The detector is **advisory `info` only**: it never mutates, never auto-dispatches to the split bridge, and never flips an exit code. It reuses existing machinery (the `heuristic_already_done` hit set, the `granularity-split` literal + `Recommendation` shape, the split-branch `triage_reason`) — no new code-scanning infrastructure, no bridge changes, and no new source token.

## Problem statement

`reconcile` audits a plan **against current code** and already has a code-grounded **merge/re-ground** producer — `_reground_already_built_recommendation` (`review.py:3880`) — which fires when **≥2 distinct steps** look already-built and re-baselines the set. Its **inverse has no producer**: a **single** step whose code reveals it spans **two separable concerns** should be **split**, but nothing detects that from code today. The only split producers are the **static** `granularity.py` detectors (which read plan structure / titles only, never code) and the completeness MIXED-STEP → `escalate_to_split` path. #70's last open arm is precisely a *code-grounded* split producer mirroring the re-ground sibling; until it lands, reconcile can surface a step that must split but has no way to say so.

## Architecture

The producer plugs into `extract_recommendations`'s `if reconcile_lane and step_filter is None:` block (`review.py:3407`), alongside `_reground_already_built_recommendation`.

**Trigger (decidable, conservative built-vs-unbuilt boundary in ONE step).** Fire **one** advisory finding for a single **non-`DONE`** step when, among that step's `heuristic_already_done` hits, there are **≥2 distinct `file` values** (the step's code touches ≥2 separable already-built files) **AND ≥1 declared `step.files` entry has no hit** (a genuinely un-built portion remains). That co-occurrence is the decidable signal that the step fuses ≥2 concerns and should split along the built/un-built seam. Count distinct files with a set comprehension **mirroring the re-ground builder's distinct-step count** (`{hit.file for hit in step_hits}`, cf. `review.py:3897`). Precision over recall — one finding per qualifying step, or none.

**Routing (reuse the `granularity-split` literal at `severity="info"`).** Emit `source="granularity-split"` as a **hard-coded literal, not imported** — `review.py` must not import `granularity.py` (the cycle rule, already how `STRUCTURAL_SOURCES` duplicates the literal at `review.py:4190`) — with `severity="info"`, `step_id=<the step>`, and remedy prose pointing at `plan-tool split`. `info` + `granularity-split` gives `is_structural=True` (split-branch `triage_reason`, deferred, pointed at `plan-tool split`) but is **NOT** auto-dispatched: `split_escalation_target` (`review_walk.py:352`) gates auto-dispatch on `severity == "medium"` **and** the source being in `extra_apply_sources`, so an `info` finding stays recommend-only — exactly like the deterministic `info` split hints granularity already emits. Do **not** use a neutral literal (`granularity-merge`); its directive grammar is merge/reground, the wrong family for a split.

**Stay OUT of `APPLY_ELIGIBLE_SOURCES`.** `STRUCTURAL_SOURCES` is disjoint from `APPLY_ELIGIBLE_SOURCES` by design (pinned by `test_structural_sources_disjoint_from_apply_eligible`, `test_review.py:8946`). This producer changes neither set.

**Reconcile-lane double gate (same as re-ground).** The shared completeness/run-gate builder (`collect_deterministic_findings`, `review.py:4574`) calls `extract_recommendations` with `heuristic_hits=[]` **and** `reconcile_lane=False`, so the producer stays off every non-reconcile surface by both guards (empty hits → no signal; `reconcile_lane=False` → the block never runs). `review_plan_full` (`review.py:6062`) passes `reconcile_lane=True`.

**Distinct rec id, own remedy prose.** Mint the id like the re-ground builder (`_make_rec_id(step_id, "granularity-split", fingerprint)` with a `code-reveals-split:<step_id>:<sorted files>` fingerprint) so distinct triggers yield distinct ids while the shared source routes correctly. Carry the finding's own title/body/suggested prose (name the built files, the un-built remainder, and `plan-tool split`); the neutral/structural `triage_reason` branch names no remedy.

**Shape.** Add `_code_reveals_split_recommendation(heuristic_hits, plan, *, plan_name)` returning `Optional[Recommendation]` per qualifying step (or a list, one per step — pick to mirror the re-ground builder's shape).

**Seams already in place (verify before extending):** `review.py` — `heuristic_already_done` (`:835`, returns `HeuristicHit(step_id, file, symbol, pattern)` at `:268`), `_reground_already_built_recommendation` (`:3880`), the emit block (`:3407`), `extract_recommendations` (`:3314`), `review_plan_full` (`:6062`), `STRUCTURAL_SOURCES` / `is_structural` (`:4195`/`:4296`), `triage_reason` split branch (`:4373`), `APPLY_ELIGIBLE_SOURCES` (`:4157`), `_make_rec_id`. `review_walk.py` — `split_escalation_target` (`:352`), `is_apply_as_finding` (`:316`, structural → False). `granularity.py` — `GRANULARITY_SPLIT_SOURCE = "granularity-split"` (`:41`), reuse the literal value only.

## Out of scope

- **Any mutation / auto-split.** Recommend-only; the finding points at `plan-tool split`. No change to `escalate_to_split`, the split bridge, or `split_escalation_target`.
- **A new source token.** Reuse `granularity-split`; introduce no `code-split` literal.
- **New code-scanning.** The trigger reads only the existing `heuristic_already_done` hit list + `step.files`; no AST/diff/git analysis.
- **Touching the static `granularity.py` detectors** or importing them into `review.py`.
- **Promoting to `medium`/blocking or into `extra_apply_sources`** — advisory `info` only.

## Risks

- **False "must split" calls** on superficial multi-file symbol overlap — keep it advisory (`info`), conservative (the built-AND-unbuilt co-occurrence, not mere multi-file), and reconcile-lane-only. `heuristic_already_done`'s coarse first-hit-per-file matching means "≥2 distinct files" is a proxy, not proof — precision-over-recall framing and recommend-only routing bound the blast radius.
- **Cycle regression** — importing `granularity` into `review.py` for the literal would re-introduce the forbidden edge; hard-code the string, as `STRUCTURAL_SOURCES` already does.
- **Lane leak** — an unconditional emit would surface the finding on completeness/review; respect the `reconcile_lane and step_filter is None` + non-empty-hits double gate.

## Testing

Mirror the re-ground test suite in `tests/test_review.py`:
- **`TestCodeGroundedSplitBuilder`** — trigger boundaries: no hits, single file, ≥2 files but all declared files hit → **no** finding; ≥2 files + an un-hit declared file → finding; `DONE` step skipped.
- **A gating class** — asserts the producer emits only in the reconcile lane + `step_filter is None`, and is omitted by `collect_deterministic_findings`.
- **A `review_plan_full` integration test** — surfaces the advisory `granularity-split` finding end-to-end through reconcile.
- Assert the finding stays `info` (not auto-dispatched) via the `split_escalation_target` boundary (`test_review_walk.py:2865`-style) and stays out of `APPLY_ELIGIBLE_SOURCES`.

Existing suites that must stay green: `test_structural_sources_disjoint_from_apply_eligible` (`test_review.py:8946`), the re-ground finding tests, the static granularity detector tests, and every existing structural-routing test.

## Acceptance criteria

- `reconcile` (via `review_plan_full`) surfaces an advisory `granularity-split` finding for a single non-`DONE` step whose `heuristic_already_done` hits span **≥2 distinct files** while **≥1 declared file has no hit** — scoped to the reconcile lane (absent from `collect_deterministic_findings` / completeness / review / run-gate paths), `severity="info"`, `step_id` set, carrying its own `plan-tool split` remedy prose.
- The finding is `is_structural=True` (split-branch `triage_reason`), is **never** auto-dispatched to `escalate_to_split` (blocked by `split_escalation_target`'s `medium`+opt-in gate), is **not** in `APPLY_ELIGIBLE_SOURCES` (disjointness test still green), and never flips an exit code. No new source token; `review.py` still does not import `granularity`.
- The re-ground finding, the static granularity detectors, `escalate_to_split`, and every existing structural-routing test remain unchanged/green.
- CLAUDE.md + RUNBOOK document the code-grounded split producer as the third code-grounded reconcile producer beside re-ground (CLAUDE.md granularity-advisor paragraph ~:64, escalate-to-split paragraph ~:62, structural-vocabulary re-split bullet ~:70; RUNBOOK.md code-grounded re-ground callout ~:1727 and four-remedies model ~:2347).
- BACKLOG #70's last arm ("Code-reveals-a-split detection") is struck and #70 is closed as fully shipped, including the T2 tier roll-up parenthetical (`BACKLOG.md` ~:482–484), with a pre-close check that no other arm remains.

## Deferred

- **Promotion to `medium`/blocking or into `extra_apply_sources`** — a later measurement item could consider promotion (cf. #110's pattern); out of scope here, kept advisory `info` only for now.
