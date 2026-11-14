# Roadmap stack-aware approval — post-run review ledger

## Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-stack-aware-approval` (`docs/implementation-plans/archive/2-roadmap-stack-aware-approval.md`), 8 steps (7 code, step 8 non-code), all green. Source: `BACKLOG.md` #431; Jira `IPPT-9`. |
| Branch | `codex/roadmap-stack-aware-approval-seed`, based on `origin/main` at `950365c2` (PR #19 merged). Local only; publishing needs a force-push. |
| Range | Baseline `aba83968`; run head `f62aad66`; reconcile-code reports committed at `d942827d`. Product code net +378 lines, tests net +3,573. |
| Checks run | Four bare-plan `completeness-audit --iterate` rounds and one detail-grounded audit (`20260924-235704-completeness.md`), each `no-qualified-current-evidence` at the pass cap; loop stopped by exit 2. Full suite green after every step and at the end: 13,936 passed, 190 skipped. One `reconcile-code --all` sweep (`20260925-014553` through `20260925-015848` `-run-reconcile.json`): 0 critical/high/medium, 1 nit. |
| `/code-review` | Pass 1 (`high`, report-only, `aba83968..b64880d9`): no logic findings. Pass 2 (`high`, independent, `aba83968..40fdb416`): no critical/high/medium; one low PLAUSIBLE finding, three nits. |
| Current disposition | **Converged (2026-09-25).** Sweep nit declined. P1.1 fixed, P1.2 and P1.3 declined, P1.4 trimmed, P1.5 left. P2.1 declined and filed in `BUG_BACKLOG.md`, P2.2 declined, P2.3 and P2.4 fixed. |

## Settled decisions (hand these to every reviewer)

From `BACKLOG.md` #431, the plan's Architecture, and the owner's decisions of 2026-09-24. A finding proposing the opposite is invalid, not deferrable.

- **Approval carries the stack.** A structural approval covers every unpromoted hop above the candidate's recorded root (`root_version_id` in stored evidence, never the current head). The stack is structural iff any such hop stores a STRUCTURAL route. Derived at use; no new persisted field; the root's own route is never read.
- **Hop contributions.** A stored route contributes itself; a hop with none (legacy, or an answered replacement) contributes nothing. A candidate with no recorded root yields "no structural hop", distinct from underivable. A hop that is missing, not a stored candidate, or fails validation makes the whole stack underivable: every guard and the recovery predicate refuse it.
- **Presentation scope (decision 2, amended 2026-09-24).** The structural decision and the proposal output of a stack with a structural hop show the whole stack. The answered route's output, `--reject-candidate`, `--discard-candidate`, and any stack with no structural hop keep current output; showing presentation-only hops on the answered route is invalid.
- **Confirm step.** Approve without `--confirm-stack-digest` prints the stack and a digest and writes nothing; with the digest recomputed at confirm time it seals and promotes; any other digest refuses with no write. The digest is stateless and not stored; no terminal prompt, show command, or confirm for edit or reject.
- **Binary observable.** Every candidate-lineage promotion whose hops above the root include a STRUCTURAL one carries a `structural-approval` seal on its top candidate and journals the enrolled seed-state member. The seal has one construction site, the confirmed approve. An answered seal over a structural stack is refused at the promotion boundary and both answered-route entries.
- **Edit and reject.** The edit check tests the replacement's stack (source's stack plus its own computed route). Reject and discard still release the whole active pointer; abandoned hops stay as history.
- **The interim block is retired last.** `--propose-candidate` stacks under a structural candidate; the stacking carve-out tests stay.
- **Old seals.** Not migrated; an unpromoted one stays promotable only while its candidate is active.
- **Deliberately not:** semantic judgment of stack content; a content-derived cumulative classifier; a second structural gate or per-hop approval; a new persisted stack or binding field; auto-approval; a terminal prompt; changes to the promotion writer's authority, publication journal, recovery machinery (beyond its stack-aware predicate), or the version and candidate stores; run-log lifecycles for decision commands; the ledger's current/stale label (#428); the unreachable selected-local runner (#429); behavior changes for legacy candidates without a route or root.

## Reconcile-code sweep 1 — triage

- **Nit (step 6, `impact: low`)** — `_render_structural_reject_effect` (`plan_tool/cli/roadmap_cmd.py`) inlines `tuple(hop.version_id for hop in view.hops)`, the same expression as `CandidateStackView.promoted_version_ids` (`plan_tool/roadmap_candidate_review.py:1483`). **Disposition:** declined — the property is named for what a promotion carries while the note lists what a reject drops, and `test_reject_note_lists_every_dropped_hop_and_says_nothing_is_promoted` fails if the note stops naming every hop.

## Review pass 1 (2026-09-24)

No logic findings; the route sweep, guard inventory, carve-out pinning tests, confirm step, and block removal (`db4e1809`) matched the code.

- **P1.1 — Comment and test docstring overclaim** (nit, documentation, CONFIRMED): `plan_tool/cli/roadmap_cmd.py:1207-1209` and `test_proposal_output_keeps_todays_output_when_the_stack_has_no_structural_hop` say "gains no failure mode", but an unreadable lower hop exits 1 after the proposal is stored (fail-closed, pinned by `test_proposal_stack_failure_after_a_stored_proposal_prints_the_stored_lines_and_exits_incomplete`). **Disposition:** fixed `5949f8fa` — wording only.
- **P1.2 — Approve and non-approve branches build and render the view identically** (nit, simplification): `roadmap_cmd.py:1351-1370`; suggestion is to hoist. **Disposition:** declined — no plan property depends on it, step 5's detail split them on purpose, and a refactor would reset the convergence window for a nit.
- **P1.3 — One confirmed approve derives the stack seven times** (low, efficiency, CONFIRMED by count): repeats inside the writer guard are independent re-checks. **Disposition:** declined — the guarded repeats are the design, stack depth is small, and sharing the pre-guard derivations adds coupling.
- **P1.4 — Prose and vocabulary pins in `tests/test_roadmap_feedback_format.py`** (proportionality, not a logic verdict): five new tests (+116 lines), including a retired-wording scan that admits a new spelling escapes, and two pins on the earlier ledger `roadmap-structural-feedback-approval-code-review.md`; agreement checks between prose artifacts are the shape the development guide refuses. **Disposition:** fixed `cce75613` (source word: "trimmed") — scan, both earlier-ledger tests, and their helpers removed (73 lines); the two format-doc phrase tests stay. Full suite after: 13,936 passed, 190 skipped.
- **P1.5 — CLI label tests, flag-plumbing rows, stated redundancy** (proportionality, not a logic verdict): about fifteen cases pin labels, line order, and flag misuse exiting 2. **Disposition:** declined (source word: "left") — they pin producer-to-consumer seams stubs cannot show and are cheap; removal is churn.

Considered and not reported (refuted or settled): the boundary check "untested" (refuted by `test_seal_requirement_holds_at_the_boundary_when_the_review_guards_are_bypassed`); old single-command seals (pinned by `test_an_approval_of_a_lower_hop_cannot_promote_after_a_later_batch_stacks_on_it`); reject note printed before the decision, exit 1 after a stored proposal, route-less hops, and legacy hops failing validation (all settled and pinned).

## Review pass 2 (2026-09-24)

Scope `aba83968..40fdb416` (comment, docstring, and test changes since pass 1). No critical, high, or medium finding; twelve traced attacks were clean, and pass 1's claims re-checked against the code.

- **P2.1 — A hop whose stored artifacts fail today's parser escapes as a raw exception** (low, error path, PLAUSIBLE): `_require_reproducible_batch_diff` (`plan_tool/roadmap_candidate_run.py:927`) catches `ValueError` but not `RoadmapArtifactError` (`class RoadmapArtifactError(Exception)`, `plan_tool/roadmap_artifacts.py:378`), so such a hop gives a traceback instead of the underivable refusal. No write happens on any path; only the refusal shape is wrong. Not reproduced. **Disposition:** declined and filed in `BUG_BACKLOG.md` (section ROADMAP, severity RISK, commit `62785adc`) — contrived trigger, and a logic-changing fix would reset the convergence window; owner, 2026-09-25. Fix on file: add `RoadmapArtifactError` to the catch tuple with one test in `tests/test_roadmap_candidate_run.py`.
- **P2.2 — Reject note printed in the indicative before the decision applies** (nit, output wording, CONFIRMED): `roadmap_cmd.py:1371-1372`; on a library refusal stdout shows "released … dropped" above `structural decision: reject refused`, exit 2. Order is pinned by `test_reject_over_a_real_stack_prints_every_hop_and_the_drop_note_before_releasing_the_pointer`. **Disposition:** declined — the final line and exit status are correct; owner, 2026-09-25.
- **P2.3 — `_ROOT` left unused by the P1.4 trim** (nit, dead code, CONFIRMED): `tests/test_roadmap_feedback_format.py`. **Disposition:** fixed `718a3a7c`.
- **P2.4 — This ledger named the review model, tool invocation, and a session id** (nit, convention; reviewer PLAUSIBLE, verified CONFIRMED): a repeat of the earlier ledger's P3.1 class. **Disposition:** fixed `48a7aefa` — both sites say "an independent review pass"; the pre-push grep found no other hit.

Considered and not reported (settled): retroactive refusal of pre-change stored state (the defect the plan closes); a stacked batch orphaning a sealed-but-unpromoted approval; stack-view failure blocking edit and reject; recovery failing closed on lower-hop load problems.

## Out-of-range findings

_(none)_

## Convergence status

**Converged (2026-09-25).** Pass 1 was clean on logic. Pass 2 added one low PLAUSIBLE finding (P2.1, declined and filed as a `RISK` in `BUG_BACKLOG.md`) and three nits (P2.2 declined, P2.3 and P2.4 fixed), with no new material issue. Two consecutive clean or low-yield passes against the latest logic-changing commit `db4e1809` (step 7) satisfy `integrations/shared/DIRECTIVES.md`, "After `run` finishes a plan". Every commit since is a comment, docstring, test, or document change (`5949f8fa`, `cce75613`, `718a3a7c`, `48a7aefa`, `62785adc`, and the ledger commits), so the window was never reset. No further pass launches.

Not covered: P2.1 stays open in the bug backlog; the reconcile-code sweep ran once (a further full sweep is warranted only after a verified class-wide correction). The full suite passed at the end of the loop (13,936 passed, 190 skipped) on the tree holding every code, test, and backlog commit.
