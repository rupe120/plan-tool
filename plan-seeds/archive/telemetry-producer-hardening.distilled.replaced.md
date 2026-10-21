> **Replaced**: this file has been superseded by `docs/implementation-plans/2-telemetry-producer-hardening.md`.
> Preserved here for history; do not edit.

## Overview

Finish the producer-side residual under `BACKLOG.md` **#72 — Decision/outcome telemetry** by making backend failures, parallel completeness results, oversized fingerprint-heavy events, and create outcomes reliably observable and joinable. The work hardens existing producers around `plan_tool/telemetry.py`, `plan_tool/launcher.py:apply_finding`, and `plan_tool/cli/completeness_apply_parallel.py` without changing the phase-3 resolver's four public derived verdicts or introducing auto-tuning. Telemetry must remain stdlib-only, local, gitignored, best-effort, and unable to fail a host command.

## Problem statement

The shipped resolver is only as trustworthy as its producer inputs, but known paths still omit, misroute, duplicate, or silently drop decision events. `plan_tool/launcher.py:apply_finding` leaves backend invocation failures only in the run log; isolated workers in `plan_tool/cli/completeness_apply_parallel.py` can write into disposable worktrees or omit canonical repo/run keys; and `plan_tool/telemetry.py:record_decision` silently returns when serialized events exceed `_MAX_LINE_BYTES`. Create telemetry also repeats a full `code_fingerprint` path→hash map on every `create-step-outcome` instead of joining compactly to its assessment. These gaps make apply results and code-state correlations incomplete or ambiguous and leave the producer-hardening residual in `BACKLOG.md` #72 unfinished.

## Architecture

`plan_tool/telemetry.py` remains the stdlib-only, swallow-all-errors leaf for `DecisionEvent`, `_MAX_LINE_BYTES`, `record_decision`, create assessment and per-step outcome helpers, and `record_apply_verdict`. Add one distinct, documented `apply-verdict` token for an unusable backend response in `plan_tool/launcher.py:apply_finding`, preserving the existing return or exception path and emitting at most one joinable event per failed attempt. Extend inline mapping in `telemetry_analysis.py` only if this token needs an explicit `still-open` or `no-op` interpretation; do not add another derived verdict.

For `completeness-apply --jobs N`, make the replayed canonical result own durable telemetry. Each per-finding result is recorded once in the canonical repository's decision log with canonical `repo_root`, `plan_slug`, run id, plan fingerprint, step id, and anchor. Worker-local logs in disposable worktrees are non-authoritative; failed workers, replay conflicts or retries, skipped findings, and successful applies receive deterministic exactly-once rules while worker isolation and replay ordering remain unchanged.

Resolve `_MAX_LINE_BYTES` loss with one coherent persisted design after inspecting real payload consumers during plan authoring. Prefer a compact deterministic code-state digest where consumers need identity or equality, retaining a full map only where per-path diffs are required; otherwise scope full maps by producer and add a small best-effort dropped-event counter or diagnostic that does not recurse through the oversized-event path. Any digest requires canonical ordering and framing plus a focused collision-resistant hash. JSON must never be truncated into an invalid or ambiguous event.

Carry the heavyweight code fingerprint, or its compact replacement, once on the create assessment event. Each `create-step-outcome` carries only a compact join identity, preferably an explicit assessment or decision id returned or supplied through the create flow. If compatibility requires `plan_slug` plus timestamp, define and test collision and ordering behavior. Keep schema-v1/v2 historical decision rows readable, and change `telemetry_analysis.py` only as needed to preserve inline outcome resolution and aggregation.

Document and drift-guard every new event token, compact digest, dropped-event artifact, or changed create join contract in `DATA_CONTRACT.md` in the same change that introduces it. Reconcile relevant architecture and operator documentation, then update `BACKLOG.md`: remove the completed #72 producer-hardening residual, correct stale Priority/Readiness text that calls the shipped resolver the next concrete pick, and retain only a precisely named residual that is genuinely deferred.

## Out of scope

- Changes to the four public derived verdicts `acted-on`, `no-op`, `reverted`, and `still-open`; this hardening changes producer reliability, not resolver vocabulary.
- Auto-tuning thresholds or mutating plans/configuration from telemetry; the plan is observational only.
- A new analytics command, dashboard, cache, or second decision log; existing telemetry surfaces and storage remain authoritative.
- General run-log redesign or telemetry rotation/time-windowing beyond what is strictly needed to expose oversized decision-event loss.
- Backfilling historical local telemetry files.
- Broad parallel-apply refactoring unrelated to canonical telemetry ownership; worker isolation and deterministic replay ordering remain intact.

## Risks

- **Backend failure masking or duplication — high severity.** Recording the new `apply-verdict` could replace the original failure or emit more than once. Preserve the host return/exception path exactly, keep recording best-effort, and assert at-most-once emission.
- **Non-canonical or duplicated parallel telemetry — high severity.** Disposable workers may retain authoritative-looking rows, or retries and replay conflicts may double-record results. Make canonical replay the durable owner and define deterministic rules for failed, retried, skipped, and successful paths.
- **Silent oversized-event loss — high severity.** Large `code_fingerprint` path→hash maps can exceed `_MAX_LINE_BYTES` on drift-gate, code-reveals-split, and create recorder sites. Use a deterministic compact representation where possible or a non-recursive dropped-event diagnostic; never truncate JSON.
- **Digest ambiguity or collision — high severity.** An unstable or weak digest could join unrelated code states. Specify canonical ordering/framing and a focused collision-resistant hash, then test stability for identical maps and inequality for changed maps.
- **Fragile create joins — high severity.** Replacing repeated fingerprints with timestamp-only correlation can collide or reorder. Prefer an explicit assessment/decision id; if `plan_slug` plus timestamp is required, define collision and ordering behavior.
- **Historical-row incompatibility — medium severity.** Persisted-shape changes could make schema-v1/v2 decision rows unreadable or break inline resolution and aggregation. Preserve legacy/ownerless row tolerance and update `telemetry_analysis.py`, `DATA_CONTRACT.md`, and its drift guard only where required.
- **Telemetry perturbing host commands — high severity.** Fingerprint computation or recorder failures could escape best-effort wrappers. Directly test raising computations and recorders at every named public producer seam.

