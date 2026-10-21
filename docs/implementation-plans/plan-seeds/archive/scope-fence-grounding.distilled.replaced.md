> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scope-fence-grounding.md`.
> Preserved here for history; do not edit.

## Overview

Preserve optional seed sections named `Scope guardrails`, `Audit guardrails`, and `Expected placement` as their own plan-body headings when present, and ground conceptual audits in the originating seed's scope contract. The work carries BACKLOG #161 and #162 as one contract: the plan body must retain the fence and the audit must receive it. It must add no Claude calls, must leave behavior unchanged when no guardrail sections or resolvable seed exist, and must not reopen the closed canonical-section model.

## Problem statement

Today `PLAN_BODY_SECTIONS` (`create.py:185-193`) and the synthesis prompt contracts reject unrecognized H2 sections, so seed guardrails are folded into `Architecture` or silently dropped; `Audit guardrails` is dropped outright. Separately, `render_plan_audit_prompt` (`review.py:5838-5846`) does not receive the seed even though `plan-audit.md:94-98` and `docs/AUDIT_FLOW.md:36-39` describe it as the scope contract. The audit is therefore instructed to honor a fence it cannot reliably see.

## Architecture

Add `Scope guardrails`, `Audit guardrails`, and `Expected placement` as optional canonical sections in `OPTIONAL_PLAN_BODY_SECTION_SHAPES` (`create.py:296`) beside `Input`, with `[conditional]` policy and an evidence-only posture: omit them entirely when absent rather than returning null. Update `plan_tool/prompts/synthesize-body.md` and `prompts/distill-seed.md` to accept the sections and include a worked example, while retaining the closed-section contract rather than accepting arbitrary H2 headings.

Add a deterministic exact-heading preservation check: when a seed contains one of the three guardrail headings and the synthesized body lacks it, emit a finding. The check is bounded by the number of seed guardrail headings, uses zero Claude calls, and does not attempt to judge whether content was materially folded elsewhere.

Exclude the three guardrail section names from defer-bucket derivation in both `derive_candidate_buckets` (`detail.py:522-545`) and `create` bootstrap (`create.py:5962-5972`), so standing audit constraints cannot be deferred.

Add `source_seed: Optional[str] = None` to `Plan` in `schema.py:180-208`, storing a repo-relative path for `create --from-existing` and eliding it on rewrite when unset. Add `--seed <path>` as an explicit completeness-audit override; do not infer provenance by slug matching. Update `DATA_CONTRACT.md`, `PLAN_FORMAT.md`, and `docs/AUDIT_FLOW.md` for the field and provenance behavior.

Extend `render_plan_audit_prompt` and its block collector with `${scope_contract_block}` in `plan_tool/prompts/plan-audit.md`. A resolvable seed supplies its originating scope contract verbatim; an unresolved seed produces an empty block and byte-identical current output. Oversized contracts are visibly truncated, and the prompt identifies this as originating intent, with the current plan body winning on direct conflict.

## Out of scope

- Any Claude call in the preservation check; material folded-content judgment remains BACKLOG #163.
- Seed-vs-plan drift detection; the contract is prompt-level originating intent, not current truth.
- Mechanically enforcing the audit contract, `partition_findings_for_triage`, `convergence.is_blocking_impact`, or convergence predicates.
- `[out-of-scope-deferred]` wiring (BACKLOG #156), `concepts.json`, `scope-review`, and the concept-record schema; the bucket exclusion is not a concept-store extension.
- Reordering or renaming the eight canonical sections, enforcing guardrails on seeds that lack them, or authoring guardrail content.

## Risks

- Exact-heading preservation can report a false positive when content was folded under another heading; mitigate by keeping the check deterministic and route evidence of noise to BACKLOG #163 rather than adding model judgment.
- Seed provenance may be unrecoverable on some `create` paths such as `--from` or `--reprocess`; record it where possible and file the remaining plumbing rather than expanding the plan.
- A wrong inferred seed would supply an incorrect fence; mitigate by requiring `source_seed` or explicit `--seed <path>` and never slug-match `plan-seeds/`.
- An oversized scope contract could lose context; mitigate with an explicit truncation marker rather than silent clipping.

## Testing

- Add tests under `tests/` for a fixture seed carrying all three guardrail sections, verifying `create` retains each heading; verify a seed carrying none invents none.
- Test the deterministic preservation check for both a dropped seed heading and a retained heading.
- Test both `create` and `detail` bucket producers to verify `## Audit guardrails` is not offered as a defer bucket.
- Test `create --from-existing` writes `source_seed`, while other creation paths omit the key.
- Test `render_plan_audit_prompt` includes a seed-backed scope contract, is byte-identical to current output without a resolvable seed, and marks oversized-contract truncation.
- Run `tests/test_data_contract.py` with the `source_seed` addition.

## Acceptance criteria

- A seed containing `Scope guardrails`, `Audit guardrails`, and `Expected placement` produces a plan body with each heading retained separately.
- A seed containing none of those headings produces none of them in the plan body.
- Synthesis that drops a seed-carried guardrail heading produces a deterministic preservation finding, while retained headings do not.
- Neither `derive_candidate_buckets` nor `create` bootstrap offers `## Audit guardrails` as a `defer` bucket.
- A plan created with `--from-existing` records `source_seed`; plans created through other paths omit the frontmatter key when it is unset.
- `render_plan_audit_prompt` contains the originating scope contract for a seed-backed plan and is byte-identical to current output when no seed resolves.
- An oversized scope contract includes a visible truncation marker.
- `tests/test_data_contract.py` passes after the `source_seed` addition.

## Deferred

- BACKLOG #163: model-based judgment of whether dropped guardrail content was materially folded elsewhere.
- Seed provenance for unrecoverable `create` paths such as `--from` and `--reprocess`, if it requires broader plumbing.
- BACKLOG #132 interaction: a concept dismiss/remove verb if the exclusion set later proves insufficient.
- Remove BACKLOG #161 and #162 only after full shipment; if execution is pending, mark them plan-authored. Keep BACKLOG #163 filed and unshipped.
