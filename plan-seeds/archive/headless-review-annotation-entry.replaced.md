> **Replaced**: this file has been superseded by `docs/implementation-plans/2-headless-review-annotation-entry.md`.
> Preserved here for history; do not edit.

# Headless remote review annotation entry

## Outcome

When `PLAN_TOOL_HUMAN_IO=remote` is explicitly configured and stdin is not a
TTY, the `review` command handler (`review`, `reconcile`, and
`reconcile-plan`) will start one saved-review walk that accepts only remote
annotation, feedback, skip, and quit responses. The walk will not dispatch an
action or mutate a plan in that mode. With remote mode unset, every existing
non-TTY skip and terminal walk behavior will remain unchanged.

## Why this is the next proof

The completed `human-input-seam` plan proves filesystem request and resolution
records only after `walk_recommendations` starts. The review command's caller
gate still requires `sys.stdin.isatty()`, so a configured headless process
reports findings and returns without reaching the provider.

Opening that gate without a smaller action contract is unsafe. The existing
annotation default dispatches `apply`; downstream review actions can retain an
applied change automatically in a non-TTY process and include terminal-only
confirmation prompts. An annotation-only walk establishes the caller-entry
property without silently weakening that mutation safety.

## Scope contract

- **In scope:** `plan_tool.cli.review_cmd.cmd_review` and its shared
  environment gate; `plan_tool.review_walk.walk_recommendations` only as
  needed to present and enforce a non-mutating response set; focused tests in
  `tests/test_review_walk.py`; and `HUMAN_IO_FORMAT.md` if its displayed
  remote prompt contract changes.
- **Allowed behavior:** explicit remote mode plus non-TTY stdin may enter a
  saved-review walk through `cmd_review`. In that walk, blank input will not
  dispatch an action, and apply, run, and apply-all will not execute. Remote
  feedback remains an annotation until a later terminal walk handles action.
- **Terminal preservation:** when remote mode is unset, the current command
  menu, default apply behavior, feedback semantics, and non-TTY skip remain
  unchanged. `--no-walk`, `--no-save`, and `--dry-run` continue to suppress a
  walk.
- **Out of scope:** `cmd_review_walk` and every other
  `walk_recommendations` caller; action dispatch and its keep/revert or
  structural prompts; all other direct-input and availability routes; remote
  defaults, cancellation, transport changes, and record retention. #322 owns
  those later decisions.
- **Verification:** prove that a non-TTY remote `cmd_review` reaches request
  records and persists skip and feedback annotations without calling raw
  terminal input or the action callback; prove that its blank, apply, run, and
  apply-all responses fail closed; retain existing terminal and ordinary
  non-TTY skip coverage.

## Fresh inventory (provenance: 2026-08-27, commit `5aaedca3`)

The inventory uses both identifiers and vocabulary before selecting the one
route above:

- Direct-read identifiers: bare `input(`, `builtins.input`, and injected
  `input_fn(`.
- Availability identifiers: `sys.stdin.isatty()`, `_stdin_is_tty()`, and
  `_stdin_has_pending_input()`.
- Vocabulary: prompt, confirmation, reuse, choice, interactive,
  non-interactive, and `walk_recommendations`.

| Route group | Current contract | Decision |
| --- | --- | --- |
| `cli/review_cmd.cmd_review` and `_review_walk_environment_allows` | A non-TTY process skips a saved-review walk even when the existing provider is configured remote. | **Select.** It is the named caller that prevents the completed proof from being reached. |
| `review_walk.walk_recommendations` | Already publishes `review-walk.annotation` and `review-walk.feedback` through the provider; its default command can dispatch an action. | **Select only the non-mutating command surface.** It is required to make the caller entry safe. |
| `cli/review_actions` | Apply, file-check, and structural routes can write plans; two paths use raw terminal confirmation and non-TTY apply may retain a change. | **Stay.** The selected walk must not reach these routes. |
| `cli/review_cmd.cmd_review_walk` | A standalone saved-review walk remains terminal-only. | **Stay.** It is a separate entry command; `cmd_review --reuse` can resume the selected proof. |
| `cli/reconcile` | Detail and run reconciliation use separate reuse, iteration, and automated-apply rules. | **Stay.** Its `walk_recommendations` callers do not share the selected non-mutating contract. |
| `cli/data_contract_cmd` and `cli/completeness_phases` | Manual audit-application walks modify authoritative documents. | **Stay.** Their apply policy is intentionally distinct. |
| `cli/run_cmd` | Missing-detail confirmation and run-scope choices are execution-selection or destructive-confirmation decisions. | **Stay.** No remote default or scope-selection policy is selected. |
| `create.py`, `intent_proposal.py`, and `cli/authoring.py` | Plan and seed authoring use interactive choices, risk declarations, and save confirmations. | **Stay.** They are authoring contracts, not the review command's response path. |
| `detail.py`, `reground.py`, `scope_out.py`, `roadmap.py`, and `change_collision.py` | Each TTY gate protects a structural, replacement, or collision decision. | **Stay.** No common headless policy is established. |
| `cli/jira_cmd`, `cli/manifest.py`, `cli/worktree_cmd.py`, `cli/lessons_cmd.py`, `cli/gates_cmd.py`, and `cli/completeness_cmd.py` | These routes configure external work, modify manifests, or apply operator decisions. | **Stay.** They are independently owned behavior classes. |
| `claude_errors.py` | Rate-limit and backend-selection prompts recover a subprocess failure. | **Stay.** It is not a review-walk response route. |
| `plan_tool.human_io` | The landed provider supplies request records, resolution matching, and no-clobber publication. | **Retain.** The selected proof consumes it without adding another provider or transport. |
| Resolved record retention | A remote session leaves request and resolution records for a future owner to clean up. | **Defer.** #322 already records this as a separate lifecycle-policy decision. |

## Seed guardrails

- Do not replace TTY detection repository-wide or infer remote mode from a
  missing TTY; only the explicit existing remote configuration can opt in.
- Do not make apply, run, apply-all, file-check, or structural commands
  silently succeed in a remote non-TTY walk. Refusing them is the proof's
  safety property.
- Do not migrate a second command merely because it has an `input_fn` or TTY
  check. A later route must establish its own behavior and owner.
- After creating or changing the plan, sweep the selected identifiers
  (`cmd_review`, `walk_recommendations`, remote mode, and action commands) and
  the vocabulary (headless, annotation-only, mutation, skip, feedback, and
  TTY) against this outcome before treating the scope as complete.
