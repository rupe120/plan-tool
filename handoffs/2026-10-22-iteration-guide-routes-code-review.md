# Iteration route documentation repair

Base: `330441789` (merged PR #135). Scope: iteration examples/defaults and
reconciliation-loop claims in README, iteration/operations/common-workflow
guides, RUNBOOK, shared directives and the three skill routers. Runtime behavior
is unchanged. The fulfilled guide bug is removed; protected policy/generated
help mismatch remains in BUG_BACKLOG.md for architect-tier work.

## Property and sites

Only implemented loops are described as iterative. `create` defaults on;
`detail` and `completeness-audit` default off. Detail stays one-shot unless
explicitly requested. Detail reconciliation rejects either iteration flag;
legacy run reconciliation rejects `--iterate`; standalone reconcile verbs do
not accept it. Plan-side reconciliation remains pre-execution, with
plan-canonical code reconciliation after execution.

Identifier search covers both reconcile aliases and iteration flags; vocabulary
search covers defaults, headless examples, loop counts, per-invocation budgets
and checkpoint claims. Sites: README headless/defaults/table/use cases/budgets/
checkpoint/gate summaries/reconcile example; ITERATION equivalents; RUNBOOK
loop introduction/reconcile recipes; OPERATIONS headless examples;
common-workflows create/run examples; shared directive iteration paragraph and
all three routers. Protected policy and generated help are separately tracked.

## Validation

Existing tests: `TestIterateFlagsDetail`, `TestDetailReconcileDispatch`,
`TestRunReconcileDispatch` in tests/test_cli.py plus tests/cli/test_skill_cmd.py:
58 passed in 0.66s. These pin authoring defaults, both reconciliation rejections,
standalone dispatch and installation behavior without a live backend. No tests
that mirror prose are added. Full suite and review results follow when completed.

## Review status

Pending actual Claude Code `/code-review` at high effort on the committed diff.
