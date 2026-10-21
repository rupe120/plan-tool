> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-pass-persistence.md`.
> Preserved here for history; do not edit.

# Resume a conceptual audit at its last completed pass

## Outcome

Every conceptual-audit pass that `review.audit_plan_until_stable` finishes and
merges into its stable-id union becomes a durable recovery boundary: the
sampler persists an in-progress checkpoint at each pass boundary, and a later
invocation whose sampler identity matches exactly resumes at the next
un-run pass instead of re-spending a backend call on completed ones. An
interrupted in-flight pass is retried, never counted complete. The checkpoint
is never final or reusable audit evidence — a resumed audit that reaches its
ordinary terminal result produces the same finding union, coverage verdict, and
qualified final sidecar as an uninterrupted run.

Source backlog entry: **`BACKLOG.md` #279** ("Persist and resume
conceptual-audit pass unions at every completed pass", 2026-08-14). This seed
inherits that entry's scope contract and elaborates it; the resulting plan
updates #279 in `BACKLOG.md` when the work ships.

## Overview

`review.audit_plan_until_stable` (`plan_tool/review.py`, def at `:8065`,
`return list(by_id.values())` at `:8538`) is the conceptual-audit sampler. It
holds **every** cross-pass value in local Python variables — `by_id`,
`materiality_by_id`, `observations_by_id`, `consecutive_dry`, `passes`,
`conforming_pass_count`, `failed_or_malformed_pass_count`, the three dry-streak
flags, `advisory_invalid`, `early_stop_reason` — and writes nothing to disk
between passes. Each pass is one Claude call of several minutes
(`CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT_S = 1800.0`,
`cli/completeness_phases.py`), and the default cap is
`AUDIT_DEFAULT_MAX_PASSES = 3`.

The existing durable boundary lands too late to help.
`cli/completeness_phases.py:write_pre_apply_audit_checkpoint` fires only
**after** the sampler has already returned, only on the `--iterate` path, and
it protects the `apply_finding` phase — not the sampling phase. An interruption
during pass 3 therefore discards passes 1 and 2 entirely and the next
invocation re-spends both.

The sampler runs **exactly once per command** on both paths — the audit-only
path via `cli/completeness_phases.py:_sample_conceptual_audit` (call at
`:2401`, driven from `cli/completeness_cmd.py:cmd_completeness`), and the
`--iterate` path via the inline call inside `_run_iterate_convergence_loop`
(`:3133`), which audits up front and reuses the result for every round. Those
are the only two production callers. So there is one sampler operation to
checkpoint, not one per round.

Everything this needs already exists as prior art: atomic durable writes
(`fileio.durable_write_text`), the `Recommendation` round trip
(`dataclasses.asdict` / `review.recommendation_from_persisted_mapping`), the
exact-input capture and revision (`review_persistence.AuditInputSnapshot`,
`.revision`, `.matches_disk`), a hash-gated resume precedent
(`checkpoint.compute_input_hash` / `load_if_valid` / `discard_checkpoint`), and
a run-log vocabulary for exactly this shape (`run_log.CheckpointSave` /
`CheckpointHit` / `CheckpointDiscard`, already driven by `create.py`). This
effort wires them into the sampler loop; it invents no new primitive.

## Architecture

### The role matrix — the closed vocabulary this effort commits to

`SavedReview.is_pre_apply_checkpoint` (`review_persistence.py`) is a
three-state role today, normalized on load by `_normalize_checkpoint_role` and
documented in `DATA_CONTRACT.md` § "Checkpoint-role policy". This effort adds a
fourth **producer state**. The state table below is the contract; the JSON
encoding that realizes it (a new role value at a new schema version, versus the
existing non-final role plus a positive in-progress discriminator) is
`detail`'s call under the invariant in the next subsection.

| Producer state | Written by | Reusable audit / apply / walk / history | Resumable |
| --- | --- | --- | --- |
| Ordinary final | the completeness report tail (`_persist_and_present_report`) | yes, when current and qualified | no |
| Pre-apply checkpoint | `write_pre_apply_audit_checkpoint`, once, before the first apply | no | no |
| **In-progress sampler checkpoint** | `audit_plan_until_stable`, at each pass boundary | **no** | yes, on exact identity match |
| Unknown role | no fresh producer; a malformed or version-mismatched marker on load, preserved as such by `update_annotation` | no | no |

Every state has an exit path: the in-progress state ends when the sampler
reaches an ordinary terminal result (the final sidecar is written and the
in-progress artifact stops being resumable), when its identity stops matching
(it is declined and a fresh sampler starts), or when an operator deletes it.
There is no state an operator can be stuck in.

### The fail-closed invariant, its mechanism, and its ordering fence

**Guarantee: an in-progress checkpoint is never read as final or reusable
evidence by any reader, including one written after this ships.**

The mechanism is not a sweep — it is that the artifact fails the *one*
predicate every existing final-eligibility reader already keys on. Seven gating
sites across five modules require the ordinary-final role
(`is_pre_apply_checkpoint is False` — tested directly, or by rejecting `True`
and `None`), and an in-progress checkpoint must never satisfy it:

- `completeness_report.is_reusable_audit_sidecar` (→ `resolve_reusable_audit`,
  the `--reuse-audit` / `--reuse-audit-id` lookup)
- `convergence_diagnosis._is_final_report_role` (→ `load_report_history`, and
  therefore every convergence verdict)
- `cli/completeness_phases._saved_audit_revision_is_current` (the
  `completeness-apply` open gate)
- `cli/review_cmd._direct_walk_role_ineligibility` and
  `_review_reuse_ineligibility` (direct saved-review walks and review reuse)
- `cli/data_contract_cmd._newest_saved_completeness_with_contract_payload` and
  `cmd_data_contract_apply`'s explicit-path gate

`convergence_diagnosis`'s audit-evidence ledger is the eighth site and the one
exception: it classifies rather than gates
(`AUDIT_EVIDENCE_SAVED_FINAL` / `_CHECKPOINT` / `_UNKNOWN_ROLE` /
`_MALFORMED_SIDECAR` / …), and it must gain a row that names an in-progress
checkpoint truthfully rather than mislabelling it as a pre-apply checkpoint or
as malformed. That is why the new state needs a **positive** discriminator, not
merely the absence of the final marker.

**Second, independent layer:** the in-progress artifact's filename must fall
outside the `<ts>-completeness.json` namespace that `resolve_reusable_audit`
and `data_contract_cmd` filter candidates on, so a pinned `--reuse-audit-id`
and the newest-candidate scan never consider it at all. Two layers, because
`review_persistence.list_saved_reviews` returns *every* `.json` in the reports
directory and only the callers narrow it.

**Ordering fence:** the role decision and its writer land before any reader
change. The reader work is then *verification that the invariant holds at each
site* — a parametrized assertion over the reader set — not seven independent
patches that could each get it right or wrong.

### Substrate: the saved-review family, and why not `checkpoint.py`

The checkpoint is a saved-review-family artifact in the plan's reports
directory (`review_persistence.plan_reports_dir`), reusing `save_review`'s
`Recommendation` serialization and `durable_write_text`. This follows #279's
stated dependency ("reuse the role-aware saved-review persistence substrate")
and is what makes the artifact visible as diagnostic evidence in the ledger.

**Rejected: `plan_tool/checkpoint.py`.** That module is a general hash-gated,
atomic, stdlib-only memoization primitive under
`<repo-root>/.plan-tool/checkpoints/<slug>/`, already used by `create.py` and
already paired with the `run_log` checkpoint events. Storing there would make
the fail-closed property structural (no saved-review reader can see it) and the
change much smaller. It is not taken because the artifact would then be
invisible to the audit-evidence ledger and to `load_review`, contradicting
#279's "remains diagnostic evidence" contract, and because #279 names the
saved-review substrate. `checkpoint.py`'s *shape* is still the model to follow
— hash-gated `load_if_valid`, explicit `discard`, no partial matching — and its
run-log events are reused verbatim.

### What the checkpoint carries: the sampler's own state, nothing invented

The payload is the loop's live state at the end of pass N, plus the identity
that licenses resuming it. Grounded in what `audit_plan_until_stable` actually
holds:

- **Findings and their derived judgments** — the `by_id` union in first-occurrence
  order, `materiality_by_id`, and `observations_by_id` (the
  `(pass_index, target_step_id)` pairs the arm-clustering advisory's
  ≥2-sample consensus rule consumes at `:8498`–`:8515`). Persisting the
  observations is what keeps a resumed run's advisory identical to an
  uninterrupted one's.
- **Streak and coverage state** — `passes`, `consecutive_dry`,
  `conforming_pass_count`, `failed_or_malformed_pass_count`, `stopped_on_dry`,
  `dry_streak_grew`, `dry_streak_unconfirmed_growth`, `dry_streak_low_yield`,
  `advisory_invalid`, `early_stop_reason`. These are exactly the inputs to
  `budget_report`'s `budget_limited` / `confirmation_kind` verdict
  (`:8434`–`:8486`); omitting one silently changes the resumed run's coverage
  verdict.
- **The frozen calibration** — `build_low_impact_demotion_lookup(repo_root)` is
  built once, before the loop (`:8207`), precisely so "history reads cannot
  change the materiality decision mid-audit". It reads repo telemetry, which can
  move between invocations, so the checkpoint carries the resolved
  `frozenset[FindingClass]` (`telemetry_analysis.LowImpactDemotionLookup`) and a
  resume restores it rather than rebuilding. Otherwise the resumed run scores
  *new* findings under a different rule than pass 1 did.
- **Identity** — see the next subsection.

**Deliberately not carried:** the once-per-run prompt-budget advisory state
(`audit_budget_covered`, `audit_base_bytes`, `audit_base_level`,
`audit_high_growth_rearmed`, `:8197`–`:8203`). It is best-effort advisory
output, not evidence; a resumed invocation may re-emit its one warning.

### Resume identity is strictly stricter than `--reuse-audit` freshness

Reuse and resume are different operations and must not share a gate. Reuse
*substitutes* one already-complete union; resume *continues accumulating into*
one, so it can mix two inputs in a way reuse cannot.

Today `resolve_reusable_audit` returns `fresh=audit_revision_match` — the
audit-input revision alone. `code_match` is computed and returned but feeds only
the staleness *explanation* (`cli/completeness_cmd.py:_resolve_audit_reuse`,
the `if not ru.fresh:` arm). A code-only change therefore leaves a saved audit
reusable today.

Resume must not inherit that. A conceptual pass reads the repo at HEAD, so
resuming across a code change would union findings from two code revisions —
which #279 forbids outright. **Resume requires all of:**

1. `AuditInputSnapshot.fingerprint` equality against a fresh capture (plan bytes,
   every selected-grade detail artifact and its resolution/state, `source_seed`
   bytes, project-context digest, and `detail_grade` — see
   `review_persistence._audit_input_fingerprint`);
2. code-fingerprint equality (`fingerprint.compute_code_fingerprint`), which
   reuse does **not** require;
3. the same audit stage (`bare` / `detail`) and detail grade;
4. the same sampler parameters: `max_passes`, `dry_rounds`, `new_threshold`.

Any mismatch, a malformed payload, or an unreadable file declines to a fresh
sampler at pass 1 and says so; nothing is partially carried and no rule is
loosened. This is a byte-equality check on recorded identity, never a
similarity judgment.

### Where the write happens, and where it must not

The write is at the **pass boundary** — after pass N's merge into `by_id` *and*
all of its bookkeeping (materiality, dry-streak, coverage counters), before
pass N+1 renders its prompt. Concretely, that is after the accounting block at
`:8401`–`:8431` in the iterations the loop continues past, including the
`pass_errored` `continue` arm at `:8363` (an errored pass still consumed a slot
against the cap; not recording it would let a resumed run re-spend it and
overrun `max_passes`).

Never between the invoker call and the merge: that is what makes an interrupted
in-flight pass retried rather than completed.

On a terminal exit — the dry-streak `break`, the plan-quota `break` at `:8358`,
or falling out at the cap — the sampler invalidates the in-progress checkpoint
**before returning**, so the ordinary final sidecar written afterwards by the
CLI tail is the only thing a later invocation can find. A completed audit
leaves nothing resumable.

**The cap is a sampler budget, not a per-invocation one.** Resume restores
`passes`, so an interrupted-and-resumed audit spends at most `max_passes` calls
in total.

### Ownership, failure posture, and presentation

**One implementation, at the sampler.** Detection, validation, load, and
invalidation live at the top and bottom of `audit_plan_until_stable`, which
already owns the input capture and the whole loop state. Neither call site
re-implements them; the orchestration change is presentation and run-log
wiring only. Two copies of a resume gate is precisely the class-sweep hazard
this repo keeps paying for.

**Asymmetric failure posture, deliberately:** a checkpoint *write* failure is
best-effort and never fails an otherwise-healthy audit (matching
`record_audit_coverage`, the prompt-budget advisory, and
`review_persistence._current_step_ids`); a checkpoint *read* failure fails
closed to a fresh sampler.

**Presentation.** The console names, at resume, which pass it is resuming at and
how many findings carry forward, and at decline, why (identity mismatch versus
malformed). The final report records that the audit was resumed as
**provenance only** — it must live outside `qualified_result` and
`audit_coverage`, both of which have to be identical to an uninterrupted run's.

**Run-log provenance reuses the existing events** — `run_log.CheckpointSave` /
`CheckpointHit` / `CheckpointDiscard`, whose `name` / `input_hash` /
`payload_bytes` / `reason` fields already fit, as `create.py` demonstrates. No
new event type and no new `DATA_CONTRACT.md` run-log row. A run log is open
**only** on the `--iterate` path today (`cli/completeness_cmd.py:cmd_completeness`
starts one under `if budget.enabled`), so the events ride that path; the
audit-only path does not gain a run log, and its resume is visible through the
console and report instead.

## In scope

`plan_tool/review.py` (`audit_plan_until_stable`'s state, pass loop, resume
detection, and terminal invalidation); `plan_tool/review_persistence.py` (the
in-progress role, its schema/version policy, and its read/write helpers);
`plan_tool/completeness_report.py`, `plan_tool/convergence_diagnosis.py`,
`plan_tool/cli/review_cmd.py`, `plan_tool/cli/data_contract_cmd.py`,
`plan_tool/cli/completeness_phases.py`, `plan_tool/cli/completeness_cmd.py`
(the reader-invariant verification and the resume presentation/wiring);
`DATA_CONTRACT.md` (§ "Saved review sidecar" and § "Checkpoint-role policy");
`docs/AUDIT_FLOW.md` (§ "Pre-apply checkpoint vs. final report — the persisted
role", § "Saved audit evidence ledger — visible artifacts, not a decision") and
`docs/AUDIT_RESUME_FLOW.md`
(§ "Crash / interrupt recovery" — the operator-facing home for resume, an
elaboration of #279's "`docs/AUDIT_FLOW.md`" within the same doc
responsibility); and `tests/`.

**Not** `plan_tool/checkpoint.py`, `plan_tool/run_log.py`, or
`plan_tool/fingerprint.py` — each is consumed as-is.

### Scope contract

- **Binary observable, in one sentence:** the sampler identity recorded in an
  in-progress checkpoint — audit-input revision, code fingerprint, audit stage,
  detail grade, `max_passes`, `dry_rounds`, `new_threshold` — is equal, value
  for value, to the one recomputed at resume time; resume iff equal, fresh
  sampler otherwise.
- **Enumerated not-allowed list** (stating "the gate is identity, not judgment"
  in prose does not hold this line; the enumeration does). None of the
  following may be built, and a finding proposing one is invalid, not deferred:
  - any partial, tolerant, "close enough", or age-weighted identity match;
  - any judgment about whether carried findings are still *relevant*, correct,
    or worth keeping — carried findings are replayed verbatim by id;
  - any re-scoring, re-severity, re-anchoring, or re-materiality of a carried
    finding, and any change to the union or confirmation rules;
  - any new gate, blocking predicate, exit-code flip, or continuation rule
    keyed on a checkpoint's presence, absence, or age — `is_blocking`,
    `is_blocking_finding`, `is_blocking_impact`, `should_continue`,
    `_completeness_has_blocking_findings`, and `--fail-on-findings` are all
    untouched;
  - any finding, advisory, or convergence signal *about* resumption;
  - any size, shape, or length cap on the checkpoint payload.
- **Allowed behavior changes:** an in-progress checkpoint artifact appears in
  the reports directory during a multi-pass audit; a matching later invocation
  spends fewer backend calls; console/report/run-log lines report resume,
  decline, and discard. Nothing else — same findings, same severities, same
  union, same coverage verdict, same qualified result, same exit codes.
- **Allowed reorganization:** none.
- **Verification:** § Testing below.
- **Stop / defer:** § Deferred, and anything the iteration loop surfaces outside
  this fence goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied as plan
  expansion.

## Out of scope

- Detaching, killing, or otherwise controlling a live backend call, and
  checkpointing a partial model reply. The pass boundary is the finest unit
  this effort claims; inside-a-call granularity is `BACKLOG.md` #124.
- Changing finding severity, union, or confirmation semantics in any way.
- Treating a checkpoint as final evidence anywhere, or relaxing any current
  reader's fail-closed posture.
- Extending the mechanism to `detail`, `run`, the per-step purity scan, the
  reconcile lanes (`reconcile-plan` / `reconcile-code`), the roadmap stage loop,
  or any other non-conceptual audit surface.
- Automatic resumption after input or configuration drift, and any prompt
  offering to resume anyway.
- Any new CLI flag. Resume is unconditional when identity matches; there is no
  `--resume-audit` / `--no-resume-audit` surface in this effort.
- Any new key in the `completeness-audit --json` payload
  (`DATA_CONTRACT.md` § "`completeness-audit --json`").
- Concurrency between two simultaneous audits of the same plan. The audit-only
  path holds no iteration lock, and `checkpoint.py`'s existing posture
  ("undefined behaviour; don't run plan-tool concurrently against the same
  plan") stands. Atomic single-file replacement plus the identity gate mean the
  worst case is a declined resume, not a corrupted union.
- Migrating, backfilling, or garbage-collecting historical report artifacts.
- Correcting the pre-existing stale claims listed in § Deferred.

## Risks

- **The fail-closed sweep is incomplete and an in-progress checkpoint is read as
  final.** The expensive failure: a partial union enters `--reuse-audit`,
  `completeness-apply`, or convergence history and reads as converged evidence.
  Mitigated structurally rather than by diligence — the artifact fails the
  single ordinary-final predicate all seven gating sites already share, and
  sits outside the `-completeness.json` filename namespace.
  The parametrized reader test in § Testing is what keeps a *future* reader from
  silently inheriting the wrong default.
- **A resumed run's coverage verdict diverges from an uninterrupted one's.**
  `confirmation_kind` / `budget_limited` depend on four counters and three
  streak flags; the arm-clustering advisory depends on the per-id observation
  history; materiality depends on a calibration read from moving repo
  telemetry. Any one omitted from the payload produces a quietly different
  verdict. Mitigated by the equivalence test, which compares the whole coverage
  record and the advisory, not just the finding count.
- **Resume mixes findings from two code revisions.** A conceptual pass reads the
  repo at HEAD, and reuse-freshness deliberately ignores the code fingerprint
  today. Mitigated by making resume identity strictly stricter than reuse
  freshness, and by mutating the code fingerprint alone in the decline matrix.
- **A malformed checkpoint is trusted.** Mitigated by the read-side fail-closed
  posture and by testing truncation, an undecodable `Recommendation` payload,
  and a future schema version — each must start a fresh sampler without raising.
- **Interaction with the existing pre-apply checkpoint.** Both artifacts can
  exist for one plan in one `--iterate` run, seconds apart, in the same
  directory whose stems `completeness_report._reserve_report_timestamp`
  reserves. A single stable-named in-progress artifact replaced in place — O(1)
  artifacts per audit, not O(passes) — keeps it out of that reservation and
  keeps the ledger from filling with partial rows.
- **Existing sampler tests change behavior.** Resume is on by default inside
  `audit_plan_until_stable`, so any test that runs two identical samplers
  against one `tmp_path` will now legitimately resume and spend fewer calls. A
  red sibling test here is the expected outcome of a class-wide change, not a
  reason to narrow the fix: read each one and decide whether it is a carve-out
  to assert or a stale expectation to update.

## Testing

Properties, each proved by mutating one thing and watching the outcome change.
The fake seam is `tests/test_review.py:TestAuditPlanUntilStable._sampling_invoker`
(a queued canned reply per call); interruption is simulated by raising a
`BaseException` such as `KeyboardInterrupt` — an ordinary `Exception` is
swallowed by `check_plan_audit`'s `except Exception` handler and recorded as an
*errored pass*, which is a different property. `TestPlanAuditPassConformance::
test_audit_plan_until_stable_pass_errored_counts_as_failed` is the precedent for
the errored-pass arm;
`tests/cli/test_completeness_cmd.py::test_pre_apply_checkpoint_sidecar_is_marked_and_v4`
and `test_iterate_loop_writes_pre_apply_checkpoint` are the precedents for
role/ordering assertions at the CLI layer.

- **Union preserved, next pass resumed.** Interrupt during pass 3 of 3 after
  passes 1–2 completed: the persisted checkpoint holds exactly their union, and
  a second invocation spends exactly one call, whose prompt carries the pass-1+2
  findings in its convergence-guidance block.
- **In-flight pass retried, never completed.** No finding from the interrupted
  pass's partial state is unioned, and the resumed run's `passes_used` matches
  the uninterrupted baseline.
- **Cap is a sampler budget.** Two invocations of a `max_passes=3` audit never
  sum to more than three backend calls.
- **Errored pass still checkpoints.** A non-zero-exit pass advances `passes` and
  `failed_or_malformed_pass_count`; a resume after it does not re-spend its
  slot.
- **Decline matrix, one mutation at a time.** Each of plan bytes, one detail
  file's bytes, `source_seed` bytes, project context, the code fingerprint,
  detail grade, audit stage, `max_passes`, `dry_rounds`, and `new_threshold`
  mutated *alone* starts a fresh sampler at pass 1 with the full budget. Proving
  the composite differs is not enough — each component must decline on its own,
  and the code fingerprint is the one reuse-freshness ignores.
- **Malformed fails closed.** Truncated JSON, an undecodable persisted
  `Recommendation`, and an unsupported schema version each start a fresh
  sampler and raise nothing.
- **Reader rejection, parametrized over the whole reader set** — one table
  covering `is_reusable_audit_sidecar` / `resolve_reusable_audit`,
  `_saved_audit_revision_is_current`, `_direct_walk_role_ineligibility`,
  `_review_reuse_ineligibility`, `_is_final_report_role` / `load_report_history`,
  both `data_contract_cmd` gates, and the evidence-ledger classifier, so a
  reader added later fails loudly instead of inheriting the wrong default.
  The ledger row additionally asserts the state is *named* as in-progress, not
  reported as a pre-apply checkpoint or as malformed.
- **Equivalence with an uninterrupted run.** Over one canned reply sequence, an
  uninterrupted run and an interrupted-then-resumed run produce identical
  finding ids and order, identical per-id materiality, identical
  `audit_coverage` (`passes_used`, `cap`, `budget_limited`,
  `confirmation_kind`, `conforming_pass_count`,
  `failed_or_malformed_pass_count`, `early_stop_reason`), identical
  `qualified_result`, and an identical arm-clustering advisory.
- **Frozen calibration survives the interruption.** Mutating the repo's
  calibration evidence between the two invocations does not change the resumed
  run's materiality for carried *or* newly-found findings.
- **No resumable checkpoint after a terminal exit** — for each of the dry-streak
  stop, the cap stop, and the plan-quota early stop, a third invocation with
  unchanged inputs starts at pass 1.
- **Asymmetric failure posture.** A write that raises `OSError` leaves the audit
  completing exactly as today; a read that raises leaves a fresh sampler.
- **Both call sites.** The audit-only path and the `--iterate` path both resume
  identically, and neither carries its own copy of the resume gate.

## Acceptance criteria

- A conceptual audit interrupted after N completed passes persists exactly
  those passes' union, materiality, and observations, and a matching later
  invocation resumes at pass N+1 rather than re-running any completed pass.
- An interruption during a pass causes that pass — and only that pass — to be
  re-run.
- Resume happens only on exact equality of the recorded sampler identity:
  audit-input revision, code fingerprint, audit stage, detail grade,
  `max_passes`, `dry_rounds`, `new_threshold`. Any single mismatch, a malformed
  payload, or an unreadable file starts a fresh sampler at pass 1 and says why.
- A resumed audit that reaches an ordinary terminal result produces the same
  finding union, the same per-id materiality, the same `audit_coverage` record,
  the same `qualified_result`, and the same arm-clustering advisory as an
  uninterrupted run over the same replies.
- No in-progress checkpoint is ever accepted as final or reusable evidence by
  `--reuse-audit`, `--reuse-audit-id`, `completeness-apply`, a direct
  saved-review walk, review reuse, `data-contract-apply`, or convergence
  history; the audit-evidence ledger names it as in-progress rather than as a
  pre-apply checkpoint or as malformed.
- A completed sampler leaves no resumable in-progress checkpoint, and a
  multi-pass audit leaves at most one in-progress artifact on disk at a time.
- An interrupted-and-resumed audit spends no more than `max_passes` backend
  calls in total.
- Finding severity, union, confirmation, blocking, continuation, and exit-code
  behavior are unchanged, and `completeness-audit --json`'s payload gains no
  key.
- `DATA_CONTRACT.md` § "Checkpoint-role policy" documents the fourth producer
  state with its eligibility and exit path; `docs/AUDIT_FLOW.md` and
  `docs/AUDIT_RESUME_FLOW.md` describe resume, decline, and discard for an
  operator.
- `BACKLOG.md` #279 is updated when this ships (per CLAUDE.md's
  backlog-derived-seed convention): removed once fully shipped, or marked
  plan-authored while execution remains pending, with any deferred follow-up
  left or updated.

## Deferred

- Pass-level or unit-level resume for `detail` authoring, `run` steps, the
  per-step purity scan, the reconcile lanes, or the roadmap stage loop. Each has
  a different natural boundary and a different evidence contract; validate this
  one under forced interruption first.
- Checkpointing *inside* a single backend call — `BACKLOG.md` #124's territory,
  and explicitly a different problem from persisting between complete calls.
- A `--resume-audit` / `--no-resume-audit` operator flag, if a case appears
  where declining an identity-valid resume matters.
- Surfacing resume state in `completeness-audit --json`, if a CI consumer needs
  it.
- **Two pre-existing stale claims found while grounding this seed — file in
  `BUG_BACKLOG.md`, do not fix here.** `docs/AUDIT_RESUME_FLOW.md` § TL;DR and
  the `--reuse-audit` help text in `cli/completeness_cmd.py` both state that
  reuse requires "both the saved plan fingerprint AND code fingerprint" to
  match. `completeness_report.resolve_reusable_audit` returns
  `fresh=audit_revision_match` and uses `code_match` only to word the staleness
  message, so a code-only change leaves a saved audit reusable. This seed
  deliberately does not repeat the claim, and this effort's resume gate does not
  inherit the behavior.
