> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract the fingerprint staleness verdict out of `_actuate_scope_out` into a shared helper

## Summary

Pull the fingerprint-staleness classification currently inlined in `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` into a small shared helper that both this actuator and step 2's future `_actuate_split` can call. The helper compares the newest saved run's `plan_fingerprint` against the current plan's fingerprint and returns one verdict — fresh, stale-mismatch, or unverifiable — with no message rendering of its own. `_actuate_scope_out` keeps every existing `info(...)` / `warn(...)` string, its `-y` handling, and its control flow unchanged; only the decision of *which* staleness state we're in moves into the helper. This is behavior-preserving: the existing `--apply-scope-out` tests in `tests/cli/test_convergence_cmd.py` must pass unchanged, and green means the staleness decision is now single-sourced for step 2 to reuse.

## Table of Contents

- [Why](#why) — the split arm (step 2) needs the same staleness short-circuit, so the decision must stop being private to scope-out
- [Input](#input) — the saved report history and fingerprint fields this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one module edit plus its test file
- [Implementation](#implementation) — the verdict constants, the classifier, and how `_actuate_scope_out` consumes it without changing behavior
- [Tests](#tests) — characterization tests to pin first, then direct helper unit tests
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the argparse/json docs relevant to this seam
- [Deferred](#deferred) — the split-arm consumer and messaging, owned by step 2

## Why

Today the fingerprint-staleness check lives entirely inside `plan_tool/cli/convergence_cmd.py:_actuate_scope_out`: it computes the current plan fingerprint, reads the newest saved run's `plan_fingerprint`, and decides whether the saved diagnosis is fresh enough to actuate a carve. Step 2 adds a sibling actuator `_actuate_split` for a spinning `FORK_LOCALIZED` verdict, and it must bail out on a stale saved report the exact same way — actuating a re-split against fingerprints that no longer match the code is the same hazard as carving against them. If the classification stays private to `_actuate_scope_out`, step 2 either copies it (two sources that can drift) or reaches into scope-out's flow. Hoisting the decision into a shared helper now, behind characterization tests, lets step 2's new arm consume one verdict without duplicating the fingerprint comparison.

## Input

This step reads the saved report history that `plan_tool.convergence_diagnosis.load_report_history` already returns and `cmd_convergence` already holds:

- **`history.runs`** — a list of `RunSnapshot` (see `plan_tool/convergence_diagnosis.py`), sorted oldest→newest. This step reads only the newest entry (`history.runs[-1]`) when the list is non-empty.
- **`RunSnapshot.plan_fingerprint`** — a `str`, with `""` as the persistence sentinel for "no fingerprint captured" (a legacy run predating fingerprint capture, or a producer that left it empty). The empty case is a distinct verdict, not a mismatch — the current code treats it that way and this step must preserve that.
- **`compute_plan_fingerprint(path)`** — from `plan_tool.review_persistence`, already imported into `plan_tool/cli/convergence_cmd.py`; returns the current plan's fingerprint. Reads the plan file on disk.

The classification depends only on those two fingerprint strings; no other field of the history or diagnosis feeds it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/convergence_cmd.py` — add the verdict constants and the shared classifier helper; rewrite `_actuate_scope_out` to call it and switch on the returned verdict while keeping its existing messages and flow.
  - `tests/cli/test_convergence_cmd.py` — add direct unit tests for the new helper covering each verdict; keep the existing `--apply-scope-out` cases unmodified as the characterization contract.

## Implementation

**Add three module-level verdict constants**, mirroring the plain string-constant style `plan_tool/convergence_diagnosis.py` uses for `FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL`:

- `STALENESS_FRESH` — the newest saved fingerprint matches the current plan (or the current fingerprint is empty, so there's nothing to contradict). Actuators proceed.
- `STALENESS_MISMATCH` — newest and current fingerprints are both non-empty and differ. The saved diagnosis is provably stale; actuators recommend-only.
- `STALENESS_UNVERIFIABLE` — the newest saved fingerprint is empty, so freshness can't be proven either way. Actuators refuse a blind `-y` carve but allow an interactive one after warning.

Use whatever concrete form matches the file's neighbors (plain `str` constants like the fork kinds is the natural fit; an `Enum` is acceptable if you prefer, but stay consistent with `convergence_diagnosis.py`).

**Add a shared classifier**, e.g. `classify_report_staleness(path, history) -> str`:

- Compute `current_fp = compute_plan_fingerprint(path)` and `newest_fp = history.runs[-1].plan_fingerprint if history.runs else ""` — the same two lines currently inside `_actuate_scope_out`.
- Return `STALENESS_MISMATCH` when `newest_fp and current_fp and newest_fp != current_fp` (this is the exact `bool(fp) and fp == current` freshness convention `plan_tool/cli/review_cmd.py` and `plan_tool/cli/reconcile.py` use for `plan_match` — an empty fingerprint on either side is never a mismatch).
- Return `STALENESS_UNVERIFIABLE` when `newest_fp` is empty.
- Return `STALENESS_FRESH` otherwise.

Keep the helper free of `args`, `info`, `warn`, and any message text — it returns a verdict only. The `-y` refinement (blind-refuse vs warn-then-proceed within the unverifiable state) stays in each actuator, because that branch is coupled to arm-specific messaging. One way to see it: the helper owns the fingerprint comparison; the caller owns what to *say* and whether `-y` is allowed.

**Rewrite `_actuate_scope_out` to consume the verdict without changing behavior:**

- Call the helper at the same point it computes the fingerprints today — after the `rec.fork != FORK_SCOPE_OUT or rec.step_focus is None` early return, before the carve. Preserve that ordering; the fingerprint read must not move relative to the fork check or the seed-glob capture.
- Map each verdict to the branch that exists now, keeping the `info(...)` / `warn(...)` strings and their exit paths identical:
  - `STALENESS_MISMATCH` → the current "predates the current … Skipping the carve" `info` block, returns 0.
  - `STALENESS_UNVERIFIABLE` **and** `args.yes` → the current "predates fingerprint capture … refusing to carve blind under -y" `info` block, returns 0.
  - `STALENESS_UNVERIFIABLE` **and not** `args.yes` → the current `warn` about confirming the step is still over-packed, then fall through to the interactive carve.
  - `STALENESS_FRESH` → fall through to the carve with no warning.
- Leave everything downstream untouched: the `seeds_before` glob capture, the `scope_out_step(...)` call, the `NarrowError` orphan-seed handling, and the `recommend_hint` branch (which already keys off `newest_fp`). If you no longer keep `newest_fp` as a local after extracting, note that the `recommend_hint` branch needs the unverifiable-vs-fresh distinction — either keep a local for it or re-derive it from the verdict; the observable hint text must not change.

**Constraints and gotchas:**

- **Behavior-preserving only.** No new user-visible strings, no changed exit codes, no reordered side effects. The characterization tests below are the contract.
- **Empty fingerprint ≠ mismatch.** The single most important invariant: an empty `newest_fp` must classify as `STALENESS_UNVERIFIABLE`, never `STALENESS_MISMATCH`, and an empty `current_fp` must not force a mismatch. Getting this wrong silently flips a legacy run into a hard block or vice versa.
- **Keep the import surface as-is.** `compute_plan_fingerprint` is already imported at module top; the helper reuses it. The module stays a cycle-free per-intent command module importing only leaves and domain packages — never `plan_tool.cli.app`.
- **Foundational logic shared elsewhere.** The same `bool(fp) and fp == current` freshness rule appears in `plan_tool/cli/review_cmd.py` (`plan_match`) and `plan_tool/cli/reconcile.py` (`plan_match` / `ReusableReconcile`). This step does **not** consolidate those — they classify a `SavedReview`'s freshness for reconcile/review reporting, a different surface with its own `code_fingerprint` axis and dataclass. Folding them together is a cross-module refactor `detail` can't mint; see Deferred.

## Tests

Test file: `tests/cli/test_convergence_cmd.py`.

### Test-creation order (refactor step)

This is a **refactor** step — behavior-preserving. The existing `--apply-scope-out` cases in `tests/cli/test_convergence_cmd.py` already pin `_actuate_scope_out`'s staleness behavior end-to-end through `main(argv)`; treat them as the characterization suite and confirm they are green **before** touching `convergence_cmd.py`. The ones that pin each staleness state:

- `test_apply_scope_out_stale_fingerprint_recommends_only` — pins `STALENESS_MISMATCH`: a non-matching saved fingerprint recommends only, mutates nothing, prints "predates the current".
- `test_apply_scope_out_empty_fingerprint_refuses_blind_under_yes` — pins `STALENESS_UNVERIFIABLE` + `-y`: empty fingerprint refuses the blind carve, prints "predates fingerprint capture", mutates nothing.
- `test_apply_scope_out_empty_fingerprint_warns_before_interactive_carve` — pins `STALENESS_UNVERIFIABLE` interactive: empty fingerprint warns, then the confirmed carve still proceeds and narrows the plan.
- `test_apply_scope_out_carves_on_scope_out_fork` — pins `STALENESS_FRESH`: a matching fingerprint carves.
- `test_no_flag_is_unchanged_read_only` — pins that the no-flag path never reaches the helper and mutates nothing.

**Pass-unchanged-after gate:** every listed characterization test must stay green, unmodified, after the extraction. Do not edit their assertions to fit a new helper — if one needs changing, the refactor changed behavior and is wrong.

Then add direct unit tests for the new helper (the hard-to-observe boundary — the classification given fabricated inputs, without driving a full carve):

- `test_classify_staleness_fresh_when_fingerprints_match` — matching newest/current fingerprints → `STALENESS_FRESH`.
- `test_classify_staleness_mismatch_when_both_present_and_differ` — two distinct non-empty fingerprints → `STALENESS_MISMATCH`.
- `test_classify_staleness_unverifiable_when_newest_empty` — empty newest fingerprint (with a non-empty current) → `STALENESS_UNVERIFIABLE`, not mismatch.
- `test_classify_staleness_unverifiable_when_no_runs` — an empty `history.runs` (no saved runs) yields `newest_fp=""` → `STALENESS_UNVERIFIABLE`, matching the empty-`newest_fp` rule and what `_actuate_scope_out` did before (an empty newest fingerprint is never a mismatch).

## Acceptance criteria

- A shared classifier in `plan_tool/cli/convergence_cmd.py` returns one of `STALENESS_FRESH` / `STALENESS_MISMATCH` / `STALENESS_UNVERIFIABLE` given a plan path and a report history, and renders no message.
- The classifier returns `STALENESS_MISMATCH` only when the newest and current fingerprints are both non-empty and differ; an empty fingerprint on either side never yields `STALENESS_MISMATCH`.
- `_actuate_scope_out` no longer contains an inline fingerprint comparison — it switches on the classifier's verdict — while emitting the same `info`/`warn` strings and returning the same exit codes as before.
- All existing `--apply-scope-out` tests in `tests/cli/test_convergence_cmd.py` pass unchanged.
- The new helper unit tests pass, one per verdict plus the empty-history case.
- `uv run pytest tests/cli/test_convergence_cmd.py -q` is green.

## References

- `plan_tool/convergence_diagnosis.py` (`load_report_history`, `RunSnapshot.plan_fingerprint`) — the saved report history and the newest run's `plan_fingerprint` string the classifier reads.
- `plan_tool/review_persistence.py` (`compute_plan_fingerprint`) — the current plan fingerprint the classifier compares the saved value against.
- [How to monkeypatch/mock modules and environments (pytest docs)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — For the existing `--apply-scope-out` cases that monkeypatch `sys.stdin.isatty` / `plan_tool.scope_out.apply_narrow`; keep those patterns intact when the characterization tests stay unchanged.

## Deferred

- **`_actuate_split` consuming the helper** — step 2 adds the split actuator and wires it to the same verdict; this step only makes the decision shareable. (owned by step 2)
- **Split-arm staleness messages** — the parallel "re-split" wording for the mismatch/unverifiable states belongs with `_actuate_split`, not here. (owned by step 2)
- **Consolidating the `plan_match` freshness rule across `review_cmd.py` / `reconcile.py`** — those surfaces classify a `SavedReview`'s freshness (with a `code_fingerprint` axis) for reconcile/review reporting, a broader refactor beyond this step's two-file footprint. Left for a dedicated consolidation change; route to reconcile if it should happen.
