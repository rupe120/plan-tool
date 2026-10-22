# New-seed default placement

Base: `330441789` on branch `fix/seed-default-location`, independent of PR #136.
Intent: new seeds default to `docs/implementation-plans/plan-seeds/`; existing
seed files stay at their current paths. Both directories receive an explanatory
README. No seed migration or configurable-directory feature ships.

## Scope and invariant

`seed_paths.py` is a stdlib-only placement leaf. Scope-out (single/region),
reground, roadmap promotion and annotate share the nested default. Explicit
annotate output/seed destinations remain authoritative and its report default
stays beside the source. `create --from-existing` keeps explicit path semantics.

Existing roadmap publications retain root placement, even if their file is
archived or absent. New promotions persist optional `publication_layout: nested`;
missing layout means legacy root. Normalization validates the closed root/nested
vocabulary, and accept/materialize state rewrites preserve it. Refresh comparison
and skipped apply targets follow the recorded destination, not folder existence.
Unpublished files never gain publication ownership from their presence.

Pre-edit identifier search covers literal plan-seeds joins in all writers and
roadmap refresh/accept/preview paths. Vocabulary search covers placement,
promotion, published copies, seed authoring, CLI help and annotate output rules.
Sites: both scope-out path builders, reground builder, ordered roadmap targets,
publication registration, accept/materialize/refresh destinations, CLI preview,
annotate derivation and batch collision preflight. Documentation sites include
seed format, roadmap/data contracts, consuming directives, routers, user guides,
generated CLI references and repository authoring policy. Scratch enumeration:
`.tmp/seed-default-location.sites.md`.

Backlog #184 retains project-level configuration as separate future work; this
user-directed change supersedes its former root-default assumption. CLAUDE.md
changes only the seed authoring path and retains old-seed editing coverage;
normal PR review must use the required architect tier for that protected file.
PR #136 independently owns iteration guidance; do not absorb that work here.

## Validation

- Affected writers/lifecycle suite: 1,367 passed, 65 skipped before the final
  malformed-layout case; integration fixtures then update explicit expectations.
- Full completed source/fixture suite: 14,711 passed, 67 skipped in 60.70s.
- Mutation: reverting the nested constant fails the new-default invariant;
  forcing legacy publications into the nested folder fails all legacy-placement
  cases. Both mutations are restored before final full-suite validation.
- Existing legacy materialization/archive tests remain; a parametrized root/
  nested test verifies the recorded destination changes and the other same-named
  file stays byte-identical. Layout roundtrip/invalidation and malformed-field
  tests pin persistence and fail-closed parsing.
- Existing annotate override tests pass. The live root-seed preflight excludes
  README.md rather than treating explanatory prose as an implementation seed;
  existing seeds are not rewritten to satisfy a wider validation sweep.
- Help snapshot and CLI reference are regenerated from intentional parser/help
  changes. `git diff --check` is clean. No existing seed file is renamed/deleted.

## Review status

Actual Claude Code `/code-review` rounds and dispositions follow below;
closure below records two consecutive advisory-only passes and their limits.


## Claude review 1

Range `330441789..562820563`; actual built-in `code-review` Skill invoked at
high effort, Sonnet 5.5, session `7c9169d2-c7c9-4ad1-b0a1-c43c1921ce85`.
Original CLI exits zero. Method: inline skill recipe with eight review angles,
source/doc/test inspection; no execution in that review. Report:
`.tmp/seed-default-location.review-1.md`. Two generated help pages were outside
that checkpoint and are included in the next committed range.

| Finding | Disposition |
| --- | --- |
| 1 medium: shared annotate output can overwrite a different same-named source | Fixed: default output refuses an existing seed before backend invocation and uses exclusive creation at write time. Batch same-stem collisions fail preflight; documented distinct explicit seed paths are the escape. Explicit destination replacement stays compatible. Regression tests cover pre-existing files, concurrent creation, same-stem batches and explicit replacement. |
| 2 low-medium: authoring/docs still direct new seeds to root | Fixed: TRACKING seed-authoring recipes, starting-point/demo guides, capability summary and contributor routing use the nested default; roadmap contract names recorded publication layout. Existing named seed references remain valid and unmoved. |
| 3 low: accept preview ignores an unrelated root file for an unpublished seed | Declined: the new default is the potential collision destination; the root file is neither owned nor a collision. Existing root files remain untouched, and recorded published-root paths are still reported through the result. |
| 4 low: import grouping and long strings | Import grouping corrected; retain explicit user-visible destination paths. No additional abstraction or broad style rewrite. |
| 5 info: target enumeration reads state more than once | Declined: bounded guarded reads, no changed failure behavior or demonstrated cost; avoid incidental refactor. |

Identifier/vocabulary sweep expands to default-output overwrites, same-name
source batches and live authoring recipes. The collision remedy protects existing
seed bytes under both common and race inputs rather than merely detecting one
reported example. No migration/config feature is added.


Annotate collision regression is verified by mutation: replacing exclusive
creation with truncating write makes the concurrent-file preservation test fail.
The mutation is restored before subsequent checks. The post-correction full
suite has 14,714 passing tests and one intentional help-snapshot mismatch;
the snapshot is regenerated and then verified without the update flag. A fresh
full-suite result follows after the corrected committed snapshot.


