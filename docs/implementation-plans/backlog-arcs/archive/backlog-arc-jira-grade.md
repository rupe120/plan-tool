# Jira developer-handoff backlog arc

## File intent

Historical record of the Jira developer-handoff companion arc (#293),
**delivered 2026-08-22** as the `jira-developer-handoff-companion` plan (7
steps, all done). Kept so a future reader does not re-litigate the
terminal-output contract's settled decisions; the shipped contract itself is
documented in `JIRA_FORMAT.md`'s "Developer-handoff companion" section and
`docs/cli/jira.md`, not here.

## Details

It records #293's terminal-output contract, its same-invocation snapshot and
provenance requirements, and the distinction between legacy Jira-grade detail
and generated developer-handoff source files.

## Choose this arc when

This arc is complete — there is nothing left to choose here. #293 shipped
2026-08-22; see `BACKLOG.md`'s Now/Next board for the current pick.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool work
uses committed green-step checkpoints; direct changes include their regression
coverage and backlog retirement in one bounded commit.
Do not push automatically; push only when the user explicitly requests it.

## Ordered route

**Delivered 2026-08-22:**

- **#293** — `jira-developer-handoff-companion` plan (7 steps, all done).
  `plan-tool jira --developer-handoff` captures one input snapshot and renders
  the story set plus a paired developer-handoff Markdown companion from it;
  the companion covers every committed plan step in dependency order and
  explains the implementation plan's route as suggested guidance. The
  story-only export is unchanged when the mode is absent. Companion mode
  regenerates both source files from current inputs on every invocation, keeps
  them outside the legacy Jira-grade path, preserves an
  existing `jira_issue_key` only through a one-to-one parseable,
  source-plan-identified canonical covered-step mapping, and defaults the
  companion destination to `jira-handoffs/<slug>/`, outside every plan-detail
  bundle and every upstream detail, review, and reconciliation input. Full
  contract: `JIRA_FORMAT.md`'s "Developer-handoff companion" section and
  `docs/cli/jira.md`. Tests: `tests/test_jira.py`, `tests/test_jira_handoff.py`,
  `tests/cli/test_jira_cmds.py`.

1. This arc is complete. There is no next stage — see `BACKLOG.md`'s Now/Next
   board for the current pick.

## Direction and history

**Updated 2026-08-24:** `detail --grade jira` no longer authors Jira-grade
detail. Existing Jira-grade files remain legacy inputs: `jira --grade jira`
continues to consume a complete validated bundle and refuses a run-grade
fallback. The later reader/artifact-removal decision is tracked in BACKLOG #308.

**Cut 2026-08-21:** #169–#171's probe, quality-ledger, materiality, and
canonical-inversion route does not continue. It would ask a thinner Jira-grade
artifact to carry implementation-planning confidence before a grounded
implementation route exists.

**Delivered 2026-08-22:** #293 shipped the separately planned output mode,
same-snapshot rendering, provenance tests, current-source regeneration,
plan-driven structure, and the boundary between structural fidelity and
suggested mechanism. The developer handoff remains terminal output; it does not
become a detail artifact or an audit input.

## Decision gates

These are the constraints the shipped contract enforces — see
`JIRA_FORMAT.md`'s "Developer-handoff companion" section for the authoritative,
current description; kept here as the decision record.

- The implementation plan fixes complete step coverage and dependency order.
  Generated Jira-grade prose follows and explains that path, but cannot turn a
  suggested route into a requirement.
- Present Scope guardrails and Expected placement remain visible implementation
  constraints in the companion; Audit guardrails remain audit-only. Those
  constraints prevail over a suggested route without prose-conflict classification
  or companion-publication refusal.
- Story and companion output derive from exactly one captured source snapshot,
  including both normalized generated destinations. Predecessor companion
  provenance validates pair ownership but does not enter the new render fingerprint.
- Any existing keyed story source proves it belongs to the selected plan before
  its `jira_issue_key` is carried forward; an unproven legacy source refuses
  companion publication.
- The captured story-source state follows the current handoff semantics: a keyed
  `draft` becomes `created`, `created` remains created, and `dropped` stays
  historical in the story source rather than returning to the current companion
  path. A dropped record naming a current step or keyless `created` record refuses;
  a changed created record reports its Jira id/key for manual Jira update.
- The generated story and companion files remain the current source handoff and
  are regenerated together on the next companion-mode invocation.
- A generated target is new or a recognizable same-plan generated source; the
  companion refuses every other existing human-owned target, including either
  detail grade, and final ownership confirmation aborts every unstarted write on a
  detected mismatch without claiming to observe an uncoordinated post-check write.
- The handoff visibly preserves each declared dependency edge; the default
  companion path is derived from the normalized story path under
  `jira-handoffs/<slug>/`, outside every plan-detail bundle; the stem removes one
  final suffix after path normalization. An existing companion binds to its exact
  story source and format; a same-stem format switch refuses rather than migrating
  or taking over that companion.
- A generated companion remains terminal: it is excluded from audit and
  reconciliation grounding and cannot overwrite legacy Jira-grade detail.

## Exit and handoff

The arc ended with a provenance-stamped handoff whose plan-driven structure
lets a developer understand the work and choose a sound mechanism that
fulfills each step's spirit and outcome.

## Out of scope

This arc does not alter grade defaults, create a probe or convergence classifier,
make terminal output audit evidence, or absorb deterministic Jira sweep work.
