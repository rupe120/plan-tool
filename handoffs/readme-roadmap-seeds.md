# README roadmap seed handoff

The README's entry-point table and roadmap overview state that stage 4 publishes
the plan mapping, not seed files. The handoff materializes a selected plan ID,
uses `--view seeds` for per-plan state, and reviews the reported seed before
create. A default-directory direct draft example is distinct from optional
promotion, which requires materializing/reviewing its candidate drafts and
uses the actual create handoff. New nested publications and retained legacy
paths both remain supported. The ordinary two audit gates remain explicit.

## Scope and evidence

Invariant: the README never implies stage completion alone supplies a seed
that create can consume. Identifier search for `seeds/`, `--materialize`,
`--apply`, and vocabulary search for `draft seed` / `ordered create` locate
the core workflow row, entry-point row, roadmap overview and plan handoff. Those sites receive
the bounded correction; existing lifecycle/status prose is not redesigned.

Sources: `docs/how-to/roadmap.md` section 7, `plan_tool/seed_paths.py`,
the generated roadmap CLI reference and the corrected common-workflows guide.

- `uv run pytest tests/test_seed_paths.py tests/cli/test_cli_reference.py -q`: **15 passed**.
- Added seed-preparation link and heading anchor resolve.
- `git diff --check` passes.
- Initial actual Claude Code reviews at `457809890` both identify the missed
  core-workflow table row as the same defect class. The correction changes it
  to separate materialization/review before create, then commits `ed029fb3d`.
- Two independent final actual built-in Claude Code reviews at
  `ed029fb3db4eadfac54e4039860f253471713a87` (range `4cf28503e..ed029fb3d`),
  using `claude-sonnet-5-5 --effort high`, find **zero confirmed README defects**.
  The all-README restatement sweep confirms no remaining claim that a stage
  run writes seed files. Retained advisories concern optional wording for
  the materialize-reported path and linked state-handling detail; these do
  not require another iteration at README altitude.
- Final focused checks repeat: **15 passed**; the guide anchor and whitespace
  checks pass. No runtime behavior is changed.
- The fulfilled README backlog entry is removed. A separate starting-point
  guide statement still claims seeds/emitted plans from roadmap; it is filed
  in BUG_BACKLOG rather than expanded into this README-only correction.
  The legacy promotion-summary bug remains separately tracked.

Review 1 session: `a10bbe21-8cac-4171-b3b5-69053cb2e38f`.

Review 2 session: `bab1f073-2300-4b4f-b100-97637a7c34e2`.

Review 3 session: `b2f31c7a-9405-40a4-b582-1cf2efede099`.

Review 4 session: `53aa6943-968a-40b3-9f48-b6bd1b910690`.
