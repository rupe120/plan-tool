# Step 2 — Add the resume module that owns the first-run resume directory

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds `plan_tool/roadmap_stage_resume.py`, a small leaf module. It is the only code that knows the path, layout, and lifecycle of the first-run resume directory at `.plan-tool/runs/<slug>/roadmap-stage-resume/`. The directory holds one text file per gate-clean stage and one file with the brief digest. The module exposes a path helper, a digest write, a per-stage write, a read that reports what it could read, a delete, and a brief-digest check. A stage file that cannot be read is reported as missing with a warning, never raised, so a damaged stage costs only its own regeneration. Only a brief-digest mismatch raises, as one named error that names the directory and states the operator's remedy. On green, step 3 can resume a failed first run through this API without touching a file or path itself. `tests/test_roadmap_stage_resume.py` covers the round trip, the damaged-file cases, the one refusal, and the module's leaf discipline.

## Table of Contents

- [Why](#why) — why one module owns the directory and why per-stage files
- [Input](#input) — what step 1 confirms and what this module reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — API shape, layout, the one refusal, constraints
- [Tests](#tests) — cases per behavior and invariant
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

- The plan removes every top-level `0N-*.md` write. A failed first run still needs somewhere durable to keep its gate-clean stages, or a stage-4 failure repeats the backend calls for stages 1–3 (about 21k output tokens and 90k input tokens, roughly seven minutes, measured from Integration's roadmap run logs).
- One file per stage means a damaged or hand-edited stage invalidates only itself and the stages after it. A single combined file would turn any damage into a whole-file question with its own refusal rule.
- The plan's Architecture states "Only the stage run reads it; one module owns its path." The plan's guard step (step 11) searches production code for reads of the directory outside the stage run. That guard is only checkable if the path and parsing live in one module.
- This step builds the module and its tests alone. Step 3 wires it into `plan_tool/roadmap.py`, so this step can be tested without driving the stage loop.

## Input

- **Step 1 output:** the confirmed run-directory layout under `.plan-tool/runs/<slug>/` and the statement that no other route reads the directory. Take the layout from the #441 record, not from this detail.
- **Path root:** `plan_tool/run_log.py:run_dir(repo_root, slug)` gives `<repo_root>/.plan-tool/runs/<slug>/`. That directory also holds `<run_id>.jsonl` logs and the in-flight snapshot (`in_flight_path`). The resume directory is a subdirectory with a name that matches neither. Confirm by reading `plan_tool/run_log.py` that nothing globs or removes subdirectories of the run directory in a way that would touch it.
- **Digest:** step 3 supplies the brief digest as a lowercase SHA-256 hex string. `plan_tool/roadmap_source.py:digest_decoded_text` is the existing helper for computing it. This module takes the string and does not compute it.
- **Stage texts:** step 3 supplies the rendered text of each gate-clean stage. This module stores them as given and does not parse them.
- **Limit:** the tests drive the module with literal strings. They cannot show that real stage output round-trips through the real stage parsers or gates. Step 3 owns that seam, including the re-gate that decides whether a held stage is still usable.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_stage_resume.py`
  - `tests/test_roadmap_stage_resume.py`
- **Existing files (edits only):** none.

## Implementation

**Behavior that must hold when the step is done:**

- **One owner.** This module is the only code that builds the resume directory's path, writes or reads its files, or deletes it.
- **Layout.** The directory is `run_dir(repo_root, slug) / RESUME_DIRNAME` with one module constant, for example `RESUME_DIRNAME = "roadmap-stage-resume"`. It holds `brief.digest` (one line, the lowercase SHA-256 hex) and `stage-<N>.md` for each held stage (`N` a positive integer). Plain text only; no JSON.
- **Held stages are contiguous from 1.** The read returns the longest run `stage-1.md, stage-2.md, …` it can read. A gap, an unreadable file, or a file whose name does not match the layout ends the run, and everything from the first problem on is reported as not held.

**Recommended API (names are the recommendation; the shapes are the constraint):**

- `resume_dir_path(repo_root, slug) -> Path` — pure, no filesystem access.
- `write_brief_digest(repo_root, slug, digest)` — writes `brief.digest`.
- `write_stage(repo_root, slug, stage_number, text)` — writes `stage-<N>.md`.
- `HeldStages` — frozen dataclass with `brief_digest: str | None`, `stages: tuple[tuple[int, str], ...]` (ordered, contiguous from 1), and `warnings: tuple[str, ...]`.
- `read_held_stages(repo_root, slug) -> HeldStages | None` — returns `None` only when the directory is absent. Otherwise returns what it could read; every file it could not read or accept adds a warning that names the file path.
- `discard_stages_from(repo_root, slug, first_stage)` — deletes `stage-<first_stage>.md` and every later stage file. Step 3 calls it when a held stage fails its re-gate, so the next stage write does not leave a stale later file behind.
- `delete_resume(repo_root, slug) -> bool` — removes the whole directory; returns whether one was removed. A missing directory is not an error.
- `require_matching_brief_digest(held, brief_digest)` — raises `RoadmapStageResumeBriefChanged` when `held.brief_digest` is a different valid digest. The message names the `roadmap-stage-resume/` directory (never its parent run-log directory, which also holds the run logs) and states the remedy: restore the brief, delete that directory by hand, or start a successor slug.

**Write mechanics:**

- **Atomic write.** Use `plan_tool/fileio.py:atomic_write_text` for every file. It creates the parent directory, so no directory exists before the first write. A failed or interrupted write leaves the previous file, never a half file.
- **Digest first.** Step 3 writes `brief.digest` before the first stage file, so a held stage always has a digest to compare against.
- **No `fsync`.** `atomic_write_text` is not durable, and that is enough here. A lost write costs a re-run of the in-flight stage, which matches the plan's risk statement that the directory "bounds it to the stage in flight".

**The one refusal, and everything that is not one:**

- A brief-digest mismatch raises `RoadmapStageResumeBriefChanged`. Every held stage is stale at once, and only the operator can say whether the brief edit was meant, so this module never discards on a mismatch.
- A missing, unreadable, empty, or malformed `brief.digest` reports a warning and `brief_digest=None`. Step 3 then treats the held stages as unverifiable and regenerates them. An atomic write cannot leave a half file, so this happens only after a hand edit or disk damage.
- An unreadable, empty, or oddly named stage file ends the contiguous run and adds a warning. Nothing is raised and nothing is deleted by the read.
- Whether a held stage still passes its gates is not decided here. Step 3 re-gates each one in memory.

**Checks this module deliberately does not make:**

- It does not parse or gate stage text.
- It does not decide when to delete the directory. Step 3 deletes it after the accepted head commits, or when it finds the directory beside an accepted head.
- It does not know how many stages a roadmap has.
- It does not compute the brief digest.

**Constraints and gotchas:**

- **A read never deletes or rewrites.** Only `discard_stages_from` and `delete_resume` remove files, and only step 3 calls them.
- **Slug check.** Validate the slug before it becomes a path segment by importing the existing `plan_tool/roadmap_artifacts.py:_validate_slug`. Do not define a second copy: `tests/test_duplication.py` fails on an exact duplicate function body, and the repo's rule is to reuse a helper that exists. `plan_tool/roadmap_artifacts.py` imports nothing first-party, so the edge adds no cycle.
- **Leaf discipline.** Import only the standard library, `plan_tool.fileio`, `plan_tool.run_log`, and `plan_tool.roadmap_artifacts` (for the slug check only). Do not import `plan_tool.roadmap_source` or `plan_tool.roadmap`. This keeps the module below the stage run, so step 3 can import it without a cycle.
- **Rejected alternative:** one JSON file holding the digest and every stage. A malformed or hand-edited file then forces a whole-file refusal or a whole-file discard, and the schema validation grows its own list of cases. Per-stage files make the plain "regenerate what is damaged" rule enough.
- **Rejected alternative:** put the directory inside the roadmap folder. The plan forbids anything in the folder before the root version publishes.

## Tests

All cases go in `tests/test_roadmap_stage_resume.py`. Use `tmp_path` as the repo root and build every input from string literals.

**Round trip and path**

- `test_resume_dir_path_is_under_the_run_directory` — the path equals `run_dir(repo_root, slug) / RESUME_DIRNAME`, and the call touches no filesystem.
- `test_resume_dir_name_does_not_collide_with_run_log_names` — the name does not end in `.jsonl` and differs from the in-flight snapshot's file name.
- `test_write_then_read_round_trips_digest_and_stages` — the read returns the digest and the stages in order, with no warnings.
- `test_first_write_creates_the_run_directory_and_a_read_of_a_missing_one_returns_none` — before the first write the directory does not exist, and `read_held_stages` returns `None`.
- `test_rewriting_a_stage_replaces_only_that_file` — a second write of `stage-2.md` leaves `stage-1.md` unchanged.
- `test_write_failure_keeps_the_previous_file` — if the rename step fails (patch `os.replace`), the previous file's bytes are unchanged.

**Damage is regenerated, never raised or deleted by a read**

- `test_unreadable_stage_file_ends_the_held_run_with_a_warning` — `stage-2.md` unreadable: the read returns `stage-1` only, one warning names the `stage-2.md` path, nothing raises, and every file is still on disk.
- `test_gap_in_stage_files_ends_the_held_run` — `stage-1.md` and `stage-3.md` present: only stage 1 is held, and `stage-3.md` is reported as not held.
- `test_empty_stage_file_is_not_held` — an empty `stage-1.md` yields no held stage and a warning.
- `test_oddly_named_file_in_the_directory_is_ignored_with_a_warning` — an unexpected file name adds a warning and changes nothing else.
- `test_missing_digest_file_reads_as_none_digest_with_a_warning` — held stages are returned with `brief_digest=None` and a warning, so step 3 can treat them as unverifiable.
- `test_malformed_digest_reads_as_none_digest_with_a_warning` — an uppercase or short digest does the same.
- `test_a_read_never_deletes_or_rewrites_any_file` — snapshot every file's bytes before and after a read over a damaged directory; they match.

**The one refusal**

- `test_matching_digest_passes` — the check returns without raising.
- `test_changed_brief_digest_refuses_naming_the_directory_and_the_remedy` — a different valid digest raises `RoadmapStageResumeBriefChanged`, the message contains the directory path and each of the three remedies, and no file is removed.
- `test_unverifiable_digest_does_not_raise_the_changed_brief_error` — `brief_digest=None` passes the check, because the caller regenerates instead.

**Discard and delete**

- `test_discard_stages_from_removes_that_stage_and_every_later_one` — `discard_stages_from(.., 2)` removes `stage-2.md` and `stage-3.md` and keeps `stage-1.md` and the digest.
- `test_delete_resume_removes_the_directory_and_reports_true` — returns `True` and the directory is gone.
- `test_delete_of_a_missing_directory_is_not_an_error` — returns `False` without raising.

**Deliberate non-checks (each must parse without raising)**

- `test_stage_text_is_stored_without_parsing` — garbage text (not valid YAML or markdown) round-trips unchanged. Gating is step 3's job.
- `test_any_stage_count_is_accepted` — one stage and a larger contiguous run both read back. The module does not know the stage count.

**Slug safety**

- `test_slug_with_traversal_or_separator_is_rejected` — `..`, a path separator, and the empty string each raise `ValueError` naming the value.

**Leaf discipline (two idioms, per the repo's convention)**

- `test_leaf_imports_no_roadmap_stage_run_module_at_import_time` — a subprocess `sys.modules` check, modeled on `tests/test_jira_grade.py:TestLeafImportDiscipline`, shows that the only `plan_tool.roadmap*` modules loaded are `plan_tool.roadmap_stage_resume` and `plan_tool.roadmap_artifacts`.
- `test_leaf_source_has_no_first_party_import_beyond_the_four_allowed` — a source-text scan, modeled on `tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import`, asserts the first-party imports are exactly `plan_tool.fileio`, `plan_tool.roadmap_artifacts`, and `plan_tool.run_log`, and catches a lazy import inside a function.

**Tests for this step.** All cases above are new, and every one must be green before this step is finished. The plan sets `enforce_step_tests: true` and this is a `feature` step, so the test-authoring gate applies. The roster covers only behavior this module adds.

## Acceptance criteria

- `plan_tool/roadmap_stage_resume.py` exists and defines the path helper, the digest and stage writes, the read, `discard_stages_from`, `delete_resume`, the digest check, and `RoadmapStageResumeBriefChanged`.
- Write then read returns the digest and the stages with order and text unchanged.
- `read_held_stages` returns `None` only when the directory is absent. Every unreadable or oddly named file adds a warning that names its path, ends the contiguous run, and leaves the file on disk. The read never raises for a damaged file.
- A changed brief digest raises the named error naming the directory and stating the remedy, and removes nothing.
- A write never leaves a half-written file, and it creates the run directory only when it writes.
- `rg -n 'roadmap_source|plan_tool\.roadmap\b' plan_tool/roadmap_stage_resume.py` returns nothing, and `rg -n '_validate_slug' plan_tool/roadmap_stage_resume.py` shows an import and calls only, no `def`.
- `rg -n 'input\(|isatty|sys\.exit' plan_tool/roadmap_stage_resume.py` returns nothing.
- No file under the roadmap folder is created or read by this module.
- `uv run pytest tests/test_roadmap_stage_resume.py -q` passes, and `uv run pytest tests/test_duplication.py -q` still passes.

## References

- `BACKLOG.md` #441 — source entry, decision, and scope contract.
- `plan_tool/run_log.py:run_dir` and `in_flight_path` — the directory and a sibling file name to avoid.
- `plan_tool/fileio.py:atomic_write_text` — the write helper and its non-durable contract.
- `plan_tool/roadmap_artifacts.py:_validate_slug` — the slug check to import and reuse.
- `plan_tool/roadmap_source.py:digest_decoded_text` — how step 3 computes the digest this module stores.
- The plan's `## Architecture`, "Resume" bullet, in `docs/implementation-plans/2-roadmap-versioned-from-birth.md` — the lifecycle this module serves.

## Applicable guardrails

- **The plan's "## Out of scope", "A tool-driven migration for existing roadmaps":** the module reads only the directory it owns and never inspects a legacy folder. The legacy-folder refusal belongs to step 3.
- **The plan's "## Out of scope", "Dates or timestamps in `INDEX.md` or version records":** the resume files also carry no timestamps. Their contents are the brief digest and the held stage text only.
- **The plan's "## Out of scope", "Changing the candidate, review-seal, promotion, or version-record contracts":** this module imports none of those modules and changes none of them.
- **The plan's "## Architecture", the no-interactive-surface rule:** a failed read warns or raises and never prompts. The `rg` criteria above make that checkable.

## Deferred

- Wiring the module into the stage run, re-gating held stages, regenerating from the first stage that fails, and choosing when to write and delete the directory — step 3.
- Recovering a pending root-version journal before reading the directory — step 3.
- The guard that no production code reads the directory outside the stage run — step 11.
- Documenting the directory and the brief-digest remedy in `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md` — the plan's docs step.
- Measuring how often held stages survive a re-gate on real briefs — needs real runs the suite cannot supply.
