# Trust-core backlog arc

## File intent

This file is the execution guide for strengthening plan execution,
post-execution reconciliation, and deterministic trust prerequisites before
the backlog expands product surface.

## Details

It records the ordered authored plans and short decisions, their audit and
commit gates, and the handoff criteria that determine whether convergence
evidence or roadmap capability is the next legitimate route.

## Choose this arc when

The next session needs to make plan execution and post-run reconciliation more
trustworthy before expanding the product surface. This arc follows the bug
drain in `bug-backlog-draining-arc.md`; an unblocked BUG takes priority over
every item here.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool work
uses committed green-step checkpoints; direct changes include their regression
coverage and backlog retirement in one bounded commit.
Do not push automatically; push only when the user explicitly requests it.

## Ordered route

**Delivered, do not re-open:**

- **2026-08-18** — `create-default-test-command`, `reconcile-code-later-
  step-context`. Green-step test evidence is repository-grounded; the
  post-run reconciliation tail preserves completed sibling work.
- **2026-08-19** — `per-call-timeout-budgets`, retroactively
  `status: completed` rather than run: its full four-step scope had already
  landed directly in commit `b173b51b` (2026-08-04), before the plan itself
  was ever executed. If a future session finds an authored, unexecuted plan
  whose scope looks suspiciously already-shipped, check `reconcile-plan`
  before running it — this is what that check is for. #210 (the purity-pass
  keep/cut decision) is unblocked and its remaining step (measure real
  `--purity` fire rate) is separate backlog work, not part of this arc.
- **2026-08-19** — #162 (`44ca13a9`): `Plan.source_seed`, set by
  `create --from-existing`, feeds the completeness-audit prompt's seed
  scope-contract block. A seed is archived immediately after the plan that
  consumes it is published (`create.py`'s standard behavior, not an edge
  case), so resolution falls back through `pathutil.latest_seed_archive` —
  without that fallback the feature fires on almost nothing. Bumping a
  *persisted* schema version (here, `audit_input_revision`) needs a
  backward-compat check against real committed data first, not just a
  version-bump-and-move-on — 169 already-saved reports would have been
  silently discarded otherwise. BACKLOG.md's entry is closed and removed.
- **2026-08-19** — #165 (`db3db553`): a per-step authoring fingerprint on
  the grounding sidecar (`Grounding.step_authoring_fingerprints`,
  `plan_tool/grounding.py` — see `DATA_CONTRACT.md`'s Grounding sidecar
  section for the field contract), stamped whenever `detail` writes a step;
  `status` and `completeness-audit`'s pre-flight both warn (non-blocking)
  via one shared `grounding.stale_detail_warning`. **Load-bearing invariant
  for anyone touching `_stamp_grounding`:** a restamp must only update the
  steps the current run actually wrote, never blanket-recompute every
  currently-detailed step — a blanket recompute silently re-baselines an
  untouched sibling step against the plan's current shape, erasing
  staleness a prior edit had already introduced for it.
  `tests/cli/test_authoring_cmds.py::TestStampGrounding
  ::test_touched_step_ids_preserves_untouched_siblings` pins this;
  mutation-verified. BACKLOG.md's entry is closed and removed.
- **2026-08-19** — #166: the trailing full-window certification path
  (`run_count >= window`) certified `converging` unconditionally, with no
  check that its runs described the same plan shape — the sub-threshold
  fingerprint-stable-streak path was already immune (an identical whole-plan
  `plan_fingerprint` across the streak makes a step-count difference
  impossible by construction). Neither of the two signals this entry's
  "Preconditions" section pointed at actually fit: #165's
  `Grounding.step_authoring_fingerprints` is a single current-state sidecar
  overwritten in place on each `detail` restamp, not a per-audit historical
  record, and it never prunes a since-removed step's key, so its key set
  cannot answer "what were the step ids at run N"; #238's `plan_mass.
  step_count` is explicitly fenced ("no field here feeds a threshold, gate,
  warning, or exit code anywhere in the tool", `DATA_CONTRACT.md`'s
  `PlanMass` section) and this is exactly a warning input. Shipped a
  dedicated, self-computed signal instead: `SavedReview.step_ids` /
  `step_ids_present` (BACKLOG #166), the sorted ids `save_review` parses
  from the plan at save time for every kind — no caller-supplied fingerprint,
  so every producer carries it with no call-site changes.
  `convergence_diagnosis.py`'s new `redecomposition_step_counts` /
  `redecomposition_span` label the full-window verdict when the trailing
  window's runs carry more than one known step count; per the entry's
  stated risk ("a plan that gains one step should not lose its whole
  trajectory"), this labels only — it never excludes a run or changes
  `run_count`/the verdict, leaving materiality to the reader. BACKLOG.md's
  entry is closed and removed.
- **2026-08-19 — #239:** `settled` is author-neutral. The checker pins every
  predecessor decision with that status, whether a stage or an operator set
  it, and carries no author signal. The format and demo now describe that
  persistence fence; no third status or persisted authorship field is added.
- **2026-08-19 — #236:** a `not-load-bearing` constraint is rejected by
  `check_attribute_totality` in the stage-2 gate set, before the components
  discharge gate can see it. The unreachable discharge carve-out is removed;
  the live `traded-away` exception remains. The test now pins that ordering.
- **2026-08-19 — #237:** the components constraint gates retain their
  no-violation return for a partial envelope with no constraints. It is a
  documented direct-caller guard, unreachable in the CLI's stage-3 route, and
  its test fails if it swallows complete envelopes. `_id_list` and
  `_optional_id_list` remain separate: required and optional key presence are
  distinct policies, not a call-site boolean.
- **2026-08-19 — #221:** one cross-module table test pins that both
  granularity sources stay out of `APPLY_ELIGIBLE_SOURCES`, structural and
  apply-eligible sources stay disjoint, and split escalation requires its
  source, `medium` severity, and command-local opt-in. The distinct owners
  remain separate because eligibility, structural routing, and blocking are
  different policies; no single predicate is introduced.

1. This arc is complete. Choose the convergence-evidence or roadmap arc using
   the exit rule below.

## Preconditions and gates

- Start from a committed baseline. Each authored plan gets a bare-plan audit,
  detail, a detail-grounded audit, committed green steps, `reconcile-code
  --all`, and code review.

## Exit and handoff

The arc ends with the scope, staleness, roadmap-gate, and apply-authority
contracts (#162, #165, #166, #239, #236, #237, #221) deterministic. Next choose
the convergence-evidence or roadmap arc according to whether the observed need
is plan-quality feedback or product-roadmap work.

## Out of scope

This arc does not introduce new audit models, Jira-grade execution, a new
roadmap position, or broad operator UX. Those belong to the other arc docs.
