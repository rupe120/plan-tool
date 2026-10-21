> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Document conceptual altitude and concept phrase rules

## Summary

This step updates `DETAIL_FORMAT.md` so detail authors have one checked-in reference for two rules: keep implementation detail at the right level, and keep one distinctive phrase stable for a recurring concept thread. The only edited file is `DETAIL_FORMAT.md`; the audit code and prompts stay unchanged in this step. The key design choice is to document a judgment rule, not a lint rule: specific details stay when they are constraints, contracts, rejected alternatives, or examples, but brittle mechanics should be framed as examples or executor notes. On green, a reviewer can point to `DETAIL_FORMAT.md` for the conceptual-altitude keep/cut table and the one-distinctive-phrase concept-thread rule that later steps use in audit guidance.

## Table of Contents

- [Summary](#summary) — overview of the docs-only change and expected result.
- [Why](#why) — why the authoring rules belong in the detail format reference first.
- [Files (creates vs edits)](#files-creates-vs-edits) — the single-file docs change.
- [Implementation](#implementation) — the intended `DETAIL_FORMAT.md` additions and related anchors to respect.
- [Tests](#tests) — non-code verification for the markdown artifact.
- [Acceptance criteria](#acceptance-criteria) — concrete checks for the completed doc update.
- [References](#references) — primary markdown reference useful for this step.
- [Deferred](#deferred) — audit and test implementation left to later steps.

## Why

`DETAIL_FORMAT.md` already tells authors that `## Implementation` should aim for intent over mechanics, but it does not define where the boundary sits or how to preserve a stable concept name while trimming brittle detail. That leaves two failure modes for future detail files: prose can read like a mandatory implementation script when it should be an adaptable recommendation, or a recurring concept can be renamed across steps until audit findings lose a stable identity. This step makes the authoring rule explicit before steps 2 and 3 teach the detail-quality and plan-audit surfaces to look for these problems.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `DETAIL_FORMAT.md` — add authoring guidance under the detail-file format reference, covering conceptual altitude, a keep/cut table, accepted ways to keep mechanical detail as examples or notes, the rule for when specificity is still required, and the one-distinctive-phrase concept-thread rule.

## Implementation

- **Add the guidance where authors already look for section meaning.** Edit `DETAIL_FORMAT.md`, likely near `## Section schema` / `### Field semantics`, because that is where `## Implementation`, `## Tests`, and `## Acceptance criteria` are defined today. Keep the current parser contract note intact: `plan_tool/detail.py:_REQUIRED_H2_TOKENS`, `plan_tool/detail.py:parse_detail_response`, and `plan_tool/prompts/detail.md` remain the enforced/runtime surfaces.

- **Define conceptual altitude as a documentation rule.** The doc should say a detail file should pin intent, constraints, contracts, real anchors, gotchas, and accepted tradeoffs, while avoiding prose that makes incidental mechanics look mandatory. A good shape is a compact markdown table with “keep” and “cut or demote” examples:
  - Keep: invariants, required signatures when already fixed, ordering constraints, failure modes, rejected alternatives with reasons, cross-step contracts, and observable acceptance checks.
  - Cut or demote: exact pseudo-code, full config/IAM blobs, magic constants copied from a source plan, exhaustive test rosters, speculative helper names, and API literals that are examples rather than contracts.
  - Demote does not mean delete. The doc should allow wording such as `e.g.`, placeholders, executor notes, or ticket notes when a mechanical detail is useful context but not the required design.

- **State when specificity is required.** Do not let the altitude rule become a reason to remove important detail. The doc must explicitly preserve specificity when the exact value, name, order, status code, token kind, event boundary, or file/symbol anchor is the constraint the implementer must satisfy. This matches the current authoring prompt stance in `plan_tool/prompts/detail.md`, which asks for real file paths and symbolic anchors while leaving exact code to the implementer.

- **Add the one-distinctive-phrase rule for concept threads.** Define a recurring concept thread as an idea that appears across plan prose, multiple step details, acceptance criteria, audit findings, or convergence reporting. The rule should ask authors to keep one short, distinctive phrase stable for that concept once chosen, while still allowing surrounding prose to vary. The phrase supports finding identity and reporting; it does not own feature capability routing.

- **Separate concept phrase identity from feature ownership.** Name the boundary from the plan body: feature IDs and `step.features` remain the ownership mechanism, while canonical concept phrases stabilize audit identity and repeated evidence. Cite nearby code anchors only as orientation, not edit targets: `plan_tool/review.py:validate_feature_refs` and `plan_tool/review.py:detect_self_referential_features` are feature-id checks; `plan_tool/prompts/plan-audit.md` already uses stable `[anchor-slug]` wording for finding identity; `plan_tool/review.py:_format_carried_findings_block` feeds prior finding anchors back into later audit passes.

- **Do not change parser behavior.** This step should not add a new required section, YAML field, schema token, or parser rule. `DETAIL_FORMAT.md` is human reference material, and its opening source-of-truth note should remain accurate: if it disagrees with `plan_tool/detail.py:parse_detail_response`, the code wins.

- **Use plain examples, not a new glossary.** The concepts should be understandable from the text without inventing a new schema. Recommended terms are “conceptual altitude,” “mechanical detail,” “one distinctive phrase,” and “concept thread,” because those match the plan language and the later audit steps.

## Tests

No unit tests are required for this docs-only step, and no test file should be edited.

- `manual_markdown_check` — read `DETAIL_FORMAT.md` and confirm the new guidance renders as normal GitHub-flavored markdown, especially the keep/cut table if one is used.
- `manual_anchor_check` — confirm every code or doc anchor named in `DETAIL_FORMAT.md` still exists, including `plan_tool/detail.py:_REQUIRED_H2_TOKENS`, `plan_tool/detail.py:parse_detail_response`, and `plan_tool/prompts/detail.md`.
- `manual_scope_check` — confirm the change does not claim a new enforced parser rule, new required H2, or audit behavior that belongs to steps 2 or 3.

### Verification (non-code step)

This is a non-code step. Verify the artifact by reviewing the rendered markdown, checking links/anchors, and confirming the doc matches the current parser and prompt boundaries. No test-ordering directive applies.

## Acceptance criteria

- `DETAIL_FORMAT.md` contains a conceptual-altitude keep/cut table or equivalent compact list.
- `DETAIL_FORMAT.md` says mechanical detail may remain as `e.g.` examples, placeholders, executor notes, or ticket notes when it is useful but not mandatory.
- `DETAIL_FORMAT.md` says exact specificity stays when the detail is the required invariant, constraint, contract, accepted tradeoff, or rejected alternative.
- `DETAIL_FORMAT.md` contains a one-distinctive-phrase rule for recurring concept threads.
- `DETAIL_FORMAT.md` states that feature IDs and `step.features` own capability/thread ownership, while concept phrases support finding identity and reporting.
- `DETAIL_FORMAT.md` does not add or imply a new required H2, YAML field, parser behavior, auto-rewrite behavior, or blocking lint rule.

## References

- [GitHub Flavored Markdown Spec](https://github.github.com/gfm/) — Use for table, list, heading, and link syntax when updating `DETAIL_FORMAT.md`.

## Deferred

- Detail-quality altitude findings — step 2 owns changes to `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/prompts/detail-quality.md`, `tests/test_detail.py`, and `tests/test_review.py`.
- Plan-audit concept phrase consistency findings — step 3 owns changes to `plan_tool/review.py`, `plan_tool/prompts/plan-audit.md`, and `tests/test_review.py`.
- Auto-rewriting or renaming detail prose — out of scope for this plan; the documented rule supports advisory findings only.
