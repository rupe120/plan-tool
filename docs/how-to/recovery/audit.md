# `completeness-audit` / `reconcile` resume & recovery

Detailed operator resume/recovery reference for the completeness convergence
loop, `plan-tool completeness-audit <name> --iterate`. The shared machinery
(iteration session, crash handler) is in [`RESUME_FLOW.md`](README.md); the happy path is in
[`AUDIT_FLOW.md`](../pipeline/audit.md).

## TL;DR

- **Deterministic findings re-derive from disk every run.** The
  well-formedness battery (file-check, deps, body/detail coverage) is recomputed
  from the **on-disk plan** every invocation — never cached, never gated by reuse.
  Re-running naturally continues: findings already resolved (the apply edits are
  durable on disk) don't reappear, so the loop just works through what's left.
- **An ordinary final conceptual audit is reused across runs when fresh.** A saved
  `-completeness.json` sidecar's conceptual findings are substituted for a fresh
  Claude audit when **both** the saved **plan fingerprint AND code fingerprint**
  still match current disk; any mismatch re-audits with Claude. Reuse is operator-gated
  by `--reuse-audit` / `--no-reuse-audit` / `--reuse-audit-id` (unset = prompt);
  the deterministic battery above runs on every invocation regardless. This
  ordinary-final selection runs before sampler recovery; a sampler checkpoint
  never competes with it.
- **A fresh conceptual sampler resumes only one exact continuing boundary.**
  `audit_plan_until_stable` restores an `in-progress` sampler checkpoint and
  starts at its next un-run logical pass only when every declared identity input
  matches. There is no resume flag or override prompt. A pass interrupted
  before its boundary is saved is retried, never counted as complete.
- **A declined sampler checkpoint starts a fresh pass-1 union.** A missing,
  unreadable, malformed, terminal, stale, or differently configured checkpoint
  remains diagnostic evidence; it contributes no carried findings and renders
  no resume-provenance note.
- **Terminal sampler handling publishes non-resumable state before cleanup.**
  For an existing sampler checkpoint, a terminal result first publishes
  `terminal-residue`; a failure before that publication preserves the prior
  recovery boundary. Once publication succeeds, a cleanup failure can leave
  only diagnostic residue that cannot resume, reuse, apply, walk, or enter
  convergence history.
- **An `--iterate` run saves a pre-apply checkpoint, and it is recovery
  evidence — not a reusable audit.** Before the first `apply_finding`,
  `write_pre_apply_audit_checkpoint` persists the finished conceptual audit
  under the ordinary `<ts>-completeness` names, marked
  `is_pre_apply_checkpoint` at schema version 4. Only an **ordinary final**
  sidecar — an unmarked version-1/2 legacy save or a role-aware version-3/4
  `false` record — is eligible for reuse and convergence history; every
  non-final checkpoint and any unknown role fail closed on both.
- **This is the in-place continuation path** for a `create` or `detail` run that
  crashed or aborted with open findings. Unlike re-running `create`, it operates
  on the existing plan and does **not** rebuild the body from a seed — applied
  edits are preserved.
- **A crash preserves its last durable boundary.** The loop runs inside
  `iteration_session`; plan edits remain on disk, a completed continuing pass
  remains resumable when its checkpoint was saved, and an in-flight pass leaves
  the prior boundary for a later retry.

## What's reused vs re-derived

The two finding layers have opposite caching postures:

- **Deterministic findings — re-derived from disk every run, no cache.**
  file-check, deps, body/detail coverage
  (`plan_tool/review.py: collect_deterministic_findings`, CLI
  `_run_deterministic_checks`). The on-disk plan is the source of truth; a re-run
  sees only the findings still open. Reuse never gates this layer.
