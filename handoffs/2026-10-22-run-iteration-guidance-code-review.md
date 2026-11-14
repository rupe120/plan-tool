# Run iteration guidance accuracy

Base: `e4ecd6e8b`, branch `fix/run-iteration-guidance`. Scope: the fulfilled
BUG_BACKLOG entry “Run iteration help and protected policy promise a reconcile
loop the CLI rejects”. Direct correction of diagnostic/help prose, policy and
documentation only; parsing, execution, warning dispatch and exit codes are
unchanged. CLAUDE.md changes require architect-tier PR review.

## Settled decisions

- No instruction promises a run or reconcile iteration loop. Ordinary `run` keeps its compatibility flags; its existing single-step warning names their lack of effect without recommending a rejected route. Reconcile rejection and authoring iteration behavior stay pinned by existing tests.
- Sites: CLAUDE iteration mandate; run_cmd warning/comment and iterate help; package catalog; drift_detection module docstring; README and command synopses; generated run reference and help golden; existing warning output test. Retained internal reconcile-loop machinery/tests are unchanged. Scratch: `.tmp/run-iteration-guidance.sites.md`.
- The existing warning test pinned the obsolete text and is updated and renamed for the new invariant (still checks successful execution, stderr routing, plain output). No prose-mirroring test is added.
- Validation: warning/style, reconcile dispatch, package-help and generated-reference checks 84 passed; mutation (recommending `detail --reconcile --iterate` again) fails the updated warning test; help regenerated through the supported golden route.
- Scope limits: do not remove compatibility flags, add execution loops, refactor dormant machinery, change authoring defaults, or absorb annotate input policy (#516) / configurable seed locations (#184). Earlier handoffs link this record so their historical deferral cannot read as pending work.

## Findings

Review 1, range `e4ecd6e8b..401644be8` (session `d112a224-c1dd-4f6b-90cf-f76f8d7d9a67`; report `.tmp/run-iteration-guidance.review-1.md`). Full suite at `401644be8`: 14,717 passed, 67 skipped.

- F1 medium, fixed (range `..1f99f9614`): inherited run loop-option descriptions misleading; run_cmd's local compatibility parent (used only by p_run) now describes all nine options as compatibility/no-effect; names, defaults, types, actions unchanged.
- F2 low, fixed (`..1f99f9614`): pipeline diagram labeled legacy value validation as a budget; now compatibility-only flags, no loop; validation stays.
- F3 low, fixed (`..1f99f9614`): helper docstring promised removed `run --mode reconcile` iteration; prose corrected only.
- F4 low, fixed (`..1f99f9614`): all-step dispatch bypasses the single-step warning; policy now says “may warn or reject”; no behavior change.
- Optional warning/style text: declined (wording retained); pending evidence placeholder replaced with actual evidence.

Review 2, range `e4ecd6e8b..1f99f9614` (session `7a70785e-373d-4532-b4dc-34c1b9eeae82`; report `.tmp/run-iteration-guidance.review-2.md`). Verified by callers, AST equivalence after removing guidance strings/docstrings, 177 targeted tests. Full suite 14,717 passed, 67 skipped.

- F-A low, fixed (`..488302fd5`): time-budget help now preserves flag/environment value-validation information; run reference regenerated.
- F-B low, fixed (`..488302fd5`): `_build_run_budget` has no production callers; docstring describes its retained compatibility delegation, as do the app re-export comment and the context test module's stale spy claim (comments only; the dated coverage baseline stays as provenance).
- F-C low, fixed (`..488302fd5`): run owns a separate compatibility parent; register docstring's verbatim/shared-parent claim removed.
- F-D declined: wording preference; existing warning is accurate.
- F-E refuted: accept-mode warning code and its existing test.
- F-F refuted: rejection tests and the recorded mutation; no prose-conformance test warranted.

Review 3, range `e4ecd6e8b..488302fd5` (session `c04a454e-d2fb-44cc-972b-4ead3d9b65d7`; report `.tmp/run-iteration-guidance.review-3.md`). Six candidates traced against dispatch/callers/tests; six-module normalized AST comparison repeated.

- D1 low, fixed (closing application, after `488302fd5`): budget value validation runs on ordinary and `--all` paths, not early-return accept/reconcile paths; all four help clauses qualified, reference regenerated, every validation branch preserved.
- D2 low, fixed (closing application): retained-wrapper/removed-alias comment sweep finished in the package header, tests/test_cli.py and both reconcile helper docstrings; package exports do not redirect handler globals, so comments describe command-module lookup ownership. No dormant code removed.
- Warning wording, silent all-step dispatch, synopsis selection, diagram precision: declined (preferences or earlier dispositions).
- Disabled-budget code removal: declined, out of scope. Backlog #517 stays tracking-only.

## Closure

Closure label: **low-yield convergence, not a clean review.** Reviews 2 and 3 contain only low-severity guidance findings and no material correctness/completeness gap. Review 3 reviews `488302fd5`, not the later closing prose/evidence commit. Under the stop-auditing-your-edits rule no further full review is launched to resample this advisory wording tail. Architect-tier PR review remains required for the protected policy change.

Closing validation: full suite 14,717 passed, 67 skipped; generated reference check included; six guidance-normalized production ASTs match the base; `git diff --check` passes.
