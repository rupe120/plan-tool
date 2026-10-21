# Step 5 — Make create concept review resumable and terminal-driven

## Summary

This step gives create-time concept review a dedicated unsigned resume record in `plan_tool/concept_tree.py` and wires it into `plan_tool/create.py:create_plan`. Each accepted decision and ownership selection is saved before review advances, so an interrupted run can continue without using or overwriting a finalized plan’s `concepts.json`. Terminal availability and `--yes` become the only inputs that control whether approval is requested, with explicit interactive confirmation required before `review_concept_scope(..., sign_off=True)`. On green, compatible runs resume saved progress, conflicting inputs stop safely, and unattended runs preserve proposals without creating approval or ownership links.

## Table of Contents

- [Summary](#summary) — The resumable review behavior and observable result.
- [Why](#why) — Why the current create review loses progress and prompts inconsistently.
- [Input](#input) — The concept, step, and step-2 contracts this feature consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The seven files changed by this step.
- [Implementation](#implementation) — Resume-record persistence, compatibility, review flow, and terminal rules.
- [Tests](#tests) — Unit and integration coverage for interruption, resume, conflicts, and approval.
- [Acceptance criteria](#acceptance-criteria) — Observable checks that prove the review is durable and safe.
- [References](#references) — Primary documentation for terminal checks, atomic replacement, hashes, and test seams.
- [Deferred](#deferred) — Create publication and enforcement work owned by later steps.

## Why

`plan_tool/create.py:_review_create_concepts` currently keeps all choices in memory and signs them merely because its caller classified the run as interactive. A crash or interrupt before the final plan write loses the entire review, while `plan_tool/create.py:create_plan` can only reuse `concepts.json` after the prospective plan already exists. Its interactive test also depends on `input_fn` and `concept_invoker` identity, so injecting a backend can change whether approval is requested even though terminal availability has not changed. Create needs an unsigned, collision-safe progress record that saves every accepted selection and requires a real terminal confirmation before approval.

## Input

- **Step 2 publication contract** — step 2 provides the typed unsigned and signed concept publication intents. This step prepares compatible reviewed state for those intents but does not publish through the transaction authority.
- **Concept record** — `plan_tool/concept_tree.py:ConceptTree`, `ConceptNode`, `_validate_tree`, `load_concepts`, and `save_concepts` define the finalized sidecar shape. The resume record must not change these fields or `CONCEPTS_SCHEMA_VERSION`.
- **Review policy** — `plan_tool/concept_review.py:review_concept_scope` remains the authority for decision validation and approval metadata. Saved progress is unsigned; only the terminal confirmation path may call it with `sign_off=True`.
- **Settled steps** — `plan_tool/create.py:create_plan` invokes concept review after `_review_step_change_types` and `_review_step_gates`. Compatibility and ownership validation therefore use that settled step list, including `Step.id`, `Step.scope`, and `Step.concept_ids`.
- **Prospective identity** — `plan_tool/create.py:predict_plan_path` supplies the intended plan path before the Markdown exists. The resume key must also cover the evidence and settled inputs that produced the concept candidates.
- **Existing resume flag** — `plan_tool/create.py:create_plan(resume=...)` controls whether compatible saved progress may be loaded. A no-resume run may start fresh, but accepted selections still need durable saves until successful completion.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — define the unsigned create-review resume record, its dedicated path, strict validation, and atomic read/write helpers.
  - `plan_tool/create.py` — make `_review_create_concepts` persist each selection, resume compatible progress, require terminal confirmation for approval, and update `create_plan` orchestration.
  - `plan_tool/data_contract.py` — register the new persisted resume dataclass and its independent schema constant.
  - `DATA_CONTRACT.md` — document the create-review resume location, fields, compatibility rules, unsigned meaning, and cleanup boundary.
  - `tests/test_concept_tree.py` — cover resume paths, serialization, validation, atomic replacement, and separation from `concepts.json`.
  - `tests/test_create.py` — cover per-selection saves, continuation, terminal behavior, conflicts, deterministic seed preservation, and create orchestration.
  - `tests/test_data_contract.py` — extend drift checks to the new resume record and schema constant.

## Implementation

The foundational logic is: **save each create concept-review selection as compatible unsigned progress, and create approval only after explicit confirmation on a terminal**.

- **Add a separate persisted resume contract in `plan_tool/concept_tree.py`.** Use a clearly named record such as `CreateConceptReviewResume` with its own schema-version constant. It should retain:
  - The plan slug and prospective plan identity.
  - A stable compatibility digest covering the evidence/seed and settled step inputs.
  - The unsigned candidate tree.
  - Accepted decisions and owner-step selections.
  - Enough progress state to distinguish a reviewed choice from a default that has not yet been presented.

  Keep the record strict and closed like `_decode_tree`; malformed types, unknown fields, duplicate concept IDs, unknown decisions, and inconsistent progress markers must not be silently ignored.

- **Use a dedicated resume path.** Resolve it beneath `.plan-tool/create-resume/<slug>/`, keyed by the prospective plan identity and compatibility digest. It must never use `concepts_path`, `load_concepts`, `save_concepts`, or the incumbent plan’s `plan-details/<slug>/concepts.json`.

- **Keep resume state explicitly unsigned.** Do not add a fake final `plan_fingerprint`, approved `review_state`, or sign-off metadata to represent unfinished work. If the resume record embeds a `ConceptTree`, document and validate that its fingerprint identifies the review source state rather than finalized plan bytes. Reject any resume record containing approval or the `signoff_decision` or `signoff_source_state` metadata written by `review_concept_scope`.

- **Persist through one injected durable writer seam.** Extend `_review_create_concepts` with a save callback, or an equivalent small persistence interface, supplied by `create_plan`. After every accepted decision and every accepted ownership selection, update unsigned progress and invoke that writer before moving to the next prompt. The writer must flush and fsync the replacement file, atomically install it, and fsync the resume directory entry before acknowledging the selection. Do not batch the walk into one final save.

- **Cross the recovery boundary before the first resume save.** The CLI command retains its repository lock while review prompts remain read-only. Immediately before the first accepted unsigned selection or unattended safe-state save would mutate `.plan-tool/create-resume/`, invoke step 3’s automatic recovery under that lock. A block there writes no resume state. Once that boundary succeeds, later selections and a declined final approval may intentionally retain only the unsigned resume record; they must not publish the plan, finalized sidecar, manifest, archives, or details.

- **Resume the object that was saved.** When `resume=True`, load compatible progress before enrichment or prompting, reconcile it with the fresh deterministic concept tree, and continue from its saved decision and ownership markers. Skip only selections proven complete; do not reset earlier answers or replay their prompts.

- **Protect deterministic concepts.** Reuse `plan_tool/concept_bootstrap.py:rederive_concepts` when comparing saved progress with freshly bootstrapped concepts. Preserve new deterministic seeds when compatible, preserve previously saved enrichment when the current enrichment call fails, and stop with `CreateError` when re-derivation reports a real conflict.

- **Treat changed inputs as a conflict, not a cache miss.** A resume record for the same prospective identity with a different evidence or settled-step digest must not be loaded as current and must not be silently replaced. Report the mismatch and require an explicit fresh start, such as `resume=False`, so old operator choices are never applied to changed evidence.

- **Do not reuse generic Claude checkpoints.** `plan_tool/checkpoint.py:Checkpoint` is fail-soft memoization for repeatable backend output and deliberately treats stale or malformed data as absent. Create-review progress carries operator decisions and needs strict mismatch and corruption handling, so it requires its own contract.

- **Make terminal behavior direct and predictable.** In `plan_tool/create.py:create_plan`, remove the `input_fn is input` and `concept_invoker is not shell_concept_invoker` conditions around concept review. Use this order:
  - `yes=True` — do not prompt; persist the safe unsigned state once.
  - `not sys.stdin.isatty()` — do not prompt; persist the safe unsigned state once.
  - Terminal available — continue the interactive walk and ask for explicit final confirmation.

  An injected input function or concept backend must not change which branch runs. Tests may use an injected terminal predicate if that keeps terminal checks deterministic, but production behavior must still come from `sys.stdin.isatty()`.

- **Separate selection from sign-off.** Apply saved and newly entered choices without approval while the walk is in progress. Once every concept decision and required ownership answer is complete, ask for a clear confirmation. Only that affirmative terminal answer may call `review_concept_scope(..., sign_off=True)` and project accepted owner links into the returned `Step.concept_ids`.

- **Keep unsigned ownership out of the plan.** Non-TTY, `--yes`, interrupted, declined-confirmation, and resumed-but-unconfirmed runs may retain owner suggestions in the resume record, but the returned steps must not gain authoritative `concept_ids`. This preserves the existing rule in `_review_create_concepts` that unattended suggestions do not become ownership.

- **Keep the saved checkpoint unsigned even at confirmation.** Save the final completed unsigned selection state before applying approval in memory. If the process stops after confirmation but before final publication, the next run must ask for confirmation again rather than treating the resume file as proof of approval.

- **Handle cleanup at the existing completion boundary.** While this step still uses create’s current final write path, remove the resume record only after the plan and final concept sidecar have completed successfully. Leave it intact on exceptions and interrupts. Step 7 will replace this temporary completion behavior with promotion inside the publication transaction.

- **Document the independent contract.** Register `CreateConceptReviewResume` in `plan_tool/data_contract.py:persisted_dataclass_contracts` and add a matching `DATA_CONTRACT.md` subsection. State that the record is local pre-publication progress, is never scope authority, is separate from `ConceptTree.plan_fingerprint` freshness for a finalized plan, and may be deleted after successful create publication.

- **Do not bump the finalized sidecar schema.** `plan_tool/concept_tree.py:CONCEPTS_SCHEMA_VERSION`, `_decode_tree`, `load_concepts`, and `save_concepts` must continue to accept and emit exactly the current `ConceptTree` and `ConceptNode` fields.

## Tests

- `tests/test_concept_tree.py:test_create_review_resume_path_is_separate_from_concepts_path` — the resume record lives under `.plan-tool/create-resume/<slug>/` and cannot alias an incumbent `concepts.json`.
- `tests/test_concept_tree.py:test_create_review_resume_round_trips_unsigned_progress` — decisions, owners, and progress markers survive an exact save/load round trip without approval metadata.
- `tests/test_concept_tree.py:test_create_review_resume_rejects_approved_tree` — approved review state or sign-off metadata cannot enter the unsigned resume record.
- `tests/test_concept_tree.py:test_create_review_resume_rejects_malformed_or_unknown_fields` — strict decoding rejects corrupt types, missing fields, unknown fields, and duplicate identifiers.
- `tests/test_concept_tree.py:test_create_review_resume_input_mismatch_is_distinct_from_absence` — changed prospective identity or compatibility digest raises a stale/conflict result rather than returning no record.
- `tests/test_concept_tree.py:test_failed_create_review_resume_replace_preserves_previous_record` — a failed atomic replacement leaves the prior complete resume record readable.
- `tests/test_concept_tree.py:test_create_review_resume_is_durable_before_prompt_advances` — file and parent-directory fsync complete before the next selection is requested.
- `tests/test_concept_tree.py:test_create_review_resume_schema_does_not_change_concepts_schema` — finalized `ConceptTree` JSON retains its exact existing field set and schema version.
- `tests/test_create.py:test_review_create_concepts_saves_after_every_selection` — the save spy is called after each decision and ownership answer, in review order.
- `tests/test_create.py:test_review_create_concepts_reentry_continues_saved_progress` — a partially reviewed record skips completed prompts and continues at the first unfinished selection.
- `tests/test_create.py:test_review_create_concepts_interrupt_preserves_last_selection` — an input interruption leaves every earlier accepted choice in the durable resume record.
- `tests/test_create.py:test_review_create_concepts_requires_terminal_confirmation_for_signoff` — completed choices remain unsigned until the operator explicitly confirms.
- `tests/test_create.py:test_review_create_concepts_declined_confirmation_stays_unsigned` — declining confirmation preserves resume progress but returns no approval or authoritative ownership.
- `tests/test_create.py:test_review_create_concepts_recovers_before_first_resume_save` — automatic publication recovery runs under the existing lock before the first resume write, and a blocking recovery leaves resume and final artifacts untouched.
- `tests/test_create.py:test_review_create_concepts_yes_accepts_unsigned_once` — `yes=True` performs no prompt, saves once, leaves concepts unreviewed, and leaves `Step.concept_ids` empty.
- `tests/test_create.py:test_review_create_concepts_non_tty_accepts_unsigned_once` — non-TTY behavior matches the safe unsigned result even with `yes=False`.
- `tests/test_create.py:test_concept_review_mode_ignores_input_and_backend_identity` — changing injected `input_fn` or `concept_invoker` does not change terminal-mode selection.
- `tests/test_create.py:test_create_resume_preserves_enrichment_when_retry_enrichment_fails` — compatible saved candidates survive an unusable enrichment response.
- `tests/test_create.py:test_create_resume_merges_new_deterministic_seeds` — compatible freshly bootstrapped concepts are retained alongside saved review progress.
- `tests/test_create.py:test_create_resume_stops_on_changed_evidence` — a changed seed/evidence digest raises `CreateError` instead of replaying or overwriting old choices.
- `tests/test_create.py:test_create_resume_stops_on_conflicting_deterministic_seed` — a re-derivation conflict stops before approval or final writes.
- `tests/test_create.py:test_create_resume_never_reads_incumbent_collision_sidecar` — replacement review uses only the dedicated resume namespace and leaves the incumbent sidecar unchanged.
- `tests/test_create.py:test_successful_create_discards_review_resume_after_final_write` — the current completion path removes progress only after the final plan and concept record succeed.
- `tests/test_create.py:test_failed_create_keeps_review_resume` — failure before final completion leaves compatible progress available for another run.
- `tests/test_data_contract.py:test_contract_registry_names_create_concept_review_resume` — the new persisted dataclass is registered.
- `tests/test_data_contract.py:test_create_concept_review_resume_contract_is_documented` — every persisted field, schema constant, path, unsigned rule, and compatibility rule appears in its own contract section.
- `tests/test_data_contract.py:test_concept_contract_remains_version_one` — the new resume contract does not alter `CONCEPTS_SCHEMA_VERSION`.

### Test-creation order (feature step)

1. Add resume path, strict round-trip, unsigned-only, mismatch, and atomic replacement tests in `tests/test_concept_tree.py`.
2. Add per-selection persistence and partial re-entry tests around `plan_tool/create.py:_review_create_concepts`.
3. Add `--yes`, non-TTY, interactive confirmation, declined confirmation, and injection-independence tests.
4. Add create orchestration tests for compatible resume, changed evidence, deterministic seed merging/conflicts, collision separation, cleanup, and failure retention.
5. Add the registry and documentation drift tests in `tests/test_data_contract.py`.
6. Run the existing concept-tree round-trip, create ownership, unattended review, and create integration tests unchanged except where their old incumbent-sidecar resume expectation is replaced by the dedicated resume contract.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- Create-review progress is stored only beneath `.plan-tool/create-resume/<slug>/` and never at `plan_tool/concept_tree.py:concepts_path`.
- Every accepted concept decision and ownership selection is atomically saved before the next prompt.
- Re-entering with compatible inputs skips completed selections and resumes at the first unfinished selection.
- Changed evidence, prospective identity, settled steps, malformed progress, or conflicting deterministic seeds stop review without creating approval or overwriting the saved record.
- A failed enrichment call does not erase compatible deterministic or previously saved concept candidates.
- `yes=True` and non-TTY runs perform no concept-review prompts, save one unsigned result, leave all concepts unapproved, and add no authoritative `Step.concept_ids`.
- Interactive mode depends only on terminal availability and `yes`; injected input and backend functions do not affect it.
- Only an explicit final confirmation on a terminal can produce approved concepts and accepted step ownership.
- An interrupt after any selection leaves all earlier selections available on the next compatible run.
- Successful create completion removes the temporary resume record only after the current final plan and concept sidecar writes succeed; failed completion retains it.
- `DATA_CONTRACT.md` documents every persisted resume field and clearly distinguishes resume progress from finalized `ConceptTree` authority.
- `plan_tool/concept_tree.py:CONCEPTS_SCHEMA_VERSION`, `ConceptTree`, `ConceptNode`, `_decode_tree`, `load_concepts`, and `save_concepts` retain their existing finalized-sidecar contract.
- All new tests in `tests/test_concept_tree.py`, `tests/test_create.py`, and `tests/test_data_contract.py` pass.

## References

- [Python 3.13 os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Use `os.replace` for complete-file replacement and `isatty` semantics for the approval gate.
- [Python 3.13 tempfile — Generate temporary files and directories](https://docs.python.org/3.13/library/tempfile.html) — Use same-directory temporary files when atomically saving resume progress.
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Use SHA-256 to bind resume progress to prospective identity and review inputs.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Control terminal checks, interrupts, atomic-write failures, and injected review seams in tests.

## Deferred

- Create artifact-bundle preparation — step 6 prepares the plan, concept record, details, collision state, and manifest mutation as one publication input.
- Transactional resume promotion and cleanup — step 7 promotes compatible unsigned resume state to final `concepts.json` only inside successful all-or-recoverable publication.
- Collision archive and manifest recovery — step 7 owns restoration when create publication fails after live mutation begins.
- Production direct-writer enforcement — step 12 adds the source scan that restricts decision-bearing uses of `save_concepts`, `write_concepts`, and raw `concepts_path` writes.
- Shared interactive-input helper consolidation — the small review prompts remain local to `plan_tool/create.py`; consolidating them with other interactive commands would be a separate refactor outside this feature step.
