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

Full-suite and actual Claude Code high-effort review results follow when complete.

## Scope limits

Do not remove compatibility flags, add execution loops, refactor dormant machinery,
change authoring defaults, or absorb annotate input policy (#516) / configurable
seed locations (#184). The completed bug entry is removed; earlier handoffs link
this record so their historical deferral cannot read as pending work.
