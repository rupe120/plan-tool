> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Record a create-stage granularity assessment event in the change-type review loop

## Summary

Make `plan_tool/create.py`'s change-type review record one granularity **assessment event** per review pass, so the tool can later answer how often create-stage split signals fire, how many distinct steps were affected, and how large the plan/file footprint was when they did. The work lives in `_review_step_change_types` plus a small new helper, and in `tests/test_create.py`. The helper runs the no-Claude advisor (`assess_granularity` with `invoker=None`) over the candidate step list, counts the `granularity-split` and `granularity-merge` findings, counts distinct split-hit steps separately, collects deduplicated split step ids as strings in candidate order, counts distinct declared file paths across the candidate steps' full file footprints (`files` plus `creates`), groups the split findings by predicate key (using step 2's `split_predicate_key`), and hands those primitives to step 3's `record_create_granularity_assessment`. The key design call: record once per pass in every mode (interactive / yes / non-TTY / checkpoint-resume) with the right `mode` label, and keep the whole thing best-effort — a telemetry or advisor failure must never change the reviewed steps, prompts, or return value. On green, a create run leaves one `kind="granularity"`, `decision="create-review"` line in `.plan-tool/telemetry/decisions.jsonl` readable through `read_decisions`.

## Table of Contents

- [Summary](#summary) — what this step ships and the result on green
- [Why](#why) — the missing create-stage observation this fills
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the assessment helper, the four record sites, and the constraints that pin them
- [Tests](#tests) — unit cases added (and why one existing test stays unchanged)
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — stdlib and pytest docs for this step
- [Deferred](#deferred) — per-step outcome events and other out-of-scope work

## Why

Create can already show a `granularity-split` hint and accept a `(s)plit` action, but it persists nothing about that decision. After a session there is no way to ask: how often did create-stage split fire, which predicate fired, how big was the plan, and was split mechanically available. BACKLOG #51 wants this data before it can tune the plan-level "this is probably more than one plan" boundary, and BACKLOG #72 names create-side granularity as a decision site worth instrumenting. Step 2 exposes a stable predicate key off each split finding, and step 3 adds the `record_create_granularity_assessment` recorder that pins the event's context shape. This step wires the recorder into the review loop — it adds observation only, changing no create behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add a best-effort helper that builds and records the assessment event from a candidate step list; call it once in each return path of `_review_step_change_types` (resume/checkpoint, `--yes`, non-TTY, interactive) with the matching `mode`. Add the imports for step 3's recorder + mode constants, step 2's `split_predicate_key`, and `GRANULARITY_MERGE_SOURCE`.
  - `tests/test_create.py` — add unit tests asserting the event through `read_decisions` for each mode and for the split/merge/predicate counts, plus a new test covering "advisor runs for telemetry regardless of `can_split`" with a `repo_root`; leave the existing `test_hint_suppressed_when_cannot_split` guard unchanged (it passes no `repo_root`, so the helper returns early — see Tests).

## Implementation

**What changes.** `_review_step_change_types` gains one side effect: it records a single assessment event per pass. Today it returns the reviewed step list through four branches — a checkpoint-resume hit, the `--yes` accept-verbatim path, the non-TTY accept-verbatim path, and the interactive loop. Each of those should record exactly one event over the **candidate (incoming) `steps` list** before it returns, tagged with the mode that branch represents.

**Add one best-effort helper.** Recommend a single module-level helper in `plan_tool/create.py` next to `_granularity_split_hints`, e.g. `_record_create_assessment(steps, *, mode, can_split, repo_root, plan_slug)`. It should:

- **Skip when there's nowhere to write.** Return early if `repo_root is None` — telemetry needs a path, and several callers/tests run without one.
- **Run the advisor once over the candidate list.** Build the same throwaway `Plan` shape `_granularity_split_hints` already uses and call `assess_granularity(plan, stage="create", evidence=GranularityEvidence(), invoker=None)`. `invoker=None` is the structural guarantee that no subprocess is spawned at create stage.
- **Compute the candidate fingerprint.** Build `candidate_fingerprint` before any interactive mutation from a canonical JSON payload over the incoming candidate steps' stable primitive fields (at minimum id, title, existing `change_type`, full file footprint, and creates/files as represented at HEAD), then hash it with SHA-256. Do not include timestamps, telemetry mode, or post-split state. This lets aggregation collapse repeated observations of the same candidate list, including abort/retry paths that never produce a checkpoint.
- **Compute the plan footprint.** Build `file_footprint` as the count of distinct file paths declared across the incoming candidate steps' full file footprints (`step.all_files`, i.e. `files` plus `creates`). Count paths as strings after normalizing only by exact string identity; do not resolve them against the filesystem or require they exist. This preserves the "aggregate file footprint" signal for later analysis without adding a threshold now and keeps the metric aligned with `_step_spans_unrelated_areas`, which also uses `all_files`.
- **Partition the recs by source.** Count `GRANULARITY_SPLIT_SOURCE` findings into `split`, `GRANULARITY_MERGE_SOURCE` findings into `merge`. A single step can produce multiple split findings, so also compute `split_steps` as the number of distinct split-hit step ids. Collect `split_step_ids` as a deduplicated `list[str]` ordered by the candidate step list (not by recommendation order), matching step 3's recorder contract. Build `predicate_counts: dict[str, int]` by mapping each split rec through step 2's `split_predicate_key(rec)` and tallying the returned deterministic create-stage keys. At create stage `invoker=None`, so `parse_mixed_step_findings` never fires and `mixed-step` is not an expected create-review key.
- **Hand primitives to step 3's recorder.** Before wiring the call, **confirm step 3's actual exported signature and arity of `record_create_granularity_assessment` (and step 2's `split_predicate_key`) at HEAD, and pass only the keyword arguments the current signature accepts** — do not treat any particular shape as fact ahead of step 3. Call `record_create_granularity_assessment` with `plan_slug=slug or ""` plus `steps=len(steps)`, `candidate_fingerprint`, `file_footprint`, the split/merge counts, `split_steps`, `split_step_ids`, `predicate_counts`, `can_split`, and `mode`. The intent is that the recorder owns the `stage="create"` context value and forwards `plan_slug` to `record_decision`, so the caller supplies create-side primitives plus the plan identity rather than stage bookkeeping; if step 3's landed signature instead expects `stage` (as its sibling `record_granularity` does), pass it accordingly. The recorder is already best-effort, so do not wrap that call in a second try/except.
- **Swallow its own computation errors.** Wrap the advisor run and predicate mapping in one `try/except Exception: return` — the same thing `_granularity_split_hints` does. This is guarding the helper's own logic (building the context), which is distinct from the recorder's internal swallow; it is not a double-wrap of the recorder.

**Wire the four record sites.** Each is a one-line call to the helper, with `can_split` and `mode`:

- **Checkpoint-resume hit** (the `load_if_valid` branch that returns `restored`) → `mode=CREATE_MODE_CHECKPOINT`.
- **`--yes` branch** → `mode=CREATE_MODE_YES`.
- **Non-TTY branch** (`not sys.stdin.isatty()`) → `mode=CREATE_MODE_NON_TTY`.
- **Interactive branch** → `mode=CREATE_MODE_INTERACTIVE`, recorded once **before** the `while` loop. The loop's `(s)plit` renumbers steps, but those are operator actions step 5 records as outcome events; the assessment is over the incoming candidate list, so record `steps` as handed in, not the post-split `reviewed`.

Use step 3's exported mode constants, not bare string literals, so the values stay single-sourced.

**`can_split` value.** Use `can_split = invoker is not None` in all four sites — the structural reading: "an invoker was wired, so split was mechanically available." This matches the gate `_ask_change_type` already uses. In `--yes`, non-TTY, and checkpoint modes no UI is presented; `mode` is the field that distinguishes those cases from an interactive offer. Future aggregation should combine `can_split` with `mode`, not read `can_split` alone as "the prompt was shown."

**Constraints and gotchas:**

- **Never change review behavior.** The recording must not alter `reviewed`, the prompts, the return value, the checkpoint write, or any split/retry flow. It is a pure side effect bracketed by its own swallow. The existing `test_advisor_failure_does_not_break_review` already pins that an advisor exception can't break the loop; the new helper's swallow keeps that true.
- **Record over the candidate list, once.** One event per pass, built from the incoming `steps`. Do not record per loop iteration and do not record the post-split list.
- **Checkpoint mode is a resume observation.** The helper still records `mode=CREATE_MODE_CHECKPOINT` on a checkpoint-resume hit, but consumers must exclude checkpoint-mode assessment events from "fresh signal fired" counts because the original interactive/yes/non-TTY pass may already have recorded the same candidate list. For non-checkpoint repeat observations, consumers use `candidate_fingerprint` with `plan_slug` to dedupe the same candidate list.
- **The advisor now runs regardless of `can_split` (when `repo_root` is set).** `_granularity_split_hints` runs the advisor only when `can_split` (the hint is noise otherwise). The assessment deliberately runs it in every mode, because the count of fired split signals in `--yes` and non-TTY runs is exactly the data BACKLOG #51 wants — but only after it returns early on `repo_root is None`, so callers with no write target still consult nothing. A new test pins this behavior with a `repo_root`; see Tests.
- **Stay off the prose kernel.** At create stage `invoker=None`, so `parse_mixed_step_findings` never fires; `predicate_counts` will hold only the deterministic keys. Still map through `split_predicate_key` rather than hard-coding the three keys.
- **`plan_slug`.** Pass `slug` through (it may be `None`); use `slug or ""` if the recorder requires a non-None string. The recorder owns the context shape — hand it primitives, nothing from `plan_tool.schema` or `granularity` beyond the already-imported `split_predicate_key`.

**Shared-logic note.** The foundational rule here — "record one assessment per review pass" — has no duplicate elsewhere. The advisor run overlaps `_granularity_split_hints`, but that helper discards merge findings and predicate keys, which the assessment needs, so the two stay separate rather than consolidating. The per-step **outcome** events (accept / override / split-applied / split-invalid / split-error) are step 5's job in the same file and the same `record`-family helpers — see Deferred.

## Tests

All new cases go in `tests/test_create.py`, driving `_review_step_change_types` directly (as `TestStepReviewLoop` already does) and asserting the event through `plan_tool.telemetry.read_decisions(repo_root)` — never by reading raw `decisions.jsonl` bytes. Pass `repo_root=tmp_path` and a `slug` so the recorder has a write target. A new test class (e.g. `TestStepReviewAssessmentTelemetry`) is the natural home.

- `test_interactive_pass_records_one_assessment` — an interactive review of a clean step list writes exactly one event with `kind="granularity"`, `decision="create-review"`, `context["stage"]=="create"`, and `mode=="interactive"`.
- `test_assessment_records_candidate_fingerprint` — two identical incoming candidate lists produce the same `candidate_fingerprint`, while changing a step title, change type, or full file footprint changes the fingerprint.
- `test_assessment_records_file_footprint` — a candidate list with repeated file names across `files` and `creates` records `file_footprint` as the distinct full declared path count.
- `test_assessment_counts_split_findings_and_distinct_steps` — a candidate list where one step produces multiple split findings records `split` as the finding count, `split_steps` as the distinct split-hit step count, and `split_step_ids` with the step id only once.
- `test_assessment_counts_split_and_merge` — a candidate list that trips a `granularity-split` predicate records `split>=1` and the offending id as a string in `split_step_ids`; a list that trips `granularity-merge` records `merge>=1`.
- `test_assessment_predicate_counts_use_helper` — a step whose title fires a known deterministic predicate records that key in `predicate_counts` (proves the count comes from `split_predicate_key`, not prose parsing).
- `test_yes_mode_records_assessment` — the `--yes` path records one event with `mode=="yes"` and does not prompt.
- `test_non_tty_mode_records_assessment` — a non-TTY pass (stdin not a TTY) records one event with `mode=="non_tty"`.
- `test_checkpoint_resume_records_assessment` — a resume that restores a saved review records one event with `mode=="checkpoint"`; this pins the event as separately filterable rather than a fresh-signal event.
- `test_no_repo_root_records_nothing` — calling with `repo_root=None` records no event and still returns the reviewed list.
- `test_advisor_failure_records_nothing_but_review_succeeds` — when `assess_granularity` is monkeypatched to raise, the review still returns the steps and no assessment event is written (the helper swallowed the failure).
- `test_can_split_reflects_invoker` — `can_split` is `true` when an invoker is wired and `false` when `invoker=None`.
- `test_advisor_runs_for_telemetry_when_cannot_split` — with `invoker=None` (so `can_split` is `False`) **and** a `repo_root`, the helper still consults `assess_granularity` (non-raising stub) and records one assessment event; pins the "advisor runs for telemetry regardless of `can_split`" behavior the suppressed-hint guard cannot, because that guard passes no `repo_root`.

**Existing test — leave it as-is; do not swap the raising stub.** `test_hint_suppressed_when_cannot_split` (in `TestStepReviewLoop`) monkeypatches `assess_granularity` to raise an `AssertionError` and asserts the `granularity:` hint line is absent when `can_split` is `False`. That test passes **no `repo_root`**, so this step's assessment helper returns early on `repo_root is None` before it would call `assess_granularity` — the raising stub is never reached and the test stays green unmodified. Do not swap the raising stub for a non-raising one: that swap rests on the false premise that the helper reaches the advisor here, and it would weaken a passing guard. To cover the new "advisor runs for telemetry regardless of `can_split`" behavior, add a **separate** test that passes a `repo_root` (so the helper does not return early) and a non-raising stub, asserting the advisor was consulted and an event was recorded even with `invoker=None` — leave the existing hint-suppression guard intact.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each test above alongside the helper and the four record sites. **Green-before-done gate:** every new test must pass, the existing `test_hint_suppressed_when_cannot_split` must stay green unmodified, and the rest of `tests/test_create.py` (especially `TestStepReviewLoop`, `TestCreatePlanStepReviewYes`, `TestStepReviewCheckpoint`) must stay green, before this step is finished. Run at minimum `uv run pytest tests/test_create.py -q`.

## Acceptance criteria

- An interactive `_review_step_change_types` pass writes exactly one event readable via `read_decisions` with `kind="granularity"`, `decision="create-review"`, and context keys `stage` (`="create"`), `steps`, `candidate_fingerprint`, `file_footprint`, `split`, `split_steps`, `merge`, `split_step_ids`, `predicate_counts`, `can_split`, `mode`.
- The assessment event carries the review loop's `slug` as top-level `plan_slug` (using `slug or ""` if the caller supplied `None`).
- `mode` records `"interactive"`, `"yes"`, `"non_tty"`, or `"checkpoint"` matching the branch the pass took.
- `file_footprint` equals the count of distinct file paths declared across the candidate steps' full file footprints (`files` plus `creates`).
- `split` / `merge` equal the number of `granularity-split` / `granularity-merge` findings the advisor returns for the candidate list; `split_steps` equals the number of distinct steps with at least one split finding; `split_step_ids` lists those ids once each as strings in candidate-list order.
- `predicate_counts` is built by mapping split findings through step 2's `split_predicate_key`, not by parsing prose.
- `predicate_counts` contains only create-stage deterministic predicate keys (`mixed-verbs`, `two-clauses`, `multi-area`); prose `mixed-step` remains supported by step 2's helper for future/detail-stage callers but is not documented as a create-review output.
- `can_split` reflects whether an invoker was wired (`invoker is not None`); `mode` distinguishes whether a UI was presented.
- Checkpoint-resume events use `mode=="checkpoint"` and the plan contract documents that this mode is excluded from "fresh signal fired" counts; repeated non-checkpoint observations of the same list are dedupable by `candidate_fingerprint`.
- Calling with `repo_root=None`, or when `assess_granularity` raises, writes no event and leaves the reviewed list, prompts, and return value unchanged.
- All new tests pass and `test_hint_suppressed_when_cannot_split` stays green unmodified (it passes no `repo_root`, so the helper returns early before the advisor); existing `tests/test_create.py` cases stay green.

## References

- [JSON Lines (jsonlines.org)](https://jsonlines.org/) — the one-object-per-line format the assessment event is appended in.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture the new hermetic tests use as `repo_root` to read events back through `read_decisions`.
- [Fixtures reference — pytest documentation](https://docs.pytest.org/en/stable/reference/fixtures.html) — `monkeypatch` and stdin/`isatty` stubbing used to drive each mode branch offline.

## Deferred

- **Per-step outcome events** — accept / override / split-requested / split-applied / split-unusable / split-invalid / split-error / unclassified-accepted are step 5's job in the same file, using step 3's `record_create_step_outcome`. This step records only the per-pass assessment.
- **`DATA_CONTRACT.md` documentation** — step 6 documents the new `decision="create-review"` value and its context keys and updates `tests/test_data_contract.py`; this step writes no contract doc.
- **Building the predicate vocabulary** — step 2 owns the exported predicate keys and `split_predicate_key`; this step only consumes them.
- **Plan-level oversized-plan advisory** — using the recorded data to warn "this is more than one plan" is out of scope (plan's Out of scope / Deferred); this step records, it does not act.
- **Aggregation / `plan-tool telemetry` report** — reading these events back into a summary is a separate future surface.
