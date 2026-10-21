> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-next-step-verdict-finish.md`.
> Preserved here for history; do not edit.

# Plan seed: finish the completeness next-step verdict

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/completeness-next-step-verdict-finish.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BACKLOG #480 (unpromoted). This seed carries that entry's scope
contract. It follows #479, which shipped the one blocking verdict
(`completeness_report.BlockingVerdict`, `next_step_gaps`, `next_stage_command`).

## Outcome

Every untrusted completeness verdict names the gaps the audit established and
prescribes the action that actually changes the result: a cut-short stop is
re-audited, an unqualified or stale result gets the answer for its real reason,
and a budget-limited audit keeps its blocking ids. Every reader and parent
derives its close list and next command from that one verdict.

## In scope

- The untrusted-cause classification
  (`cli/completeness_cmd.py:_verdict_untrusted_cause`, fed by
  `classify_qualified_audit_result`): a cause per real reason — transient stop,
  persistent coverage, stale revision — each with its own prescribed action.
- `cli/completeness_phases.py:_conceptual_bar_from_audit_recs`: an incomplete
  audit keeps the blocking ids it established, while the finalize gate's bool
  stays what it is today.
- The seven residual reader seams from the entry: grouped report routing a
  blocking correctness gap on a detailed plan to the auto-apply bullet; prose
  that can name the re-audit twice; the audit how-to citing the deleted
  `_actionable_conceptual_gaps`; `_authoring_guidance` re-scanning the bundle
  for the stage; console `blocking N` counting synthetic arms and saying
  "verdict unavailable" for `incomplete`; the dead deterministic splice in the
  fresh-audit early return; finalize passing both the raw deterministic arms and
  the collected tuple.

## Out of scope / Non-goals

- Changing what blocks (`is_blocking_finding`, `is_blocking_impact`), or the
  finalize gate's external contract: `--json` `has_blocking_findings`,
  `--fail-on-findings`, exit codes.
- New advisories, new gates, or new convergence signals.
- Re-deciding #479's settled states (`set` / `incomplete` / `absent`) or its
  trust-follows-the-gate rule; this effort makes the cause classification
  reachable and the ids complete, nothing more.
- Splitting the blocking predicate to give incomplete audits a second one.

## Allowed behavior changes

Only the next-step text, the console list, and the untrusted-cause label for
the three cases and seven seams above.

## Allowed reorganization

None.

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

## Risks

- Keeping ids for an incomplete audit could change the gate's bool if the ids
  feed `has_blocking_findings`. Stop and surface it rather than splitting the
  predicate.
- #479's four review passes each found a new class at the reader/verdict seam;
  a reader the plan misses reintroduces a "no gaps remain" message. Enumerate
  readers by identifier and by vocabulary before editing any.

## Deferred

None. Each item the entry names is in scope above.

## References

- `docs/how-to/pipeline/audit.md` — the qualified-result contract and the
  renderer-agreement paragraph; carries the stale `_actionable_conceptual_gaps`
  citation.
- `handoffs/2026-10-10-completeness-next-steps-blocking-set-code-review.md` —
  #479's review ledger, settled decisions, and the pass-4 findings this seed
  closes.
- `docs/implementation-plans/2-completeness-next-steps-blocking-set.md` — the
  shipped plan whose verdict this finishes.

## Backlog reconciliation

When this plan ships, remove BACKLOG #480 and its roll-up line under
`gate-signal`. Authoring the plan alone marks #480 plan-authored; it does not
remove it.
