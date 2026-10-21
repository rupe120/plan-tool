# Step 3 — Add localized-vs-structural fork classifier and forked copy-paste recommendation renderer

## Summary

- Adds the **fork** layer to `plan_tool/convergence_diagnosis.py`: a pure `classify_fork(diagnosis)` that reads step 2's `ConvergenceDiagnosis` and decides whether a `spinning` plan's recurrence is a **localized over-pack** (one step doing too much → recommend an in-place re-split) or **structural** (the decomposition itself is wrong → recommend authoring a fresh seed and re-decomposing).
- Adds `render_diagnosis(diagnosis)` — the **forked copy-paste recommendation renderer** — which prints the one-line verdict and, when `spinning`, the shape line plus a pre-filled command (`plan-tool split <slug> --step N --into …` for localized, `plan-tool create --from-existing <seed> --iterate` for structural).
- Most important design decision: the classifier reads a per-region **step focus** from `RegionTrend.step_id` *or*, when that is `None`, a `step<N>` token parsed out of the anchor slug — because plan-completeness findings carry `step_id=None` and name the step in the anchor (e.g. `step5-over-pack`). It is wired to consume the granularity advisor's `granularity-split` source (`plan_tool/granularity.py: GRANULARITY_SPLIT_SOURCE`) as the strongest localized signal rather than re-deriving any per-step over-pack check — though that path is inert until upstream completeness persistence carries smell recs into the report sidecar (see Implementation).
- Small enabling edit: add a `sources: frozenset[str]` field (defaulted) to step 2's `RegionTrend` and populate it in `_recurring_regions`, so the classifier stays pure over the diagnosis instead of re-walking history.
- On green: `classify_fork(diagnose_convergence(load_report_history(plan_path)))` returns a `localized` fork targeting the single recurring step for the committed spinning fixture, `structural` when recurrence spans multiple steps, and a `structural` fork flagged `ambiguous` (cautious re-seed) when the signal is mixed or concept-only. No classification, no CLI wiring beyond the renderer — the `plan-tool convergence` seam is step 4.

## Table of Contents

