> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Completeness Next Step Verdict Finish
intent: 'Every untrusted completeness verdict names the gaps the audit established
  and prescribes the action that actually changes the result: a cut-short stop is
  re-audited, an unqualified or stale result gets the answer for its real reason,
  and a budget-limited audit keeps its blocking ids. Every reader and parent derives
  its close list and next command from that one verdict.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because no interactive operator
  decision is available.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/completeness-next-step-verdict-finish.md
steps:
- id: 1
  title: Split the untrusted-verdict cause into transient, persistent, and stale-revision,
    each with its own next action
  intent: A stop that a plain re-audit would continue gets told to re-audit, and a
    stale revision gets the fresh-audit answer instead of hand triage or the claim
    that 'unchanged text reproduces this'.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/completeness-next-step-verdict-finish/01-split-untrusted-verdict-cause-transient.md
  status: done
- id: 2
  title: Keep an incomplete (budget-limited) audit's blocking ids in the verdict's
    close list without changing the finalize gate's bool
  intent: A budget-limited audit that already found HIGH correctness gaps names them
    as blocking and offers no stage on a current revision (a stale revision takes
    the fresh-audit answer instead). `has_blocking_findings`, `--fail-on-findings`,
    and the exit codes stay exactly as they are. Every consumer of the returned ids
    (the stop-reason remap and both call sites) is enumerated and keeps treating an
    incomplete audit as non-blocking for the gate.
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the per-cause classification that decides whether an incomplete audit's ids
      are offered as gaps to close
  detail: docs/implementation-plans/plan-details/completeness-next-step-verdict-finish/02-keep-incomplete-budget-limited-audit.md
  status: done
- id: 3
  title: Give finalize the BlockingVerdict as its single input and remove the dead
    deterministic splice from the fresh-audit early return
  intent: Finalize reads its list from the one verdict, so it cannot drift from the
    other readers.
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_completeness_cmd.py
  complexity: low
  change_type: refactor
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/completeness-next-step-verdict-finish/03-give-finalize-blockingverdict-its.md
  status: done
- id: 4
  title: Make the grouped report, prose, console, and `_authoring_guidance` take their
    gap list, count, and next command from the verdict
  intent: Closes the remaining reader seams so that no reader can bring back a 'no
    gaps remain' message or recompute the stage on its own. Every reader consumes
    step 2's retained ids through the verdict on a current revision, and every reader
    that shares a seam is found by identifier and by vocabulary, with the list recorded
    in the handoff, before any edit.
  files:
  - plan_tool/completeness_report.py
  - plan_tool/cli/authoring.py
  - plan_tool/cli/completeness_cmd.py
  - tests/test_completeness_report.py
  - tests/cli/test_authoring_cmds.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: the cause-specific next actions the readers render
    2: the incomplete-audit ids the readers must name
    3: the single verdict input the readers consume
  detail: docs/implementation-plans/plan-details/completeness-next-step-verdict-finish/04-make-grouped-report-prose-console.md
  status: done
- id: 5
  title: 'Update the audit how-to''s verdict guidance, replace the `_actionable_conceptual_gaps`
    citation, and remove BACKLOG #480 and every roll-up mention of it'
  intent: The operator contract describes the shipped causes and actions, and the
    backlog stops listing work that has shipped.
  files:
  - docs/how-to/pipeline/audit.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/completeness-next-step-verdict-finish/05-update-audit-how-verdict-guidance.md
  status: done
---
# Completeness Next Step Verdict Finish

## Overview

This plan finishes the single blocking completeness verdict that #479 shipped (`completeness_report.BlockingVerdict`, `next_step_gaps`, `next_stage_command`). When a verdict cannot be trusted, it will name the gaps the audit found and tell the reader the action that actually changes the result. A cut-short stop gets re-audited, an unqualified or stale result gets an answer that matches its real cause, and a budget-limited audit keeps its blocking ids. Every reader and parent takes its close list and next command from that one verdict. What blocks does not change, and neither does the finalize gate's external contract (`--json` `has_blocking_findings`, `--fail-on-findings`, exit codes).

## Problem statement

