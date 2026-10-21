> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make every low-risk audit pass replace ceremony with at most one tier-challenge

## Summary

Make `plan_tool/review.py` pass step 1’s low-risk directives into every conceptual-audit prompt and enforce the resulting finding policy before findings reach reports or apply routing. Update `plan_tool/prompts/plan-audit.md` with an explicit low-risk response contract, add fixture-driven coverage, and document the behavior in `docs/AUDIT_FLOW.md`. The key decision is that low risk suppresses unlisted ceremony requests but never suppresses evidence that the declared tier is wrong. On green, each low-risk audit pass yields at most one manual `tier-challenge`, while standard, high, and undeclared plans render the same prompt bytes as today.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the audit-policy change.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why low-risk audits need tier-aware result selection.
- [Input](#input) — Upstream directive, finding, and snapshot contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Code, prompt, documentation, fixture, and test work.
- [Implementation](#implementation) — Required prompt, parsing, and routing behavior.
- [Tests](#tests) — Focused prompt and finding-policy coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant primary documentation.
- [Applicable guardrails](#applicable-guardrails) — Boundaries for this step.
- [Deferred](#deferred) — Work left outside the audit path.

## Why

`plan_tool/review.py:render_plan_audit_prompt` gives every plan the same conceptual-audit instructions, so an explicit low declaration can still produce several findings asking for ceremony the declaration intentionally excludes. Step 1 supplies the policy and step 3 supplies the manual challenge route; this step connects them at the audit boundary. The audit must remain rigorous: it omits unlisted ceremony requests, preserves ordinary correctness findings, and asks for a manual tier decision when repository evidence contradicts low risk.

## Input

- **Step 1 shared directives:** Consume the shared low-risk directives outcome from step 1. It is the only source of ceremony classes and eligible authorizations; do not infer a low tier from plan prose, guardrail wording, or the `Plan.effective_risk_profile` fallback.

- **Explicit declaration:** Use the `risk_profile` field of `plan_tool/schema.py:Plan` to select the low-risk path. An absent declaration remains ordinary behavior.

- **Step 3 manual finding:** Reuse step 3’s recognized `tier-challenge` transport, evidence shape, fixed standard minimum, blocking behavior, and manual-only disposition. This step decides when the challenge is produced, not how downstream reports or apply routes resolve it.

- **Frozen audit inputs:** Preserve `plan_tool/review_persistence.py:AuditInputSnapshot` behavior. `plan_tool/review.py:render_plan_audit_prompt` must render directives from the captured plan body during sampled audits, rather than reading changed guardrails from disk on later passes.

- **Existing audit flow:** Keep `plan_tool/review.py:check_plan_audit`, `_parse_plan_audit_findings_with_evidence`, and `audit_plan_until_stable` as the conceptual-audit path. Preserve the stable-anchor union for ordinary findings.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/risk_profile/lean-plan.md` — An explicit-low plan with no counter-signal.
  - `tests/fixtures/risk_profile/lean-named-consumer-plan.md` — An explicit-low plan with named-consumer evidence that challenges the tier.
  - `tests/test_risk_profile_honoring.py` — Fixture-driven low-risk audit behavior tests.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Render directives, validate low-risk response classification, coalesce challenges, preserve frozen inputs, and account for prompt bytes.
  - `plan_tool/prompts/plan-audit.md` — Add an optional low-risk audit contract that disappears fully for non-low plans.
  - `docs/AUDIT_FLOW.md` — Describe proportional low-risk audit behavior and update `## Source map`.
  - `tests/test_review.py` — Cover prompt rendering, snapshot behavior, parser validation, retry handling, and sampled-pass aggregation.

## Implementation

- **Foundational logic:** For an explicit-low plan, replace unlisted ceremony requests with at most one evidence-backed `tier-challenge` without weakening unrelated conceptual review.

- **Render one shared policy block.** Update `plan_tool/review.py:render_plan_audit_prompt` to consume step 1’s directives renderer. Pass the captured body when `AuditInputSnapshot` is present; the non-snapshot path may use the live plan body. Keep the policy vocabulary and authorization parsing in step 1’s module.

- **Keep non-low prompts unchanged.** Add an optional template slot in `plan_tool/prompts/plan-audit.md` that contributes no text or whitespace when directives are absent. Standard, high, and undeclared plans must retain the same rendered prompt bytes and stable prompt prefix.

- **Place policy before volatile plan input.** Render the low-risk instructions with the other audit guidance before `## Plan body`, so every sampled pass receives the same policy before it evaluates the body and detail bundle.

- **Require a parseable low-risk classification.** When the directives block is present, require each candidate finding to carry exactly one trailing marker: `[risk-profile:non-ceremony]`, `[risk-profile:ceremony:<canonical-id>]`, or `[risk-profile:tier-challenge]`. The shared authorization list distinguishes an authorized from an unlisted ceremony identifier. Keep this metadata out of non-low responses and use the shared canonical identifiers rather than prompt-local aliases.

- **Use the parser's complete low-only grammar.** Low-only candidates may use only `CRITICAL`, `HIGH`, `MEDIUM`, `NIT`, or `LOW`, matching `plan_tool/launcher.py:parse_finding_bullets`; `INFO` is not a candidate severity in this response contract. A candidate that uses another severity is malformed and follows the same one-retry unqualified path as malformed policy metadata.

- **Validate before routing.** In `plan_tool/review.py:_parse_plan_audit_findings_with_evidence`, validate low-risk classifications against the rendered authorization set before a candidate becomes a `Recommendation`. Preserve independent findings and authorized ceremony concerns; drop unlisted ceremony requests before reporting, persistence, blocking, or apply eligibility.

- **Challenge the tier, not the ceremony.** When named consumers, live surfaces, credentials, or equivalent grounded evidence refute low risk, produce one recognized challenge with concrete, ordered evidence entries. Do not let an overlapping ceremony request produce a second finding. Keep unrelated non-ceremony correctness findings visible.

- **Fail closed on malformed low-only output.** Missing, repeated, unknown, or inconsistent low-risk classification must trigger one response-format retry through `check_plan_audit`. If the response remains malformed, record the pass as unqualified and do not downgrade malformed candidates into ordinary findings. Preserve current non-low parsing and required-heading recovery.

- **Preserve sampled-pass behavior.** Coalesce valid challenge candidates within a pass, then let step 3’s challenge transport aggregate distinct evidence across `audit_plan_until_stable` samples. Ordinary findings retain the existing first-occurrence union and must not be folded into the challenge.

- **Keep prompt-budget accounting honest.** Add the rendered directives block to `render_plan_audit_prompt`’s `collect_blocks` output only when present, so `audit_plan_until_stable` reports the bytes actually embedded.

- **Document proportional scrutiny.** In `docs/AUDIT_FLOW.md`’s conceptual-audit description, state that low risk changes ceremony result selection, not whether the audit tests the declaration against repository evidence. Update the `## Source map` entry for the conceptual audit to include the parser-side policy route.

## Tests

### Tests for this step

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_prompt_renders_shared_directives_once` — An explicit-low declaration renders the shared audit policy once before the plan body.

- `tests/test_review.py::TestCheckPlanAudit::test_non_low_profiles_render_the_same_prompt_bytes` — Standard, high, and absent declarations match the no-directives prompt.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_snapshot_keeps_directives_from_captured_plan_body` — A guardrail edit after capture cannot change later sampled prompts.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_directives_are_in_prompt_budget_blocks` — Budget collection includes the directive block only when it is rendered.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_policy_keeps_authorized_and_non_ceremony_findings` — Authorized ceremony and independent findings remain ordinary audit findings.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_policy_drops_unlisted_ceremony_before_routing` — An unlisted ceremony request cannot reach reports or an applyable recommendation.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_malformed_policy_output_retries_then_is_unqualified` — Invalid low-risk metadata gets one retry and never becomes an ordinary finding.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_info_candidate_retries_then_is_unqualified` — A low-only `INFO` candidate cannot be absorbed before policy routing.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_pass_coalesces_tier_challenge_evidence` — Several tier-refuting candidates in one response become one challenge with all usable evidence.

- `tests/test_review.py::TestAuditPlanUntilStable::test_low_risk_challenge_unions_evidence_across_samples` — Separate sampled responses retain one challenge and aggregate distinct evidence while an ordinary duplicate keeps its first response.

- `tests/test_risk_profile_honoring.py::test_lean_plan_omits_unlisted_ceremony_requests` — `tests/fixtures/risk_profile/lean-plan.md` receives no ceremony request or tier challenge.

- `tests/test_risk_profile_honoring.py::test_named_consumer_plan_emits_one_tier_challenge` — `tests/fixtures/risk_profile/lean-named-consumer-plan.md` yields one manual high-severity challenge proposing standard.

- `tests/test_risk_profile_honoring.py::test_tier_challenge_keeps_independent_correctness_visible` — Replacing an overlapping ceremony request does not hide an unrelated grounded correctness finding.

Every listed test, plus `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- Every explicit-low conceptual-audit pass receives the shared directives block from the same plan body the pass audits.

- Standard, high, and undeclared plans render the same conceptual-audit prompt bytes as the empty-directives path.

- An unlisted ceremony request never reaches reporting, persistence, blocking, or an apply writer for an explicit-low plan.

- An authorized ceremony concern remains eligible for ordinary audit scrutiny.

- Tier-refuting repository evidence produces no more than one manual `tier-challenge` per pass and one aggregated challenge across sampled passes.

- The challenge retains concrete contradiction evidence and the standard minimum supplied by step 3.

- Independent non-ceremony correctness findings remain visible beside a tier challenge.

- Malformed low-risk response metadata retries once, then makes the pass unqualified without creating an ordinary recommendation.

- A low-only candidate with an unsupported severity retries once, then makes the pass unqualified without creating an ordinary recommendation.

- `docs/AUDIT_FLOW.md` describes the low-risk result-selection rule and its source map names the changed audit anchors.

## References

- [string — Common string operations](https://docs.python.org/3.13/library/string.html#template-strings-strings) — Use `Template.safe_substitute` correctly for an optional prompt block.

- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Review declared-field handling for the explicit risk-profile branch.

- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Review heading and list rules for the machine-parsed audit response.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover explicit-low and non-low prompt variants without duplicating setup.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep low-risk work proportionate, but preserve evidence-based scrutiny of the declared tier.

- **The plan’s “## Step intent”** — Test the declaration against repository evidence and retain the standard-minimum challenge boundary.

- **The plan’s “## Out of scope”** — Do not change risk classification, general correctness scoring, or non-audit command behavior.

- **The plan’s scope contract, allowed behavior changes** — Limit code and prompt changes to tier-conditioned audit context and the existing challenge kind.

- **The plan’s scope contract, allowed reorganization** — Keep the change within the current audit rendering and parsing path.

## Deferred

- Tier-aware `reconcile`, `run`, `jira`, and `annotate` behavior — The plan’s “## Out of scope” reserves these surfaces for follow-up work.

- Risk-profile classification and frontmatter changes — These belong to the classifier and declaration work outside this step.

- Detail-writing route changes — Step 2 owns those prompt and rewrite paths; this step only enforces the policy during completeness audit.

- Real-model calibration — Canned responses verify prompt and routing contracts, while hit-rate measurement needs a representative external corpus.
