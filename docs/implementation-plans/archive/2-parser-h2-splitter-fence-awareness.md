> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Parser H2 Splitter Fence Awareness
intent: '`plan_tool/parser.py`''s H2 section splitter (`parse_body_sections`, `split_body_sections`,
  `replace_body_sections`) no longer mistakes a line inside a fenced code block for
  a real section heading, at every one of its consumers — including `review.py`''s
  completeness-audit/reconcile engine, which reads a plan''s `## Out of scope`/`##
  Acceptance criteria`/etc. through exactly this splitter. Closes `BUG_BACKLOG.md`''s
  "`parser.py`''s canonical plan-body H2 splitter has no fence-awareness" entry and
  its related "unclosed fence spans to end-of-text" RISK entry, both filed 2026-09-02;
  the plan updates or removes those entries when the work ships.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
enforce_step_tests: true
source_seed: plan-seeds/parser-h2-splitter-fence-awareness.md
steps:
- id: 1
  title: Add opt-in fence-safe H2 parsing, detect unmatched opening fences, and limit
    section replacement to real headings
  intent: Give every H2 consumer one shared way to ignore fenced pseudo-headings and
    reject an unmatched opening fence while leaving the default parser behavior unchanged
    until a consumer explicitly opts in.
  files:
  - plan_tool/parser.py
  - plan_tool/scope_fence.py
  - tests/test_parser.py
  - tests/test_scope_fence.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/parser-h2-splitter-fence-awareness/01-opt-fence-safe-h2-parsing-detect.md
  status: done
- id: 2
  title: Use fence-safe H2 parsing in every read consumer and strip examples only
    for matching
  intent: Keep completeness, reconcile, concept, grounding, handoff, and inspection
    reads faithful to the real H2 outline.
  files:
  - plan_tool/review.py
  - plan_tool/create.py
  - plan_tool/detail.py
  - plan_tool/grounding.py
  - plan_tool/jira_handoff.py
  - plan_tool/cli/inspect.py
  - plan_tool/cli/scope_review_cmd.py
  - tests/test_review.py
  - tests/test_create.py
  - tests/test_detail.py
  - tests/test_grounding.py
  - tests/test_jira_handoff.py
  - tests/cli/test_inspect_cmds.py
  - tests/cli/test_scope_review_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the explicit boundary-only and content-stripping modes plus the unmatched-opening
      signal.
  detail: docs/implementation-plans/plan-details/parser-h2-splitter-fence-awareness/02-use-fence-safe-h2-parsing-every-read.md
  status: done
- id: 3
  title: Reject an unmatched opening fence before a parser-driven annotate, create,
    detail, reprocess, scope-out, run, roadmap, or run-grade Jira paired-export write,
    or completeness/reconcile report write, leaving targets and existing archive,
    cleanup, and rollback behavior unchanged
  intent: Prevent an H2 reader from silently losing every section after an unmatched
    opening fence and then using that truncated result to produce or modify a target.
  files:
  - plan_tool/annotate_render.py
  - plan_tool/cli/app.py
  - plan_tool/cli/annotate_cmd.py
  - plan_tool/cli/authoring.py
  - plan_tool/cli/run_cmd.py
  - plan_tool/create.py
  - plan_tool/detail.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/jira.py
  - plan_tool/jira_handoff.py
  - plan_tool/cli/jira_cmd.py
  - plan_tool/launcher.py
  - plan_tool/reprocess.py
  - plan_tool/renderer.py
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap.py
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - plan_tool/scope_out.py
  - ROADMAP_FORMAT.md
  - tests/test_create.py
  - tests/test_annotate_render.py
  - tests/test_detail.py
  - tests/test_jira.py
  - tests/test_jira_handoff.py
  - tests/test_reprocess.py
  - tests/test_review.py
  - tests/test_review_persistence.py
  - tests/test_scope_out.py
  - tests/test_launcher.py
  - tests/test_renderer.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap.py
  - tests/test_roadmap_format.py
  - tests/cli/test_annotate_cmd.py
  - tests/cli/test_app.py
  - tests/cli/test_authoring_cmds.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_jira_cmds.py
  - tests/cli/test_review_cmds.py
  - tests/cli/test_run_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Supplies the shared unmatched-opening signal used by existing scope-fence readers.
    2: Ensures parser-based readers use the same unmatched-opening contract before
      the owner-specific error handling is verified.
  detail: docs/implementation-plans/plan-details/parser-h2-splitter-fence-awareness/03-reject-unmatched-opening-fence-before.md
  status: done
