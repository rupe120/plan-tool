> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document sampler resume, decline, and discard in the audit flow

## Summary

Document the completed sampler-checkpoint behavior in `docs/how-to/pipeline/audit.md` and `docs/how-to/recovery/audit.md`, then retire or accurately restate `BACKLOG.md` #279. Keep the concise audit workflow separate from the detailed recovery decision flow. The key decision is that only a matching nonterminal conceptual-audit checkpoint resumes; every declined or terminal artifact remains non-final evidence. Green means an operator can tell when an audit resumes, starts fresh, or leaves diagnostic-only residue.

## Table of Contents

- [Summary](#summary) — The completed documentation outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the recovery contract needs one clear operator explanation.
- [Input](#input) — Upstream checkpoint, resume, ledger, and provenance contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation and tracking edits.
- [Implementation](#implementation) — Required resume, decline, discard, and evidence wording.
- [Tests](#tests) — Documentation-focused verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Scope and evidence boundaries that constrain the wording.
- [Deferred](#deferred) — Related recovery work outside this documentation step.

## Why

`docs/how-to/pipeline/audit.md` currently explains the pre-apply checkpoint, while `docs/how-to/recovery/audit.md` explains final-audit reuse and crash recovery, but neither gives an operator the completed pass-level sampler contract from steps 1–5. Without that distinction, an in-progress sampler checkpoint can look like reusable final evidence or an unexplained leftover. These edits make the recovery boundary understandable without changing audit behavior or widening it beyond conceptual sampling.

## Input

- **Sampler persistence and resume** — Steps 1–3 provide the stable nonterminal sampler checkpoint, exact-match resume decision, and fresh-sampler decline path. Read the landed `plan_tool/review.py:audit_plan_until_stable` behavior and persistence API before naming them; landed code wins over earlier detail wording.

- **Terminal handling** — Step 2 provides the terminal transition and cleanup rule. Document the published `terminal-residue` lifecycle as the recovery fact after a terminal-path error.

- **Ledger and presentation** — Step 4 provides the `in-progress-checkpoint` and `terminal-sampler-residue` ledger states, and step 5 provides positive-only human resume provenance. Keep the ledger’s diagnostic states separate from the final report’s provenance note.

- **Existing checkpoint contract** — Preserve the separate apply-phase checkpoint owned by `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` and the persisted role normalization in `plan_tool/review_persistence.py:_normalize_checkpoint_role`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `docs/how-to/pipeline/audit.md` — Add the sampler checkpoint to the high-level audit path, saved-evidence ledger, non-final-reader boundary, and source map without conflating it with the pre-apply checkpoint.
  - `docs/how-to/recovery/audit.md` — Make this the detailed operator reference for matching resume, safe decline, terminal invalidation, cleanup residue, and source anchors.
  - `BACKLOG.md` — Remove #279 once all six plan steps are complete, or replace its pending status with the specific remaining follow-up if the full plan cannot ship.

## Implementation

- **Foundational logic: identity-gated sampler checkpoint recovery.** Document that `plan_tool/review.py:audit_plan_until_stable` resumes only a completed continuing-pass boundary and starts at the next un-run logical pass. An interruption inside a pass must retry that pass rather than count it as complete.

- **Give each flow document one job.** Keep `docs/how-to/pipeline/audit.md` concise: update `## High-level flow`, `### Saved audit evidence ledger — visible artifacts, not a decision`, `### Pre-apply checkpoint vs. final report — the persisted role`, and `## Source map`. Put the full resume/decline/discard decision sequence in `docs/how-to/recovery/audit.md`, linked from the concise flow rather than repeated in both files.

- **Describe the resume gate precisely.** In `docs/how-to/recovery/audit.md`, state that a fresh conceptual sampling path resumes only when the nonterminal sampler artifact and its declared audit identity match. The explanation must cover the captured audit inputs, declared code input, audit stage and detail grade, selected backend/model, and sampler settings without inventing a new operator choice.

- **Preserve reusable-final precedence.** Explain that `plan_tool/completeness_report.py:resolve_reusable_audit` and `is_reusable_audit_sidecar` retain their existing final-evidence selection. A sampler checkpoint is considered only when the command reaches fresh conceptual sampling; it must not reorder or weaken reusable-final selection.

- **Make decline fail closed.** State that a missing, unreadable, malformed, nonterminal-invalid, stale, or differently configured sampler checkpoint starts a fresh pass-1 sampler. It must not carry any prior union forward, prompt the operator to override the result, or gain a resume-provenance marker. The declined artifact remains diagnostic evidence until later lifecycle handling replaces or retires it.

- **Explain terminal discard as a lifecycle, not a final result.** Document that every terminal sampler result first publishes the non-resumable `terminal-residue` lifecycle before cleanup. A failure before that publication preserves the prior durable boundary; after publication, any cleanup residue stays diagnostic-only and cannot resume, reuse, apply, walk, or enter convergence history.

- **Keep the non-final artifacts distinct.** In `docs/how-to/pipeline/audit.md`, retain the existing pre-apply checkpoint as apply-phase recovery evidence and add the step-4 sampler ledger states for resumable progress and terminal residue. Do not add a new final-evidence role or imply that any artifact is an ordinary final.

- **Update the reader boundary and source maps.** Keep `plan_tool/convergence_diagnosis.py:load_audit_evidence_ledger` visible as diagnostic discovery, and keep `plan_tool/convergence_diagnosis.py:load_report_history`, `plan_tool/completeness_report.py:resolve_reusable_audit`, and `plan_tool/cli/review_cmd.py:cmd_review_walk` final-only. Add source-map entries for the landed sampler persistence and resume anchors while leaving the existing `write_pre_apply_audit_checkpoint` entry separate.

- **Retire the backlog entry accurately.** Remove only the complete #279 entry after confirming steps 1–6 meet the plan’s acceptance criteria. If a scoped follow-up remains, keep the entry with a current status and explicit tracker rather than claiming the work shipped; do not alter adjacent backlog entries.

- **Leave parallel recovery docs alone.** Keep `docs/how-to/recovery/README.md` and `docs/how-to/recovery/create.md` unchanged because they own shared session mechanics and create-specific recovery, not conceptual sampler behavior.

## Tests

No test file is in this non-code step’s declared scope. Use the landed implementation tests as documentation evidence, then perform the artifact checks below.

### Verification (non-code step)

- `tests/test_review.py:TestAuditPlanUntilStable` — Confirm the documented completed-pass, next-pass resume, declined-resume, and terminal behavior matches the landed sampler tests.

- `tests/test_review_persistence.py` — Confirm the documented non-final artifact wording matches the landed saved-review role and sampler-payload tests.

- `verify_audit_flow_checkpoint_distinction` — Confirm `docs/how-to/pipeline/audit.md` names pre-apply and in-progress sampler checkpoints as separate artifacts with separate purposes.

- `verify_resume_decline_discard_paths` — Confirm `docs/how-to/recovery/audit.md` states the matching-resume, fresh-decline, pre-publication-failure, post-publication-residue, and cleanup outcomes.

- `verify_final_evidence_boundary` — Confirm neither flow document describes an in-progress sampler checkpoint as reusable, applicable, walkable, historical convergence evidence, or a qualified final result.

- `verify_links_and_source_anchors` — Check intra-document links, cross-document links, and every cited source-map path and symbol against the landed tree.

- `verify_backlog_279_status` — Confirm #279 is removed only after the complete plan ships, or otherwise reports the real remaining work.

## Acceptance criteria

- `docs/how-to/pipeline/audit.md` distinguishes the sampler’s in-progress and terminal-residue ledger rows from the existing pre-apply checkpoint.

- `docs/how-to/recovery/audit.md` states that an exact identity match resumes at the next un-run conceptual pass without a new CLI flag or prompt.

- `docs/how-to/recovery/audit.md` states that a declined checkpoint starts a fresh sampler and cannot mix old findings into the new union.

- Both flow documents state that terminal checkpoint cleanup residue is non-resumable, non-final diagnostic evidence.

- Both flow documents preserve ordinary-final-only reuse, apply, direct-walk, and convergence-history boundaries.

- Each added source-map reference resolves to a landed path and symbolic anchor.

- `BACKLOG.md` #279 no longer reports pending plan-authored work after all six steps ship, or names the specific remaining follow-up.

## Applicable guardrails

- **Recovery boundary — the plan’s `## Plan intent`.** Document only completed conceptual-audit pass boundaries; this step must not imply recovery inside a backend call.

- **Surface limits — the plan’s `## Out of scope`.** Do not document a new resume flag, operator override, or equivalent behavior for another execution lane.

- **Evidence boundary — the plan’s `## Out of scope`.** The wording must preserve every current reader’s non-final treatment of sampler checkpoints.

- **Public output boundary — the plan’s `## Out of scope`.** Do not imply that resume information changes the `completeness-audit --json` contract.

## Deferred

- **Reusable-final freshness wording outside the sampler contract** — Leave it untouched in this step; the plan’s `## Deferred` owns that separate issue.

- **Shared and create-specific recovery documentation** — Leave `docs/how-to/recovery/README.md` and `docs/how-to/recovery/create.md` unchanged because they do not own conceptual sampler recovery.
