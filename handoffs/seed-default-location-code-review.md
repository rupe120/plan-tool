# New-seed default placement

| Item | Record |
| --- | --- |
| Base | `330441789`, branch `fix/seed-default-location`, independent of PR #136 |
| Intent | New seeds default to `docs/implementation-plans/plan-seeds/`; existing seed files stay at their current paths; both directories get an explanatory README |
| Reviews | Three Claude Code `/code-review` passes (built-in skill, high effort, Sonnet 5.5): ranges `330441789..562820563`, `..808c80e03`, `..f08c6190f`; reports `.tmp/seed-default-location.review-N.md` |
| Closure | **Low-yield convergence**, not zero-findings clean: reviews 2 and 3 are consecutive independent passes with only low/advisory findings after the last placement/collision logic change (`f53201887`) |
| Checks | Full suite at `f08c6190f`: 14,717 passed, 67 skipped in 55.00s; after merging main `176ce30a5` (merge `42922cdc0`): 14,717 passed, 67 skipped in 74.19s; `git diff --check` clean |

## Settled decisions

- `seed_paths.py` is a stdlib-only placement leaf. Scope-out (single/region), reground, roadmap promotion and annotate share the nested default. Explicit annotate output/seed destinations stay authoritative and its report default stays beside the source; `create --from-existing` keeps explicit path semantics.
- Existing roadmap publications keep root placement, even if archived or absent. New promotions persist optional `publication_layout: nested`; a missing layout means legacy root. Normalization validates the closed root/nested vocabulary, accept/materialize rewrites preserve it, and refresh/apply-skip follow the recorded destination, not folder existence. Presence of an unpublished file never grants publication ownership.
- Not shipped: seed migration, configurable directory. BACKLOG #184 keeps project-level configuration as separate future work and its former root-default assumption is superseded by this user-directed change. CLAUDE.md changes only the seed authoring path (architect-tier PR review required). PR #136 owns iteration guidance and is not absorbed here.
- The live root-seed preflight excludes `README.md`; no existing seed is renamed, deleted or rewritten. Site enumeration: `.tmp/seed-default-location.sites.md`.
- Validation evidence: mutation reverting the nested constant fails the new-default invariant; forcing legacy publications into the nested folder fails all legacy-placement cases and the legacy accept/apply-skip tests; a parametrized root/nested test leaves the other same-named file byte-identical; layout roundtrip/invalid/malformed-field tests pin persistence and fail-closed parsing.

## Findings

| Review | Finding | Disposition |
| --- | --- | --- |
| 1 | Medium: shared annotate output can overwrite a different same-named source | fixed: default output refuses an existing seed before backend invocation and uses exclusive creation at write time; same-stem batches fail preflight; explicit destination replacement stays compatible. Tests cover pre-existing files, concurrent creation, same-stem batches, explicit replacement; truncating-write mutation fails the concurrent-file test. Full suite 14,714 plus one intentional help-snapshot mismatch, regenerated |
| 1 | Low-medium: authoring docs still direct new seeds to root | fixed: TRACKING recipes, starting-point/demo guides, capability summary and contributor routing use the nested default; roadmap contract names publication layout; existing references unmoved |
| 1 | Low: accept preview ignores an unrelated root file for an unpublished seed | declined: the nested default is the collision destination; the root file is neither owned nor a collision |
| 1 | Low: import grouping, long strings | fixed (import grouping); path literals kept explicit, no abstraction |
| 1 | Info: target enumeration reads state more than once | declined: bounded guarded reads, no demonstrated cost |
| 2 | Low: seed-create race can leave a fresh report without a new seed | declined: annotate already permits partial report/seed writes on I/O failure; it returns failure, does not archive, and the existing seed is protected; no atomic report/seed transaction added |
| 2 | Low: legacy apply-skip and accept not directly pinned | fixed: two tests (skip returns root destination without moving bytes; accept updates only the root publication, preserves a same-named nested file and the absent layout field). Fresh full suite at `808c80e03`: 14,715 passed |
| 2 | Nits: target docstring ambiguity, collision-remedy wording | fixed: clarified as recorded/default destination; remedy says choose a new explicit path or pass the existing path to permit replacement |
| 2 | Nit: state change between two CLI handoff reads | declined: unchanged narrow race, no demonstrated failure |
| 2 | Nit: import alphabetization | declined: no linter contract, style churn |
| 3 | N1 low: an unrecorded root file no longer blocks a nested promotion | declined: intended default-new behavior; presence is not ownership; collision docstring clarified |
| 3 | N2 low: directory-wide annotate also sees more seed Markdown | tracked BACKLOG #516 (input-selection policy; recursive traversal already includes nested seeds) |
| 3 | Repeated overwrite/partial-report/preview advisories | declined: prior dispositions stand |
| 3 | Optional stale path vocabulary in docstrings | fixed: reworded once to default/recorded publication directory; marker and ownership semantics unchanged |
| 3 | Optional import ordering, path literals | declined: avoid unrelated churn |

Reviews 2 and 3 ran affected suites independently (1,394 passed, 65 skipped; 2,844 passed, 66 skipped).

## Closure

**Low-yield convergence**, not zero-findings clean. The final sweep changed explanatory prose and tracking only; no further full review is claimed after it. Seed-directory changes are the two added READMEs only. Tracked Claude skill copies byte-match canonical sources; user-level copies are not refreshed from this branch, to avoid replacing PR #136's separately reviewed iteration guidance.

Integration after the PR #136 merge (2026-10-22): main `176ce30a5` merged as `42922cdc0` without conflicts; the two tracked Claude copies were regenerated from the combined sources; no runtime or test-source change relative to the reviewed branch. The change is committed locally on `fix/seed-default-location`, ready for its own architect-tier PR; no push, PR, migration, configuration feature or merge is part of this action.

Tracked: BACKLOG #516 (annotate directory input selection). Pending: none.
