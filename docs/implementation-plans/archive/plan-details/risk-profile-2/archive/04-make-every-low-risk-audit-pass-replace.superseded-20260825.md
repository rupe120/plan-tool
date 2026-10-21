> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make every low-risk audit pass replace ceremony with at most one tier-challenge

## Summary

Make `plan_tool/review.py` provide step 1’s shared low-risk directives to every conceptual-audit prompt and enforce the resulting finding policy before recommendations reach reports or apply routing. Update `plan_tool/prompts/plan-audit.md`, `docs/AUDIT_FLOW.md`, and focused fixture-driven tests. The key decision is that low risk suppresses unlisted ceremony requests but never hides evidence that the declared tier is wrong. On green, an explicit-low audit pass produces at most one manual `tier-challenge`, while standard, high, and undeclared plans keep their current prompt text.

## Table of Contents

- [Summary](#summary) — The audit-policy result.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why ceremony findings need tier-aware handling.
- [Input](#input) — Upstream directive, challenge, and snapshot contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Code, prompt, documentation, fixture, and test work.
- [Implementation](#implementation) — Required prompt, parsing, and routing behavior.
- [Tests](#tests) — Focused prompt and finding-policy coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant primary references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries for this audit-only change.
- [Deferred](#deferred) — Work outside the completeness-audit path.

## Why

`plan_tool/review.py:render_plan_audit_prompt` currently gives every plan the same conceptual-audit instructions, so an explicit low declaration can still yield several requests for procedure it intentionally excludes. Step 1 supplies the policy and step 3 supplies the manual challenge route; this step connects them at the audit boundary. The audit stays rigorous by dropping only unlisted ceremony requests, preserving independent correctness findings, and raising one evidence-backed question when repository evidence contradicts the tier.

## Input

- **Step 1 directives:** Use `render_low_risk_directives` in `plan_tool/plan_directives.py` as the only source of ceremony classes and eligible authorizations. Do not infer low risk from prose, guardrail wording, or the `Plan.effective_risk_profile` fallback.

- **Explicit declaration:** Use the `risk_profile` field of `plan_tool/schema.py:Plan` to select the low-risk path. An absent declaration remains ordinary behavior.

- **Step 3 challenge route:** Reuse the `tier-challenge` identity, evidence shape, fixed `standard` minimum, blocking result, and manual-only disposition from step 3. This step controls when the challenge is emitted, not how reports or apply routes resolve it.

- **Frozen audit input:** Preserve `plan_tool/review_persistence.py:AuditInputSnapshot`. During sampled audits, directives must come from the captured plan body rather than a later on-disk guardrail edit.

- **Current audit path:** Keep `plan_tool/review.py:check_plan_audit`, `_parse_plan_audit_findings_with_evidence`, and `audit_plan_until_stable` as the conceptual-audit path. Ordinary findings retain their stable-anchor, first-occurrence behavior.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/risk_profile/lean-plan.md` — Explicit-low plan with no repository counter-signal.
  - `tests/fixtures/risk_profile/lean-named-consumer-plan.md` — Explicit-low plan with named-consumer evidence that challenges the tier.
  - `tests/test_risk_profile_honoring.py` — Fixture-driven low-risk audit behavior tests.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Render directives, validate low-risk response metadata, coalesce challenge candidates, preserve captured inputs, and account for embedded prompt bytes.
  - `plan_tool/prompts/plan-audit.md` — Add the conditional low-risk audit contract.
  - `docs/AUDIT_FLOW.md` — Describe proportional low-risk result selection and update `## Source map`.
  - `tests/test_review.py` — Cover prompt rendering, parser validation, retry behavior, captured inputs, and sampled-pass aggregation.

## Implementation

- **Foundational logic:** For an explicit-low plan, replace unlisted ceremony requests with at most one evidence-backed `tier-challenge` without weakening unrelated conceptual review.

- **Render the shared policy once.** Update `plan_tool/review.py:render_plan_audit_prompt` to use step 1’s renderer. Pass the captured plan body when `AuditInputSnapshot` is present; a live invocation may use the current plan body. Keep ceremony vocabulary and authorization parsing in `plan_tool/plan_directives.py`.

- **Keep non-low output unchanged.** Add an optional slot in `plan_tool/prompts/plan-audit.md` that adds neither text nor extra whitespace when directives are empty. Standard, high, and undeclared plans must retain their empty-directives prompt bytes.

- **Put policy before the plan body.** Render low-risk instructions with the other stable audit guidance before `## Plan body`, so every sampled pass sees the same policy before it evaluates plan and detail content.

- **Require low-risk metadata.** When directives are present, require each candidate finding to carry exactly one trailing policy marker: `[risk-profile:non-ceremony]`, `[risk-profile:ceremony:<canonical-id>]`, or `[risk-profile:tier-challenge]`. Use the shared authorization list to distinguish authorized ceremony from an unlisted request.

- **Preserve the response parser’s severity contract.** Low-risk candidates may use only the severity tokens recognized by `plan_tool/launcher.py:parse_finding_bullets`: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, and `NIT`. Treat `INFO` or an unrecognized severity as malformed low-risk output, rather than allowing it through ordinary parsing.

- **Validate before creating recommendations.** Extend `plan_tool/review.py:_parse_plan_audit_findings_with_evidence` and its `check_plan_audit` caller so malformed, repeated, unknown, or inconsistent low-risk markers trigger the existing one-retry response-format boundary. A second malformed response leaves the pass unqualified and creates no ordinary recommendation.

- **Apply the policy at the finding boundary.** Retain independent non-ceremony findings and authorized ceremony concerns. Drop unlisted ceremony requests before reporting, persistence, blocking checks, or apply eligibility.

- **Challenge the tier, not each ceremony request.** Require a valid `[risk-profile:tier-challenge]` candidate to use step 3’s `Evidence:` record shape. Coalesce all valid challenge candidates in one response into one manual challenge, retaining distinct evidence in first-seen order; an overlapping ceremony request must not produce a second recommendation.

- **Preserve cross-pass behavior.** Let step 3’s challenge transport merge additional evidence across `plan_tool/review.py:audit_plan_until_stable` samples. Keep the current first-occurrence union for every ordinary finding.

- **Keep prompt-budget data accurate.** Add the rendered directives block to `render_plan_audit_prompt`’s `collect_blocks` output only when the block is actually embedded.

- **Document the boundary by behavior.** In `docs/AUDIT_FLOW.md`, state that low risk changes ceremony result selection, not the audit’s duty to test the declaration against repository evidence. Update `## Source map` to name the prompt and parser-side policy route.

## Tests

### Tests for this step

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_prompt_renders_shared_directives_once` — An explicit-low declaration renders the shared policy once before `## Plan body`.

- `tests/test_review.py::TestCheckPlanAudit::test_non_low_profiles_keep_empty_directives_prompt_bytes` — Standard, high, and undeclared plans match the empty-directives prompt.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_snapshot_uses_captured_plan_body_for_directives` — A guardrail edit after capture cannot change a later sampled prompt.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_directives_are_in_prompt_budget_blocks` — Prompt-budget collection includes directive bytes only when directives render.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_policy_keeps_authorized_ceremony_and_non_ceremony_findings` — Authorized ceremony and independent findings remain ordinary audit findings.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_policy_drops_unlisted_ceremony_before_recommendation_routing` — An unlisted ceremony request cannot reach a report or applyable recommendation.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_malformed_policy_output_retries_then_is_unqualified` — Invalid or repeated policy metadata gets one retry and never becomes an ordinary finding.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_info_candidate_retries_then_is_unqualified` — A low-risk `INFO` candidate cannot bypass the severity contract.

- `tests/test_review.py::TestCheckPlanAudit::test_low_risk_pass_coalesces_tier_challenge_evidence` — Several tier-refuting candidates in one response become one challenge with all valid evidence.

- `tests/test_review.py::TestAuditPlanUntilStable::test_low_risk_challenge_unions_evidence_across_samples` — Separate sampled responses retain one challenge with aggregated evidence while an ordinary duplicate keeps its first wording.

- `tests/test_risk_profile_honoring.py::test_lean_plan_omits_unlisted_ceremony_requests` — `tests/fixtures/risk_profile/lean-plan.md` yields neither an unlisted ceremony request nor a tier challenge.

- `tests/test_risk_profile_honoring.py::test_named_consumer_plan_emits_one_tier_challenge` — `tests/fixtures/risk_profile/lean-named-consumer-plan.md` yields one manual high-severity challenge proposing `standard`.

- `tests/test_risk_profile_honoring.py::test_tier_challenge_keeps_independent_correctness_visible` — Replacing overlapping ceremony requests does not hide an unrelated correctness finding.

Every listed test, plus `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- Every explicit-low conceptual-audit pass receives step 1’s shared directives from the same plan body the pass audits.

- Standard, high, and undeclared plans render the same conceptual-audit prompt bytes as the empty-directives path.

- An unlisted ceremony request never reaches reporting, persistence, blocking, or an apply writer for an explicit-low plan.

- An authorized ceremony concern remains eligible for ordinary audit scrutiny.

- Tier-refuting repository evidence produces at most one manual `tier-challenge` per pass and one aggregated challenge across sampled passes.

- The challenge preserves concrete contradiction evidence and the `standard` minimum supplied by step 3.

- Independent non-ceremony correctness findings remain visible beside a tier challenge.

- Malformed low-risk metadata or an unsupported low-risk severity retries once, then makes the pass unqualified without producing an ordinary recommendation.

- `docs/AUDIT_FLOW.md` describes the low-risk result-selection rule and its source map names the changed audit anchors.

## References

- [string — Template strings](https://docs.python.org/3.13/library/string.html#template-strings-strings) — Use an optional `Template` value without leaving unresolved placeholders.

- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Check explicit model fields when selecting the low-risk branch.

- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Reference heading and list rules for the machine-parsed audit response.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover profile variants without repeating fixture setup.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep low-risk work proportionate while retaining evidence-based scrutiny of the declaration.

- **The plan’s “## Step intent”** — Preserve the one standard-minimum challenge boundary for repository evidence that refutes low risk.

- **The plan’s “## Out of scope”** — Do not change risk classification, general correctness scoring, or non-audit command behavior.

- **The plan’s scope contract, allowed behavior changes** — Limit changes to tier-conditioned audit context and step 3’s existing challenge kind.

- **The plan’s scope contract, allowed reorganization** — Keep work within the current audit rendering and parsing path.

## Deferred

- Tier-aware `reconcile`, `run`, `jira`, and `annotate` behavior — The plan’s “## Out of scope” reserves those surfaces for follow-up work.

- Risk-profile classification and frontmatter changes — These belong to the related declaration work.

- Detail-writing route changes — Step 2 owns authoring and rewrite prompt behavior.

- Real-model calibration — Canned responses verify prompt and routing contracts; hit-rate measurement needs a representative external corpus.
