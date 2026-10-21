> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Load each stage's predecessor before it writes, and carry it in the gate envelope

## Summary

Teach `plan_tool/roadmap.py` to read, before any stage runs, the artifact each stage-to-run is about to replace, and to hand that prior version to two places: step 4's revision prompt renderer and step 2's `ArtifactEnvelope.predecessor` field. The whole change lives in `run_roadmap`'s pre-flight block, `_build_envelope`, and `_run_stage`; no new file, no new import, no new stage-table field. The key design decision: **the predecessor snapshot is taken pre-flight, and an artifact that is present but unreadable or malformed is an error rather than a silent "no predecessor"** — a revision that quietly falls back to authoring is exactly the regenerate-over-the-human failure this plan exists to remove. On green, a re-run over an existing roadmap sends the model its own prior artifact plus the reviewer's open feedback and is judged by the three predecessor gates, while a run over an empty directory behaves exactly as it does today.

## Table of Contents

- [Summary](#summary) — what lands and what is observable on green.
- [Why](#why) — steps 2 and 4 both built for a predecessor nothing supplies.
- [Input](#input) — the position-01 loading seam and what steps 2 and 4 produce.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, no new files.
- [Implementation](#implementation) — when the read happens, what counts as absent, and the upstream/predecessor split.
- [Tests](#tests) — the new roster, the existing cases that become revision runs, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs bearing on the prior-artifact block.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step.
- [Deferred](#deferred) — what steps 6–8 own.

## Why

After steps 2 and 4, the machinery for a revision exists and nothing turns it on. `plan_tool/roadmap_gates.py` holds three gates that read `envelope.predecessor`, and `plan_tool/roadmap.py:_build_envelope` never fills that field, so all three are inert in production. `_render_stage_prompt` takes a `predecessor` keyword that only a test ever passes, so `plan_tool/prompts/roadmap-revision.md` is unreachable from a real run. Meanwhile a `--from-stage N` re-entry still does the thing the plan's Problem statement names: it overwrites the artifact without ever reading it, so a reviewer's feedback rows and the design they were written against are gone before the model is asked anything. This step is the wire that connects the two halves — it is the smallest change that makes revision mode real, and it is where "before any overwrite" stops being a wish and becomes an ordering.

## Input

This step reads contracts that already ship or that steps 2 and 4 land. Each must stay true.

- **`_load_stage_artifact(stage, *, plans_dir, slug)` is the one reader**, and it returns a `_LoadedArtifact` carrying `stage`, `path`, `text`, and `artifact` from a single read. It raises `RoadmapError` naming the path and the writing stage when the file cannot be read, and lets `RoadmapArtifactError` through with the path attached when the file is malformed. Reuse it; the predecessor needs both halves it carries — step 4's renderer wants the on-disk `text`, step 2's gates want the parsed `artifact`.
- **Pre-flight failures raise before anything is invoked or written.** `_check_from_stage`, `_read_brief`, and `_load_and_regate_below` all run before the stage loop, and `test_re_entry_regate_failure_is_pre_flight_not_a_retry` pins that the invoker is never called. This step joins that block rather than adding a mid-loop failure point.
- **`_build_envelope(entries)` fills `ArtifactEnvelope` by `artifact_key`** from `_LoadedArtifact` entries and is called from two places: `_run_stage` (the artifact under check plus everything below it) and `_load_and_regate_below` (the below-stage re-gating pass). Only the first gains a predecessor.
- **Step 2 produces `ArtifactEnvelope.predecessor`**, an optional field defaulting to `None`, holding the prior version of the artifact under check. Its three gates are inert while it is `None`. Step 2 deliberately does not check that the predecessor's type matches the artifact under check, because this step builds the pair from one stage row.
- **Step 4 produces the revision prompt path.** `_render_stage_prompt` gains a keyword-only `predecessor` (an `Optional[_LoadedArtifact]`); with one it wraps the authoring prompt in `plan_tool/prompts/roadmap-revision.md`, renders the predecessor's text and an active-feedback block holding the `open` rows, and with none it returns the authoring prompt unchanged. This step chooses when that argument is non-`None`; it renders nothing itself.
- **Step 1's collections reach this step only through the parsed artifact.** `feedback` and `removals` default to `()`, so an artifact written before this plan loads as a predecessor with no review rows and behaves as an ordinary revision with nothing active.
- **What this step cannot verify.** Every case here drives canned replies. It can prove the right prior artifact reaches the prompt and the gates, and that a wrong one never does; it cannot prove a model revises well. Step 9's real-run exercise owns that.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/roadmap.py` — add the optional predecessor reader and the pre-flight sweep that builds one entry per stage-to-run; add a keyword-only `predecessor` to `_build_envelope` and to `_run_stage`; pass it from `run_roadmap`'s loop. Correct the module docstring's "Disk is the interface between stages" paragraph, `run_roadmap`'s "each one overwrites its artifact" clause, and `_build_envelope`'s docstring.
- `tests/test_roadmap.py` — add the cases listed in [Tests](#tests); extend the artifact-writing helpers on `_Env` so a case can pre-write an artifact carrying feedback.

## Implementation

### What must be true when this is done

- Before the first stage is invoked, `run_roadmap` has read the artifact that every stage from `from_stage` up is about to replace.
- A stage whose artifact was on disk renders the revision prompt and gets its gate envelope's `predecessor` filled with that prior artifact.
- A stage whose artifact was not on disk behaves exactly as at HEAD — same prompt, same envelope, same violations.
- A predecessor that exists but cannot be read or parsed stops the run before any call and before any write.
- Below-stage artifacts keep their current role and their current treatment; `_load_and_regate_below` is unchanged.
- Nothing outside `plan_tool/roadmap.py` and `tests/test_roadmap.py` changes.

### Read the predecessors pre-flight, not per stage

Sweep the stages once, after `_load_and_regate_below` and before the stage loop, producing one optional `_LoadedArtifact` per stage the run will actually execute.

- **Keep the existing pre-flight order** — `_check_from_stage`, then `_read_brief`, then `_load_and_regate_below`, then the predecessor sweep. Each existing pre-flight message keeps the precedence its test asserts.
- **Per-stage lazy loading gives the same predecessor and a worse failure.** On a `--from-stage 1` re-run over a populated directory, a malformed `02-constraints.md` would surface only after stage 1 spent its tokens and rewrote `01-domain.md`. The pre-flight sweep costs one read per stage and buys the guarantee the rest of the module already makes.
- **Pre-flight also makes "before any overwrite" true by the ordering rather than by care.** Nothing later has to remember to read a file before writing it, because every read already happened.
- **Index the snapshot by table position, not by `stage.number`.** `_stage_numbers` returns whatever numbers the table holds and nothing enforces uniqueness, so a dict keyed by number would silently merge two rows. One way: build a sequence parallel to the sorted `ordered` tuple and walk the two together.
- **Only stages at or above `from_stage` get an entry.** A skipped stage is never rewritten, so it has nothing to be a predecessor of.

### Two pre-flight checks on the loaded predecessor, before any invoke

Step 2 routes two reviewer-authored defects here rather than to the retry loop, because only the reviewer can fix either and a retry spends three attempts writing nothing. Both run at this load site, after the predecessor parses and before the stage is rendered, in the existing pre-flight order (they join the checks that already fail the run before a call).

- **Duplicate feedback ids in the predecessor** → error naming the duplicated id. Every predecessor-joining rule in gate 2 keys on id, so two rows sharing one make "the predecessor's row for this id" undefined; parse time deliberately lets the duplicate through, so nothing else catches it.
- **A `row` target whose `row_id` resolves against neither the predecessor's design rows nor the ids its removal records name** → error naming the row and the unresolvable id. The only model-side repair is editing the reviewer's `target`, which `VIOLATION_ALTERED_FEEDBACK_SOURCE` forbids, so it cannot be a retry.
  - **The message must not call this a typo.** The likeliest cause is the *restore* path: the reviewer pruned a carried removal record for `entity-3`, which is exactly what step 2 tells them to do to ask for the row back — and that prune drops `entity-3` from the removal-named set the check resolves against, so any feedback row still targeting it now resolves against nothing. Name a pruned removal as the likely cause **before** a typo, or the message points the reviewer at the wrong edit.
  - **State the ordering the restore path requires**, here and in step 2: prune the carried removal **and** close or retarget every feedback row that named the removed id — or ask for the restore with an `artifact`-level target, which resolves against nothing and is the simpler move. Without that ordering the plan's own documented reopen flow errors before any call.

**The now-redundant gate rule survives, deliberately.** Once this check exists, gate 2's `VIOLATION_UNRESOLVED_FEEDBACK_TARGET` is reachable only for a row the *model* invented or altered — a case `VIOLATION_ALTERED_FEEDBACK_SOURCE` already reports, and one step 6's fourth rejection kind refuses before the gates ever run. Keep it anyway: gates are also run by `_load_and_regate_below`, which never passes through this pre-flight, and a gate that is unreachable *on one path* is not a gate that can be deleted. Say so in its docstring so a later author does not "simplify" it away.

### Absent means no predecessor; present-but-unusable is an error

- **The only "no predecessor" case is a path that does not exist.** Recommended shape: a thin optional wrapper that returns `None` when the artifact path is missing and otherwise delegates to `_load_stage_artifact`. A directory or an unreadable file then surfaces through the existing message naming the path and the stage that writes it, rather than being mistaken for a first run and blowing up later in `_write_artifact`.
- **Do not soften `_load_stage_artifact` itself.** Its strictness is what `_load_and_regate_below` relies on, and a tolerant reader shared by both would make a missing upstream artifact silently acceptable.
- **Never fall back to authoring mode on a read or parse failure.** This is the rule that is not free to vary. Silently dropping the predecessor discards the reviewer's feedback rows *and* makes step 2's three gates inert, so the run regenerates over the human's contribution with nothing reporting it — the plan's Problem statement, reproduced by an error handler. The operator's way to ask for a fresh authoring pass is to delete the file; the error message should say so.

### Threading the predecessor to the two consumers

- **`_build_envelope` gains a keyword-only `predecessor: Optional[_LoadedArtifact] = None`** and passes `predecessor.artifact` into `ArtifactEnvelope`. The `artifact_key`-driven keyword construction is untouched.
  - **Rejected alternative:** pushing the predecessor into the `entries` sequence. It shares an `artifact_key` with the artifact under check, so the dict comprehension would drop one of them.
- **`_load_and_regate_below`'s call stays on the default.** A below-stage artifact is judged on its own terms, exactly as today, and the three new gates stay inert there. A hand-edited upstream must not be compared to anything — there is nothing it is a revision of.
- **`_run_stage` gains the same keyword-only parameter** and uses it twice: it passes it to `_render_stage_prompt` for the base prompt, and to `_build_envelope` on every attempt. The base prompt is rendered once before the attempt loop, so the prior artifact and the active feedback are identical on every attempt while only the corrections tail varies — the property step 4's `test_the_active_feedback_block_is_identical_on_every_attempt` pins.

### Upstream and predecessor are two different roles

Say this plainly in the code, because the same file can play either part on different runs:

- **Upstream** — an artifact *below* `from_stage`. It is ground truth for the stages above, so `_load_and_regate_below` re-runs its own stage's gates over it and a failure is a hard pre-flight error. It is read once and never rewritten.
- **Predecessor** — the artifact of a stage *at or above* `from_stage`. It is the starting point for a revision, and this run replaces it.
- **Never both, on one run.** A stage's own written artifact is read back off disk as upstream for the stages above it; that read-back never becomes anyone's predecessor.
- **Do not gate the predecessor.** A reviewer who hand-edits an artifact into a state the gates would reject and attaches feedback asking for the fix is the flow this position exists to serve. Gating the predecessor would refuse exactly that. Give this its own test — it is the kind of rule a later author "completes" by symmetry with `_load_and_regate_below`.

### The overwrite record and the predecessor now describe the same fact

`_write_artifact` computes `replaced = path.exists()` at write time; the predecessor snapshot answers the same question at pre-flight time. Leave `_write_artifact` as it is — collapsing the two is a behavior-preserving refactor that does not belong in a feature step — and pin the relationship instead: every stage in `overwritten_stages` had a predecessor. A stage that halts with an exhausted budget can have a predecessor and write nothing, so the containment runs one way only.

### Existing cases that become revision runs, and why they stay green

Turning revision mode on in production changes what several existing cases exercise, without changing what they assert. Each pre-writes an artifact and then replies with text equal to the one it replaces, so every predecessor rule passes: rows all survive, there are no feedback rows, and the settled decision `tests/test_roadmap.py:_domain` builds by default is carried unchanged.

- In `tests/test_roadmap.py`: `test_overwriting_an_existing_artifact_records_the_stage_number`, `test_re_entry_records_the_stages_it_rewrote`, `test_stages_skipped_by_from_stage_are_not_recorded_as_overwritten`, `test_the_orchestrator_renders_no_operator_advice`, `TestShippedTableReEntry`'s `test_hand_deleted_entity_breaks_the_anchor_on_re_entry`, and `TestReEntryAgainstTheRealGateSets`'s `test_hand_edited_upstream_is_visible_to_the_later_stages_gates` — the last two still expect exactly one violation kind, which is the sharpest check that the new gates add nothing on an unchanged revision.
- In `tests/cli/test_roadmap_cmd.py`: `TestOverwriteAdviceIsPrintedExactlyOnce` pre-writes both artifacts and drives the real orchestrator through the CLI, so it becomes the only end-to-end revision run in the suite. It is outside this step's file list and must stay green **unedited**.

If one of these needs an edit to pass, that is the signal that the predecessor is being judged somewhere it should not be — fix the code, not the case.

## Tests

All new cases go in `tests/test_roadmap.py`, in the file's existing section-comment layout. Reuse the `feedback_row(...)` / `removal(...)` builders and the `_predecessor(...)` helper step 4 adds to this same file rather than minting second copies; extend `_Env.write_domain` / `write_constraints` usage with locally built feedback-bearing text where a case needs it. Cases that drive the real gate sets go under `@pytest.mark.integration`, matching `TestReEntryAgainstTheRealGateSets`.

### Tests for this step

Approx. 27 new cases. Every one must be green before this step is done, and `tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`, and `tests/cli/test_roadmap_cmd.py` must stay green **without being edited**.

Finding the predecessor:

- `test_a_first_run_loads_no_predecessor` — nothing on disk, every envelope's `predecessor` is `None`.
- `test_an_artifact_already_on_disk_becomes_that_stages_predecessor`.
- `test_the_predecessor_is_the_version_from_before_the_write` — the reply differs from the pre-written file; the predecessor is the old parse.
- `test_every_stage_of_a_full_re_run_gets_its_own_predecessor` — both files pre-written, `--from-stage 1`.
- `test_one_stage_gets_a_predecessor_while_a_sibling_with_no_file_gets_none`.
- `test_a_skipped_stages_artifact_is_upstream_not_a_predecessor` — on `--from-stage 2`, stage 2's envelope predecessor is `02-constraints.md`'s prior parse, and stage 1's file is never read as one.
- `test_predecessors_are_indexed_by_table_position_not_stage_number` — a table whose two rows share a number still gets one predecessor each.

Pre-flight ordering:

- `test_a_malformed_predecessor_raises_before_any_invoke` — invoker call count is zero.
- `test_a_malformed_predecessor_writes_no_artifact_for_an_earlier_stage` — the `--from-stage 1` case, where lazy loading would have written one.
- `test_a_malformed_predecessor_surfaces_as_a_parse_error_naming_the_path`.
- `test_a_predecessor_path_that_is_not_a_readable_file_raises_naming_the_stage_that_writes_it`.
- `test_a_below_stage_regate_failure_still_takes_precedence` — both broken; the existing upstream message is the one raised.

The envelope:

- `test_the_gate_envelope_carries_the_predecessor` — through a `_GateRecorder`.
- `test_the_envelope_predecessor_is_absent_on_a_first_run`.
- `test_below_stage_re_gating_builds_a_predecessor_free_envelope` — the inertness `_load_and_regate_below` depends on.
- `test_the_same_predecessor_is_used_on_every_attempt` — three attempts, three equal predecessors.
- `test_the_predecessor_is_never_re_gated` — a gate-failing artifact on disk plus a conforming reply completes.

The prompt:

- `test_the_predecessor_text_reaches_the_revision_prompt` — the on-disk bytes, not a re-render.
- `test_open_feedback_on_disk_reaches_the_prompt` — id and request appear in the invoker's prompt.
- `test_a_first_run_prompt_carries_no_revision_framing` — the regression guard against turning revision mode on everywhere.

Against the real gate sets (integration):

- `test_an_unchanged_revision_over_an_existing_roadmap_completes` — the identity case both shipped stages must pass.
- `test_a_revision_dropping_a_predecessor_row_is_retried_with_the_continuity_message`.
- `test_a_dropped_row_with_a_cited_removal_completes` — the sanctioned path, end to end.
- `test_a_flipped_settled_decision_is_retried_with_the_settled_gate_message`.

Invariants and no new surface:

- `test_every_overwritten_stage_had_a_predecessor`.
- `test_a_synthetic_stage_with_a_predecessor_drives_through_the_loop_unchanged` — re-asserts that `plan_tool/roadmap.py` holds no comparison on a stage's name or number.
- `test_no_new_run_log_event_is_emitted` — the event kinds a revision run writes are the ones a first run writes.
- `test_run_is_non_interactive` stays green unchanged.

## Acceptance criteria

- With no artifact on disk, every gate envelope `run_roadmap` builds has `predecessor is None`, and the prompt each stage receives equals the one it receives at HEAD.
- With `01-domain.md` on disk, the stage-1 gate envelope's `predecessor` equals `parse_domain_artifact` of that file's contents as they were before the run, and the rendered prompt contains that file's text.
- On `--from-stage 1` with both artifacts on disk, each stage's envelope predecessor is its own artifact's prior parse — stage 2's is the constraints artifact, never stage 1's.
- On `--from-stage 2` with both artifacts on disk, the envelope stage 2's gates receive carries `01-domain.md` as `domain` and `02-constraints.md`'s prior parse as `predecessor`.
- A malformed artifact at a stage-to-run's path raises `RoadmapArtifactError` naming that path, the invoker is never called, and no artifact file is created or modified.
- A predecessor holding two feedback rows with the same id fails pre-flight naming the duplicated id; the invoker is never called and no artifact is written.
- A predecessor feedback row whose `row` target resolves against neither its design rows nor its removal records' `removed_id`s fails pre-flight naming the row and the unresolvable id; the invoker is never called. A target resolving against a removal record's `removed_id` passes.
- The envelope `_load_and_regate_below` builds has `predecessor is None` for every below-stage artifact.
- An artifact on disk that fails its own stage's gates does not by itself fail the run: a conforming reply over it completes.
- Every stage number in `result.overwritten_stages` had a non-`None` predecessor.
- `rg -n 'stage\.(name|number) ==' plan_tool/roadmap.py` returns nothing, and `RoadmapStage` declares no predecessor field.
- `rg -n 'input\(|isatty' plan_tool/roadmap.py` returns nothing.
- `uv run pytest tests/test_roadmap.py tests/test_roadmap_artifacts.py tests/test_roadmap_gates.py tests/cli/test_roadmap_cmd.py -q` is green, with the last three files unmodified.
- `uv run pytest tests/test_duplication.py -q` is green with no new `ALLOWED_DUPLICATE_GROUPS` entry.
- `git diff --name-only` lists exactly `plan_tool/roadmap.py` and `tests/test_roadmap.py`.

## References

- [Long context prompting tips — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — read for why the prior artifact has to arrive as the exact document the reviewer read, with its own boundary, rather than as a summary or a re-render.
- [Prompt caching — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — why the predecessor block must be identical across a stage's attempts, which is what reading it once pre-flight gives for free.
- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — the frontmatter grammar a hand-edited predecessor is parsed against, and therefore what a malformed-predecessor pre-flight failure is reporting.

## Applicable guardrails

- **The plan's "## Out of scope", no second store, sidecar, or hidden feedback state.** This binds this step hardest, because a pre-flight snapshot is exactly where a cache feels natural. The snapshot lives in one local variable for the length of one call; write no file, no `.plan-tool/` state, and nothing that survives the run.
- **The plan's "## Out of scope", cross-artifact feedback propagation.** A stage's predecessor is its own artifact's prior version and nothing else. An upstream artifact's feedback rows must never fill a later stage's `ArtifactEnvelope.predecessor` or count as active guidance; they remain visible inside the upstream artifact text, which the prompt carries whole.
- **The plan's "## Out of scope", no TTY walk, confirmation prompt, or new command.** A run over an existing roadmap must not gain a confirm, however tempting it is at the moment the tool has both versions in hand.
- **The plan's "## Out of scope", no cap or rejection keyed on feedback length, shape, count, or semantics.** The loader reads whatever the artifact holds and passes it on whole; the prompt-budget advisory below `plan_tool/shell.py:claude_invoke` stays the only pressure signal.
- **The plan's "## Out of scope", optimistic write conflicts for simultaneous editors.** The snapshot is a plain read. Add no lock, no mtime check, and no re-read before the write.
- **The plan's "## Architecture", a stage is data and the revision wrapper is shared.** The predecessor arrives as a value computed from a stage row's own `artifact_path`; `RoadmapStage` gains no field and the loop gains no branch on which stage it is running.
- **The plan's "## Architecture", the one-way dependency line.** `plan_tool/roadmap.py` reads from `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py` and adds no import in the other direction. It decides *when* a gate sees a predecessor; it never decides what one means.
- **The plan's "## Acceptance criteria", first-run behavior unchanged.** The no-artifact-on-disk path must produce the same prompt, the same envelope, and the same violations as HEAD. That is what makes this additive rather than merely intended.

## Deferred

- **Performing the `open` → `awaiting-review` transition and writing the revision** — step 6. This step supplies the prior artifact; nothing here changes a feedback row's state or what gets written.
- **Computing the predecessor digest and emitting `RevisionFeedbackDelivered`** — step 6, using the bytes this step's loaded predecessor carries. Step 3 minted the event; step 5 emits no run-log event of its own.
- **Reporting revision facts on `RoadmapResult`** — which stages were revisions, and how many feedback rows await review — steps 6 and 7. `RoadmapResult` gains no field here, so `plan_tool/cli/roadmap_cmd.py` compiles and behaves unchanged.
- **The operator summary that points at feedback awaiting review** — step 7.
- **Documenting the revision loop, the upstream-versus-predecessor split, and the delete-the-file escape** — step 8, reading whatever actually lands here.
- **Deriving `_write_artifact`'s `replaced` flag from the predecessor snapshot** — not taken. The two answer the same question at different times, and folding them is a behavior-preserving refactor that would ride inside a feature step. If it is worth doing, it is a `BACKLOG.md` entry.
- **Gating the predecessor the way `_load_and_regate_below` gates an upstream artifact** — deliberately not taken, and the reason belongs in the code: a reviewer's hand edit may leave the artifact failing its own gates, and the revision is how it gets fixed.
- **Re-reading a predecessor between attempts, or after a stage writes** — not taken. The snapshot is the state the reviewer edited before invoking; refreshing it mid-run would let a stage revise against its own output.
- **Measuring the prompt-size effect of carrying a full prior artifact, and any `MAX_STAGE_ATTEMPTS` calibration** — step 9's real-run exercise and BACKLOG #215 respectively, per the plan's Deferred list.