## Testing

Set `enforce_step_tests: true`; each production change owns its focused real-path tests in the same commit. Preserve established helpers rather than creating a parallel fake telemetry layer.

Unit-focused coverage belongs in `tests/test_telemetry.py`, `tests/test_launcher.py`, and `tests/test_review.py`. Verify the compact digest or dropped-event primitive and persisted shape; identical maps produce a stable digest and changed maps differ; oversized JSON is never truncated; the dropped-event signal cannot recurse through the same oversized path; schema-v1/v2 and ownerless/legacy rows remain readable; create assessment/outcome joining is compact and unambiguous; and backend invocation failure records exactly one documented `apply-verdict` without changing the host failure behavior. Parameterize the apply-loop forwarding and Part-A/escalate wrapper cases so kwargs and canonical keys are forwarded unchanged, raising fingerprint computations or recorders do not perturb the host command, and successful, failed, retried, or skipped paths do not double-record.

Cross-module wiring coverage belongs in `tests/cli/test_completeness_apply_parallel.py` and `tests/cli/test_completeness_cmd.py`. Exercise both the lower-level worker/replay seam and the command-level `completeness-apply --jobs N` path, proving canonical `repo_root`, `plan_slug`, run id, plan fingerprint, step id, and anchor ownership for durable results while disposable worktrees do not create authoritative duplicates. Cover failed workers, replay conflicts or retries, skipped findings, and successful applies without changing isolation, deterministic replay order, or command success behavior.

Update and run the `DATA_CONTRACT.md` drift guard for every persisted event token, digest, diagnostic, or create join change. Run the focused suites above and the full test suite. After execution, run plan-canonical `reconcile-code` to convergence, then complete code review, fixes, and re-review until clean. The workflow also requires one conceptual completeness audit only after all `detail --no-iterate` files exist; manually review its saved findings and edit plan/detail files directly rather than blanket auto-applying them.

## Acceptance criteria

- When `plan_tool/launcher.py:apply_finding` cannot obtain a usable backend response, it emits exactly one documented, joinable `apply-verdict` distinct from `APPLIED`, `NOT-APPLICABLE`, `BLOCKED`, and `BLOCKED-STRUCTURAL`, while preserving the original host failure behavior.
- The backend-failure event carries the same plan slug, step/finding anchor, plan fingerprint, and run binding available to ordinary apply verdicts, and a recorder exception never masks the backend failure.
- `completeness-apply --jobs N` records every durable per-finding result exactly once in the canonical repository's decision log with canonical `repo_root`, `plan_slug`, run id, plan fingerprint, step id, and anchor.
- Failed workers, replay conflicts or retries, skipped findings, and successful applies follow deterministic exactly-once rules; disposable worker worktrees do not retain authoritative duplicates, and telemetry never causes the command to fail.
- Fingerprint-heavy events from drift-gate, code-reveals-split, and create recorder sites no longer disappear silently at `_MAX_LINE_BYTES`; the selected compactness or dropped-event mechanism is deterministic, valid JSON, tested, non-recursive, and documented.
- If a digest is used, identical maps yield the same value regardless of input ordering, and any changed map yields a different tested value under the documented canonical framing and collision-resistant hash.
- The create assessment event owns the full `code_fingerprint` or chosen compact replacement once; each `create-step-outcome` contains only the compact identity needed to join unambiguously to that assessment.
- Schema-v1/v2 historical decision rows and ownerless/legacy rows remain readable, and inline outcome resolution and aggregation continue to work through `telemetry_analysis.py` where applicable.
- Direct parameterized tests at the public seams cover every named apply-loop telemetry threading site and Part-A/escalate best-effort wrapper, including unchanged kwargs/canonical-key forwarding, raising fingerprint/recorder behavior, and non-duplication across successful, failed, retried, and skipped paths.
- Telemetry writes remain local, gitignored, stdlib-only, read-only from the analysis command, and best-effort at every producer.
- `DATA_CONTRACT.md`, its drift guard, and relevant architecture/operator documentation match every final persisted shape.
- `BACKLOG.md` #72 no longer lists shipped producer hardening, and its Priority/Readiness text no longer calls the shipped #72 resolver the next concrete pick.
- The focused suites in `tests/test_telemetry.py`, `tests/test_launcher.py`, `tests/test_review.py`, `tests/cli/test_completeness_apply_parallel.py`, and `tests/cli/test_completeness_cmd.py`, plus the full test suite, pass.

## Deferred

No producer-hardening requirement is deferred at seed time. If code grounding or the final completeness audit proves that one of the five named #72 residuals requires a separate architectural effort, name that residual precisely in `BACKLOG.md` and state why it cannot safely ship in this plan; do not use a generic future-work placeholder.
