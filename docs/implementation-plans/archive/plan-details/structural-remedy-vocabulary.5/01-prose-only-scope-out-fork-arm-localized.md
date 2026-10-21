> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a prose-only scope-out sub-arm to the localized convergence fork

## Summary

- Adds a third sub-arm — **scope-out / defer** — to the localized branch of `plan_tool/convergence_diagnosis.py:classify_fork`. Re-split and scope-out become the two sub-arms of the localized fork; the structural re-seed branch is unchanged.
- Introduces one new fork state constant `FORK_SCOPE_OUT` and one severity-trend predicate (`_region_triggers_scope_out`). The predicate fires when a region on the single resolved step is **currently severe and not improving**: `last_severity` at high or critical **and** a non-decreasing `first_severity → last_severity` trend. Bar 1 keys on current severity (`last_severity`), not peak-ever (`max_severity`) — a region that spiked to high once and recovered to medium does **not** fire.
- `render_diagnosis` (via `_spinning_body`) gains a prose-only scope-out arm — it describes carving the over-packed step out of the plan and deferring it, and renders **no runnable command** (the executor ships in the follow-up `scope-out-executor` plan). The key design decision: keep `step_focus` set on the scope-out recommendation but leave `command=""`, so the follow-up plan can later flip it to a runnable `plan-tool scope-out … --step N` line.
- On green: `plan-tool convergence` on a spinning plan whose localized step has any high+/not-improving region prints a distinct scope-out recommendation instead of the re-split command; medium-only or improving regions still render the existing re-split command.

## Table of Contents

