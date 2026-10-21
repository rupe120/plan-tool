> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make every low-risk audit pass replace ceremony with at most one tier-challenge

## Summary

Make the conceptual audit consume the shared low-risk directives block in `plan_tool/review.py:render_plan_audit_prompt` and apply its ceremony-replacement rule on every pass. Update `plan_tool/prompts/plan-audit.md` so declared-low plans do not emit unlisted ceremony requests, retain ordinary grounded correctness review, and raise no more than one manual `tier-challenge` when evidence refutes the tier. Add focused prompt, response, and fixture coverage in `tests/test_review.py` and `tests/test_risk_profile_honoring.py`, then document the low-risk audit path in `docs/AUDIT_FLOW.md`. On green, standard, high, and undeclared plans render the same audit prompt as before.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the audit-policy change.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why low-risk audits currently create ceremony churn.
- [Input](#input) — Upstream directive and manual-finding contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Planned code, documentation, fixture, and test changes.
- [Implementation](#implementation) — Required low-risk prompt and finding behavior.
- [Tests](#tests) — Prompt, response, and fixture coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for prompt substitution and test coverage.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this audit-only change.
- [Deferred](#deferred) — Work outside this step.

## Why

`plan_tool/review.py:render_plan_audit_prompt` currently gives every plan the same conceptual-audit instructions, so a declared-low plan can receive several findings that ask for procedure its tier deliberately leaves out. Step 1 supplies the policy block and step 3 supplies the manual finding route; this step joins them at the audit boundary so the audit selects the tier-appropriate result: an explicit ceremony requirement stays visible, an unlisted ceremony request is replaced by the one challenge, and unrelated design defects still report. This preserves the audit gate rather than bypassing it.

## Input

- **Step 1 directives:** Consume `plan_tool/plan_directives.py:render_low_risk_directives(plan, plan_path, *, plan_body=None)`. Its nonempty result is the only signal that a plan has an explicit low declaration; do not infer low risk from ordinary prose, scope-fence text, or legacy default behavior.

- **Step 3 manual finding:** Preserve the shared `tier-challenge` identity and its fixed `standard` minimum through `plan_tool/review.py:_parse_plan_audit_findings_with_evidence` and `check_plan_audit`. Step 3 owns explicit-low evidence admission, severity, blocking, report, and the non-success manual-resolution result.

- **Audit sampling contract:** Keep `plan_tool/review.py:audit_plan_until_stable`’s stable-anchor union and `AuditInputSnapshot` behavior intact. Every pass in one sampled audit receives its directive authorization from that same captured plan body, not from live guardrails. Step 3 owns the sole union exception: the recognized manual challenge merges its typed evidence collection across otherwise duplicate passes; ordinary findings remain first-occurrence records.

- **Prompt rendering contract:** `plan_tool/review.py:render_plan_audit_prompt` uses `string.Template.safe_substitute` over `plan_tool/prompts/plan-audit.md`; an empty directive block must leave no added heading, instruction, or blank-line drift.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/risk_profile/lean-plan.md` — Declared-low plan with no named counter-signal or ceremony authorization.
  - `tests/fixtures/risk_profile/lean-named-consumer-plan.md` — Declared-low plan whose named consumer provides challenge evidence.
  - `tests/test_risk_profile_honoring.py` — Fixture-driven coverage of low-risk audit behavior.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Render the shared directive block into conceptual-audit prompts, account for its bytes, keep each low-risk pass to one evidence-preserving challenge, and supply the challenge evidence shape step 3 aggregates.
  - `plan_tool/prompts/plan-audit.md` — Add the optional audit-context slot and low-risk audit instructions without changing the empty-block render.
  - `docs/AUDIT_FLOW.md` — Describe low-risk ceremony replacement in the conceptual-audit flow and update the relevant source-map entry.
  - `tests/test_review.py` — Cover prompt placement, empty-block compatibility, budget accounting, and challenge coalescing.

## Implementation

- **Foundational logic:** For an explicitly low plan, replace unlisted ceremony requests with at most one evidence-backed `tier-challenge` while keeping the audit gate active.

- **Consume one policy source.** Have `plan_tool/review.py:render_plan_audit_prompt` obtain the block from step 1’s `render_low_risk_directives`, passing `audit_input_snapshot.plan_body` whenever a snapshot is supplied. A direct non-snapshot render may use the live-path wrapper. Keep ceremony vocabulary, authorization rules, and the proposed minimum in `plan_tool/plan_directives.py`; this step must not duplicate or shorten that policy in `plan_tool/prompts/plan-audit.md`.

- **Keep the block optional.** Insert the rendered block through a template slot that disappears completely when empty. Standard, high, and undeclared plans must retain their current rendered prompt text, including whitespace and the stable prefix used across repeated audit passes.

- **Make low-only policy classification machine-readable.** Require every low-tier audit candidate to carry exactly one trailing marker: `[risk-profile:non-ceremony]`, `[risk-profile:ceremony:<canonical-id>]`, or `[risk-profile:tier-challenge]`. The shared policy module owns the canonical ceremony identifiers; prompt prose must not introduce aliases. The marker is response metadata, not a new finding kind or a change to non-low output.

- **Make the audit decision explicit.** In the low-only prompt context, require the auditor to:
  - treat an explicitly authorized ceremony as a plan requirement rather than replacing it;
  - omit findings that demand an unlisted ceremony-class procedure;
  - examine named consumers, live surfaces, credentials, and equivalent repository evidence as possible reasons the declared tier is wrong;
  - emit one `tier-challenge` that lists each contradiction in the dedicated evidence sub-list and proposes the shared standard minimum when that evidence refutes low risk; and
  - retain unrelated non-ceremony correctness findings.

- **Normalize policy before routing.** Before report, persistence, blocking, or apply eligibility sees a low-tier candidate, validate its marker against the rendered authorization list. Keep `non-ceremony` and authorized `ceremony:<id>` candidates as ordinary findings; discard an unlisted `ceremony:<id>` request; and send only `tier-challenge` candidates to step 3’s evidence admission. Do not use prompt compliance alone to decide whether an unauthorized ceremony reaches an apply writer.

- **Recover malformed classification without downgrading safety.** A missing, repeated, unknown, or mismatched low-only marker triggers one response-format retry. If the retry remains malformed, the audit is unqualified with no routed recommendation from the malformed candidate. This response-validation path applies only to explicit-low audits; standard, high, and undeclared parsing remains unchanged.

- **Enforce one result per pass and one complete result across samples.** After policy normalization, coalesce several valid challenge candidates in a pass into one evidence-preserving manual decision. Step 3 then merges only that challenge evidence when later sampled passes reuse the same recognized challenge; it keeps the first spelling of duplicate entries, appends new evidence in pass order, and leaves every ordinary finding under `audit_plan_until_stable`'s existing first-occurrence union. Do not merge unrelated correctness findings into the challenge.

- **Keep the manual boundary.** Reuse step 3’s recognized finding transport in `plan_tool/review.py:check_plan_audit`; this step decides when the challenge is emitted, not how it is scored, blocked, saved, or applied.

- **Keep prompts auditable and within budget.** Place the dynamic block after the static audit guidance and before the plan body, alongside the other volatile inputs. Include its rendered byte size in `render_plan_audit_prompt`’s `collect_blocks` result whenever it is present so `audit_plan_until_stable` reports accurate prompt-budget data.

- **Document the behavior at the flow level.** In `docs/AUDIT_FLOW.md`’s conceptual-audit section, distinguish low-risk result selection from reduced scrutiny: the audit still tests the declaration against evidence and retains ordinary correctness findings. Point the source map at `plan_tool/review.py:render_plan_audit_prompt` and `_parse_plan_audit_findings_with_evidence`.

- **Use canned invoker responses for behavior tests.** They prove prompt content, parser handling, and finding routing, not real-model hit rate. Keep live-model calibration outside this hermetic suite.

## Tests

- `test_plan_audit_low_risk_prompt_includes_shared_directives_once` — A declared-low plan renders the shared block once with its audit-specific ceremony-replacement instruction.

- `test_plan_audit_non_low_profiles_preserve_the_empty_directive_render` — Standard, high, and undeclared plans produce the same prompt bytes as the empty-directive path.

- `test_plan_audit_low_risk_directives_follow_the_stable_prefix` — The optional block stays after static prompt guidance and before `## Plan body`.

- `test_plan_audit_collect_blocks_includes_rendered_low_risk_directives` — Prompt-budget collection reports the directive block only when it is present.

- `test_low_risk_audit_directives_freeze_guardrails_from_snapshot` — A post-capture guardrail edit cannot change a sampled audit prompt’s directives, while a non-snapshot render reflects the current detail-authoring policy.

- `test_low_risk_policy_classification_routes_authorized_unlisted_and_non_ceremony_candidates` — Parser-side policy retains authorized and non-ceremony records but discards an unlisted ceremony before report or apply routing.

- `test_low_risk_policy_classification_retries_then_leaves_malformed_response_unqualified` — Missing, repeated, or unknown policy markers retry once and never degrade into ordinary findings.

- `test_low_risk_audit_coalesces_tier_challenge_candidates` — Several challenge candidates in one low-risk response become one evidence-preserving manual challenge.

- `test_low_risk_audit_unions_challenge_evidence_across_samples` — Two sampled responses cite distinct counter-signals yet persist one challenge containing both; the ordinary duplicate control keeps its first-pass body.

- `test_lean_plan_omits_unlisted_ceremony_requests` — `tests/fixtures/risk_profile/lean-plan.md` receives the low-risk policy without a ceremony request or tier challenge.

- `test_named_consumer_plan_emits_one_tier_challenge` — `tests/fixtures/risk_profile/lean-named-consumer-plan.md` yields one high-severity challenge proposing standard.

- `test_tier_challenge_replaces_overlapping_ceremony_and_keeps_independent_correctness` — An overlapping ceremony observation is absent while an unrelated grounded correctness finding remains visible.

### Tests for this step

- `tests/test_review.py::test_plan_audit_low_risk_prompt_includes_shared_directives_once` — Pins the only prompt-policy source and placement.

- `tests/test_review.py::test_plan_audit_non_low_profiles_preserve_the_empty_directive_render` — Pins byte-identical behavior outside declared low risk.

- `tests/test_review.py::test_plan_audit_low_risk_directives_follow_the_stable_prefix` — Keeps prompt caching and repeated-pass layout intact.

- `tests/test_review.py::test_plan_audit_collect_blocks_includes_rendered_low_risk_directives` — Pins prompt-budget accounting.

- `tests/test_review.py::test_low_risk_audit_directives_freeze_guardrails_from_snapshot` — Pins capture-time authorization across sampled audit passes and the live detail-authoring boundary.

- `tests/test_review.py::test_low_risk_policy_classification_routes_authorized_unlisted_and_non_ceremony_candidates` — Pins parser-side ceremony replacement before report or apply eligibility.

- `tests/test_review.py::test_low_risk_policy_classification_retries_then_leaves_malformed_response_unqualified` — Pins exact marker validation, one retry, and the fail-closed result.

- `tests/test_review.py::test_low_risk_audit_coalesces_tier_challenge_candidates` — Pins the one-challenge-per-pass rule and preserved evidence.

- `tests/test_review.py::test_low_risk_audit_unions_challenge_evidence_across_samples` — Pins the cross-sample evidence union and ordinary-union boundary.

- `tests/test_risk_profile_honoring.py::test_lean_plan_omits_unlisted_ceremony_requests` — Covers the lean fixture’s no-ceremony-request path.

- `tests/test_risk_profile_honoring.py::test_named_consumer_plan_emits_one_tier_challenge` — Covers the named-consumer challenge path.

- `tests/test_risk_profile_honoring.py::test_tier_challenge_replaces_overlapping_ceremony_and_keeps_independent_correctness` — Covers replacement without hiding unrelated defects.

Every listed test, plus `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A declared-low plan receives the shared directives block in every conceptual-audit pass.

- An unlisted ceremony-class procedure does not produce a ceremony request for a declared-low plan; the audit still reports a tier challenge when evidence contradicts that declaration.

- Every low-tier candidate is classified by the shared policy before routing: authorized ceremony and independent non-ceremony findings remain reportable, while an unlisted ceremony never reaches persistence or an apply writer.

- Evidence that refutes low risk produces one high-severity manual `tier-challenge` proposing the shared standard minimum, with every cited contradiction retained across sampled passes.

- An explicitly authorized ceremony remains subject to normal audit scrutiny.

- Unrelated non-ceremony correctness findings remain reportable alongside a tier challenge.

- Standard, high, and undeclared plans render the same conceptual-audit prompt bytes as the empty-directive path.

- Prompt-budget reporting includes rendered low-risk directives.

- Every sampled audit pass derives directive authorization from its captured plan body; post-capture live guardrail edits affect only non-snapshot detail-authoring routes.

- A malformed low-only policy classification retries once then leaves the audit unqualified; it cannot weaken to an ordinary applyable finding.

- The focused tests in `tests/test_review.py` and `tests/test_risk_profile_honoring.py` pass.

## References

- [string — Common string operations](https://docs.python.org/3.13/library/string.html#template-strings-strings) — Review `Template.safe_substitute` behavior for an optional prompt block.

- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Review heading and list rules used by the machine-parsed audit response.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover declared and undeclared profile variants without repeating fixture setup.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep the audit proportionate while retaining evidence-based review of a declared tier.

- **The plan’s “## Step intent”** — Limit the behavior change to the standard-minimum challenge policy and preserve scrutiny of counter-signals.

- **The plan’s “## Out of scope”** — Leave declaration, general correctness policy, and non-completeness command behavior unchanged; step 3's existing direct-pipeline stop remains the manual-resolution boundary.

- **The plan’s scope contract, allowed behavior changes** — Restrict this step to tier-conditioned audit context and the established finding kind.

- **The plan’s scope contract, allowed reorganization** — Do not turn prompt wiring into a broader audit-pipeline refactor.

## Deferred

- Tier-aware behavior outside conceptual completeness audit — The plan’s “## Out of scope” reserves those surfaces for follow-up work.

- Risk-tier classification and general correctness scoring — The plan assigns those decisions outside this step.

- Real-model calibration — Canned responses prove the prompt and routing contract; production hit-rate measurement needs a separate representative corpus.