- **Conceptual audit — role-gated, then fingerprint-gated reuse from the saved
  sidecar.** The single-Claude-call audit (`plan_tool/review.py:
  check_plan_audit`, driven by `audit_plan_until_stable`) is the reusable axis.
  `plan_tool/completeness_report.py: resolve_reusable_audit` locates the newest
  **eligible** `-completeness.json` — eligibility is
  `is_reusable_audit_sidecar`: `kind="completeness"` **and** the ordinary-final
  role, decided from the loaded payload, so a filename/payload kind mismatch is
  rejected on the payload. It then recomputes `compute_plan_fingerprint`
  (`plan_tool/review_persistence.py`) and `compute_code_fingerprint`
  (`plan_tool/completeness_report.py`), and returns a `ReusableAudit` whose
  `fresh` is true only when **both** fingerprints match. On `fresh`, the CLI
  substitutes the saved conceptual recs for a fresh `audit_plan_until_stable`
  call; on any mismatch it declines and re-audits. A marked checkpoint or an
  unknown role is skipped before freshness is ever computed — it is not a stale
  verdict, it is not a candidate.

```
load plan from disk
        │
   ┌────▼─────────────────────────────────┐
   │ re-derive deterministic findings      │   ◄── always; source = on-disk plan
   │   (file-check, deps, body/detail      │
   │    coverage, ...)                     │
   └──────────────┬───────────────────────┘
                  │
        eligible sidecar? (kind="completeness" + ordinary-final role)
          AND fresh? (plan + code fingerprints both match)
          │                          │
          yes                        no
          │                          │
   reuse saved conceptual     run conceptual audit passes
   recs (no Claude call)      (audit_plan_until_stable → Claude)
          └────────────┬─────────────┘
                       │
      --iterate: write the pre-apply checkpoint  ◄── marked; recovery evidence,
                       │                             never a reusable audit
   triage → apply eligible findings   ◄── apply_finding edits plan in place
                       │
            should_continue? ── yes ──► loop
                       │ no
                       ▼
              save the final report   ◄── unmarked; the eligible artifact
```

Deterministic findings are recomputed from disk each run, so their "resume" is
implicit: a re-run sees only the findings still open. The conceptual axis instead
reuses the saved sidecar whenever it is an eligible final *and* both fingerprints
still match — the durable artifacts are the plan file itself and the
`-completeness.json` sidecars beside it, of which only the ordinary finals can be
reused.

## Sampler resume, decline, and discard

The sampler is a recovery path only after reusable-final selection has declined
and the command reaches fresh conceptual sampling. It never changes the
selection or freshness rules in `resolve_reusable_audit` /
`is_reusable_audit_sidecar`.

```
ordinary final selected and fresh?
        │
   yes  │  no
        │
reuse final evidence       enter fresh conceptual sampling
                                 │
                      load stable sampler sidecar
                                 │
              valid in-progress checkpoint with exact identity?
                       │                         │
                      yes                       no
                       │                         │
restore union and start at      start a new empty union at pass 1
next un-run pass                (leave declined artifact diagnostic-only)
                       │                         │
                       └───────── complete logical pass ─────────┘
                                             │
                        another pass needed? │ terminal result
                                │            │
                              yes            ▼
                                │   publish terminal-residue for any existing
replace stable in-progress      checkpoint, then attempt cleanup
boundary with the completed               │
union; interruption inside a        cleanup fails → diagnostic-only residue
later pass retries that pass
```

**Exact identity gate.** The sampler accepts only a readable, structurally
complete `in-progress` artifact. Its captured audit-input fingerprint binds the
plan and the selected-grade detail inputs, including the declared detail grade
and the bare/detail audit stage those inputs determine. Its declared code input
must match the current code fingerprint. Its sampler identity must also match
the pass cap, dry-round count, new-finding threshold, selected backend, and
resolved model. A missing code fingerprint, a changed input, a missing or
terminal lifecycle, malformed state, or any mismatch fails closed. No new CLI
choice exists: the fresh sampler starts at pass 1 with an empty union and cannot
mix the declined findings into it.

**Completed-pass boundary.** After a successfully parsed pass that will
continue, the sampler atomically replaces its stable sidecar with the union,
observations, counters, and `next_pass`. A stop during the next backend call has
not crossed another boundary, so the next invocation retries that logical pass
rather than recording it as complete. A successful resume adds a positive-only
`Audit provenance` note to the human report; it changes neither findings,
coverage, qualified result, nor the `completeness-audit --json` payload.

