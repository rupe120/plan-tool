> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Preapply Audit Checkpoint Identity
intent: Ensure pre-apply audit checkpoints remain durable crash-recovery evidence
  without contaminating final-report convergence or audit reuse, while preserving
  compatibility.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a checkpoint role to saved reviews with safe legacy handling
  intent: Makes checkpoint identity durable while keeping unmarked historical sidecars
    readable with their legacy behavior.
  files:
  - plan_tool/review_persistence.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_review_persistence.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/preapply-audit-checkpoint-identity/01-checkpoint-role-saved-reviews-safe.md
  status: done
- id: 2
  title: Mark pre-apply checkpoint sidecars without changing their names
  intent: Keeps crash-recovery checkpoints on disk while identifying them separately
    from final reports.
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/preapply-audit-checkpoint-identity/02-mark-pre-apply-checkpoint-sidecars.md
  status: done
- id: 3
  title: Keep marked checkpoints out of reusable audit lookup
  intent: Prevents a partial checkpoint from being reused on the next completeness
    audit.
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/preapply-audit-checkpoint-identity/03-keep-marked-checkpoints-out-reusable.md
  status: done
- id: 4
  title: Keep marked checkpoints out of convergence history
  intent: Keeps convergence calculations based only on final report snapshots.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/preapply-audit-checkpoint-identity/04-keep-marked-checkpoints-out-convergence.md
  status: done
- id: 5
  title: Remove the manual newest-checkpoint drop from report rendering
  intent: Makes final-report convergence rendering rely on the shared history rule
    instead of guessing that the newest sidecar is a checkpoint.
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: low
  change_type: refactor
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/preapply-audit-checkpoint-identity/05-remove-manual-newest-checkpoint-drop.md
  status: done
- id: 6
  title: Document checkpoint roles and close the checkpoint identity handoff
  intent: Leaves operators and the next session with the final checkpoint policy,
    recovery behavior, and closure record.
  files:
  - docs/AUDIT_FLOW.md
  - docs/AUDIT_RESUME_FLOW.md
  - docs/cli/completeness-audit.md
  - BUG_BACKLOG.md
  - handoffs/2026-08-05-checkpoint-identity-session.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/preapply-audit-checkpoint-identity/06-document-checkpoint-roles-close.md
  status: done
- id: 7
  title: Keep unsafe sidecars out of reconcile-plan reuse
  intent: Prevents a partial or untrusted saved report from being automatically reused
    and walked by reconcile-plan.
  files:
  - plan_tool/cli/review_cmd.py
  - tests/cli/test_review_cmds.py
  - docs/cli/reconcile-plan.md
  - tests/cli/test_cli_reference.py
  - BUG_BACKLOG.md
  - handoffs/2026-08-05-checkpoint-identity-session.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 6
  detail: docs/implementation-plans/plan-details/preapply-audit-checkpoint-identity/07-keep-unsafe-sidecars-out-reconcile-plan.md
  status: done
---
# Preapply Audit Checkpoint Identity

## Overview

Add an additive persisted checkpoint-role marker so pre-apply completeness-audit checkpoints can be distinguished from final reports. Mark new checkpoints explicitly, keep them as crash recovery evidence, and exclude them from convergence history, reusable-audit selection, and `reconcile-plan` saved-review reuse. Preserve existing report naming and filename compatibility, and keep historical unmarked completeness sidecars loadable with legacy behavior.

## Problem statement

`write_pre_apply_audit_checkpoint` currently persists a normal completeness sidecar, making pre-apply checkpoints indistinguishable from final reports downstream. `load_report_history` counts a checkpoint as a full `RunSnapshot`, `resolve_reusable_audit` can choose it as the newest reusable audit, and `reconcile-plan` can reuse and walk its partial findings, creating the `BUG_BACKLOG` risk.

## Architecture