- id: 4
  title: Make concept sync compare and replace only real headings, preserve atomic
    plan and sidecar overwrite and rollback, and leave both files unchanged on fence
    errors
  intent: Keep concept decisions from replacing fenced examples or corrupting adjacent
    plan content during synchronization.
  files:
  - plan_tool/concept_sync.py
  - tests/test_concept_sync.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides fence-safe parsing and replacement boundaries for the concept-sync
      write path.
  detail: docs/implementation-plans/plan-details/parser-h2-splitter-fence-awareness/04-make-concept-sync-compare-replace-only.md
  status: done
- id: 5
  title: Close the parser fence bug and unmatched-opening risk while keeping the default-off
    item open
  intent: Keep the recorded defect and deferred default-change status aligned with
    the behavior that ships.
  files:
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  depends_on_notes:
    2: Completes the parser consumer sweep.
    3: Establishes the tested unmatched-opening failure behavior.
    4: Closes the destructive concept-sync replacement case.
  detail: docs/implementation-plans/plan-details/parser-h2-splitter-fence-awareness/05-close-parser-fence-bug-unmatched.md
  status: done
---
# Parser H2 Splitter Fence Awareness

## Overview

`parser.py`'s splitter is the most heavily consumed H2-section splitter in
the codebase — more so than `scope_fence.extract_h2_sections`, which a prior
sweep (commits `395e2d07`, `4c8bb270`) already made fence-aware across its
own, smaller consumer set. `parser.py`'s functions were never touched by that
work and have no fence-awareness at all, not even the boundary-only
protection `scope_fence.py`'s `ignore_fenced_code` gives its callers.

## Problem statement

`parser.py:parse_body_sections`'s heading regex (`h2_re`/`higher_re`) matches
any line starting with `##`/`#`, wherever it appears — including inside a
fenced code block. A plan whose real `## Out of scope`, `## Acceptance
criteria`, or other section legitimately quotes a markdown or command example
containing its own `##`-prefixed line (e.g. showing another plan's section,
or example CLI output) has its real section content silently truncated, or —
because `split_body_sections`' dict comprehension keeps the *last*
same-named section rather than the first — silently replaced by the fenced,
fake one if the fake occurrence happens to come after the real one.
Reproduced directly against `split_body_sections` in `BUG_BACKLOG.md`'s
entry. This corrupts what `review.py`'s completeness-audit and plan-vs-code
reconcile engine reads when judging a plan, and what `concept_sync.py`'s
`replace_body_sections` overwrites when syncing concept-driven scope
decisions back into a plan file.

## Architecture

`parser.py` gains the fence-detection primitive from `scope_fence.py` rather
than a third independent implementation. Left open, for `create`/`detail` to
resolve during authoring: whether `parser.py`'s splitter should consolidate
onto `scope_fence.extract_h2_sections` outright, or keep its own function
shapes while sharing only the fence-span primitive. The two splitters are
*not* provably identical today — `parser.py`'s dedup keeps the last
same-named section, `scope_fence.py`'s keeps the first, and their title
normalization differs (`parser.py` strips trailing `:`/`.`;
`scope_fence.py` strips an optional ATX closing sequence) — so a merge is a
decision this seed does not make, not a default; compare their behavior
before choosing, per this repo's own duplication-consolidation bar
(`CLAUDE.md` § "Authoring hygiene and anti-creep" — evidence, not
resemblance).