## Claude review 2

Range `330441789..808c80e03`; actual built-in `code-review` Skill, high effort,
Sonnet 5.5, session `b4805783-6a97-4430-aa3a-e71f71b9e0aa`; CLI exits zero.
It verifies candidate findings against code/tests and independently runs the
affected suites: 1,394 passed, 65 skipped. Report:
`.tmp/seed-default-location.review-2.md` (with its test log in sibling scratch).
No blocking/medium finding; one low advisory behavior and one low coverage gap.

| Finding | Disposition |
| --- | --- |
| 1 low: a seed-create race can leave a fresh report without a new seed | Declined: annotate already permits partial report/seed writes on I/O failure; the command returns failure, source is not archived, and the existing seed is protected. This change does not add an atomic report/seed transaction. |
| 2 low: legacy apply-skip and accept not directly pinned | Fixed with two direct tests: skip returns root destination without moving bytes; accept updates only the root publication and preserves a same-named nested file and absence of the layout field. Existing nested tests and legacy materialize/refresh coverage remain. |
| Nit: target docstring uses old ambiguous path | Clarified as recorded/default destination. |
| Nit: state change between two CLI handoff reads can escape guard | Declined as unchanged narrow race in guarded reads; no normal-input failure or source corruption is demonstrated. No incidental state-read refactor. |
| Nit: default-collision remedy wording | Clarified: choose a new explicit path, or explicitly pass the existing path to permit replacement. |
| Nit: import alphabetization | Declined: no linter contract; no behavioral change and avoid style-only churn. |

Fresh full suite at `808c80e03`: 14,715 passed, 67 skipped in 61.58s. The new
review-2 changes are tests and explanatory strings/docstring only; no placement
or collision logic changes after `f53201887`. One completed advisory-only review
is recorded; independent confirmation remains pending.


## Claude review 3 and closure

Range `330441789..f08c6190f`; actual built-in `code-review` Skill, high effort,
Sonnet 5.5, session `624aaefd-0c8a-43ab-989c-27f8c4634ecb`; CLI exits zero.
The skill returns candidate findings; the supervising review independently checks
them against source/base/tests and runs affected suites: 2,844 passed, 66 skipped.
Report: `.tmp/seed-default-location.review-3.md`, with its sibling test log.
No new blocking or medium defect; all requested invariants are independently
confirmed. The legacy accept/apply-skip regression tests also fail under a
mutation redirecting legacy publications into the nested directory; restored
source precedes final validation.

| Finding | Disposition |
| --- | --- |
| N1 low: an unrecorded root file no longer blocks a new nested promotion | Declined as intended default-new behavior: presence is not ownership, the root file stays untouched, and only the new destination collides. Clarify the collision docstring; do not invent publication from file presence. |
| N2 low: directory-wide annotate also sees more seed Markdown | Deferred to BACKLOG #516 for input-selection policy. Recursive traversal already includes existing nested seed files; changing it is a separate behavior choice. |
| Repeated default overwrite/partial-report/preview advisories | Retain prior dispositions; no newly verified material failure. |
| Optional stale path vocabulary in module/function docstrings | Corrected once to default/recorded publication directory; marker and ownership semantics stay unchanged. |
| Optional import ordering and path literals | Retain prior decisions; avoid unrelated refactor and formatting churn. |

Convergence is **low-yield**, not zero-findings clean: reviews 2 and 3 are
independent consecutive completed passes with only low/advisory findings after
the last placement/collision logic change. Their known implications are applied
or explicitly dispositioned. The final sweep changes explanatory prose and
tracking only; no further full review is claimed after that sweep.

Final full suite at `f08c6190f`: **14,717 passed, 67 skipped in 55.00s**.
`git diff --check` is clean. Seed-directory changes contain only the two added
READMEs; existing seed contents, paths and references stay in place. The tracked
Claude skill copies byte-match canonical sources. No user-level skill refresh
is performed from this independent branch, to avoid replacing the separately
reviewed PR #136 iteration guidance installed in this session.

The change is committed locally on `fix/seed-default-location`. It requires
architect-tier PR review because CLAUDE.md changes its seed authoring location.
No push, PR, automatic migration, configuration feature or merge is part of this
user-directed atomic action.


## Integration after PR #136 merge — 2026-10-22

Bitbucket confirms #136 merged. Current main `176ce30a5` is integrated in merge
commit `42922cdc0`. Canonical integration sources combine without conflicts;
the two tracked Claude copies are regenerated from those combined sources, and
the handoff index retains both records. No runtime or test-source change occurs
relative to the reviewed seed branch; only #136 documentation and guidance
arrive. Existing review findings/dispositions remain the seed-logic evidence.

Post-merge full suite: 14,717 passed, 67 skipped in 74.19s. Tracked copies
byte-match their canonical sources, no conflict markers remain, and the tree is
clean before this evidence update. User-level copies are not refreshed from an
unshipped feature branch; they can update with the installed build after merge.
The seed-default change remains a separate local branch, ready for its own PR.
