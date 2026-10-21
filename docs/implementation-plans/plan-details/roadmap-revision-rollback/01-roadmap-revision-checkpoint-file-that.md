# Step 1 — Add a roadmap revision checkpoint file that records, for every file a stage run can write, its pre-run and last-written bytes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds a new, self-contained leaf module, `plan_tool/roadmap_revision_checkpoint.py`, that gives one roadmap slug a single checkpoint file recording, for each of the 10 files a stage run can touch (the four stage artifacts, their four baselines, `seed-state.json`, and `source.json`), two independent byte-or-absent states: the bytes it had before the current revision started (`pre_run_bytes`), and the bytes the run itself last wrote (`last_written_bytes`). The module treats every tracked file as an opaque byte blob — it never parses artifact, baseline, or seed-state content — and exposes capture, persist, load, per-entry update, and discard operations, each independently testable against `tmp_path` fixtures with no dependency on `plan_tool/roadmap.py` or any other roadmap orchestrator. On green, the module has no callers yet: wiring it into `run_roadmap`, deciding when to keep an existing checkpoint versus start a new one, and refusing a write on a bytes mismatch are step 2's job, and the restore runner that reads this checkpoint back is step 3's.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — existing contracts this step reads and must fit
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the tracked inventory, the record shape, and the six operations
- [Tests](#tests) — test roster
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

A stage run holds the roadmap writer lock for its whole run and publishes each stage as it goes (`plan_tool/roadmap.py:run_roadmap` / `_run_roadmap`, the stage loop's `publish_stage_artifact` call). Nothing today records what the roadmap looked like before that run started, so a run that stops partway — an invalid stage, an exhausted attempt budget, an interrupt, a crash — leaves the roadmap in a mixed state with no way back except by hand. The plan's restore route (steps 2–5) needs one shared, tested record of "before" and "what this run itself has written so far" to decide whether restoring is safe. This step builds that record in isolation, before anything calls it, so the record's shape — and its two hardest properties, absence tracked explicitly rather than guessed, and discarding it touching nothing else — are settled and tested on their own.

## Input

- **The roadmap's own directory layout** (`plan_tool/roadmap_artifacts.py`) — `roadmap_dir(plans_dir, slug)` returns `<plans_dir>/roadmaps/<slug>`, and every tracked file sits somewhere under it: `domain_path`, `constraints_path`, `components_path`, `plans_path` (the `01-domain.md` / `02-constraints.md` / `03-components.md` / `04-roadmap.md` artifacts), `brief_source_path` (`source.json`); `plan_tool/roadmap_source_identity.py:baseline_path(root, stage_key)` for each stage's `.roadmap-baselines/<stage_key>.json`, keyed by the same `stage_key` strings `plan_tool/roadmap.py`'s stage table already uses (`"domain"`, `"constraints"`, `"components"`, `"plans"` — see `RoadmapStage.artifact_key` on each of the four `RoadmapStage(...)` entries); `plan_tool/roadmap_seed_state.py:seed_state_path(root)` for `seed-state.json`. This step depends on none of these changing shape — it only calls the path helpers, never their parsers.
- **The byte-or-absent convention `plan_tool/roadmap_revision_publish.py:_member_state` already uses** — `path.read_bytes()`, with `FileNotFoundError` mapped to `None`. This step's own capture function must apply that same rule to every tracked path, since a stage run legitimately hasn't reached later stages yet (a `--from-stage 3` run has no stage-1/2 baseline to miss, but stage-3/4 artifacts, baselines, and possibly `seed-state.json` may not exist yet).
- **What this step must not read as anything but bytes** — `plan_tool/roadmap_artifacts.py`'s `parse_domain_artifact` / `parse_constraints_artifact` / `parse_components_artifact` / `parse_plans_artifact` (and their `load_*_artifact` wrappers), `plan_tool/roadmap_source_identity.py`'s `load_baseline_record` / `compare_baseline` / `baseline_record`, and `plan_tool/roadmap_seed_state.py`'s `load_seed_state` all interpret one of these files' content. None of them is a dependency of this step; the checkpoint never calls them and never needs the files it tracks to parse successfully.
- **Downstream shape this step commits to without building it** — step 3's restore runner publishes this checkpoint's pre-run bytes back through the existing `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation`, which takes a `GenerationMember(relative_path, old_bytes, new_bytes)` per file. This step does not call `publish_roadmap_generation` or import `plan_tool/roadmap_revision_publish.py`, but its own per-entry relative-path convention (see Implementation) must match `GenerationMember.relative_path`'s convention exactly — root-relative, forward-slash, no leading `./` — or step 3's conversion breaks silently on the first hand-off.

## Files (creates vs edits)

**New files:**

- `plan_tool/roadmap_revision_checkpoint.py` — the checkpoint record, its path helper, the tracked-file inventory, and the capture / render / parse / write / load / update / discard operations.
- `tests/test_roadmap_revision_checkpoint.py` — its test suite.

**Existing files (edits only):** none.

## Implementation

**The tracked inventory is this module's to define, and every later step reads it from here.** Give the module one function, e.g. `tracked_paths(plans_dir: Path, slug: str) -> tuple[Path, ...]`, that returns the 10 absolute paths in one fixed order (the four artifacts via `domain_path` / `constraints_path` / `components_path` / `plans_path`, then the four baselines via `baseline_path(roadmap_dir(plans_dir, slug), stage_key)` for `stage_key` in `"domain"`, `"constraints"`, `"components"`, `"plans"`, then `seed_state_path`, then `brief_source_path`). Build it by calling those existing path helpers — never by hardcoding a filename string — so a future rename of any one of them changes this module for free instead of silently drifting out of sync. Step 2 and step 3 must read the tracked set through this one function rather than re-deriving their own list.

**Deriving each entry's `relative_path` from `tracked_paths()`'s absolute paths uses the existing `roadmap_relative_stage_path(plans_dir, slug, path) -> str`** (`plan_tool/roadmap_artifacts.py`) — the same helper step 2 imports into `plan_tool/roadmap.py` for the identical purpose, and the one already proven to match `GenerationMember.relative_path`'s convention (root-relative, forward-slash, no leading `./`) because it resolves both the root and the candidate path before computing the relative form, which a naïve `Path.relative_to(...).as_posix()` does not — the two can diverge on a symlinked directory (e.g. macOS's `/tmp` resolving to `/private/tmp`), a real risk under a test's `tmp_path` fixture. `capture_checkpoint` calls this helper for each of `tracked_paths()`'s ten absolute paths; do not invent a different derivation.

**Deliberately excluded from the inventory:** the pending-publication journal itself (`roadmap_source_identity.py:pending_generation_path`, `.roadmap-publication-pending.json`). By the time this module's capture or comparison runs (after `recover_roadmap_publication`, per step 2's ordering fix), the journal is always absent — recovery either commits it or rolls it back and unlinks it either way. Tracking an 11th file that is guaranteed absent at every point this module ever looks at it would carry no restore-relevant information.

