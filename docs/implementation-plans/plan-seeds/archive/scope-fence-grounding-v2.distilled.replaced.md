> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scope-fence-grounding-v2.md`.
> Preserved here for history; do not edit.

## Overview

Update `create` so it preserves supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` sections, can propose missing guardrails, and writes proposals only after explicit author approval. Carry the resolved originating scope contract into conceptual audits without adding audit invocations; non-interactive operation safely omits unapproved proposals.

## Problem statement

The prior preservation-only `scope-fence-grounding` contract was too restrictive: it could not help an author develop a missing scope fence. The tool must support model suggestions without silently treating them as author constraints, while keeping supplied guardrails intact and grounding audits in the resulting contract.

## Architecture

Keep the three named guardrails as optional canonical sections in `OPTIONAL_PLAN_BODY_SECTION_SHAPES`; do not allow general unknown-H2 passthrough. Deterministic exact-heading preservation checks stay zero-model-call checks at both distill and synthesis boundaries, while proposals may only fill missing headings and require explicit accept/reject handling.

Exclude all three guardrails from defer-bucket derivation in both create and detail. Store the durable repo-relative seed actually used as body/guardrail input in `Plan.source_seed`, following only an explicit canonical provenance pointer; if archival fails, retain a verified readable original or omit the field.

Add `completeness-audit --seed <path>` as an explicit provenance override that forces a fresh audit. The audit prompt receives the resolved source contract as originating intent, including `Audit guardrails`; absent contracts produce no added prompt block and remain byte-identical, while oversized contracts use a visible marker plus bounded excerpts of every present scope/guardrail heading.

## Risks

- Approval interaction may require a broader create UX redesign; preserve supplied guardrails and file author-approved proposals as follow-up rather than silently accepting them.
- The proposal path may expose a separate review/remove need; file it rather than extending concept storage.
- Archive failure must not leave invalid provenance; retain a verified readable original or omit `Plan.source_seed`.

## Testing

- Verify a seed with all three supplied guardrails preserves them exactly and offers no rewrite proposal.
- Verify a seed with no guardrails can receive proposals, accepted proposals are written only after explicit author approval, and rejected proposals are omitted.
- Verify heading loss at distill or synthesis boundaries produces deterministic, bounded findings and ordinary seeds gain no sections without approval.
- Verify neither bucket producer offers any guardrail section as deferrable.
- Cover durable provenance, `--seed` override and fresh-audit behavior, prompt fallback, safe truncation, and `Audit guardrails` grounding with tests.
- Keep relevant existing tests under `tests/` passing.

## Acceptance criteria

- `create` preserves supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` headings and text under their own headings.
- Missing guardrail sections may be proposed but reach the plan only after an explicit author accept decision; rejection and non-interactive operation omit them unless existing explicit approval input is supplied.
- Existing author-supplied guardrail text is not rewritten or weakened by the proposal path.
- Deterministic exact-heading checks at distill and synthesis boundaries use zero model calls and produce bounded findings when headings are lost.
- `Plan.source_seed` records only a durable repo-relative originating seed resolved through an existing explicit canonical provenance pointer, or is omitted when no verified readable original can be retained.
- `completeness-audit --seed <path>` overrides stored provenance and forces a fresh audit.
- The audit prompt honors `Audit guardrails` and the resolved source contract without increasing conceptual audit calls; no resolvable contract leaves the prompt byte-identical.
