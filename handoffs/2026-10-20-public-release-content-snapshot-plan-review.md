# Public-release content snapshot design review

Use this record when checking the content-selection contract or diagnosing a
planning-workflow issue. The six-step plan supplies content selection, reference
repair, policy alignment, independent verification and backlog reconciliation.
Current release actions belong in [the pickup record](2026-10-19-public-onboarding-and-release.md).

## Contract to preserve

- Select content explicitly and keep useful conclusions in maintained documents.
- Keep content digests tied to the bytes they identify; report summaries do not
  inherit captured audit qualification.
- Make guidance self-contained and preserve the judgment rules in both governing
  documents.
- Verify a candidate in an independent repository and environment.
- Keep rights decisions, technical checks, architect review and publication
  authority distinct.

## Findings and dispositions

| Finding | Disposition and useful conclusion |
| --- | --- |
| Shared guidance lacks the same provenance-check route as project guidance | Fixed: step 3 covers both governing documents and preserves the distinction between a bad prior fix and structural recurrence |
| PDF declared in step files appears unmentioned | Refuted: the detail names the PDF twice; the filename extractor excludes the `pdf` extension. Do not alter accurate prose merely to silence this diagnostic |
| Binary PDF enters argv during detail authoring | Tracked: inspect binary artifacts through extracted text and rendered pages; the transport fix belongs to separate tool work |
| Generated detail references resolve beside the wrong owner | Fixed: local targets point to their actual repository owners; all six details parse |

The 2026-10-20 bare audit has zero conceptual findings at 0/6 detail coverage.
The final detail audit has zero conceptual findings at 6/6 coverage and
`confirmed-dry` coverage; its overall result is `awaiting-human-action` because of
the false PDF diagnostic. Preserve that distinction when interpreting a result:
a completed process and a clean audit are different claims.

## Review use

Read [the plan](../docs/implementation-plans/archive/2-public-release-content-snapshot.md),
its details and the [maintained conclusions](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions).
Treat audit measurements as evidence about their named inputs. Review changed
plan content again before a new implementation; use code reconciliation and
implementation review after execution. Do not re-audit unchanged text merely to
obtain a different label for a known diagnostic.
