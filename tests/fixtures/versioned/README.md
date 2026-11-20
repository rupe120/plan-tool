# Captured examples of versioned persisted formats

Each file here was written by the code of the release or commit in its path,
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

## Plan and run-grade detail

In throwaway checkouts of `v0.2.0` (`03cbb6882`) and `5d9ce9aca`, a one-off
test in `tests/test_detail.py` calls the revision's `_write_orchestrator_plan`
and runs its `generate_detail` for step 1 with `_GOOD_BODY` as the stubbed
model response. The writer saves the detail and rewrites the plan with its
detail pointer. Both output files are copied verbatim with their relative paths
intact. `5d9ce9aca` comes from the pre-publication history, before the format
declarations. It supplies the two declaration-free legacy version 1 examples.

| File | Source | Declared format version |
| --- | --- | --- |
| `authored/v0.2.0/2-orch.md` | v0.2.0 | 1 |
| `authored/v0.2.0/plan-details/orch/01-wire-up-renderer.md` | v0.2.0 | 1 |
| `authored/5d9ce9aca/2-orch.md` | `5d9ce9aca` | none |
| `authored/5d9ce9aca/plan-details/orch/01-wire-up-renderer.md` | `5d9ce9aca` | none |

## Completeness report with a data-contract finding

The `v1.8.0` release's
`tests/test_completeness_report.py::test_write_report_persists_data_contract_recommendations_without_schema_change`
writes all three files. The saved-review JSON carries the finding, and the
companion JSON carries the apply payload keyed by the finding ID. The files
retain their original names so the current reader can resolve the companion.

| File | Source | Contents |
| --- | --- | --- |
| `data-contract/v1.8.0/20260526-120000-completeness.md` | v1.8.0 | Rendered report |
| `data-contract/v1.8.0/20260526-120000-completeness.json` | v1.8.0 | Saved-review sidecar v1 |
| `data-contract/v1.8.0/20260526-120000-completeness-data-contract.json` | v1.8.0 | Companion apply payload |

## Checkpoint

The `v1.8.0` release's
`tests/test_checkpoint.py::test_load_returns_checkpoint_when_hash_matches`
writes this checkpoint. The compatibility test uses the current reader with
its age limit disabled because the captured timestamp stays fixed. It checks
the stored payload and requires the original input hash.

| File | Source | Schema version |
| --- | --- | --- |
| `checkpoint/v1.8.0/cp.json` | v1.8.0 | 1 |

## Grounding

The `v1.8.0` release's
`tests/test_grounding.py::TestWriteGroundingPreservesStepFingerprints::test_omitted_kwarg_preserves_existing_step_map`
writes the record twice. The capture is the second write, which carries
forward the step fingerprints while updating the plan and code fingerprints.
The fixture keeps the sidecar path that the reader derives from `2-foo.md`.

| File | Source | Schema version |
| --- | --- | --- |
| `grounding/v1.8.0/plan-details/foo/grounding.json` | v1.8.0 | 1 |

## Concept records

The `v1.8.0` tests `test_save_and_load_round_trip_exact_record` and
`test_flat_decision_record_round_trips` in `tests/test_concept_tree.py` write
these two records. The full tree requires the original plan fingerprint. The
flat decision record preserves that fingerprint as provenance and still loads
after the plan changes.

| File | Source | Schema version |
| --- | --- | --- |
| `concepts/v1.8.0/full-tree/plan-details/sample/concepts.json` | v1.8.0 | 1 |
| `concepts/v1.8.0/decision-record/plan-details/sample/concepts.json` | v1.8.0 | 1 |

## Purity cache

The `v1.8.0` tests `test_empty_findings_distinct_from_absent_entry` and
`test_load_prunes_entries_for_absent_steps` in `tests/test_purity_cache.py`
write these files. The first stores a completed check with no findings. The
second stores findings for two steps, one of which a plan-aware read omits
because that step is no longer in the plan.

| File | Source | Schema version |
| --- | --- | --- |
| `purity-cache/v1.8.0/checked-pure/x.json` | v1.8.0 | 1 |
| `purity-cache/v1.8.0/pruned-steps/x.json` | v1.8.0 | 1 |

## Project profile

The `v1.8.0` test `test_initialize_writes_the_v1_profile_and_reader_roundtrips`
in `tests/test_project_profile.py` writes this profile. The capture keeps its
project-relative path, and the current reader preserves the intent, non-goals,
and settled decisions.

| File | Source | Schema version |
| --- | --- | --- |
| `project-profile/v1.8.0/.plan-tool/project.json` | v1.8.0 | 1 |

## Roadmap version records

The `v1.8.0` test `test_load_explicit_stored_version_returns_complete_candidate_bundle`
in `tests/test_roadmap_versions.py` writes the root and candidate records. The
capture preserves their version directories. The compatibility test loads
`version.json` through the metadata reader and checks the predecessor binding
and the recorded member digests.

| File | Source | Schema version |
| --- | --- | --- |
| `roadmap-version/v1.8.0/roadmaps/storefront/.roadmap-versions/5c14e9ab88513c2f4c8cc5b36aa3d7d01018d9b755aaa5ef2bfc0d8b0d57667c/version.json` | v1.8.0 | 1 |
| `roadmap-version/v1.8.0/roadmaps/storefront/.roadmap-versions/7907f8cab455e8f9d91e0648f4aa117fce2ceaf79a9cf556e4e7d67bc6ac9d70/version.json` | v1.8.0 | 1 |

## Decision-settlement receipts

The test `test_fresh_receipt_is_committed_before_created` in
`tests/test_roadmap_decision_settlement_receipt.py` publishes both receipts.
The `v1.8.0` writer records the enrolled predecessor and resulting versions.
The pre-publication writer at `8b76b5409` records explicit null bindings for
unenrolled lineage. Each capture keeps the hash that the writer uses as its
filename, which the current reader checks against the receipt.

| File | Source | Schema version |
| --- | --- | --- |
| `decision-settlement/v1.8.0/34acc5455b7d7a1f9c2d154b26259a87fdcae0b143fa972866e67ab88c317796` | v1.8.0 | 1 |
| `decision-settlement/8b76b5409/30ad5cc309399fabfe473132323ae3906095f4eb6a9bd9bc5594d04baf5750d5` | `8b76b5409` | 1 |

## Pending

Every sidecar version the reader supports (1 to 4) has an example, and so does the
current audit-revision version. Not covered, and not filled with a synthetic file:

- audit-revision versions 1 and 2: every tag back to v0.2.0 writes revision 3, so no
  writer of these can be retrieved;

## When a version changes

A version bump adds an example of the new version, captured from the commit that
introduced it, in the same change. The coverage guard in the test fails otherwise.
