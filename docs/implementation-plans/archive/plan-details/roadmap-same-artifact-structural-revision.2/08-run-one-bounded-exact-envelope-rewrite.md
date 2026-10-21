> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Run one bounded exact-envelope rewrite with preserved seed invalidation and snapshot-checked single-artifact replacement

## Summary

Create `plan_tool/roadmap_structural_revision_run.py` to carry one accepted exact-evidence request through one host-isolated backend call, candidate construction, proof, and step 6’s guarded publication boundary. Add `plan_tool/prompts/roadmap-structural-feedback-revision.md` for the closed V1 reply contract, plus focused runner and transport coverage. Keep the backend unable to edit or read the workspace before publication; a prompt-only instruction, `-C`, or a read-only tool policy is not enough. On green, the runner emits the step-7 lifecycle records, invalidates seeds only after accepted preflight, and replaces only the proved selected artifact through the final snapshot check.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the structural path needs its own guarded one-shot runner.
- [Input](#input) — Upstream proof, publication, lifecycle, and backend contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint and required additions.
- [Implementation](#implementation) — Bounded execution order, restricted backend boundary, and publication rules.
- [Tests](#tests) — Focused runner, transport, prompt, and redaction coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary sources for the reply and binding contracts.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this runner.
- [Deferred](#deferred) — Work left to the command and future semantic routing.

## Why

`plan_tool/roadmap_revision_run.py:run_local_feedback_revision` handles a different, local feedback contract and invokes the normal backend transport, which grants workspace-edit authority. Structural rewrites need one runner that preserves step 2’s exact evidence binding, accepts only step 3’s closed envelope, and prevents any backend-side canonical change before steps 4 through 6 have proved and published the candidate.

## Input

- **Exact-evidence context:** Step 2 produces the accepted `StructuralRevisionPreflight`-style context from `plan_tool/roadmap_structural_revision.py`, including the selected stage, selected row, selected feedback request, raw evidence digests, and complete snapshot binding.

- **Closed reply contract:** Step 3 owns `plan_tool/roadmap_structural_operations.py` and its strict V1 parser. Pass the raw backend reply to that parser unchanged; do not strip fences, skip preamble, or add tolerant parsing in this runner.

- **Candidate and proof:** Step 4 supplies the pure structural merger and step 5 supplies the proof result that distinguishes structural rejection from gate rejection.

- **Final publication:** Step 6’s structural publisher in `plan_tool/roadmap_revision_publish.py` owns the final exact-pair reload, full snapshot comparison, and atomic one-artifact replacement. The runner supplies its active writer token and successful proof.

- **Lifecycle contract:** Step 7 adds `RunLogWriter.roadmap_structural_revision_preflight` and `RunLogWriter.roadmap_structural_revision_attempt`. Use their closed fact matrices rather than adding runner-specific event payloads.

- **Backend seam:** `plan_tool/shell.py:claude_invoke`, `plan_tool/backend.py:CliBackend`, and `plan_tool/backend_runner.py:run_streaming_once` provide the existing batch invocation, transport selection, console, and run-log boundaries. `TESTING.md` records the project’s required fake-invoker pattern.

- **Configuration isolation:** `plan_tool/backend_config.py:load_backend_overrides` supplies global batch and streaming argv for ordinary commands. The structural runner does not consume that selection path; its tests prove those values cannot change the fixed evaluator.

- **Evaluator capability contract:** `docs/CODEX_CLI_CONTRACT.md` owns the
  captured structural evaluator version, exact no-user-config/no-rules argv,
  host-isolation profile, and sanitized probe record. The existing general
  Codex backend contract is not by itself authorization to run this new profile.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_structural_revision_run.py` — Add the one-shot structural runner, restricted production invoker, redacted result type, prompt renderer, and lifecycle sequencing.
  - `plan_tool/prompts/roadmap-structural-feedback-revision.md` — Add the installed prompt template for one strict structural-rewrite envelope.
  - `tests/test_roadmap_structural_revision_run.py` — Add isolated fixture-based runner, prompt, ordering, lifecycle, and refusal coverage.

- **Existing files (edits only):**
  - `TESTING.md` — Add the structural runner’s fake-invoker recipe and production-wrapper seam.
  - `docs/CODEX_CLI_CONTRACT.md` — Add the structural evaluator capability
    record: exact supported `codex --version`, isolated argv, sanitized JSON
    terminal-envelope probe, read-only deliberate-write refusal probe, and
    workspace-only-read denial probe.
  - `plan_tool/backend.py` — **Required footprint addition:** add the fixed Codex structural transport profile without changing existing default transports.
  - `plan_tool/shell.py` — **Required footprint addition:** let the structural invoker select the read-only transport, disable all recovery re-invocation, and suppress content-bearing failure diagnostics.
  - `plan_tool/backend_runner.py` — **Required footprint addition:** let the structural invocation suppress raw console and tool-summary output even under verbose or debug modes.
  - `tests/test_backend.py` — **Required footprint addition:** prove the fixed Codex profile uses its captured read-only argv and a caller-supplied isolated working root, while every other backend remains unavailable to the structural runner.
  - `tests/test_backend_config.py` — **Required footprint addition:** prove configured `extra_batch_argv` and `extra_streaming_argv` cannot change a structural command.
  - `tests/test_shell.py` — **Required footprint addition:** prove the structural invocation profile uses the restricted transport once and does not print or persist raw failure content.
  - `tests/test_backend_runner.py` — **Required footprint addition:** prove the structural profile suppresses raw stream and tool output without changing normal runner behavior.

## Implementation

- **Foundational logic:** Run one accepted structural rewrite through a no-tool backend call, then through merge, proof, and proof-bound publication under one writer lease.

- **Expose a dedicated runner.** Add a public entry point such as `run_structural_revision` and a frozen result type in `plan_tool/roadmap_structural_revision_run.py`. Accept only the slug, explicitly named receipt and analysis finals, resolved paths, optional injected invoker, optional logger, and stage table. Keep CLI parsing, duplicate-option handling, and operator-facing rendering in step 9.

- **Hold one writer lease across mutable work.** After mode validation, use `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` from exact-pair preflight through step 6’s final replacement. Reuse that token for `preinvalidate_roadmap_seeds` and structural publication; do not nest or reacquire a second writer guard.

- **Make mode and evaluator validation the first decision boundaries.** Before
  evidence loading or writer-guard acquisition, validate the command's explicit
  final-name shapes. Emit step 7's fact-free `mode-rejected` preflight record
  and stop with no attempt event on malformed or mixed command forms. Next run
  the local `codex --version` probe with no prompt or model request, prepare the
  verified host-isolation provider, and run its content-free workspace-read
  denial check against a known canonical path. Accept only when the version
  exactly equals the captured structural evaluator version and the provider
  both denies that read and can start an isolated no-op child. V1 implements
  only macOS `/usr/bin/sandbox-exec`: generate a direct Seatbelt profile that
  denies file data and metadata reads beneath the resolved repository and plans
  roots. Do not use `codex sandbox`, whose permission profile is config-derived.
  A missing, malformed, nonzero, or different version; non-macOS host; missing
  provider; profile-generation failure; or failed denial probe emits fact-free
  `evaluator-rejected` and stops before evidence, seed invalidation, or a model
  invocation. Do not log the observed version, executable path, configuration,
  protected path, profile, or probe error. Run step 2’s exact-pair preflight
  while guarded only after both boundaries pass; map its typed failures to the
  remaining step-7 preflight vocabulary.

- **Invalidate seeds only after accepted preflight.** Call `plan_tool/roadmap_revision_publish.py:preinvalidate_roadmap_seeds` before prompt rendering or backend contact. If invalidation fails, emit the required terminal attempt tuple and stop. Do not restore invalidated seed state after an envelope, merge, proof, final-snapshot, or publication failure.

- **Use and capture the fixed isolated Codex evaluator.** Add a clearly named
  profile through `plan_tool/backend.py:CliBackend` and
  `plan_tool/shell.py:claude_invoke` with the captured Codex argv `codex exec
  --json -C ISOLATED_EMPTY_DIR -s read-only --skip-git-repo-check --ephemeral
  --ignore-user-config --ignore-rules PROMPT`. On the verified macOS provider,
  invoke that exact command under the generated direct `sandbox-exec` profile;
  do not let the Codex process start outside the outer boundary. Create
  `ISOLATED_EMPTY_DIR` as a fresh empty non-repository directory outside the
  project workspace and remove it after the one call. The outer profile denies
  both data and metadata reads beneath the resolved canonical repository and
  plans roots, so a model tool cannot recover unselected content with an
  absolute path; `-C` merely supplies an empty working root. The capability
  record must be produced by a sanitized real probe using this exact nested
  profile: it captures the JSON terminal envelope, confirms a deliberate write
  request is refused, and confirms a workspace-only read is denied without
  retaining the protected content. It is refreshed, with the version pin and
  probe fixture, before any supported CLI-version change lands; updating argv,
  a version string, or an isolation profile without that probe is invalid.
  Active backend selection, fallback selection, and configured
  `extra_batch_argv` or `extra_streaming_argv` cannot select or modify this
  profile. Do not derive it through `build_effective_backend`, layer a
  conflicting flag over the normal `acceptEdits` or `workspace-write`
  transport, or rely on prompt wording to prevent writes or reads.

- **Keep the physical call singular.** The structural production invoker should use the restricted profile with rate-limit recovery disabled and `max_transient_retries=1`, which permits the first attempt but no retry. Bind `RunLogWriter.claude_call_start` and `RunLogWriter.bind_shell_sink` around that one call so ordinary process facts remain available without giving the runner a second backend path.

- **Suppress content-bearing diagnostics.** The restricted profile must prevent raw backend stdout, stderr, tool summaries, prompt text, and reply text from reaching the terminal, generic stream records, the structural result, or the structural lifecycle events. Retain only closed process and structural status facts. Preserve existing diagnostics and console behavior for all non-structural callers.

- **Render a self-contained prompt.** Load `plan_tool/prompts/roadmap-structural-feedback-revision.md` through `plan_tool/renderer.py:prompts_dir` and `string.Template`. Supply only the selected feedback request, selected target facts, selected scalar values, and body-region context needed to satisfy step 3’s contract; do not include the full snapshot, another artifact, or an instruction to inspect the repository or write files.

- **Keep the prompt contract tied to landed code.** Restate the V1 reply shape and selected-target limits inside the template because installed prompts cannot rely on repository documentation. Read field names and operation vocabulary from the landed step-3 contract when authoring the template, and add containment tests so future contract changes cannot leave stale prompt names or unresolved `${...}` placeholders.

- **Pass the raw reply through the owned boundaries.** Reject nonzero exits and blank replies without exposing their text. For a nonblank successful reply, call step 3’s parser unchanged, step 4’s merger against the accepted preflight context, and step 5’s proof. Map each typed rejection to the exact step-7 terminal tuple; do not retry, reinterpret, or broaden an envelope.

- **Publish only a proved candidate.** Pass the successful proof and the still-active writer token to step 6’s structural publisher. Treat a stale final snapshot as a refusal before replacement. Let that publisher derive the selected output path and write the exact candidate bytes; this runner must not call `plan_tool/roadmap_revision_publish.py:publish_revision_candidate`.

- **Close every accepted attempt once.** Emit one structural terminal attempt for every accepted preflight, including interruption. Use `RunLogWriter.run_end` once in a `finally` path with a redacted category and exit mapping. The result type must carry only facts step 9 needs to render a safe outcome.

## Tests

### Tests for this step

- `test_structural_runner_preflights_invalidates_merges_proves_and_publishes_once` — asserts the accepted path holds one writer token, calls the injected invoker once, and reaches only the selected structural publisher.

- `test_structural_runner_records_each_preflight_refusal_without_seed_or_backend_contact` — covers mode, evaluator, evidence, feedback, and render-canonical refusal rows with one preflight event and no attempt event.

- `test_structural_runner_records_interrupted_preflight_without_attempt` — asserts preflight interruption emits the step-7 interruption verdict and never begins invalidation or a backend call.

- `test_structural_runner_invalidates_seeds_before_prompt_and_preserves_the_result_after_failure` — proves invalidation precedes prompt rendering and remains unchanged after envelope, merge, proof, snapshot, or publication failure.

- `test_structural_runner_passes_raw_reply_to_the_closed_envelope_parser` — rejects fenced, prefixed, trailing, or otherwise off-contract replies through step 3 without runner-side cleanup.

- `test_structural_runner_maps_envelope_merge_proof_and_final_snapshot_failures_to_closed_terminal_tuples` — asserts each typed boundary produces only its permitted step-7 attempt facts.

- `test_structural_runner_reports_unknown_after_interrupt_only_after_replacement_can_start` — distinguishes interruption before publication from interruption after step 6 reaches its replacement boundary.

- `test_structural_prompt_contains_only_bound_selected_context_and_landed_v1_contract` — asserts the prompt contains the selected request and required structural vocabulary but not sibling-artifact or full-snapshot content.

- `test_structural_prompt_has_no_unresolved_template_placeholders_or_unescaped_dollar` — renders every supplied variable and rejects a template that leaves `${...}` or a bare literal dollar marker.

- `test_structural_runner_redacts_prompt_reply_and_backend_failure_from_console_result_and_log` — injects distinct sensitive values and asserts none appear in captured output, the runner result, generic events, or structural events.

- `test_structural_runner_does_not_use_local_revision_publication` — proves `plan_tool/roadmap_structural_revision_run.py` neither calls `run_local_feedback_revision` nor `publish_revision_candidate`.

- `test_structural_codex_runtime_or_isolation_contract_rejects_before_evidence` — verifies a missing, nonzero, malformed, or changed `codex --version`; unsupported host; unavailable provider; or failed workspace-read denial yields fact-free `evaluator-rejected` before evidence, seed invalidation, or a model invocation.

- `test_structural_codex_profile_uses_captured_host_isolated_capabilities` — verifies the exact captured Codex argv, including user-config and rules isolation, fresh non-repository root, and the direct macOS Seatbelt parent command. A macOS-gated subprocess fixture proves the generated profile denies both a data and metadata read of a workspace-only sentinel while an isolated no-op still starts. It also verifies the committed sanitized capability record includes terminal-envelope, deliberate-write-refusal, and workspace-read-denial probes for the pinned runtime.

- `test_structural_backend_selection_and_config_cannot_change_fixed_evaluator` — verifies active backend selection, fallback selection, configured batch or streaming argv, and config-derived `codex sandbox` profiles cannot change the fixed evaluator; malformed final identities and an unsupported runtime or isolation provider stop as fact-free preflights before seed invalidation or spawning.

- `test_structural_shell_profile_spawns_once_without_recovery_or_raw_failure_output` — asserts the production wrapper uses the restricted transport, makes no retry, and suppresses raw backend diagnostics.

- `test_structural_backend_runner_profile_suppresses_debug_stream_and_tool_summaries` — proves the restricted profile remains redacted even when normal console verbosity would print stream output.

Every test above must be green before this step is considered finished:

`uv run pytest tests/test_roadmap_structural_revision_run.py tests/test_backend.py tests/test_backend_config.py tests/test_shell.py tests/test_backend_runner.py -q`

## Acceptance criteria

- `plan_tool/roadmap_structural_revision_run.py` accepts only an explicit receipt-analysis pair and never infers evidence, a selector, a route, or a write target.

- An accepted preflight holds one `RoadmapWriterToken` through seed invalidation, the single backend request, candidate proof, final snapshot check, and single-artifact replacement.

- The structural production invoker makes one physical attempt through the
  captured, version-pinned read-only Codex profile in a fresh isolated
  non-workspace directory with user config and execpolicy rules disabled, and
  with no rate-limit or transient retry. The Codex process runs under the
  verified macOS Seatbelt parent that denies canonical repository and plans-root
  reads; no V1 fallback is permitted on another host. A sanitized real
  capability probe proves the pinned profile's JSON terminal envelope, denied
  deliberate write, and denied workspace-only read; an unknown or changed
  runtime or unavailable isolation emits fact-free `evaluator-rejected` before
  evidence, seed invalidation, or spawning. Active backend selection, fallback,
  and configured backend argv cannot change that evaluator; malformed final
  identities refuse at the same early boundary.

- A rejected or interrupted preflight emits one closed structural preflight event and no structural attempt event; every accepted preflight emits exactly one valid terminal attempt tuple.

- No prompt, reviewer request, artifact prose, backend reply, backend stderr, tool summary, or exception detail reaches console output, generic stream records, structural lifecycle records, or the runner result.

- The raw successful reply reaches only the step-3 parser, then step 4’s merger, step 5’s proof, and step 6’s structural publisher in that order.

- Final publication uses step 6’s proof-bound boundary and changes only the selected artifact. `rg 'run_local_feedback_revision|publish_revision_candidate' plan_tool/roadmap_structural_revision_run.py` returns no matches.

- `TESTING.md` documents the injected structural invoker and the restricted production-wrapper seam.

## References

- [Python `json` — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html#json.load) — Read the strict object-decoding behavior that step 3 owns and the runner must not weaken.

- [RFC 8259 — The JavaScript Object Notation Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html#section-4) — Use the unique-object-member requirement behind the closed reply contract.

- [Python `fcntl.flock`](https://docs.python.org/3.13/library/fcntl.html#fcntl.flock) — Read the advisory-lock behavior behind the continuous participating-writer lease.

- [Python `hashlib` — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html#hashlib.file_digest) — Use deterministic digest facts without persisting the evidence or prompt content.

## Applicable guardrails

- **The plan intent, one-artifact rewrite boundary:** Let step 6 own the only canonical write. This runner must not write another roadmap artifact or widen the selected target.

- **The plan’s step intent, bounded backend boundary:** Run one restricted backend attempt only after the selected reviewer request passes step 2’s exact-evidence preflight.

- **The plan’s `## Architecture`, no-workspace-read boundary:** Wrap the
  evaluator in the verified host boundary before it can start. Do not treat an
  empty working root, a prompt instruction, or Codex's read-only tool policy as
  a replacement for operating-system-enforced denial.

- **The plan’s `## Architecture`, exact-evidence and route boundary:** Treat both permitted static routes as evidence only. Do not use route metadata to infer another artifact, candidate scope, or semantic approval.

- **The plan’s `## Architecture`, closed-envelope boundary:** Pass the reply unchanged to the step-3 parser and refuse every shape it does not accept.

- **The plan’s `## Architecture`, continuous-guard boundary:** Keep the writer lease through final comparison and replacement, while making no claim to recover an external manual edit after that comparison.

- **The plan’s `## Out of scope`, revision and transaction boundary:** Do not reuse the local-revision command, add broad stage re-entry, create a generic editor, or add recovery journals to this runner.

## Deferred

- **CLI parsing, conflict handling, and terminal rendering** — Step 9 owns the exclusive command surface and turns this runner’s redacted result into an operator-facing exit code.

- **Candidate semantic-impact classification and a cross-artifact transaction** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — The plan’s `## Out of scope` keeps this outside the bounded runner; BACKLOG #289 remains the follow-up path.

- **Lifecycle consolidation with local, escalation, and impact runners** — Keep `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`, `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt`, and `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis` separate because their evidence and compatibility contracts differ.

- **Alternative host-isolation providers** — Linux, Windows, and any replacement
  macOS provider remain unavailable to V1. A later provider must demonstrate
  the same data-and-metadata workspace-read denial and receive a separate plan;
  it must never become an unverified fallback.