- [Why](#why) — what's missing in the fork vocabulary today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files, both edits
- [Implementation](#implementation) — the new constant, predicate, classify branch, and render arm
- [Tests](#tests) — predicate, classify, and render cases plus the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — the plan-level docs relevant to this step
- [Deferred](#deferred) — what the follow-up executor plan owns

## Why

- `classify_fork` today offers only **rebuild** remedies for a spinning region: re-split one over-packed step in place (`FORK_LOCALIZED` → `_split_command`) or re-seed and re-decompose the whole plan (`FORK_STRUCTURAL` → `_reseed_command`). There is **no scope-out remedy** in the vocabulary.
- The motivating case (the PPW `prune`/clone-lifecycle work) recurred as HIGH across rounds and then **backfired into data-loss HIGHs when patched** — its one right remedy was to **carve the step out of scope and defer it**, which the tool could not recommend. A region that stays severe and stops improving is exactly the signal that in-place patching is backfiring; re-splitting it again wastes another round.
- This step adds the **advisory recommendation only** — detection is unconditional, mutation stays gated and is out of scope (the executor is the follow-up plan). The recommendation renders prose-only so it never points at a `plan-tool scope-out` command that does not exist yet.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add `FORK_SCOPE_OUT` constant; add `_region_triggers_scope_out` predicate; add the scope-out branch inside `classify_fork`'s single-resolved-step arm; add the scope-out prose arm in `_spinning_body`.
  - `tests/test_convergence_diagnosis.py` — add predicate, `classify_fork`, and `render_diagnosis` cases for the scope-out arm; extend the import block with the two new symbols.

## Implementation

### `plan_tool/convergence_diagnosis.py`

**Foundational logic of this step:** a severity-trend predicate (current-severity floor on `last_severity` + non-decreasing first→last trend) that gates a third sub-arm of the localized fork. This predicate is new and unique to this module — no other file forks the localized/structural decision or renders the convergence fork. The only consumers of the fork state are `classify_fork` and `_spinning_body`, both edited here.

- **Add the fork-state constant** beside `FORK_LOCALIZED` / `FORK_STRUCTURAL` / `FORK_NONE`:
  - `FORK_SCOPE_OUT = "scope-out"` — one step is over-packed and severe-and-not-improving; carve it out of the plan and defer it.
  - Keep the existing docstring convention ("the fork states step 4's render and step 5's CLI key on — do not inline the literals downstream").

- **Add the severity-trend predicate** `_region_triggers_scope_out(region: RegionTrend) -> bool`:
  - **Bar 1 — currently severe:** `_SEVERITY_RANK[region.last_severity.lower()] >= _SEVERITY_RANK["high"]` (the region is *still* at high or critical, keyed on `last_severity` — not `max_severity`, the peak ever reached). A region that spiked to high once and recovered to medium has `last_severity = medium` and fails this bar, so the trigger matches "stays severe."
  - **Bar 2 — not improving:** `_SEVERITY_RANK[region.last_severity.lower()] >= _SEVERITY_RANK[region.first_severity.lower()]` (the `first → last` trend held flat or worsened).
  - Return `severe and not_improving`. One such region on the resolved step is enough.
  - **Lowercase before every `_SEVERITY_RANK` lookup** — `RegionTrend` severities come from `_max_severity_str`, which returns the raw severity string and may be uppercase (e.g. `"HIGH"`); a raw-case lookup would `KeyError`. This mirrors the existing lowercase guard documented on `_SEVERITY_RANK`.
  - Regions reaching here are already scoped to medium+ by `recurring_regions` (the `is_blocking` filter), so `_SEVERITY_RANK[...]` is always populated after lowering.
  - **Reuse `_SEVERITY_RANK`** as the single severity-order source (the module already documents it as the one source for severity ranking).
  - **Deliberately do not reuse `_ADVISORY_SEVERITIES`** for bar 1. That frozenset is `{critical, high}` and would compute the same boolean today, but it is the **run-readiness advisory** severity set used by `_latest_blocking_findings` — a different concept. Coupling the scope-out bar to it would silently shift this trigger if that advisory set ever changes. Expressing bar 1 over `_SEVERITY_RANK` keeps the two independent.

- **Edit `classify_fork`** — branch inside the existing single-resolved-step arm:
  - The current arm is entered when `None not in foci and len(resolved) == 1`; in that arm **every** recurring region resolves to the **same** step, so all `regions` are co-located on it.
  - After resolving `step`, check `any(_region_triggers_scope_out(r) for r in regions)`:
    - **True →** `return ForkRecommendation(FORK_SCOPE_OUT, step, "", regions, False)` — carry `step_focus=step` (so the follow-up executor plan can flip the empty command to `--step N`), `command=""` (prose-only, decision 4), `ambiguous=False`.
    - **False →** keep the current `FORK_LOCALIZED` return with `_split_command(diagnosis.plan_slug, step)`.
  - **Update the `ForkRecommendation.step_focus` inline comment** — it currently reads `# set only on FORK_LOCALIZED, else None`, which the new arm contradicts (scope-out sets `step_focus=step` too). Change it to `# set on FORK_LOCALIZED and FORK_SCOPE_OUT, else None`.
  - **Leave the structural branch untouched.** Distinct foci, any unresolvable region, or no resolvable focus still falls to `FORK_STRUCTURAL` with `_reseed_command` and the existing `ambiguous` flag. Scope-out fires **only** in the single-resolved-step case, including several co-located regions that all resolve to that one step; distinct-step or unresolvable evidence never reaches it (the follow-up executor is single-step `--step N`; multi-step carve is deferred there).
  - `FORK_NONE` (not spinning) is unchanged.

- **Edit `_spinning_body`** — add the scope-out arm before the localized/structural split:
  - The per-region severity-trend lines (`_spinning_trend_lines`) are emitted first and are independent of the fork arm — unchanged.
  - Restructure the fork dispatch to three explicit branches: `if rec.fork == FORK_SCOPE_OUT: … elif rec.fork == FORK_LOCALIZED: … else: # FORK_STRUCTURAL`.
  - The scope-out branch appends **prose only, no command line**. State both halves of the altitude (architecture note `scope-out-altitude`): the trigger is the localized over-packed step (`step {rec.step_focus}`), but the remedy **acts at plan scope** — carve that step out of the plan into a forward-seed and defer it so the rest of the plan converges, then re-plan the carved work on its own. Word it so it reads as "patching this step in place is backfiring." Do **not** emit any `plan-tool scope-out …` / `plan-tool split …` / `plan-tool create …` line in this arm.
  - The localized (`_split_command`) and structural (`_reseed_command` + the hand-author note + the `ambiguous` note) arms keep their current text.

## Tests

Reference: `tests/test_convergence_diagnosis.py`. Reuse the existing in-memory builders `_fork_region` (accepts `step_id`, `anchor`, `focus`, `first`, `last`, `peak`), `_series`, and `_diag`. Extend the top-of-file import block with `FORK_SCOPE_OUT` and `_region_triggers_scope_out`.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add these unit tests **with** the implementation. Every new test must be green, and the full `tests/test_convergence_diagnosis.py` suite must stay green, before the step is considered finished.

Predicate (`_region_triggers_scope_out`):

- `test_scope_out_region_high_flat_trend` — region `first=high, last=high, peak=high` → True.
- `test_scope_out_region_critical_peak_rising_trend` — `first=medium, last=high, peak=critical` → True (non-decreasing trend, `last_severity` ≥ high).
- `test_no_scope_out_region_below_high` — `first=medium, last=medium, peak=medium` → False (fails bar 1).
- `test_no_scope_out_region_improving_trend` — `first=high, last=medium, peak=high` → False (recovered below high, so bar 1's `last_severity` check fails).
- `test_no_scope_out_region_recovered_spike` — `first=medium, last=medium, peak=high` → False (peaked at high once but currently medium; bar 1 reads `last_severity`, not the `max_severity` peak).
- `test_scope_out_region_uppercase_severity` — `first="MEDIUM", last="HIGH", peak="CRITICAL"` → True (lowercase guard before `_SEVERITY_RANK`).

`classify_fork`:

- `test_classify_scope_out_single_step_severe_region` — one spinning series, single region on step 5 with `peak=high, first=high, last=high` → `fork == FORK_SCOPE_OUT`, `step_focus == 5`, `command == ""`, `ambiguous is False`.
- `test_classify_scope_out_any_co_located_region_trips` — two regions both on step 5, one medium and one high-and-flat → `FORK_SCOPE_OUT` (any co-located region clearing both bars suffices).
- `test_classify_localized_when_region_improving` — single region on step 5, `peak=high` but `first=high, last=medium` (improving) → stays `FORK_LOCALIZED`, `command` contains `--step 5`.
- `test_classify_localized_when_below_high_unchanged` — single medium region on step 5 → stays `FORK_LOCALIZED` (guards the existing path against regression).
- `test_classify_scope_out_not_for_distinct_steps` — two high-and-flat regions on steps 3 and 5 → `FORK_STRUCTURAL` (scope-out never fires on multi-step evidence), `command` contains `plan-tool create`.

`render_diagnosis`:

- `test_render_scope_out_prose_no_command` — spinning diagnosis whose single step has a high-and-flat region. Assert the output names the step and describes carving/deferring it (scope-out), the per-region severity-trend line is still present, and the output contains **no** `plan-tool split`, `plan-tool scope-out`, or `plan-tool create` command line.

Already-green regression guards (no edits needed, confirm they stay green): `test_classify_localized_single_region_one_step` and `test_render_spinning_localized_emits_split_command` use default medium-severity regions, so they keep classifying as `FORK_LOCALIZED`; `test_diagnose_then_classify_on_spinning_fixture` consumes the all-medium `sample-report-history.json` fixture, so it keeps rendering the split command; `test_render_includes_severity_trend` asserts only the trend line, which is unchanged.

## Acceptance criteria

- `classify_fork` returns `FORK_SCOPE_OUT` with `step_focus` set to the resolved step and `command == ""` when the diagnosis is spinning, the localized fork resolves to a single step, and any co-located region on that step has `last_severity ≥ high` and a non-decreasing `first → last` severity trend.
- `_region_triggers_scope_out` returns False for any region whose `last_severity` is below high (including a recovered spike whose `max_severity` reached high but ended lower), or whose `last_severity` rank is below its `first_severity` rank (improving), and tolerates uppercase severity strings.
- A medium-only or improving localized region still returns `FORK_LOCALIZED` with the `plan-tool split … --step N` command (no behavior change).
- Distinct-step or unresolvable evidence still returns `FORK_STRUCTURAL` with the re-seed command — scope-out never fires there.
- `render_diagnosis` on a scope-out diagnosis prints a scope-out/defer recommendation that names the step and renders **no** runnable command line; the per-region severity-trend line is still present.
- All new tests pass and the full `tests/test_convergence_diagnosis.py` suite is green.

## References

- `plan_tool/convergence_diagnosis.py` — `classify_fork`, `ForkRecommendation`, `RegionTrend` (`first_severity` / `last_severity` / `max_severity`), `_SEVERITY_RANK`, `_ADVISORY_SEVERITIES`, `_split_command` / `_reseed_command`, `_spinning_body`, `render_diagnosis`; the surfaces this step edits.
- `plan-seeds/scope-out-executor.md` — the follow-up executor plan that flips this prose-only recommendation into a runnable `plan-tool scope-out … --step N` command for the single-step case; explains why `step_focus` is carried now and `command` left empty.
- `docs/implementation-plans/2-structural-remedy-vocabulary.md` — the plan; decision 1 (the scope-out trigger over the localized region set) and decision 4 (prose-only, no forward-ref command) ground this step.
- `MISSION.md` — the *always surface the more-correct plan* principle: detection unconditional, mutation gated — this step adds detection only.

## Deferred

- **Flipping the scope-out arm to a runnable `plan-tool scope-out … --step N` line in `render_diagnosis`** — held prose-only until the `scope-out-executor` follow-up plan ships the gated executor; that plan reads `step_focus` and fills the now-empty `command`.
- **Multi-step carve** — out of scope here and in the executor's first cut; distinct-step evidence falls to `FORK_STRUCTURAL` (re-seed), never scope-out.
- **Any plan mutation / forward-seed emission** — owned entirely by the `scope-out-executor` plan; this step writes no files and spends no Claude.
