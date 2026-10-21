> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add advisory-only detail-quality altitude findings and tests

## Summary

This step teaches the detail-quality audit to report conceptual-altitude problems without auto-editing detail prose. The main edits are in `plan_tool/prompts/detail-quality.md`, `plan_tool/detail.py`, and `plan_tool/review.py`, with regression coverage in `tests/test_detail.py` and `tests/test_review.py`. The key design decision is to keep altitude findings out of the normal apply path: they should be visible to the operator, but `apply_finding` must not try to rewrite them. On green, over-prescriptive mechanical detail can be flagged as an advisory finding, while required constraints, anchors, rejected alternatives, and correctness rationale stay allowed.

## Table of Contents

- [Summary](#summary) — overview of the advisory detail-quality behavior and test surface.
- [Why](#why) — why altitude findings need a separate non-apply path.
- [Files (creates vs edits)](#files-creates-vs-edits) — the prompt, parser, triage, and test files to change.
- [Implementation](#implementation) — the recommended advisory finding flow and the constraints to preserve.
- [Tests](#tests) — unit tests to add with the feature.
- [Acceptance criteria](#acceptance-criteria) — observable checks for the completed behavior.
- [References](#references) — prompt and pytest references useful for this step.
- [Deferred](#deferred) — related work owned by later steps or out of scope.

## Why

Step 1 documents conceptual altitude in `DETAIL_FORMAT.md`, but the detail-quality loop still treats every semantic prompt finding as a normal `claude` recommendation that can be sent to `apply_finding`. That is too strong for altitude judgments: a reviewer can notice prose that reads like mandatory pseudo-code, magic constants, or exhaustive test rosters, but the tool should recommend demoting that material to examples or notes, not auto-strip it. This step adds the advisory signal where detail bodies are already reviewed while keeping the read-existing-detail-first rule that protects real constraints from being weakened.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/prompts/detail-quality.md` — add advisory conceptual-altitude instructions and an output block that is separate from the normal final `## Findings` block.
  - `plan_tool/detail.py` — parse and merge advisory altitude findings inside `collect_detail_quality_findings` without routing them through the normal `claude` recommendation path.
  - `plan_tool/review.py` — name the new advisory source and keep it out of `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES`, with a clear `triage_reason` message.
  - `tests/test_detail.py` — cover prompt rendering, advisory parsing, merge behavior, and convergence-loop non-dispatch.
  - `tests/test_review.py` — cover source eligibility and triage behavior for the new advisory source.

## Implementation

- **Add an advisory output lane, not another normal finding.** Update `plan_tool/prompts/detail-quality.md` near `## Step purity (refactor vs feature)` and `Style nits (flag at NIT, never block)` so the reviewer looks for conceptual-altitude problems:
  - Flag prose that makes incidental mechanics look mandatory: full pseudo-code, exact speculative helper names, magic constants copied from a source plan, API argument literals, full config/IAM snippets, or exhaustive test rosters.
  - Do not flag exact details when they are the required constraint: real file/symbol anchors, fixed names already present at HEAD, ordering rules, event boundaries, rejected alternatives, failure modes, and acceptance checks.
  - Recommend demotion to `e.g.`, placeholders, executor notes, or ticket notes; do not ask the apply pass to delete or rewrite the body.

- **Keep the final `## Findings` contract intact.** The existing `plan_tool/detail.py:collect_detail_quality_findings` path calls `plan_tool.review:_claude_recommendations` on the final `## Findings` block, and that produces `source="claude"` recommendations. Altitude findings should not enter that path. A good approach is a separate prompt block such as `## Advisory altitude findings`, parsed by a small helper in `plan_tool/detail.py` before the existing `raw_for_findings` parse, similar in placement to the existing `## Structural findings` handling via `plan_tool.granularity:parse_mixed_step_findings`.

- **Use one stable advisory source.** Introduce a self-descriptive source string such as `detail-altitude` and use it for every altitude recommendation. The resulting `Recommendation` should carry `severity="info"`, `step_id=step.id`, a stable id from the body content, and no targeted fix. The exact helper names are up to the implementer, but keep the behavior easy to test from `collect_detail_quality_findings`.

- **Make advisory-only a triage fact, not prompt wording.** In `plan_tool/review.py`, keep the new source absent from `APPLY_ELIGIBLE_SOURCES`, absent from `STRUCTURAL_SOURCES`, and add a special `triage_reason` branch so the deferred summary says this is an advisory detail-quality altitude issue, not a path or dependency diagnostic. This is the important safety check: even with `--include-info`, the apply-eligibility gate should keep these findings away from `apply_finding`.

- **Do not weaken existing grounding and purity behavior.** `plan_tool/detail.py:collect_detail_quality_findings` must still merge normal Claude findings, deterministic grounding findings from `collect_step_grounding_findings`, change-type test-order findings from `collect_change_type_test_order_findings`, and mixed-step findings from `parse_mixed_step_findings`. Add the altitude group to that merge without changing the existing groups' ids, sources, or ordering assumptions.

- **Handle misplaced model output defensively.** The prompt should say where to place the advisory block, but `plan_tool/detail.py` should strip or parse the advisory block before calling `_claude_recommendations` so an advisory bullet cannot be absorbed into a normal MEDIUM/NIT finding if the model places blocks in the wrong order. The existing structural-block strip around `plan_tool.detail:_STRUCTURAL_BLOCK_RE` is the closest local pattern.

## Tests

- `tests/test_detail.py::TestRenderDetailQualityPrompt::test_quality_prompt_includes_advisory_altitude_contract` — the rendered prompt asks for advisory altitude findings, says to demote rather than delete, and preserves the final `## Findings` requirement.
- `tests/test_detail.py::TestCollectDetailQualityFindings::test_advisory_altitude_block_returns_detail_altitude_rec` — an advisory altitude block produces one `source="detail-altitude"` recommendation with `severity="info"` and `step_id` set.
- `tests/test_detail.py::TestCollectDetailQualityFindings::test_advisory_altitude_block_not_lifted_as_claude_finding` — advisory bullets do not appear as `source="claude"` recommendations.
- `tests/test_detail.py::TestCollectDetailQualityFindings::test_misordered_advisory_block_never_leaks_into_findings` — advisory output before or after the normal findings block stays separate from normal findings.
- `tests/test_detail.py::TestDetailQualityIterationLoop::test_advisory_altitude_findings_are_not_dispatched_to_apply_finding` — the convergence loop reports the advisory finding but does not call `apply_finding` for it.
- `tests/test_review.py::TestApplyTriage::test_detail_altitude_source_not_apply_eligible` — `is_apply_eligible` is false for the new source.
- `tests/test_review.py::TestApplyTriage::test_detail_altitude_deferred_even_with_include_info` — `partition_findings_for_triage(..., include_info=True)` still leaves the advisory finding in the deferred bucket.
- `tests/test_review.py::TestApplyTriage::test_detail_altitude_triage_reason_names_advisory_altitude` — `triage_reason` gives a clear advisory altitude reason, not the generic structural diagnostic text.
- Shared regression fixture — use the same plan/detail example as step 3, with brittle mechanical detail demoted to examples and one recurring concept phrase kept stable across steps.

### Test-creation order (feature step)

This is a **feature** step. Add the tests above with the implementation so the new advisory lane is covered as it is introduced. Every new test in `tests/test_detail.py` and `tests/test_review.py` must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/prompts/detail-quality.md` tells the reviewer to flag over-prescriptive mechanical detail as advisory conceptual-altitude findings.
- `plan_tool/prompts/detail-quality.md` says exact specificity remains valid when it is the required constraint, real anchor, failure mode, rejected alternative, or acceptance check.
- `plan_tool/detail.py:collect_detail_quality_findings` returns advisory altitude recommendations from the detail-quality response.
- Advisory altitude recommendations use a source that is not `claude`, have `severity="info"`, and carry the reviewed step id.
- Advisory altitude recommendations are absent from `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` and `plan_tool/review.py:STRUCTURAL_SOURCES`.
- `plan_tool/review.py:partition_findings_for_triage` defers advisory altitude recommendations even when `include_info=True`.
- A misordered advisory altitude block does not leak into normal Claude findings.
- The altitude tests include the shared plan/detail regression fixture that also exercises stable recurring concept wording.
- `pytest tests/test_detail.py tests/test_review.py` passes.

## References

- [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Use for keeping the prompt instructions explicit, structured, and narrow.
- [pytest: Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use for before/after and block-order variants without duplicated tests.
- [pytest: Assertions in Tests](https://docs.pytest.org/en/stable/how-to/assert.html) — Use for clear assertions around recommendation source, severity, and triage buckets.
- [Python re Module Reference](https://docs.python.org/3/library/re.html) — Use if the advisory block parser follows the existing regex-based block parsing style.

## Deferred

- Plan-wide concept phrase consistency — step 3 owns `plan_tool/review.py`, `plan_tool/prompts/plan-audit.md`, and `tests/test_review.py` changes for recurring concept wording across steps.
- Auto-rewriting detail prose — out of scope for this plan; altitude findings must stay advisory and require human judgment.
- Changing feature ownership semantics — out of scope; feature IDs and `step.features` remain the ownership mechanism, while this step only adds detail-quality advice.
