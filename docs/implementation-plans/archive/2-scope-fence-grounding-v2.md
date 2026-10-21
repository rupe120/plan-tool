---
title: Scope Fence Grounding V2
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Keep supplied guardrail sections in new plans
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - plan_tool/prompts/synthesize-body.md
  - tests/test_create.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/scope-fence-grounding-v2/01-keep-supplied-guardrail-sections-new.md
  status: current
- id: 2
  title: Ask before adding missing guardrails
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - plan_tool/prompts/synthesize-body.md
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/scope-fence-grounding-v2/02-ask-before-adding-missing-guardrails.md
- id: 3
  title: Keep guardrails out of defer buckets
  files:
  - plan_tool/create.py
  - plan_tool/detail.py
  - tests/test_create.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/scope-fence-grounding-v2/03-keep-guardrails-out-defer-buckets.md
- id: 4
  title: Save a usable source seed with new plans
  files:
  - PLAN_FORMAT.md
  - plan_tool/cli/authoring.py
  - plan_tool/create.py
  - plan_tool/schema.py
  - tests/cli/test_authoring_cmds.py
  - tests/test_create.py
  - tests/test_parser.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/scope-fence-grounding-v2/04-save-usable-source-seed-new-plans.md
- id: 5
  title: Add the completeness-audit --seed option
  files:
  - docs/cli/completeness-audit.md
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_cli_reference.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/scope-fence-grounding-v2/05-completeness-audit-seed-option.md
- id: 6
  title: Ground conceptual audits in the source contract
  files:
  - docs/AUDIT_FLOW.md
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/prompts/plan-audit.md
  - plan_tool/review.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_review.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/scope-fence-grounding-v2/06-ground-conceptual-audits-source-contract.md
---
# Scope Fence Grounding V2

## Overview

Update `create` so it preserves supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` sections, can propose missing guardrails, and writes proposals only after explicit author approval. Carry the resolved originating scope contract into conceptual audits without adding audit invocations; non-interactive operation safely omits unapproved proposals.

## Problem statement

The prior preservation-only `scope-fence-grounding` contract was too restrictive: it could not help an author develop a missing scope fence. The tool must support model suggestions without silently treating them as author constraints, while keeping supplied guardrails intact and grounding audits in the resulting contract.

## Architecture

Keep the three named guardrails as optional canonical sections in `OPTIONAL_PLAN_BODY_SECTION_SHAPES`; do not allow general unknown-H2 passthrough. Deterministic exact-heading preservation checks stay zero-model-call checks at both distill and synthesis boundaries, while proposals may only fill missing headings and require explicit accept/reject handling.

Exclude all three guardrails from defer-bucket derivation in both create and detail. Store the durable repo-relative seed actually used as body/guardrail input in `Plan.source_seed`, whether it is the direct `--from-existing` input or a source selected by its existing explicit canonical provenance pointer; if archival fails, retain a verified readable original or omit the field.

Add `completeness-audit --seed <path>` as an explicit provenance override that forces a fresh audit. The audit prompt receives the resolved source contract as originating intent, including `Audit guardrails`; absent contracts produce no added prompt block and remain byte-identical, while oversized contracts use a visible marker plus bounded excerpts of every present scope/guardrail heading.

## Input

Consume the resolved originating scope contract and the durable seed used as body/guardrail input. `Plan.source_seed` may record the direct `--from-existing` input or a source selected by its existing explicit canonical provenance pointer, but only when the resulting repo-relative path is verified readable; otherwise omit the field. `completeness-audit --seed <path>` is an explicit override that bypasses stored provenance and forces a fresh audit.

## References

- [argparse — Python Standard Library](https://docs.python.org/3/library/argparse.html) — Defines subcommands and option parsing needed to add and validate the explicit `completeness-audit --seed` override.
- [pathlib — Python Standard Library](https://docs.python.org/3/library/pathlib.html) — Covers path resolution and filesystem checks needed to store only verified repo-relative seed provenance.
- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Explains model fields, validation, and configuration for adding `Plan.source_seed` without weakening the plan schema.
- [Pydantic Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) — Documents controlled model serialization for persisting the new provenance field through plan frontmatter.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Provides the loader and dumper behavior relevant to retaining YAML plan metadata while changing canonical body sections.
- [Claude API Messages Reference](https://platform.claude.com/docs/en/api/messages) — Specifies message and system-prompt inputs an implementer would consult when grounding audit prompts in the resolved scope contract.
- [pytest Output Capturing](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Covers output and input-test considerations for verifying interactive approval and safe non-interactive omission behavior.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- General unknown-H2 passthrough.
- Adding audit invocations as part of grounding conceptual audits in the resolved source contract.

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

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- `create` preserves supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` headings and text under their own headings.
- Missing guardrail sections may be proposed but reach the plan only after an explicit author accept decision; rejection and non-interactive operation omit them unless existing explicit approval input is supplied.
- Existing author-supplied guardrail text is not rewritten or weakened by the proposal path.
- Deterministic exact-heading checks at distill and synthesis boundaries use zero model calls and produce bounded findings when headings are lost.
- `Plan.source_seed` records only a durable repo-relative originating seed from the direct `--from-existing` input or its existing explicit canonical provenance pointer, or is omitted when no verified readable original can be retained.
- `completeness-audit --seed <path>` overrides stored provenance and forces a fresh audit.
- The audit prompt honors `Audit guardrails` and the resolved source contract without increasing conceptual audit calls; no resolvable contract leaves the prompt byte-identical.

## Deferred

- A broader create UX redesign for approval interaction; preserve supplied guardrails and file author-approved proposals as follow-up.
- A separate review/remove path for proposals; file it rather than extending concept storage.