The shared parser keeps `scope_fence.py`'s existing supported fence grammar:
an opening line has at most three leading spaces followed by at least three
backticks or tildes; a closing line has at most three leading spaces, the
same marker, at least the opening marker's length, and no trailing content
other than whitespace. An opening fence with no such closing line before EOF
is an **unmatched opening fence** and is the only fence-shape failure this
plan rejects. A different marker, a shorter same-marker run, or trailing
content on a possible closer remains code and does not fail independently; a
later valid closer still closes the fence.

`plan_tool/jira_grade.py` still has an artifact-specific fence-aware H2 scanner
and unterminated-fence validator, reached by
`plan_tool/review.py:check_jira_grade_bundle`. That legacy Jira-grade detail
lane is scheduled for retirement by `BACKLOG.md` #308. It is not a plan/seed-
body reader; this plan neither reuses nor preserves it.

The unmatched-opening refusal applies only where an action reads a plan or
seed H2 body through the parser/scope-fence path and then produces or changes
its target: annotate's report/seed, create's plan, detail's detail file,
reprocess's plan, scope-out's plan/seed, run's code or status update,
roadmap's artifact, and the run-grade Jira paired story/developer-handoff
export, plus completeness-audit and reconcile-plan's persisted reports. Each
route refuses before its first published target change. Sources available at a
command boundary are checked before that command writes preferences or opens a
run log; create or roadmap content assembled after model work is checked
immediately before materialization, while its already-open run log records the
refusal as an operational receipt. Create checks both its input seed and the
assembled body it is about to publish; completeness and reconcile check both
the plan body and the resolved `source_seed`, including its archive fallback.
Run-grade Jira publication leaves both output targets unchanged, while
`--no-write` remains a pure preview. Audit/reconcile do not invoke a model or
save a report. Step 4 owns concept-sync's separate in-place plan/sidecar
replacement. A command that changes only frontmatter or status without
interpreting the H2 body does not need this refusal: it cannot lose body
sections through this bug.
`origin/main` has diverged from this branch's local `main` (measured
2026-09-02: 28 commits ahead here, 15 ahead there, unreconciled — check
`git rev-list --left-right --count main...origin/main` for the current
count rather than trusting this snapshot) and separately hardens
audit-finding fence parsing there. Reconciling that unmerged work is
explicitly not this plan's job; handle it when the branch divergence is
resolved rather than anticipating it here.

## References

