# Token-ledger logging recovery

## Scope and site decisions

The invariant is that calls with an existing run logger retain their exact prompt
identity and completed model-call telemetry, without changing model behavior.
This recovery lives in `plan-tool-2`; the source analysis remains in
`plan-tool-1/experiments/token-ledger/REPORT.md`. No other clone is edited.

Identifier search: `claude_call_start`, `prompt_bytes`, `apply_finding`,
`assess_direct_source_split_from_claude`, `install_call_end_sink` and
`bind_shell_sink`. Vocabulary search: `invoker`, `run_logger`, `start_step`,
`begin_seed_attempt`, `call_end` across the source and mirrored tests.

| Sites | Decision |
| --- | --- |
| launcher `apply_finding`, primary and follow-up | Emit streaming completion inside the existing sink; retain restoration and verdict behavior. |
| create `assess_direct_source_split_from_claude` | Bind/unbind the existing writer around the actual invocation; cached assessment emits no call. |
| create `_propose_risk_profile_from_seed` | Add start and sink to its existing optional logger; preserve fallback and checkpoint behavior. |
| create steps, references, synthesis, seed distillation, including repairs | Hash the actual prompt; add missing repair starts where a sink already exists. |
| intent proposal and gate suggestion | Add the missing start/hash to existing sink-bearing direct calls; retain no-target skips. |
| detail authoring, repair, lesson extraction | Hash actual prompts at existing starts. |
| review conceptual audit | Emit start from the actual reporting-independent invocation wrapper, including response-shape retries. |
| launcher run step | Hash the final execution prompt, leaving transport byte accounting unchanged. |
| foundational-logic sweep | Hash at existing start, preserving its no-run-log-import contract. |
| roadmap stages, feedback revisions, seed attempts, candidate run/review | Hash actual prompts and forward through the existing seed observer. |
| review criteria fulfillment, full review, review lesson extraction | Remain unchanged: functions have no run-logger parameter; command-to-function lifecycle plumbing is separate work. |
| create slug suggestion | Remain unchanged: no logger in scope. |
| jira export, annotate classification, lesson equivalence, concept-tree emission | Remain unchanged: no logger in scope; do not add command logging lifecycles here. |
| launcher deep validation and all-done review | Remain unchanged: no logger in scope. |

The follow-up sink inventory contains four functions without a start in their
body: `intent_proposal.propose_intents`, `gates.suggest_gates`,
`cli.completeness_cmd.finalize_completeness_run`, and
`cli.review_cmd._audit_sink`. The first two invoke directly and receive starts.
The last two only wrap/delegate calls; their no-prompt helper boundary stays.
Known command-lifecycle and slug deferrals remain BACKLOG #176 and #177.

## Verification contract

The final record identifies the reviewed range, focused and full-suite results,
mutation checks, and completed reviews. Existing tests outrank speculative
logging diagnoses. Older events lack `prompt_sha256`; a new event without an
available prompt uses null. This recovery adds no raw prompt text to the run log.

## Use of the recent analysis

Use prompt hashes to measure repeated explicit prompts in future captured runs.
Hash equality establishes equal rendered UTF-8 prompts, not equal model settings,
auto-loaded instructions, repository state, or tool reads; it does not alone
prove that a repeated call wastes tokens.
Keep backend-specific cached-token normalization in analysis, not production
logging. Lessons surface ablation and per-pass finding instrumentation remain
separate efforts; do not reduce audit samples from this repair or claim token
savings before a controlled comparison. The Integration replay retains its current
pipeline and scope boundaries.


## Review triage (2026-10-16 provenance)

| Review | Finding | Disposition |
| --- | --- | --- |
| 1 | No actionable findings in the initial recovery. | Candidate only. |
| 2 | Runtime hash import moves under `TYPE_CHECKING` during import cleanup. | Confirmed and corrected; concept-tree imports remain type-only. |
| 3 | No actionable findings after import correction. | Candidate only. |
| 4 | Intent proposals have a sink but no start/hash. | Confirmed and corrected; the class sweep also repairs gate suggestions. |
| 5 | No actionable findings in the complete final code. | First clean final pass. |
| 6 | No actionable findings in `a8119e1e6..d02362927`. | Second consecutive clean final pass; review converges. |

The sink inventory guard checks direct `invoker` calls in functions that bind
a sink, including a completely missing start event. The prompt-bearing start
guard separately checks hash forwarding. Neither claims semantic coverage of
arbitrary callback names or model-call paths without a run logger.

The parametrized behavioral checks cover apply, apply follow-up, source
assessment, risk classification, intent proposals and gate suggestions. Separate
skip cases pin zero calls for no-target intent/gate requests. The audit sampler
check pins exact hashes with no progress reporter. Historical reverted-attempt
notes remain provenance; this record owns the current recovery status.


## Verification evidence (2026-10-16 provenance)

Reviewed production/test range: `a8119e1e6..d02362927`.

| Commit | Concern |
| --- | --- |
| `83cfdf9aa` | Optional prompt-hash schema, reporter forwarding, and compatibility tests. |
| `4d80e5fba` | Invocation prompt identities, repaired completion sinks/events, and audit starts. |
| `d02362927` | Missing intent/gate starts, skip cases, and sink-bearing direct-call guard. |

- Final full suite: `.venv/bin/python -m pytest tests/ -q -n auto` —
  **14,570 passed, 67 skipped**, 82.65 seconds.
- Final focused writer/intent/gate suite: **267 passed**.
- Assessment-sink mutation: removing the sink makes the parametrized assessment
  case fail; restoration passes.
- Prompt-hash mutation: dropping the writer's forwarded hash makes the exact
  UTF-8/null regression fail; restoration passes.
- Intent-start mutation: removing the start makes both the functional intent
  case and the missing-start guard fail; restoration passes.
- Final reviews 5 and 6: independent `codex exec --model gpt-6.1-sol`,
  read-only, complete diff; two consecutive no-actionable-finding results on
  the final code. Static reviews, no test claims.

Raw logs and reports use `.tmp/token-ledger-recovery.*`; the durable assertions
and summarized results above remain useful without those transient files.
The global editable install still points at the older checkout. Replay calls
must keep explicitly selecting this clone through `PYTHONPATH`; this recovery
does not change another checkout or the global installation.


## Pickup

The logging recovery is implemented, tested, and review-converged in this clone.
Publication uses `fix/token-ledger-logging-recovery` from `origin/main`,
with the unrelated extensionless-file backlog note excluded. The owner
authorizes publication on 2026-10-16; merge remains an owner action. The original untracked
reverted-attempt handoff remains untouched. The isolated Integration replay remains
at its separate observation-index design decision; logging recovery does not
approve that pending scope choice or mutate the application repository.


## Publication mapping (2026-10-16 provenance)

The dedicated branch preserves the reviewed production and test files exactly.
The reviewed source commits map to publication commits as follows:

| Reviewed source | Publication |
| --- | --- |
| `83cfdf9aa` | `419bb93e0` |
| `4d80e5fba` | `25fae15f8` |
| `d02362927` | `5f977dfac` |

`changelog.d/token-ledger-logging-recovery.md` describes the visible log changes.
This owner-tracked repair has no Jira ticket; BACKLOG #176/#177 remain separate.
