# Headless-process route inventory (2026-08-28)

## Purpose and boundary

This dated pre-proof inventory satisfied BACKLOG #322's required current-code
sweep at `69628a05`. It classified human-input and human-availability routes
by their observable operator contract and selected one bounded seed. The
selected route is now complete; this analysis remains evidence for that
selection, not a current inventory for another route.

The completed `cmd_review` proof is excluded. Its explicit remote, non-TTY,
skip-or-quit contract is intact; this inventory finds no failure that warrants
reopening it.

## Method

The identifier sweep covers direct `input` / `builtins.input` reads,
`sys.stdin.isatty()` and injected `isatty_fn` checks, and the named helpers
that gate a prompt or an operator wait. The vocabulary sweep covers `remote`,
`headless`, `non-interactive`, `TTY`, `terminal`, `prompt`, `confirm`,
`readiness`, `rate limit`, `collision`, `skip`, `quit`, `feedback`, and
`apply`.

`prompt` has two meanings in this repository. Model prompt construction and
terminal appearance/progress matches do not read a human response, so they
are recorded as exclusions instead of migration candidates. The response
record provider remains used only by `review_walk`.

## Classified routes

| Contract family | Current identifiers and caller | Non-TTY behavior and operator consequence | Owner and disposition |
| --- | --- | --- | --- |
| Completed review entry | `cli/review_cmd.py:cmd_review`, `_remote_non_tty_review_walk_allowed`, `review_walk.walk_recommendations` | Exact `PLAN_TOOL_HUMAN_IO=remote` plus non-TTY permits only one `s`/`skip` or `q`/`quit` annotation request. No action or feedback can run. | **Excluded, completed proof.** `tests/test_review.py` and `tests/test_review_walk.py` cover the selected gate and response set. |
| Completed standalone saved-review annotation | `cli/review_cmd.py:cmd_review_walk`; aliases `reconcile-plan-walk`, `reconcile-walk`, and `review-walk` | Exact remote, non-TTY input now permits only a skip or quit annotation walk for an eligible final saved review. It preserves final-sidecar selection, ordinary non-TTY reporting, and terminal actions. | **Completed bounded proof.** [Headless Review Walk Annotation Entry keeps its caller-specific skip-only boundary. |
| Inline reconciliation and action dispatch | `cli/reconcile.py`, `cli/review_actions.py`, `cli/run_cmd.py:cmd_reconcile_code` | Reuse can be automatic in non-TTY mode; some paths apply findings or iterate with `yes_to_all`. Nested detail reconciliation warns and leaves findings unapplied when it cannot walk. | **Different owner; stay unchanged.** The operator consequence includes plan/code edits and iteration, so a skip/quit annotation proof cannot select it. |
| Completeness and data-contract application | `cli/completeness_phases.py`, `cli/completeness_apply_parallel.py`, `cli/data_contract_cmd.py`, `cli/gates_cmd.py` | Serial non-TTY completeness and data-contract walks report and stop; completeness returns a nonzero result so automation cannot mistake it for convergence. Parallel completeness apply is its explicit unattended contract. Gate suggestions report rather than write. | **Terminal/manual or explicit parallel owner.** These routes decide authoritative plan or contract changes; remote annotation alone is not a substitute. |
| Destructive confirmation | `scope_out._confirm_scope_out`, `reground._confirm_reground`, `roadmap._confirm_apply_seeds`, `cli/manifest.py`, `cli/worktree_cmd.py`, `cli/lessons_cmd.py` | Non-TTY refuses the mutation unless the operator supplies the existing explicit `-y` / `--yes` opt-in. | **Stay terminal-only / flag-authorized.** A remote response must not bypass the existing assent boundary. Relevant coverage remains in the corresponding command tests. |
| Structural replacement and merge | `detail._confirm_replace`, `_confirm_split`, `_confirm_merge`, `launcher.escalate_to_split`, `cli/authoring.py:cmd_merge` | Replacement and structural confirmation normally decline off a TTY; the explicitly requested merge path has its existing non-TTY semantics. | **Different owner.** These routes need structural-safety and re-authoring decisions, not a generic response record. |
| Collision pause | `change_collision.prompt_user_to_merge` and `handle_drift_collision` | Non-TTY writes/displays sidecars, halts iteration, and requires the operator to merge files before retrying. | **Stay external-work owner.** The needed response is a completed file merge, not a choice that a skip/quit record can establish. |
| Rate-limit recovery and wait cancellation | `shell._can_prompt_on_rate_limit`, `launcher._can_prompt_on_rate_limit`, `claude_errors.ask_on_rate_limit_action`, `wait_until` | A rate-limit menu is available only with terminal stdin and stderr; a keypress can stop a terminal countdown. Non-TTY execution uses its configured recovery behavior rather than blocking on a menu or key poll. | **Different recovery owner.** It is already separately constrained by rate-limit policy and does not select a response-record lifecycle. |
| Create and detail review/defaults | `create.prompt_metadata`, `prompt_steps`, checkpoint resume gates, `intent_proposal.review_intent_drafts`, `detail._confirm_resume` | Required manual authoring input fails cleanly or takes the documented default; proposal and checkpoint paths either preserve proposals, auto-accept a valid resume, or skip an optional review. | **Absent-mode defaults, stay unchanged.** The selected property is deterministic authoring behavior, not delayed human response. |
| Invocation/selection menus | `cli/run_cmd:_read_plan_choice`, `_prompt_run_scope`, `_confirm_missing_step_details`, `cli/authoring._confirm_repo_root`, `_create_branch_collision_gate` | Non-TTY requires an explicit plan name where necessary, otherwise keeps the documented current-root/default behavior or proceeds with the existing missing-detail warning. | **Terminal UI or established default.** These routes need command arguments, not a remote continuation policy. |
| Jira configuration and assignment | `cli/jira_cmd` epic assignment, tag confirmation, and configuration wizard | Non-TTY rejects missing epic/tag input and directs the caller to `--epic`, a tag, or `jira config`; the wizard collects free text interactively. | **Configuration owner.** Explicit CLI arguments already provide the headless form; a record protocol would widen the configuration scope. |
| Record protocol itself | `human_io.make_human_input_provider`, `review_walk._request_human_input` | Filesystem request/resolution records block until a matching response and are retained. Only `review_walk` constructs this provider. | **No lifecycle change.** Retention remains unselected until a route group names an owner and needs a lifecycle policy. |
| Vocabulary-only exclusions | model invokers, `renderer`, `backend`, `progress`, and `style` | These matches construct model text, measure prompt size, render progress, or choose color; they never solicit an operator response. | **Excluded.** They are not headless human-input routes. |

## Completed selection checked against the goal

The selected `cmd_review_walk` group was the smallest route whose operator
consequence could remain a human annotation without enabling a plan or code
action. The completed proof admits only explicit remote mode and non-TTY stdin
and records only a skip or quit against a selected final saved finding. It
retains existing final-sidecar eligibility, `--id`, `--rewalk`, info selection,
ordinary non-TTY presentation, and terminal action behavior.

The route does not authorize remote feedback, apply, run, apply-all,
structural remedies, default changes, cleanup, timeouts, another transport, or
a shared policy for its peer callers. In particular, it must not turn a
qualified completeness sidecar into an automatic completion or application
path. A later lifecycle decision remains contingent on a selected route that
actually requires it.

## Follow-on condition

`headless-review-walk-annotation-entry` delivered this selection without
revising `human_io.py` or the shared walk engine. No follow-on route is
selected. Before selecting one, refresh this inventory against post-proof code
and compare every candidate's identifier and vocabulary sites with the
headless-process goal; a matching input call alone is insufficient.