Extend persisted `SavedReview` with an additive `is_pre_apply_checkpoint`
boolean for `kind="completeness"` sidecars, carry its normalized role through
save/load/update_annotation, and document it in `DATA_CONTRACT`. The pre-apply
writer serializes version-3 `true`; final-report writers omit the optional key
so their existing payload shape remains compatible. Raw version-3 `false` and
an absent key in a version-1/2 sidecar mean an ordinary final artifact, with
absence preserving legacy behavior only in those legacy formats.

A present non-boolean marker, a marker on a non-completeness sidecar, a marker
in a version 1 or 2 sidecar, or a version 3 sidecar with an absent marker is an
unknown role: `load_review` remains able to inspect it, but convergence history,
reusable-audit selection, and `reconcile-plan` saved-review reuse fail closed by
excluding it. Versions 1 and 2 remain the legacy final-report formats and
accept unmarked sidecars with their current semantics. Version 3 is the
role-aware format: the checkpoint writer emits
`is_pre_apply_checkpoint: true` only in version 3, and a version 3 `false`
value is a readable ordinary final only for raw compatibility input, never a
supported final-writer output. Older role-unaware readers reject version 3
rather than silently treating a checkpoint as final; newer readers retain
version-1 and version-2 compatibility and reject unsupported future versions.
`DATA_CONTRACT` distinguishes this producer scope from an annotation rewrite:
when a loaded role is already unknown, `update_annotation` preserves that
unknown state even if the original malformed marker appeared outside a
version-3 completeness sidecar.
`write_pre_apply_audit_checkpoint` must explicitly write the version-3 marker;
readers in convergence history, reusable-audit selection, and plan-wide
saved-review reuse must recognize marked checkpoints and exclude them while
retaining the persisted artifact for crash recovery.

`write_completeness_report` owns collision-safe publication for every complete
report pair. Before writing Markdown, its sidecar, or any sibling
data-contract payload, it reserves one unused canonical whole-second
`<timestamp>-completeness` stem. If a prior complete-report artifact already
uses that stem, it advances the logical UTC timestamp by whole seconds until
the full artifact set has an unused stem, then passes that same timestamp to
both writers. Thus a checkpoint and its rapid final report retain distinct,
sortable existing-format names and matching persisted `created_at` values;
neither may overwrite recovery evidence. This serial in-process allocation is
not a new parallel-writer or filename-format feature.

For unpinned reusable-audit lookup, scan newest to oldest and select the newest
eligible final artifact after marked, unknown, or unloadable sidecars are
skipped. Eligible means both `SavedReview.kind="completeness"` and the
ordinary-final role; the existing `-completeness.json` filename filter is only
a locator, not evidence of payload kind. A pinned `review_id` is exact: a
marked, unknown, unloadable, or kind-mismatched requested sidecar is declined,
never silently replaced by an older final report. Historical unmarked
completeness sidecars remain loadable and eligible, without heuristic migration
or a bulk rewrite. Preserve report naming and existing filename compatibility.

`reconcile-plan` saved-review reuse accepts only a loaded `kind="review"`
sidecar whose normalized role is the ordinary final state. In unpinned
selection it scans newest to oldest, skipping unloadable, non-review, marked,
and unknown-role candidates; after it finds the newest eligible candidate, the
existing fingerprint freshness gate decides whether to reuse it and a stale
result starts a fresh review without scanning older reports. An exact pin is
never replaced by another sidecar: an unloadable or ineligible match declines
with an operator-facing reason, then starts fresh. This holds for the
interactive prompt, `--reuse`, `--yes`, and non-TTY entry paths. A non-TTY
reuse may select a safe sidecar, but it must skip the per-finding walk and
return without calling `input()`, just as a fresh non-TTY review does.

`reconcile-plan-walk` remains kind-agnostic and outside this step. Its direct
saved-artifact selection needs a separate contract because it replays
reconcile-family reports without a fresh-audit fallback and shares recovery
helpers with other consumers. `BUG_BACKLOG.md` keeps that remaining reader gap
open; do not describe step 7 as closing it.

