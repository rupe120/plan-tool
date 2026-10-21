> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Run guarded impact analysis with no-overwrite publication and temporary cleanup

## Summary

Create `plan_tool/roadmap_impact_run.py` and `tests/test_roadmap_impact_run.py` for the non-CLI runner that turns one exact escalation receipt into immutable impact-analysis evidence. The runner holds the existing roadmap writer guard across receipt validation, snapshot capture, relation closure, freshness recheck, and analysis publication. Its key decision is that a record is published only from one rechecked current snapshot, while an occupied final is reused only for exact candidate bytes. Green means step 9 can call a typed, redacted runner and inspect stored analyses without any canonical roadmap mutation.

## Table of Contents

- [Summary](#summary) — The runner’s completed behavior and observable result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why impact evidence needs one guarded execution boundary.
- [Input](#input) — The receipt, snapshot, closure, storage, and telemetry contracts the runner consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new runner files.
- [Implementation](#implementation) — Guarded admission, recheck, publication, lifecycle, and inspection rules.
- [Tests](#tests) — Focused runner coverage for valid, invalid, collision, and interruption paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for locking, publication, and controlled interleavings.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the runner.
- [Deferred](#deferred) — CLI, follow-on workflow, and wider lifecycle work left outside this step.

## Why

`plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` can create a current receipt, but it does not bind that receipt to all current roadmap inputs or publish impact evidence. Without one guarded runner, a valid receipt could be combined with changed artifact or brief inputs, and separate code could accidentally overwrite a semantic final or treat a stored record as current authority.

## Input

- **Receipt evidence:** Read only the caller-requested final from `plan_tool/roadmap_evidence_store.py:scan_evidence` in `EvidenceNamespace.ESCALATIONS`. Step 5 owns strict receipt parsing and validation through `plan_tool/roadmap_escalation.py:parse_receipt`, `validate_receipt_final_name`, and `validate_receipt_source_path`.

- **Step 4 planned snapshot output (dependency):** After step 4 lands, consume its successful capture and recheck contract. It supplies the full current gate result, parsed artifacts, raw-source-record digest, decoded-brief digest, and bound safe artifact digests. The snapshot module is not present at the current baseline.

- **Step 2/5 planned closure and analysis outputs (dependencies):** After those steps land, use their deterministic selected closure, analysis builder, canonical renderer, and exact occupied-final comparison. Do not reproduce relation traversal, receipt revalidation, route precedence, or canonical JSON rules here. Their modules are not present at the current baseline.

- **Storage and coordination:** Hold `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` while using step 6’s planned impact-analysis namespace extension with `plan_tool/roadmap_evidence_store.py:publish_evidence`. The namespace member is created by step 6, not supplied by HEAD.

- **Telemetry:** Use the closed impact lifecycle emitters that step 7 adds to `plan_tool/run_log.py:RunLogWriter`, then finish through `RunLogWriter.run_end`. The impact emitters are planned step-7 output, not existing methods.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_impact_run.py` — Define the guarded creation runner, redacted result and status contract, and read-only current-record inspection boundary.
  - `tests/test_roadmap_impact_run.py` — Cover guarded admission, freshness, immutable publication, telemetry, interruption, and no-mutation behavior.

- **Existing files (edits only):**
  - None.

## Implementation

- **Foundational logic — capture, bind, recheck, then publish under one guard.** Expose a typed entry point such as `run_roadmap_impact_analysis` in `plan_tool/roadmap_impact_run.py`. After validating the roadmap location, hold `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` until the runner has either returned a redacted terminal result or completed immutable publication and lifecycle logging.

- **Reject unavailable writer coordination before side effects.** If `roadmap_writer_guard` cannot acquire or provide its writer token, return the existing redacted no-route status-`1` result. Do not start telemetry, capture inputs, publish evidence, or fall through into CLI exception rendering. This creation-side operational failure is distinct from step 9’s completed, log-free reader `guard-unavailable` inspection state.

- **Require one exact receipt final.** The supplied final name selects the record; do not choose a receipt by scan order, time, or contents. `plan_tool/roadmap_evidence_store.py:scan_evidence` may supply the opaque record bytes, but only the entry whose name exactly matches the requested final is eligible. A missing, unreadable, malformed, mismatched, or stale receipt is an invalid admission and never creates an analysis.

- **Build only from dependency-owned facts.** Capture step 4’s current snapshot, compute step 2’s selected closure from the captured selected target and parsed artifacts, then pass both with the selected receipt to step 5’s analysis builder. The receipt reason can affect the step 5 route class, but it must not add closure nodes or artifacts. The builder rejects an unsafe or unmappable selected closure before any evidence, telemetry, or renderable result exists; an unsafe disconnected inventory relation is not an input to this decision.

- **Recheck while the guard remains held.** Immediately before publication, call step 4’s freshness operation on the original snapshot. A changed raw source-record byte stream, artifact bytes, decoded-text brief digest, canonical form, or current gate result makes the invocation invalid and leaves no analysis final. Do not replace this with digest comparison alone or move the recheck outside the guard.

- **Publish through the evidence store only.** Render the candidate with step 5’s canonical renderer and call `plan_tool/roadmap_evidence_store.py:publish_evidence` in `EvidenceNamespace.IMPACT_ANALYSES`. Do not write a final directly or manage a temporary file in the runner; the store owns no-overwrite linking, durability, and temporary cleanup.

- **Classify an occupied final without repairing it.** Map a created final to `created`. For an existing final, use step 5’s exact-byte comparison: equal canonical candidate bytes produce `reused`; every other payload, including malformed or wrong-final data, produces `collision` and keeps the stored bytes unchanged.

- **Return only redacted terminal facts.** Define a frozen result type, such as `ImpactRunResult`, that carries command outcome, status, durable analysis identity, route class, immutable publication outcome, and nullable next workflow. A `completed` result has one route class and one `created`/`reused` publication outcome; valid `requires-scope-review` is completed, retains its route class, has a null workflow, and returns status `0`. `preflight-rejected` returns `2`; post-admission or recheck `invalid`, distinct evidence-store `storage-rejected`, `collision`, `write-failed`, and return-only `telemetry-unavailable` return `1`; `interrupted` returns `130`. Failure results have no route, publication outcome, identity, or workflow. The command outcome is not the telemetry event vocabulary: only append-confirmed terminal outcomes become events. Follow `plan_tool/roadmap_escalation_run.py:EscalationRunResult` only for its status-family conventions and append-failure distinction, not its receipt-specific outcome vocabulary.

- **Make telemetry part of admission, not evidence authority.** After `RunLogWriter.start` succeeds, resolve and append one step-7 preflight before publication. `mode-rejected` and `final-rejected` append before a `preflight-rejected` result; receipt, snapshot, and closure rejection append before an `invalid` result; only accepted preflight reaches publication. Emit a terminal result only after its append completes. A telemetry failure or interruption during a preflight/result append returns a redacted process outcome, performs normal generic cleanup, and does not fabricate a compensating event. A telemetry failure before publication blocks publication. If publication succeeds but the terminal-result append does not, do not delete or replace the final, return no route facts, and let a later exact retry report `reused`. Once that terminal result append succeeds, it is the durable result: a later `RunLogWriter.run_end` interruption or cleanup failure returns its route, identity, and publication facts without a compensating event.

- **Preserve lifecycle cleanup and redaction.** Follow the interruption sequencing in `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt`: do not fabricate a compensating impact event after an append may already have succeeded, and always use the normal `RunLogWriter.run_end` cleanup path when the logger is available. Never pass receipt prose, artifact or brief content, paths, raw selector input, or unsafe relation identifiers to a result or telemetry emitter.

- **Provide read-only inspection for step 9.** Add a current-record inspection operation that accepts one stored analysis record supplied by its caller, strictly parses it, validates its entry name against its semantic final, recomputes current receipt, snapshot, closure, and canonical candidate, then requires the recomputed final and canonical candidate bytes to equal the supplied entry name and bytes before it reports `current`. A parser-valid record with a different recomputed candidate is `stale`; a malformed, noncanonical, or final-mismatched record is `invalid`; unavailable current inputs remain `unavailable`. It must not scan to choose a record, acquire a reader guard, publish evidence, or emit telemetry; step 9 owns caller coordination and rendering.

- **Keep sibling lifecycle code separate.** `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` is the closest lifecycle precedent, but its receipt-specific outcomes cannot become a shared helper in this feature step. Keep the two runners separate unless a later reconcile step establishes a common contract.

## Tests

### Tests for this step

- `tests/test_roadmap_impact_run.py:test_valid_current_receipt_captures_rechecks_and_publishes_one_analysis` — A valid exact receipt and unchanged current snapshot produce one canonical analysis final, a completed result carrying distinct route and publication facts, and the expected redacted lifecycle pair.

- `tests/test_roadmap_impact_run.py:test_requested_receipt_final_is_the_only_receipt_eligible_for_analysis` — Extra receipt records cannot affect selection, and a missing requested final produces no analysis.

- `tests/test_roadmap_impact_run.py:test_writer_guard_unavailable_returns_invalid_without_side_effects` — Guard acquisition failure returns the redacted status-`1` result before lifecycle telemetry or immutable evidence exists.

- `tests/test_roadmap_impact_run.py:test_runner_holds_writer_guard_across_capture_recheck_and_publication` — An interleaved roadmap writer cannot change the bound inputs between capture, recheck, and publication.

- `tests/test_roadmap_impact_run.py:test_invalid_receipt_snapshot_or_closure_never_publishes_partial_analysis` — Invalid upstream admission results create no analysis final and disclose no route facts.

- `tests/test_roadmap_impact_run.py:test_recheck_refuses_changed_raw_source_artifact_brief_or_current_gate_state` — Each bound input or gate change after capture, including semantically equivalent source-record whitespace, prevents publication rather than mixing revisions.

- `tests/test_roadmap_impact_run.py:test_scope_review_persists_a_durable_analysis_without_a_workflow` — A valid one-artifact cross-artifact concern records `requires-scope-review`, returns completed status `0` with `created` publication, and leaves the workflow null.

- `tests/test_roadmap_impact_run.py:test_exact_existing_analysis_is_reused_without_overwrite` — Exact canonical occupied bytes return `reused`, preserve the existing final, and leave no temporary evidence file.

- `tests/test_roadmap_impact_run.py:test_scope_review_reuse_preserves_route_and_reports_reused_publication` — An exact retry of scope-review evidence returns status `0`, `route_class=requires-scope-review`, `publication_outcome=reused`, and no workflow.

- `tests/test_roadmap_impact_run.py:test_storage_failure_outcomes_remain_distinct_and_never_publish` — Evidence-store invalid-input and write failures return distinct `storage-rejected` and `write-failed` no-route outcomes with status `1` and matching terminal events.

- `tests/test_roadmap_impact_run.py:test_nonmatching_existing_analysis_is_collision_and_remains_unchanged` — Malformed, substituted, or different occupied bytes return `collision` without replacement or route reuse.

- `tests/test_roadmap_impact_run.py:test_prepublication_telemetry_failure_blocks_evidence_publication` — Failure to start the log or append the admitted preflight prevents `publish_evidence`.

- `tests/test_roadmap_impact_run.py:test_postpublication_telemetry_failure_is_recoverable_by_exact_reuse` — A final that publishes before terminal logging fails remains immutable, and a later retry returns `reused`.

- `tests/test_roadmap_impact_run.py:test_impact_lifecycle_emits_only_append_confirmed_events` — Every preflight verdict is emitted before its matching terminal path after logger startup; a preflight/result append failure returns a redacted process outcome without a compensating impact event.

- `tests/test_roadmap_impact_run.py:test_run_end_failure_returns_the_already_logged_result` — An interruption or ordinary cleanup failure after the terminal event append preserves the already durable completed result and emits no second impact result.

- `tests/test_roadmap_impact_run.py:test_runner_never_calls_backend_or_mutates_canonical_feedback_or_seed_state` — The runner changes only permitted lock, evidence, and telemetry state.

- `tests/test_roadmap_impact_run.py:test_current_analysis_inspection_requires_exact_recomputed_candidate_bytes_and_final` — Parser-valid stale and substituted records, including a different canonical final or bytes, produce no route; only exact recomputed current candidate evidence is current and inspection performs no publication, telemetry, lock acquisition, or receipt selection.

- **Green-before-done gate:** `uv run pytest tests/test_roadmap_impact_run.py -q` passes.

## Acceptance criteria

- One requested valid receipt and one unchanged step 4 snapshot produce exactly one deterministic step 5 analysis candidate under `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`.

- A changed raw source record, unreadable, malformed, noncanonical, selected-closure-unsafe, or gate-invalid input during recheck returns an invalid no-record result with status `1` and publishes no analysis.

- An unavailable writer guard returns the same redacted status-`1` no-record result before telemetry, capture, or publication.

- The runner uses `EvidenceNamespace.IMPACT_ANALYSES` and `plan_tool/roadmap_evidence_store.py:publish_evidence`; it never overwrites an occupied final or leaves its own temporary file.

- Exact canonical occupied bytes return `reused`; every nonmatching occupied payload returns `collision` without route reuse or storage mutation.

- Durable `requires-scope-review` analysis returns a completed status-`0` result with separate route class and `created` or `reused` publication outcome, an analysis identity, and no workflow.

- After logger startup, every resolved preflight is appended before its matching terminal path; an append failure is return-only and never fabricates a compensating event. A telemetry failure before publication prevents publication. If the terminal-result append fails or is interrupted after publication, the return remains redacted and an exact retry can report `reused`; if it succeeds, a later `run_end` interruption or cleanup failure preserves that already durable terminal result without adding another event.

- Results and impact telemetry expose only step 7’s approved safe facts, while canonical artifacts, feedback state, seed state, receipts, Git state, and backend behavior remain unchanged.

- Runner and CLI status is exactly `0` for every durable current route, `1` for accepted no-route failures after admission, `2` for malformed/repeated/parseably incompatible requests, and `130` for interruption.

- Read-only inspection renders one caller-supplied analysis record only when strict parse, final-name binding, and exact bytes of the recomputed current candidate all agree; it otherwise returns no route and does not create evidence, telemetry, locks, or a selected receipt.

- `uv run pytest tests/test_roadmap_impact_run.py -q` passes.

## References

- [fcntl — The fcntl and ioctl system calls](https://docs.python.org/3.13/library/fcntl.html) — Read this for the advisory lock behavior behind the roadmap writer guard.

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Read this for the existing immutable publication operations that the evidence store owns.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Read this for the strict canonical analysis bytes supplied by step 5.

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read this for controlled interleaving, changed-input, telemetry-failure, and no-side-effect tests.

## Applicable guardrails

- **The plan’s “## Step intent,” fully bound evidence:** Publish only analysis evidence built from one guarded, rechecked input set; do not return partial records.

- **The plan’s “## Architecture,” immutable publication:** Preserve exact-final reuse and collision behavior through the storage and analysis contracts; do not add overwrite or repair behavior.

- **The plan’s “## Architecture,” telemetry lifecycle:** Treat run-log events as redacted observations, preserve their ordering and cleanup rules, and never use them to validate a record.

- **The plan’s “## Out of scope,” operational workflow changes:** Do not invoke broad generation, call a backend, choose or execute a patch, or change canonical, feedback, seed, or receipt state.

- **The plan’s “## Out of scope,” writer boundary:** Reuse `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` for this runner without replacing or widening its coordination contract.

- **The plan’s “## Out of scope,” views and command surfaces:** Keep argument parsing, result rendering, reader coordination, and log-free views out of this new module.

## Deferred

- CLI analysis creation, result rendering, reader coordination, and log-free views — Step 9 owns the operator surface around this runner.

- Same-artifact and cross-artifact changes — Named follow-on workflows own any later canonical mutation after separate admission.

- A shared lifecycle abstraction for `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and this runner — Establishing a common contract needs a separate reconcile decision because their evidence and terminal outcomes differ.
