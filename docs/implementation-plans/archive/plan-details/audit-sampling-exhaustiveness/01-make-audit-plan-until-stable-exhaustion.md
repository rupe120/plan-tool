> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Make `audit_plan_until_stable` exhaustion-aware

## Summary

Replace the conceptual audit's "stop at 3 samples or one dry sample" rule with an exhaustion-aware stop: keep sampling while the last sample's marginal-new count stays at or above a `new_threshold` (default 1), stop only after `dry_rounds` consecutive zero-new samples (default raised to **2**), and bound the whole loop with a raised hard cap (`AUDIT_DEFAULT_MAX_SAMPLES`, raised to **8**). The core change is in `plan_tool/review.py:audit_plan_until_stable` plus the three `AUDIT_DEFAULT_*` constants; `plan_tool/cli/completeness_cmd.py` only updates the `--audit-dry-rounds` default/help and inherits the rest through the existing f-string help. An errored sample (invoker raises / non-zero exit) stays neutral — it never counts toward the dry-stop, so a flaky audit can't masquerade as convergence. When the loop reaches the cap without confirming dryness — or stops on a below-threshold-but-still-growing tail — it emits a one-line "coverage budget-limited, not converged" log so truncation is never silent. On green, a plan that keeps discovering past 3 samples keeps sampling, a plan that goes dry in two samples still costs exactly two Claude calls, and the audit stays fully driven through the `invoker=` seam.

## Table of Contents

