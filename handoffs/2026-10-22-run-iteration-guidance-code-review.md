# Run iteration guidance accuracy

Base: `e4ecd6e8b`, branch `fix/run-iteration-guidance`. Scope: the fulfilled
BUG_BACKLOG entry “Run iteration help and protected policy promise a reconcile
loop the CLI rejects”. This direct correction changes diagnostic/help prose,
policy and documentation only; parsing, execution, warning dispatch and exit
codes remain unchanged. CLAUDE.md changes require architect-tier PR review.

## Property and sites

No instruction promises a run or reconcile iteration loop. Ordinary `run`
retains its compatibility flags, and its existing single-step warning names
their lack of effect without recommending a rejected route. Reconcile rejection
and authoring iteration behavior remain pinned by existing tests.

Identifier search covers --iterate, --mode reconcile, detail --reconcile,
“loops reconcile” and “only applies to”. Vocabulary search covers no effect,
re-audit loop, non-reconcile run, protected mandate and drift-detection entry
points. Sites: CLAUDE iteration mandate; run_cmd warning/comment and iterate
help; package catalog; drift_detection module docstring; README and command
synopses; generated run reference and help golden; existing warning output test.
Retained internal reconcile-loop machinery/tests remain unchanged. Scratch:
`.tmp/run-iteration-guidance.sites.md`.

The existing warning test pins the obsolete text, so it is intentionally updated
and named for the new invariant. It still verifies successful execution, stderr
routing and plain output; its sibling checks color prefixes. Existing parser and
handler rejection tests remain unchanged. No prose-mirroring test is added.

## Validation

Affected warning/style, run/detail reconcile dispatch, package-help and generated
reference checks: 84 passed in 1.13s. Mutation verified: recommending
`detail --reconcile --iterate` again fails the updated warning regression test;
source is restored before full-suite validation. Help is regenerated through
the supported golden update route and verified without its update flag.

Full suite at `401644be8`: 14,717 passed, 67 skipped in 63.08s. Actual
Claude Code review rounds and dispositions follow below.

## Scope limits

Do not remove compatibility flags, add execution loops, refactor dormant machinery,
change authoring defaults, or absorb annotate input policy (#516) / configurable
seed locations (#184). The completed bug entry is removed; earlier handoffs link
this record so their historical deferral cannot read as pending work.


## Claude review 1

Range `e4ecd6e8b..401644be8`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `d112a224-c1dd-4f6b-90cf-f76f8d7d9a67`; CLI exits zero.
Report `.tmp/run-iteration-guidance.review-1.md`. The skill returns candidates
and the supervising review traces each against code/tests; no tests run in that
review. No new defect in the changed statements, but sibling guidance remains.

| Finding | Disposition |
| --- | --- |
| F1 medium: inherited run loop-option descriptions remain misleading | Fixed in run_cmd's local compatibility parent only. Source inspection shows it is local to this module and used only by p_run; authoring parsers have their own definitions. All nine options now describe run compatibility/no-effect semantics. Names, defaults, types and actions are unchanged. |
| F2 low: pipeline diagram labels legacy value validation as a budget | Clarified: compatibility-only loop flags, no loop. Value validation stays. |
| F3 low: helper docstring promises removed run --mode reconcile iteration | Corrected prose only, clarifying disabled CLI budgets. This is the same obsolete guidance class; internal implementation/tests remain outside the repair. |
| F4 low: all-step dispatch bypasses the single-step warning | Clarified policy to “may warn or reject”; preserve existing warning dispatch. No sweep parity behavior change. |
| Optional warning/style and pending evidence text | Retain warning wording; replace pending placeholder with actual evidence. Preserve the index's existing loose-list format. |

Second site enumeration covers every option in the run-only compatibility
parent, the pipeline validation box, the retained helper's obsolete route
comment and sweep-vs-single-step warning wording. It does not alter the shared
contracts of authoring commands. A green message test alone was not treated as
proof the option descriptions were complete.
