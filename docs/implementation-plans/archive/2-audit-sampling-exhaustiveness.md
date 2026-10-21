> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Audit Sampling Exhaustiveness
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: 'Make audit_plan_until_stable exhaustion-aware: dry_rounds default 2, raised
    hard cap, new_threshold knob, and a budget-limited truncation log'
  files:
  - plan_tool/review.py
  - plan_tool/cli/completeness_cmd.py
  - docs/cli/completeness-audit.md
  - tests/test_review.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/audit-sampling-exhaustiveness/01-make-audit-plan-until-stable-exhaustion.md
  status: done
---
# Audit Sampling Exhaustiveness

## Overview

Make the conceptual completeness audit's sampling exhaustion-aware so one pass captures the stable finding set instead of just the first three samples' worth. The audit (`review.audit_plan_until_stable`) samples a non-deterministic Claude check N times and unions findings by stable slug; today it stops at `max_samples = 3` or after a single dry sample (`dry_rounds = 1`), which truncates an unconverged process on deep plans. The v1 change replaces that stop condition with: keep sampling while the last sample's marginal-new count stays at or above a threshold, stop only after `dry_rounds ≥ 2` consecutive zero-new samples, and bound the whole thing with a raised hard safety cap that logs when coverage was budget-limited. Scope is the adaptive stop condition only — the bigger coverage levers (per-step fan-out, diversified lenses, in-loop re-sample) are deferred.

## Problem statement

`review.py:audit_plan_until_stable` (defaults at `review.py:4319`) sets `AUDIT_DEFAULT_MAX_SAMPLES = 3` and `AUDIT_DEFAULT_DRY_ROUNDS = 1`. The loop unions findings by stable slug and breaks on `consecutive_dry >= dry_rounds` or at `max_samples`. Two defects:

1. **The cap truncates while still discovering.** On a real 9-step plan (`escalate-structural-findings-to-split`) the marginal-new sequence was sample 1 → +3 new (3 unique), sample 2 → +2 new (5 unique), sample 3 → +1 new (6 unique) — still positive. It stopped at the budget ceiling, not on dryness; sample 4+ would very likely have found more. A corroborating fresh `--no-reuse-audit` run on the same plan surfaced a HIGH finding (`guard-b-create-side`, a real create-side trigger-2 inconsistency) the earlier 3-sample pass never reported. One pass does not see the whole set.

2. **`dry_rounds = 1` is too weak a convergence proof.** A single no-new sample declares the set complete, but the code's own comment admits "one sample can't prove itself complete." With the `known_anchors` slug-reuse feedback (`review.py:4441`) nudging later samples to re-confirm what's already found, a sample can come back dry by redundancy while the tail is still unsampled.

**Why it matters beyond cost.** Because the audit stops before going dry, every non-trivial plan keeps yielding new findings on each fresh look. That confounds two situations the operator must distinguish: the plan is genuinely mis-shaped (real non-convergence → re-decompose) vs. the audit simply never exhausted the finding set (a sampling artifact). The recurrence signal that BACKLOG #57 (the non-convergence detector) and the RUNBOOK "won't converge → re-decompose" workflow lean on is therefore polluted by undersampling. Making one audit pass exhaustive is a prerequisite for trusting #57's signal — the same-concept-recurs vs. different-concept-each-pass distinction only holds if a single pass saw the whole set.

## Architecture

**Adaptive, exhaustion-aware stop (the v1 core).** In `audit_plan_until_stable`, replace "stop at `max_samples` or one dry sample" with:

- **Keep sampling while productive.** Continue as long as the last sample's marginal-new count is `>= new_threshold` (default 1 — any new finding means the set isn't exhausted).
- **Stop on genuine dryness.** Break only after `dry_rounds` (default raised to 2) consecutive zero-new samples — two dry in a row is a real convergence signal; one is noise.
- **Hard safety cap.** Bound total samples by a `max_samples` ceiling raised to a safe upper bound (e.g. 6–8) so a pathological plan can't sample forever; when the cap is hit while marginal-new is still positive, log that the audit stopped at the cap, not on dryness (no silent truncation — the operator must know coverage was budget-limited).
- **Bounded cost growth on converging plans.** Under the default `dry_rounds=2`, a converging plan pays one extra dry-confirmation call versus the old default — productive samples, then two dry rounds to prove convergence — so cost scales with discovery depth plus that one confirmation. "No regression" holds only for explicit `dry_rounds=1` callers, who keep their two-call shallow cost.

