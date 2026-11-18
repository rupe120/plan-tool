# Captured examples of versioned persisted formats

Each file here was written by the code of the release or commit in its name,
captured once, and is never edited or regenerated. A test
(`tests/test_versioned_examples.py`) loads every example through today's reader
and checks it against an expected record written in the test, so a reader change
that breaks a real old file fails here, which a record built from current output
cannot show.

**A failing example means the reader regressed.** Fix the reader. Do not change
the example: a regenerated example would test nothing.

## How each example was captured

In a throwaway checkout of the named release, a one-off test (not committed)
reused that release's own test setup and copied the saved file out. A fixed
`--basetemp=/tmp/plan-tool-example/<source>` keeps the absolute paths a revision
records neutral; on macOS they read `/private/tmp/plan-tool-example/<source>/...`
because `/tmp` resolves there:

- `completeness-final.*`: the end-to-end `plan-tool completeness-audit` run in
  `tests/cli/test_completeness_cmd.py::test_completeness_audit_persists_run_grade_report_and_qualified_sidecar`
  (the model call stubbed), which writes `qualified_result.audit_revision`.
- `completeness-checkpoint.*`, `run-reconcile.*`, `detail-reconcile.*`:
  `_save_completeness_sidecar` in `tests/test_completeness_report.py`, which calls
  the release's own `save_review` (`kind=` and `is_pre_apply_checkpoint=`).
- `completeness-legacy.*`, `completeness-advisory.*`,
  `completeness-checkpoint-no-revision.*`, `review.*`: the release's own
  `save_review` called directly, with no revision (legacy), with an
  `AuditShapeAdvisory` (the construction in
  `tests/test_review_persistence.py::test_audit_shape_advisory_round_trips_without_finding_prose`),
  with `is_pre_apply_checkpoint=True` and no revision, and with `kind="review"`.
  Their recommendations carry `severity`, `impact` and `step_id` values so the loader's handling of
  each is pinned.

Each captured file keeps its capture-time `created_at` and, where a revision
records them, its absolute detail paths under `/private/tmp/plan-tool-example/`. No test
reads either. A real saved report carries the paths of whichever machine wrote
it, so a reader that starts resolving them must cope with files that do not exist.

| File | Source | Sidecar version | Audit-revision version |
| --- | --- | --- | --- |
| `completeness-legacy.sidecar-v1.v1.6.0.json` | v1.6.0 | 1 | none |
| `review.sidecar-v1.v1.6.0.json` | v1.6.0 | 1 | none |
| `run-reconcile.sidecar-v1.v1.6.0.json` | v1.6.0 | 1 | none |
| `detail-reconcile.sidecar-v1.v1.6.0.json` | v1.6.0 | 1 | none |
| `completeness-advisory.sidecar-v2.v1.6.0.json` | v1.6.0 | 2 | none |
| `completeness-checkpoint-no-revision.sidecar-v3.v1.6.0.json` | v1.6.0 | 3 | none |
| `completeness-final.sidecar-v4.revision-v3.v1.6.0.json` | v1.6.0 | 4 | 3 (in `qualified_result`) |
| `completeness-checkpoint.sidecar-v4.revision-v3.v1.6.0.json` | v1.6.0 | 4 | 3 (`checkpoint_audit_revision`) |
| `completeness-final.sidecar-v4.revision-v4.main-4226931b3.json` | `main` at `4226931b3` (revision v4, `sibling_paths_digest`, was introduced earlier in `6e873dd59`) | 4 | 4 |
| `completeness-checkpoint.sidecar-v4.revision-v4.main-4226931b3.json` | `main` at `4226931b3` | 4 | 4 |

## Pending

Every sidecar version the reader supports (1 to 4) has an example, and so does the
current audit-revision version. Not covered, and not filled with a synthetic file:

- audit-revision versions 1 and 2: every tag back to v0.2.0 writes revision 3, so no
  writer of these can be retrieved;
- the `data-contract` kind of saved report;
- every other versioned format: plan and detail `format_version`, roadmap version
  records, checkpoints, grounding, concept tree, purity cache, project profile, and
  the decision-settlement receipt. Each needs its own capture from the release that
  wrote it (BACKLOG #543).

## When a version changes

A version bump adds an example of the new version, captured from the commit that
introduced it, in the same change. The coverage guard in the test fails otherwise.
