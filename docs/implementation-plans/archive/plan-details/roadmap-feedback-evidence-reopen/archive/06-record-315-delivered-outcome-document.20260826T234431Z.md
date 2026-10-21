# Step 6 — Record #315's delivered outcome and document the recovery boundary for #242

## Summary

Document the delivered evidence-blocked feedback recovery workflow across `RUNBOOK.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `docs/ARCHITECTURE.md`. Retire the stale “no reopen mechanism” backlog and bug-record claims, while preserving the incident and recording #315 as a bounded input to #242’s future retention redesign. Keep `docs/cli/roadmap.md` and the landed `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` surface as the command-syntax source of truth. On green, operators have one safe recovery sequence, #315 is recorded as resolved, and #242 remains paused and separate.

## Table of Contents

- [Summary](#summary) — The completed documentation and tracking outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The stale guidance this step removes.
- [Input](#input) — The landed command and recovery contracts this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six documentation and tracking files to update.
- [Implementation](#implementation) — The recovery narrative, status sweep, and #242 boundary.
- [Tests](#tests) — Non-code verification of documentation accuracy and existing contract tests.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and tracking results.
- [References](#references) — Command-surface reference material.
- [Applicable guardrails](#applicable-guardrails) — Scope limits on the documented workflow.
- [Deferred](#deferred) — Broader retention and command-catalog work outside this step.

## Why

`BACKLOG.md` #315, the linked `BUG_BACKLOG.md` incident, and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` describe a response-bearing feedback row as permanently blocked and requiring a raw edit. Once step 5 provides the guarded operator workflow, that advice directs users around the history, confirmation, and recovery protections the feature exists to enforce. #242 needs the delivered recovery contract as design input, but it must not treat that narrow path as completion of its broader retention work.

## Input

- **Step 5 command contract:** Read the landed forms, exclusivity rules, confirmations, terminal outcomes, and redaction guarantees from `docs/cli/roadmap.md:## Usage`, `docs/cli/roadmap.md:## Options`, and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()`. Their final spellings win over this detail.

- **Step 4 publication and recovery contract:** Use the landed recovery result semantics and exact-event boundary from step 4. `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, `recover_roadmap_publication()`, and `plan_tool/run_log.py:RunLogWriter.run_end()` remain the relevant publication and terminal-event anchors.

- **Existing operator guidance:** Preserve ordinary feedback guidance in `RUNBOOK.md:### Redirecting a proposal with feedback` and `docs/ROADMAP_WALKTHROUGH.md:## 5. Ask for a revision with feedback`. The new route is an exception for admitted evidence-blocked responses, not a replacement for normal reviewer edits or stage re-entry.

- **Future retention boundary:** Read the active #242 record in `BACKLOG.md` and ordered-route item 3 in `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`. Keep their pause and redesign gate intact while naming the delivered #315 contract as input.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `RUNBOOK.md` — Add the bounded evidence-blocked response recovery sequence beside `### Redirecting a proposal with feedback`; correct the blanket editor-only reopen wording; explain terminal-event recovery without exposing sensitive content.
  - `docs/ROADMAP_WALKTHROUGH.md` — Add the recovery forms to `## Command sequence at a glance` and a clearly alternative branch in `## 5. Ask for a revision with feedback`.
  - `docs/ARCHITECTURE.md` — Extend `### Immutable roadmap evidence` with the retirement, reopen admission, guarded publication, terminal-event recovery, CLI, and read-only review-view ownership boundaries.
  - `BACKLOG.md` — Replace #315’s pending proposal with a concise resolved record and update #242’s status text to name the delivered recovery contract as a separate input.
  - `BUG_BACKLOG.md` — Retain the version-1 evidence incident and archive disposition, but remove its stale claim that no supported reopen mechanism exists.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Record #315 as delivered in `## Real-world evidence source` and `## Ordered route`, while preserving #242’s separate pause and next gate.

## Implementation

- **Make the documentation-status sweep the foundational logic.** Before editing, search the six scoped files by identifier (`#315`, `#242`) and by vocabulary (`no reopen mechanism`, `raw hand-edit`, `reopen path`). Replace every statement that says evidence-blocked feedback has no supported route; retain ordinary manual feedback behavior where it remains true.

- **Use the landed CLI reference as the sole flag authority.** Copy final command forms from `docs/cli/roadmap.md:## Usage` after step 5 completes. The runbook and walkthrough may show the bounded forms, including `--record-retired-evidence`, `--import-retired-evidence`, `--reopen-feedback`, and `--recover-reopen`, but they must not invent aliases, defaults, or companion flags.

- **Document one ordered recovery path.** In `RUNBOOK.md:### Redirecting a proposal with feedback`, explain that an `awaiting-review` response blocked by the supported evidence classifications first needs the applicable retirement record or documented archive import, then an explicit controlled reopen, then a normal run of the row’s owning stage. Make the command forms alternatives, not a script every operator runs.

- **Keep terminal-event recovery separate from reopening.** Document that `--recover-reopen ATTEMPT_ID` applies only to the matching recorded recovery attempt after its terminal log write is pending. It must not be described as a second reopen, an evidence repair, an artifact republish, or a replacement for `--from-stage`.

- **Preserve ordinary reviewer ownership.** Update the editor-action table in `RUNBOOK.md:### Redirecting a proposal with feedback` and the local-revision explanation in `docs/ROADMAP_WALKTHROUGH.md:## 5. Ask for a revision with feedback` so routine close, defer, and ordinary reopen actions remain reviewer decisions. State the evidence-blocked reopen command as a narrow, guarded exception rather than a general feedback editor.