- [CommonMark Spec — Fenced code blockshttps: — Defines fence delimiters, matching closure rules, embedded content handling, and the specified end-of-document behavior for unclosed fences.
- [CommonMark Spec — ATX headingshttps: — Defines the Markdown heading syntax the splitter must recognize only outside fenced code blocks.
- [Python 3.13 documentation — re: Regular expression operationshttps: — Documents multiline anchors, compiled patterns, match spans, and other APIs used to implement line-oriented heading detection.
- [pytest documentation — How to parametrize fixtures and test functionshttps: — Covers parametrized regression tests suitable for replaying fenced-heading cases across every splitter consumer.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Allowed behavior changes:** (1) content a fenced pseudo-heading
  previously corrupted or silently swapped is now parsed correctly, at every
  swept consumer; (2) an unmatched opening fence in author-facing text makes
  each listed parser/scope-fence-driven write refuse before its first target
  change, instead of silently losing all later sections. Nothing else
  user-visible changes.
- **Allowed reorganization:** none, unless the consolidation-vs-shared-
  primitive decision in Architecture requires moving code — then only the
  minimal move that decision needs.
- Flipping `scope_fence.extract_h2_sections`'s `ignore_fenced_code`/
  `strip_fenced_code` parameters to default on — `BUG_BACKLOG.md`'s
  "defaults to off" MINOR entry stays open, deferred until this ships and
  its prerequisite is satisfied.
- `validate_draft_seed_content`'s redundant double frontmatter parse
  (`BUG_BACKLOG.md`'s other MINOR entry) — unrelated, separately filed.
- `detail.py:parse_detail_file_sections` — a deliberate, already-documented
  carve-out (a detail file's fixed seven-section schema, not the flexible
  plan-body outline `parser.py` splits); do not fold it into this fix.
- The retiring legacy Jira-grade detail scanner and unterminated-fence validator
  in `plan_tool/jira_grade.py`, reached through
  `review.py:check_jira_grade_bundle` — #308 removes that lane. Do not
  preserve, adapt, consolidate, or test it in this parser plan.
- Any other heading-regex implementation that parses a *different* document
  shape than a plan/seed's own H2 body (pending-lessons sections in
  `lessons.py`, a step's completion summary in `launcher.py`, a declared
  response contract in `response_contract.py`, sidecar sections in
  `data_contract.py`, docs sections in `capability_catalog.py`) — different
  formats and threat models, out of scope here.

## Risks

- A blanket fence-awareness change to the single most-consumed splitter
  could silently alter behavior across 8+ modules, one of which
  (`concept_sync.py`'s `replace_body_sections`) mutates a plan file in
  place. Apply the fix opt-in and per-consumer, the same way the sibling
  `scope_fence.py` sweep was, rather than as a bare default flip.
- Some existing tests likely assert today's non-fence-aware boundary
  behavior as their baseline and need auditing and updating rather than
  blind preservation — the sibling fix's mutation-testing already
  demonstrated this is necessary, not hypothetical.
- This branch's diverged history means a later merge with `origin/main`
  could bring in that branch's own, independently built fence-detection
  work (see Architecture). This plan should not anticipate or design
  against that unmerged code — doing so would be designing against a
  moving target — but the eventual merge will likely need to reconcile two
  parallel fence-hardening efforts; note this for whoever drives that
  merge rather than solving it now.

## Testing

A parameterized replay proves the fenced-pseudo-heading corruption no longer
reproduces at every swept call site, using the reproduction already recorded
in `BUG_BACKLOG.md` as its base case. A dedicated test proves
`replace_body_sections`'s in-place mutation is not corrupted or does not
drop real content adjacent to a fenced pseudo-heading. Per-route tests prove
that each listed parser/scope-fence-driven write refuses an unmatched opening
fence before its first target change, while valid later closers and
nonclosing marker-like lines do not reject it. The Jira export test preserves
both the story and developer-handoff targets on refusal; completeness-audit
and reconcile-plan do not call a model or save a report. A concept-sync test
proves an unmatched opening fence leaves both its plan and sidecar unchanged.
The parser's default path still recognizes a fenced pseudo-heading exactly as
before; only an explicit fence-safe mode changes that behavior.
Full suite green.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- No consumer of `parser.py`'s H2 splitter misidentifies a line inside a
  fenced code block as a real section-boundary heading.
- Every enumerated call site has an explicit, verified choice between
  boundary-safety-only and content-stripping semantics, matching whether it
  renders/preserves vs. pattern-matches the extracted body.
- The parser's default path remains unchanged: a fenced pseudo-heading affects
  it exactly as before this plan, while only an explicit fence-safe mode
  ignores it.
- A supported opening fence with no valid same-marker closer before EOF makes
  every listed parser/scope-fence-driven plan/seed or run-grade Jira paired-
  export write refuse before its first target change instead of silently
  dropping every later section; a different marker, a shorter marker run, or
  trailing content on a potential closer does not fail independently.
- Concept sync rejects an unmatched opening fence before changing either the
  plan or its sidecar, preserving its existing rollback guarantee.
- `BUG_BACKLOG.md`'s "`parser.py`'s canonical plan-body H2 splitter has no
  fence-awareness" entry and its related "unclosed fence spans to
  end-of-text" RISK entry are removed; the "`ignore_fenced_code`/
  `strip_fenced_code` default" MINOR entry remains, updated to note its
  prerequisite has shipped.

## Deferred

- Flipping `extract_h2_sections`'s fence-awareness parameters to default on,
  now that this plan's prerequisite work exists (`BUG_BACKLOG.md`, remains
  open).
- Any further consolidation of `parser.py`'s and `scope_fence.py`'s
  splitters beyond what this plan's Architecture decision requires, if
  `create`/`detail` decide against a full merge.
