> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Describe stack-aware approval in the docs, the persisted-contract doc, and the review ledger; delete the shipped backlog entry and reword the entries that name the block

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step brings every current-state document in line with the behavior steps 1–7 ship. The documents are `ROADMAP_FEEDBACK_FORMAT.md`, `docs/how-to/roadmap.md`, `docs/ARCHITECTURE.md`, `README.md`, `CAPABILITIES.md`, `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, the two handoffs, and `BACKLOG.md`. Approve becomes two invocations, an approval covers the whole unpromoted stack, and a new batch stacks under a structural candidate. The step deletes `BACKLOG.md` #431 and rewords the two places in entry #430 that name the block. It adds `changelog.d/roadmap-stack-aware-approval.md`. The main decision is that each fact has one home document and the others point to it. `DATA_CONTRACT.md` states that the stack and the digest are derived at use and never persisted. On green, no current-state document states the block, and `tests/test_roadmap_feedback_format.py` pins the reworded lifecycle.

## Table of Contents

- [Summary](#summary) — what the step changes and the key decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the documents that state retired behavior
- [Input](#input) — what steps 1–7 hand this step, and what its checks cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the one new file and the edits per file
- [Implementation](#implementation) — facts each document must state, the site sweep, constraints, and pins
- [Tests](#tests) — pin updates, new cases, and non-code verification
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan, the ledger, and the modules to read
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — what this step does not do, and why

## Why

Five current-state documents describe behavior that steps 1–7 retire.
- `ROADMAP_FEEDBACK_FORMAT.md` (§ "Ledger-to-candidate workflow", item 4), `docs/how-to/roadmap.md` (§ 6), and `docs/ARCHITECTURE.md` (the paragraph on the reviewer ledger) each say an active structural candidate blocks another `--propose-candidate`.
- The same three describe approve as one command that seals and promotes.
- The review ledger `handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md` lists the block under "Settled decisions". Its "Open owner directions" section calls the stack work "not implemented".
- The completion record `handoffs/2026-09-22-roadmap-feedback-revision-approval.md` states the block as an outcome.
- `README.md`, `CAPABILITIES.md`, `ROADMAP_FORMAT.md`, and `DATA_CONTRACT.md` say an approval binds "one candidate". They say nothing about the stack or the confirm.

A reader or an audit acts on stale current-state prose. The already-implemented signal (`# Roadmap` matching in `ROADMAP_FEEDBACK_FORMAT.md` and the ledger) is a title match. Neither file describes a stack-aware approval at HEAD. The ledger mentions "stack" only as an owner direction marked not implemented, so none of this step's work is done.

## Input

- **Outputs of steps 1–7.** Names, flag spelling, result lines, and exit statuses come from the landed code. The landed names win over any name in this file or in the sibling detail files.
  - **Flag and confirm contract (step 5).** Read the flag off `plan_tool/cli/roadmap_cmd.py` and `docs/cli/roadmap.md` (step 5 regenerates it). Read result lines and exit statuses off the step 5 assertions in `tests/cli/test_roadmap_cmd.py`, not off step 5's detail file.
  - **Stack view and digest (step 4).** Read what the digest covers off `plan_tool/roadmap_candidate_review.py`. The digest is recomputed, never stored.
  - **Presentation surfaces (step 6).** Which outputs print the stack: the structural decision (edit and reject), and the proposal output of a stack that carries a structural hop.
  - **Guards (steps 1–3, 7).** The stack-route derivation lives in `plan_tool/roadmap_candidate_run.py` beside `source_ancestry_to_root`. Steps 2 and 3 make the answered route, decision eligibility, promotion, and recovery ask it. Step 7 removes the batch block.
