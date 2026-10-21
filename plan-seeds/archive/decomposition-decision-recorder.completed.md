> **Completed 2026-08-19** — BACKLOG #255 ships directly as `plan-tool decide`.
> This consumed seed is preserved as implementation provenance; do not re-author
> it. The active backlog entry owns any future change to the recorder.

# Plan seed: explicit decomposition-decision recorder

Use this as the source for BACKLOG #255 when its small, direct implementation
is selected. It records an explicit operator decision; it does not decide
whether a plan is well decomposed.

## Outcome

An explicit invocation either records one durable decomposition-decision
telemetry event or reports that persistence failed. It accepts `plan` or
`step:<id>` as its public anchor grammar, records a documented closed-vocabulary
outcome and a non-empty rationale, and leaves existing granularity telemetry
unchanged.

## Evidence and boundary

The withdrawn audit-trajectory-instrumentation effort produced seventeen
step-altitude assessments but no record of the later explicit decision to
withdraw the plan after its premise was disproved. That absence justifies
recording the human decision. It does not justify inferring one from the
seventeen assessments or adding another recurring altitude check.

## Surface

Add a small `plan-tool decide <plan>` command. It accepts:

- an outcome from the documented vocabulary: `single`, `split`, `scope-out`,
  `reframe`, `withdraw`, or `defer`;
- an anchor written as `plan` or `step:<id>` for an existing step; and
- a non-empty rationale.

The command validates those inputs before calling a
`record_decomposition_decision` wrapper. The wrapper writes a dedicated
`decomposition-decision` telemetry kind through the existing append-only
best-effort primitive. The command checks the wrapper result: an append failure
is a reported command failure, never a success that claims a durable record.
The data-contract entry distinguishes an explicitly recorded operator/session
decision from a heuristic decision the tool made.

## In scope

- CLI parsing and validation for the one record action.
- The telemetry wrapper, schema/data-contract documentation, and drift guard.
- Focused tests for valid writes and every invalid input boundary.

## Out of scope

- Interactive-chat commands, backend hand-off, briefings, roadmap chat modes,
  or transcript storage.
- A telemetry analysis, calibration reader, backfill, or history replay.
- Inferring a decision from audit findings, plan diffs, metric counts, or
  conversation text.
- Re-asking the plan-altitude question automatically.
- Gates, changes to unrelated command exit codes, refusals, or automatic split,
  scope-out, re-seed, or plan mutation actions. The `decide` command's own
  failed persistence result is its stated outcome, not a new gate.

## Verification

- An explicit command records exactly one withdraw event against a plan anchor.
- Each allowed outcome writes the documented event shape; unknown outcomes fail.
- A missing rationale and an invalid `plan` or `step:<id>` anchor fail before
  telemetry writes.
- A simulated append failure reports persistence failure and records no success
  result.
- Text that resembles a decomposition conclusion records nothing without the
  explicit command.
- Existing granularity-assessment telemetry stays byte-for-byte compatible.

## Deferred

A broader interactive-chat hand-off is preserved in
`plan-seeds/archive/interactive-chat-surface.deferred.md`. It requires a
separate demonstrated operator workflow before it becomes a backlog candidate.
