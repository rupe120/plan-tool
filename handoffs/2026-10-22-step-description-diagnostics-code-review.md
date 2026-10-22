# Step description diagnostic repair

| Item | Record |
| --- | --- |
| Base | `2445c3740`, merged gate repair PR #141 |
| Branch | `fix/step-description-diagnostics` |
| Scope | BUG_BACKLOG “Step-field diagnostics advertise only legacy title after description alias support” |
| Route | Bounded direct formatter correction; no schema or alias change |
| Current state | Affected checks and mutation pass; full suite and actual Claude Code reviews pending |

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
- cli.inspect.cmd_validate is the concise formatter's consumer. Preserve its
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
mutation. Exact mutation counts and full-suite/review evidence follow.

Old-formatter mutation: 5 failed, 13 passed in 0.57s. Full suite after restoring
the fix: 15,030 passed, 67 skipped in 74.77s. Diff whitespace check passes.
