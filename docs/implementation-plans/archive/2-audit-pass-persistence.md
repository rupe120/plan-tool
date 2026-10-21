> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Audit Pass Persistence
intent: 'Every nonterminal conceptual-audit pass that `review.audit_plan_until_stable`
  finishes and whose boundary checkpoint persists becomes a durable recovery boundary:
  the sampler replaces an in-progress checkpoint only when another pass will run,
  and a later fresh-sampling invocation whose declared sampler identity matches exactly
  resumes at the next un-run pass instead of resampling completed durable passes.
  An interrupted in-flight pass is retried, never counted complete. The checkpoint
  is never final or reusable audit evidence. At a normal terminal result, the sampler
  attempts a non-resumable transition of any existing checkpoint before cleanup; a
  published transition makes any cleanup residue non-resumable, while only a transition
  failure before publication preserves the prior recovery boundary. Terminal delivery
  recovery and global repository identity are outside this proof.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/audit-pass-persistence.md
steps:
- id: 1
  title: Add an in-progress sampler-checkpoint role to review_persistence, stored
    as one stable-named artifact that each write replaces in place, sits outside the
    reserved report stems, carries its sampler state in a separately persisted and
    registered SavedReview field, and is rejected by each current per-candidate role
    check downstream of the raw saved-review listing
  intent: Give the conceptual-audit sampler a durable place to record a completed
    pass that no reader can mistake for a final result.
  files:
  - plan_tool/review_persistence.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_review_persistence.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/audit-pass-persistence/01-progress-sampler-checkpoint-role-review.md
  status: done
- id: 2
  title: Write and replace the in-progress checkpoint after each pass that will continue,
    then invalidate the prior checkpoint at terminal results with publication-aware
    failure handling
  intent: Make each continuing conceptual pass a durable boundary so an interruption
    no longer discards successfully persisted passes, without turning a terminal pass
    into resumable work.
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The role, the stable artifact path, and the write helper the sampler calls
      for a continuing pass and for terminal invalidation.
  detail: docs/implementation-plans/plan-details/audit-pass-persistence/02-write-replace-progress-checkpoint-after.md
  status: done
- id: 3
  title: Resume the sampler at the next un-run pass on an exact identity match, decline
    to a fresh pass-1 sampler on any mismatch or malformed payload, and update the
    existing sampler tests that now legitimately resume
  intent: Let a matching later invocation continue an interrupted audit instead of
    resampling completed logical passes.
  files:
  - plan_tool/review.py
  - plan_tool/backend.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/prompts/plan-audit.md
  - tests/test_review.py
  - tests/test_backend.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: The loader whose read failures fail closed, and the recorded identity fields
      the resume gate compares.
    2: The persisted pass-boundary state this step restores; its recovery outcome
      follows the actual published artifact rather than an undifferentiated write
      error.
  detail: docs/implementation-plans/plan-details/audit-pass-persistence/03-resume-sampler-next-un-run-pass-on.md
  status: done
- id: 4
  title: Give load_audit_evidence_ledger checkpoint-aware loading and a third artifact-discovery
    branch for the stable-named sampler checkpoint, name its lifecycle in the ledger,
    and prove each current final-eligibility reader still rejects it, including the
    direct saved-review walk
  intent: Keep a partial finding union out of every reuse, apply, walk, and convergence-history
    path while still showing it truthfully as diagnostic evidence.
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/data_contract_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_convergence_diagnosis.py
  - tests/test_review_persistence.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: The persisted role the ledger classifies and the seven gating readers test
      against; the ordering fence puts it before any reader change.
    2: The stable writer and terminal transition the readers observe only after they
      land.
  detail: docs/implementation-plans/plan-details/audit-pass-persistence/04-give-load-audit-evidence-ledger.md
  status: done
- id: 5
  title: Report a resumed audit as provenance only, leaving qualified_result and audit_coverage
    identical to an uninterrupted run
  intent: Tell an operator that an audit was resumed without letting resumption leak
    into the evidence a reader treats as the audit's verdict.
  files:
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: The resumed/declined signal the sampler surfaces to its callers, and the guarantee
      that a resumed run's coverage record already matches an uninterrupted one's.
  detail: docs/implementation-plans/plan-details/audit-pass-persistence/05-report-resumed-audit-provenance-only.md
  status: done
- id: 6
  title: 'Document resume, decline, and discard in the audit flow docs and update
    BACKLOG.md #279'
  intent: Give an operator one place that explains when an interrupted audit resumes,
    when it starts over, and what the leftover artifact is.
  files:
  - docs/how-to/pipeline/audit.md
  - docs/how-to/recovery/audit.md
  - BACKLOG.md
  allowed_mentions:
  - docs/how-to/recovery/README.md
  - docs/how-to/recovery/create.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 3
  - 4
  - 5
  depends_on_notes:
    1: The landed role names, artifact path, and identity fields the docs describe
      and the source maps must cite.
    3: The decline reasons and identity components an operator sees.
    4: The ledger state name the evidence-ledger section documents.
    5: The console and report lines the operator-facing walkthrough quotes.
  detail: docs/implementation-plans/plan-details/audit-pass-persistence/06-document-resume-decline-discard-audit.md
  status: done
---
# Audit Pass Persistence

## Overview

