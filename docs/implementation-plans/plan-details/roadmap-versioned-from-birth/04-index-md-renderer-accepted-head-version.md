# Step 4 — Add the INDEX.md renderer for the accepted head and version lineage

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds `plan_tool/roadmap_index.py`, a leaf module that owns the content of the roadmap folder's `INDEX.md`. It reads the version store and returns one markdown string, and it can write that string to `<roadmap folder>/INDEX.md`. The string links the accepted head's four artifacts. It also lists every stored version in lineage order with its short id, kind, status, predecessor, and the feedback items it answered. The key design decision is that each version gets exactly one status by a fixed precedence, with `unrecorded` last, so a crash-orphaned version is listed and never blocks the rest of the file. On green, `tests/test_roadmap_index.py` shows the rendering and every status. Step 5 owns every call site, so nothing in the repo calls this module yet.

## Table of Contents

- [Why](#why) — what a person browsing the folder cannot see today
- [Input](#input) — the store records the renderer reads and what the tests cannot prove
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — API shape, status precedence, ordering, import rule
- [Tests](#tests) — cases per behavior and invariant
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to other steps

## Why

- A roadmap folder holds only `.roadmap-versions/` JSON, a ledger, and seed files. A person cannot tell which version is current or what happened to a candidate without opening the store's JSON.
- The plan's "`INDEX.md`" bullet in `## Architecture` requires one generated, human-facing index that no command reads. Building the renderer on its own lets step 5 wire it into every commit point without also designing its content.
- Status is not stored in one place. It comes from the head selector, the admission pointer, terminal-resolution records, and supersession records. One owner for that precedence stops each caller from re-deriving it.

## Input

- **Step 1 output:** the `BACKLOG.md` #441 record. It confirms that nothing reads `INDEX.md`. Take that statement from the record.
- **Version store (`plan_tool/roadmap_versions.py`):** `version_namespace_path`, `accepted_head_path`, `load_accepted_head` (returns `AcceptedRoadmapHead | None`), `load_stored_version` and `StoredRoadmapVersion` (`version_id`, `version_kind`, `predecessor_version_id`, `artifact_members`), `artifact_member_name`, `VERSION_ARTIFACT_KEYS`, `RoadmapVersionError`.
- **Status records written by `plan_tool/roadmap_candidate_run.py`:**
  - `candidate-admission.json` in the namespace root. Its `active_candidate_version_id` names the active candidate, or is null once released. A selector-era record has no such key.
  - `candidate-terminal-resolutions/<version_id>.json`, with a `reason` of `rejected`, `discarded`, or `settled`.
  - `candidate-supersessions/<superseded_version_id>.json`.
  - `candidate-evidence.json` inside each candidate's version directory. The feedback items come from `batch_receipt.reviewer_items[].item_id` for a batch candidate, or `feedback.feedback_id` for a selector-era candidate.
  - Read the real directory and file names from the `_*_DIRECTORY` / `_*_FILENAME` constants and path helpers in that module. The names above are orientation.
- **Limit:** unit tests build a store from small literal records. They cannot show that a store produced by the real candidate and promotion commands renders correctly. Step 5 owns that seam.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_index.py`
  - `tests/test_roadmap_index.py`
- **Existing files (edits only):** none.

## Implementation

**Behavior that must hold when the step is done:**

- **One owner.** This module is the only code that builds `INDEX.md` content or decides a version's status.
- **Pure render, thin read.** Split the work in two: a pure function over already-read rows that returns the markdown, and a function that reads the store and calls it. Tests drive the pure function with literal rows.
- **Recommended API (names are a recommendation, shapes are the constraint):**
  - `IndexVersionRow` — frozen dataclass with the full version id, kind, status, predecessor id or `None`, and a tuple of answered feedback item ids.
  - `classify_version_status(...)` — the precedence rule, one call per version.
  - `render_roadmap_index(slug, head_version_id, rows, ...) -> str`.
  - `collect_index_rows(plans_dir, slug)` — reads the store.
  - `write_roadmap_index(plans_dir, slug)` — replaces `<roadmap_dir>/INDEX.md` whole through `plan_tool/fileio.py:atomic_write_text`.
- **Status precedence, top to bottom, first match wins:**
  - `accepted head` — the version id in `accepted-head.json`.
  - `promoted` — an ancestor of the head on its predecessor chain. This outranks `superseded`: a stack hop that was superseded when the stack grew is still promoted with it.
  - `active` — equals `active_candidate_version_id`.
  - `rejected` / `discarded` / `settled` — the terminal record's `reason`.
  - `superseded` — has a supersession record.
  - `unrecorded` — none of the above. A version with no status record is listed this way, and every other row still renders.
- **No head.** A folder with no accepted head has no meaningful index. Return or raise a named result for it, and let step 5 decide whether to call at all. Do not write an index with no head link.
- **Head links.** Link each of the four artifacts of the head through `VERSION_ARTIFACT_KEYS` and `artifact_member_name`, as paths relative to the roadmap folder. Do not hardcode the member file names.
- **Lineage order.** Root first. Order the rest by predecessor-chain depth from the root, then by version id for ties. No dates or timestamps appear anywhere, and no clock is read.
- **Row content.** Show the first 8 characters of the version id as the short id, plus the kind, status, short predecessor id (or `—` for a root), and the answered feedback ids (or `none`). Per the repo's explicit-over-implicit rule, an empty cell says so.
- **Version discovery.** List version directories under `version_namespace_path` that hold `version.json`. Skip the two record directories and any file.
- **Import rule — this is the key constraint.** `plan_tool/roadmap_candidate_run.py` imports `plan_tool.roadmap`, and step 5 makes `plan_tool/roadmap.py` call this module. Importing `roadmap_candidate_run` here would create a `roadmap` ↔ `roadmap_index` cycle.
  - Allowed first-party imports: `plan_tool.roadmap_versions`, `plan_tool.roadmap_artifacts`, `plan_tool.fileio`.
  - For the admission, terminal, supersession, and evidence files, read the few fields needed straight from the JSON, and mirror the directory and file names as module constants. Do not import them.
  - The mirrored names are pinned by a test that compares them with the `roadmap_candidate_run.py` path helpers. This is the repo's mirror-don't-import practice for leaves; consolidating is out of scope.
- **Failure behavior.** A malformed store record raises `RoadmapVersionError` or a module-named error. Do not swallow it here. Step 5 owns the "warn and never roll back" policy.
- **Smallest mechanism.** No template engine, no configurable columns, no pagination.

## Tests

All cases in `tests/test_roadmap_index.py`. The suite builds a store on `tmp_path` with the real `roadmap_versions` writers, or small literal JSON for the status records, and drives the pure render with literal rows.

- `test_render_links_the_four_artifacts_of_the_accepted_head` — one link per key in `VERSION_ARTIFACT_KEYS`, with the member names from `artifact_member_name`.
- `test_every_version_gets_exactly_one_status` — over a mixed store, each version appears once with one status value.
- `test_head_is_listed_as_accepted_head_and_ancestors_as_promoted` — head and predecessor chain statuses.
- `test_superseded_stack_hop_that_was_promoted_reads_promoted` — pins that `promoted` outranks `superseded`, the stack-hop case the plan names.
- `test_active_candidate_reads_active` — the admission pointer sets `active`.
- `test_terminal_reasons_render_as_rejected_discarded_settled` — one case per reason.
- `test_superseded_candidate_that_is_not_promoted_reads_superseded` — the plain supersession case.
- `test_version_with_no_status_record_is_listed_unrecorded` — a candidate stored with no admission, terminal, supersession, or head record gets `unrecorded`.
- `test_unrecorded_version_does_not_stop_the_rest_of_the_index` — the other rows and the head links are still rendered.
- `test_selector_era_admission_without_pointer_keys_is_readable` — an admission with no `active_candidate_version_id` key renders without error.
- `test_answered_feedback_ids_come_from_batch_and_selector_evidence` — both evidence shapes, plus an explicit "none" for a root.
- `test_lineage_order_is_root_first_then_depth_then_id` — fixed order, with a sibling tie broken by id.
- `test_render_contains_no_date_or_timestamp` — pins the plan's no-dates fence on the output.
- `test_render_is_deterministic_for_the_same_store` — two renders match byte for byte.
- `test_no_head_is_a_named_refusal_not_an_empty_index` — the no-head result.
- `test_write_replaces_the_whole_file` — a stale longer `INDEX.md` is fully replaced.
- `test_mirrored_record_names_match_candidate_run_path_helpers` — compares this module's constants with the `roadmap_candidate_run.py` path helpers; it must fail if either side is renamed.
- `test_module_imports_no_roadmap_orchestrator` — a subprocess `sys.modules` check plus a source-text scan that `plan_tool.roadmap` and `plan_tool.roadmap_candidate_run` are never imported, including inside a function. Both idioms are needed because only the source scan sees a lazy import.

### Tests for this step

Every case above must be green before the step is finished. Verify the two carve-outs by mutation: swap the `promoted` and `superseded` branches and watch `test_superseded_stack_hop_that_was_promoted_reads_promoted` go red; make `unrecorded` raise and watch `test_unrecorded_version_does_not_stop_the_rest_of_the_index` go red.

## Acceptance criteria

- `plan_tool/roadmap_index.py` exists and is the only module that builds `INDEX.md` content.
- The rendered text links the head's four artifacts and lists every stored version once.
- Each version's status follows the precedence order above, and a version with no record reads `unrecorded`.
- The rest of the file is written when an `unrecorded` version is present.
- The output contains no date or timestamp and is identical across two renders of one store.
- `rg 'roadmap_candidate_run|plan_tool\.roadmap import|from plan_tool import roadmap\b' plan_tool/roadmap_index.py` returns nothing.
- `rg 'roadmap_index' plan_tool --glob '!plan_tool/roadmap_index.py'` returns nothing, because step 5 owns every call.
- `uv run pytest tests/test_roadmap_index.py -q` is green, and `tests/test_duplication.py` stays green.

## References

- `BACKLOG.md` #441 — source entry and scope contract.
- `docs/implementation-plans/2-roadmap-versioned-from-birth.md` § `## Architecture`, the "`INDEX.md`" bullet — status table and precedence.
- `plan_tool/roadmap_versions.py` — `load_accepted_head`, `load_stored_version`, `version_namespace_path`, `artifact_member_name`.
- `plan_tool/roadmap_candidate_run.py` — admission, terminal-resolution, supersession, and evidence path helpers.
- `plan_tool/fileio.py:atomic_write_text` — the write helper.

## Applicable guardrails

- **The plan's "`## Out of scope`", dates or timestamps:** this step must not put a date, timestamp, or clock read in `INDEX.md` or in any record it reads or writes.
- **The plan's "`## Out of scope`", record contracts:** this step reads the candidate, terminal, supersession, admission, and version records and must not change any of their schemas.
- **The plan's "`## Out of scope`", read-only mirror:** `INDEX.md` links to stored artifacts and must not copy their content into the folder.
- **The plan's `INDEX.md` bullet, "No command reads it":** this module only writes; nothing in it parses `INDEX.md`, and the tests must not either, beyond checking the rendered string.
- **Step intent:** the index exists so a person can find the current version and every version's status. It must not grow into a diff view, a comparison, or a review summary.

## Deferred

- Calling the renderer after each version-store change, the best-effort warn-on-failure policy, and the post-head refusal path rewrite — step 5 owns every call site.
- Handling a no-head folder at the command level — step 5 and step 3 own the refusals.
- Documenting `INDEX.md` in `docs/how-to/roadmap.md` and `ROADMAP_FORMAT.md` — the plan's docs step owns it.
- Consolidating the mirrored record names with `plan_tool/roadmap_candidate_run.py` — a cross-module refactor, not a feature step; file it on `BACKLOG.md` if it recurs.
