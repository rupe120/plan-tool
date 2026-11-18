# Captured examples of versioned persisted formats

Each file here was written by the code of the release or commit in its name,
captured once, and is never edited or regenerated. A test (`tests/test_versioned_examples.py`)
loads every example through today's reader, so a reader change that breaks a
real old file fails here, which a record built from current output cannot show.

**A failing example means the reader regressed.** Fix the reader. Do not change
the example: a regenerated example would test nothing.

## How each example was captured

In a throwaway checkout of the named release, a one-off test (not committed)
reused that release's own test setup, with `--basetemp=/tmp/plan-tool-example/<source>`
so the absolute paths the revision records are neutral, and copied the saved file out:

- `completeness-final.*`: the end-to-end `plan-tool completeness-audit` run in
  `tests/cli/test_completeness_cmd.py::test_completeness_audit_persists_run_grade_report_and_qualified_sidecar`
  (the model call stubbed), which writes `qualified_result.audit_revision`.
- `completeness-checkpoint.*`, `run-reconcile.*`, `detail-reconcile.*`:
  `_save_completeness_sidecar` in `tests/test_completeness_report.py`, which calls
  the release's own `save_review` (`kind=` and `is_pre_apply_checkpoint=`).

| File | Source | Sidecar version | Audit-revision version |
| --- | --- | --- | --- |
| `completeness-final.sidecar-v4.revision-v3.v1.6.0.json` | v1.6.0 | 4 | 3 (in `qualified_result`) |
| `completeness-checkpoint.sidecar-v4.revision-v3.v1.6.0.json` | v1.6.0 | 4 | 3 (`checkpoint_audit_revision`) |
| `run-reconcile.sidecar-v1.v1.6.0.json` | v1.6.0 | 1 | none |
| `detail-reconcile.sidecar-v1.v1.6.0.json` | v1.6.0 | 1 | none |
| `completeness-final.sidecar-v4.revision-v4.main-4226931b3.json` | `main` at `4226931b3` (the first commit writing revision v4, `sibling_paths_digest`) | 4 | 4 |
| `completeness-checkpoint.sidecar-v4.revision-v4.main-4226931b3.json` | `main` at `4226931b3` | 4 | 4 |

## Pending: no code that wrote these can be retrieved

Every tag back to v0.2.0 already writes sidecar version 4 and audit-revision
version 3, and Loom's 776 saved reports (surveyed 2026-11-18) hold nothing older.
Until an older writer turns up, these have no example and are not filled with a
synthetic one:

- saved-review sidecar versions 1, 2 and 3 for `completeness`;
- audit-revision versions 1 and 2;
- the `review` kind and the `data-contract` kind;
- every other versioned format: plan and detail `format_version`, roadmap version
  records, checkpoints, grounding, concept tree, purity cache, project profile, and
  the decision-settlement receipt. Each needs its own capture from the release that
  wrote it (BACKLOG #543).

## When a version changes

A version bump adds an example of the new version, captured from the commit that
introduced it, in the same change. The coverage guard in the test fails otherwise.
