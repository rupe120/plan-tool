# Step 12 — Block direct production concept writes

## Summary

Add an architecture regression guard in `tests/test_concept_sync.py` that rejects production code which writes a final concept sidecar outside the concept publication authority. The guard covers `plan_tool/concept_tree.py:save_concepts`, its `write_concepts` alias, and filesystem mutations of paths derived from `plan_tool/concept_tree.py:concepts_path`. Use syntax-aware inspection with a small explicit allowlist instead of a name-only text search. On green, the production routes delivered by steps 4, 7, 9, and 11 cannot silently return to direct `concepts.json` writes.

## Table of Contents

- [Summary](#summary) — The regression guard and its observable result.
- [Why](#why) — Why the publication boundary needs mechanical enforcement.
- [Input](#input) — The dependency outcomes and current persistence surfaces the guard checks.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single test file changed by this step.
- [Implementation](#implementation) — The required scan coverage, allowlist, and failure reporting.
- [Tests](#tests) — Focused cases for the architectural predicate.
- [Acceptance criteria](#acceptance-criteria) — Checkable proof that direct production writes are blocked.
- [References](#references) — Primary documentation for syntax-aware source inspection.
- [Deferred](#deferred) — Related work intentionally left outside this test-only step.

## Why

Steps 4, 7, 9, and 11 route scope review, create, detail, and scope-out publication through the shared authority, but that boundary can regress without a repository-wide check. Scanning only calls named `save_concepts` is incomplete because `plan_tool/concept_tree.py:write_concepts` aliases the same writer and a caller can mutate the final sidecar through `plan_tool/concept_tree.py:concepts_path` plus `Path.write_text`, `Path.unlink`, `open` in a write mode, or another filesystem helper. A syntax-aware guard makes “one production concept writer” an enforced rule rather than a convention.

## Input

- **Step 4 outcome:** `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` publishes reviewed concepts through the concept authority.
- **Step 7 outcome:** `plan_tool/create.py:create_plan` publishes final signed and unsigned create results through the concept authority; its separate create-resume storage is not a final `concepts_path` write.
- **Step 9 outcome:** `plan_tool/detail.py:generate_detail` publishes detail files and concept deferral changes together through the concept authority.
- **Step 11 outcome:** `plan_tool/scope_out.py:apply_narrow` publishes the narrowed plan and concept changes through the concept authority.
- `plan_tool/concept_tree.py:save_concepts`, `plan_tool/concept_tree.py:write_concepts`, and `plan_tool/concept_tree.py:concepts_path` define the low-level surfaces a caller could misuse. Their definitions may remain for serialization, bootstrap, and tests; production call sites must follow the explicit allowlist.
- `plan_tool/concept_sync.py:synchronize_concepts` is the current guarded publication anchor. Steps 2 and 3 may replace or supplement it with typed intents and the all-or-recoverable coordinator; the guard should allow the authority delivered by those dependency steps without restating its internal design.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `tests/test_concept_sync.py` — add the production-source inspection helper, focused detector cases, and the repository-wide assertion that only approved publication symbols can mutate a final concept sidecar.

## Implementation

The foundational logic is: **reject any production mutation of the final concept sidecar unless it occurs inside an explicitly approved concept publication symbol**.

- **Inspect all production Python modules.** Walk `plan_tool/**/*.py`, parse each file, and report every forbidden occurrence with its full repo-root-relative path and enclosing symbol. Do not limit the check to the four known callers; a new production module must be covered automatically.

- **Use syntax-aware matching.** An AST-based helper is the recommended approach because it can distinguish imports, aliases, calls, assignments, reads, and mutations. A plain substring or regular-expression scan is not sufficient: it can miss renamed imports and cannot reliably tell `concepts_path(...).is_file()` from `concepts_path(...).unlink()`.

- **Cover the low-level writer names.** Reject production imports, aliases, attribute access, or calls that reach `plan_tool/concept_tree.py:save_concepts` or `plan_tool/concept_tree.py:write_concepts` outside the approved authority. Resolve common import shapes such as direct imports with `as`, module imports, and calls through the imported module.

- **Cover raw final-sidecar mutation.** Track direct expressions and simple local aliases derived from `plan_tool/concept_tree.py:concepts_path`. Reject their use as mutation targets, including `Path.write_text`, `Path.write_bytes`, `Path.unlink`, rename/replace operations, write-capable `open` calls, and project filesystem writers. Reads such as `Path.read_text`, `Path.exists`, and `Path.is_file` remain valid.

- **Catch direct chained calls and assigned paths.** Both `concepts_path(plan_path).unlink()` and `sidecar = concepts_path(plan_path); sidecar.write_text(...)` must fail. Include the equivalent module-qualified and import-aliased forms in the detector’s focused cases.

- **Keep the allowlist narrow and symbolic.** Allow the low-level serializer definition in `plan_tool/concept_tree.py:save_concepts` and the final publication or recovery symbols delivered in `plan_tool/concept_sync.py` by steps 2 and 3. Prefer `(repo-root path, enclosing symbol)` entries over allowing an entire module, so an unrelated helper added beside the coordinator does not gain write authority automatically.

- **Keep tests outside the production restriction.** Existing tests use `plan_tool/concept_tree.py:save_concepts` to arrange fixtures. Scan `plan_tool/`, not `tests/`, so fixture setup remains available without weakening the production rule.

- **Treat create-resume storage separately.** Step 7 may write unsigned progress under its dedicated resume namespace. The guard should identify the final sidecar through `concepts_path` or the canonical `concepts.json` target, not ban every concept-related JSON write.

- **Fail with useful evidence.** Return or assert a deterministic list of violations containing the production path, enclosing symbol, and detected mutation form. Sort findings so CI output is stable and a developer can update the caller or, after review, the symbolic allowlist.

- **Do not change production code in this step.** If the repository-wide assertion finds a bypass left by steps 4, 7, 9, or 11, fix it in that dependency’s owning implementation step. `tests/test_concept_sync.py` must not weaken the rule to make an unexpected caller pass.

## Tests

- `test_direct_concept_write_detector_rejects_low_level_writer_aliases` — rejects direct, renamed-import, module-qualified, and `write_concepts` alias calls outside the authority.
- `test_direct_concept_write_detector_rejects_raw_sidecar_mutations` — rejects chained and assigned-path writes, deletion, write-mode `open`, and replacement of a path derived from `concepts_path`.
- `test_direct_concept_write_detector_allows_sidecar_reads` — accepts existence checks and reads through `concepts_path`.
- `test_direct_concept_write_detector_allows_only_named_authority_symbols` — accepts the approved serializer/publication symbols but rejects an unrelated function in the same production module.
- `test_production_concept_writes_use_publication_authority` — scans every `plan_tool/**/*.py` file and reports no direct final-sidecar writers outside the explicit allowlist.

### Verification (non-code step)

- Run `pytest tests/test_concept_sync.py`.
- Run the detector-focused cases against small parsed source snippets so each bypass form is proven detectable independently of the current repository contents.
- Confirm the repository-wide case discovers production files recursively rather than using a fixed caller list.
- Confirm each allowlist entry points to a real path and enclosing symbol at HEAD.
- Confirm removing an approved authority entry makes the repository-wide assertion fail at the authority’s real publication site.
- Confirm adding a synthetic direct writer under `plan_tool/` makes the guard fail with its full repo-root-relative path and enclosing symbol.
- Run the full test suite, data-contract drift checks, and `reconcile-code` after all dependency steps have landed.

## Acceptance criteria

- `tests/test_concept_sync.py` scans every checked-in Python module under `plan_tool/` for direct final concept-sidecar mutations.
- The guard rejects production use of both `save_concepts` and the `write_concepts` alias outside explicitly named authority symbols.
- The guard rejects direct and locally aliased mutation of paths returned by `concepts_path`, including write, delete, and replacement forms.
- The guard permits read-only use of `concepts_path`.
- The allowlist is expressed as full repo-root-relative paths plus enclosing symbols; it does not grant permission to an entire caller module.
- `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, `plan_tool/create.py:create_plan`, `plan_tool/detail.py:generate_detail`, and `plan_tool/scope_out.py:apply_narrow` produce no violations.
- A violation report names the full production path, enclosing symbol, and detected write form in deterministic order.
- `pytest tests/test_concept_sync.py` passes without modifying production files.

## References

- [Python 3.13 `ast` — Abstract Syntax Trees](https://docs.python.org/3.13/library/ast.html) — Use `ast.parse`, node types, and tree traversal to inspect imports, aliases, calls, and path mutations without executing production modules.

## Deferred

- Removing `plan_tool/concept_tree.py:save_concepts` or its `write_concepts` compatibility alias — the low-level serializer may remain for explicit bootstrap and test use.
- A general repository-wide filesystem authority framework — this guard is limited to final concept-sidecar publication.
- Fixing a production bypass found after dependency implementation — route the fix to the step that owns the affected production file rather than expanding this test-only step.
