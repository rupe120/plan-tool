> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add concept phrase consistency guidance to plan audit and tests

## Summary

This step teaches the plan audit to look for concept phrase drift: a recurring idea should keep one distinctive phrase across the plan body, step titles, acceptance criteria, and per-step detail files when that phrase is how readers track the concept. The main edits are in `plan_tool/prompts/plan-audit.md`, `plan_tool/prompts/apply-finding.md`, `tests/test_review.py`, and `tests/test_launcher.py`; `plan_tool/review.py` should stay behaviorally unchanged unless a small prompt-contract comment or helper name needs updating. The key design decision is to keep this as model-facing audit/apply guidance, not a deterministic phrase linter or a new finding source. On green, the rendered audit prompt asks for phrase-consistency findings, `completeness-apply`'s gap-closing prompt preserves the same authoring guidance while applying updates, and tests pin that guidance plus the existing `plan-completeness` / `plan-correctness` parser path.

## Table of Contents

- [Summary](#summary) — overview of the prompt and test behavior this step adds.
- [Why](#why) — why concept phrase consistency belongs in plan audit after step 1.
- [Files (creates vs edits)](#files-creates-vs-edits) — files this step should modify and what each change owns.
- [Implementation](#implementation) — intended behavior, anchors, and constraints.
- [Tests](#tests) — regression tests to add with the prompt change.
- [Acceptance criteria](#acceptance-criteria) — observable checks for completion.
- [References](#references) — prompt and pytest references for this step.
- [Deferred](#deferred) — out-of-scope deterministic work.

## Why

Step 1 documents the authoring rule that a recurring concept should keep one distinctive phrase stable, but `plan_tool/prompts/plan-audit.md` does not yet tell the conceptual audit to notice phrase drift across the plan and detail bundle. That leaves a gap where a plan can describe the same thread under several names, making findings harder to anchor and weakening the existing `[anchor-slug]` convergence behavior in `plan_tool/review.py:_PLAN_AUDIT_KEY_RE`, `plan_tool/review.py:Recommendation.anchor`, and `plan_tool/review.py:_format_carried_findings_block`.

The same guidance also needs to carry into the update path. `plan-tool completeness-apply` replays saved `plan-completeness` findings through `apply_finding`, which renders `plan_tool/prompts/apply-finding.md` to build the concrete plan/detail edit. If that prompt only says "apply this finding," the resulting update can close the local gap while reintroducing over-prescriptive detail, synonym drift, or prose-only feature ownership. The apply prompt should therefore preserve conceptual altitude and canonical concept-thread wording while it edits.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/prompts/plan-audit.md` — add concept phrase consistency guidance to the conceptual audit instructions, including when to flag drift and when not to flag harmless wording differences.
  - `plan_tool/prompts/apply-finding.md` — add apply-time guardrails so conceptual-completeness updates preserve conceptual altitude, reuse canonical concept phrases, and keep feature ownership tied to feature IDs / `step.features`.
  - `tests/test_review.py` — add prompt-rendering and parser-path coverage in `TestCheckPlanAudit` for the new phrase-consistency guidance.
  - `tests/test_launcher.py` — add dry-run `apply_finding` prompt coverage proving the gap-closing prompt used by `completeness-apply` includes the authoring guardrails.
  - `plan_tool/review.py` — no runtime change is expected; only update comments/docstrings near `render_plan_audit_prompt`, `_PLAN_AUDIT_KEY_RE`, or `_format_carried_findings_block` if the prompt wording needs a matching code-facing explanation.

## Implementation

- **Foundational logic: concept phrase consistency.** The new audit rule should say that when a plan introduces a distinctive phrase for a recurring concept, later references should reuse that phrase or make the relationship explicit. The audit should flag drift when renaming makes it unclear that two sections, steps, criteria, risks, or detail files are talking about the same concept.

- **Put the rule in the stable prompt prefix.** Update `plan_tool/prompts/plan-audit.md` near `## What to audit`, likely under `### Completeness — does the plan cover everything it needs to?`, because phrase drift is a coverage and traceability problem unless it creates a direct contradiction. Keep the volatile sections (`## Plan body` and `## Detail files (implementation bundle)`) at the end so `tests/test_review.py:TestCheckPlanAudit.test_volatile_inputs_are_last_for_prefix_caching` remains true.

- **Define the positive and negative cases.** The prompt should ask for a finding when the same concept is renamed in a way that breaks traceability, such as a risk using one distinctive phrase while the implementing step/detail uses a different one with no bridge. It should not flag normal prose variation, generic synonyms, shorter local wording after a clear first use, or exact names that differ because they are real code/file/symbol names.

- **Route findings through existing audit sources.** Do not add a new `Recommendation.source`, a new parsed output block, or a new apply lane in `plan_tool/review.py`. A phrase-drift finding should be emitted in the existing `## Completeness findings` or `## Correctness findings` section and parsed by `plan_tool/review.py:_parse_plan_audit_findings` as `source="plan-completeness"` or `source="plan-correctness"`. Phrase drift alone should use only low/info advisory severity; reserve medium+ correctness/completeness findings for independent substantive design gaps.

- **Preserve the existing anchor contract.** The guidance should connect phrase consistency to the current `[anchor-slug]` rule in `plan_tool/prompts/plan-audit.md:## Findings format`. If the audit flags phrase drift, the `[anchor-slug]` should name the underlying concept thread, not the wording problem itself, so `plan_tool/review.py:_split_audit_key` and `plan_tool/review.py:_make_rec_id` keep stable ids across re-audits.

- **Keep the fix conceptual.** The prompt should make the expected `→ fix:` read like a plan/detail prose edit, for example “choose one distinctive phrase for the concept and bridge the alternate wording,” not a mechanical instruction to edit a specific line. This keeps the finding compatible with `plan_tool/review.py:AUDIT_FIX_SOURCES` and `plan_tool/review.py:audit_targeted_fix`.

- **Carry the guidance into completeness-apply updates.** Update `plan_tool/prompts/apply-finding.md`, the shared prompt used when `completeness-apply` routes `plan-completeness` findings through `apply_finding`. The apply prompt should tell the model that when it adds or revises plan/detail prose it must:
  - preserve conceptual altitude by adding durable decisions, constraints, contracts, correctness rationale, and accepted-residual rationale rather than brittle mechanics;
  - demote mechanical specifics to `e.g.` examples, placeholders, executor notes, or ticket notes unless the specificity is itself the invariant;
  - reuse the canonical concept phrase for recurring threads, or explicitly bridge alternate wording instead of scattering synonyms;
  - keep feature IDs and `step.features` as the authoritative ownership thread, using concept phrases only as finding identity/reporting context.

- **Avoid a deterministic phrase linter.** A regex or token-overlap checker would create false positives because concept naming depends on context. The plan audit already sees the plan body and the detail bundle through `plan_tool/review.py:render_plan_audit_prompt`, so the model prompt is the right place for this advisory judgment.

## Tests

- `test_plan_audit_prompt_mentions_concept_phrase_consistency` — asserts `render_plan_audit_prompt` includes the new concept phrase consistency guidance and the “do not flag harmless wording variation” guard.
- `test_plan_audit_phrase_guidance_stays_in_stable_prefix` — asserts the new guidance appears before `## Plan body` and `## Detail files (implementation bundle)`, preserving the prefix-caching shape pinned by `test_volatile_inputs_are_last_for_prefix_caching`.
- `test_plan_audit_parses_phrase_drift_finding_as_completeness` — drives `check_plan_audit` with a fake low/info phrase-drift completeness finding and asserts `source="plan-completeness"`, `anchor`, `suggested_action`, `impact`, and `complexity` parse through the existing path.
- `test_plan_audit_phrase_drift_finding_id_uses_concept_anchor` — asserts two fake findings with the same concept slug but different prose keep the same id, matching `test_anchor_slug_gives_rephrasing_stable_id`.
- `tests/test_launcher.py::TestApplyFindingDryRun::test_apply_prompt_includes_plan_authoring_guardrails` — drives `apply_finding(..., dry_run=True)` and asserts the rendered prompt includes conceptual-altitude guidance, concept-thread wording guidance, and the feature-ownership boundary. This pins the prompt seam that `completeness-apply` uses when applying conceptual-completeness updates.
- Shared regression fixture — use the same plan/detail example as step 2, with brittle mechanical detail demoted to examples and one recurring concept phrase kept stable across steps.

### Test-creation order (feature step)

Add the prompt-rendering tests with the prompt update, then add the parser-path regression using `check_plan_audit` and a fake invoker. Every new test in `tests/test_review.py` must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/prompts/plan-audit.md` tells the audit to flag concept phrase drift when it makes a recurring concept hard to trace across the plan body and detail bundle.
- `plan_tool/prompts/plan-audit.md` tells the audit not to flag harmless wording variation, generic synonyms, or real code/file/symbol names that differ for valid reasons.
- `render_plan_audit_prompt` output includes the phrase-consistency guidance before `## Plan body`.
- A fake phrase-drift audit response still parses through `check_plan_audit` as an ordinary low/info `plan-completeness` or `plan-correctness` recommendation with `anchor` and `suggested_action` populated.
- `plan_tool/prompts/apply-finding.md` tells gap-closing updates to preserve conceptual altitude, preserve canonical concept-thread wording, and not infer feature ownership from prose alone.
- `apply_finding(..., dry_run=True)` renders those guardrails, covering the prompt path used by `completeness-apply` for `plan-completeness` findings.
- No new `Recommendation.source`, `APPLY_ELIGIBLE_SOURCES` entry, or `STRUCTURAL_SOURCES` entry is added for this guidance.
- The phrase-consistency tests include the shared plan/detail regression fixture that also exercises brittle mechanical detail demotion.
- The new `tests/test_review.py` tests pass.

## References

- [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Use for clear prompt instructions, examples, and output-format guardrails.
- [pytest: Assertions in Tests](https://docs.pytest.org/en/stable/how-to/assert.html) — Use for direct prompt-content and parsed-recommendation assertions.
- [pytest: Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use if the positive and negative phrase-drift cases are clearer as parametrized prompt assertions.

## Deferred

- Deterministic phrase matching — leave this out because phrase consistency is contextual and a regex/token heuristic would be noisy.
- Detail-quality concept phrase findings — this step targets `plan_tool/prompts/plan-audit.md`; any separate detail-quality prompt behavior belongs in a later scoped step.
- Completeness-apply runtime routing changes — existing `plan-completeness` findings already route through `apply_finding`; this step only updates the prompt contract and tests that rendered prompt.
