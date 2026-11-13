# Plan body newline preservation

| Item | Record |
| --- | --- |
| Base | `75aa0a7e5`, merged PR #142 |
| Branch | `fix/plan-body-newline-preservation` |
| Scope | BUG_BACKLOG “Concept sync and scope-out rollback normalize existing plan body newlines” |
| Route | Bounded direct I/O and heading-boundary correction |
| Current state | Complete: 15,068 tests pass; two consecutive independent clean Claude Code reviews after the final logic change |

## Settled decisions

Invariant: concept synchronization retains unowned body bytes, and failed narrowing restores the original plan bytes and matching provenance.

- Raw UTF-8 reads and a newline-translation-free atomic publisher at every site that republishes original plan bytes: concept_sync's current source, create's two snapshots, scope_review_cmd's snapshot, scope_out's `original_plan_text` snapshot and restore. `compute_frontmatter_hash` hashes the same raw frontmatter as parser provenance.
- Parser `_real_h2_matches` and `parse_body_sections` use CR-aware offsets; unowned slices are preserved, not normalized.
- Excluded by design: sidecar JSON reads, seed/detail/reference reads (they do not republish plan bytes), read-only normalization, scope selection, archive moves, publication ownership.
- Mixed owned-section endings and canonical LF frontmatter are permitted output. Raw frontmatter hashes deliberately invalidate newline-only stale narrowing previews. Helper extraction is a preference, not applied.

## Verification

- Before the fix (dated 2026-10-22): six raw-byte regressions fail (four concept-sync CRLF/CR combinations with and without source snapshots; two rollback cases after real plan publication); LF controls pass.
- Affected module suite 1,733 tests pass, including the real scope-review handler, scope-out sidecar-save failure after publication, and both create snapshot seams; assertions inspect bytes, owned-section replacement, fences, concurrent owned/unowned edits, fingerprints, restored details and provenance. Four further cases (successful narrowing keeps raw body bytes; newline-only frontmatter change invalidates a stale preview) pass in the 605-test parser/scope-out run.
- Implementation commits: `c80e96dad` (concept sync, source snapshots, raw heading boundaries), `778fabcdd` (scope-out snapshots, restoration, CAS). Final production logic `35173d3f8`; full suite **15,068 passed, 67 skipped**. `git diff --check` passes.

## Findings

Review 1, range `75aa0a7e5..778fabcdde4dffb78e48f82d305eb896d76abbcf`, built-in `code-review` Skill at high effort, session `5b24ca95-9688-4811-aa2c-38e42bd6fda9`.

- F-1 fixed `35173d3f8`: narrowing higher-heading whitespace changed existing empty/non-ASCII boundaries; nine new cases failed before the fix; original `\s+` semantics restored while keeping raw CR/LF anchors (all 1,746 affected-module tests pass).
- F-2 tracked BUG_BACKLOG “Concept sync deletes an unowned H1 after an owned H2”: pre-existing; H1 content after an owned H2 is deleted (reproduced for LF/CRLF/CR).
- F-3 tracked BUG_BACKLOG “Scope-out rollback overwrites the concurrent edit rejected by provenance”: pre-existing; an injected concurrent priority edit raises ConcurrentModificationError but unconditional rollback overwrites it. Data loss despite the review's low-severity label.
- Import-order nit fixed (`35173d3f8`).
- EOF and repeat-sync coverage suggestions: declined, advisory; no reproduced defect.

Review 2, range `75aa0a7e5..35173d3f8ecf52a53f1b568a96659d48ba7b76c4`, session `338eec86-3699-49d0-9dd6-2578d9d7cd5f`: clean for introduced defects. Differential probes against the previous LF parser (80,000 cross-ending, 40,000 LF cases) show zero mismatches; replacement is idempotent. Seven raw recommendations checked: owned/frontmatter LF allowed (declined); read-only normalization excluded (declined); F-2/F-3 stay tracked; raw CR line starts reproduce prior universal-newline behavior (refuted as defect). The separate create body patch/References helpers still use normalizing I/O: tracked in BUG_BACKLOG for investigation (no public-path reproduction claimed).

Review 3, range `75aa0a7e5..82ab0765977cdafb95358357ba4431047962de9a`, session `84af0abf-87f1-44e1-ba73-0635e245ecfd`: clean for introduced defects. 1,746 tests pass; raw-prefix/suffix and missing-section append probes preserve bytes; a 5,000-sequence parser differential finds zero mismatches. Eight recommendations: F-2/F-3 and create patch helpers tracked; mixed owned sections and LF frontmatter declined (allowed); trimming CR/LF section-edge terminators refuted (restores prior translated semantics); raw frontmatter hashes declined (deliberate); helper extraction declined (preference).

## Closure

Reviews 2 and 3 are two consecutive independent clean reviews after final logic `35173d3f8`; only evidence, changelog and backlog records follow it. The original newline-normalization entry is removed after verified completion; three separately scoped follow-ups remain tracked (F-2, F-3, create patch helpers). The changelog describes only the normalization repair; it does not claim the H1-deletion or concurrent-rollback defects are fixed.