Some of #479's verdict states still give the wrong guidance. The untrusted-cause classification (`cli/completeness_cmd.py:_verdict_untrusted_cause`, fed by `classify_qualified_audit_result`) does not tell transient stops, persistent causes (coverage limits, hand-apply stops), and stale revisions apart. As a result, a stop that a plain re-audit would continue can be told to do hand triage, and a stale-revision `no-qualified-current-evidence` result is told that "re-auditing unchanged text reproduces this". `cli/completeness_phases.py:_conceptual_bar_from_audit_recs` drops the blocking ids an incomplete (budget-limited) audit already established. Seven reader seams also remain: the grouped report sends a blocking correctness gap on a detailed plan to the auto-apply bullet; prose can name the re-audit twice; the audit how-to cites the deleted `_actionable_conceptual_gaps`; `_authoring_guidance` re-scans the bundle to find the stage; console `blocking N` counts synthetic arms and says "verdict unavailable" for `incomplete`; a dead deterministic splice sits in the fresh-audit early return; and finalize passes both the raw deterministic arms and the collected tuple. Any one of these readers can bring back a "no gaps remain" message.

## Architecture

The untrusted-cause classifier has exactly three cause values — `transient`, `persistent`, and `stale-revision` — and each has its own prescribed action; "persistent coverage" and "persistent hand-apply" below describe reasons that all map to the one `persistent` value. **Transient** covers `max_iterations`, `deadline_exceeded`, and `no_progress`, and its action is to re-audit. **Persistent** keeps `terminal_hand_apply`. **Stale revision** gets the fresh-audit answer, and its saved gaps are never offered as text to close. The cause comes from what `classify_qualified_audit_result` actually produces, not from hand-paired cases.

**Precedence when one result carries several causes** (first match wins): (1) **`stale-revision`** — the `no-qualified-current-evidence` headline with `QualifiedAuditResult.revision_status` other than `current` (`stale`, `unknown-legacy`, or `not-sampled`); the saved gaps describe text that no longer matches, or no sample exists, so they are not offered as text to close and the answer is a fresh audit. (2) **Incomplete / budget-limited**, carried as `persistent` (a coverage reason) with retained ids (no fourth cause value) — the audit's retained blocking ids are named for hand triage and no stage is offered, whatever the stop reason; a `max_iterations` stop on a budget-limited audit is still incomplete. With no retained ids, nothing is named to close, any findings stay listed as advisory, no stage is offered, and the command is the plain re-audit (coverage, not text, is what limits the result); steps 1 and 4 share that one wording. (3) **Non-empty blocking set on a qualified, current-revision result** — trusted (`""`): its gaps are named whatever the stop, per #479's trust-follows-the-gate rule, which this plan does not re-decide. (4) **Transient stop** — `max_iterations`, `deadline_exceeded`, or `no_progress` on an otherwise qualified result with an empty blocking set; re-audit. (5) **`persistent`, hand-apply reason** — `terminal_hand_apply` / `manual_fix_blocking_findings`. (6) **Catch-all, `persistent`** — any other untrusted result (unqualified headline, `awaiting-human-action` deferrals) is `persistent`, never trusted (`""`), so it cannot bring back a "no gaps remain" message. The classifier takes `revision_status` as an explicit input so the stale trigger has one source. The gate, `--json` `has_blocking_findings`, `--fail-on-findings`, and the exit codes read only the gate pair, never a `BlockingVerdict`'s ids or `blocking_count`.

`_conceptual_bar_from_audit_recs`'s gate pair (`(), True` for an incomplete audit) is unchanged, so the finalize gate's bool keeps its current value. The verdict receives the established stage-bar blocking ids for an incomplete audit separately (`compute_conceptual_bar_blocking_ids`), and they feed its close list without feeding `has_blocking_findings`, so the blocking predicate is not split.

