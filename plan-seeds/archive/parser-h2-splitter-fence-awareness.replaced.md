> **Replaced**: this file has been superseded by `docs/implementation-plans/2-parser-h2-splitter-fence-awareness.md`.
> Preserved here for history; do not edit.

## Outcome

`plan_tool/parser.py`'s H2 section splitter (`parse_body_sections`,
`split_body_sections`, `replace_body_sections`) no longer mistakes a line
inside a fenced code block for a real section heading, at every one of its
consumers — including `review.py`'s completeness-audit/reconcile engine,
which reads a plan's `## Out of scope`/`## Acceptance criteria`/etc. through
exactly this splitter. Closes `BUG_BACKLOG.md`'s "`parser.py`'s canonical
plan-body H2 splitter has no fence-awareness" entry and its related
"unclosed fence spans to end-of-text" RISK entry, both filed 2026-09-02; the
plan updates or removes those entries when the work ships.

## In scope

- Give `parser.py`'s splitting logic the same fence-detection primitive
  `plan_tool/scope_fence.py:_fenced_code_spans` already provides (`parser.py`
  can safely import `scope_fence.py` — stdlib-only, no cycle risk) so a
  fenced pseudo-heading can no longer split a section early or forge one that
  isn't there.
- Classify each of `parser.py`'s current consumers by whether it renders/
  preserves the extracted body verbatim or pattern-matches it against known
  content, and apply the matching semantics per consumer — the same split
  `scope_fence.extract_h2_sections`'s `ignore_fenced_code` (boundary-safety
  only) vs. `strip_fenced_code` (also excises fenced content) already draws,
  landed in commit `4c8bb270`. Enumerate and classify every call site:
  `review.py` (6 sites: 1403, 1796, 2782, 3174, 6456, 7373), `create.py`
  (8466-8468), `detail.py:556`, `grounding.py:224`, `jira_handoff.py:747`,
  `concept_sync.py` (186, 191, 214 — including `replace_body_sections`, which
  mutates a plan body in place rather than only reading it), `cli/inspect.py
  :807`, `cli/scope_review_cmd.py` (71, 146).
- Decide the failure mode for an unclosed/mismatched fence in author-facing
  seed/plan text. Today, once fence-awareness is on, everything after an
  unclosed fence silently vanishes from the result with no signal — this
  "spans to end-of-text" choice shipped with `ignore_fenced_code` itself
  (commit `79c316ee`, whose message records no design rationale), and this
  seed's new author-facing consumers (a plan/seed body a human or model
  wrote) may warrant a different, more visible failure mode than silent
  dropping. Apply the same decision to `scope_fence.py`'s existing
  mechanism, which the prior sweep already extended to author-facing seed
  parsing (`create.py`, `reprocess.py`, `roadmap_gates.py`) without
  addressing this.
- Regression tests proving the fenced-pseudo-heading corruption no longer
  reproduces at every swept call site (mirroring the direct reproduction
  recorded in `BUG_BACKLOG.md`), that `replace_body_sections`'s in-place
  mutation does not corrupt or drop real content adjacent to a fenced
  pseudo-heading, and that the chosen unclosed-fence failure mode actually
  fires.

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

`origin/main` has diverged from this branch's local `main` (measured
2026-09-02: 28 commits ahead here, 15 ahead there, unreconciled — check
`git rev-list --left-right --count main...origin/main` for the current
count rather than trusting this snapshot) and independently hardened a
separate
fence-detection mechanism there (`jira_grade.py`'s citation-fence scanner,
consumed by `review.py`'s audit-finding parsing) — neither that module nor
`plan_tool/review.py`'s corresponding fence-awareness exists on this branch
today. Reconciling that third implementation is explicitly not this plan's
job; it becomes relevant only once the branch divergence is resolved, and
should be handled then rather than anticipated here.

## Out of scope

- **Allowed behavior changes:** (1) content a fenced pseudo-heading
  previously corrupted or silently swapped is now parsed correctly, at every
  swept consumer; (2) an unclosed/mismatched fence in author-facing text
  produces whatever failure mode this plan selects, instead of today's
  silent, total, no-error section loss. Nothing else user-visible changes.
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
- Any heading-regex implementation that parses a *different* document shape
  than a plan/seed's own H2 body (jira-grade detail sections in `jira.py`,
  pending-lessons sections in `lessons.py`, a step's completion summary in
  `launcher.py`, a declared response contract in `response_contract.py`,
  sidecar sections in `data_contract.py`, docs sections in
  `capability_catalog.py`) — different formats and threat models, out of
  scope here.

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
drop real content adjacent to a fenced pseudo-heading. A test proves the
chosen unclosed-fence failure mode actually fires for author-facing text.
Full suite green.

## Acceptance criteria

- No consumer of `parser.py`'s H2 splitter misidentifies a line inside a
  fenced code block as a real section-boundary heading.
- Every enumerated call site has an explicit, verified choice between
  boundary-safety-only and content-stripping semantics, matching whether it
  renders/preserves vs. pattern-matches the extracted body.
- An unclosed/mismatched fence in author-facing seed/plan text has a defined,
  tested failure mode instead of silently dropping every later section.
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

## References

- `BUG_BACKLOG.md` — "`parser.py`'s canonical plan-body H2 splitter has no
  fence-awareness" (source entry: files, direct reproduction, fix options)
  and the related "unclosed fence spans to end-of-text" RISK entry, both
  filed 2026-09-02.
- `plan_tool/parser.py:parse_body_sections`, `split_body_sections`,
  `replace_body_sections` — the splitter this plan fixes.
- `plan_tool/scope_fence.py:extract_h2_sections`, `_fenced_code_spans`,
  `_excise_fenced_code` — the sibling mechanism and precedent pattern.
- `plan_tool/review.py` — the highest-stakes consumer (completeness-audit /
  plan-vs-code reconcile engine).
- Commit `4c8bb270` — the sibling `scope_fence.py` fix this plan mirrors:
  per-consumer semantics classification, mutation-verified regression tests.