- [Why](#why) — the cap truncates undersampled plans and one dry round is a weak convergence proof.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files this step touches and the edit per file.
- [Implementation](#implementation) — the stop-condition rewrite, the new knob/constants, the truncation log, and the CLI/doc updates.
- [Tests](#tests) — marginal-sequence unit tests asserting the new stop points and the no-regression cost case.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors a reviewer or CI bot can confirm.
- [References](#references) — argparse, pytest monkeypatch/fixtures docs for this step.
- [Deferred](#deferred) — coverage levers and a `new_threshold` CLI flag left out of v1.

## Why

`plan_tool/review.py:audit_plan_until_stable` samples a non-deterministic conceptual check and unions findings by stable slug, but stops at `AUDIT_DEFAULT_MAX_SAMPLES = 3` or after a single dry sample (`AUDIT_DEFAULT_DRY_ROUNDS = 1`). On a real 9-step plan the marginal-new sequence was still positive at sample 3 (+3, +2, +1), so the audit stopped at the budget ceiling, not on dryness — a fresh re-run surfaced a HIGH finding the 3-sample pass never reported. One dry sample is also a weak convergence proof: the `known_anchors` slug-reuse feedback nudges later samples to re-confirm what's already found, so a sample can come back dry by redundancy while the tail is unsampled. Until one audit pass actually exhausts the finding set, the "plan keeps yielding new findings" signal that the non-convergence detector and the RUNBOOK "won't converge → re-decompose" workflow lean on stays polluted by undersampling — the operator can't tell a mis-shaped plan from an under-sampled audit.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — raise `AUDIT_DEFAULT_DRY_ROUNDS` to 2 and `AUDIT_DEFAULT_MAX_SAMPLES` to 8; add `AUDIT_DEFAULT_NEW_THRESHOLD = 1`; add a `new_threshold` parameter to `audit_plan_until_stable`; rewrite its stop condition (productive-vs-dry on the threshold, break on consecutive dry); make an errored sample distinguishable from a zero-new one so a failed sample stays neutral (never counts toward the dry-stop); emit a budget-limited truncation log when the cap is reached without a dry-stop; refresh the defaults comment.
  - `plan_tool/cli/completeness_cmd.py` — update the `--audit-dry-rounds` argparse `default` and `help` prose to match the raised default; no new flag.
  - `docs/cli/completeness-audit.md` — regenerated CLI reference reflecting the new `--audit-dry-rounds` default and the `--audit-samples` default (now 8) embedded in help.
  - `tests/test_review.py` — add stop-condition tests under `TestAuditPlanUntilStable`; add a constants-default test.

## Implementation

### `plan_tool/review.py`

- **Raise the two existing defaults and add a third**, in the `# Defaults for :func:`audit_plan_until_stable`` constant block (just above `_make_reporting_invoker`):
  - `AUDIT_DEFAULT_MAX_SAMPLES = 8` — the hard safety cap. With continue-while-productive plus a 2-dry-round stop, a converging plan stops well below this; the cap only catches a pathological plan that never goes dry.
  - `AUDIT_DEFAULT_DRY_ROUNDS = 2` — two consecutive zero-new samples is a real convergence signal; one is noise.
  - `AUDIT_DEFAULT_NEW_THRESHOLD = 1` — minimum marginal-new count for a sample to count as "productive". Default 1 means any new finding keeps the loop alive.
- **Rewrite the defaults comment** to describe the forward behavior: sample while productive, stop after two dry rounds, bounded by the hard cap; drop the "typical cost is 2-3 calls" line (cost now scales with convergence depth).
- **Add the `new_threshold` parameter** to `audit_plan_until_stable`'s keyword-only signature, beside `dry_rounds`:
  - `new_threshold: int = AUDIT_DEFAULT_NEW_THRESHOLD`.
  - Document in the docstring that a sample is "productive" when its marginal-new count is `>= new_threshold`, and the loop stops after `dry_rounds` consecutive non-productive samples or at the `max_samples` hard cap — whichever comes first.
- **Rewrite the per-sample stop logic** (today's `if new == 0: consecutive_dry += 1 … else: consecutive_dry = 0` block). Replace with a threshold test, a dry-stop flag, and a still-growing-tail flag:
  - Compute `productive = new >= max(1, new_threshold)`.
  - On productive: reset `consecutive_dry = 0` and `dry_streak_grew = False`.
  - On non-productive: increment `consecutive_dry`; if `new > 0` (below threshold yet still unioned in — the set is still growing), set `dry_streak_grew = True`. When `consecutive_dry >= max(1, dry_rounds)`, set a new local `stopped_on_dry = True` and `break`.
  - Initialize `stopped_on_dry = False` and `dry_streak_grew = False` before the `while samples < cap` loop.
  - **Backward-compatible:** with `new_threshold=1`, `productive` is exactly `new >= 1`, i.e. the old `new != 0`, and `dry_streak_grew` can never be set (a non-productive sample has `new == 0`) — every caller passing explicit `dry_rounds`/`max_samples` keeps its current behavior.
  - **A threshold-triggered stop is not silent convergence.** When `new_threshold > 1`, the dry-stop can fire on below-threshold-but-nonzero samples that still grew the set; `dry_streak_grew` records that so the truncation log below fires instead of declaring convergence — the threshold knob can't converge silently while the set still grows.
- **Distinguish an errored sample from a genuinely zero-new one.** `check_plan_audit` returns `[]` both when a sample legitimately finds nothing new *and* when the invoker raises or exits non-zero (`review.py:check_plan_audit`), so without a signal a transient failure is indistinguishable from convergence — two consecutive failures would reach `dry_rounds=2`, set `stopped_on_dry=True`, and pass the `cap > 1 and not stopped_on_dry` gate, emitting **no** warning ("all clear, converged"). Make the per-sample failure observable so `audit_plan_until_stable` can tell the two apart: have `check_plan_audit` distinguish a no-findings success from an invoker error (return/raise a distinguishable error result), or catch the invoker error in the loop. An errored sample must be **neutral**: it does not increment `consecutive_dry` (a failure never advances toward the dry-stop) and never sets `stopped_on_dry` — so a flaky audit can never masquerade as convergence. It still counts against the `cap` sample budget (so a persistently failing invoker can't loop unbounded), and the loop emits a per-sample warning noting the sample errored. Because errors never set `stopped_on_dry`, a run that exhausts the cap on errored samples falls through to the budget-limited truncation log below rather than reporting convergence.
- **Emit the budget-limited truncation log** after the loop, before the existing `if samples > 1:` union line. Gate it so it fires only on a genuine cap hit, not the deliberate single-sample mode:
  - Condition: `cap > 1 and (not stopped_on_dry or dry_streak_grew)`. The loop emits the log when it ran out of cap before two dry samples (budget-limited) **or** when the dry-stop fired on a still-growing tail (any nonzero marginal-new at the stop point, `dry_streak_grew`) — either way convergence is unconfirmed and must not be silent. Only a truly zero-new dry tail (`stopped_on_dry` with `dry_streak_grew` false) is clean convergence and emits no log.
  - Message (via the existing `tool(...)` helper, `stream=out`, `level="warning"`): note the loop stopped at the `cap`-sample hard cap with convergence unconfirmed, and that the operator can raise `--audit-samples` for deeper coverage. Mirror the wording style of the existing `plan-audit: unioned …` line.
  - Keep the existing `if samples > 1:` union line and the per-sample `tool(...)` line (gated `cap > 1`) unchanged.
- **Leave the rest untouched:** the `invoker=` seam, `_make_reporting_invoker`, the `known_anchors` slug-reuse feedback (the `known_anchors=[(r.anchor, r.title) …]` argument), union-by-`rec.id` first-occurrence-wins dedupe, `run_logger.bind_shell_sink` logging, and the `max_samples <= 1` single-sample fallback (`cap = max(1, max_samples)`).

### `plan_tool/cli/completeness_cmd.py`

- **Update the `--audit-dry-rounds` argument only**, in the `p_completeness.add_argument("--audit-dry-rounds", …)` block:
  - `default=AUDIT_DEFAULT_DRY_ROUNDS` already references the constant, so the numeric default follows the bump automatically — no literal to change there.
  - Update the `help` prose: the default is now 2; reword the trailing "Detecting dryness needs >=2 samples, so the typical cost is 2-3 calls" line, which no longer holds (cost scales with how long the plan keeps discovering). State that two consecutive no-new samples is the convergence proof and the loop is bounded by the `--audit-samples` hard cap.
- **No new CLI flag.** `new_threshold` stays an internal function knob (default 1); the plan keeps the raised defaults internal rather than adding a `--audit-new-threshold` surface (see Deferred).
- **`--audit-samples` needs no code edit:** its help is an f-string on `AUDIT_DEFAULT_MAX_SAMPLES`, so the displayed default tracks the bump to 8 automatically; the "1 reproduces the legacy single-call behavior" line stays true.
- **Inheriting consumers need no change:** `_effective_audit_samples` (coalesces `audit_samples is None` → `AUDIT_DEFAULT_MAX_SAMPLES`), `_audit_dry = getattr(args, "audit_dry_rounds", AUDIT_DEFAULT_DRY_ROUNDS)` in `cmd_completeness`, and the iterate-loop call to `audit_plan_until_stable` (in `_run_iterate_convergence_loop`) all read the constants/args, so they pick up the new defaults with no edit.

### `docs/cli/completeness-audit.md`

- **Regenerate, don't hand-edit.** This file is the generated CLI reference, drift-guarded by `tests/cli/test_cli_reference.py`. After the `completeness_cmd.py` help/default change, regenerate with `python -m plan_tool.cli_reference --write`.
- The diff is limited to the `--audit-dry-rounds` row (default `1` → `2`, new help prose) and the `--audit-samples` row (help default `3` → `8`). The usage line is unchanged (no new flag).

### Out-of-footprint consumers (no edit — confirm only)

- `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` passes `max_samples` / `dry_rounds` through to `audit_plan_until_stable` and does **not** pass `new_threshold`, so it picks up the default 1 with no change. It is not in this step's `files:` and stays untouched.
- `plan_tool/cli/app.py` re-imports `AUDIT_DEFAULT_DRY_ROUNDS` / `AUDIT_DEFAULT_MAX_SAMPLES` for the package surface; raising the values is transparent to the re-export.

## Tests

All tests drive `audit_plan_until_stable` through the injected `invoker=` seam — no real `claude` spawn (the `tests/conftest.py` autouse gate raises on a registered backend binary). New cases live under `tests/test_review.py:TestAuditPlanUntilStable`, reusing its `_sampling_invoker` (one queued response per call, raises if over-called) and `_sections(*slugs)` helpers.

- `test_two_dry_rounds_required_to_stop` — sequence `["a", "b", "a", "b"]` with `dry_rounds=2`, `max_samples=8`: one dry sample (3rd) does **not** stop; asserts a 4th call happens. Pin that a single no-new sample is no longer a stop.
- `test_stops_after_two_consecutive_dry_rounds` — sequence yielding `[+new, +new, 0, 0]` with `dry_rounds=2`: stops after the second consecutive dry sample; asserts exactly 4 invoker calls and the unioned finding set.
- `test_keeps_sampling_while_productive_past_three` — five productive samples (each a new slug) with `max_samples=5`, `dry_rounds=2`: asserts more than 3 calls (the old cap) and all five findings unioned — the cap no longer truncates a still-discovering plan.
- `test_hard_cap_stops_and_logs_budget_limited` — every sample productive (new slug each call) with `max_samples=3`, `dry_rounds=2`: asserts exactly 3 calls (cap hit) and that the captured stderr/log contains the "budget-limited / stopped at cap" truncation line.
- `test_dry_stop_emits_no_truncation_log` — sequence that goes dry (`[+new, 0, 0]`, `dry_rounds=2`): asserts the truncation log is **absent** (`stopped_on_dry` path) and exactly 3 calls.
- `test_no_regression_two_sample_dry_costs_two_calls` — sequence `[+new, 0]` with `dry_rounds=1` (explicit, legacy value): asserts exactly 2 invoker calls — explicit-arg callers keep their behavior.
- `test_new_threshold_treats_low_yield_as_dry` — `new_threshold=2`, sequence where a sample adds exactly 1 new finding: that 1-new sample counts as non-productive; with `dry_rounds=1` the loop stops on it. Pins the threshold knob.
- `test_low_yield_stop_emits_budget_limited_log` — `new_threshold=2`, `dry_rounds=2`, a tail of two samples each adding exactly 1 new finding (below threshold, still growing): the loop stops but the captured log contains the budget-limited / not-converged line — a threshold stop on a still-growing set is never silent (`dry_streak_grew` path).
- `test_single_sample_cap_emits_no_truncation_log` — `max_samples=1`: one call, no truncation log (the `cap > 1` gate suppresses it for the deliberate single-sample mode).
- `test_errored_samples_do_not_count_as_dry` — invoker fails (raises / non-zero exit) on two consecutive samples with `dry_rounds=2`, `max_samples=8`: asserts the failures do **not** set `stopped_on_dry`, the loop does not report convergence, and a budget-limited / error warning is emitted (a flaky audit never masquerades as "all clear, converged").
- `test_audit_default_constants` — asserts `AUDIT_DEFAULT_DRY_ROUNDS == 2`, `AUDIT_DEFAULT_MAX_SAMPLES == 8`, and `AUDIT_DEFAULT_NEW_THRESHOLD == 1`.

Existing cases in `TestAuditPlanUntilStable` (`test_unions_across_samples_and_stops_on_dry_round`, `test_max_samples_caps_even_without_dry_round`, `test_single_sample_reproduces_legacy_behavior`, `test_first_occurrence_wins_on_duplicate_id`, `test_later_samples_see_accumulated_slugs`) pass explicit `dry_rounds`/`max_samples`, so they stay green unmodified. `tests/cli/test_completeness_cmd.py` (passes explicit `max_samples`/`dry_rounds` to `_sample_conceptual_audit`) and `tests/cli/test_cli_reference.py` (after regen) also stay green.

### Test-creation order (feature step)

This is a **feature** step — new stop-condition behavior. Add each unit test above **with** the implementation it covers (threshold rewrite → the dry/threshold/regression tests; truncation log → the cap/no-log tests; constant bumps → `test_audit_default_constants`). Green-before-done gate: every new test, plus the unmodified existing `TestAuditPlanUntilStable` cases, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_cli_reference.py`, must be green before this step is considered finished.

## Acceptance criteria

- `AUDIT_DEFAULT_DRY_ROUNDS == 2` and `AUDIT_DEFAULT_MAX_SAMPLES == 8` in `plan_tool/review.py`; `AUDIT_DEFAULT_NEW_THRESHOLD == 1` exists.
- A single no-new sample no longer stops the loop; two consecutive zero-new samples do.
- The loop keeps sampling while the last sample's marginal-new count is `>= new_threshold`, up to the hard cap; a plan still discovering at the old 3-sample point keeps going (a 5-productive-sample run makes >3 calls).
- When the cap is reached without two consecutive dry samples, the run emits a "coverage budget-limited / stopped at cap, not converged" log; a dry-stop on a truly zero-new tail emits no such log.
- A dry-stop that fires on below-threshold-but-nonzero samples (any nonzero marginal-new at the stop point, e.g. `new_threshold > 1`) still emits the budget-limited log — the threshold knob can't declare convergence while the set is still growing.
- A run with `max_samples=1` makes one call and emits no truncation log.
- An errored sample (invoker raises / non-zero exit) is neutral: it does not increment `consecutive_dry` and never sets `stopped_on_dry`, so consecutive failures never report convergence — the run surfaces the failure instead of reading as "all clear, converged."
- A shallow run that goes dry in two samples (`dry_rounds=1`) costs exactly two invoker calls.
- `audit_plan_until_stable` is exercised entirely through the injected `invoker=` seam in all new tests; no real `claude` spawn.
- `python -m plan_tool.cli_reference --write` produces no further diff after the `completeness_cmd.py` edit (the regenerated `docs/cli/completeness-audit.md` is committed); `tests/cli/test_cli_reference.py` passes.
- Existing `TestAuditPlanUntilStable` and completeness CLI tests stay green unmodified.

## References

- [argparse — add_argument (Python docs)](https://docs.python.org/3/library/argparse.html) — `type=int` / `default` / `help` semantics for the `--audit-dry-rounds` default and help update.
- [pytest — monkeypatch (docs)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — `setattr`-style patching pattern behind the `invoker=` seam override the stop-condition tests rely on.
- [pytest — fixtures (docs)](https://docs.pytest.org/en/stable/how-to/fixtures.html) — authoring/scoping the hermetic `tmp_path` fixtures the new tests use.

## Deferred

- **`--audit-new-threshold` CLI flag** — `new_threshold` stays an internal function knob in v1 (default 1); add a CLI surface only if operators need to tune it. Tracked here, not built now.
- **Per-step audit fan-out** — auditing each step's detail independently and unioning; a bigger change to the audit's shape, revisit after the adaptive stop proves out.
- **Diversified sample lenses** — varying each sample's framing (correctness / completeness / edge-case) to decorrelate samples; out of scope (prompt content is unchanged this step).
- **In-loop post-apply conceptual re-sample** — `--iterate` still re-runs only deterministic checks after an apply; adding a fresh conceptual sample post-mutation is separate work.
- **Feeding the per-run sample count / "stopped at cap" signal into the non-convergence detector (BACKLOG #57)** so it can distinguish budget-limited coverage from real recurrence — left for that detector's own work.
