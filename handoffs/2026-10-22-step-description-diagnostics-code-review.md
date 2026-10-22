# Step description diagnostic repair

| Item | Record |
| --- | --- |
| Base | `2445c3740`, merged gate repair PR #141 |
| Branch | `fix/step-description-diagnostics` |
| Scope | BUG_BACKLOG “Step-field diagnostics advertise only legacy title after description alias support” |
| Route | Bounded direct formatter correction; no schema or alias change |
| Current state | Full suite passes; first actual Claude Code review clean on logic; independent confirmation pending |

## Property and sites

Concise validation diagnostics expose preferred step description and accepted
legacy title. Missing step text must be distinguished from missing plan/feature
titles; typo lists include both spellings and plan-level description points to
a step. Preserve structured errors, raw ValidationError text, internal Step.title,
validation outcomes, exit codes and unsupported-version ordering.

Pre-edit identifier search: format_validation_errors, _explain_extra_field,
model_fields, missing required errors and their validate consumer. Vocabulary
search: allowed fields, missing/typo/misplaced fields, title and description in
parser/tests/CLI validation and the format reference.

- parser.format_validation_errors renders structured errors. Remap only an
  actual missing error at (steps, integer index, title); do not mutate the
  payload or rewrite invalid/conflicting values.
- parser._explain_extra_field lists Step.model_fields, which intentionally
  lacks the input-only alias. Include description before legacy title in the
  step allowed list, and recognize the alias when explaining misplacement.
- cli.inspect.cmd_validate renders the concise format; locator and sweep
  also consume the same renderer, as review 1 verifies. Preserve its
  default findings exit 0 and opt-in --fail-on-findings exit 1.
- Tests mirror parser and exercise real main([...]) validation calls. Plan and
  feature title errors remain their original locations/messages.
- The Step validator, serialization, parser exception constructors and schema
  models remain unchanged. Other surfaces retaining raw Pydantic diagnostics
  are outside the concise-formatter scope; this change does not claim to
  normalize every application error.

## Validation

Affected parser/validation CLI/inspection checks: 497 passed in 1.54s.
Restoring the complete pre-change parser makes the new unit/CLI regressions
fail while existing carve-outs remain asserted; source is restored after the
mutation. Exact mutation counts and full-suite/review evidence are recorded below.

Old-formatter mutation: 5 failed, 13 passed in 0.57s. Full suite after restoring
the fix: 15,030 passed, 67 skipped in 74.77s. Diff whitespace check passes.

## Claude Code review 1

Range `2445c3740..4ab08849d`; actual built-in code-review Skill at high effort,
Sonnet 5.5, session `51fb5c33-dbe5-46ef-bc4a-746d56c2f53d`, CLI exit zero. Consolidated
report `.tmp/step-description-diagnostics.review-1.md`. Six candidates receive
independent code/caller/test verification and real-parser probes. Reviewer
runs 290 targeted checks; it does not claim another full suite or mutation.
**No introduced logic defect**; first clean pass against `fedb8ff44`.

- F1 pre-existing feature-container label/list error is confirmed; file
  “Feature-container unknown fields are mislabeled as plan-level fields” in
  BUG_BACKLOG with the actual probe/source evidence. Do not widen this repair
  into feature-container normalization.
- F2 stale status/evidence phrasing is corrected in this record.
- F3 optional coverage is added as two cases: legacy/preferred valid step text
  plus a typo must produce only unknown-key advice, never missing-field advice.
  This strengthens the intended missing-vs-typo distinction without changing
  production behavior.
- Speculative internal-field rename/wrapper changes are refuted by the preserved
  schema and tests. Display versus structured location differences are intended
  and payload preservation is pinned. The backlog entry stays until convergence.
- Plan/feature missing titles, invalid aliases, conflicts, version/exit behavior,
  raw exception constructors and the changelog are verified unchanged/accurate.

This round adds tests and tracking only. Production logic stays at `fedb8ff44`.

Review-1 follow-up checks: 499 affected tests pass in 1.21s; full suite 15,032
passed, 67 skipped in 73.79s. Production formatter is unchanged; new coverage
and tracking do not reset the logic review window.
