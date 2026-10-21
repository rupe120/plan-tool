> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add Data Contract Discovery And Drift Checks

## Summary

This step creates `plan_tool/data_contract.py` as the code-owned registry for persisted and serialized data shapes, then rewires `tests/test_data_contract.py` to test against that registry instead of hard-coding every dataclass locally. The main design decision is to keep discovery explicit and conservative: discover fields from real dataclasses with `dataclasses.fields`, but require humans to register which dataclasses, sidecar JSON documents, and durable config files are part of the runtime contract. On green, `DATA_CONTRACT.md` is checked section-by-section against the code-owned contract, so registered persisted fields, JSON key aliases, schema constants, manifest keys, grounding freshness keys, project-config keys, stale documented fields, and obsolete contract sections cannot drift from documentation; unregistered non-dataclass JSON keys are not discoverable unless this step adds exported key constants or a parser-backed check for that contract.

## Table of Contents

- [Summary](#summary) — What the step adds and how reviewers should read it.
- [Why](#why) — Why the current drift guard is too weak for this subsystem.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact files this step creates or changes.
- [Implementation](#implementation) — The intended contract registry, doc checks, and constraints.
- [Tests](#tests) — The test cases that cover the new behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs relevant to the implementation.
- [Deferred](#deferred) — Related work this step does not take on.

## Why

`tests/test_data_contract.py:test_every_persisted_field_is_documented` currently catches only one broad failure: a persisted dataclass field missing anywhere in `DATA_CONTRACT.md`. That leaves avoidable gaps: a field can be documented in the wrong section, `SavedReview.schema_version` can drift from its JSON key `version`, constants like `SCHEMA_VERSION` and `TELEMETRY_SCHEMA_VERSION` can be dropped from prose, and non-dataclass JSON contracts such as `plan_tool/locator.py:load_manifest_plan_paths` are not represented by a shared code contract. The fix is a small code-owned discovery layer that names the persisted shapes once and gives tests enough structure to check the doc where the field actually belongs.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/data_contract.py` — Add the registry and discovery helpers for runtime persisted data contracts.

- **Existing files (edits only):**
  - `tests/test_data_contract.py` — Replace the local `_PERSISTED_DATACLASSES` list and broad text checks with tests driven by `plan_tool/data_contract.py`.
  - `DATA_CONTRACT.md` — Update the source-of-truth note and any field tables needed so the stricter checks pass.
  - `plan_tool/review_persistence.py` — Edit only if the registry needs a tiny exported constant or comment to avoid duplicating an existing JSON key name, or if `update_annotation` must preserve registered saved-review JSON keys while rewriting annotations.
  - `plan_tool/review.py` — Edit only if a field comment is stale after the registry names the persisted `Recommendation` / `Redirect` contract; do not change recommendation behavior.
  - `plan_tool/telemetry.py` — Edit only if a schema constant or docstring is stale after the registry names the `DecisionEvent` contract; do not change telemetry write/read behavior.
  - `plan_tool/locator.py` — Edit only if the manifest contract needs a stable exported key constant; preserve `DEFAULT_MANIFEST_SUBPATH` and `load_manifest_plan_paths`.
  - `plan_tool/grounding.py` — Register the persisted grounding sidecar shape, including `schema_version`, `grounded_at`, `plan_fingerprint`, and `code_fingerprint`; edit only comments/constants needed for stable contract naming.
  - `plan_tool/project_config.py` — Register the durable project and user config shape, including `.plan-tool/config.json`, `~/.plan-tool/config.json`, `branch_awareness`, and `smell_checks`; edit only comments/constants needed for stable contract naming.
  - `tests/test_grounding.py` — Keep grounding sidecar behavior green while adding registry-backed documentation checks.
  - `tests/test_project_config.py` — Keep config read/write behavior green while adding registry-backed documentation checks.

## Implementation

- **Foundational logic: persisted contract discovery registry.** Add `plan_tool/data_contract.py` as a small module that describes the contract surfaces tests should enforce. It should answer: which dataclass fields are serialized, which fields are in-memory only, which field names have JSON key aliases, which schema/version constants must be named, and which non-dataclass JSON documents have stable keys.

- **Keep discovery explicit.** One good shape is a pair of frozen dataclasses such as `PersistedDataclassContract` and `JsonObjectContract`, plus functions like `persisted_dataclass_contracts()` and `json_object_contracts()`. The registry should name real classes from `plan_tool/review_persistence.py:SavedReview`, `plan_tool/review_persistence.py:Annotation`, `plan_tool/review.py:Recommendation`, `plan_tool/review.py:Redirect`, and `plan_tool/telemetry.py:DecisionEvent`.

- **Use runtime dataclass introspection for fields.** Use `dataclasses.fields()` in `plan_tool/data_contract.py` or in the tests that consume it. Do not copy the field lists by hand into `tests/test_data_contract.py`; the test should fail automatically when a registered persisted dataclass grows a field.

- **Model aliases and exclusions directly.** `plan_tool/review_persistence.py:SavedReview.schema_version` is persisted as JSON key `version`, while `SavedReview.path` is not persisted. The registry must make both facts visible so tests can check that `DATA_CONTRACT.md` documents the alias and does not treat `path` as a normal saved JSON key.

- **Record intentional documentation exclusions durably.** Add an explicit registry field for serialized fields or keys that are intentionally not documented as part of the public contract. Each exclusion must name the owner, field/key, reason, and reviewer-facing rationale. The drift checker should suppress missing-doc findings only for entries in this explicit exclusion list, and `DATA_CONTRACT.md` should have a short "Intentional exclusions" subsection or table that mirrors those decisions. Do not silently drop discovered serialized fields.

- **Preserve module boundaries.** `plan_tool/review_persistence.py` is intentionally narrow and keeps persistence behavior around `save_review`, `load_review`, and `update_annotation`. The new registry can import that module, but do not make `review_persistence.py`, `review.py`, `telemetry.py`, or `locator.py` import `plan_tool/data_contract.py`; the contract registry is for tests and documentation checks, not runtime persistence.

- **Do not change the serialized schemas.** This step should not add fields to `SavedReview`, `Annotation`, `Recommendation`, `Redirect`, or `DecisionEvent`, and should not bump `SCHEMA_VERSION` or `TELEMETRY_SCHEMA_VERSION`. If a stricter test exposes a missing doc entry, update `DATA_CONTRACT.md`; do not reshape the data to fit the doc.

- **Preserve saved-review contract keys on annotation updates.** `plan_tool/review_persistence.py:update_annotation` rewrites the saved review sidecar and therefore must retain every registered persisted `SavedReview` key it loaded, including fingerprint fields such as `detail_bundle_fingerprint` and `detail_bundle_fingerprint_present`. Treat this as preserving the existing serialized contract during annotation edits, not as adding a new saved-review schema.

- **Keep telemetry as an open context bag.** `plan_tool/telemetry.py:DecisionEvent.context` is a persisted top-level field, but per-kind context keys are variant documentation, not dataclass fields. Keep the existing targeted tests in `tests/test_data_contract.py` for create granularity and plan criteria keys; the new registry should not turn every context key into a top-level `DecisionEvent` field.

- **Cover locator JSON deliberately.** `plan_tool/locator.py:DEFAULT_MANIFEST_SUBPATH` and `plan_tool/locator.py:load_manifest_plan_paths` define the registered plan manifest contract: JSON object with a `plans` array of repo-relative path strings. Register that as a non-dataclass JSON object so `DATA_CONTRACT.md:Plan manifest` stays tied to the declared contract, and only claim drift coverage for registered keys unless the implementation also introduces exported key constants or a parser-backed check. Treat `plan_tool/locator.py:load_known_roots` / `record_known_root` as out of scope for the app data contract unless the plan is expanded; it is a best-effort cache, not the plan manifest.

- **Register grounding freshness sidecars.** `plan_tool/grounding.py:Grounding` is an existing persisted sidecar contract with `schema_version`, `grounded_at`, `plan_fingerprint`, and `code_fingerprint`. Register it as a dataclass-backed contract so the overview's fingerprint/freshness scope is enforced by `DATA_CONTRACT.md` checks rather than left as an implementation promise.

- **Register durable project configuration.** `plan_tool/project_config.py` owns durable config files such as `.plan-tool/config.json` and `~/.plan-tool/config.json`, with current documented keys including `branch_awareness` and `smell_checks`. Register those JSON objects or exported key constants as durable config contracts so the plan's registry/config scope is checked from code.

- **Make doc checks section-aware.** Update `tests/test_data_contract.py` so a field must appear under the section registered for its class, not merely anywhere in the file. A simple Markdown section slicer is enough: find headings like ``### `SavedReview` (`review_persistence.py`)`` and check that the registered fields appear inside that section before the next heading of the same or higher level.

- **Reject stale contract documentation.** The section-aware checks must work in both directions: registered code fields must appear in the expected section, and documented fields that are not present in the registered code contract must fail unless the registry marks them as accepted aliases, open-bag keys, or intentionally documented implementation notes. Also fail obsolete sections whose registered owner no longer exists. This prevents `DATA_CONTRACT.md` from passing by accumulating doc-only fields after code changes.

- **Emit structured drift payloads for apply.** The checker should return neutral drift records that include source type, owner, field/key, target `DATA_CONTRACT.md` section, current code fingerprint or registry fingerprint, current contract fingerprint, candidate operation (`add`, `update`, `remove`, or `intentional-exclusion`), and enough candidate field metadata for step 3 to present operator choices. The persisted `Recommendation` can still use free-form `body` and `suggested_action`, but the apply command must have access to this structured payload through the saved sidecar or a colocated payload map.

- **Use stable symbolic anchors in failure messages.** Test failures should point to names like `DATA_CONTRACT.md:SavedReview section`, `plan_tool/review_persistence.py:SavedReview`, or `plan_tool/locator.py:load_manifest_plan_paths`, not line numbers.

- **Update `DATA_CONTRACT.md` to match the new owner.** The opening source-of-truth note should still say code wins, but it should mention that the enforced registry lives in `plan_tool/data_contract.py`, while runtime behavior still lives in `plan_tool/review_persistence.py:save_review`, `plan_tool/review_persistence.py:load_review`, `plan_tool/telemetry.py:record_decision`, `plan_tool/telemetry.py:read_decisions`, and `plan_tool/locator.py:load_manifest_plan_paths`.

## Tests

- `test_contract_registry_names_persisted_dataclasses` — Asserts `plan_tool/data_contract.py` registers `SavedReview`, `Annotation`, `Recommendation`, `Redirect`, and `DecisionEvent`.
- `test_contract_registry_discovers_dataclass_fields` — Asserts registered dataclass field names come from `dataclasses.fields()` and include current fields such as `SavedReview.detail_bundle_fingerprint_present` and `Recommendation.anchor`.
- `test_saved_review_schema_version_alias_is_registered` — Asserts `SavedReview.schema_version` maps to persisted JSON key `version`.
- `test_saved_review_path_is_registered_as_in_memory_only` — Asserts `SavedReview.path` is explicitly excluded from persisted JSON keys but still documented as in-memory only.
- `test_intentional_exclusion_requires_reason` — Asserts an intentionally undocumented serialized field must carry owner, field/key, and rationale in the registry.
- `test_update_annotation_preserves_saved_review_contract_keys` — Asserts `update_annotation` retains registered persisted `SavedReview` keys such as `detail_bundle_fingerprint` and `detail_bundle_fingerprint_present` while updating annotations.
- `test_every_persisted_field_is_documented_in_own_section` — Asserts every registered persisted dataclass field appears in its registered `DATA_CONTRACT.md` section.
- `test_schema_constants_are_documented_from_registry` — Asserts `SCHEMA_VERSION` and `TELEMETRY_SCHEMA_VERSION` are named in the expected doc sections.
- `test_plan_manifest_contract_is_documented_from_registry` — Asserts the `DATA_CONTRACT.md:Plan manifest` section names `.plan-tool/plans.json`, `plans`, and repo-relative path strings based on the registered `plan_tool/locator.py` contract.
- `test_grounding_contract_is_documented_from_registry` — Asserts the `DATA_CONTRACT.md` grounding section names the registered `plan_tool/grounding.py:Grounding` fields and sidecar purpose.
- `test_project_config_contract_is_documented_from_registry` — Asserts the `DATA_CONTRACT.md` config section names the registered `.plan-tool/config.json` / user config paths and current durable keys.
- `test_stale_documented_field_fails_contract_check` — Asserts a doc-only field in a registered section is reported as stale rather than ignored.
- `test_obsolete_contract_section_fails_contract_check` — Asserts a contract section for an unregistered owner is reported as obsolete unless explicitly allowed.
- `test_drift_record_contains_apply_payload` — Asserts a missing, stale, or intentionally excluded contract finding carries target section, operation, registry fingerprint, contract fingerprint, and candidate field metadata for `data-contract-apply`.
- `test_report_kinds_documented` — Keep or adapt the existing check for `detail-reconcile`, `run-reconcile`, and `completeness`.
- `test_create_granularity_context_keys_documented` — Keep the existing per-kind telemetry context-key guard.
- `test_plan_criteria_context_keys_documented` — Keep the existing plan criteria telemetry context-key guard.

### Test-creation order (feature step)

Add the registry-focused tests first in `tests/test_data_contract.py`, then implement `plan_tool/data_contract.py` until those tests can import the registry and inspect current classes. Next, convert the existing broad doc tests to use section-aware checks and update `DATA_CONTRACT.md` only for real doc gaps the stricter tests reveal. The green-before-done gate is that every new and existing test in `tests/test_data_contract.py` passes, along with the focused persistence and locator suites that cover the source symbols: `tests/test_review_persistence.py`, `tests/test_telemetry.py`, and `tests/test_locator.py`.

## Acceptance criteria

- `plan_tool/data_contract.py` exists and exports a registry for persisted dataclass contracts and JSON object contracts.
- `tests/test_data_contract.py` no longer owns a standalone `_PERSISTED_DATACLASSES` list; it consumes the registry from `plan_tool/data_contract.py`.
- `SavedReview.schema_version` is checked as persisted JSON key `version`.
- `SavedReview.path` is checked as documented but not persisted.
- `update_annotation` preserves registered persisted `SavedReview` keys when rewriting a saved review sidecar.
- Fields for `SavedReview`, `Annotation`, `Recommendation`, `Redirect`, and `DecisionEvent` are checked inside their own `DATA_CONTRACT.md` sections.
- The plan manifest contract tied to `plan_tool/locator.py:DEFAULT_MANIFEST_SUBPATH` and `plan_tool/locator.py:load_manifest_plan_paths` is checked from the registry.
- The grounding sidecar contract tied to `plan_tool/grounding.py:Grounding` is checked from the registry.
- The project/user config contract tied to `plan_tool/project_config.py` is checked from the registry.
- Stale documented fields and obsolete contract sections fail the data-contract test instead of being ignored.
- Intentionally undocumented serialized fields are represented in an explicit registry exclusion list with a rationale and are mirrored in `DATA_CONTRACT.md`.
- Data-contract drift records expose structured apply payloads and freshness fingerprints; free-form recommendation prose is not the only input to `data-contract-apply`.
- `SCHEMA_VERSION` and `TELEMETRY_SCHEMA_VERSION` remain unchanged.
- `pytest tests/test_data_contract.py tests/test_review_persistence.py tests/test_telemetry.py tests/test_locator.py tests/test_grounding.py tests/test_project_config.py` passes.

## References

- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Use `dataclasses.fields()` for field discovery without hand-copying persisted shapes into tests.
- [Python json](https://docs.python.org/3/library/json.html) — Use for the manifest and sidecar JSON shape assumptions the registry documents.
- [CommonMark Specification](https://spec.commonmark.org/) — Use for predictable Markdown heading parsing in section-aware doc tests.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Use for parametrized drift tests and clear assertion messages.

## Deferred

- `plan_tool/locator.py:load_known_roots` cache contract — Leave the best-effort `~/.plan-tool/.plan-tool/git-roots.json` cache out of the application data contract unless a later step decides caches should be documented and drift-guarded.
- Static AST validation of every code reference in `DATA_CONTRACT.md` — Useful later, but this step should focus on registered persisted shapes and manifest keys, not a general Markdown-to-code linker.
