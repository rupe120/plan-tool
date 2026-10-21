# Audit next-step correctness branch comparison

Owner-approved retirement is complete on 2026-10-21:
`fix/audit-next-steps-open-correctness` is deleted from Bitbucket and remote
absence is verified. The expected-tip lease protects the reviewed tip; the
full pre-push suite passes. Do not replay its six commits. Current main supplies its intended behavior through the
shared `BlockingVerdict` contract and has broader tests for deterministic blockers,
Jira-grade output and authoring-tail freshness. No runtime change is needed.

## Compared snapshots

- Branch tip: `abf9b1ba6ec9cf9f857fcc1595cb00f3efd8d04b`.
- Main baseline: `25fe3b1ff87e79e9783ef3b2c36abc14c06d5b5b`.
- Later main fixes include `9e2633d27`, `c1680dcde` and `da40b889b`.
- The branch changes seven paths across six commits. Its full aggregate patch
  does not match one landing commit; retirement rests on behavior and tests,
  rather than a claim of byte-identical patches.

## Behavior comparison

| Branch intent | Current behavior and existing evidence |
| --- | --- |
| Open conceptual correctness ends with a re-audit, never `detail` or `run` | `_verdict_offers_stage` permits advancement only for a completed empty blocking set. `test_integration_bare_plan_blocking_correctness_gap_does_not_offer_detail` pins the original failing scenario. |
| Advisory findings remain visible without holding back a stage | The four readers consume `next_step_gaps` from the gate's verdict. `test_advisory_gaps_are_listed_but_hold_back_no_stage` and `test_four_readers_agree_across_stage_grade_finding_kind_and_verdict` cover the class. |
| Console and prose count the same actionable gaps | `BlockingVerdict` carries the gate's IDs without independently recomputing severity. `test_verdict_wraps_gate_ids_without_refiltering` and `test_console_summary_counts_only_blocking_correctness_as_fix_first` cover the contract. |
| Re-audit appears once and retains the correct grade | `_reaudit_command` supplies the shared row. `test_console_list_keeps_exactly_one_reaudit_row_in_the_stronger_form` and `test_every_reaudit_carries_the_audit_grade_and_jira_never_iterates` pin it. |
| Jira's withheld sidecar cannot hide an actual blocker | `test_jira_grade_blocking_gap_withholds_stage_though_findings_are_withheld` confirms the verdict still prevents export advancement. |
| Bare-plan handling respects the current blocking set | `test_blocking_completeness_gap_on_bare_plan_is_counted_though_its_action_is_demoted` preserves a material blocker. Replaying the older branch's unconditional withholding/filtering would bypass this newer contract. |
| Deterministic blockers and authoring parents must also withhold `run` | The branch files this as follow-up work; main carries deterministic findings in the same verdict and checks tail freshness before emitting a stage. Existing completeness and authoring tests cover these routes. |

The branch's removed BUG entry describes the original conceptual-gap symptom;
its added BUG entry describes deterministic blockers and parents appending `run`.
Both responsibilities have current code and tests above. The branch-specific
`blocking_conceptual_gaps` helper and `_actionable_conceptual_gaps` wiring are
superseded by the explicit verdict; restoring them would create a second reader
policy. The audit guide describes the current verdict owner instead.

## Verification on 2026-10-21

- `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py` and
  `tests/test_review.py`: 2,319 passed, one existing skip in 50.94 seconds.
- `tests/cli/test_authoring_cmds.py -k 'verdict or blocking or reaudit'`:
  11 passed, 215 deselected.
- An in-memory mutation forces `_verdict_offers_stage` to return true. Both the
  original bare-plan blocker test and Jira-grade blocker test fail, demonstrating
  that the existing assertions detect incorrect advancement. No tracked source
  file is modified; scratch log:
  `.tmp/public-release-correctness-stage-gate-mutation.log`.

This is a focused retirement comparison, not a new implementation or a fresh
whole-project audit. Preserve its history in the private backup. Demo branches remain retained; the experiment branch
keeps its separate content-selection decision.
