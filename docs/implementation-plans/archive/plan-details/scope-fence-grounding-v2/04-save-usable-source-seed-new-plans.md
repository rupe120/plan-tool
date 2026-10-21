# Step 4 — Save a usable source seed with new plans

## Summary

Add optional `Plan.source_seed` provenance for plans created from a verified existing seed. Update `plan_tool/create.py` and `plan_tool/cli/authoring.py` so the stored path follows the actual seed used for body and guardrail input and remains readable after archival. Document the frontmatter field in `PLAN_FORMAT.md` and cover schema serialization plus normal, canonical, collision, and archive-failure paths. On green, a seeded plan has a safe repo-relative pointer to a readable source file; plans without trustworthy seed provenance omit the field.

## Table of Contents

- [Summary](#summary) — The provenance behavior delivered by this step.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why later audit work needs a durable seed pointer.
- [Input](#input) — Existing create, canonical-provenance, archival, and serialization contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Rules for selecting and persisting a usable seed path.
- [Tests](#tests) — Regression coverage for creation and serialization paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for paths and Pydantic serialization.
- [Deferred](#deferred) — Later consumers of the stored provenance.

## Why

`plan_tool/cli/authoring.py:cmd_create` reads a supplied seed and can follow `plan_tool/cli/authoring.py:_read_seed_body` to an original canonical-provenance source, but the created `Plan` loses that connection. The command then archives input files, so retaining the pre-archive path would give later work a broken pointer. Step 2 establishes which guardrail text enters the created plan; this step preserves a trustworthy link to the source that supplied that contract.

## Input

- **Seed selection** — `plan_tool/cli/authoring.py:cmd_create` passes `source_path`, `description`, and `_read_seed_body` output into `plan_tool/create.py:create_plan`. When `plan_tool/canonical.py:read_canonical_provenance` identifies a separate original seed, use that explicit target rather than treating the canonical wrapper as the source contract.

- **Archive outcome** — `plan_tool/create.py:archive_existing_source` returns `ArchiveResult.archived` and `ArchiveResult.skipped`. Only an actual archived pair, or a still-readable original file, can prove a usable stored path.

- **Plan serialization** — `plan_tool/parser.py:write_plan` serializes `Plan` with unset defaults and `None` values omitted. The new field must remain optional so existing plans keep parsing and rewriting unchanged.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — add `source_seed` to the frontmatter shape, semantics, defaults, and validation notes.
  - `plan_tool/cli/authoring.py` — carry the resolved seed through archival and persist only the verified durable location.
  - `plan_tool/create.py` — expose the actual seed selected by `create_plan` to the authoring handoff without guessing from plan metadata.
  - `plan_tool/schema.py` — add the optional `Plan.source_seed` frontmatter field.
  - `tests/cli/test_authoring_cmds.py` — cover canonical-provenance seed selection and archive-to-plan persistence at the authoring seam.
  - `tests/test_create.py` — cover seeded creation, archive collisions, and archive-failure fallback behavior.
  - `tests/test_parser.py` — cover `source_seed` parsing, round-trip serialization, and omission when unset.

## Implementation

- **Foundational logic: persist only a verified durable source seed.** A newly created plan may record `source_seed` only when it names the repository-relative file that actually supplied its body and guardrail input and that file is readable after creation finishes.

- **Add an optional plan-level field.** Add `source_seed: Optional[str] = None` near `Plan.registered_by` in `plan_tool/schema.py:Plan`. Keep the schema strict for unknown fields, but do not make legacy plans supply provenance.

- **Use explicit provenance, never discovery.** Start from `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/cli/authoring.py:_read_seed_body`. For a canonical input whose `CanonicalProvenance.source` points to the original seed, record that verified original source, not the canonical wrapper. For a direct `--from-existing` input, use only that explicitly supplied file. Do not search by slug, scan `plan-seeds`, or manufacture a likely source path.

- **Store a portable path.** Convert a verified in-repository source to a repo-root-relative POSIX path before assigning `Plan.source_seed`. Never serialize an absolute path, a path outside the selected repository, or an escaping relative path.

- **Make archival part of the provenance decision.** `create_plan` writes the plan before `cmd_create` calls `archive_existing_source`, so carry enough source identity through `CreateResult` or an equivalent bounded handoff for `cmd_create` to update the written plan after archival. Prefer the actual destination returned in `ArchiveResult.archived`; reject the tempting alternative of deriving `archive/<name>.replaced.md`, because collision-safe archive naming is owned by `_archive_targets`.

- **Fail closed on uncertain archival.** If archival does not prove a readable in-repository destination, retain the original path only when it is still readable and safely relative to `repo_root`; otherwise leave `source_seed` unset. A failed or partial archive must not leave a speculative pointer in frontmatter.

- **Keep normal create behavior intact.** Blank-skeleton and `--from` creation have no file-backed seed and must omit `source_seed`. The multi-plan return from `plan_tool/create.py:create_plan` writes no plan, so it must not create provenance.

- **Preserve serialization compatibility.** Let `plan_tool/parser.py:write_plan` continue to own YAML rendering. A populated `source_seed` must survive parse/write round trips; `None` must remain absent from rewritten frontmatter.

- **Document the boundary.** In `PLAN_FORMAT.md`, state that `source_seed` is optional, repo-relative provenance for a verified source used by `create --from-existing`, may point at its durable archive location, and is omitted when the source cannot be safely retained. State that parsing validates the field shape, while create-time path verification establishes whether it is written.

## Tests

- `test_from_existing_records_readable_repo_relative_source_seed` — a direct in-repository seed produces a plan whose stored path is readable after the command completes.
- `test_canonical_provenance_records_originating_seed_not_wrapper` — an explicit canonical `source` pointer records the archived original seed that supplied the body and guardrails.
- `test_collision_safe_archive_destination_is_recorded` — collision numbering from `archive_existing_source` is reflected in `source_seed`, not reconstructed by the caller.
- `test_archive_failure_keeps_only_verified_source_seed` — a skipped or partial archive keeps a readable original path or omits the field, never a guessed destination.
- `test_non_file_backed_create_omits_source_seed` — blank and `--from` creation leave the frontmatter key absent.
- `test_source_seed_round_trips_through_write_plan` — a populated field survives `parse_plan` and `write_plan`.
- `test_unset_source_seed_is_omitted_on_write` — legacy or newly unseeded plans do not gain the key during serialization.
- `test_plan_format_documents_source_seed_contract` — `PLAN_FORMAT.md` matches the optional schema field and durable-path rule.

### Test-creation order (feature step)

1. Add the `tests/test_parser.py` schema and serialization cases with the `Plan.source_seed` field.

2. Add the `tests/test_create.py` source-selection and archive-outcome cases with the create handoff.

3. Add the `tests/cli/test_authoring_cmds.py` canonical-provenance and command-level persistence cases after wiring `cmd_create`.

4. Add the `PLAN_FORMAT.md` contract check once the documented behavior is settled.

5. Every new test must be green before this step is considered finished.

## Acceptance criteria

- A created plan records `source_seed` only when it names a readable file under the selected repository root.

- A canonical input with an explicit provenance source records the original seed used for body and guardrail input, not its canonical wrapper.

- A successful archive records the exact returned archive destination, including collision-safe names.

- An archive failure leaves `source_seed` pointing at a verified readable original file or omits it.

- `source_seed` is repo-relative and never an absolute, outside-repository, guessed, or unreadable path.

- Plans created without an explicit file-backed seed omit `source_seed`.

- Existing plans without `source_seed` parse and rewrite without gaining the key.

- `PLAN_FORMAT.md`, `tests/test_create.py`, `tests/test_parser.py`, and `tests/cli/test_authoring_cmds.py` pass with the documented contract.

## References

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Review optional model fields and strict model configuration.
- [Pydantic Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) — Review omission of unset and `None` fields during serialization.
- [pathlib — Python Standard Library](https://docs.python.org/3/library/pathlib.html) — Review path resolution, containment checks, and repo-relative conversion.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Review the YAML behavior used by plan frontmatter serialization.

## Deferred

- `completeness-audit --seed` — step 5 owns the explicit operator override for plans without stored provenance.

- Scope-contract prompt grounding — step 6 consumes `Plan.source_seed`; this step only records durable provenance.
