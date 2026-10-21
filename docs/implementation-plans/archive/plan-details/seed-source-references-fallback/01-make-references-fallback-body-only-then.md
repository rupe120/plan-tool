> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Make the References fallback body-only, then add it to the remaining plan seeds

## Summary

Make `## References` recognition use only Markdown prose below leading YAML frontmatter. Update `plan_tool/create.py:validate_from_existing_seed` and `plan_tool/annotate_render.py:render_create_seed`, then add source-specific References blocks to every listed live seed. Keep scope-out’s existing body extraction unchanged and prove its single-step and region seeds remain valid create inputs. On green, a frontmatter-only heading fails before authoring, while valid body references and generated fallbacks pass.

## Table of Contents

- [Summary](#summary) — The change and its green result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why source evidence must be visible in the body.
- [Input](#input) — Source-text and generated-seed contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required body-only validation and seed updates.
- [Tests](#tests) — Focused regression and corpus coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — External format and test references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this step.
- [Deferred](#deferred) — Work intentionally left outside this step.

## Why

File-backed create sources require real reference evidence before authoring begins, but an H2-shaped YAML comment currently satisfies the shared heading reader even though it is not visible seed prose. That can admit a false source through `plan_tool/create.py:validate_from_existing_seed` or cause `plan_tool/annotate_render.py:render_create_seed` to preserve the false block. The live seed corpus also advertises `create --from-existing` routes without the required fallback, so those routes must become usable without weakening the evidence gate.

## Input

- **File-backed seed text** — `plan_tool/create.py:validate_from_existing_seed` receives complete source text that may begin with YAML frontmatter. The body-only rule must use `plan_tool/scope_fence.py:_strip_frontmatter` before `extract_h2_sections`.
- **Annotated source text** — `plan_tool/annotate_render.py:render_create_seed` reads `PlanAnnotation.source_text`; preserve a valid body References section or render its existing source-document and report fallback.
- **Scope-out source body** — `plan_tool/scope_out.py:scope_out_step` passes the parsed plan body to `extract_h2_sections` before calling `render_carved_seed` or `render_carved_region_seed`. Reuse that behavior unchanged.
- **Live seed corpus** — test only root `plan-seeds/*.md` files. Archive content is outside this step.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — make `validate_from_existing_seed` inspect only the Markdown body while preserving its existing refusal and no-authoring boundary.
  - `plan_tool/annotate_render.py` — make `render_create_seed` preserve References only from the source body and use its fallback when frontmatter is the only match.
  - `plan-seeds/audit-finding-staleness-classification.md` — add a `## References` block citing its existing source evidence.
  - `plan-seeds/audit-shape-advisory-generic-walk.md` — add a source-specific `## References` block.
  - `plan-seeds/audit-shape-saturation-and-provenance.md` — add a source-specific `## References` block.
  - `plan-seeds/completeness-output-quality.md` — add a source-specific `## References` block.
  - `plan-seeds/connectivity-pause-and-poll.md` — add a source-specific `## References` block.
  - `plan-seeds/convergence-policy-channel-ownership.md` — add a source-specific `## References` block.
  - `plan-seeds/create-detail-phase-decomposition.md` — add a source-specific `## References` block.
  - `plan-seeds/deferred-findings-digest.md` — add a source-specific `## References` block.
  - `plan-seeds/disable-jira-grade-detail-authoring.md` — add a source-specific `## References` block.
  - `plan-seeds/feature-health-2-attribution-and-ledger.md` — add a source-specific `## References` block.
  - `plan-seeds/jira-sweep-verify-code-truth.md` — add a source-specific `## References` block.
  - `plan-seeds/lessons-store-restructure.md` — add a source-specific `## References` block.
  - `plan-seeds/premise-ledger.md` — add a source-specific `## References` block.
  - `plan-seeds/reseed-advisor.md` — add a source-specific `## References` block.
  - `plan-seeds/risk-profile-3-advisory-effectiveness.md` — add a source-specific `## References` block.
  - `plan-seeds/walk-advisory-chat-mode.md` — add a source-specific `## References` block.
  - `tests/test_create.py` — cover body-only validation, direct-call refusal ordering, and the live seed corpus.
  - `tests/cli/test_authoring_cmds.py` — cover the CLI refusal before `create_plan` when only frontmatter supplies the heading.
  - `tests/test_annotate_render.py` — cover body-only preservation and fallback output.
  - `tests/test_scope_out.py` — prove both scope-out seed forms remain valid `--from-existing` inputs.

## Implementation

- **Foundational rule:** only a non-placeholder `## References` section in the Markdown body counts as the required source fallback.

- **Keep create validation as the single gate.** In `plan_tool/create.py:validate_from_existing_seed`, strip only leading frontmatter with `plan_tool/scope_fence.py:_strip_frontmatter`, then use the existing `extract_h2_sections` and `_is_placeholder_section` checks. Preserve the current `CreateError` and its pre-invoker placement in both `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/create.py:_prepare_create_plan`.

- **Do not change the shared H2 extractor.** `plan_tool/scope_fence.py:extract_h2_sections` has consumers beyond this source-evidence check, including its closing-ATX-heading behavior. Apply the body boundary at the two source readers rather than changing global heading semantics.

- **Make annotate follow the same boundary.** In `plan_tool/annotate_render.py:render_create_seed`, derive `source_references` from the frontmatter-stripped `PlanAnnotation.source_text`. A valid body section must remain the rendered References content. A missing, placeholder, or frontmatter-only section must render the existing `Source document` and `Annotated report` fallback instead.

- **Leave scope-out production code unchanged.** `plan_tool/scope_out.py:scope_out_step` already uses `parser._split_frontmatter(...).body` before selecting `source_references`, and both `render_carved_seed` and `render_carved_region_seed` share `_references_block`. Test that existing contract rather than adding another renderer or extraction path.

- **Add meaningful seed evidence.** Append one body-level `## References` section to every listed root seed. Each block must cite real source material that seed already relies on, such as a named backlog item, report, decision record, module, or documentation path. Keep the seed’s existing scope and citations intact; do not use a fabricated URL, an empty list, a placeholder, or the seed’s own path as a pass token.

- **Keep the change narrow.** Do not alter distillation, body synthesis, direct-ready routing, split handling, model-call order, or create signatures. The body-only check must not become a general schema or canonical-body requirement.

## Tests

### Tests for this step

- `test_rejects_frontmatter_only_references` — `validate_from_existing_seed` rejects a leading-frontmatter H2 with no body References.
- `test_accepts_body_references_after_frontmatter` — a real non-placeholder body H2 remains valid when frontmatter is present.
- `test_direct_create_frontmatter_only_references_refuses_before_invokers_and_writes` — direct `create_plan` makes no authoring call and creates no output, checkpoint, archive, plan, or manifest artifact.
- `test_live_plan_seeds_pass_references_preflight` — every root `plan-seeds/*.md` file passes `validate_from_existing_seed`, without including archived seeds.
- `test_cli_frontmatter_only_references_stops_before_create_plan` — `cmd_create` returns its existing usage refusal before dispatching to `create_plan` or opening a run log.
- `test_seed_frontmatter_only_references_uses_source_fallback` — `render_create_seed` drops the false frontmatter block, emits both fallback provenance rows, and produces output accepted by the real create validator.
- `test_seed_preserves_body_references_after_frontmatter` — annotate output keeps actual body References rather than replacing them with fallback content.
- `test_single_and_region_scope_out_fallbacks_pass_create_preflight` — output from `render_carved_seed` and `render_carved_region_seed` each passes `validate_from_existing_seed`.
- `test_applied_scope_out_frontmatter_reference_uses_body_fallback` — an applied scope-out operation ignores a frontmatter-only heading and writes a validator-clean source-plan fallback.

Run `uv run pytest tests/test_create.py tests/cli/test_authoring_cmds.py tests/test_annotate_render.py tests/test_scope_out.py -q` and the plan test command before marking the step done.

## Acceptance criteria

- `plan_tool/create.py:validate_from_existing_seed` accepts a non-placeholder body References section and rejects a frontmatter-only, missing, or placeholder section.
- A rejected file-backed source reaches no authoring invoker and writes no output, checkpoint, archive, plan, or manifest artifact.
- `plan_tool/annotate_render.py:render_create_seed` preserves only body References; a frontmatter-only heading produces its existing provenance fallback.
- Every root `plan-seeds/*.md` file has a meaningful, non-placeholder body `## References` section and passes the real create validator.
- `plan_tool/scope_out.py:render_carved_seed` and `plan_tool/scope_out.py:render_carved_region_seed` remain validator-clean without production changes.
- All focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [CommonMark Spec — ATX headingshttps: — Confirm the H2 and optional closing-hash rules used by the existing extractor.
- [Python 3.13 — Regular expression operationshttps: — Review multiline matching behavior behind the heading and placeholder predicates.
- [Python 3.13 — Object-oriented filesystem pathshttps: — Use root-only globbing and text reads for the corpus test.
- [pytest — How to parametrize fixtures and test functionshttps: — Structure focused controls and maintained-seed coverage.

## Applicable guardrails

- **The plan’s “Plan intent”** — every edit must help maintained `--from-existing` seeds reach their existing authoring route through valid References evidence.
- **The plan’s “Step intent”** — keep the body-only boundary and pre-invoker refusal intact for live seeds, annotate output, and both scope-out forms.
- **The plan’s “Out of scope”** — do not broaden body-section requirements, change authoring flow behavior, edit archived seeds, add a seed schema, or treat weak reference content as evidence.

## Deferred

- Broader source-admission and canonical-body policy changes remain outside this step under the plan’s out-of-scope boundary.
- Refactoring scope-out’s existing body extraction remains unnecessary while its current output passes the create validator.