This plan makes every successfully persisted nonterminal conceptual-audit pass a durable recovery boundary. `review.audit_plan_until_stable` (`plan_tool/review.py`, def at `:8065`, `return list(by_id.values())` at `:8538`) is the conceptual-audit sampler: after a pass that will continue, it replaces an in-progress checkpoint, and a later fresh-sampling invocation whose declared sampler identity matches exactly resumes at the next un-run pass instead of resampling completed durable passes. An interrupted in-flight pass is retried, never counted complete. The checkpoint is never final or reusable audit evidence. This is a recovery proof for an interrupted sampler, not a global repository snapshot or a new policy for reusable final audits.

Everything this needs already exists as prior art: atomic durable writes (`fileio.durable_write_text`), the `Recommendation` round trip (`dataclasses.asdict` / `review.recommendation_from_persisted_mapping`), the exact-input capture and revision (`review_persistence.AuditInputSnapshot`, `.revision`, `.matches_disk`), a hash-gated resume precedent (`checkpoint.compute_input_hash` / `load_if_valid` / `discard_checkpoint`), and a run-log vocabulary for exactly this shape (`run_log.CheckpointSave` / `CheckpointHit` / `CheckpointDiscard`, already driven by `create.py`). This effort wires them into the sampler loop; it invents no new primitive.

Source backlog entry: **`BACKLOG.md` #279** (plan-authored as `audit-pass-persistence`, 2026-08-14). It records this plan's scoped contract while execution remains pending and will be removed or updated when the work ships.

## Problem statement

`review.audit_plan_until_stable` holds **every** cross-pass value in local Python variables — `by_id`, `materiality_by_id`, `observations_by_id`, `consecutive_dry`, `passes`, `conforming_pass_count`, `failed_or_malformed_pass_count`, the three dry-streak flags, `advisory_invalid`, `early_stop_reason` — and writes nothing to disk between passes. Each logical pass is one complete conceptual sample. `check_plan_audit` may make one bounded heading-repair attempt for that sample, but the repair has no independent checkpoint or sampler slot. The default logical-pass cap is `AUDIT_DEFAULT_MAX_PASSES = 3`.

The existing durable boundary lands too late to help. `cli/completeness_phases.py:write_pre_apply_audit_checkpoint` fires only **after** the sampler has already returned, only on the `--iterate` path, and it protects the `apply_finding` phase — not the sampling phase. An interruption during pass 3 therefore discards passes 1 and 2 entirely and the next invocation resamples both.

Each command that reaches fresh sampling runs the sampler **exactly once** on either path — the audit-only path via `cli/completeness_phases.py:_sample_conceptual_audit` (call at `:2401`, driven from `cli/completeness_cmd.py:cmd_completeness`), or the `--iterate` path via the inline call inside `_run_iterate_convergence_loop` (`:3133`), which audits up front and reuses the result for every round. Existing reusable-final selection invokes the sampler zero times. Those are the only two production callers, so a fresh-sampling command has one sampler operation to checkpoint, not one per round.

## Architecture

### The role matrix — the closed vocabulary this effort commits to

`SavedReview.is_pre_apply_checkpoint` (`review_persistence.py`) is a three-state role today, normalized on load by `_normalize_checkpoint_role` and documented in `DATA_CONTRACT.md` § "Checkpoint-role policy". This effort adds the sampler producer role with two lifecycle states: resumable `in-progress` and non-resumable `terminal-residue`. The state table below is the contract; the JSON encoding that realizes it (a new role value at a new schema version, versus the existing non-final role plus a positive lifecycle discriminator) is `detail`'s call under the invariant in the next subsection.

**Whichever encoding is chosen, it must not fall through `_normalize_checkpoint_role`'s legacy path.** That function (`review_persistence.py:419`) recognizes a role marker only for `version in {_ROLE_AWARE_SCHEMA_VERSION, _AUDIT_REVISION_SCHEMA_VERSION}`; any other version reads a missing marker as `False` (ordinary final) — the deliberate version-1/2 legacy-compatibility default. Picking "a new role value at a new schema version" without also adding that version to the recognized set — or picking an encoding whose lifecycle marker can read as absent — silently normalizes the checkpoint to ordinary-final, defeating the fail-closed guarantee this section exists to state. Whichever encoding `detail` picks must keep either lifecycle outside that fallback, not merely inside the role-matrix table.

The sampler's live state has its own conditionally persisted `SavedReview`
field rather than stretching the exact-shape `audit_coverage` record. Its
serialized form and the field both register in `plan_tool/data_contract.py`,
so the existing dataclass/registry drift check remains true. The chosen field
stores only the checkpoint payload named below; it does not change final
sidecars or the public `completeness-audit --json` contract.

| Producer state | Written by | Reusable audit / apply / walk / history | Resumable |
| --- | --- | --- | --- |
| Ordinary final | the completeness report tail (`_persist_and_present_report`) | yes, when current and qualified | no |
| Pre-apply checkpoint | `write_pre_apply_audit_checkpoint`, once, before the first apply | no | no |
| **In-progress sampler checkpoint** | `audit_plan_until_stable`, after each successfully persisted pass that will continue | **no** | yes, while incomplete and on exact identity match |
| **Terminal sampler residue** | `audit_plan_until_stable`, after its non-resumable transition publishes and the artifact remains on disk | **no** | no |
| Unknown role | no fresh producer; a malformed or version-mismatched marker on load, preserved as such by `update_annotation` | no | no |

