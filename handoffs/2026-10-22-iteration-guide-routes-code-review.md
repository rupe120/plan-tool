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
that mirror prose are added. Full-suite and review results are recorded below.

## Review status

Four actual Claude Code Skill reviews are complete. Reviews 3 and 4 are
consecutive low-yield passes with no new medium-or-higher finding. Their
advisories are dispositioned below; closure is low-yield, not wholly clean.

## Claude review 1

Range `330441789..9816a9482`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `918ad21b-85d2-4e5f-905a-dccfd3471ef3`; CLI exits zero.
Saved report: `.tmp/iteration-guide-routes.review-1.md`.

| Finding | Disposition |
| --- | --- |
| 1 medium: GATES guide still advertises reconcile iteration | Fixed: gate lists and example use implemented authoring routes. |
| 2 medium: directives imply reconcile-run is the valid iterate route | Fixed: ordinary run is named as a no-op; reconcile rejection remains explicit. |
| 3 medium: TRACKING prescribes removed mode/iteration | Fixed: phase 3b and examples use post-execution `reconcile-code`, with judged separate invocations. |
| 4 low: headless explanations still reference obsolete loop | Fixed: explain deterministic authoring fixes, conceptual judgment, valid independent examples and actual completeness CI flag. |
| 5 low: architecture/recovery/pipeline siblings | Fixed: supported route lists and time-budget coverage; internal helper references explicitly distinguish implementation from CLI availability. |
| 6 low: runtime warning absent from follow-up | Filed in existing protected-policy/help bug; runtime behavior stays unchanged here. |
| 7 low: router argument hints include ineffective iteration flags | Fixed: remove run-iteration budget flags from all three hints; authoring loops remain documented in the body. |
| 8 low: voice and unnecessary churn | Fixed human-facing detail-request wording and headless paragraphs; retain equivalent README/guide facts while correcting stale route claims. No broad style rewrite. |
| 9 info: whitespace | Fixed extra separators at changed sites. |

Second sweep: identifier searches include `--mode reconcile`, `_iterate_reconcile_loop`,
both aliases and iteration flags. Vocabulary includes gate surface lists,
re-audit, per-step/per-run budgets, headless apply and time-budget coverage.
Additional sites are GATES, TRACKING, ARCHITECTURE, recovery index/audit and
pipeline audit; all receive route corrections or explicit internal-only labels.

Full suite at `9816a9482`: 14,698 passed, 66 skipped in 54.73s. Parser-only probes
confirm three defaults, four valid forms and four unsupported combinations;
run-side rejection is pinned by its existing handler test. Review is not yet
converged; the next pass reviews the corrected committed snapshot.


## Claude review 2

Range `330441789..99ffa33e6`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `7cf66b91-f7dc-4e1e-af4c-66950cd54049`; CLI exits zero.
Saved report: `.tmp/iteration-guide-routes.review-2.md`.

| Finding | Disposition |
| --- | --- |
| 1 medium: TRACKING retains run/reconcile iteration sentence | Fixed: describe separate invocations and actual completeness default. |
| 2 low: plan-route rationale promises reconcile iteration | Fixed: name authoring audits plus separate reconciliation/review. |
| 3 low: backlog recipes use removed mode | Fixed: three recipes use `reconcile-code`; source-investigation entry explicitly distinguishes dormant helper from available CLI route. |
| 4 low: touched detail example has unsupported no-walk/no-save | Fixed: remove both lines; standalone reconcile-plan flags stay. |
| 5 low: repo-local installed Claude copy remains stale | Refresh from canonical integration sources using the supported copy installer; retain copies as tracked artifacts, not a second authoring source. |
| 6 low: handoff pending text is stale | Fixed: name completed review snapshots in the overview. |
| 7 low: recovery entry-point list implies a live reconcile loop | Fixed: supported authoring entry points are separate from the retained internal helper, whose budget no CLI route enables. |
| 8 info: reconcile-code has no automatic commit | Clarified: workflow example says verify and commit separately. |
| 9 optional/unverified: detail iteration wording | Declined: current text explicitly requires a request for detail iteration and correctly states its off default. No conflicting claim is verified. |