- **Keep broad work unavailable.** In `docs/ROADMAP_WALKTHROUGH.md:Record structural feedback, then analyze its current route`, retain the boundary that `--from-stage N` does not provide feedback-free regeneration or broad recovery. The new route changes eligibility for one admitted row; it does not authorize a structural rewrite, a cross-artifact transaction, or ordinary re-escalation.

- **Document ownership, not implementation detail.** Extend `docs/ARCHITECTURE.md:### Immutable roadmap evidence` to distinguish immutable retirement evidence from active evidence storage, reopen admission from publication, and exact terminal-event recovery from artifact recovery. Name `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()`, `plan_tool/run_log.py:RunLogWriter.run_end()`, and `plan_tool/roadmap_view.py:render_decision_ledger()` where they explain a boundary; use the landed step-2 through step-4 public names rather than names proposed in earlier details.

- **Keep review output redacted and read-only.** State that review mode can show only the persisted safe recovery facts supplied by `plan_tool/roadmap_view.py:render_decision_ledger()`. Do not document prior response text, evidence bytes, attestation prose, arbitrary log inspection, or a command that exposes them.

- **Close #315 without erasing its useful provenance.** Replace `BACKLOG.md` #315’s proposal fields with a dated resolved outcome that identifies the bounded recovery contract, preserved ordinary eligibility rule, audit trail, operator confirmations, and focused verification. Remove future-tense implementation scope and the suggestion that #315 might be folded into #242.

- **Keep #242 independent.** Update the #242 status in `BACKLOG.md` and ordered-route item 3 in `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` to name the delivered `roadmap-feedback-evidence-reopen` contract as an input to its next redesign. Do not call it “step 6,” imply #242 has started, or weaken its existing evidence and audit gates.

- **Correct the bug record without rewriting the incident.** In `BUG_BACKLOG.md:Version-1 roadmap evidence receipts appeared through the CLI escalation path after the schema lock landed`, retain the evidence-schema failure and archived disposition. Replace only the obsolete “no reopen mechanism” consequence with a pointer to the supported bounded recovery route and its limits.

## Tests

Step 6 is `non-code`, so the test-authoring gate does not apply. It changes no production behavior or test file.

### Verification (non-code step)

1. `tests/test_roadmap_format.py::test_stage_feedback_route_guidance_sweep_keeps_active_feedback_and_feedback_free_regate_distinct` — Passes after the guide edits, proving existing stage-selection language remains aligned.

2. `tests/test_roadmap_format.py::test_architecture_reference_assigns_baseline_publication_to_writers_and_admission_to_readers` — Passes after the architecture addition, preserving the writer-versus-reader evidence boundary.

3. `tests/cli/test_roadmap_cmd.py` — Passes against step 5’s landed command forms, confirmations, exclusivity checks, and redacted terminal output before those forms are documented here.

4. **Command-reference check** — Compare every command and outcome shown in `RUNBOOK.md` and `docs/ROADMAP_WALKTHROUGH.md` with `docs/cli/roadmap.md:## Usage` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()`.

5. **Status-vocabulary sweep** — Confirm the scoped files contain no claim that an evidence-blocked response has no reopen mechanism or requires clearing `proposed_response` by raw edit.

6. **Link and rendering check** — Verify new Markdown links resolve, headings retain valid anchors, `git diff --check` passes, and the changed prose contains no raw response text, evidence bytes, or attestation prose.

## Acceptance criteria

- `RUNBOOK.md` describes the admitted evidence-blocked recovery route, its separate terminal-event recovery form, and the required follow-up stage run without treating either as broad regeneration.

- `docs/ROADMAP_WALKTHROUGH.md` presents the retirement, import, reopen, recovery, and stage-run forms as bounded alternatives and directs readers to `docs/cli/roadmap.md` for final syntax.

- `docs/ARCHITECTURE.md:### Immutable roadmap evidence` assigns retirement evidence, admission, guarded publication, terminal-event recovery, CLI dispatch, and redacted review rendering to distinct owners.

- `BACKLOG.md` records #315 as resolved with its delivered behavior and verification, and its #242 entry keeps retention paused while naming the delivered recovery contract as a separate design input.

- `BUG_BACKLOG.md` retains the version-1 incident but no longer claims that a supported reopen mechanism is absent.

- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` records #315 as delivered and preserves the explicit gate before #242’s redesign.

- The documentation does not promise a general feedback editor, ordinary re-escalation, evidence mutation, artifact republishing during terminal recovery, or exposure of response and evidence contents.

- The listed verification checks and `uv run pytest tests/test_roadmap_format.py tests/cli/test_roadmap_cmd.py -q` pass.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use when checking that documented command forms match the parser’s option and exclusivity model.

## Applicable guardrails

- **The plan’s “## Plan intent”, supported recovery with preserved protections** — Document only the bounded recovery path and make clear that ordinary already-responded behavior remains protected.

- **The plan’s “## Step intent”, #315 outcome and #242 boundary** — Record the delivered behavior and its future design relevance without expanding this documentation step into retention work.

- **The plan’s “## Out of scope”, no general feedback editor** — Do not describe the CLI as arbitrary feedback mutation or raw-response replacement.

- **The plan’s “## Out of scope”, no ordinary re-escalation** — Do not present recovery as a general route for responses outside the evidence classifications the plan names.

## Deferred

- Roadmap revision retention #242 — Keep its closed-feedback retention, removal history, and redesign decisions separate until its documented gates permit a new plan and audit.

- `docs/cli/roadmap.md` command-catalog changes — Step 5 owns the final parser help and option reference; this step consumes that landed contract rather than reopening its CLI design.