Every state has an exit path: at a normal terminal result, the sampler skips the ordinary resumable write and attempts a non-resumable transition of any existing prior checkpoint before cleanup. If none exists, it has nothing to transition or clean up. Once a transition is published, a cleanup failure leaves diagnostic non-final residue that a later invocation declines rather than resumes. A failure before publication leaves the prior durable pass boundary, so a later fresh-sampling invocation may re-run the terminal pass. A post-publication durability error is resolved from the valid artifact's role on the later invocation — never treated as proof that the prior boundary survived — and carries no crash-durability claim. Final-presentation recovery after process or output failure is outside this effort. An identity mismatch starts a fresh sampler, and an operator may delete either artifact. There is no state an operator can be stuck in.

### The fail-closed invariant, its mechanism, and its ordering fence

**Guarantee: no sampler checkpoint lifecycle is read as final or reusable evidence by the current readers named below.**

The mechanism is not a sweep — it is that the artifact fails the *one* predicate every existing final-eligibility reader already keys on. Seven gating sites across five modules require the ordinary-final role (`is_pre_apply_checkpoint is False` — tested directly, or by rejecting `True` and `None`), and neither sampler lifecycle may satisfy it:

- `completeness_report.is_reusable_audit_sidecar` (→ `resolve_reusable_audit`, the `--reuse-audit` / `--reuse-audit-id` lookup)
- `convergence_diagnosis._is_final_report_role` (→ `load_report_history`, and therefore every convergence verdict)
- `cli/completeness_phases._saved_audit_revision_is_current` (the `completeness-apply` open gate)
- `cli/review_cmd._direct_walk_role_ineligibility` and `_review_reuse_ineligibility` (direct saved-review walks and review reuse)
- `cli/data_contract_cmd._newest_saved_completeness_with_contract_payload` and `cmd_data_contract_apply`'s explicit-path gate

`convergence_diagnosis`'s audit-evidence ledger is the eighth site and the one exception: it classifies rather than gates (`AUDIT_EVIDENCE_SAVED_FINAL` / `_CHECKPOINT` / `_UNKNOWN_ROLE` / `_MALFORMED_SIDECAR` / …), and it must name an in-progress checkpoint and a terminal sampler residue truthfully rather than mislabelling either as a pre-apply checkpoint or as malformed. That is why the new state needs a **positive** discriminator, not merely the absence of the final marker.

**Second, independent layer:** the sampler artifact's filename must fall outside the `<ts>-completeness.json` namespace that `resolve_reusable_audit` and `data_contract_cmd` filter candidates on, so a pinned `--reuse-audit-id` and the newest-candidate scan never consider it at all. Two layers, because `review_persistence.list_saved_reviews` returns *every* file in the reports directory with no completeness-suffix or role filter of its own — it is not itself a gate, and this effort adds none to it. What keeps the checkpoint out of anything consequential is unchanged: every one of `list_saved_reviews`'s roughly ten callers already applies its own downstream per-candidate role check before treating a loaded sidecar as final, and that check is exactly what the eight gating sites above enumerate. A stable-named sampler artifact can appear in the raw listing; it is rejected wherever the listing is actually consumed.

**Ledger discovery needs checkpoint-aware loading before its third branch, not just a third label.** `load_audit_evidence_ledger` currently loads only `COMPLETENESS_SIDECAR_SUFFIX` files before it pairs `artifact_paths`; a stable checkpoint outside that namespace therefore is absent from the saved-review cache, and adding it later would fail the cache check rather than produce a row. Its normal loading path must include the stable checkpoint before pairing and classification. Row construction then gains a third branch that recognizes that filename directly and adds it as a standalone entry with no `.md` report to pair with (an in-flight sampler writes none), before it can be classified and named.

**Ordering fence:** the role decision and its writer land before any reader change. The reader work then verifies this invariant at the named sites through one parametrized assertion. A future reader must add its own role check and test; this effort does not introduce a new universal admission framework.

### Substrate: the saved-review family, and why not `checkpoint.py`

The checkpoint is a saved-review-family artifact in the plan's reports directory (`review_persistence.plan_reports_dir`), reusing `save_review`'s `Recommendation` serialization and `durable_write_text`. Before its first stable-name write, its writer creates that reports directory, matching `save_review` and `write_completeness_report`; a first bare audit therefore reaches the best-effort checkpoint write instead of failing on a missing parent. This follows #279's stated dependency ("reuse the role-aware saved-review persistence substrate") and is what makes the artifact visible as diagnostic evidence in the ledger.

**Rejected: `plan_tool/checkpoint.py`.** That module is a general hash-gated, atomic, stdlib-only memoization primitive under `<repo-root>/.plan-tool/checkpoints/<slug>/`, already used by `create.py` and already paired with the `run_log` checkpoint events. Storing there would make the fail-closed property structural (no saved-review reader can see it) and the change much smaller. It is not taken because the artifact would then be invisible to the audit-evidence ledger and to `load_review`, contradicting #279's "remains diagnostic evidence" contract, and because #279 names the saved-review substrate. `checkpoint.py`'s *shape* is still the model to follow — hash-gated `load_if_valid`, explicit `discard`, no partial matching — and its run-log events are reused verbatim.

### What the checkpoint carries: the sampler's own state, nothing invented

The payload is the loop's live state at the end of pass N, plus the identity that licenses resuming it. Grounded in what `audit_plan_until_stable` actually holds:

