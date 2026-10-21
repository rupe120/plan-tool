> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Record that a revision's feedback was delivered, carrying ids and counts but no feedback text

## Summary

Add one run-log event to `plan_tool/run_log.py` — `RevisionFeedbackDelivered` — that records **that a stage revision was written, and against which bytes** — it fires for every written revision, including one whose predecessor carries no feedback at all (`feedback_count` 0, empty ids, and `counts_by_state` still carrying all three lifecycle states at zero (not an empty map — the all-states rule holds unconditionally, which is what lets a reader index it without a `.get`)), so a zero-count line is the intended marker and not a defect. It carries the stage number, the predecessor artifact's digest, the feedback ids, and the counts by lifecycle state. Register it in `plan_tool/data_contract.py` and document it in `DATA_CONTRACT.md` beside the `GateViolations` section it is modeled on. The key design decision: **the event has no field and the emit helper has no parameter that can carry the reviewer's request or the model's proposed response** — omission is a fact about the signature, not a redaction pass over text someone handed in. On green, a caller can prove a revision was delivered and to which ids, the JSONL line stays under the 4096-byte cap however many ids there are, and `RUN_LOG_SCHEMA_VERSION` is still `2`.

## Table of Contents

- [Summary](#summary) — what the event carries and what it deliberately cannot carry.
- [Why](#why) — delivery is invisible today, and the obvious fix copies sensitive text into a local log.
- [Input](#input) — the run-log and data-contract contracts this step extends, and what it can't check.
- [Files (creates vs edits)](#files-creates-vs-edits) — three declared edits plus two additions, each with its reason.
- [Implementation](#implementation) — the event shape, the rules that are not free to vary, and the alternatives rejected.
- [Tests](#tests) — the new roster in `tests/test_run_log.py` and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs that bear on the event's fields.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's code.
- [Deferred](#deferred) — the producer wiring and everything else later steps own.

## Why

A revision run is the one place where a human's words enter a model prompt, and nothing on disk records that it happened. `phase_end` says `ok` or `exhausted`; `claude_call_start` says how many prompt bytes went out. Neither answers "which feedback ids did this run actually deliver, and against which prior artifact?" — the question a reviewer asks when a response looks like it ignored one of three requests. The obvious fix is to log the feedback, and that is the wrong fix: the request text is the reviewer's own prose about their project and can carry context they would not choose to copy into `.plan-tool/runs/`. It also already lives in the committed artifact, so a copy in the log is duplication, not evidence. This step ships the narrow thing instead — ids, counts, stage, digest — and makes the omission structural, so no later caller has to remember a redaction rule.

## Input

This step reads contracts that already ship; each must stay true.

- **`plan_tool/run_log.py` is a leaf with no module-level first-party imports.** Its docstring states the rule; the only first-party imports in the file are lazy, inside `RunLogWriter.bind_shell_sink` and `telemetry_run_id_scope`. This step adds none — which is why the lifecycle-state names arrive as caller-supplied strings rather than as an import of step 1's vocabulary.
- **`GateViolations` is the sibling to model.** It is the only other event this plan's arc added, and it settled the shape: an exact count field, a bounded list field, and an omitted-count field. Reuse that shape rather than inventing a second way to bound a list.
- **`_bounded_violations` and `_append_jsonl_line` own the size rules.** `_bounded_violations` keeps whole strings up to `_MAX_VIOLATION_BYTES_IN_PAYLOAD` and reports how many were dropped; `_append_jsonl_line` truncates any single over-long string via `_truncate_long_strings` and raises `RunLogLineTooLarge` when the whole line still exceeds `_MAX_LINE_BYTES`. That raise is the hazard: an observability event must never break the run it observes.
- **`plan_tool/data_contract.py:persisted_dataclass_contracts` is the registry, and registration is not optional here.** `tests/test_data_contract.py:_obsolete_dataclass_sections` flags any `DATA_CONTRACT.md` heading shaped `` `Name` (`something.py`) `` whose name is not in the registry, and `test_obsolete_contract_section_fails_contract_check` asserts the doc currently produces an empty set. Documenting the event under the sibling's heading style without registering it turns that test red.
- **The registry's guard tests are parameterized, so they need no edit.** `test_documented_fields_are_registered_or_aliases` and `test_every_persisted_field_is_documented_in_own_section` iterate `persisted_dataclass_contracts()`; a new entry is covered the moment it is added. `test_contract_registry_names_persisted_dataclasses` asserts a subset (`<=`), so it does not need the new owner either.
- **What this step cannot check.** Every emit helper accepts `**extra` keys that are merged into the payload, so a future caller *could* put text in the log by hand. This step's guarantee is narrower and honest: the event's own fields offer no text channel. Keeping text out of `extra` is the producer's contract — step 6, which wires the call.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/run_log.py` — add the `RevisionFeedbackDelivered` frozen dataclass, add it to the `Event` union, and add the matching `RunLogWriter.revision_feedback_delivered` emit helper next to `gate_violations`. If a size budget for the id list is needed, reuse `_bounded_violations` rather than adding a second bounding helper.
  - `DATA_CONTRACT.md` — add a `### RevisionFeedbackDelivered (run_log.py)` subsection under `## Run log events`, beside the existing `GateViolations` subsection, with one table row per field.
  - `tests/test_run_log.py` — add a `revision_feedback_delivered` section after the existing `gate_violations` block, reusing the module's `_make_writer` / `_read_events` helpers.

- **Declared in the step's `files:` list, each required — listed here because the reason is not obvious from the path:**
  - `plan_tool/data_contract.py` — one `PersistedDataclassContract` entry for the new event. Without it the new doc heading fails `tests/test_data_contract.py`, so this is not optional polish. Same one-entry edit the `GateViolations` change made.
  - `README.md` — one bullet in the "What's recorded per run" list under the run-log section. That list enumerates every event kind including `gate_violations`; leaving the new kind out makes the list wrong by omission.

## Implementation

### What must be true when the step is done

- A caller with a writer can record one delivery: `writer.revision_feedback_delivered(...)` appends a single JSONL line carrying the discriminator `revision_feedback_delivered`, the phase, the stage number, the predecessor digest, the exact feedback count, the ids, how many ids were dropped, and the counts by lifecycle state.
- No parameter of that method, and no field of the dataclass, can hold a reviewer's request or a model's proposed response.
- The line never exceeds `_MAX_LINE_BYTES`, whatever the id list looks like.
- `plan_tool/roadmap.py` is untouched — this step ships the primitive, and nothing calls it yet.

### Event shape

Mirror `GateViolations` field-for-field where the concern is the same.

- **`phase: str`** — the caller's phase label. `plan_tool/roadmap.py:_run_stage` builds phase strings as `stage-{number}-{name}`, and `plan_tool/cli/runs.py`'s `runs show` renderer prints `phase` from its extras allowlist, so carrying it keeps the new line readable with no renderer change.
- **`stage: int`** — the stage number as a number. `phase` already contains it as text, but digging a number back out of a display string is the brittleness worth one field. Note the contrast: `GateViolations` takes `stage` through `**extra` at its producer, so it is not drift-guarded there; as a declared field here it is.
- **`predecessor_digest: str`** — a hex digest of the prior artifact's bytes, **supplied by the caller**. Do not hash inside `run_log.py`: the writer records what it is handed, every other event follows that rule, and hashing here would mean passing the artifact bytes into an event helper.
- **`feedback_count: int`** — the exact number of feedback rows delivered, always exact whether or not every id was retained.
- **`feedback_ids: list[str]`** — the ids, whole, up to the payload budget.
- **`feedback_ids_omitted: int`** — how many ids did not fit; `feedback_count - len(feedback_ids)`.
- **`counts_by_state: dict[str, int]`** — lifecycle-state name → count, keys supplied by the caller.
- **`event: str = "revision_feedback_delivered"`** — the discriminator, declared last, as every other event does so the redefined base field keeps its position.

**Deliberately dropped: `attempt`.** `GateViolations` carries it because it fires once per rejected attempt. A delivery fires once per written revision, so an attempt number here would be a field with no meaning to fill in — and an unused number is exactly the field a later author gives a meaning the design never wanted.

### The two rules that are not free to vary

- **The lifecycle vocabulary stays out of `run_log.py`.** `counts_by_state` is a plain string-keyed mapping, not three typed fields named after `open` / `awaiting-review` / `deferred`. Step 1 owns that vocabulary in `plan_tool/roadmap_artifacts.py`; a second copy here would put a closed vocabulary in two homes and would push a leaf module into importing from a module above it, against the plan's one-way dependency line. Declare the field as an open bag in the registry entry (`open_bag_fields`, the same label `DecisionEvent.context` carries) so the registry snapshot says so honestly — it is descriptive metadata, not an enforced check.
- **The id list is bounded, and bounding never fails a run.** A long id list must not push the line past `_MAX_LINE_BYTES` and raise `RunLogLineTooLarge`. Reuse `_bounded_violations` — it takes any `Sequence[str]`, counts serialized bytes, keeps whole strings, and returns `(kept, omitted)`; its budget is a byte figure, not a claim about messages. **Do not write a second bounding helper:** `tests/test_duplication.py` fails on a new exact-duplicate function body of four lines or more, and a copy of that loop is one. If reuse genuinely does not fit, add a keyword-only budget parameter defaulting to today's constant rather than forking the body — and keep it at that, since a real extract is a separate change from this one.

### Things to leave alone

- **Do not bump `RUN_LOG_SCHEMA_VERSION`.** It stays `2`, and `tests/test_run_log.py:test_schema_version_is_two` stays green. The version gates `read_in_flight`'s accept/reject and the `runs` schema check, so a bump would treat every in-flight snapshot written by an older process as "no in-flight run" — real cost for an additive event kind that readers already tolerate. `GateViolations` was added the same way, with no bump.
- **Do not touch `plan_tool/cli/runs.py`.** `runs show` prints any event kind generically and takes its extra columns from a fixed key allowlist, so the new line renders without a change there. A field-aware row is not needed to prove delivery.
- **Do not add a call site.** Producing the digest, choosing what counts as delivered, and calling the helper all belong to step 6.

### Doc and registry edits

- The `DATA_CONTRACT.md` subsection follows the `GateViolations` one: a short paragraph saying what the event answers and why the text is absent, then a `| field | description |` table with one row per field, then a `Producer:` line. Name step 6's writer as the producer that will emit it, and say plainly that the request and response text are not recorded because they already live in the committed artifact.
- The registry entry is one `PersistedDataclassContract(owner=..., cls=run_log.RevisionFeedbackDelivered, section_title=..., source_symbol="plan_tool/run_log.py:RevisionFeedbackDelivered", open_bag_fields=...)` beside the `GateViolations` entry. `section_title` must match the heading text the doc uses, since `_section` looks the section up by substring.

### Rejected alternatives

- **Log the feedback text and scrub it.** A redaction pass has to decide what counts as sensitive, which is a judgment no test can settle, and it leaves a channel that only works when every caller remembers it. A signature with no text parameter needs no one to remember anything.
- **A separate feedback-delivery sidecar file.** The plan's fence rules out a second store; the run log is where per-run evidence already lives, and `runs show` / `runs list` already read it.

## Tests

All new cases land in `tests/test_run_log.py`, in a new `# ---------- revision_feedback_delivered ----------` block placed after the existing `gate_violations` block, reusing that module's `_make_writer` and `_read_events` helpers. No new fixture or test class is needed.

### Tests for this step

- `test_revision_feedback_delivered_records_stage_digest_ids_and_counts` — one call writes one line whose `event` is `revision_feedback_delivered` and which carries `phase`, `stage`, `predecessor_digest`, `feedback_count`, `feedback_ids`, and `counts_by_state` as given.
- `test_revision_feedback_delivered_has_no_text_field` — the dataclass's field names, read with `dataclasses.fields`, contain nothing named for a request, response, body, message, or text. This is the step's structural claim, checked against the field set rather than against any particular content.
- `test_revision_feedback_delivered_omits_request_and_response_text` — build stand-in feedback rows whose request and proposed-response strings are distinctive sentinels, derive ids and counts from them, emit, and assert neither sentinel appears anywhere in the raw JSONL. Proves the helper's shape leaves no way to pass the text in.
- `test_revision_feedback_delivered_keeps_the_exact_count_when_ids_are_dropped` — with more ids than the payload budget holds, `feedback_count` stays the true total and `feedback_ids_omitted` accounts for every id not kept.
- `test_revision_feedback_delivered_keeps_retained_ids_whole` — retained ids are the caller's ids unchanged, in order, with no mid-string cut.
- `test_revision_feedback_delivered_line_stays_under_the_cap` — a deliberately oversized id list still produces a line under `_MAX_LINE_BYTES`, and the call does not raise `RunLogLineTooLarge`.
- `test_revision_feedback_delivered_counts_map_keeps_caller_state_keys` — the state names in `counts_by_state` are written exactly as the caller supplied them; the module mints no vocabulary of its own.
- `test_revision_feedback_delivered_is_appendable_as_an_event` — an instance passes through `append_event` (it is a member of the `Event` union), matching the construction-section style the existing event tests use.

Existing tests this step must leave green without editing them:

- `tests/test_run_log.py:test_schema_version_is_two` — the version does not move.
- `tests/test_data_contract.py` — every registry-parameterized case picks the new entry up on its own, and `test_obsolete_contract_section_fails_contract_check` stays green only because the new doc section is registered.
- `tests/test_duplication.py` — no new duplicate group from the bounding logic.

**Green-before-done gate:** every case above, plus the three existing suites named, must pass before this step is finished. Run `uv run pytest tests/test_run_log.py tests/test_data_contract.py tests/test_duplication.py -q` at minimum, and the full suite before committing.

## Acceptance criteria

- `rg 'revision_feedback_delivered' plan_tool/run_log.py` finds the dataclass discriminator, the `Event` union member, and the `RunLogWriter` emit helper.
- `dataclasses.fields(RevisionFeedbackDelivered)` yields field names containing none of `request`, `response`, `text`, `body`, `message`.
- Emitting the event with 200 ids writes exactly one line, that line is under 4096 bytes, and the call raises nothing.
- `feedback_count` equals the number of ids the caller passed, in every case, including when `feedback_ids_omitted` is greater than zero.
- `RUN_LOG_SCHEMA_VERSION == 2` and `tests/test_run_log.py:test_schema_version_is_two` passes unchanged.
- `uv run pytest tests/test_data_contract.py -q` passes, including `test_obsolete_contract_section_fails_contract_check`.
- `uv run pytest tests/test_duplication.py -q` passes.
- `rg '^from plan_tool|^import plan_tool' plan_tool/run_log.py` returns nothing — the module keeps no module-level first-party import.
- `rg 'revision_feedback_delivered' plan_tool/roadmap.py plan_tool/cli/` returns nothing — this step adds no producer and no CLI surface.
- `DATA_CONTRACT.md` has a `RevisionFeedbackDelivered` subsection under `## Run log events` with one table row per dataclass field, and `README.md`'s per-run event list names the new kind.

## References

- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) and [headless mode](https://docs.claude.com/en/docs/claude-code/headless) — the invocation and exit-status contract the run log records around; useful for what a delivery event should and should not duplicate from a call's own events.
- [Prompt caching — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — why a stable predecessor-artifact prefix is worth identifying by digest when later measuring revision prompts.

## Applicable guardrails

- **The plan's "## Out of scope", second-store bullet.** This event is a record that a delivery happened, not feedback state. Nothing written here may be read back as authority by a later run; the artifact stays the only place review state lives.
- **The plan's "## Out of scope", no-cap-on-feedback bullet.** The byte budget on the id list bounds the *log line* only. It must never reject, warn about, or fail a run because of how much feedback there is.
- **The plan's "## Out of scope", non-interactive and roadmap-only bullet.** This step adds no CLI surface, no prompt, and no command.
- **The plan's "## Architecture", one-way dependency line.** `plan_tool/run_log.py` sits below `plan_tool/roadmap.py` and must not learn anything the roadmap modules own — which is why the lifecycle-state names arrive as caller data.
- **The step's own intent — auditable without duplicating human guidance.** This is the fence that binds hardest, because the tempting shortcut is exactly the useful one: adding a small text preview so the log "reads better". No preview, no truncated excerpt, no first-N-characters field.

## Deferred

- **Calling the event from `plan_tool/roadmap.py`** — step 6 owns the write path and decides when a revision counts as delivered.
- **Computing the predecessor digest** — step 6, alongside loading the predecessor (step 5's outcome). This step only carries the string it is given.
- **Keeping feedback text out of `**extra`** — a caller-side contract, tested with step 6's producer, not provable from `run_log.py`.
- **Naming the new fields in `plan_tool/cli/runs.py`'s `runs show` extras allowlist** — the line already renders by kind, and the fields are readable in the raw JSONL. File a `BACKLOG.md` entry if operators want a field-aware row.
- **Any judgment about whether the delivered feedback was honored** — outside the plan's scope by its "## Out of scope" first bullet, and not something a log line can settle.
- **Extracting a shared bounded-list helper across event kinds** — reuse `_bounded_violations` here; if a third caller ever needs it with a different budget, that extract is its own change.