**Terminal transition and cleanup.** When a sampler result becomes terminal and
an earlier boundary exists, the sampler first publishes the same stable artifact
with lifecycle `terminal-residue`. A transition error that occurs before that
publication leaves the older `in-progress` boundary recoverable. Once the
terminal lifecycle is present, the sampler attempts to remove it. Successful
cleanup leaves no sampler artifact; a cleanup failure leaves
`terminal-sampler-residue` in the evidence ledger. That residue is
non-resumable and non-final: it cannot be reused, applied, directly walked, or
included in convergence history. Whether an existing checkpoint is present at
this point is itself a best-effort filesystem check: a failed check is treated
as "a checkpoint might be there" rather than "there is none," so it still
attempts the transition — a spurious attempt when nothing was actually there
is a harmless extra write, while treating unknown as absent could otherwise
leave a real resumable boundary un-transitioned for a later, unrelated
invocation to wrongly resume.

**A skipped pass never confirms convergence on a resumed checkpoint.** A pass
that samples nothing (no invoker configured, or the plan has no body to
audit) is scored like any other pass by default — but on a run that resumed a
genuine `in-progress` checkpoint, that would let a single skipped pass read as
an immediate dry-streak "confirmed" result, finalizing (and discarding, via
the terminal transition) a real earlier pass's carried findings under a false
convergence label. A skipped pass therefore degrades neutrally on a resumed
run, the same way an errored pass already does: it consumes a slot against
the cap but never advances the dry-streak count. A skipped pass on a *fresh*
run (nothing carried) is unaffected and keeps converging immediately, since
there is nothing it could wrongly discard.

## Refresh resume posture

`plan-tool reconcile-plan <name> --refresh` (the cheap fingerprint gate,
`plan_tool/refresh.py: refresh_plan`) has a far simpler resume story than the
completeness loop above — it is a single scoped reconcile, **not** a loop.

- **The grounding baseline is the durable state.** `--refresh` diffs the plan's
  tracked grounding sidecar (`<plan-dir>/plan-details/<slug>/grounding.json`,
  written by `plan_tool/grounding.py: write_grounding`) against a freshly
  recomputed code fingerprint. The sidecar is on disk (and committed), so it
  survives a crash; the code fingerprint is re-derived from disk every run, never
  cached — mirroring the *What's reused vs re-derived* posture above.
- **No-drift refresh is a zero-Claude no-op that rewrites nothing.** When the
  baseline still matches, `refresh_plan` returns having spawned no invoker and
  left the sidecar byte-identical, so its "resume" is trivial: there is nothing to
  continue. Only the drift / no-baseline branches reconcile and re-stamp.
- **The refresh path is *not* wrapped in `iteration_session`.** Unlike the
  completeness loop, `--refresh` runs a single scoped reconcile
  with no convergence loop and no in-run drift lock, so it sits outside the
  `iteration_session` machinery entirely. A crash mid-reconcile leaves the saved
  findings (if any) on disk and the baseline un-stamped; re-running `--refresh`
  simply re-detects the same drift and reconciles again.

## Detail reconciliation is a separate scoped walk

`plan-tool detail <name> --reconcile` runs one pre-execution audit and may walk
its saved findings; it has no iteration loop or iteration-session recovery
contract. After interruption, inspect saved findings and on-disk edits, judge
what remains, and commit corrections before a new invocation. Do not infer
completeness sampler/checkpoint recovery from this route's saved review.

## Crash / interrupt recovery

- The completeness loop wraps its body in `iteration_session`, so Ctrl-C or an unexpected
  exception still restores the SIGINT handler and emits any live-edit drift
  warning on the way out.
- An unexpected exception propagates to `main()`'s crash handler (traceback file
  + clean message, exit `1`).
- Mid-`apply_finding` edits are written to disk immediately, so a crash leaves
  the plan partially advanced; the re-run re-derives and continues — already
  -applied findings drop out.
- **The pre-apply checkpoint survives the crash, and stays evidence.** It is
  written before the first apply, so a crash inside `apply_finding` cannot
  discard the conceptual pass that produced the edits. It remains readable
  through `load_review` for inspecting what the audit found. It does **not**
  become a reusable conceptual audit or a completed convergence snapshot: its
  findings predate the apply work, so both readers fail closed on the marked
  role.