- **Findings and their derived judgments** — the `by_id` union in first-occurrence order, `materiality_by_id`, and `observations_by_id` (the `(pass_index, target_step_id)` pairs the arm-clustering advisory's ≥2-sample consensus rule consumes at `:8498`–`:8515`). Persisting the observations is what keeps a resumed run's advisory identical to an uninterrupted one's.
- **Streak and coverage state** — `passes`, `consecutive_dry`, `conforming_pass_count`, `failed_or_malformed_pass_count`, `stopped_on_dry`, `dry_streak_grew`, `dry_streak_unconfirmed_growth`, `dry_streak_low_yield`, `advisory_invalid`, `early_stop_reason`. These are exactly the inputs to `budget_report`'s `budget_limited` / `confirmation_kind` verdict (`:8434`–`:8486`); omitting one silently changes the resumed run's coverage verdict.
- **The frozen calibration** — `build_low_impact_demotion_lookup(repo_root)` is built once, before the loop (`:8207`), precisely so "history reads cannot change the materiality decision mid-audit". It reads repo telemetry, which can move between invocations, so the checkpoint carries the resolved `frozenset[FindingClass]` (`telemetry_analysis.LowImpactDemotionLookup`) and a resume restores it rather than rebuilding. Otherwise the resumed run scores *new* findings under a different rule than pass 1 did.
- **Identity** — see the next subsection.

**Deliberately not carried:** the once-per-run prompt-budget advisory state (`audit_budget_covered`, `audit_base_bytes`, `audit_base_level`, `audit_high_growth_rearmed`, `:8197`–`:8203`). It is best-effort advisory output, not evidence; a resumed invocation may re-emit its one warning.

### Resume identity is a declared recovery fence

Reuse and resume stay separate. Existing `resolve_reusable_audit` resolution keeps its current precedence: if it selects an ordinary final audit, the command reuses that final union and never enters sampling. The in-progress checkpoint participates only on the fresh-sampling path; it does not change `--reuse-audit`, `--reuse-audit-id`, or the default reuse decision.

Within that path, **resume requires all of:**

1. `AuditInputSnapshot.fingerprint` equality against a fresh capture (plan bytes, every selected-grade detail artifact and its resolution/state, `source_seed` bytes, project-context digest, and `detail_grade` — see `review_persistence._audit_input_fingerprint`; this already determines bare versus detail stage);
2. equality of the existing declared-code fingerprint (`fingerprint.compute_code_fingerprint`), whose surface is this plan's `files`/`creates` list and explicitly includes `plan_tool/prompts/plan-audit.md` in step 3;
3. the same sampler parameters: `max_passes`, `dry_rounds`, `new_threshold`; and
4. the same selected backend and resolved model. `--backend` / `--model` / `PLAN_TOOL_BACKEND` (`plan_tool/backend.py`, `plan_tool/cli/parser.py`) choose that sampler; the effective `CliBackend` exposes the model already selected for dispatch without recomputing precedence.

This is intentionally **not** a global repository or execution-environment snapshot. The auditor may explore code beyond the declared surface, but detecting every such mutable input would be a separate consistency system. A concern about unrelated repository change calls for a fresh audit, not a widened resume gate. A mismatch, malformed payload, or unreadable checkpoint declines to fresh sampling at pass 1 and says why; nothing is partially carried.

### Where the write happens, and where it must not

The sampler decides whether another logical pass will run before it writes a resumable boundary. If it will continue, it writes after pass N's merge into `by_id` and all bookkeeping (materiality, dry-streak, coverage counters), before pass N+1 renders its prompt. If it will stop, it suppresses that ordinary replacement and takes the terminal-transition path against the prior checkpoint instead. The dry-streak, plan-quota, and cap paths share that rule; a nonterminal errored pass is still a continuing-pass boundary. A pass becomes a recovery boundary only when its replacement is durably published.

Never between the invoker call and the merge: that is what makes an interrupted in-flight pass retried rather than completed.

On a terminal exit — the dry-streak `break`, the plan-quota `break` at `:8358`, or falling out at the cap — the sampler attempts the non-resumable transition for any existing checkpoint, then tries to delete it **before returning** only after publication. Its publication makes any cleanup residue diagnostic and non-resumable. A transition failure before publication leaves the prior durable boundary, so a later fresh-sampling invocation may re-run the terminal pass. The ordinary final presentation remains the caller's existing responsibility; this plan does not preserve a terminal result across a process stop or output failure after the sampler returns.

**Both persistence writes and terminal cleanup are best-effort.** An `OSError` must not crash an otherwise-successful audit. The existing durable writer can report an error before or after its stable replacement becomes visible, so the recovery contract distinguishes them: a pre-publication failure leaves the prior durable checkpoint as the recovery boundary; after publication, a later fresh-sampling invocation uses the valid artifact it finds and its role to decide resume or decline. No stronger crash-durability or total-work claim applies across a post-publication error. Only a published terminal transition makes cleanup residue non-resumable.

**The cap is a logical sampler-pass budget, not a per-invocation or subprocess-attempt budget.** Across a successful durable-resume chain, restoring `passes` completes at most `max_passes` logical passes; a bounded heading repair remains within its triggering pass.

### Ownership, failure posture, and presentation

**One implementation, at the sampler.** Detection, validation, load, and invalidation live at the top and bottom of `audit_plan_until_stable`, which already owns the input capture and the whole loop state. Neither call site re-implements them; the orchestration change is presentation and run-log wiring only. Two copies of a resume gate is precisely the class-sweep hazard this repo keeps paying for.

**Asymmetric failure posture, deliberately:** a checkpoint *write* error is best-effort and never fails an otherwise-healthy audit, but recovery distinguishes pre-publication preservation from post-publication artifact state; a checkpoint *read* failure fails closed to a fresh sampler.

**Presentation.** The console names, at resume, which pass it is resuming at and how many findings carry forward, and at decline, why (identity mismatch versus malformed). The final report records that the audit was resumed as **provenance only** — it must live outside `qualified_result` and `audit_coverage`, both of which match an uninterrupted run over the same declared inputs and replies.

**Run-log provenance reuses the existing events** — `run_log.CheckpointSave` / `CheckpointHit` / `CheckpointDiscard`, whose `name` / `input_hash` / `payload_bytes` / `reason` fields already fit, as `create.py` demonstrates. A matching resume emits one `CheckpointHit`; continuing boundaries emit saves and terminal cleanup emits discard. No new event type and no new `DATA_CONTRACT.md` run-log row. A run log is open **only** on the `--iterate` path today (`cli/completeness_cmd.py:cmd_completeness` starts one under `if budget.enabled`), so the events ride that path; the audit-only path does not gain a run log, and its resume is visible through the console and report instead.

### In scope

`plan_tool/review.py` (`audit_plan_until_stable`'s state, pass loop, resume detection, and terminal invalidation); `plan_tool/review_persistence.py` (the in-progress role, its schema/version policy, and its read/write helpers); `plan_tool/data_contract.py` (the new conditionally persisted `SavedReview` field's registry entry); `plan_tool/backend.py` (one additive field exposing the already-resolved model as data — no resolution-logic change); `plan_tool/completeness_report.py`, `plan_tool/convergence_diagnosis.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/cli/data_contract_cmd.py`, `plan_tool/cli/completeness_phases.py`, `plan_tool/cli/completeness_cmd.py` (the current reader-invariant verification and the resume presentation/wiring); `plan_tool/prompts/plan-audit.md` (the declared template fingerprint); `DATA_CONTRACT.md` (§ "Saved review sidecar" and § "Checkpoint-role policy"); `docs/how-to/pipeline/audit.md` (§ "Pre-apply checkpoint vs. final report — the persisted role", § "Saved audit evidence ledger — visible artifacts, not a decision") and `docs/how-to/recovery/audit.md` (§ "Crash / interrupt recovery" — the operator-facing home for resume, an elaboration of #279's "`docs/how-to/pipeline/audit.md`" within the same doc responsibility); and `tests/`.

**Not** `plan_tool/checkpoint.py`, `plan_tool/run_log.py`, or `plan_tool/fingerprint.py` — each is consumed as-is. `plan_tool/backend.py` is a narrow exception: it gains one additive field that exposes the already-computed resolved model as data (§ "Resume identity" above); no resolution logic changes.

## Input

This plan consumes several existing contracts as-is:

- **`SavedReview.is_pre_apply_checkpoint`** (`plan_tool/review_persistence.py:SavedReview.is_pre_apply_checkpoint`) — the three-state checkpoint role, normalized on load by `_normalize_checkpoint_role` and documented in `DATA_CONTRACT.md` § "Checkpoint-role policy". The unknown role is produced by no fresh writer; it is a malformed or version-mismatched marker on load, preserved as such by `update_annotation`. The new sampler-state field follows the same conditionally persisted contract and is distinct from `audit_coverage`.
- **`review_persistence.AuditInputSnapshot`**, its `.fingerprint`, `.revision`, and `.matches_disk`, and `review_persistence._audit_input_fingerprint` — the exact-input capture over plan bytes, every selected-grade detail artifact and its resolution/state, `source_seed` bytes, project-context digest, and `detail_grade`.
- **`fingerprint.compute_code_fingerprint`** — the declared-code fingerprint, consumed unchanged. Step 3 includes `plan_tool/prompts/plan-audit.md` in that declared surface because it is direct fixed audit input; this remains intentionally narrower than a repository-wide snapshot.
- **`completeness_report.resolve_reusable_audit`**, which returns `fresh=audit_revision_match` and computes `code_match` only to word the staleness message (`plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse`, the `if not ru.fresh:` arm) — so a code-only change leaves a saved audit reusable today.
- **`plan_tool/checkpoint.py`** — `compute_input_hash` / `load_if_valid` / `discard_checkpoint`, the hash-gated resume precedent whose shape is followed; the module itself is not modified.
- **`run_log.CheckpointSave` / `CheckpointHit` / `CheckpointDiscard`** — their `name` / `input_hash` / `payload_bytes` / `reason` fields, already driven by `plan_tool/create.py`; reused verbatim with no new event type.
- **`review_persistence.plan_reports_dir`**, `fileio.durable_write_text`, and `save_review`'s `Recommendation` serialization (`dataclasses.asdict` / `review.recommendation_from_persisted_mapping`). The writer follows the existing reports-directory creation convention before its first durable write.
- **The sampler's own constants and state** — `AUDIT_DEFAULT_MAX_PASSES = 3`, `CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT_S = 1800.0` (`plan_tool/cli/completeness_phases.py`), `build_low_impact_demotion_lookup(repo_root)` / `telemetry_analysis.LowImpactDemotionLookup` (built at `:8207`), and `budget_report`'s `budget_limited` / `confirmation_kind` computation (`:8434`–`:8486`).
- **The selected sampler** — `backend.build_effective_backend`'s selected backend and resolved model. Resume records those chosen values only; project argv overrides, rate-limit policy, timeout, retries, and provider outcomes remain existing execution behavior rather than new resume-identity axes.
- **The two production call sites** — `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` (call at `:2401`, driven from `plan_tool/cli/completeness_cmd.py:cmd_completeness`) and the inline call inside `_run_iterate_convergence_loop` (`:3133`). A run log is open only on the `--iterate` path (`cmd_completeness` starts one under `if budget.enabled`).

## References

- [os — Miscellaneous operating system interfaces (Python 3 Standard Library)https: — Reference for os.replace() and os.fsync(), the primitives behind durable_write_text's atomic single-file replacement, which the in-progress checkpoint relies on so an interrupted write can never leave a partial payload on disk.
- [tempfile — Generate temporary files and directorieshttps: — Documents mkstemp/NamedTemporaryFile for staging a fully written temp file in the reports directory before the atomic rename, the standard shape for replacing a stable-named checkpoint in place.
- [json — JSON encoder and decoderhttps: — Covers dumps/loads and JSONDecodeError, needed for the checkpoint's serialized payload and for the read-side fail-closed posture on truncated or undecodable files.
- [dataclasses — Data Classeshttps: — Reference for asdict() and field semantics, which govern the Recommendation round trip the checkpoint reuses when persisting and restoring the by_id finding union.
- [hashlib — Secure hashes and message digestshttps: — Documents the digest constructors used to compute the recorded sampler identity (audit-input and code fingerprints), whose byte equality is the sole gate licensing a resume.
- [Built-in Exceptions — the exception hierarchyhttps: — Defines why KeyboardInterrupt derives from BaseException rather than Exception, the distinction that separates a simulated interruption from an errored pass caught by check_plan_audit's except Exception handler.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Detaching, killing, or otherwise controlling a live backend call, and checkpointing a partial model reply. The pass boundary is the finest unit this effort claims; inside-a-call granularity is `BACKLOG.md` #124.
- Changing finding severity, union, or confirmation semantics in any way.
- Treating a checkpoint as final evidence anywhere, or relaxing any current reader's fail-closed posture.
- Extending the mechanism to `detail`, `run`, the per-step purity scan, the reconcile lanes (`reconcile-plan` / `reconcile-code`), the roadmap stage loop, or any other non-conceptual audit surface.
- Automatic resumption after input or configuration drift, and any prompt offering to resume anyway.
- Any new CLI flag. Resume is unconditional when identity matches; there is no `--resume-audit` / `--no-resume-audit` surface in this effort.
- A global repository snapshot, or automatic decline on code the auditor may inspect outside this plan's declared code and prompt surface.
- Changing the existing precedence or behavior of `--reuse-audit`, `--reuse-audit-id`, or default reusable-final selection.
- Retaining a terminal sampler result across a process stop or final-presentation failure after the sampler returns.
- Any new key in the `completeness-audit --json` payload (`DATA_CONTRACT.md` § "`completeness-audit --json`").
- Concurrency between two simultaneous audits of the same plan. The audit-only path holds no iteration lock, and `checkpoint.py`'s existing posture ("undefined behaviour; don't run plan-tool concurrently against the same plan") stands. Atomic single-file replacement plus the identity gate mean the worst case is a declined resume, not a corrupted union.
- Migrating, backfilling, or garbage-collecting historical report artifacts.
- Correcting the pre-existing stale claims listed in § Deferred.

## Risks

- **A named current reader accepts a sampler-lifecycle artifact as final.** The expensive failure: a partial union or terminal residue enters `--reuse-audit`, `completeness-apply`, or convergence history and reads as converged evidence. Mitigated structurally rather than by diligence — the artifact fails the single ordinary-final predicate all seven current gating sites share, and sits outside the `-completeness.json` filename namespace. The parametrized reader test pins those current sites; a future reader must add its own role test.
- **A resumed run's coverage verdict diverges from an uninterrupted one's.** `confirmation_kind` / `budget_limited` depend on four counters and three streak flags; the arm-clustering advisory depends on the per-id observation history; materiality depends on a calibration read from moving repo telemetry. Any one omitted from the payload produces a quietly different verdict. Mitigated by the equivalence test, which compares the whole coverage record and the advisory, not just the finding count.
- **Resume mixes findings under a changed declared input.** Mitigated by the captured plan/detail/context revision, declared-code fingerprint (including the audit template), sampler parameters, and selected backend/model. This is deliberately not a repository-wide guarantee: unrelated mutable code remains outside the recovery fence and calls for a fresh audit when it matters.
- **A write error is treated as proof that the prior recovery boundary survived.** The existing durable writer can report an error after its replacement is visible, so that inference is false. Mitigated by distinguishing pre-publication failure from post-publication error and having a later fresh-sampling invocation decide from the valid artifact and its role; it never invents a stronger crash-durability or total-work guarantee.
- **A malformed checkpoint is trusted.** Mitigated by the read-side fail-closed posture and by testing truncation, an undecodable `Recommendation` payload, and a future schema version — each must start a fresh sampler without raising.
- **Interaction with the existing pre-apply checkpoint.** Both artifacts can exist for one plan in one `--iterate` run, seconds apart, in the same directory whose stems `completeness_report._reserve_report_timestamp` reserves. A single stable-named in-progress artifact replaced in place — O(1) artifacts per audit, not O(passes) — keeps it out of that reservation and keeps the ledger from filling with partial rows.
- **Existing sampler tests change behavior.** Resume is on by default inside `audit_plan_until_stable`, so any test that runs two identical samplers against one `tmp_path` will now legitimately resume and spend fewer calls. A red sibling test here is the expected outcome of a class-wide change, not a reason to narrow the fix: read each one and decide whether it is a carve-out to assert or a stale expectation to update.

## Testing

Properties, each proved by mutating one thing and watching the outcome change. The fake seam is `tests/test_review.py:TestAuditPlanUntilStable._sampling_invoker` (a queued canned reply per call); interruption is simulated by raising a `BaseException` such as `KeyboardInterrupt` — an ordinary `Exception` is swallowed by `check_plan_audit`'s `except Exception` handler and recorded as an *errored pass*, which is a different property. `TestPlanAuditPassConformance::test_audit_plan_until_stable_pass_errored_counts_as_failed` is the precedent for the errored-pass arm; `tests/cli/test_completeness_cmd.py::test_pre_apply_checkpoint_sidecar_is_marked_and_v4` and `test_iterate_loop_writes_pre_apply_checkpoint` are the precedents for role/ordering assertions at the CLI layer.

- **Union preserved, next pass resumed.** Interrupt during pass 3 of 3 after passes 1–2 successfully persist: the checkpoint holds exactly their union, and a second fresh-sampling invocation spends exactly one logical pass, whose prompt carries the pass-1+2 findings in its convergence-guidance block.
- **In-flight pass retried, never completed.** No finding from the interrupted pass's partial state is unioned, and the resumed run's `passes_used` matches the uninterrupted baseline.
- **Cap is a logical sampler-pass budget.** A successful durable-resume chain for a `max_passes=3` audit never sums to more than three completed or errored sampler slots. A missing-heading repair remains inside the triggering slot and gets no checkpoint or independent budget.
- **Nonterminal errored pass still checkpoints.** A non-zero-exit pass that will continue advances `passes` and `failed_or_malformed_pass_count`; a resume after it does not re-spend its slot.
- **First write has a directory; write-error phases are distinct.** Starting a first bare audit with no reports directory still reaches the stable checkpoint write after the writer creates its parent. An `OSError` preserves the best-effort audit outcome. A forced pre-publication failure plus interruption restores only the prior durable prefix and reruns the unsaved pass; a forced post-publication error makes a later fresh-sampling invocation use the replacement's valid role rather than assume the prior prefix remains.
- **Decline matrix, one mutation at a time.** Each of plan bytes, one detail file's bytes, `source_seed` bytes, project context, declared code (including `plan_tool/prompts/plan-audit.md`), detail grade, `max_passes`, `dry_rounds`, `new_threshold`, and selected backend/model mutated *alone* starts a fresh sampler at pass 1 with the full logical-pass budget. This proves the declared recovery fence; it does not claim that unrelated repository code or execution policy is fingerprinted.
- **Malformed fails closed.** Truncated JSON, an undecodable persisted `Recommendation`, and an unsupported schema version each start a fresh sampler and raise nothing.
- **Sampler state is separate and registered.** An in-progress `SavedReview` round-trips its required sampler payload through its own conditionally persisted field; extending that dataclass keeps the `plan_tool/data_contract.py` registry and its field-for-field drift test current.
- **A new-state marker never falls through the legacy default.** Writing the checkpoint's chosen encoding at its chosen schema version, then loading it through `_normalize_checkpoint_role` unchanged, must not return `False` (ordinary final) — pin this against the literal legacy fallback so choosing "a new role value at a new schema version" without registering that version is a failing test, not a silent miss.
- **Reader rejection, parametrized over the current reader set** — one table covering `is_reusable_audit_sidecar` / `resolve_reusable_audit`, `_saved_audit_revision_is_current`, `_direct_walk_role_ineligibility`, `_review_reuse_ineligibility`, `_is_final_report_role` / `load_report_history`, both `data_contract_cmd` gates, and the evidence-ledger classifier. The ledger row is proven to exist through its normal checkpoint-aware loading path — the sampler artifact's stable filename is discovered as a standalone entry despite sitting outside the `-completeness.{json,md}` pairing the other two states use — and additionally asserts each lifecycle is named correctly rather than reported as a pre-apply checkpoint or as malformed.
- **Equivalence with an uninterrupted run.** Over one canned reply sequence and the same declared identity, an uninterrupted run and an interrupted-then-resumed run produce identical finding ids and order, identical per-id materiality, identical `audit_coverage` (`passes_used`, `cap`, `budget_limited`, `confirmation_kind`, `conforming_pass_count`, `failed_or_malformed_pass_count`, `early_stop_reason`), identical `qualified_result`, and an identical arm-clustering advisory.
- **Frozen calibration survives the interruption.** Mutating the repo's calibration evidence between the two invocations does not change the resumed run's materiality for carried *or* newly-found findings.
- **Terminal transition and cleanup are distinct.** For each dry-streak stop, cap stop, and plan-quota early stop, the ordinary resumable write is suppressed. A published transition plus successful cleanup leaves no checkpoint; a published transition plus forced cleanup failure leaves residue a later fresh-sampling invocation declines. A forced terminal-transition failure before publication restores only the prior durable pass boundary and re-runs the terminal pass; a post-publication error follows the terminal artifact's non-resumable role. Neither path treats a prefix as final.
- **Asymmetric failure posture.** A write that raises `OSError` leaves the audit completing exactly as today; pre-publication failure creates no new recovery boundary, while a post-publication error is resolved from the persisted artifact's role. A read that raises leaves a fresh sampler; a terminal-cleanup `OSError` is logged and swallowed only after the non-resumable transition is published.
- **Both call sites and existing reuse.** The audit-only path and the `--iterate` path both resume identically when they take fresh sampling. A reusable ordinary final audit retains current precedence and skips the sampler as it does today.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A conceptual audit interrupted after N successfully persisted passes retains exactly those passes' union, materiality, and observations, and a matching later fresh-sampling invocation resumes at pass N+1 rather than re-running any durable pass.
- An interruption during a pass causes that pass — and only that pass — to be re-run.
- Resume happens only on exact equality of the recorded sampler identity: audit-input revision, declared code fingerprint (including the audit template), `max_passes`, `dry_rounds`, `new_threshold`, and selected backend/model. Any single mismatch, a malformed payload, or an unreadable file starts fresh sampling at pass 1 and says why. Unrelated repository code and execution policy are outside this recovery fence.
- A terminal path suppresses the ordinary resumable write. If an existing checkpoint is present, a published non-resumable transition makes cleanup residue non-resumable, never final or reusable evidence; a cleanup failure is logged and never crashes an otherwise-successful audit. A terminal-transition failure before publication may resume the prior durable prefix to re-run the terminal pass; a post-publication error is resolved from the artifact role rather than treated as preservation of that prefix. Whichever schema encoding the checkpoint role uses, loading it through `_normalize_checkpoint_role` never returns the ordinary-final role.
- A first bare audit creates the reports directory before its in-progress checkpoint write. Setup or write errors remain best-effort and do not fail an otherwise healthy audit: a pre-publication error retains the prior boundary, while later recovery after a post-publication error follows the valid artifact's role.
- A resumed audit that reaches an ordinary terminal result produces the same finding union, the same per-id materiality, the same `audit_coverage` record, the same `qualified_result`, and the same arm-clustering advisory as an uninterrupted run over the same declared identity and replies.
- The checkpoint stores its sampler state in a separately registered conditionally persisted `SavedReview` field, never in the exact-shape `audit_coverage` record or the public JSON result.
- No sampler-lifecycle artifact is accepted as final or reusable evidence by the current `--reuse-audit`, `--reuse-audit-id`, `completeness-apply`, direct saved-review walk, review reuse, `data-contract-apply`, or convergence-history readers; the audit-evidence ledger names it as in-progress or terminal residue rather than as a pre-apply checkpoint or as malformed.
- A completed sampler whose terminal transition is published leaves no resumable in-progress checkpoint: successful cleanup leaves none, and failed cleanup leaves only non-final residue that cannot return to sampling. A terminal-transition failure before publication follows the prior-boundary rule; a post-publication error follows the artifact role. A multi-pass audit leaves at most one in-progress artifact on disk at a time.
- An interrupted-and-resumed successful durable chain completes no more than `max_passes` logical sampler passes in total. A bounded heading repair is part of its triggering pass, not a separately checkpointed pass.
- Existing reusable-final selection keeps its precedence: it skips fresh sampling rather than changing behavior to resume a checkpoint.
- Finding severity, union, confirmation, blocking, continuation, and exit-code behavior are unchanged, and `completeness-audit --json`'s payload gains no key.
- `DATA_CONTRACT.md` § "Checkpoint-role policy" documents both sampler lifecycle states with their eligibility and exit paths; `docs/how-to/pipeline/audit.md` and `docs/how-to/recovery/audit.md` describe resume, decline, and discard for an operator.
- `BACKLOG.md` #279 remains marked plan-authored while execution is pending, then is removed once fully shipped or updated with any deferred follow-up.

## Deferred

- Pass-level or unit-level resume for `detail` authoring, `run` steps, the per-step purity scan, the reconcile lanes, or the roadmap stage loop. Each has a different natural boundary and a different evidence contract; validate this one under forced interruption first.
- Checkpointing *inside* a single backend call — `BACKLOG.md` #124's territory, and explicitly a different problem from persisting between complete calls.
- A `--resume-audit` / `--no-resume-audit` operator flag, if a case appears where declining an identity-valid resume matters.
- Surfacing resume state in `completeness-audit --json`, if a CI consumer needs it.
- A repository-wide audit-input snapshot or a policy for unrelated files an auditor may inspect. This plan keeps the declared code-and-prompt surface as its recovery fence.
- Reordering reusable-final selection and in-progress resume, or retaining terminal sampler output through final-presentation failure. Neither is needed to prove interrupted pass recovery.
- **Two pre-existing stale claims found while grounding this seed — file in `BUG_BACKLOG.md`, do not fix here.** `docs/how-to/recovery/audit.md` § TL;DR and the `--reuse-audit` help text in `cli/completeness_cmd.py` both state that reuse requires "both the saved plan fingerprint AND code fingerprint" to match. `completeness_report.resolve_reusable_audit` returns `fresh=audit_revision_match` and uses `code_match` only to word the staleness message, so a code-only change leaves a saved audit reusable. This seed deliberately does not repeat the claim, and this effort's resume gate does not inherit the behavior.