This reader change does not alter `completeness-apply` or data-contract apply.
`data_contract_cmd._newest_saved_completeness_with_contract_payload` can inspect
a checkpoint while locating an applyable payload, but its per-finding freshness
verification rejects stale checkpoint evidence and directs the operator to run
a fresh audit. Keep that recovery path outside this reader-selection change.

`load_report_history` owns marked-sidecar exclusion for every convergence
consumer. Once it does, `_completeness_convergence_diagnosis` must remove its
`drop_checkpoint` argument and never slice the newest on-disk completeness
snapshot; it appends the one in-memory current final snapshot to the complete
role-filtered history.

## Input

This plan consumes persisted `SavedReview` completeness sidecars, including artifacts written by `write_pre_apply_audit_checkpoint` and read by `load_report_history`, `resolve_reusable_audit`, and `reconcile-plan` saved-review reuse. It relies on the existing save/load/update_annotation flow, `DATA_CONTRACT`, report naming, and existing filename compatibility; historical unmarked completeness sidecars must remain readable with legacy behavior.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Covers defaulted dataclass fields, which supports adding an additive legacy-safe marker to SavedReview.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Documents Python’s JSON parsing and serialization APIs used to persist, load, and validate the checkpoint-role field.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Defines the JSON object and value rules relevant to specifying malformed-marker handling in the persisted sidecar contract.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Shows the supported pytest pattern for a concise regression matrix covering marked, final, legacy, and malformed sidecars.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Renaming report sidecars or changing filename compatibility; the role marker must distinguish artifacts without disrupting existing paths.
- Migrating, rewriting, or deleting historical sidecars; unmarked artifacts retain their legacy behavior in place.
- Removing pre-apply checkpoint persistence or changing crash-recovery workflow; checkpoints remain durable recovery evidence.
- Redesigning convergence or reusable-audit behavior beyond excluding marked checkpoints; this plan limits reader changes to checkpoint identity.
- Changing data-contract apply's saved-artifact locator; its existing per-finding freshness gate remains the safety boundary for checkpoint payloads.

## Risks

- A marked pre-apply checkpoint could still be counted by `load_report_history` or selected by `resolve_reusable_audit`, leaving the `BUG_BACKLOG` risk unresolved; mitigation is reader coverage and focused regression tests.
- A marked or unknown sidecar could be selected by `reconcile-plan` reuse and apply partial findings to a plan; mitigation is loaded-payload review selection, exact-pin notices, and focused regression coverage. The separate generic saved-walk risk remains in `BUG_BACKLOG.md`.
- A marker change could make historical unmarked completeness sidecars unreadable or change their legacy behavior; mitigation is the documented legacy policy without heuristic migration or bulk rewrite.
- A malformed marker, a role/version mismatch, or a downgrade reader could produce incorrect reader behavior; cover malformed-marker policy, the version-3 fence, and older-reader rejection.
- A checkpoint and final report written in the same wall-clock second could overwrite one another and lose recovery evidence; reserve distinct canonical report stems and cover the pairwise collision path.

## Testing

Add a raw-sidecar matrix for version-1/2 legacy finals and version-3 role-aware
sidecars: emitted checkpoint `true`, raw final `false`, absent legacy marker,
non-boolean marker, a marker in a legacy-version sidecar, a version-3 sidecar
with no marker, and a marker on a non-completeness sidecar. Prove that
save/load/update_annotation preserves the normalized role, final writers keep
omitting the optional key and their current versions, malformed or
role/version-mismatched metadata stays inspectable but is ineligible, and
unsupported versions remain rejected. Prove a simulated role-unaware v1/v2
reader rejects the emitted version-3 checkpoint rather than interpreting it as
final.

Add a fixed-clock writer regression that produces a pre-apply checkpoint and
its final report in the same second. Prove both Markdown/JSON pairs and any
sibling data-contract payload remain distinct, keep the existing canonical
`<timestamp>-completeness` filename convention, carry their respective logical
timestamps consistently, and preserve the checkpoint marker plus the final
writer's unmarked version.

