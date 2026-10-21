> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-next-step-verdict-finish.md`.
> Preserved here for history; do not edit.

## Overview

This plan finishes the single blocking completeness verdict that #479 shipped (`completeness_report.BlockingVerdict`, `next_step_gaps`, `next_stage_command`). When a verdict cannot be trusted, it will name the gaps the audit found and tell the reader the action that actually changes the result. A cut-short stop gets re-audited, an unqualified or stale result gets an answer that matches its real cause, and a budget-limited audit keeps its blocking ids. Every reader and parent takes its close list and next command from that one verdict. What blocks does not change, and neither does the finalize gate's external contract (`--json` `has_blocking_findings`, `--fail-on-findings`, exit codes).

## Problem statement

Some of #479's verdict states still give the wrong guidance. The untrusted-cause classification (`cli/completeness_cmd.py:_verdict_untrusted_cause`, fed by `classify_qualified_audit_result`) does not tell transient stops, persistent coverage limits, and stale revisions apart. As a result, a stop that a plain re-audit would continue can be told to do hand triage, and a stale-revision `no-qualified-current-evidence` result is told that "re-auditing unchanged text reproduces this". `cli/completeness_phases.py:_conceptual_bar_from_audit_recs` drops the blocking ids an incomplete (budget-limited) audit already established. Seven reader seams also remain: the grouped report sends a blocking correctness gap on a detailed plan to the auto-apply bullet; prose can name the re-audit twice; the audit how-to cites the deleted `_actionable_conceptual_gaps`; `_authoring_guidance` re-scans the bundle to find the stage; console `blocking N` counts synthetic arms and says "verdict unavailable" for `incomplete`; a dead deterministic splice sits in the fresh-audit early return; and finalize passes both the raw deterministic arms and the collected tuple. Any one of these readers can bring back a "no gaps remain" message.

## Architecture

The untrusted-cause classifier gets one cause per real reason, and each cause has its own prescribed action. **Transient** covers `max_iterations`, `deadline_exceeded`, and `no_progress`, and its action is to re-audit. **Persistent coverage** keeps `terminal_hand_apply`. **Stale revision** gets the fresh-audit answer, and its saved gaps are never offered as text to close. The cause comes from what `classify_qualified_audit_result` actually produces, not from hand-paired cases.

`_conceptual_bar_from_audit_recs` keeps the established blocking ids for an incomplete audit. The finalize gate's bool keeps its current value. The ids feed the verdict's close list without feeding `has_blocking_findings`, so the blocking predicate is not split.

Every reader (grouped report, prose, console, `_authoring_guidance`, finalize, docs) derives its list and next command from the one `BlockingVerdict` and does not recompute stage or gaps itself. To close the seven seams: fix the auto-apply routing, de-duplicate the re-audit prose, fix the doc citation, take the stage from the verdict, make the console count only real ids and label `incomplete` properly, remove the dead splice, and give finalize a single input. Readers are enumerated by identifier and by vocabulary before any edit. No reorganization is allowed.

## Out of scope

- Changing what blocks (`is_blocking_finding`, `is_blocking_impact`), or the
  finalize gate's external contract: `--json` `has_blocking_findings`,
  `--fail-on-findings`, exit codes.
- New advisories, new gates, or new convergence signals.
- Re-deciding #479's settled states (`set` / `incomplete` / `absent`) or its
  trust-follows-the-gate rule; this effort makes the cause classification
  reachable and the ids complete, nothing more.
- Splitting the blocking predicate to give incomplete audits a second one.

## Risks

- Keeping ids for an incomplete audit could change the gate's bool if the ids
  feed `has_blocking_findings`. Stop and surface it rather than splitting the
  predicate.
- #479's four review passes each found a new class at the reader/verdict seam;
  a reader the plan misses reintroduces a "no gaps remain" message. Enumerate
  readers by identifier and by vocabulary before editing any.

## Testing

- The existing agreement tables gain the stop × headline pairings the
  classifier actually produces (not hand-paired ones): `max_iterations`,
  `deadline_exceeded`, and `no_progress` reach `transient`; `terminal_hand_apply`
  stays `persistent`.
- A budget-limited audit with HIGH correctness findings names them as blocking
  and offers no stage; the finalize gate's bool is identical before and after.
- A stale-revision `no-qualified-current-evidence` result gets the fresh-audit
  answer, not "re-auditing unchanged text reproduces this".
- Each pinned by mutation: revert the change and the test goes red.

## Acceptance criteria

- No reader prescribes hand triage for a stop a plain re-audit would continue.
- An incomplete audit's blocking ids are named by every reader; the gate's bool,
  `--json`, and exit codes are unchanged.
- A stale revision never has its saved gaps named as text to close.
- The seven seams are closed, each at every reader that shares it.
- BACKLOG #480 is removed with its `gate-signal` roll-up line.

## Deferred

None. Each item the entry names is in scope above.
