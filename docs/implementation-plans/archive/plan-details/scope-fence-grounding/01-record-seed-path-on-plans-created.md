# Step 1 — Record the seed path on plans created from an existing file

## Summary

Add optional `source_seed` provenance to the `Plan` frontmatter model and populate it when `plan-tool create --from-existing` creates a plan from a repository file. The change touches `plan_tool/schema.py`, `plan_tool/create.py`, and the archive handoff in `plan_tool/cli/authoring.py`, with coverage in `tests/test_create.py` and documentation updates in `DATA_CONTRACT.md` and `PLAN_FORMAT.md`. Store a repo-relative path to the durable archived seed location, never an absolute path or a guessed match. On green, seeded plans carry a readable `source_seed`, while ordinary creates and existing plans continue to omit the key.

## Table of Contents

- [Summary](#summary) — What this step delivers.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why seed provenance must be explicit.
- [Input](#input) — Existing plan and create contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required provenance behavior and constraints.
- [Tests](#tests) — Coverage for seeded and unseeded creates.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant primary documentation.
- [Deferred](#deferred) — Provenance paths not covered here.

## Why

`plan_tool/schema.py:Plan` has no field that tells later workflows which file supplied a plan’s original scope. `plan_tool/create.py:create_plan` already receives `from_existing_path`, but that information disappears when the plan is written. Persisting explicit provenance gives later audit work a trustworthy starting point without guessing from a slug or scanning `plan-seeds/`.

## Input

- **Plan serialization:** `plan_tool/parser.py:render_plan_text` and `plan_tool/parser.py:write_plan` serialize `Plan` with unset defaults omitted. `source_seed=None` must therefore preserve the frontmatter shape of existing and non-seeded plans.
- **Create input:** `plan_tool/create.py:create_plan` receives `from_existing_path` from `plan_tool/cli/authoring.py:cmd_create`; use that explicit input rather than deriving a path from plan metadata.
- **Archive outcome:** `plan_tool/cli/authoring.py:cmd_create` archives every `--from-existing` source after `create_plan` writes the plan. Persist the archive destination, not the transient source path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/schema.py` — add the optional `Plan.source_seed` frontmatter field.
  - `plan_tool/create.py` — derive and attach seed provenance during `create_plan`.
  - `plan_tool/cli/authoring.py` — replace the provisional source path after archival with the durable archive destination.
  - `tests/test_create.py` — cover seeded, unseeded, and archived-seed create paths.
  - `tests/test_data_contract.py` — guard the documented `source_seed` contract against schema drift.
  - `DATA_CONTRACT.md` — document authored plan seed provenance beside the existing authored-plan metadata contract.
  - `PLAN_FORMAT.md` — add `source_seed` to the frontmatter schema and field semantics.

## Implementation

- **Foundational logic:** bind a plan created from an existing file to the actual originating seed used as its body/guardrail input through an optional repo-relative `source_seed` path.

- **Add an additive field.** Add `source_seed: Optional[str] = None` to `plan_tool/schema.py:Plan`, near the existing plan-level provenance field `registered_by`. Keep it optional so `parse_plan` continues to accept every existing plan unchanged.

- **Write provenance only from explicit input.** In `plan_tool/create.py:create_plan`, derive `source_seed` from `from_existing_path` after the final `repo_root` is known. Use a path relative to that root and store a portable repo-relative string. Do not infer a seed from the new plan’s slug, output directory, or a conventional `plan-seeds/` location.

- **Follow only explicit canonical provenance.** When `plan_tool/cli/authoring.py:_read_seed_body` resolves a canonical input's declared provenance source and uses that file as the body/guardrail input, pass that same resolved source through the create/archive handoff and record its archive destination. Do not treat the canonical wrapper itself as the originating contract, and do not perform any new discovery beyond the existing explicit provenance pointer.

- **Keep the seed reference durable.** Because `cmd_create` archives every `--from-existing` source, replace the provisional path with the archived destination reported through `ArchiveResult.archived` before the command returns. Do not leave a normal or collision seed pointing at its removed original path.

- **Fail closed on archive uncertainty.** Set an archived `source_seed` only when `ArchiveResult.archived` proves the matching source was moved to a readable, repo-relative destination. If archiving is skipped or partially fails but the original input remains readable inside the repository, retain that verified original path; otherwise omit `source_seed`. Never manufacture an archive name from convention or record a path that cannot be read.

- **Do not serialize unsafe provenance.** Never write an absolute path or manufacture a relative path for a seed outside the selected repository root. Preserve the current create behavior for such inputs while leaving provenance unset when there is no safe repo-relative location.

- **Preserve rewrite compatibility.** Rely on the established `Plan.model_dump(exclude_defaults=True, exclude_none=True)` behavior in `plan_tool/parser.py:write_plan` and `plan_tool/parser.py:render_plan_text`: unset `source_seed` must not appear in frontmatter, and a populated value must survive parse/write round trips.

- **Document the authored contract.** Update `DATA_CONTRACT.md` with the optional field, its repo-relative path rule, and its unset behavior. Update `PLAN_FORMAT.md`’s frontmatter example and `source_seed` field semantics to state that `create --from-existing` records explicit provenance and ordinary creation paths do not.

## Tests

- `test_from_existing_records_archived_repo_relative_source_seed` — a plan created from an in-repository `--from-existing` file points at the archive destination that remains readable after the source is moved.
- `test_from_existing_collision_records_archived_source_seed` — a seed archived by the replacement flow leaves the created plan pointing at the archived file, not the removed original.
- `test_canonical_from_existing_records_archived_provenance_source_seed` — when the existing canonical provenance selects an originating seed body, the resulting plan points at that archived originating seed rather than the canonical wrapper.
- `test_from_existing_archive_failure_keeps_only_verified_provenance` — skipped or partial archival retains a still-readable original source path or omits `source_seed`; it never records a speculative archive target.
- `test_non_seed_create_omits_source_seed_frontmatter` — a create without `from_existing_path` writes no `source_seed` key.
- `test_source_seed_round_trips_through_plan_serialization` — a populated `Plan.source_seed` survives parse and rewrite.
- `test_source_seed_contract_documented` — `DATA_CONTRACT.md` names the field, its optional state, and repo-relative provenance rule.
- `test_source_seed_contract_matches_plan_schema` — `Plan.model_fields` exposes `source_seed` with an unset default and the data-contract section documents it.

### Test-creation order (feature step)

1. Add the `tests/test_create.py` seeded-create cases with the implementation, covering the normal archival path and collision archives.
2. Add the unseeded serialization case with the implementation, covering omission of the frontmatter key.
3. Add the `tests/test_data_contract.py` schema/documentation drift cases after the documentation updates.
4. Every new test must be green before this step is considered finished.

## Acceptance criteria

- A plan created with `--from-existing` from a file inside the selected repository has a repo-relative `source_seed` value that names the archived file remaining on disk.
- When archive naming collides, `source_seed` names the collision-safe archived file that remains on disk.
- When archival does not establish a readable destination, `source_seed` is either the verified still-readable original source or omitted; no speculative archive path is serialized.
- A plan created without `--from-existing` omits `source_seed` from serialized frontmatter.
- Existing plans without `source_seed` still parse and rewrite without gaining the key.
- `DATA_CONTRACT.md` and `PLAN_FORMAT.md` describe `source_seed` consistently with `plan_tool/schema.py:Plan`.
- `tests/test_create.py` and `tests/test_data_contract.py` pass.

## References

- [Pydantic Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) — Review default and `None` exclusion behavior used by plan serialization.
- [Python pathlib](https://docs.python.org/3/library/pathlib.html) — Review resolution and repository-relative path conversion.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Review YAML serialization behavior for the new optional frontmatter field.

## Deferred

- `--from` and `--reprocess` provenance — these paths do not supply the explicit existing-file input this step records; later audit override work owns their fallback.
- Seed lookup and scope-contract injection — step 3 consumes `source_seed`; this step only records the provenance.