Add focused regression tests proving that a marked checkpoint is neither
selected nor counted, a final report remains selected and counted once, and an
unmarked legacy completeness sidecar remains readable under the documented
policy. Validate default newest-eligible reuse, including rejection of a
loadable non-completeness payload under a `-completeness.json` filename, exact
pinned checkpoint/unknown/kind-mismatch rejection without fallback, every
relevant writer and reader, including
`write_pre_apply_audit_checkpoint`, `load_report_history`,
`resolve_reusable_audit`, `reconcile-plan` reuse, and
save/load/update_annotation behavior. For `reconcile-plan`, cover unpinned
scans past marked, unknown, unloadable, and non-review candidates; an exact
unsafe pin with a distinct notice and no fallback; ordinary `kind="review"`
acceptance; the interactive prompt, `--reuse`, `--yes`, and non-TTY entry
paths, including a selected safe non-TTY sidecar that skips the per-finding
walk; and the rule that a stale newest eligible candidate starts fresh rather
than widening the scan. Prove the
final convergence render receives the complete role-filtered history plus its
one in-memory final snapshot; it must not remove a newest final positionally.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (refactor) — tests covering the behavior this step changes; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- New checkpoints written by `write_pre_apply_audit_checkpoint` are explicitly marked with the persisted checkpoint-role marker on `SavedReview`.
- `is_pre_apply_checkpoint=true` in a version-3 sidecar is the only checkpoint producer output; final reports omit the optional key and retain their current version, while raw version-3 `false` and unmarked version-1/2 sidecars read as eligible final artifacts.
- Marker metadata on a non-completeness sidecar, with a non-boolean value, or in a version-1/2 sidecar, plus a marker-less version-3 sidecar, remains loadable for inspection but is excluded from reuse and convergence. Role-unaware readers reject version 3; newer readers preserve version-1/2 compatibility and reject unsupported future versions.
- `load_report_history` does not count a marked checkpoint as a full `RunSnapshot`.
- `resolve_reusable_audit` selects the newest `kind="completeness"` eligible final report by default, skips unreadable candidates, and declines an exact pin to a marked, unknown, unloadable, or kind-mismatched sidecar without falling back.
- `reconcile-plan` reuse accepts only an ordinary-final `kind="review"` sidecar; its unpinned scan skips marked, unknown-role, non-review, and unloadable candidates, and an unsafe exact pin declines with a distinct reason and no fallback.
- `reconcile-plan` selection stops at the newest eligible sidecar before the existing freshness gate runs; a stale eligible sidecar starts a fresh review and does not widen selection to older reports. The rule holds for the interactive prompt, `--reuse`, `--yes`, and non-TTY entry paths.
- A non-TTY `reconcile-plan` reuse of an eligible sidecar does not call the per-finding walk or block on `input()`; it reports the saved review and exits successfully, matching the fresh-review non-TTY behavior.
- A final report remains an ordinary reusable completeness artifact, is selected when applicable, and is counted once.
- Final rendering appends its current final snapshot to the complete role-filtered history and never removes the newest saved snapshot by position.
- Historical unmarked completeness sidecars remain loadable and preserve legacy behavior under the documented policy.
- Report naming and existing filename compatibility are preserved.
- A same-second checkpoint and final report have distinct canonical report stems; neither overwrites the other or a sibling data-contract payload.
- Schema version policy and malformed-marker policy are defined and covered.
- `DATA_CONTRACT.md` distinguishes the version-3 completeness producer contract from annotation rewrites that preserve an already-unknown role on another saved-review kind or version.
- The generated `docs/cli/reconcile-plan.md` reference matches the changed reuse help and its drift test passes.
- Step 7 updates `BUG_BACKLOG.md` and the session handoff to record the closed prompt-reuse portion while keeping the generic saved-walk reader gap open; do not represent this prompt-only change as final closure.
- Validation is completed and the session handoff is updated.

## Deferred

- Bulk migration of historical unmarked sidecars — defer until a separate migration and retention policy is defined; this plan preserves their legacy behavior in place.
