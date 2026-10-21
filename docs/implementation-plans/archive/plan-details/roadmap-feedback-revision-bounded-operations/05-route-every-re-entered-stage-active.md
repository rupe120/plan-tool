# Step 5 — Route re-entered stages through bounded feedback or no-op re-gating

## Summary

Route each selected existing roadmap artifact through trusted baseline admission before deciding whether it needs a bounded feedback revision or a feedback-free re-gate. Update `plan_tool/roadmap.py` to use the stage context and merger from steps 2 and 3, while `plan_tool/roadmap_revision_run.py` applies the same admission rule before its existing selector-bound flow. Replace whole-artifact stage revision prompting with a bounded JSON-operation prompt, and add explicit no-change and invalid outcomes to the CLI mapping. Green means active feedback is the only re-entry path that calls the backend or publishes a change; feedback-free stages re-gate in memory without writes.

## Table of Contents

- [Summary](#summary) — The step’s routing and observable outcome.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The whole-artifact re-entry behavior this step removes.
- [Input](#input) — The upstream contracts that determine safe routing.
- [Files (creates vs edits)](#files-creates-vs-edits) — Prompt, runner, CLI, fixture, and test changes.
- [Implementation](#implementation) — Admission, routing, no-op, prompt, and outcome rules.
- [Tests](#tests) — Focused route and result-contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary JSON and hermetic-test references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits on the new route.
- [Deferred](#deferred) — Follow-up work outside this step.

## Why

`plan_tool/roadmap.py:_render_revision_prompt` sends a re-entered stage’s full predecessor and nested authoring prompt back to the model, while `plan_tool/roadmap.py:_run_roadmap` rewrites every selected existing stage even when it has no active request. That makes untouched content part of the model contract and lets harmless presentation drift, unauthorized semantic edits, and feedback-free re-entry take the wrong path. This step makes the baseline comparison the common admission point, then makes active `open` feedback the sole reason to invoke the bounded stage revision route.

## Input

- **Step 2 bounded context:** Consume the landed stage-context builder and closed stage-envelope parser. Use its active-feedback order and authority facts; do not recreate its relation, prose-span, or ordering selection in `plan_tool/roadmap.py`.

- **Step 3 candidate merge:** Consume the landed stage merger. It remains the only route that turns stage-envelope operations into a candidate artifact before the existing gates run.

- **Step 4 source identity and publication:** Use the trusted-baseline comparison and recoverable publisher delivered by step 4. The comparison must supply a canonical in-memory working artifact for presentation-only drift and a precise semantic-drift diagnostic otherwise.

- **Existing stage flow:** Keep `plan_tool/roadmap.py:_load_and_regate_below`, `_load_predecessors`, `_build_envelope`, `_run_stage`, `_write_artifact`, and `RoadmapResult` as the orientation points for stage ordering, gates, writes, and result reporting.

- **Existing local route:** Keep `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`, `preflight_feedback_revision`, and `_run_accepted_revision` selector-bound. This step changes its source admission, not its one-feedback authority or existing local-prompt contract.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/roadmap-stage-feedback-revision.md` — Define the bounded stage-feedback request and closed JSON response contract.
  - `tests/fixtures/roadmap/integration-scale-domain.md` — Provide a canonical tens-of-KB Domain artifact with active and untargeted review rows.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Admit re-entered source, select bounded-feedback versus no-op handling, re-gate no-op stages, and widen the closed run outcomes.
  - `plan_tool/roadmap_revision_publish.py` — Gate local candidates against the caller-provided admitted upstream map and recheck source admission before final publication rather than rereading untrusted upstream text.
  - `plan_tool/roadmap_revision_run.py` — Run shared baseline admission before local selector authorization and preserve the existing local route after admission.
  - `plan_tool/cli/roadmap_cmd.py` — Map completed-no-change and invalid results to the correct exit code and distinct operator output.
  - `plan_tool/prompts/roadmap-revision.md` — Remove whole-artifact and nested-authoring instructions from the stage revision contract while retaining only portable shared revision guidance.
  - `tests/test_roadmap.py` — Cover stage routing, bounded prompts, no-op re-gating, result outcomes, and the integration-scale replay.
  - `tests/test_roadmap_revision_publish.py` — Cover local publication against admitted upstream artifacts and the pre-write source recheck.
  - `tests/test_roadmap_revision_run.py` — Cover local-route source admission and refusal ordering.
  - `tests/cli/test_roadmap_cmd.py` — Cover the widened outcome-to-exit-code and summary mapping.
  - `TESTING.md` — Update the roadmap test seam guidance for bounded JSON replies and fail-on-call no-op cases.

## Implementation

- **Make source admission the first re-entry decision.** In `plan_tool/roadmap.py:_run_roadmap`, compare each selected predecessor’s non-feedback projection with its trusted baseline before `_check_predecessor_review_rows`, stage-context construction, or gate re-checking. Before `plan_tool/roadmap.py:_load_and_regate_below` runs any lower-stage gate for `--from-stage N`, apply that same admission to every lower existing artifact and use its canonical in-memory value as upstream input. Retain the resulting binding beside each file-backed loaded artifact, recheck it immediately before every gate or route use — including a correction/retry prompt and a selected feedback-free re-gate — and immediately before that stage publishes, and refuse `OUTCOME_STAGE_INVALID` without a write when it changed. Use the step 4 comparison API as the single source of this rule; do not duplicate projection or digest logic in either runner.

- **Snapshot project limits before re-entry work.** Resolve `StageFeedbackLimits` once from the project root before source admission, prompt construction, or backend invocation. A valid project block can only tighten the three numeric caps; pass that one immutable value to every selected stage's context builder, response parser, and prompt renderer. A config error is a command-preflight error with the named config problem — it has no invented stage outcome and reaches no admission, invoker, correction, merge, or publisher path. Never reload config between stages or consult a user-level file during a run.

- **Use canonical working text only in memory.** When the projection matches, render the parsed artifact canonically and use that text plus its immutable admission binding in the `_LoadedArtifact` passed to context construction and later upstream stages. A comment, formatting change, or schema-unrecognized value must not trigger an artifact write merely to normalize bytes.

- **Refuse semantic drift before all other re-entry work.** A changed non-feedback row, removal, ordering value, or body prose must stop the normal route as `OUTCOME_STAGE_INVALID`, with the affected stage and available comparison detail. It must not call the invoker, retry, write, publish, invalidate seeds, or append the rejected artifact to `loaded`. This ordering also ensures a deleted or renamed feedback target reports source drift instead of becoming a model retry.

- **Freeze reviewer feedback for one attempt.** After normal route source admission and selected-stage preflight, capture the step 4 ordered feedback snapshot. Before every correction/retry prompt and before every bounded stage candidate publishes, reread and compare that selected artifact feedback projection under the writer guard. An observed added, changed, reopened, reordered, or removed row returns `OUTCOME_STAGE_INVALID` with a concurrent-feedback message; it does not write a stale candidate, retry, ask the backend for a correction, update a baseline, or invalidate seeds. Do not put feedback into the durable semantic baseline.

- **Keep stage feedback target admission aligned with stage authority.** Retain the duplicate-feedback-id check before context construction, but do not reject a stage feedback target through the local `design_row_ids` view. Let the step 2 stage context validate active targets so fixed `hosting` edits and identity-only `stores` edits or removals reach their admitted stage operations. Leave the selector-bound local route on its existing narrower target contract.

- **Select routes by active feedback, not stage identity.** Keep the `STAGES` loop table-driven. For a baseline-admitted predecessor with one or more rows selected by `plan_tool/roadmap.py:_open_feedback`, build the step 2 context, render the bounded stage prompt, parse the step 1 envelope, merge it through step 3, and run the existing stage gates against the candidate. Do not branch on a stage name or number; a route distinction belongs in generic per-stage data or outcome handling.

- **Retire whole-artifact stage revision prompting.** Bypass the predecessor-plus-authoring wrapper in `plan_tool/roadmap.py:_render_revision_prompt` for the bounded stage route. `plan_tool/prompts/roadmap-stage-feedback-revision.md` must require one unfenced closed JSON object and receive only the context facts the step 2 builder issued. Neither it nor the revised `plan_tool/prompts/roadmap-revision.md` may embed a predecessor artifact, a nested authoring prompt, or unrelated row or body text. Keep the local route on its existing selector-bound prompt.

- **Render the response contract from its typed source.** The stage prompt obtains its operation schema and the effective project-snapshotted item, response-byte, and prose-byte limits from step 1's typed stage-envelope contract; the one-material-operation-per-feedback rule remains fixed. It instructs the model to split work that would exceed a limit; it does not maintain a second hand-written schema or limit table.

- **Preserve the existing retry and gate boundary for active feedback.** A stage-envelope parse, merge, or gate rejection uses the existing content-attempt budget and correction channel, except a declared response-budget violation. More active items, reply bytes, or amendment bytes than the resolved numeric limit, or more than one material operation for one feedback id, is `invalid` immediately: report the actual and allowed value plus the split action, and make no correction request, retry, partial merge, or write. The successful merged candidate is the only re-entered path in this step that publishes an artifact and its required seed invalidation through the step 4 publisher.

- **Treat feedback-free stages as re-gates, not regeneration.** For an admitted predecessor without active feedback, build the gate envelope from the canonical artifact and the current in-memory upstream set. A passing re-gate ends the phase as `completed-no-change` with zero backend attempts, no artifact reload, no publisher call, no baseline replacement, and no seed-state change. Append that canonical in-memory artifact to `loaded` so a later selected stage receives the same upstream text it would receive after a write-and-read cycle.

- **Stop on a no-op re-gate failure.** If that re-gate reports violations, return `OUTCOME_STAGE_INVALID` immediately and preserve any earlier accepted bounded merge. Do not retry or run the failed stage’s backend call, and do not enter a broad feedback-free generation path.

- **Widen result and CLI handling together.** Extend `plan_tool/roadmap.py:OUTCOMES` to the four planned values: completed, completed-no-change, stage-exhausted, and stage-invalid. Ensure `RoadmapResult`, the lifecycle completion in `_run_roadmap`, and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` treat both completed outcomes as success, while invalid output names its failure without presenting retry-exhaustion advice.

- **Apply admission to every local gate input.** In `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`, under `roadmap_writer_guard`, admit and canonicalize the selected source and every earlier upstream artifact before `preflight_feedback_revision` examines the selected row or the backend runs. Build one fixed canonical upstream map with its source-identity facts, pass that map to `publish_revision_candidate`, and make the publisher gate only that map rather than rereading paths. Capture the selected artifact's feedback snapshot immediately after preflight. Before a correction/retry prompt and immediately before the atomic write, recheck each admitted source identity and that feedback snapshot so an external semantic or reviewer-feedback edit observed during the backend loop refuses before publication. Preserve the existing selector-bound prompt, one-request limit, and merge authority. A local selected or upstream semantic-source-drift or concurrent-feedback refusal must not invoke, publish, or invalidate seeds; keep the existing run-log schema unchanged if its preflight verdict cannot represent the more specific result outcome.

- **Report actual writes, not re-entry assumptions.** Keep `RoadmapResult.overwritten_stages` as the actual artifact-write set. Replace `_overwrite_summary_lines`'s copy-aside and “every stage from N up rewrites” advice with a compact list of artifacts actually published, plus feedback-first guidance for a further construct or prose change and the fact that feedback-free re-entry only re-gates. Do not encourage direct semantic hand edits or a preservation pointer for changes source admission will reject.

- **Use the fixture as a leak detector.** Make `tests/fixtures/roadmap/integration-scale-domain.md` parseable and canonical, with long unrelated content plus an untargeted `awaiting-review` response. Tests should prove those bytes never enter the bounded prompt and remain unchanged after a permitted stage merge.

## Tests

### Tests for this step

- `test_reentered_open_feedback_uses_bounded_stage_context_and_json_operations` — Verifies an admitted stage with open feedback calls the backend with bounded context, merges the parsed operations, and gates the candidate.

- `test_stage_feedback_prompt_excludes_predecessor_authoring_and_unselected_content` — Verifies both stage prompt templates omit whole-artifact and nested-authoring payloads, supply every placeholder, and leave no unresolved placeholder.

- `test_stage_feedback_prompt_renders_the_typed_schema_and_effective_response_limits` — Verifies the prompt renders the stage contract's current schema, effective numeric limits, and fixed material-operation rule rather than duplicating literals.

- `test_stage_feedback_limit_violation_returns_invalid_without_correction_retry_or_write` — Verifies each response-budget rejection returns an actionable invalid result and leaves the invoker correction path, merge, and publisher unreachable.

- `test_stage_feedback_limits_snapshot_project_config_once_and_render_effective_values` — Verifies a valid stricter project block reaches context, prompt, and validation as one value, while a changed file cannot affect a later selected stage in the same run.

- `test_invalid_project_stage_feedback_limit_config_fails_preflight_before_admission_or_invocation` — Verifies config failure is precise and leaves source admission, backend, correction, merge, and publication unreachable.

- `test_integration_scale_stage_revision_changes_only_authorized_content` — Replays an authorized revision over `tests/fixtures/roadmap/integration-scale-domain.md` and preserves the untargeted awaiting-review response exactly.

- `test_source_admission_precedes_stage_feedback_authorization` — Verifies semantic baseline drift stops before stage-context construction or envelope authorization.

- `test_semantic_reentry_drift_returns_invalid_without_call_write_loaded_or_seed_change` — Verifies a direct non-feedback change produces `OUTCOME_STAGE_INVALID` with no backend request, publication, seed action, or loaded-artifact update.

- `test_normal_route_rechecks_admitted_sources_before_every_gate_use_and_publication` — Verifies a semantic edit after normal admission is caught before a later stage consumes that upstream artifact, a terminal feedback-free re-gate, or a selected stage publishes, without overwriting or omitting the edit.

- `test_presentation_only_reentry_drift_uses_canonical_memory_text_without_rewrite` — Verifies comments or ignored fields become canonical upstream text without rewriting the on-disk artifact.

- `test_upstream_source_admission_precedes_from_stage_regating` — Verifies a direct semantic edit below `--from-stage` returns invalid before its artifact enters the upstream gate envelope, while presentation-only drift supplies canonical in-memory text.

- `test_stage_context_admits_hosting_and_store_feedback_without_widening_local_revision` — Verifies stage feedback may reach the admitted hosting and store operations while the selector-bound local route retains its current target boundary.

- `test_feedback_free_reentry_regates_without_invoker_or_mutation` — Verifies a passing feedback-free stage has zero attempts and changes no artifact, baseline, or seed state.

- `test_feedback_free_regate_uses_an_earlier_bounded_merge_as_upstream` — Verifies a later feedback-free stage sees the current upstream candidate and stops invalid before its own call or write when an upstream add or removal breaks its gates.

- `test_all_feedback_free_selected_stages_return_completed_no_change` — Verifies no-write re-entry maps to the distinct successful terminal outcome.

- `test_mixed_feedback_free_and_bounded_stages_return_completed` — Verifies any accepted bounded merge keeps the overall result in the ordinary completed outcome.

- `test_feedback_free_gate_failure_returns_stage_invalid_without_retry` — Verifies gate messages, failed stage, non-success result, zero backend attempts, and preserved earlier writes.

- `test_local_source_admission_precedes_selector_preflight` — Verifies `run_local_feedback_revision` refuses semantic drift before selected-feedback validation.

- `test_local_presentation_only_source_drift_uses_canonical_working_artifact` — Verifies local revision accepts baseline-equal presentation drift without treating it as a render-canonical refusal.

- `test_local_semantic_source_drift_does_not_invoke_publish_or_invalidate` — Verifies local drift refusal leaves all mutation paths unreachable.

- `test_local_upstream_semantic_drift_refuses_before_selector_or_invocation` — Verifies a direct semantic edit to any earlier local publication-gate input fails before selector preflight, backend work, or publication.

- `test_local_publication_uses_admitted_upstreams_and_rechecks_before_write` — Verifies harmless upstream presentation drift is gated from its canonical admitted value, the publisher never rereads a raw upstream path, and a semantic edit after admission but before publication refuses without a write.

- `test_bounded_publication_refuses_changed_feedback_snapshot_before_retry_or_write` — Verifies normal and local bounded candidates refuse observed added, changed, reopened, reordered, and removed reviewer feedback after preflight, including between failed attempts before a correction prompt, with no write, correction, baseline update, or seed invalidation.

- `test_completed_no_change_outcome_returns_zero_without_write_summary` — Verifies the CLI distinguishes successful no-change completion from an artifact-writing completion.

- `test_mixed_reentry_summary_reports_only_actual_writes_and_feedback_first_guidance` — Verifies no-op re-gates are absent from the write summary and the output does not claim every re-entered stage rewrites or recommend preserving direct semantic hand edits.

- `test_stage_invalid_outcome_returns_nonzero_and_renders_specific_reason` — Verifies the CLI reports invalid source or re-gate detail without exhausted-stage retry advice.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Every existing artifact read for `--from-stage` compares its non-feedback projection to its trusted baseline before it becomes upstream gate input. A selected existing stage applies the same comparison before feedback selection or re-gating. The local route does the same for its selected artifact and every earlier publication-gate input before selector authorization or backend work.

- Presentation-only source drift supplies canonical in-memory text without a formatting write; semantic non-feedback drift stops before a backend call, write, retry, seed invalidation, or `loaded` update, including a source change after initial normal-route admission but before every gate or route use or publication.

- An admitted selected stage with active feedback sends only bounded stage context to the backend, accepts only the step 1 JSON envelope, and publishes only the step 3 merged candidate after its selected feedback snapshot still matches before a retry/correction prompt and publication.

- The active-feedback prompt renders the same typed response schema and effective limits that validation enforces. An over-limit active set, reply, amendment, or per-feedback material operation count returns actionable `invalid` without a correction request, retry, merge, or write.

- The command resolves valid project-only stricter numeric limits once and uses that snapshot consistently for every stage prompt and response check. An invalid block fails command preflight before artifact admission or backend work; no user-level configuration participates.

- Stage target admission accepts the authority matrix’s fixed hosting edits and identity-only store edits or removals without widening selector-bound local revision.

- An admitted selected stage with no active feedback re-gates without a backend request, artifact write or reload, baseline replacement, seed-state change, or downstream rewrite caused solely by that no-op.

- A failed feedback-free re-gate returns `OUTCOME_STAGE_INVALID`, reports its gate violations, preserves earlier accepted work, and never retries the skipped stage.

- `OUTCOMES` contains the four planned terminal values; completed and completed-no-change return success, while exhausted and invalid return failure.

- `run_local_feedback_revision` retains its selected-feedback-only authority, refuses selected or upstream semantic source drift before invocation or publication, gates only its fixed admitted canonical upstream map, and rechecks that map plus its selected feedback snapshot before writing.

- The integration-scale fixture proves a permitted change does not expose or alter unrelated content or an untargeted awaiting-review response.

- CLI summaries list only actual artifact writes, distinguish feedback-free re-gates, and direct a further construct or prose change through feedback rather than hand-edit preservation guidance.

- `uv run pytest tests/test_roadmap.py tests/test_roadmap_revision_run.py tests/cli/test_roadmap_cmd.py -q` and `uv run pytest tests/ -q -n auto` pass.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) — Use the closed, single-object response rule for the stage feedback prompt.

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Review strict decoding behavior used by the stage-envelope parser from step 1.

- [pytest: How to Monkeypatch/Mock Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Stub invokers and publishers to prove no-op and source-drift paths make no calls.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded model input:** Keep stage feedback input and output limited to typed, authorized operations; this step must not restore whole-artifact regeneration.

- **The plan’s “## Out of scope”, body-edit and patch boundary:** Consume only the row-scoped operation and merge surface from steps 1–3; do not add a general body editor or patch language.

- **The plan’s “## Out of scope”, gate and retry boundary:** Preserve existing gate predicates and the active-feedback retry budget. Route selection must not become a reason to change either contract.

- **The plan’s “## Out of scope”, local and structural authority:** Limit local-runner work to shared source admission. Do not widen selector authority or alter structural revision behavior.

- **The plan’s “## Out of scope”, relation authority:** Do not add a re-entry path that retargets existing ordering or other declared relations.

- **The plan’s “## Out of scope”, broad recovery boundary:** Do not infer a feedback-free regeneration or recovery command from `--from-stage`.

- **The plan’s “## Out of scope”, baseline-reader boundary:** Keep receipt, impact, escalation, and structural-evidence readers outside this routing change.

## Deferred

- **Receipt, impact, escalation, and structural-evidence source admission** — The plan’s “## Out of scope” reserves those readers for the follow-up source-identity work.

- **A deliberate feedback-free regeneration command** — A future operator surface needs separate design and explicit input rather than reuse of `--from-stage`.

- **Feedback retention and raw-YAML repair behavior** — Keep the existing reviewer-owned lifecycle and artifact parsing boundaries until their separately scoped work lands.