**Keep the existing seams.** The `invoker=` seam stays — sampling must remain stubbable so tests script a marginal sequence without spawning Claude (per `TESTING.md`). Union-by-stable-slug and the `known_anchors` feedback are unchanged; only the stop condition changes. `--audit-samples N` keeps working as an explicit override (pins the cap); add a `--audit-dry-rounds N` surface (threaded through `parser.py` / `completeness_cmd.py`, with the CLI reference regenerated) if a CLI lever is warranted, else keep the raised default internal.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — Authoritative reference for add_argument (type=int, default, help) — consult when threading the optional --audit-dry-rounds flag through parser.py.
- [How to monkeypatch/mock modules and environments (pytest docs)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Official guide to setattr-style patching used to override the invoker= seam so unit tests script marginal-new sequences without spawning Claude.
- [How to use fixtures (pytest docs)](https://docs.pytest.org/en/stable/how-to/fixtures.html) — Reference for authoring and scoping the hermetic tmp_path/invoker fixtures the new stop-condition tests rely on.
- [Claude Code CLI reference (Anthropic docs)](https://docs.anthropic.com/en/docs/claude-code/cli-usage) — Official flags/commands for the claude binary the audit shells out to — needed to keep the real-CLI invoker argv builders correct.
- [subprocess — Subprocess management (Python docs)](https://docs.python.org/3/library/subprocess.html) — Primary reference for the shell-out backend behind the invoker seam (argv, capture, return codes) when validating per-sample Claude calls.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing the conceptual-audit *prompt* content or what counts as a finding.
- The union/dedup mechanism (stable-slug keying, `known_anchors`) — reused as-is.
- Auto-applying anything — this changes only how *thoroughly* the audit samples.

## Risks

- **Cost blow-up on a genuinely deep plan.** Severity: medium (minimize-Claude posture). Mitigation: the hard safety cap plus the continue-while-productive threshold mean extra calls happen only when each one is still returning findings; a dry plan pays nothing extra. Surface the per-run sample count so cost stays visible.
- **More samples → more slug drift / semantic dupes.** Severity: low. The `known_anchors` feedback already collapses re-found concepts onto established slugs; more samples lean on it harder but don't change its mechanism.
- **Test seam not neutralized.** Severity: low. Mitigation: tests inject a scripted invoker returning a fixed marginal sequence; the conftest gate catches a real `claude` spawn.

## Testing

Drive `audit_plan_until_stable` entirely through the `invoker=` seam — no real `claude` spawn (the conftest gate raises if one occurs). Unit tests script marginal-new sequences and assert the stop point: e.g. `[3,2,1,0,0]` stops after the 2nd consecutive dry sample; `[1,1,1,1,1,1,…]` stops at the raised safety cap and emits the "stopped at cap, not dry" truncation log. Cover the no-regression case: a sequence that goes dry in two samples costs exactly two invoker calls. Existing `audit_plan_until_stable` and completeness tests must stay green. If the optional `--audit-dry-rounds` CLI surface lands, add coverage that the flag threads through `parser.py` / `completeness_cmd.py` and that the CLI reference regen stays drift-free.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- `dry_rounds` default is ≥ 2: a single no-new sample no longer stops sampling; two consecutive zero-new samples do.
- Sampling continues while the last sample's marginal-new count is `>= new_threshold`, up to a raised hard cap; a plan still discovering at the old 3-sample point keeps going.
- When the hard cap is reached while marginal-new is still positive, the run logs that coverage was budget-limited (stopped at cap, not dry) — no silent truncation.
- Under the default `dry_rounds=2` a converging plan pays one extra dry-confirmation call (productive samples, then two dry rounds); "no regression" is scoped to explicit `dry_rounds=1` callers, who still cost exactly two Claude calls when dry in two samples.
- `audit_plan_until_stable` stays driven through the `invoker=` seam; unit tests script marginal sequences and assert the stop point without spawning Claude.
- Existing `audit_plan_until_stable` / completeness tests stay green.

## Deferred

- **Per-step audit fan-out** — audit each step's detail independently and union, so step-local issues aren't drowned out when one call reasons over all 9 steps at once. Bigger change to the audit's shape; revisit after v1 proves the adaptive stop helps.
- **Diversified sample lenses** — vary each sample's framing (correctness / completeness / edge-case) to decorrelate samples and raise coverage per call, instead of N identical prompts.
- **In-loop post-apply conceptual re-sample** — today `--iterate` re-runs only deterministic checks after an apply ("no new claude audit"), so convergence is declared without re-checking the conceptual layer against the mutated plan. A single fresh sample after applying would catch issues the edit introduced.
- **Feeding the per-run sample count / "stopped at cap" signal into BACKLOG #57** so the non-convergence detector can distinguish budget-limited coverage from real recurrence.