Every reader (grouped report, prose, console, `_authoring_guidance`, finalize, docs) derives its list and next command from the one `BlockingVerdict` and does not recompute stage or gaps itself. To close the seven seams: fix the auto-apply routing, de-duplicate the re-audit prose, fix the doc citation, take the stage from the verdict, make the console count only real ids and label `incomplete` properly, remove the dead splice, and give finalize a single input. Readers are enumerated by identifier and by vocabulary before any edit. No reorganization is allowed.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3.13/library/dataclasses.html) — Covers frozen dataclasses, field defaults, and replace(), which matter when extending the immutable BlockingVerdict with retained blocking ids and an untrusted cause.
- [enum — Support for enumerations (Python 3.13 docs)](https://docs.python.org/3.13/library/enum.html) — Covers Enum and StrEnum semantics for modeling separate transient, persistent, and stale-revision cause values, each with its own prescribed action.
- [Structural pattern matching — PEP 636 tutorial](https://peps.python.org/pep-0636/) — The official guide to match/case, useful for mapping the outcomes classify_qualified_audit_result actually produces onto cause classes without pairing cases by hand.
- [argparse — Parser for command-line options (Python 3.13 docs)](https://docs.python.org/3.13/library/argparse.html) — Reference for the existing --json and --fail-on-findings flags, whose external contract has to stay the same.
- [sys.exit and exit status (Python 3.13 docs)](https://docs.python.org/3.13/library/sys.html#sys.exit) — Defines exit-status behavior, for checking that the finalize gate's exit codes don't change.
- [How to parametrize fixtures and test functions (pytest docs)](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Covers pytest.mark.parametrize, for extending the agreement tables with stop × headline pairings and for writing one parametrized test across every verdict reader.
- [How to monkeypatch/mock modules and environments (pytest docs)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers monkeypatch, for stubbing invoker seams and classifier outputs so the reader and finalize tests stay hermetic.

## Steps

See the `steps:` block in the frontmatter.

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
- Combined causes follow the stated precedence, one row per ordered pair:
  stale × incomplete (fresh audit, ids not offered as text to close);
  a cut-short stop with a non-empty blocking set on a qualified result is
  trusted and names its gaps;
  `not-sampled` gets the fresh-audit answer;
  incomplete × `max_iterations` (ids named, hand triage, no stage);
  stale × a cut-short stop (stale wins over transient); `unknown-legacy` alone
  (fresh audit);
  a qualified, empty-set, awaiting-action result with a transient stop is
  `transient` and with a hand-apply stop is `persistent`;
  an incomplete audit with no retained ids names nothing to close, offers no
  stage, and prescribes the plain re-audit;
  a current-revision untrusted result matching no earlier rule (unqualified
  headline or awaiting-action deferrals, no stop reason) is persistent.
- Every consumer of `_conceptual_bar_from_audit_recs`' ids is enumerated, and
  the iterate stop reason and `_remap_iterate_stop_for_conceptual_bar` result are
  asserted identical for an incomplete audit with and without ids.
- An incomplete audit with retained ids leaves `--json`
  `has_blocking_findings`, `--fail-on-findings`, and the exit code identical to
  the same audit without ids, asserted across all three.
- Each pinned by mutation: revert the change and the test goes red.

## Acceptance criteria

- On a qualified, current-revision result with an empty blocking set, no reader
  prescribes hand triage for a stop a plain re-audit would continue. The
  exceptions are named: a budget-limited audit (persistent, ids named, no stage)
  and a non-empty blocking set (trusted, gaps named).
- On a current revision, an incomplete audit's blocking ids are named by every
  reader; on a stale or `unknown-legacy` revision the fresh-audit answer wins
  and the ids are not offered as text to close. The gate's bool, `--json`, and
  exit codes are unchanged either way.
- A stale revision (`revision_status` `stale`, `unknown-legacy`, or `not-sampled`) never has its
  saved gaps named as text to close, whatever else the result carries; the
  precedence in Architecture orders stale before incomplete before transient.
- The reader enumeration (identifier and vocabulary searches, with the sites
  returned and why any stays) is written into `handoffs/2026-10-10-completeness-next-step-verdict-finish-reader-enumeration.md` before step 4 edits
  any reader.
- The seven seams are closed, each at every reader that shares it.
- BACKLOG #480 and every roll-up mention of it (including under `gate-signal`) are removed.

## Deferred

None. Each item the entry names is in scope above.
