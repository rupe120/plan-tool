# Files-coherence extensionless Dockerfile: code review ledger

One bounded change, reviewed headlessly (`claude-personal -p`, report-only):
the path and filename mention extractors in `plan_tool/detail.py` recognize an
exact, case-sensitive `Dockerfile` through one fixed list, and an identical
`Dockerfile` basename in another directory is never a near-miss in
`plan_tool/review.py`. The drain procedure lives in
[`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head (the branch carries one unrelated handoff-trim commit, `9e0173ede`) |
| Heads reviewed | Pass 1: `4abcb9171`. Pass 2: `8bc109c46`. Pass 3: `f8a8c9f42`. Corrections to pass 3: `ef4ef9202`, then this ledger revision (the next commit) |
| Checks | Full suite 14,906 passed, 67 skipped, 2026-11-13, with `ef4ef9202`'s code. The reviewers could not run tests; the author ran them. One skip is `tests/test_cli.py:3277`, a run-log scope proxy that skips whenever the branch diff touches a test file outside its allowlist (here `tests/test_review.py`); it passes on `main`. The other skips are unchanged (`tests/test_roadmap.py`, one unresolvable plan title) |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/files-coherence-dockerfile-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

## Settled decisions

- The supported extensionless set is exactly `Dockerfile`: no `Makefile`,
  `Jenkinsfile` or `Procfile`, and no `Dockerfile.<suffix>`. It is a fixed list,
  not a pattern.
- The class-wide effect on every consumer of the extractors is intended.
- A bare backticked `Dockerfile` credits every declared Dockerfile in the step
  (the existing basename rule, as for a bare `__init__.py`); a test states it.
- The `docs/` Dockerfile classification change is a recorded verdict change.
- The five `F811` lint errors in `tests/test_detail.py` and `tests/test_review.py`
  and the two `F821` in `plan_tool/launcher.py` exist on `main` and are out of
  scope.

## Evidence for the fix (this session's runs; the reviewers could not execute code)

- Before the fix, exactly the two tests that need the new recognition failed.
- Final mutants, measured on the final tests: dropping the path arm fails 10;
  dropping the bare arm fails 4; neutralizing the repeated-by-design skip fails 7;
  the first remedy (`dockerfile` in the generic set) fails 5; substring matching
  and case-insensitivity are each caught.
- Sibling-directory scores that motivated the skip, reproduced by running
  `_nearest_declared_match`: `docker/web` vs `docker/api` 0.857, `services/web`
  vs `services/api` 0.870, `worker-b` vs `worker-a` 0.947 (bar 0.85). Generic
  names keep the existing tradeoff and can reach the same route: `index.ts` in
  the same layouts scores 0.842, 0.857 and 0.941, so only the first stays under
  the bar. A cited `Dockerfile` vs a declared `Dockerfile.dev` in one directory
  also cleared the near-miss rules before the dotted-variant clause.

## Findings and dispositions

Pass 1 (seven findings):

1. A context citation such as `api/Dockerfile` drew a new `detail_only` "did
   you mean" finding — `fixed 50f35c48a` (`dockerfile` as a generic basename),
   found incomplete by pass 2 finding 1 and completed in `52d26f957`.
2. Consumers other than `check_files_coherence` unpinned — `fixed 50f35c48a`
   (near-miss, plan-level orphan deferral, claim-vs-delivery trip and no-trip,
   domain cells).
3. A medium finding citing only a `docs/` Dockerfile flips from blocking to
   non-blocking — `fixed 50f35c48a`: `docs/` and `tests/` cells pinned as a
   recorded verdict change.
4. Stale comment and docstrings saying a known extension is required —
   `fixed 50f35c48a`.
5. A bare `Dockerfile` credits every declared Dockerfile — `declined` as a
   defect (the existing basename rule); pinned by a test in `50f35c48a`.
6. Handoff log inaccuracies (test count, `lessons.py`, the near-miss direction,
   a stray blank line) — `fixed 8bc109c46`.
7. The handoff trim dropped the only record of a residual `detail` /
   `scope-review` empty-heading crash — `fixed 1acb52485`: reproduced on
   `derive_candidate_buckets` and filed in `BUG_BACKLOG.md`.

Pass 2 (five findings, one medium):

1. (medium) The generic-basename entry did not close the sibling-directory
   route: a long basename pushes full-path similarity over the 0.85 bar —
   `fixed 52d26f957`. Verified by running the scores above. `dockerfile` now
   lives in its own repeated-by-design set; an identical basename there never
   reaches either near-miss rule, and the generic names are unchanged.
2. The recorded bare-arm mutant count was not reproducible, and the skipped
   count moved — `fixed 52d26f957`: the bare-arm count is re-measured (4) and the
   skip is explained above.
3. A pre-existing test was renamed inside this change — `fixed 52d26f957`: the
   original name `test_claim_vs_delivery_no_trip_when_step_declares_it` is
   restored.
4. Consumer coverage the log claimed but tests did not pin — `fixed 52d26f957`
   for a repo-root `Dockerfile` cited bare and as `./Dockerfile`, and for a bare
   token in the classify test. `declined`: orphan condition 2 (a consuming
   step's citation). A test for it passed without the Dockerfile arm, because
   the step is already recognized through the path-derived symbol, so the
   extractor does not decide that outcome; the vacuous test was removed.
5. Pass-1 record not enumerable in the drain log — `fixed` in this ledger
   revision.

Pass 3 (four low findings, confirming pass; verified by running the scores):

1. `_claim_delivered` still fuzzy-matches a sibling-directory Dockerfile as
   delivered — `declined`: it only reduces the recall of an info advisory and
   produces no false finding, and Dockerfile claims were not extracted at all
   before this change, so nothing regressed. Not filed.
2. A cited `Dockerfile` against a declared `Dockerfile.<suffix>` in one
   directory still drew a near-miss (`services/api/Dockerfile` vs
   `services/api/Dockerfile.dev`, reproduced) — `fixed ef4ef9202`: the repeated-by-design
   skip also covers a dotted variant of the cited basename; a unit case and a
   files-coherence case pin it, and dropping the clause fails both.
3. The test docstring and this ledger claimed `index.ts` stays under the
   similarity bar in the same layouts — `fixed ef4ef9202` and this revision:
   reproduced at 0.842, 0.857 and 0.941; the claim now states the existing
   tradeoff for generic names. Not filed: it is documented behavior.
4. The range row named a head that was not the branch head, and the README
   entry said "the open pass" — `fixed` in this ledger revision.

## Closure

**Stopped at exit 2 on 2026-11-13; not converged, not clean.** Pass 2's one
medium finding reset the low-yield streak, and pass 3 was the only low-only pass
after it, so the two-consecutive-passes condition was not met. Most of pass 2's
and pass 3's findings describe this branch's own earlier edits (the first
remedy, its tests and claims, and this ledger), the shape `CLAUDE.md` calls the
loop auditing its own edits, so every finding is applied or dispositioned above
and no fourth pass is planned unless the owner asks for one. The extractor
change itself drew no material finding after pass 1's regression and pass 2's
incomplete-remedy finding were fixed.
