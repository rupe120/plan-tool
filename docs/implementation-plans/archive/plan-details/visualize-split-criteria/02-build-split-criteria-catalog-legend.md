> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Build the split-criteria catalog and legend renderer

## Summary

Creates `plan_tool/split_criteria.py`, a read-only leaf that declares every structural-split criterion the tool already applies as one catalog of descriptors, and renders the plan-independent **legend** from it — all criteria across the three altitudes plus the *altitude × disposition* remedy vocabulary. Each criterion is described once as data (`id`, `altitude`, `description`, the live threshold/lexicon/source it reads, advisory-vs-actuating, its detector, its remedy), so the later per-plan mode (step 3) renders from the same catalog and never re-describes a criterion. The key rule: the renderer **imports each backing constant from its owning module and interpolates it** — it never re-types a `3`/`0.85`/`16384` literal — and `tests/test_split_criteria.py` drift-guards each rendered value against its imported source. On green, `render_split_criteria()` (no plan argument) returns the full legend string, `plan_tool/split_criteria.py` imports only cycle-free leaves below it, and every drift-guard test passes.

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result on green
- [Why](#why) — the missing single surface for the tool's split criteria
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files this step creates
- [Implementation](#implementation) — the catalog shape, the two criteria tiers, the import/drift-guard rule, and cycle safety
- [Tests](#tests) — unit tests in test_split_criteria.py, drift-guarding each rendered constant
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse note plus the criteria's owning modules
- [Deferred](#deferred) — the per-plan evaluator, CLI, telemetry call, and the declarative-decider refactor owned by later steps

## Why

The tool decides how to split work at three altitudes, but those criteria are scattered across `plan_tool/granularity.py`, `plan_tool/convergence_diagnosis.py`, `plan_tool/distill_thresholds.py`, `plan_tool/review.py`, `plan_tool/launcher.py` (`escalate_to_split`), and `plan_tool/scope_out.py`, and each only fires *inside* another command. No single surface answers "what are all the split criteria, and what do they read?" This step builds that surface's foundation: one declarative catalog plus the legend that prints it. It lands first, before the per-plan evaluator (step 3) and the CLI (step 6), so the catalog — the single source of truth both render modes read — is reviewable on its own. Landing the descriptors before the evaluator mirrors how step 1 landed the telemetry recorder before its caller.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/split_criteria.py` — the criteria catalog (a list of frozen descriptors), the legend renderer `render_split_criteria()`, and the small helpers that format the remedy vocabulary. No Claude, no plan/code mutation.
  - `tests/test_split_criteria.py` — unit tests for the catalog shape and the legend, drift-guarding each rendered constant against the value imported from its owning module.
- **Existing files (edits only):** none.

## Implementation

**Foundational logic: one declarative catalog of split criteria that the legend (this step) and the per-plan breakdown (step 3) both read from.** The catalog is *descriptors* — data about each criterion — not the deciders. It must not copy or re-implement any predicate, and must not refactor the correctness-sensitive deciders (`granularity`, `convergence_diagnosis`, `review`) to serve this read-only view. The same criteria logic lives in those modules today; this catalog references it by importing the modules' public constants, never by re-typing their values.

**Declare each criterion once as a frozen descriptor.** One way: a `@dataclass(frozen=True)` — suggest `SplitCriterion` — with fields the legend and (later) the evaluator both need:
- `id: str` — a stable slug the step-3 evaluator maps detector output back to (e.g. `mixed-verbs`, `multi-area`, `localized`, `merge`, `split-safety`, `mixed-step`). Reuse the existing predicate slugs where one exists so the ids line up with `plan_tool/granularity.py`'s `SPLIT_PREDICATE_MIXED_VERBS` / `SPLIT_PREDICATE_CONJOINED_CLAUSES` / `SPLIT_PREDICATE_UNRELATED_AREAS`, the merge source `GRANULARITY_MERGE_SOURCE`, and the fork arms `plan_tool/convergence_diagnosis.py`'s `FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL`. The catalog is the **full** criteria set (the legend shows all of them); the per-plan evaluator (step 3) evaluates only the deterministic ones (see `deterministic` below).
- `altitude: int` — `1` (plan too big → many plans), `2` (decompose into steps), `3` (conditionally split one step). Match the plan's three-altitude framing.
- `description: str` — a one-line human explanation of what the criterion checks.
- `advisory: bool` (or an enum) — whether the criterion only advises or actually drives a mutation. The `granularity-*` sources are advisory (kept out of `plan_tool/review.py`'s `APPLY_ELIGIBLE_SOURCES`); read that stance from `plan_tool/review.py`'s `is_apply_eligible` / `is_structural` framing rather than re-deciding it.
- `deterministic: bool` — whether the per-plan evaluator (step 3) can evaluate this criterion **without Claude**. The deterministic split/merge smells, the convergence forks, and the `split-safety` checks are `True`; the **altitude-1 distill split** criterion is `False` — its thresholds gate the create-time **seed**, not an authored plan file (`distill_thresholds.py` docstring), and the split decision is Claude-judged, so per-plan mode cannot fire it by comparing the plan's bytes. The legend still renders the altitude-1 threshold values as drift-guarded reference numbers; only its per-plan *firing* is Claude-judged. The legend shows a `deterministic=False` criterion; per-plan mode marks it "not evaluated (Claude-judged)" rather than firing it.
- `detector: str` — the name of the function/source that produces the finding (e.g. `granularity._step_spans_unrelated_areas`, `convergence_diagnosis.classify_fork`). A string label is enough for the legend; step 3 owns the actual call.
- `remedy: str` — which structural remedy applies (`re-split` / `scope-out` / `merge` / `re-seed`), matching the vocabulary in CLAUDE.md's "Structural remedy vocabulary".

Keep the catalog itself a module-level constant — suggest `SPLIT_CRITERIA: tuple[SplitCriterion, ...]`.

**Split the criteria into two tiers — this is the key correctness decision.** A criterion is either backed by a single owning constant (drift-guard it) or by predicate control flow with no single constant (render it as plain, unpinned prose). Do not pretend the second kind is drift-guarded.

- **Data-backed criteria — import the constant and interpolate it.** Never re-type the literal. The renderer must read each value from its owning module:
  - `plan_tool/distill_thresholds.py`: `DISTILL_SKIP_BELOW_BYTES` (16384) and `DISTILL_ADVISE_ABOVE_BYTES` (262144) — altitude 1's data-backed size signals.
  - `plan_tool/granularity.py`: `_REFACTOR_VERBS` and `_FEATURE_VERBS` (the title-smell lexicons), `_TRIVIAL_REFACTOR_MAX_FILES` (1), `_TEST_TOP_DIRS`, plus `GRANULARITY_SPLIT_SOURCE` / `GRANULARITY_MERGE_SOURCE` — altitude 2.
  - `plan_tool/convergence_diagnosis.py`: `WINDOW_SIZE` (3), `RECURRENCE_TOLERANCE` (1), `TITLE_SIMILARITY_CUTOFF` (0.85), and `_SEVERITY_RANK` (the medium+ rank map) — altitude 3.
- **Control-flow criteria — render terse, unpinned prose.** Some criteria have no single backing constant because the rule lives in a function body: `plan_tool/granularity.py`'s `_step_spans_unrelated_areas` (the top-level-area count with test/doc riders folded out), `plan_tool/launcher.py`'s `escalate_to_split` safe-gate (no downstream non-`PENDING`/run-started step blocks the split), and `plan_tool/scope_out.py`'s blockers. Describe these in a sentence and state in the code (a comment) that the prose is unpinned — nothing drift-guards it. Do **not** restructure any decider to make its predicate renderable from this read-only surface.

**Note on the private-constant import.** Reading `convergence_diagnosis._SEVERITY_RANK` and `granularity._REFACTOR_VERBS`/`_FEATURE_VERBS` crosses the leading-underscore boundary on purpose: the alternative — re-typing `{"medium": 1, "high": 2, "critical": 3}` or the verb sets in the renderer — is exactly the drift this catalog exists to prevent. Import the live constant and let the drift-guard test hold the two in sync. If a later maintainer prefers a public alias, that is a follow-up in the owning module, not a reason to copy the literal here.

**Two criteria that need explicit catalog entries (so step 3's mapping and the breakdown can reference them).** (a) **`split-safety`** (altitude 3, `deterministic=True`) — the read-only `launcher.escalate_to_split` safe-gate (`split_safety.split_is_safe`) plus `scope_out.py`'s blocker computation. Its *rule* is control-flow prose (unpinned), but its *result* is computable without Claude, so step 4 actually calls these per step and the criterion is deterministically-evaluable. (b) **`mixed-step`** (altitude 2, `deterministic=True`) — the detail-purity check `granularity` surfaces at `stage="detail"` **without** an invoker: `assess_granularity` never calls Claude here, it lifts already-recorded MIXED-STEP findings from `evidence.detail_bodies` via `parse_mixed_step_findings` (a regex parse), so per-plan mode evaluates it deterministically. Also give the **merge** source (`GRANULARITY_MERGE_SOURCE`) its own catalog `id` so step 3 can map merge findings to it.

**Render the remedy vocabulary from the altitude × disposition axis.** The legend's second half prints the four structural remedies as one split/merge axis parameterized by altitude (a step vs the plan's scope) and disposition of the carved side (kept as a sibling step vs carved to a forward-seed), matching CLAUDE.md's "Structural remedy vocabulary": `re-split` (step-altitude split, both halves kept), `scope-out` (plan-scope split, carved side deferred to a seed), `merge` / re-ground (the inverse), and `re-seed` (split everything / restart). Keep this section catalog-driven where a `remedy` field already names the remedy, so a criterion and its remedy stay described in one place.

**Renderer shape and approach.** `render_split_criteria(*, color: bool = False)` takes no plan and returns the full legend as a string; the CLI handler (step 6) is the only caller that prints it. Keep the function pure — build a `list[str]` of lines and `"\n".join` them, the same shape as `plan_tool/convergence_diagnosis.py`'s `render_diagnosis`. Spend no Claude, mutate nothing. The legend is **TTY-aware**: it colors via `plan_tool/style.py` (`paint`) when `color=True` and is plain when `color=False` — the *same* coloring approach step 3's `render_plan_breakdown` uses, so the two render modes do not diverge on color. The CLI handler (step 6) passes `color=style.color_enabled(sys.stdout)`, delivering the plan's AC1 ("legend colored on a TTY, plain when piped").

**Cycle safety — this module sits above the criteria modules.** `plan_tool/split_criteria.py` imports `granularity`, `convergence_diagnosis`, `distill_thresholds`, and `review` (and later `review_persistence` / `telemetry` in step 5); none of those import it back, exactly as the CLI layer sits above them. Do not import any heavy orchestrator — `create.py` is not imported; the distill thresholds are read from the `plan_tool/distill_thresholds.py` leaf precisely so this module stays light. Keep `plan_tool/telemetry.py`'s stdlib-only leaf status intact (this step does not touch it).

## Tests

All in `tests/test_split_criteria.py` (unit, no Claude — the autouse conftest gate must never fire). Enumerate:

- `test_render_split_criteria_returns_string` — `render_split_criteria()` returns a non-empty string with no plan argument.
- `test_legend_covers_all_three_altitudes` — the rendered legend mentions altitude 1, 2, and 3 criteria.
- `test_catalog_ids_unique` — every `SplitCriterion.id` in `SPLIT_CRITERIA` is unique.
- `test_catalog_reuses_granularity_predicate_slugs` — the altitude-2 split criterion ids equal `granularity.SPLIT_PREDICATE_MIXED_VERBS` / `_CONJOINED_CLAUSES` / `_UNRELATED_AREAS` (so step 3's mapping lines up).
- `test_legend_renders_distill_thresholds_from_source` — the legend text contains `str(distill_thresholds.DISTILL_SKIP_BELOW_BYTES)` and `str(DISTILL_ADVISE_ABOVE_BYTES)` (drift-guard: fails if the renderer re-types the number).
- `test_legend_renders_convergence_window_from_source` — the legend contains `str(convergence_diagnosis.WINDOW_SIZE)` and `str(RECURRENCE_TOLERANCE)`.
- `test_legend_renders_title_similarity_cutoff_from_source` — the legend contains the rendered form of `convergence_diagnosis.TITLE_SIMILARITY_CUTOFF` (0.85).
- `test_legend_renders_severity_rank_from_source` — the legend names the `_SEVERITY_RANK` levels (`medium`/`high`/`critical`) read from the imported map, not a re-typed set.
- `test_legend_renders_verb_lexicons_from_source` — every verb in `granularity._REFACTOR_VERBS` and `_FEATURE_VERBS` appears in the rendered legend.
- `test_legend_renders_trivial_refactor_max_files_from_source` — the legend contains `str(granularity._TRIVIAL_REFACTOR_MAX_FILES)`.
- `test_legend_renders_remedy_vocabulary` — the legend names all four remedies (`re-split`, `scope-out`, `merge`, `re-seed`).
- `test_control_flow_criteria_present_but_unpinned` — the multi-area / safe-gate / scope-out-blocker criteria appear in the legend as prose (assert their descriptions are present; do not assert a backing number, since none exists).
- `test_legend_plain_when_color_off_colored_when_on` — `render_split_criteria(color=False)` contains no ANSI escape sequences; `render_split_criteria(color=True)` does (delivers AC1's TTY-aware legend, matching step 3's coloring).
- `test_catalog_has_merge_and_split_safety_ids` — `SPLIT_CRITERIA` contains a criterion mapping the `granularity.GRANULARITY_MERGE_SOURCE` merge source and a `split-safety` criterion (altitude 3, `deterministic=True`).
- `test_mixed_step_criterion_marked_deterministic` — a `mixed-step` criterion is present with `deterministic=True` (per-plan mode lifts its findings via `parse_mixed_step_findings`, no Claude).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each drift-guard test alongside the catalog entry and rendered line it covers: add the criterion descriptor, render it from the imported constant, then add the test asserting the rendered token equals the imported value. Every new test in `tests/test_split_criteria.py` must be green before this step is done.

## Acceptance criteria

- `plan_tool/split_criteria.py` exists and exports `SPLIT_CRITERIA` (a tuple of frozen `SplitCriterion` descriptors) and `render_split_criteria()`.
- `render_split_criteria()` returns a non-empty string, takes no plan argument, spends no Claude, and mutates nothing.
- Every criterion id in `SPLIT_CRITERIA` is unique; the altitude-2 split ids equal `granularity.SPLIT_PREDICATE_*` values. The catalog also carries the merge-source id, a deterministic `split-safety` criterion, and a `mixed-step` criterion flagged `deterministic=True`.
- `render_split_criteria(color=...)` is TTY-aware: plain (no ANSI) when `color=False`, colored via `style.paint` when `True` — the same coloring step 3 uses.
- The legend's numeric/lexical values are read from their owning modules: `16384` / `262144` from `distill_thresholds`, `3` / `1` / `0.85` from `convergence_diagnosis`, `1` and the verb lexicons from `granularity`. A drift-guard test fails if any is re-typed.
- The legend prints all four remedies (`re-split`, `scope-out`, `merge`, `re-seed`) across the altitude × disposition axis.
- `plan_tool/split_criteria.py` imports no orchestrator (`create.py`) and nothing in `granularity` / `convergence_diagnosis` / `review` / `distill_thresholds` imports it back.
- `uv run pytest tests/test_split_criteria.py -q` is green.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — background for the optional-positional `split-criteria [<plan>]` command, though the CLI wiring itself is step 6; this step only builds the no-arg legend renderer that command will call.
- [How to mark test functions with attributes (pytest docs)](https://docs.pytest.org/en/stable/how-to/mark.html) — reference for pytest markers; this step's tests are plain unit tests (unmarked) since the renderer needs no `main([...])` drive.

## Deferred

- **The per-plan evaluator and breakdown renderer** — owned by step 3 (`depends_on: [1, 2]`); it calls the real detectors (`granularity.assess_granularity`, `convergence_diagnosis.load_report_history` → `diagnose_convergence` → `classify_fork`) and maps their output back to catalog ids; the read-only `escalate_to_split` / `scope_out` split-safety checks are added separately by step 4. This step declares the catalog and legend only.
- **The telemetry recording call** — step 5 calls `record_plan_criteria_breakdown` (the recorder step 1 adds to `plan_tool/telemetry.py`) with the plan fingerprint. This step writes no telemetry and does not import `telemetry.py`.
- **The drift note (diffing a plan's latest breakdown against an earlier fingerprint)** — step 5's report layer.
- **The `plan-tool split-criteria` CLI handler** — step 6 (`plan_tool/cli/split_criteria_cmd.py`), modeled on `plan_tool/cli/convergence_cmd.py`.
- **Making the deciders themselves declarative** (so a control-flow predicate like `_step_spans_unrelated_areas` or the `escalate_to_split` safe-gate could be pinned from this surface) — a `BACKLOG.md` criteria-metadata-catalog item, not a detail-time change. This step renders those criteria as unpinned prose and touches no decider.