Site enumeration expands to TRACKING's plan-route rationale and quality paragraph,
BACKLOG's three removed-mode recipes and one investigation claim, recovery's
session entry-point list, touched detail examples and the tracked Claude install.
Archive plans/evidence describe retained implementation/history rather than live
CLI recipes and stay. Protected CLAUDE.md, generated help and runtime warning
stay under the explicit follow-up entry.

Full suite at `99ffa33e6`: 14,698 passed, 66 skipped in 64.75s. Affected tests
pass again (58 in 0.80s). No runtime implementation changes are introduced.


## Claude review 3

Range `330441789..0ba7e8692`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `20aa6f74-8c4f-41fd-9db2-4bc2a8a9f3e6`; CLI exits zero.
Report: `.tmp/iteration-guide-routes.review-3.md`. No medium-or-higher finding;
the reviewer explicitly classifies the pass as low-yield.

| Finding | Disposition |
| --- | --- |
| 1 low: ordinary-run iteration flags remain in backlog | Fixed: remove ineffective flags from the enumerated ordinary-run recipes and replace the wizard's loop claim with fixture coverage and post-run review. |
| 2 low: hand-written run synopses list accepted but ineffective flags | Deferred with existing help-surface follow-up; add README and command reference to its Files list so help and synopses move together. |
| 3 generated pointer repeats deferred issue | Already tracked; no new finding. |
| 4 optional: restore iteration to run-oriented hints | Declined: iteration is documented at its authoring verbs, not ineffective run flags. |
| 5 optional: show literal commit command | Declined: workflow explicitly requires verifying and committing separately; reconcile-code accepts no commit flag. |
| 6 optional: capital letter after colon | Declined: no behavior/interpretation defect; avoid installer churn for typography. |

The third sweep covers ordinary-run ineffective iteration recipes, not only
reconcile aliases. Tracked Claude files byte-match their canonical sources;
review 3 independently verifies both copies. Full suite at `0ba7e8692`:
14,698 passed, 66 skipped in 63.72s; affected tests 58 passed in 0.67s.
Convergence window: one completed low-yield pass; independent confirmation pending.


## Claude review 4 and closure

Range `330441789..655c70b3a`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `0cb2fa6f-c51e-464b-982f-0f9336172154`; original CLI exits
zero. Report: `.tmp/iteration-guide-routes.review-4.md`. It independently
re-runs the 58 affected tests (pass in 0.73s), probes defaults/rejections and
verifies canonical/installed-copy equality. It reports no medium-or-higher issue
and explicitly classifies the pass as low-yield.

| Finding | Disposition |
| --- | --- |
| 1 low: recovery audit intro/crash text still says both loops | Fixed: name only the completeness loop, and give detail reconciliation its separate scoped-walk interruption guidance. Identifier/vocabulary sweep covers intro, refresh comparison, crash section and internal helper table. |
| 2 low: drift-detection module docstring advertises rejected invocation | Deferred in the existing policy/help follow-up: add the exact source docstring to its Files list. Runtime/source cleanup stays outside this instruction repair. |
| 3–4: backlog examples lose an execute step | Refuted by reviewer after inspecting base: both already contain a rejected reconcile-mode recipe, not execution. No execute step is removed by this change. |
| Optional: phase label, router typography/hints, operator voice | Retain existing dispositions; no newly verified route/default defect. |
| Protected policy, generated help and runtime warning/synopses | Already deferred explicitly; do not silently broaden this repair. |

Convergence is **low-yield**: two consecutive completed independent passes
(3 and 4) add only low/advisory findings, with no new material defect. Finish the
bounded recovery-text application and retain the named follow-up; stop here
under the repository policy rather than raising the pass cap for prose precision.
There is no claim of zero findings or a clean whole-branch review after the
final record/recovery edit.

Final verification: the installed Codex and tracked Claude skill/directive
files byte-match their canonical sources. `git diff --check` is clean. No
runtime behavior or parser change is introduced. Full suite at `0ba7e8692` is
14,698 passed / 66 skipped in 63.72s; later changes are backlog recipes,
recovery prose and review records. All findings have dispositions. Changes are
committed on `fix/iteration-guide-routes`; no push or PR is part of this action.