**The record shape.** Use a small, plainly-named pair of frozen dataclasses rather than reaching for `roadmap_source_identity.py`'s `GenerationMember` / `PendingGeneration` directly:

- `CheckpointEntry(relative_path: str, pre_run_bytes: bytes | None, last_written_bytes: bytes | None)`
- `RevisionCheckpoint(entries: tuple[CheckpointEntry, ...])`

`GenerationMember` is structurally the same shape (`relative_path`, two byte-or-`None` fields) and is worth knowing about — it's why the relative-path convention above must match — but `PendingGeneration`'s serializer stamps the journal's own `SOURCE_IDENTITY_VERSION` and carries a `kind` field that means "what triggered this in-flight publish." Reusing it would tie this checkpoint's on-disk format to a version number and a vocabulary that belongs to a different artifact for no shared benefit; a local, independently-versioned format is one page of code and avoids that coupling. This is a recommendation, not a hard requirement — if a later reviewer prefers reusing `GenerationMember` bytes-for-bytes, nothing about the plan or this step forbids it, as long as the relative-path convention still matches.

**Path and filename.** One new sibling file inside the roadmap's own directory, not under the repo-root `.plan-tool/` tree — every other piece of this roadmap's own sidecar state (`.roadmap-baselines/`, the publication journal, `seed-state.json`, `source.json`) already lives there, keyed by `(plans_dir, slug)` the same way. Recommended: `REVISION_CHECKPOINT_FILENAME = ".roadmap-revision-checkpoint.json"` (dot-prefixed, matching `.roadmap-publication-pending.json` and `.roadmap-baselines/` — this is this tool's own bookkeeping about an in-progress revision, not roadmap content, unlike `seed-state.json` / `source.json`), with `revision_checkpoint_path(plans_dir, slug) -> Path` returning `roadmap_dir(plans_dir, slug) / REVISION_CHECKPOINT_FILENAME`. `roadmap_dir` already validates the slug; this step does not need its own slug check.

**The six operations:**

- `capture_checkpoint(plans_dir, slug) -> RevisionCheckpoint` — reads every tracked path's current bytes (`None` on `FileNotFoundError`, mirroring `_member_state`) and returns one entry per path with `pre_run_bytes == last_written_bytes` (nothing has been written by "this run" yet at the moment of capture). This function has no opinion on *when* it is safe to call it — step 2 owns calling it only after `recover_roadmap_publication` has resolved any dangling journal, and owns deciding whether to call it at all when an earlier failed run's checkpoint already exists. Do not add that ordering or that "keep the existing checkpoint" policy here.
- `render_checkpoint(checkpoint) -> bytes` / `parse_checkpoint(text: str) -> RevisionCheckpoint` — the text-form serializer/parser pair, independent of any file path (mirrors the `parse_*(text)` / `load_*(path)` split `plan_tool/jira_grade.py` and `roadmap_source_identity.py` both use, which is what keeps most of this step's tests fixture-free). Encode each entry's two byte states with an explicit presence flag — `{"present": false}` for absence, `{"present": true, "data": "<base64>"}` for bytes present — mirroring (not importing) the same shape `roadmap_source_identity.py:_encode_member_bytes` / `_decode_member_bytes` already use for exactly this problem. Stamp the module's own format-version constant (e.g. `REVISION_CHECKPOINT_FORMAT_VERSION = 1`) and reject anything else on parse. Raise a new `RoadmapRevisionCheckpointError(ValueError)` on malformed content — duplicate relative paths, a value that is neither absent nor valid base64, an unsupported version.
- `write_checkpoint(plans_dir, slug, checkpoint) -> None` — `durable_write_bytes(revision_checkpoint_path(plans_dir, slug), render_checkpoint(checkpoint))`. Use `durable_write_bytes`, not `atomic_write_bytes`: this is state a later run and the restore route both read back and trust, which is exactly the case `plan_tool/fileio.py`'s own docstring calls out for the durable (fsync'd file and directory) writer rather than the merely-atomic one. `durable_write_bytes` creates the parent directory itself, so this works even when a roadmap has never had a stage publish yet.
- `load_checkpoint(plans_dir, slug) -> RevisionCheckpoint | None` — `None` when `revision_checkpoint_path(plans_dir, slug)` does not exist; otherwise read its bytes and `parse_checkpoint`, re-raising `RoadmapRevisionCheckpointError` with the path attached on malformed content (the `load_*` wraps `parse_*` and adds path context, per the same split above).
- `with_last_written(checkpoint, relative_path, new_bytes) -> RevisionCheckpoint` — a pure update returning a new `RevisionCheckpoint` with exactly one entry's `last_written_bytes` replaced; every other entry, including that same entry's `pre_run_bytes`, is unchanged. Raise `RoadmapRevisionCheckpointError` if `relative_path` does not match any tracked entry — this is what catches a step-2 wiring mistake (a caller passing the wrong path) at the point it happens instead of it silently doing nothing.
- `discard_checkpoint(plans_dir, slug) -> None` — `revision_checkpoint_path(plans_dir, slug).unlink(missing_ok=True)` and nothing else. This is the step title's own constraint: discarding the checkpoint must never touch any of the 10 tracked files, the `.roadmap-baselines/` directory, or anything else under `roadmap_dir`.

**What this step does not decide:** whether the checkpoint file itself belongs in git or is ignored by it. The four stage artifacts, the baselines, `seed-state.json`, and `source.json` are all git-tracked today; this checkpoint is transient recovery bookkeeping in the same sense as the already-gitignored `**/reports/in-progress-sampler-checkpoint.json` (`.gitignore`). Adding a `.gitignore` line is left to step 2, the step that actually causes a real checkpoint file to appear in a real run's working tree — this step's tests only ever write into `tmp_path`.

## Tests

### Tests for this step

All cases live in `tests/test_roadmap_revision_checkpoint.py`. Every one must be green before this step is done.

- `test_tracked_paths_covers_all_ten_inventory_files_in_a_stable_order` — asserts `tracked_paths` returns exactly the four artifact paths, the four baseline paths, `seed_state_path`, and `brief_source_path`, in the same order on repeat calls.
- `test_checkpoint_path_sits_beside_the_tracked_files_under_the_roadmap_root` — `revision_checkpoint_path(plans_dir, slug).parent == roadmap_dir(plans_dir, slug)`.
- `test_capture_checkpoint_records_absence_explicitly_for_every_missing_file` — on a roadmap directory with none of the 10 files written yet, every entry's `pre_run_bytes` and `last_written_bytes` is `None`, not an empty string or empty bytes standing in for "missing" — this is the step's own "absence recorded explicitly" requirement, named directly.
- `test_capture_checkpoint_sets_last_written_equal_to_pre_run_bytes_at_capture_time` — with some tracked files written and some absent, capture, and assert every entry's two fields are equal to each other, proving capture never assumes anything has been written by "this run" yet.
- `test_capture_checkpoint_relative_paths_match_roadmap_relative_stage_path` — capture against a `tmp_path` roadmap directory and assert each entry's `relative_path` equals `roadmap_relative_stage_path(plans_dir, slug, path)`'s own output for that same tracked path, proving `capture_checkpoint` uses that helper rather than a different derivation that could diverge under a symlinked temp directory.
- `test_render_then_parse_checkpoint_round_trips_every_entry_including_absent_ones` — a fixture-free round trip through `render_checkpoint` / `parse_checkpoint` that includes at least one absent and one present entry, asserting the parsed value equals the original.
- `test_parse_checkpoint_rejects_an_unsupported_format_version` — asserts `RoadmapRevisionCheckpointError`, not a silent fallback.
- `test_write_then_load_checkpoint_round_trips_through_disk` — `write_checkpoint` then `load_checkpoint` against a `tmp_path` roadmap directory returns the same value written.
- `test_load_checkpoint_returns_none_when_no_checkpoint_file_exists` — absence of the checkpoint file itself, distinct from absence of one of the 10 tracked members.
- `test_with_last_written_updates_only_the_named_entry` — updates one `relative_path`'s `last_written_bytes` and asserts every other entry, and that same entry's `pre_run_bytes`, is unchanged.
- `test_with_last_written_rejects_a_relative_path_outside_the_tracked_inventory` — asserts `RoadmapRevisionCheckpointError` for a path not among the 10.
- `test_discard_checkpoint_deletes_only_the_checkpoint_file` — build a `tmp_path` roadmap directory with all 10 tracked files present and non-trivial content plus a written checkpoint, call `discard_checkpoint`, then assert the checkpoint file is gone and every one of the 10 tracked files still has its original bytes. This is the step title's core guarantee, named in the test itself rather than left to be inferred from the code path it happens to exercise.
- `test_discard_checkpoint_is_a_no_op_when_no_checkpoint_exists` — calling it against a roadmap directory with no checkpoint file does not raise and touches nothing.
- `test_capture_and_round_trip_tolerate_syntactically_invalid_tracked_file_content` — write garbage bytes (not valid YAML frontmatter, not valid JSON) to one of the 10 tracked paths, capture, write, and load the checkpoint, and assert the garbage bytes come back unchanged. A module that tried to parse tracked content would raise here; this proves it never does.
- `test_checkpoint_module_does_not_import_roadmap_orchestrators` — an AST-based source scan (mirroring `tests/test_roadmap_source_identity.py:test_source_identity_module_does_not_import_orchestrators`) asserting the module imports none of `plan_tool.roadmap`, `plan_tool.roadmap_revision_publish`, `plan_tool.roadmap_revision_run`, `plan_tool.cli.roadmap_cmd`.

(14 tests)

## Acceptance criteria

- `plan_tool/roadmap_revision_checkpoint.py` exists, imports none of `plan_tool.roadmap`, `plan_tool.roadmap_revision_publish`, `plan_tool.roadmap_revision_run`, or `plan_tool.cli.roadmap_cmd`, and never calls any of the artifact/baseline/seed-state parsing functions listed in Input.
- `tracked_paths(plans_dir, slug)` returns exactly 10 paths, matching the four stage artifacts, their four baselines, `seed-state.json`, and `source.json`.
- `capture_checkpoint` returns `None` for both byte fields of every tracked file absent on disk, non-`None` bytes for every file present, and equal `pre_run_bytes` / `last_written_bytes` for every entry.
- `capture_checkpoint`'s `relative_path` for each entry equals `roadmap_relative_stage_path(plans_dir, slug, path)`'s output for that path, not an independently-invented conversion.
- `render_checkpoint` followed by `parse_checkpoint`, and `write_checkpoint` followed by `load_checkpoint`, return a value equal to the one that went in, including entries with `None` bytes.
- `load_checkpoint` returns `None` when no checkpoint file exists at `revision_checkpoint_path(plans_dir, slug)`.
- `with_last_written` changes only the named entry's `last_written_bytes` and raises `RoadmapRevisionCheckpointError` for an untracked `relative_path`.
- `discard_checkpoint` deletes only the file at `revision_checkpoint_path(plans_dir, slug)`; every one of the 10 tracked files is byte-for-byte unchanged afterward.
- `uv run pytest tests/test_roadmap_revision_checkpoint.py -q` passes, and the full suite (`uv run pytest tests/ -q -n auto`) passes.

## References

- `plan_tool/roadmap_artifacts.py` — `roadmap_dir`, `domain_path` / `constraints_path` / `components_path` / `plans_path`, `brief_source_path`: the path helpers `tracked_paths` is built from. `roadmap_relative_stage_path` (lines 115-131) is the absolute-to-relative conversion `capture_checkpoint` uses for every entry's `relative_path`, resolving both root and candidate before computing the relative form so it matches `GenerationMember.relative_path`'s convention even under a symlinked directory.
- `plan_tool/roadmap_source_identity.py` — `baseline_path`, `GenerationMember`, `_encode_member_bytes` / `_decode_member_bytes`: the baseline path helper, and the present/absent byte-encoding shape this step's serializer mirrors.
- `plan_tool/roadmap_seed_state.py` — `seed_state_path`: the last of the 10 tracked paths.
- `plan_tool/roadmap_revision_publish.py` — `_member_state`, `publish_roadmap_generation`, `recover_roadmap_publication`: context for why absence must be tracked explicitly and why this checkpoint's relative-path convention must match `GenerationMember`'s; this step calls none of these.
- `plan_tool/fileio.py` — `durable_write_bytes`: the write helper, and its docstring's own guidance on durable-vs-atomic that this step's Implementation section cites directly.
- `plan_tool/cli/checkpoints.py`, `plan_tool/checkpoint.py` — the unrelated `plan-tool checkpoint list` / `clear` authoring-cache family this step's artifact shares a name with but nothing else.

## Applicable guardrails

The plan's `## Scope guardrails` bind this step on several points:

- "No new persisted state except the checkpoint" — this step is the one that persists it; it must not add a second sidecar (a receipt, an evidence-store entry, a content-addressed record) alongside the single checkpoint file.
- "No automatic restore, and no restore offered on anything but an explicit command" — this module ships no restore or apply function of any kind; it only captures, persists, loads, updates one entry, and discards.
- "No change to enrollment, candidates, review seals, promotion, or the `.roadmap-versions/` namespace" — this module must not import `plan_tool/roadmap_versions.py` or read or write anything under `.roadmap-versions/`.
- "Eligibility never reads run logs" — this module must not import `plan_tool/run_log.py` or read anything under `.plan-tool/runs/`.

## Deferred

- Wiring `capture_checkpoint` / `write_checkpoint` / `with_last_written` / `discard_checkpoint` into `run_roadmap` / `_run_roadmap`, including calling `recover_roadmap_publication` before the first capture or comparison, keeping an earlier failed run's checkpoint across a new run in the same lineage, and discarding on completion — step 2.
- The write-time check that a tracked file's current bytes still match the checkpoint's `last_written_bytes` before writing it, and refusing the run on a mismatch — step 2.
- Moving `_write_brief_source`'s confirmed-rebind write to after `recover_roadmap_publication` — step 2.
- The restore runner and its case matrix (no checkpoint, enrolled, matches last-written, matches pre-run, anything else) — step 3.
- CLI flags, exit-code mapping, and the restore-command message at `cmd_roadmap`'s four non-completion paths — steps 4 and 5.
- Operator documentation, including distinguishing this checkpoint from `plan-tool checkpoint list` / `clear`, and closing `BACKLOG.md` #394 — step 6.
- Adding the checkpoint filename to `.gitignore` — step 2, the step whose wiring first causes the file to appear in a real run's working tree.
- Tracking the pending-publication journal itself as an 11th inventory member — deliberately excluded; see Implementation.