- **Plan ownership of the facts.** The plan's "Design decisions" section and the settled owner sign-off state the property. Documents restate the shipped behavior, not the plan's wording.
- **Pins that read the documents this step edits.**
  - `tests/test_roadmap_feedback_format.py` reads `ROADMAP_FEEDBACK_FORMAT.md`, including the "no prompt or `-y` shortcut" phrase in § "Settlement confirmation".
  - `tests/test_roadmap_format.py` reads the marked `immutable-candidate-version-authority` block of `ROADMAP_FORMAT.md`. It requires six symbol anchors in that block and forbids the phrase "feedback selector" there.
  - The same file requires `--propose-candidate` present and `--revise-feedback` absent in five documents, and holds brief-drift phrase pins in several of them.
  - `tests/test_backlog_ids.py` and `tests/test_backlog_readability.py` read `BACKLOG.md`.
  - `tests/test_capability_catalog.py` reads `CAPABILITIES.md`.
- **What this step's checks cannot show.** They prove wording and links, not that the prose matches the code. Accuracy comes from reading the landed modules and tests while writing.

## Files (creates vs edits)

- **New files:**
  - `changelog.d/roadmap-stack-aware-approval.md` — a fragment stating the two user-visible changes. The format is in `changelog.d/README.md`.
- **Existing files (edits only):**
  - `ROADMAP_FEEDBACK_FORMAT.md` — § "Ledger-to-candidate workflow", items 3–5. This is the home of the lifecycle vocabulary.
  - `docs/how-to/roadmap.md` — § 6 "Turn reviewer ledger feedback into a candidate". This is the operator procedure.
  - `docs/ARCHITECTURE.md` — the `## Roadmap` paragraph that begins "The reviewer ledger remains mutable input outside artifact versions".
  - `README.md` — the command-catalog comment on `--decide-candidate`, and the "Reviewer ledger items" bullet under "Review what it guessed".
  - `CAPABILITIES.md` — the `--enroll-version, --propose-candidate, --decide-candidate …` bullet of the `architecture-roadmap` capability.
  - `ROADMAP_FORMAT.md` — the paragraph opening § "Reviewer feedback and candidate lifecycle", and the sentence in the marked authority block about enrolled structural publication.
  - `DATA_CONTRACT.md` — § "Enrolled candidate approval records".
  - `handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md` — the current-state sections only: Summary, Settled decisions, Open owner directions, Convergence status.
  - `handoffs/2026-09-22-roadmap-feedback-revision-approval.md` — the completion record and "Current artifacts".
  - `BACKLOG.md` — delete entry #431 whole. Reword the `**Dependencies:**` bullet and the `**Out of scope / Non-goals:**` bullet of #430.
  - `tests/test_roadmap_feedback_format.py` — update the approval pin and add the cases in [Tests](#tests).

## Implementation

**What must be true when done.** Every current-state document states only what ships. The block is gone from them, approve is two invocations, and an approval covers the whole unpromoted stack.

**Facts to state, and where they live.** Each fact has one home. Other documents state the part their reader needs and point to the home.

| Fact | Home | Also stated in |
| --- | --- | --- |
| A new batch sources from the active candidate, structural or not. `--propose-candidate` never refuses because the active candidate is structural. | `ROADMAP_FEEDBACK_FORMAT.md` items 3–4 | `docs/how-to/roadmap.md`, `docs/ARCHITECTURE.md` |
| A stack is structural iff any hop above the recorded root has a stored STRUCTURAL route. It is derived at use. A hop with no stored route contributes nothing. | `ROADMAP_FEEDBACK_FORMAT.md` | `docs/ARCHITECTURE.md` (owner module), `DATA_CONTRACT.md` (nothing persisted) |
| Approve is two invocations. The first prints every unpromoted hop above the root, the cumulative diff, and a digest, writes nothing, and exits with the landed confirmation-required status. The second supplies the digest. It seals and promotes only when the library's recompute matches exactly. | `docs/how-to/roadmap.md` (procedure), `ROADMAP_FEEDBACK_FORMAT.md` (lifecycle) | `README.md`, `CAPABILITIES.md` |
| The digest is stateless. It is not a stored receipt, and it covers the stack's stored facts, not the printout's wording. | `DATA_CONTRACT.md` | `ROADMAP_FEEDBACK_FORMAT.md` |
| The seal binds the top candidate. Promotion re-derives the stack. A promotion whose stack carries a structural hop requires the `structural-approval` seal and journals the enrolled seed-state member. Recovery applies the same rule. | `DATA_CONTRACT.md`, `ROADMAP_FORMAT.md` | `docs/ARCHITECTURE.md` |
| The answered route (`--review-candidate` / `--answer-question`, and an answered seal promoted through `--promote-review-seal`) refuses a stack that carries a structural hop and names `--decide-candidate`; a structural-approval seal promotes as before. | `ROADMAP_FEEDBACK_FORMAT.md` item 4 | `docs/how-to/roadmap.md` |
| Edit is accepted when its replacement's stack carries a structural hop. Reject releases only the active candidate and drops every unpromoted hop. Neither takes a confirm. | `ROADMAP_FEEDBACK_FORMAT.md` | `docs/how-to/roadmap.md` |
| Deliberately not built: a read-only show command (an unconfirmed approve is the read-only view), a confirm step for edit or reject, and stack output on the answered route and standalone `--reject-candidate` / `--discard-candidate`. | `docs/how-to/roadmap.md` | — |

- **State the omissions as omissions.** Say "deliberately not" with the reason. Do not leave the absence to be inferred, and do not present any of the three as planned work.
- **A seal left by an interrupted confirm stays promotable while its candidate is still the active one.** Re-running the confirmed approve with the same digest promotes it, and `--promote-review-seal` also works. A later stacked batch makes the seal stale; the operator then approves the new top, which covers the sealed hop. State this once in `docs/how-to/roadmap.md`.
- **Do not assert `-y` behavior.** State that the confirm is not a terminal prompt. Say whether `-y` is refused or ignored only after reading the landed parser.
- **Keep the pinned settlement sentence.** The "no prompt or `-y` shortcut" sentence in § "Settlement confirmation" belongs to settlement. Leave it as is.

**Site sweep: the class is "current-state prose that states the block, the single-command approve, or a one-candidate approval".** The identifier pass covered `--propose-candidate`, `--decide-candidate`, `structural-approval`, `promote_review_seal`, and `#431`. The vocabulary pass covered "blocks another", "refuses before any model call", "the block", "invokes promotion", "seals and promotes", "top candidate", and "unpromoted".

| Site | Action |
| --- | --- |
| `ROADMAP_FEEDBACK_FORMAT.md`, items 4–5 | Rewrite: delete the block sentence, describe two-invocation approve and stack scope, keep the seal-then-promote separation. |
| `docs/how-to/roadmap.md`, § 6 | Rewrite: the command block shows both approve invocations. Delete "blocks another `--propose-candidate`" and the answered-route sentence gains the stack. |
| `docs/ARCHITECTURE.md`, ledger paragraph | Rewrite: delete the block clause. Name the derivation's owner module, the stack view and digest owner, and that promotion applies the seed-state effect for a structural stack. Cite only symbols that exist at HEAD. |
| `README.md`, two sites | Terse: the catalog comment gains the two-invocation confirm, and the bullet says an approval covers the stack its top carries. |
| `CAPABILITIES.md`, the lifecycle bullet | Rewrite the "Structural approval seals exactly the reviewed candidate" clause. Leave `surfaces` and `principles` untouched, because this step adds no subcommand or module. |
| `ROADMAP_FORMAT.md`, lifecycle paragraph and marked block | Update the approval sentence and the seed-state sentence. Keep the six anchors, and never write "feedback selector" in the block. |
| `DATA_CONTRACT.md`, approval records | Change "when the promoted candidate is a structural proposal" to the stack rule. State that no stack or digest field is persisted. Keep the route-less-evidence carve-out. |
| The 2026-09-23 ledger | See the ledger rules below. |
| The 2026-09-22 handoff | Replace the block clause with the current property and one dated pointer to `roadmap-stack-aware-approval`. Add the plan to "Current artifacts". |
| `BACKLOG.md` #431 | Delete whole. It is a full entry: it has no `→ promoted to` stub and no Jira key, and the source backlog note says roadmap items are owner-tracked, not promoted. |
| `BACKLOG.md` #430 | Two rewords. `**Dependencies:**` becomes `none.` and the adjacency clause is deleted. In `**Out of scope / Non-goals:**`, delete "and any change to the structural batch block" and repair the list grammar. |

**Sites checked and left unchanged, each with its reason.**
- `**Closed #423 — …**` in `BACKLOG.md`: its outcome sentence ("approval seals that candidate and promotion alone advances the accepted head") is still true and is dated provenance.
- The dated review sections (passes 1–4) of the ledger: they record findings as they stood.
- `docs/implementation-plans/2-roadmap-stack-aware-approval.md` and `plan-seeds/archive/roadmap-stack-aware-approval.replaced.md`: shipped plan records. The plan cites #431 as its source.
- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`: it lists no #431.
- `docs/how-to/roadmap-demo.md`, `docs/reference/commands.md`, `RUNBOOK.md`: a search found no approve or block statement.
- `docs/cli/roadmap.md`: generated by step 5, never hand-edited.
- `BACKLOG.md` #428 and #429: the plan's "Out of scope" leaves them alone.

**Ledger rules.**
- **History versus current state.** The pass sections stay as dated history. Only the four current-state sections change.
- **Retirement note.** Add one dated line near the top: the interim refusal of a batch under a structural candidate (`ae3fb0bc`) was superseded by `roadmap-stack-aware-approval`, and passes 2–4 record it as it stood.
- **Settled decisions.** Replace the "One active structural decision" bullet with the stack-aware rule. Update the "Approval binds one reviewed candidate" bullet, because approve is now confirmed and covers the stack.
- **Open owner directions.** Keep the heading. The stack and confirm directions are shipped, so keep only a short don't-reopen record dated 2026-09-24: the block goes, the whole stack is presented, approve is confirmed in a separate step, and there is no separate show command. Delete the "Current state, verified in the code" bullets. The wider run-log direction stays open and stays listed.
- **Convergence status.** Change "the two open owner directions above" to the one that remains. State the fact that this plan's logic commits post-date the closure. Do not declare the window reopened or closed beyond what the ledger's own rule says.
- **No tooling or model names.** Pass 3 finding P3.1 records that the ledger must not name review tooling, model tier, or turn count.

**Constraints that are not free to vary.**
- **Land after the code.** Describe only behavior on disk. If a name or status in this file disagrees with the code, the code wins.
- **Do not rename a heading.** Anchors in other documents and the ledger's cross-references depend on them. Confirm with `git diff` on heading lines.
- **Keep the pinned anchors in `ROADMAP_FORMAT.md`.** Edit inside the marked block only within the two constraints listed under Input.
- **Write forward-looking prose.** Do not describe the former single-command approve or the block in the present tense. Where history earns a place, date it and frame it as past.
- **Say what is empty.** After #431 goes, #430's dependency bullet reads `none.` and does not disappear.

**Changelog fragment.** Use category sections and bullets written for a user of the tool.
- **Bullet 1 (Changed):** approve is two invocations. The first prints the whole stack and a digest and changes nothing. The second, given `--confirm-stack-digest`, seals and promotes only on a match.
- **Bullet 2 (Changed):** `--propose-candidate` stacks under a structural candidate. A structural hop anywhere in a stack needs the confirmed structural approval, and the answered route refuses such a stack.
- **No ticket key.** None exists for this work: #431 is a backlog id, not a ticket key, and the sibling fragments carry none. Do not cite #431, because the entry is deleted.
- **File name.** The slug `roadmap-stack-aware-approval`, as declared.

## Tests

The test-authoring gate does not apply: it keys on `change_type` (`feature` / `refactor`), and this step is `non-code` under a plan that sets `enforce_step_tests`. The step still edits `tests/test_roadmap_feedback_format.py` because that file pins `ROADMAP_FEEDBACK_FORMAT.md`. Cases (approx. 5, in that file):

- `test_ledger_format_distinguishes_proposal_decision_and_promotion` (existing, updated) — the approval pin matches the reworded sentence. The pins that stay true (`stores an inert candidate`, `Approval authorizes, but does not itself publish`, `rejection releases only the active candidate`) stay.
- `test_ledger_format_documents_two_invocation_approval_over_the_whole_unpromoted_stack` — the document names the confirm flag, says the first invocation writes nothing and prints the whole stack, says the digest is recomputed at confirm time and never stored, and says edit and reject take no confirm.
- `test_ledger_format_states_a_new_batch_stacks_on_a_structural_active_candidate` — the document states stacking, so the retired refusal cannot return unstated.
- `test_retired_structural_batch_block_wording_is_absent_from_every_current_state_doc` — parametrized over `ROADMAP_FEEDBACK_FORMAT.md`, `docs/how-to/roadmap.md`, `docs/ARCHITECTURE.md`, the 2026-09-22 handoff, and the ledger's `## Settled decisions` section. It compares whitespace-normalized text, because these documents hard-wrap. Precedent: `retired_risk not in …` in `tests/test_roadmap_format.py`.
  - **What it pins:** the known retired wordings only. It is not a semantic check, and a new spelling of the same claim escapes it. The vocabulary sweep in Implementation is the real check.
- `test_review_ledger_keeps_the_dated_record_of_the_block_it_retired` — the ledger still holds its dated pass 2 section naming `ae3fb0bc`. This pins the carve-out: the absence check must not spread to the dated history.

**Mutation checks.** Reinsert one retired sentence into each scanned document and confirm the absence case for that document goes red. Delete the two-invocation sentence and confirm its presence case goes red. Delete the pass 2 heading and confirm the carve-out case goes red.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_feedback_format.py tests/test_roadmap_format.py tests/test_backlog_ids.py tests/test_backlog_readability.py tests/test_capability_catalog.py tests/test_data_contract.py -q`. All pass. `tests/test_roadmap_format.py` is not edited, so a red case there means an edit broke a pinned anchor or phrase.
2. Run `rg -n "blocks another|the block continues|ends the block|continues the block|refuses while a structural|structural batch block|batch block" ROADMAP_FEEDBACK_FORMAT.md docs/how-to/roadmap.md docs/ARCHITECTURE.md README.md CAPABILITIES.md ROADMAP_FORMAT.md DATA_CONTRACT.md handoffs/2026-09-22-roadmap-feedback-revision-approval.md BACKLOG.md`. No match.
3. Run the same `rg` over the ledger. A match is allowed only inside a `## Review pass` section or the dated retirement note.
4. Run `rg -n "#431" BACKLOG.md`. No match. Outside `BACKLOG.md`, `#431` may remain only in the plan, its detail files, and the archived seed.
5. Run `rg -n "confirm-stack-digest" plan_tool/cli/roadmap_cmd.py docs/cli/roadmap.md`. The spelling equals the one in every edited document and in the changelog fragment.
6. Run `rg` for every code symbol a document cites (`source_ancestry_to_root`, and the landed stack-route, view, and builder names) in `plan_tool/`. Each exists.
7. Run `git diff -U0` over the edited documents and filter lines starting with `#`. No heading text changes.
8. Open `BACKLOG.md` around #430. It keeps every field, `**Dependencies:** none.` is present, and the Out of scope list reads grammatically.
9. Check the changelog fragment: only the categories in `changelog.d/README.md`, written for a user, no ticket key, ending with a newline.
10. Run `git status --short`. Only the twelve declared files appear.

## Acceptance criteria

- No current-state document among those listed under Files states that an active structural candidate blocks a new `--propose-candidate`. Check 2 returns nothing and the parametrized absence test passes.
- `ROADMAP_FEEDBACK_FORMAT.md`, `docs/how-to/roadmap.md`, and the review ledger's Settled decisions describe approve as two invocations, name the confirm flag as it is spelled in the parser, and state that an approval covers every unpromoted hop beneath the top.
- `DATA_CONTRACT.md` states that no stack or digest field is persisted. It states that the seed-state member is journaled when any hop above the recorded root has a stored structural route.
- `docs/how-to/roadmap.md` states the three deliberate omissions with their reasons. It states that an unconfirmed approve is the read-only view.
- `tests/test_roadmap_feedback_format.py` passes, and its approval pin matches the reworded sentence.
- `tests/test_roadmap_format.py`, `tests/test_backlog_ids.py`, `tests/test_backlog_readability.py`, `tests/test_capability_catalog.py`, and `tests/test_data_contract.py` pass.
- `BACKLOG.md` has no entry #431. Entry #430 names no block, and `**Dependencies:** none.` is explicit. No follow-up entry is filed for any item in [Deferred](#deferred).
- The ledger keeps its `## Open owner directions` heading, lists the run-log direction as still open, and records the stack directions as shipped and dated 2026-09-24.
- `changelog.d/roadmap-stack-aware-approval.md` exists and states both user-visible changes.
- `git diff --name-only` lists only the twelve declared files.

## References

- [`docs/implementation-plans/2-roadmap-stack-aware-approval.md`](../../2-roadmap-stack-aware-approval.md) — "Scope guardrails", step 8's acceptance criteria, and the owner sign-off the documents restate.
- [`handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md`](../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — P2.1, the interim block, and the owner directions this step records as shipped.
- [`ROADMAP_FEEDBACK_FORMAT.md`](../../../../ROADMAP_FEEDBACK_FORMAT.md) — the lifecycle vocabulary and the batch stacking rule.
- [`docs/how-to/roadmap.md`](../../../how-to/roadmap.md) — § 6, the operator procedure.
- [`plan_tool/roadmap_candidate_run.py`](../../../../plan_tool/roadmap_candidate_run.py) — the stack-route derivation and batch sourcing.
- [`plan_tool/roadmap_candidate_review.py`](../../../../plan_tool/roadmap_candidate_review.py) — the structural decision, the stack view, and the digest.
- [`plan_tool/cli/roadmap_cmd.py`](../../../../plan_tool/cli/roadmap_cmd.py) — the confirm flag, result lines, and exit statuses.
- [`changelog.d/README.md`](../../../../changelog.d/README.md) — fragment name and format.

## Applicable guardrails

- **The plan's "Scope guardrails", binary observable and mechanism.** The documents describe the seal as constructed only by the confirmed approve. They must not describe a stored digest, a persisted stack, or a second approval per hop.
- **The plan's "Scope guardrails", "Not allowed".**
  - No persisted stack or binding field: `DATA_CONTRACT.md` must state the absence, not leave it to be inferred.
  - The separate show command, the confirm step for edit or reject, and stack output on the answered route and standalone reject and discard are not built. The documents say so and never present them as planned. No `BACKLOG.md` entry is filed for them.
  - Any change to the promotion writer, the publication journal, or recovery: the documents describe only the structural predicate becoming stack-aware.
- **The plan's "Scope guardrails", ordering fence.** This step runs after the block's removal (step 7). The documents describe the end state and never an intermediate one.
- **The plan's "Out of scope".** The run-log coverage direction stays open in the ledger. `BACKLOG.md` #428 and #429 stay untouched. A seal left by the earlier single-command approve stays promotable and is not migrated.
- **The plan's "Acceptance criteria", backlog and changelog items.** #431 is deleted, every other entry naming the block is reworded, and the fragment states the two changes.
- **The plan's "Deferred".** The plan defers nothing, so this step files no follow-up entry.

## Deferred

- **Regenerating `docs/cli/roadmap.md`** — step 5 owns it. It is generated from the parser and is not hand-edited.
- **Rewriting the ledger's dated review passes 1–4** — they record findings as they stood. Only the four current-state sections change.
- **A read-only show command** — refused by the plan, not deferred. An unconfirmed approve is the read-only view (owner decision, 2026-09-24). No `BACKLOG.md` entry is filed.
- **A confirm step for edit or reject, including reject of a multi-hop stack** — refused by the plan. No `BACKLOG.md` entry is filed.
- **Stack output on the answered route's review, answer, and promote output, and on standalone `--reject-candidate` / `--discard-candidate`** — refused by the plan. No `BACKLOG.md` entry is filed.
- **Run-log lifecycles for the decision commands** — the owner's separate aim, tracked in the ledger's open directions. This step keeps it listed and does not scope it.
- **Editing `docs/implementation-plans/2-roadmap-stack-aware-approval.md` or its status** — the plan tool owns plan status. This step edits no plan file.
- **`BACKLOG.md` #428 and #429** — outside the plan's scope.