- [Why](#why) — what the step-2 verdict still can't tell the operator
- [Files (creates vs edits)](#files-creates-vs-edits) — edits to the two existing step-1/2 files only
- [Implementation](#implementation) — the fork model, the step-focus rule, the classifier, the renderer, reuse decisions
- [Tests](#tests) — unit cases per branch + the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — stdlib + module docs for the surfaces this step touches
- [Deferred](#deferred) — CLI seam, semantic inter-step detection, auto-execution left for later steps

## Why

- Step 2 turns the report history into a `spinning` / `converging` verdict plus recurring `RegionTrend`s, but it makes **no repair recommendation** — it deliberately emits `RegionTrend.step_id`/`anchor` and stops, leaving the localized-vs-structural decision to this step.
- The fork is the heart of v1: the **wrong path wastes work**. Recommending a 1→2 `split` for a cross-step spine problem can't fix it; recommending a full re-seed for one over-packed step is heavy-handed. This step encodes the plan's deterministic fork rule and renders the exact copy-paste command for the matched shape, so the operator acts on the right repair.
- It stays read-only and Claude-free — pure logic over the in-memory `ConvergenceDiagnosis`. The reader (step 1) already did all disk work; the detector (step 2) already did all cross-run trend analysis.

## Files (creates vs edits)

**New files:**
- None.

**Existing files (edits only):**
- `plan_tool/convergence_diagnosis.py` — add the fork classifier + renderer on top of steps 1–2:
  - one new top-level import (`plan_tool/granularity.py: GRANULARITY_SPLIT_SOURCE`),
  - a small additive field on step 2's `RegionTrend` (`sources: frozenset[str] = frozenset()`) and its population inside `_recurring_regions`,
  - one new frozen dataclass (`ForkRecommendation`),
  - the public `classify_fork(diagnosis)` and `render_diagnosis(diagnosis)` plus private helpers (`_region_step_focus`, `_localized_command`, `_structural_command`).
- `tests/test_convergence_diagnosis.py` — add the classifier + renderer test cases. Keep steps 1–2's reader/model/detector tests unchanged.

No new fixture file is needed: the committed `tests/fixtures/convergence/sample-report-history.json` is the spinning series; multi-step / anchor-only / mixed / converging variants are built inline by mutating loaded fixture payloads (same pattern steps 1–2 use).

## Implementation

### `plan_tool/convergence_diagnosis.py` (edits)

**New top-level import (acyclic — state why so a later reader doesn't body-localize it).**
- `from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE`.
- `plan_tool/granularity.py` is a cycle-free advisory leaf importing only `plan_tool/schema.py` and `plan_tool/review.py`'s finding primitives; it never imports this module — so the top-level import is safe, same posture as steps 1–2's `review_persistence` / `convergence` imports. Do **not** lazy-import it.
- `GRANULARITY_SPLIT_SOURCE == "granularity-split"` is the single source for that literal. Import it; do **not** hardcode the string. The plan's localized signal is the granularity advisor's `granularity-split`.

**Enabling edit on step 2's `RegionTrend` — add the per-region source set.**
- Add field `sources: frozenset[str] = frozenset()` — the set of `RunFinding.source` values across the region's trailing streak. Default keeps every existing step-2 construction call site and test unchanged.
- Populate it in `_recurring_regions`: when building each `RegionTrend`, collect `frozenset(f.source for f in streak_findings)` for that region.
- Rationale: the classifier needs `source` to consume `granularity-split`, and the natural home for "which sources flagged this region" is the per-region record — not a re-walk of `history` inside the classifier. This keeps `classify_fork` a pure function of `ConvergenceDiagnosis` (the clean API step 4's CLI calls).

**New frozen dataclass (`@dataclass(frozen=True)`, matching the step-1/2 model posture).**
- `ForkRecommendation` — the matched repair for a `spinning` plan:
  - `shape: str` — `"localized"` or `"structural"`.
  - `ambiguous: bool` — `True` when the classifier could not cleanly localize and fell back to the cautious re-seed (the plan's "when unsure, recommend the cautious re-seed and say so" rule). Always `False` on a clean localized or clean multi-step structural call.
  - `target_step_id: Optional[int]` — the step to split; set only on `shape == "localized"`, else `None`.
  - `granularity_backed: bool` — `True` when the localized region's `sources` includes `GRANULARITY_SPLIT_SOURCE` (the strongest localized signal). `False` otherwise. **Inert today (forward-wiring):** smell recs are not yet persisted to the report sidecar (see "Foundational logic" below), so in production this stays `False`; the field and its reason branch light up only once upstream persistence carries `granularity-split` into the report history.
  - `command: str` — the pre-filled, copy-paste command line for the matched shape.
  - `reason: str` — the one-line shape explanation rendered on the `shape:` line.

**Step-focus helper — `_region_step_focus(region: RegionTrend) -> Optional[int]`.**
- Return `region.step_id` when not `None`.
- Else parse `region.anchor` for a leading step token via a module-level compiled regex (`re.compile(r"^step-?(\d+)")`) and return the captured int when it matches — plan-completeness anchors encode the step in the slug (`step5-over-pack` → `5`), matching the plan's example output line "step 5 re-flagged".
- Else return `None` — a concept anchor with no step binding (e.g. `cache-invalidation`), which the fork treats as un-localizable.
- This is the one place that maps a recurring region to "which step is this about"; both branches of the classifier read it.

**The public classifier — `classify_fork(diagnosis: ConvergenceDiagnosis) -> Optional[ForkRecommendation]`.**
- No `invoker`, no I/O — pure function over the in-memory model.
- **Converging short-circuit.** Return `None` when `diagnosis.verdict != "spinning"` — a converging plan needs no repair recommendation. (Step 2 guarantees `spinning` implies non-empty `regions`.)
- Compute the focus of every recurring region: `foci = [_region_step_focus(r) for r in diagnosis.regions]`; `concrete = {f for f in foci if f is not None}`.
- **Localized** when `len(concrete) == 1` and concept-only regions are a minority (`concept_only_count < step_focused_count`, where `concept_only_count = sum(1 for f in foci if f is None)` and `step_focused_count = len(foci) - concept_only_count`) — recurrence concentrates on a single step and that step focus dominates, with at most a minority of regions concept-only:
  - `shape="localized"`, `target_step_id = concrete.pop()`, `ambiguous=False`.
  - `granularity_backed = any(GRANULARITY_SPLIT_SOURCE in r.sources for r in diagnosis.regions)`.
  - `command = _localized_command(diagnosis.plan_slug, target_step_id)`.
  - `reason` = `"localized over-pack (granularity advisor flagged step N for splitting)"` when `granularity_backed`, else `"localized over-pack (recurrence on a single step)"`.
- **Structural (confident)** when `len(concrete) >= 2` — recurrence spans multiple steps; a 1→2 split can't fix an N-way problem:
  - `shape="structural"`, `target_step_id=None`, `ambiguous=False`, `command = _structural_command(diagnosis.plan_slug)`, `reason="structural (the decomposition itself is wrong)"`.
- **Structural (ambiguous → cautious re-seed)** for every other case — all regions concept-only (`concrete` empty), or one step focus that concept-only regions tie or outnumber (concept-only not a minority):
  - `shape="structural"`, `target_step_id=None`, `ambiguous=True`, `command = _structural_command(diagnosis.plan_slug)`, `reason="structural — ambiguous signal; recommending the cautious re-seed"`.
  - This mirrors `create`'s `direct`-vs-`plan-tool` "when unsure, author a plan" default: never emit a confident wrong split.

**The command builders (private).**
- `_localized_command(plan_slug, step_id) -> str` → `plan-tool split {plan_slug} --step {step_id} --into "<first concern>" --into "<second concern>"`. The `<…>` placeholders are intentional — v1 cannot name the concerns; the operator fills them. Flags match `docs/cli/split.md` (`--step`, repeated `--into`).
- `_structural_command(plan_slug) -> str` → `plan-tool create --from-existing <seed> --iterate`. The `<seed>` placeholder is intentional — re-decompose is human-authored. Flags match `docs/cli/create.md` (`--from-existing`, `--iterate`).

**The renderer — `render_diagnosis(diagnosis: ConvergenceDiagnosis) -> str`.**
- Builds the operator-facing text block; the verbatim string step 4's CLI prints to stdout. Pure; no I/O.
- **Line 1 (verdict summary).**
  - Converging: `converging — {plan_slug}: no spinning region across {runs_examined} audit(s)` — return this line alone.
  - Spinning: `spinning — {focus_summary}{", no shrinkage" if diagnosis.no_shrinkage else ""}`, where `focus_summary` is:
    - localized: `step {target_step_id} re-flagged in {region.run_count} of the last {runs_examined} audits` (the region whose focus is `target_step_id`),
    - structural (multi-step): `findings span steps {sorted concrete foci, comma-joined}`,
    - structural (ambiguous/concept-only): `findings recur on {region keys, comma-joined} (no single step)`.
- **Lines 2–3 (spinning only).** Call `classify_fork(diagnosis)` and append:
  - `  shape: {fork.reason}`,
  - `  → {fork.command}`.
- Single source for the fork: `render_diagnosis` calls `classify_fork` rather than re-deriving the shape, so the printed shape and the structured fork never diverge.

**Foundational logic and where else it lives.**
- This step's core rule is **"single recurring step → recommend split; multiple steps or concept-only → recommend re-seed; unsure → cautious re-seed."**
- The per-step over-pack signal it consumes (`granularity-split`) is **owned by `plan_tool/granularity.py`** (`GRANULARITY_SPLIT_SOURCE`, the split detectors). This step does **not** re-derive a static per-step granularity check — it reads the advisor's findings from the report history when they are present. **Forward-wiring (inert today):** `cli/completeness_phases.py` currently persists only `correctness_recs + conceptual_recs` to the report sidecar (`smell_recs`, which carry `granularity-split`, go to markdown only), so `RunFinding.source` / `RegionTrend.sources` never contain `GRANULARITY_SPLIT_SOURCE` in production — `granularity_backed` stays `False` and the granularity-backed reason branch is dead until upstream sidecar persistence is scoped to include smell recs. Wire the consumer now so it lights up when that persistence lands; do not state it flows today. No consolidation needed; the producing detector stays in `granularity.py`.
- The localized split it recommends is the same surgical 1→2 the `plan-tool split` command executes via `plan_tool/create.py: _apply_step_split`; the cautious-default-when-unsure mirrors `create`'s direct-vs-plan heuristic. Both are referenced, not edited — v1 recommends only; auto-execution is Deferred.

## Tests

Reference file: `tests/test_convergence_diagnosis.py`. Fixture: `tests/fixtures/convergence/sample-report-history.json` (committed by step 1; reused, mutated inline for variants).

- `test_region_trend_sources_populated` — `_recurring_regions` sets `RegionTrend.sources` to the underlying findings' `source` values (the enabling edit); step 2's existing detector tests stay green with the defaulted field.
- `test_region_step_focus_from_step_id` — a region with `step_id=5` and no anchor → `_region_step_focus` returns `5`.
- `test_region_step_focus_from_anchor_slug` — a region with `step_id=None`, `anchor="step5-over-pack"` → focus `5` (the canonical completeness case).
- `test_region_step_focus_concept_anchor_is_none` — `anchor="cache-invalidation"`, `step_id=None` → focus `None`.
- `test_classify_localized_single_step` — spinning diagnosis, one region focusing step 5, no concept-only region → `shape=="localized"`, `target_step_id==5`, `ambiguous is False`.
- `test_classify_structural_multi_step` — recurring regions focusing steps {4,5,7} → `shape=="structural"`, `ambiguous is False`, `target_step_id is None`.
- `test_classify_concept_only_is_ambiguous_structural` — every recurring region concept-only (focus `None`) → `shape=="structural"`, `ambiguous is True`.
- `test_classify_mixed_step_and_concept_is_ambiguous` — one step-5 region + one concept-only region (a tie, concept-only not a minority) → `structural`, `ambiguous is True`.
- `test_classify_dominant_step_with_minor_concept_is_localized` — two step-5 regions + one concept-only region (concept-only a minority) → `shape=="localized"`, `target_step_id==5`, `ambiguous is False`.
- `test_granularity_split_marks_localized_backed` — single-step region whose `sources` includes `GRANULARITY_SPLIT_SOURCE` → `granularity_backed is True`, `shape=="localized"`, reason names the granularity advisor.
- `test_classify_converging_returns_none` — a `converging` diagnosis → `classify_fork` returns `None`.
- `test_render_localized_command_prefilled` — spinning localized render contains `spinning`, `shape: localized`, and `plan-tool split <slug> --step 5 --into`.
- `test_render_structural_command_prefilled` — multi-step render contains `shape: structural`, `findings span steps`, and `plan-tool create --from-existing <seed> --iterate`.
- `test_render_ambiguous_labeled` — ambiguous render contains the word `ambiguous` and the cautious re-seed command (never a split command).
- `test_render_converging_no_recommendation` — converging render contains `converging` and no `→` / `split` line.
- `test_classify_and_render_spend_no_io` — both functions take only the in-memory `ConvergenceDiagnosis`, construct no invoker, and read/write no disk.

### Test-creation order (feature step)

- This is a **feature** step. Write each test **alongside** the symbol it covers — the `RegionTrend.sources` enrichment and `_region_step_focus` cases first, then `classify_fork`'s per-branch cases, then `render_diagnosis`'s output cases.
- Green-before-done gate: every new test in `tests/test_convergence_diagnosis.py` (steps 1–2's plus step 3's) must pass before this step is finished. Run `uv run pytest tests/test_convergence_diagnosis.py -q`.

## Acceptance criteria

- `classify_fork(diagnosis)` returns `None` when `diagnosis.verdict == "converging"`.
- A spinning diagnosis whose recurrence focuses exactly one step (via `step_id` or a `step<N>` anchor) yields `ForkRecommendation(shape="localized", target_step_id=N, ambiguous=False)`.
- A spinning diagnosis whose recurring regions focus ≥2 distinct steps yields `shape="structural"`, `ambiguous=False`, `target_step_id=None`.
- A spinning diagnosis with only concept-only regions, or one step focus that concept-only regions tie or outnumber, yields `shape="structural"`, `ambiguous=True`; a single step focus with concept-only regions in the minority yields `shape="localized"`.
- A localized region carrying `source="granularity-split"` yields `granularity_backed=True`.
- `render_diagnosis` prints the `plan-tool split <slug> --step N --into …` command for localized and `plan-tool create --from-existing <seed> --iterate` for structural, with the matching `shape:` line; a converging diagnosis prints one line and no recommendation.
- Neither `classify_fork` nor `render_diagnosis` takes an `invoker`, reads disk, or writes files.
- `plan_tool/convergence_diagnosis.py` still imports cleanly with no import cycle after the `plan_tool/granularity.py` import is added.

## References

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for `ForkRecommendation` and the added `RegionTrend.sources` field default.
- [re — Regular expression operations — Python documentation](https://docs.python.org/3/library/re.html) — `re.compile` / anchored match behind `_region_step_focus`'s `^step-?(\d+)` anchor parse.
- [Built-in Functions — `sorted`, `any`, `all`](https://docs.python.org/3/library/functions.html) — the deterministic step-id span sort and the `any`/`all` predicates behind the localized/structural decision.

## Deferred

- **`plan-tool convergence <plan>` CLI seam and the zero-Claude integration test** — step 4 (`plan_tool/cli/convergence_cmd.py`, parser registration, generated reference). This step renders the text; step 4 prints it and pins the exit-0-regardless-of-verdict convention.
- **Semantic inter-step shape detection** (the plan example's "2 reference inter-step ordering") — v1 infers structural purely from step-span / concept-only anchors, not by parsing finding text for ordering/dependency semantics. A Claude-assisted classifier for genuinely ambiguous cases is the plan's own deferred follow-up.
- **Naming the split's sub-step concerns** — the `--into "<first concern>"` placeholders stay literal; auto-suggesting concern titles would require reading code/detail and spending Claude, out of v1's read-only scope.
- **Auto-executing the localized split** — wiring the recommendation into the `plan-tool split` executor (`plan_tool/create.py: _apply_step_split`) behind an opt-in + TTY gate is the plan's deferred item; v1 recommends only and never mutates structure.
