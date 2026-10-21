> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Localized-vs-structural fork classifier + `render_diagnosis` output

## Summary

This step adds the **top layer** of `plan_tool/convergence_diagnosis.py`: `classify_fork(diagnosis)` decides whether a `spinning` verdict is a **localized** over-pack (one step doing too much → re-split it in place) or a **structural** mis-decomposition (the boundaries themselves are wrong → author a fresh `create` seed and re-decompose), and `render_diagnosis(diagnosis)` turns the whole `ConvergenceDiagnosis` into the human-readable string the step-5 CLI prints. It edits only `plan_tool/convergence_diagnosis.py` and `tests/test_convergence_diagnosis.py`. The key design decision: **localize only when every recurring region resolves to one concrete step number** (via `step_id` or a `step<N>` anchor); any mixed, multi-step, or anchor-unresolvable evidence falls to the cautious structural re-seed. On green, `render_diagnosis` prints a four-state headline, a per-kind breakdown, and — on `spinning` — a pre-filled `plan-tool split … --into "…"` or `plan-tool create … --from-existing …` command with the recurring region's severity trend, spending no Claude.

## Table of Contents

- [Why](#why) — what step 3 leaves unrendered and why the fork is its own step
- [Files (creates vs edits)](#files-creates-vs-edits) — the two-file set and the no-new-file note
- [Implementation](#implementation) — the fork classifier, the four-state render, the command builders, and the sibling renderer to mirror
- [Tests](#tests) — unit cases for each fork branch, each verdict render, and the fixture end-to-end
- [Acceptance criteria](#acceptance-criteria) — checkable outputs of `classify_fork` and `render_diagnosis`
- [References](#references) — dataclasses / textwrap docs for this step's surfaces
- [Deferred](#deferred) — the CLI, the granularity-backed localized path, and the shared split-renderer consolidation

## Why

Step 3 lands `diagnose_convergence(history) → ConvergenceDiagnosis` carrying the four-state headline, the per-series verdicts, and the `recurring` regions that tripped — but it deliberately makes **no** fork and renders **no** string. The whole user-facing point of `plan-tool convergence` is the forked recommendation: a `spinning` plan stuck on one over-packed step should hear "re-split step N", while a plan whose decomposition is wrong across steps should hear "re-seed and re-decompose" — patching a fourth time only grows the plan. The information needed to fork (`SeriesDiagnosis.recurring[*]` region `step_id` / `anchor` / `sources` / severity) already sits on the step-3 record; this step is the one place that reads it, picks the fork, and renders the verdict plus a concrete, pre-filled command an operator can run. It is the last logic layer before step 5 wires the thin CLI.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add the fork-state string constants, the `ForkRecommendation` record, `_region_step_focus`, the `classify_fork` entry point, the `_split_command` / `_reseed_command` builders, and the `render_diagnosis` entry point. No new imports beyond stdlib (reuses step 2's `_step_token` and `RegionTrend`, step 3's `ConvergenceDiagnosis` / `SeriesDiagnosis` / the four `VERDICT_*` constants).
  - `tests/test_convergence_diagnosis.py` — add the fork-classifier and render unit classes alongside steps 1–3's reader, region, and verdict tests, driven off in-test `RegionTrend` / `SeriesDiagnosis` / `ConvergenceDiagnosis` fixtures plus step 1's committed `tests/fixtures/convergence/sample-report-history.json` for the end-to-end case.

> **Files note.** Step 4 is the only step among steps 1–4 that declares `files:` explicitly (`plan_tool/convergence_diagnosis.py`, `tests/test_convergence_diagnosis.py`) — the same pair steps 1–3 edit (which use `creates:`/nothing); steps 5–6 declare their own `files:` for other surfaces. It creates nothing new and touches no file outside that pair. Step 5 adds the CLI surface; this step adds zero CLI wiring.

## Implementation

### Cross-step input contract (depends_on: 3)

`classify_fork` and `render_diagnosis` are pure functions over step 3's `ConvergenceDiagnosis`. They read these fields and nothing else; if step 3 names them differently, align there, not here:

- **`ConvergenceDiagnosis`** (step 3) — `plan_slug: str`, `verdict: str` (one of the four `VERDICT_*`), `window: int`, `series: tuple[SeriesDiagnosis, ...]`.
- **`SeriesDiagnosis`** (step 3) — `verdict: str`, `kind: str`, `step_id: int | None`, `run_count: int`, `recurring: tuple[RegionTrend, ...]` (non-empty only when `verdict == VERDICT_SPINNING`).
- **`RegionTrend`** (step 2) — reads `step_id`, `anchor`, `focus`, `sources`, `run_indices`, `max_severity`, `first_severity`, `last_severity`.
- **`VERDICT_NO_HISTORY` / `VERDICT_INSUFFICIENT_HISTORY` / `VERDICT_CONVERGING` / `VERDICT_SPINNING`** (step 3 constants) — key on these, never inline the literal strings.
- **`_step_token(anchor) -> int | None`** (step 2) — reuse for anchor parsing; do **not** re-declare the `^step-?(\d+)` regex here (step 2's Deferred assigns `_region_step_focus` to this step and says reuse `_step_token`).

### `plan_tool/convergence_diagnosis.py` — symbols to add

- **Fork-state constants**
  - `FORK_LOCALIZED = "localized"` — one step over-packed; recommend an in-place re-split.
  - `FORK_STRUCTURAL = "structural"` — cross-step / unresolvable mis-decomposition; recommend a fresh `create` seed and re-decompose.
  - `FORK_NONE = "none"` — the diagnosis is not `spinning`; no recommendation. Step 4's render and step 5's CLI key on these; do not inline the literals downstream.

- **`def _region_step_focus(region: RegionTrend) -> int | None`** — the classifier-facing step resolver:
  - Return `region.step_id` when it is not `None` (reconcile regions carry the audited step).
  - Else return `_step_token(region.anchor)` (completeness `plan-correctness` findings carry `step_id=None` and name the step only in a `step<N>` anchor, e.g. `step5-over-pack` → 5).
  - Else `None` — the **step`<N>`-anchor-only caveat**: a region whose focus came from a bare concept-slug anchor or a title slug (no `step<N>` token) has **no reliable step number**, so localization is impossible and the fork must fall structural. Reuse `_step_token`; do not duplicate its regex.

- **`@dataclass(frozen=True) class ForkRecommendation`** — the classify output `render_diagnosis` (and step-5 tests) read:
  - `fork: str` — one of `FORK_LOCALIZED` / `FORK_STRUCTURAL` / `FORK_NONE`.
  - `step_focus: int | None` — the single localized step number; set only on `FORK_LOCALIZED`, else `None`.
  - `command: str` — the pre-filled `plan-tool …` command for this fork (empty string on `FORK_NONE`).
  - `regions: tuple[RegionTrend, ...]` — the recurring regions that drove the fork (the spinning regions across all series), carried so the render shows their severity trend without re-walking.
  - `ambiguous: bool` — `True` when the evidence mixed a resolvable step focus with an unresolvable one (some regions localize, some don't), so the classifier defaulted **cautiously** to `FORK_STRUCTURAL`. Drives the render's "defaulted to re-seed" note. Always `False` on `FORK_LOCALIZED` / `FORK_NONE`.

- **`def classify_fork(diagnosis: ConvergenceDiagnosis) -> ForkRecommendation`** — the fork decision:
  - **Gather the spinning regions.** `regions = tuple(r for s in diagnosis.series if s.verdict == VERDICT_SPINNING for r in s.recurring)`. When empty (the headline is not `spinning`, or no series tripped), return `ForkRecommendation(FORK_NONE, None, "", (), False)`.
  - **Resolve each region's focus.** `foci = [_region_step_focus(r) for r in regions]`; `resolved = {f for f in foci if f is not None}`.
  - **Localized** when every region resolves to **one and the same** step number: `None not in foci and len(resolved) == 1`. Take `step = resolved.pop()`; return `ForkRecommendation(FORK_LOCALIZED, step, _split_command(diagnosis.plan_slug, step), regions, False)`. This covers both one recurring region on step N and several regions all on step N (one over-packed step).
  - **Structural (cautious default)** otherwise — distinct step foci (`len(resolved) > 1`), or any region with `None` focus (anchor-only / title-only), or no resolvable focus at all. Set `ambiguous = bool(resolved) and (None in foci)` (a genuine mix of resolvable and unresolvable evidence). Return `ForkRecommendation(FORK_STRUCTURAL, None, _reseed_command(diagnosis.plan_slug), regions, ambiguous)`.
  - **Why cautious toward structural:** recommending a narrow `plan-tool split --step N` when the evidence does not cleanly point at one step would send the operator to patch a single boundary while the real fault spans several — the more thorough re-seed is the safe default when the fork is unclear, matching the read-only advisory's cautious-default posture (lean toward the more complete fix, never the riskier narrow one).

- **`def _split_command(plan_slug: str, step: int) -> str`** — the localized recommendation, mirroring the existing split-recommendation renderer in `plan_tool/completeness_report.py` (`_blocked_next_step` / `_blocked_split_targets`):
  - `f'plan-tool split {plan_slug} --step {step} --into "<first sub-step>" --into "<second sub-step>"'`.
  - **`--into` values are placeholders, by design.** The diagnosis knows the over-packed **step**, but not the two concern titles to split it into (no granularity finding reaches the sidecar in v1 — see Deferred), so the command leaves `<first sub-step>` / `<second sub-step>` for the operator to fill, exactly as `completeness_report.py`'s BLOCKED renderer does. The schema-contract's `split-command-placeholders` disposition ("step-targeted command with concern-title placeholders") is this rule.

- **`def _reseed_command(plan_slug: str) -> str`** — the structural recommendation:
  - `f'plan-tool create {plan_slug} --from-existing <seed.md> --iterate'` (matching the plan's Output example and the mandated `--iterate` workflow) plus a short prose note (rendered around it) to hand-author the seed, mirroring `RUNBOOK.md`'s "When repeated audit/apply doesn't converge — re-decompose, don't keep patching" workflow. `<seed.md>` is a placeholder path the operator supplies; the diagnosis does not author a seed (zero Claude, no file writes in v1).

- **`def render_diagnosis(diagnosis: ConvergenceDiagnosis) -> str`** — the full printable block step 5 emits with one `print(...)`:
  - **Headline line** — the verdict and the plan, read straight from the diagnosis: `f"convergence: {diagnosis.verdict} — {diagnosis.plan_slug} (window {diagnosis.window})"`. Read `diagnosis.plan_slug`; **do not recompute the slug** in the renderer or the CLI (step 5 prints what the render returns).
  - **Per-kind breakdown** — one line per `SeriesDiagnosis` in `diagnosis.series` order: the kind (and `step_id` for reconcile, e.g. `detail-reconcile/step 5`), its verdict, and its `run_count` (e.g. `… (3 audits)` — the series' own run count, never a `N of window` framing whose denominator a spinning series can exceed), so a `completeness` series reading `converging` next to a `detail-reconcile` series reading `spinning` both show under the `spinning` headline.
  - **Four-state body:**
    - `VERDICT_NO_HISTORY` — name that no completeness/reconcile reports are saved yet and that the diagnostic needs ≥`window` separate invocations before it has signal. No command.
    - `VERDICT_INSUFFICIENT_HISTORY` — name the run count vs. `window` ("not enough data yet — N of `window` audits"); no recommendation, never a reassuring "converging".
    - `VERDICT_CONVERGING` — a positive line ("the audit/apply loop is converging; no re-decomposition needed"). No command.
    - `VERDICT_SPINNING` — call `classify_fork(diagnosis)` and render its recommendation:
      - The recurring regions' **severity trend**: iterate the spinning series directly — `for s in diagnosis.series if s.verdict == VERDICT_SPINNING`, then each `r in s.recurring` — **not** the flattened `rec.regions`, because the windowed count needs the owning series' `run_count`, which `rec.regions` (collapsed across all spinning series) and `RegionTrend` itself do not carry. Derive the window start **per spinning series** as `window_start = max(0, s.run_count - diagnosis.window)`. Emit per region one line — its focus (`step{n}` or the anchor), how many of the window's audits it recurs in (the **windowed** count `sum(1 for i in r.run_indices if i >= window_start)` of `window` — never `len(r.run_indices)`, which spans the whole series and can exceed `window` for a spinning series), and the trend `first_severity → last_severity (peak max_severity)`. (`rec.regions` still backs the fork line below; the per-series walk here is only for the windowed counts.)
      - The fork line: for `FORK_LOCALIZED`, the rationale ("one step is over-packed") + `rec.command`; for `FORK_STRUCTURAL`, the rationale ("the decomposition itself is wrong across steps") + `rec.command` + the re-seed prose note.
      - When `rec.ambiguous`, an explicit note that the evidence mixed a step-localized region with an unresolvable one, so it **defaulted cautiously to a re-seed** rather than guessing a single `--step`.

### Foundational logic and where else it lives

- **The localized-vs-structural fork** is this step's core rule and lives **only** here — there is no other cross-run fork classifier in the codebase.
- **The split-command renderer is duplicated logic to *mirror*, not consolidate now.** `plan_tool/completeness_report.py:_blocked_next_step` already builds `plan-tool split {plan_name} --step {sid} --into "<first sub-step>" --into "<second sub-step>"` for BLOCKED apply findings, and `_blocked_split_targets` resolves the `(step_id, title)` pairs. Match that command's exact shape and placeholder convention so an operator sees one consistent split recipe across `completeness` and `convergence`. Folding both onto a single shared command-builder is a behavior-preserving refactor across two modules that `detail` cannot mint — route it to `## Deferred` for reconcile rather than expanding this step's scope.

### Acyclicity

No new cross-package edges. `classify_fork` / `render_diagnosis` are pure over steps 1–3's records plus stdlib; `convergence_diagnosis.py` stays a leaf below the CLI (no `plan_tool.cli` import). Step 5 imports these three functions at module top (the leaf has no `cli` dependency).

## Tests

All new cases land in `tests/test_convergence_diagnosis.py`, unit (unmarked), built from in-test `RegionTrend` / `SeriesDiagnosis` / `ConvergenceDiagnosis` fixtures plus step 1's committed `tests/fixtures/convergence/sample-report-history.json` for the end-to-end case. Mutate in memory for variants — do not author new fixture files.

**`_region_step_focus`**
- `test_region_step_focus_prefers_step_id` — `region.step_id=5` resolves to `5` even when the anchor differs.
- `test_region_step_focus_parses_anchor_token` — `step_id=None`, anchor `step7-over-pack` resolves to `7` (reuses `_step_token`).
- `test_region_step_focus_none_for_anchor_only` — `step_id=None`, concept-slug anchor with no `step<N>` token resolves to `None`.

**`classify_fork`**
- `test_classify_fork_none_when_not_spinning` — a `converging` / `insufficient-history` / `no-history` diagnosis returns `FORK_NONE`, empty command.
- `test_classify_localized_single_region_one_step` — one spinning region on step 5 → `FORK_LOCALIZED`, `step_focus=5`, command names `--step 5`.
- `test_classify_localized_multiple_regions_same_step` — two spinning regions both resolving step 5 → `FORK_LOCALIZED`, `step_focus=5` (one over-packed step).
- `test_classify_structural_distinct_steps` — regions on step 3 and step 5 → `FORK_STRUCTURAL`, `step_focus=None`, `ambiguous=False`.
- `test_classify_structural_anchor_only_focus` — single region with no resolvable step (anchor-only) → `FORK_STRUCTURAL` (the step`<N>`-anchor-only caveat).
- `test_classify_ambiguous_mixed_resolved_and_unresolved` — one region on step 5, one anchor-only → `FORK_STRUCTURAL` with `ambiguous=True`.
- `test_classify_fork_gathers_across_spinning_series` — spinning regions drawn from two different spinning series are all collected into `regions`.

**`render_diagnosis`**
- `test_render_no_history` — `no-history` verdict: output names the empty history, contains no `plan-tool split` / `plan-tool create` command.
- `test_render_insufficient_history` — names run count vs. window; emits no recommendation.
- `test_render_converging` — a positive converging line; no split/create command.
- `test_render_spinning_localized_emits_split_command` — output contains `plan-tool split <slug> --step 5 --into "<first sub-step>"` with placeholders intact.
- `test_render_spinning_structural_emits_create_command` — output contains `plan-tool create <slug> --from-existing` and the re-seed note.
- `test_render_spinning_ambiguous_notes_cautious_reseed` — an ambiguous structural diagnosis's render states it defaulted cautiously to re-seed.
- `test_render_includes_severity_trend` — a spinning region's render shows `first_severity → last_severity (peak max_severity)` and its recur count out of the window.
- `test_render_includes_per_series_breakdown` — headline plus one line per `SeriesDiagnosis`, in series order, each naming its verdict and run count.
- `test_render_reads_plan_slug_from_diagnosis` — the printed slug equals `diagnosis.plan_slug` (not recomputed).

**End-to-end (fixture)**
- `test_diagnose_then_classify_on_spinning_fixture` — `diagnose_convergence` over the committed fixture yields `spinning`; `classify_fork` returns a non-`FORK_NONE` fork whose `command` starts with `plan-tool`, and `render_diagnosis` includes that command.

### Test-creation order (feature step)

This is a **feature** step — new fork and render behavior on steps 1–3's module. Add every test above **with** the implementation in the same change. Green-before-done gate: all new `tests/test_convergence_diagnosis.py` cases (plus steps 1–3's existing reader, region, and verdict cases) must pass before this step is complete. Run the fast loop `uv run pytest tests/test_convergence_diagnosis.py -q` during development.

## Acceptance criteria

- `classify_fork(diagnosis)` returns `FORK_NONE` with an empty command whenever the headline is not `spinning`.
- `classify_fork` returns `FORK_LOCALIZED` with the single `step_focus` **only** when every recurring region resolves (via `step_id` or a `step<N>` anchor) to one and the same step number; otherwise it returns `FORK_STRUCTURAL`.
- A spinning diagnosis whose recurring regions mix a resolvable step focus with an unresolvable one returns `FORK_STRUCTURAL` with `ambiguous=True`.
- A region whose focus came only from a bare concept-slug or title anchor (no `step<N>`) never produces a localized fork.
- The localized command is `plan-tool split <slug> --step <N> --into "<first sub-step>" --into "<second sub-step>"` with the two `--into` values left as placeholders; the structural command is `plan-tool create <slug> --from-existing <seed.md> --iterate`.
- `render_diagnosis` prints a four-state headline plus a per-series breakdown for all four verdicts; only `spinning` emits a pre-filled command and the recurring region's `first → last (peak)` severity trend.
- The rendered plan slug equals `diagnosis.plan_slug`; the renderer recomputes nothing.
- `convergence_diagnosis.py` imports no `plan_tool.cli` module and adds no import cycle.

## References

- [dataclasses — Data Classes (Python docs)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for the `ForkRecommendation` record, matching steps 1–3's frozen records.
- [textwrap — Text wrapping and filling (Python docs)](https://docs.python.org/3/library/textwrap.html) — `textwrap.dedent`/`indent` reference for composing the multi-line `render_diagnosis` block cleanly.

## Deferred

- **`plan-tool convergence` CLI wiring** — step 5: `load_report_history` → `diagnose_convergence` → `print(render_diagnosis(...))`, zero Claude, exits 0, no `--fail-on-findings` / `--min-runs`. This step adds no CLI surface.
- **Consolidating the two split-command renderers** — `completeness_report.py:_blocked_next_step` and this step's `_split_command` both build the `plan-tool split … --into "…"` recipe. Folding them onto one shared builder is a behavior-preserving cross-module refactor `detail` cannot mint; route it to reconcile.
- **Granularity-backed localized fork** — v1 localizes only off `step_id` / `step<N>` anchors. The granularity advisor's `granularity-split` findings (which would name the concern titles for `--into` and give a reliable step focus) are dropped at the producer before `save_review`, so `RegionTrend.sources` never carries them in v1. Populating real `--into` titles from granularity findings waits on the producer-change parked in the plan's `## Deferred`.
- **Structural re-seed authoring** — v1 emits the `create --from-existing <seed.md>` template only; it does not author the seed (that would spend Claude and write files, both out of v1 scope). The annotate→`create --from-existing` bridge remains the operator's manual path.
- **`--into` concern titles in the localized command** — left as placeholders because no persisted signal names the two sub-steps; the schema-contract's `split-command-placeholders` cut. Unlocked by the same granularity producer-change above.
