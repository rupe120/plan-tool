# Project model selection implementation

The implementation branch is `implement/project-model-selection`, based on
`d858703b1` (merged plan PR #193). All four steps are done. Project backend
defaults and backend-scoped command models ship through the existing reader,
selector, and CLI; documentation and bundled routers share that contract.
Backlog #254 is reconciled; copied-skill freshness remains #525.

## Execution and verification

- `plan-tool --backend codex --model gpt-6.1-sol run project-model-selection --all --commit -y`
  completes all four steps, with full-suite gates green after each step.
- `plan-tool --backend codex --model gpt-6.1-sol reconcile-code project-model-selection --all --no-walk --no-reuse -y`
  completes one full sweep of steps 1–3; non-code step 4 is excluded.
  Reports `20261113-033850`, `20261113-034025`, and `20261113-034201`
  remain in the plan's reports directory. Steps 2 and 3 are clean. Step 1
  identifies missing explicit `path=` compatibility coverage.
- `1b6ac78e0` closes that coverage finding for all three reader APIs.
  Identifier search (`path=`, reader symbols) and vocabulary search
  (`override`, configuration source) identify the shared reader and its
  wrappers; no existing test pins explicit-path precedence. The new test
  asserts that an explicit file wins over a conflicting conventional file.
  Disabling explicit-path selection makes all three parametrized cases fail.
- Final `uv run pytest tests/ -q -n auto`: **14824 passed, 67 skipped**.

## Independent code reviews

Both reviews inspect `d858703b148f78b3c27ddb1655ae9209f68091f5...1b6ac78e0b24cd3c6504dd8c2ca7a34ff99e7a44`.
Two fresh, read-only Codex processes independently compare the diff with the
plan, four details, and existing tests. Both return explicit clean verdicts
with no confirmed actionable correctness or completeness defects. They trace
configuration compatibility, command aliases, backend/model precedence,
repository resolution, read-only behavior, provisional backends, argv paths,
and fallback isolation/restoration. Read-only executable checks pass; the
full-suite result above comes from the writable execution session.

Local reports are `.tmp/project-model-selection.review-1.md` and
`.tmp/project-model-selection.review-2.md`; their process logs carry the
`project-model-selection.codex-review-` prefix. Claude `/code-review` cannot
start because its saved authentication expires; Codex supplies both reviews.

The branch remains local. Publication and pull-request review are the next
team checkpoint; no push, pull request, or merge is part of this execution.