- **A rapid final report never overwrites it.** When the checkpoint and the
  final report land in the same wall-clock second, `_reserve_report_timestamp`
  reserves the markdown, sidecar, and data-contract payload together and
  advances whole seconds until a free stem is found, so both artifacts persist
  under distinct canonical names — no suffix, no separate directory.
- **The re-run still re-derives deterministic findings from disk**, exactly as
  above; the checkpoint changes nothing about that layer.

- **Sampler state is separate from apply-phase recovery.** The stable sampler
  sidecar records completed conceptual passes before the sampler returns; the
  timestamped pre-apply checkpoint records a finished audit before iteration
  applies findings. Both are non-final evidence, but only a matching
  `in-progress` sampler lifecycle resumes sampling.

## Relationship to create / detail recovery

When a `create` run aborts with open findings (exit `3`) or either flow crashes,
the recommended continuation is `plan-tool completeness-audit <slug>` — it drives the
remaining findings down **in place** on the authored plan. This is why the
`create` FAILURE banner and the `main()` crash message both point here rather
than only at re-running `create` (which would rebuild the body from the seed and
discard applied edits — see [`CREATE_RESUME_FLOW.md`](create.md)).

## Source map

| Concern | File |
|---------|------|
| Completeness convergence loop | `plan_tool/cli/completeness_cmd.py` (`cmd_completeness`) |
| Internal reconcile iteration helper (not exposed as a CLI loop) | `plan_tool/cli/reconcile.py` (`_iterate_reconcile_loop`) |
| Finding re-derivation (no cache) | `plan_tool/review.py` (`collect_deterministic_findings`) |
| Conceptual-audit reuse verdict | `plan_tool/completeness_report.py` (`resolve_reusable_audit`, `is_reusable_audit_sidecar`, `ReusableAudit`) |
| Sampler resume gate and lifecycle transition | `plan_tool/review.py` (`audit_plan_until_stable`, `_restore_sampler_checkpoint_state`, `write_completed_sampler_boundary`, `_remove_sampler_checkpoint`) |
| Stable sampler persistence | `plan_tool/review_persistence.py` (`sampler_checkpoint_path`, `load_sampler_checkpoint`, `save_sampler_checkpoint`, `SavedReview.is_in_progress_sampler_checkpoint`) |
| Pre-apply checkpoint writer | `plan_tool/cli/completeness_phases.py` (`write_pre_apply_audit_checkpoint`) |
| Checkpoint role (persisted contract) | `plan_tool/review_persistence.py` (`SavedReview.is_pre_apply_checkpoint`, `_normalize_checkpoint_role`); policy in [`../DATA_CONTRACT.md`](../../../DATA_CONTRACT.md) § `SavedReview` |
| Same-second stem allocation | `plan_tool/completeness_report.py` (`_reserve_report_timestamp`, `_report_artifact_paths`) |
| Role-aware convergence history | `plan_tool/convergence_diagnosis.py` (`load_report_history`, `_is_final_report_role`) |
| Diagnostic sampler ledger | `plan_tool/convergence_diagnosis.py` (`load_audit_evidence_ledger`, `_sampler_checkpoint_evidence_state`) |
| Plan / code fingerprints | `plan_tool/review_persistence.py` (`compute_plan_fingerprint`), `plan_tool/completeness_report.py` (`compute_code_fingerprint`) |
| Reuse decision + code-drift warning (CLI) | `plan_tool/cli/completeness_cmd.py` (`_resolve_audit_reuse`, `_warn_code_drift`) |
| In-place apply | `plan_tool/launcher.py` (`apply_finding`) |
| Iteration session (drift + SIGINT cleanup) | `plan_tool/iteration_lock.py` (`iteration_session`) |
| Refresh entry point (no iteration session) | `plan_tool/refresh.py` (`refresh_plan`) |
| Grounding baseline (the refresh gate's durable state) | `plan_tool/grounding.py` (`read_grounding`, `write_grounding`, `check_grounding_drift`) |
| Shared engine | [`RESUME_FLOW.md`](README.md) |
| Tests | `tests/test_cli.py` |
