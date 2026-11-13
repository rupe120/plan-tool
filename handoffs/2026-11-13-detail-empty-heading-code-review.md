# Detail empty-heading refusal: code review ledger

One bounded change, reviewed headlessly (`claude-personal -p`, report-only):
`detail` refuses a plan body that holds a heading whose name is empty after
normalization (`## :`, `## .`) with a `DetailError` that names the heading and
the plan, through one helper (`empty_concept_headings_message` in
`plan_tool/concept_bootstrap.py`) that `create` now shares. The drain procedure
lives in [`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head; the branch carries one unrelated handoff-trim commit (`c3fd86f38`) |
| Heads reviewed | Pass 1: `f7c5afc13`. Pass 2: `ef923fdf8`. Corrections to pass 2: `4a9979704`, then this ledger revision (the next commit) |
| Checks | Full suite 14,915 passed, 67 skipped, 2026-11-13, with `4a9979704`'s code. The reviewers could not run tests; the author ran them. The one extra skip is `tests/test_cli.py:3277`, a run-log scope proxy that skips whenever a branch's diff touches a test file outside its allowlist; it passes on `main` |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/detail-empty-heading-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Closed at low-yield convergence, 2026-11-13: not a clean audit.** Pass 1 returned three low findings and pass 2 six low plus one info, none material |

## Settled decisions

- Refuse rather than skip or rename an empty-named section; the empty-name
  predicate is `not section.name` (the parser strips whitespace before dropping
  trailing `:`/`.`, so a name is empty exactly when `concept_id` would raise).
- `scope-review` has no guard (see pass 2, finding 1): its legacy route only
  reaches the bootstrap with a record that matches the plan, and a plan holding
  such a heading cannot have had one written.
- `detail` and the `scope-review` legacy route do not run the repeated-heading
  check from the `create` refusal; they collapse silently or exit cleanly, as
  recorded earlier.
- The CLI handler that prints `DetailError` (`cli/authoring.py`) was traced by a
  reviewer, not run.

## Evidence (this session's runs; the reviewers could not execute code)

- Before the fix, the two `derive_candidate_buckets` refusal cases failed with
  the bare `ValueError`; the zero-width carve-out passed. The helper's own unit
  tests could not import before the helper existed.
- Mutants, measured: skipping the refusal in `create` fails 8; skipping it in
  `detail` fails 3 (the `generate_detail` test and the two bucket cases);
  widening the helper to a zero-width name fails 3; silently dropping a
  zero-width-named section fails the zero-width test; dropping the plan-path
  prefix fails the `generate_detail` test.
- Probe behind pass 2's finding 1: a full-tree record written while the plan was
  clean, then `## :` hand-added, makes `scope-review` exit 4 with "stored plan
  fingerprint is stale" and never reach the bootstrap.

## Findings and dispositions

Pass 1 (three low findings):

1. The zero-width carve-out test in `detail` asserted only a truthy dict —
   `fixed 84d9aae57` (it asserts the invisible-named bucket exists).
2. The helper docstring overstated "every command" — `fixed 84d9aae57`.
3. No test drove the refusal through the real `detail` entry point —
   `fixed 84d9aae57` (a `generate_detail` test: `DetailError` naming the heading,
   no model call, plan and detail directory untouched).

Pass 2 (six low findings and one info):

1. The `scope-review` legacy-route guard was unreachable by any real flow, and
   its test forged a state no tool can produce — `fixed 4a9979704`: the guard and its
   two tests are removed and the `scope-review` files match `main`. Verified by
   running a realistic hand-edit (stale-record exit). The earlier command-level
   reproduction had used a forged record, and the backlog entry had overstated it.
2. The review record was embedded in the drain handoff instead of a ledger —
   `fixed` in this ledger revision.
3. The branch carries an unrelated commit and the range was miscounted —
   accepted: the trim is a separate, separately described commit and the pull
   request body states the true range; the Dockerfile ledger stays indexed in
   `handoffs/README.md`.
4. The refusal is applied at opt-in call sites, not at the bootstrap
   precondition — `fixed 4a9979704` for the documentation (a note on `bootstrap_concepts`
   that callers run the helper first). `declined`: making `bootstrap_concepts`
   itself raise a descriptive error, a more general design change.
5. The `detail` refusal did not name the plan — `fixed 4a9979704` (the error carries the
   plan path; the `generate_detail` test asserts it).
6. The flat carve-out test pinned only the return code — moot: removed with the
   guard it protected.
7. Handoff verification claims were partly unverifiable (the pre-fix claim and a
   missing mutant) — `fixed` in this ledger revision.

## Closure

**Closed at low-yield convergence on 2026-11-13; not a clean audit.** Two
consecutive passes returned only low and info findings, none material. The
largest outcome of review was removing a guard that protected no real flow.
