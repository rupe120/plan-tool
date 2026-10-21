> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add an impact-analysis evidence namespace while preserving immutable finals and temporary cleanup

## Summary

Extend `plan_tool/roadmap_evidence_store.py` with a closed namespace for immutable impact-analysis records and cover it in `tests/test_roadmap_evidence_store.py`. The new namespace uses the existing opaque publication and scan APIs, including exact final names, durable publication, and per-call temporary cleanup. Keep storage unaware of receipt or analysis schemas; callers decide whether returned bytes are reusable or a semantic collision. Green means receipt evidence and impact-analysis evidence can use the same final-name grammar without seeing or overwriting each other.

## Table of Contents

- [Summary](#summary) — The completed storage boundary and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why impact analyses need their own evidence location.
- [Input](#input) — Existing storage and receipt-consumer contracts that remain in force.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — Namespace, immutability, scan, and cleanup rules.
- [Tests](#tests) — Focused namespace-isolation and storage-invariant coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary API references for the storage operations.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this storage step.
- [Deferred](#deferred) — Publication, semantic validation, and CLI work owned elsewhere.

## Why

`plan_tool/roadmap_evidence_store.py:EvidenceNamespace` currently gives escalation receipts the only evidence location, so an analysis record with the same opaque final-name grammar would be mixed into receipt scans and views. Impact analyses need independent immutable records without duplicating the storage protocol or making this leaf understand either record schema.

## Input

- **Storage contract:** Preserve `plan_tool/roadmap_evidence_store.py:EvidenceNamespace`, `_NAMESPACE_COMPONENTS`, `namespace_relative_components`, `publish_evidence`, and `scan_evidence` as the only namespace-to-path and opaque-record boundary.

- **Final-name and result contract:** Keep `_FINAL_NAME_RE`, `EvidencePublishResult`, and `EvidenceScanResult` namespace-neutral. A final name remains a 64-character lowercase hexadecimal value, while record meaning belongs to a higher layer.

- **Existing receipt consumers:** `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_escalations_view` must continue to select `EvidenceNamespace.ESCALATIONS` unchanged.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_evidence_store.py` — Add the closed impact-analysis namespace and its fixed relative path.
  - `tests/test_roadmap_evidence_store.py` — Extend storage coverage to prove the new namespace is isolated and retains the shared immutable-publication rules.

## Implementation

- **Add one closed analysis namespace.** Add an intuitive `EvidenceNamespace.IMPACT_ANALYSES` member and map it in `plan_tool/roadmap_evidence_store.py:_NAMESPACE_COMPONENTS` to `.plan-tool/evidence/impact-analyses`. `namespace_relative_components` must remain the single way callers obtain that path shape.

- **Keep namespace membership strict.** `plan_tool/roadmap_evidence_store.py:_valid_namespace` must accept only enum members present in `_NAMESPACE_COMPONENTS`. Invalid namespace inputs must retain the current no-storage-access behavior.

- **Keep final semantics opaque.** Do not add receipt parsing, impact-analysis parsing, canonical-byte comparison, or collision classification to `publish_evidence`. An occupied exact final still returns `EVIDENCE_EXISTING` with the stored bytes; the later analysis runner compares those bytes with its candidate and decides reuse or collision.

- **Apply the existing immutable publication protocol unchanged.** `publish_evidence`, `_ensure_namespace`, `_open_temporary`, `_write_all`, `_sync_file`, `_read_exact_existing`, and `_sync_directory` must provide the same private temporary, exclusive final link, synchronization, and exact-final lookup behavior for the new namespace as for `ESCALATIONS`.

- **Clean up only the current call’s temporary.** Preserve `publish_evidence`’s `finally` cleanup of the temporary it created. Do not scan for or delete other dot-temporary files: another live publisher can own them, and crash-left files remain ignored by scans.

- **Keep scans local and read-only.** `scan_evidence` must enumerate only the selected namespace, keep raw-name ordering and grammar filtering, and avoid creating a missing analysis directory. Receipt and analysis records may use the same final name with different bytes because their directories are separate.

- **Leave callers out of this step.** Do not alter `plan_tool/roadmap_escalation_run.py` or `plan_tool/cli/roadmap_cmd.py`; they continue to use the receipt namespace. Step 8 will select the new namespace when it publishes analyses.

## Tests

### Tests for this step

- `test_impact_analysis_namespace_has_fixed_components` — `namespace_relative_components(EvidenceNamespace.IMPACT_ANALYSES)` returns the fixed analysis-only path components.

- `test_publish_creates_durable_final_and_removes_its_temporary` — extend coverage to the impact-analysis namespace and prove a created final contains the supplied bytes with no publisher-owned temporary left behind.

- `test_publish_reuses_exact_final_without_overwriting` — extend coverage to the impact-analysis namespace and prove a second write to the same final returns the original stored bytes.

- `test_namespaces_isolate_identical_final_names` — publish the same valid final name in receipt and impact-analysis namespaces with different bytes, then prove each scan reads only its own record.

- `test_each_publisher_synchronizes_the_full_fixed_namespace_ancestry` — cover the impact-analysis path’s complete directory synchronization sequence.

- `test_scan_returns_only_matching_records_in_raw_name_order` — cover analysis-namespace ordering and prove dot temporaries and nonfinal names stay invisible.

- `test_scan_empty_namespace_is_read_only` — prove a missing impact-analysis namespace returns no records without creating `.plan-tool`.

- **Green-before-done gate:** Every updated and added case in `tests/test_roadmap_evidence_store.py` is green before this step is complete.

## Acceptance criteria

- `EvidenceNamespace` contains an impact-analysis member whose path is `.plan-tool/evidence/impact-analyses`.

- `publish_evidence` accepts the new namespace and preserves the existing created, existing, invalid-input, and write-failed result behavior.

- Identical final names in receipt and impact-analysis namespaces do not overwrite, appear in, or affect each other.

- Publishing in the analysis namespace uses a private temporary and removes only that call’s temporary after success or failure.

- `scan_evidence` lists only grammar-matching analysis finals in deterministic raw-name order and creates no missing directory.

- `tests/test_roadmap_evidence_store.py` passes with both namespaces covered.

## References

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Read the `O_EXCL`, `link`, and `fsync` contracts that preserve no-overwrite immutable publication.

- [fcntl — The fcntl and ioctl system calls](https://docs.python.org/3.13/library/fcntl.html) — Read the platform synchronization support used by `plan_tool/roadmap_evidence_store.py:_sync_file`.

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use scoped replacements to cover synchronization and temporary-file failure paths.

## Applicable guardrails

- **Plan intent, separate immutable impact-routing analysis:** This step provides only the isolated storage location; it does not validate, classify, or route an analysis.

- **Plan step intent, evidence-type separation:** Keep receipt and analysis records separate by namespace while retaining exact-name immutable storage behavior.

- **The plan’s “## Out of scope”, execution and state changes:** Do not add receipt creation, broad execution, canonical writes, backend calls, patching, or reviewer-state changes to these files.

- **The plan’s “## Out of scope”, boundary changes:** Do not replace the writer boundary, alter canonical artifact schemas, or widen this leaf into unrelated storage refactoring.

## Deferred

- Impact-analysis construction, semantic validation, and collision classification — Step 5 owns the analysis contract; this store returns opaque occupied-final bytes only.

- Guarded analysis publication and reuse — Step 8 selects `EvidenceNamespace.IMPACT_ANALYSES` after its snapshot and analysis checks pass.

- Impact-analysis CLI inspection — Step 9 adds the view surface and must scan only the analysis namespace.
