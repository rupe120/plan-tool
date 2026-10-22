# Plan body newline preservation

| Item | Record |
| --- | --- |
| Base | `75aa0a7e5`, merged PR #142 |
| Branch | `fix/plan-body-newline-preservation` |
| Scope | BUG_BACKLOG “Concept sync and scope-out rollback normalize existing plan body newlines” |
| Route | Bounded direct I/O and heading-boundary correction |
| Current state | Complete: 15,068 tests pass; two consecutive independent clean Claude Code reviews after the final logic change |

## Property and pre-edit sites

Invariant: concept synchronization retains unowned body bytes, and failed narrowing restores the original plan bytes and matching provenance.
Identifier search: synchronize_concepts/source_plan_text identifies concept_sync's current source plus create's two snapshots and scope_review_cmd's snapshot. All require raw UTF-8 reads. Its atomic text publisher must disable newline translation.
Vocabulary search: newline/rollback/source_plan_text in concept_sync, scope_out and scope_review_cmd identifies scope_out's original_plan_text snapshot and restore, plus compute_frontmatter_hash (must hash the same raw frontmatter as parser provenance).
Parser _real_h2_matches and parse_body_sections need CR-aware offsets/boundaries once normalization is removed; preserve unowned slices rather than normalize input.
Excluded: sidecar JSON reads and seed/detail/reference reads do not republish original plan bytes; no change. Scope selection, archive moves and publication ownership remain unchanged.

## Verification

Before the fix, raw-byte regressions produce six failures: four concept-sync
CRLF/CR combinations (with and without source snapshots) and two rollback
cases after real plan publication. LF controls pass. This is a dated
reproduction, 2026-10-22, rather than an inferred universal-newline claim.

The affected module suite passes 1,733 tests, including the actual scope-review
handler, scope-out sidecar-save failure after publication, and both create
snapshot seams. Assertions inspect bytes, owned-section replacement, fences,
concurrent owned/unowned edits, fingerprints, restored details and provenance.

Successful narrowing also retains raw body bytes; a newline-only frontmatter
change invalidates a stale narrowing preview. These four additional cases pass
in the 605-test parser/scope-out run. Final committed full suite: **15,059 passed,
67 skipped** in 60.19s. `git diff --check` passes.

Implementation commits: `c80e96dad` (concept sync and its source snapshots/raw
heading boundaries) and `778fabcdd` (scope-out snapshots, restoration and CAS).

## Claude Code review 1 and dispositions

Range `75aa0a7e5..778fabcdde4dffb78e48f82d305eb896d76abbcf`;
actual built-in `code-review` Skill at high effort, followed by supervising
verification; 48 selected tests pass. Session `5b24ca95-9688-4811-aa2c-38e42bd6fda9`.

- F-1 confirmed: narrowing higher-heading whitespace changes existing empty
  and non-ASCII whitespace boundaries. No existing test contradicts the report.
  Nine new cases fail before correction; restore the original `\s+` semantics
  while retaining raw CR/LF anchors. This is the minimal compatibility fix.
- F-2 confirmed, pre-existing and deferred: H1 content after an owned H2 is
  deleted. Independent probes reproduce for LF/CRLF/CR. BUG_BACKLOG
  “Concept sync deletes an unowned H1 after an owned H2” owns the follow-up.
- F-3 confirmed, pre-existing and deferred: an injected concurrent priority
  edit triggers ConcurrentModificationError but unconditional rollback overwrites
  it. BUG_BACKLOG “Scope-out rollback overwrites the concurrent edit rejected by
  provenance” owns the follow-up. Treat it as data loss, regardless of the
  review's low-severity label.
- Mixed owned-section endings and canonical LF frontmatter are permitted output;
  unrelated read-only readers and JSON sidecar semantics remain out of scope.
  Helper extraction is unnecessary. Import-order nit is corrected.
- EOF and repeat-sync coverage suggestions are advisory, with no reproduced
  defect; retain them here rather than expand the repair.

After correction, all 1,746 affected-module tests pass. The new nine-case
compatibility matrix verifies the regression by failure before the fix. A fresh
pair of reviews must cover the final logic snapshot.

Final production logic is `35173d3f8`. Full suite after that correction:
**15,068 passed, 67 skipped** in 60.32s. No full-suite failures remain.

## Claude Code review 2

Range `75aa0a7e5..35173d3f8ecf52a53f1b568a96659d48ba7b76c4`;
actual built-in `code-review` Skill at high effort plus supervising verification.
Session `338eec86-3699-49d0-9dd6-2578d9d7cd5f`.
Clean for introduced defects. All 1,746 affected tests pass in the reviewer run.
Differential probes compare the previous LF parser with raw CRLF/CR and LF
inputs: 80,000 cross-ending cases and 40,000 LF cases have zero mismatches.
Replacement idempotence adds no difference from previous LF behavior.

Seven raw recommendations are checked: owned/frontmatter LF is allowed;
read-only normalization is excluded; F-2/F-3 remain documented deferrals;
raw CR line starts reproduce prior universal-newline behavior. The separate
create body patch/References helpers still use normalizing I/O; no public-path
reproduction is claimed, and the follow-up belongs in BUG_BACKLOG for
investigation. This does not expand the concept-sync/scope-out repair.

## Claude Code review 3 and convergence

Range `75aa0a7e5..82ab0765977cdafb95358357ba4431047962de9a`;
actual built-in `code-review` Skill at high effort plus supervising verification.
Session `84af0abf-87f1-44e1-ba73-0635e245ecfd`.
Clean for introduced defects. All 1,746 affected tests pass in 3.94s;
`git diff --check` is clean. Independent raw-prefix/suffix and missing-section
append probes preserve bytes for LF/CRLF/CR. A 5,000-sequence parser differential
finds zero cross-ending mismatches.

Eight raw recommendations are checked: F-2/F-3 and create patch helpers are
known separate backlog work; mixed owned sections and LF frontmatter are
allowed; trimming CR/LF section-edge terminators restores prior translated
semantics; raw frontmatter hashes deliberately invalidate newline-only stale
previews; helper extraction is a preference. No new in-scope defect remains.

Reviews 2 and 3 are two consecutive independent clean reviews after final logic
`35173d3f8`. Only evidence, changelog and backlog records follow that logic.
The original newline-normalization entry is removed after verified completion;
three separately scoped follow-ups remain. Optional EOF/repeat-sync coverage is
retained above as advisory rather than claimed as a regression.

The changelog describes the normalization repair specifically; it does not claim
that the separate H1-deletion or concurrent-rollback ownership defects are fixed.
