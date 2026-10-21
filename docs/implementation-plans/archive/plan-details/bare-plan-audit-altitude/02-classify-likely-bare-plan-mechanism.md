> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Classify likely bare-plan mechanism findings from persisted recommendation text

## Summary

Add a conservative, deterministic classifier for likely internal delivery-mechanism requests in `plan_tool/review.py`, and carry its derived result into saved-report history through `plan_tool/convergence_diagnosis.py`. Update `tests/test_review.py` and `tests/test_convergence_diagnosis.py` to prove the classifier uses only persisted finding text and stays separate from enforcement. The key decision is that explicit property, route, and observable-contract language always wins over a mechanism match. On green, later advisory work can read a stable per-finding signal without changing any blocking, continuation, or exit behavior.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing stable signal for operators.
- [Input](#input) — The persisted finding and history contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing modules and tests to change.
- [Implementation](#implementation) — The classifier rule and history handoff.
- [Tests](#tests) — Unit and history coverage for the new signal.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Primary references for deterministic matching and tests.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that keep the signal advisory.
- [Deferred](#deferred) — Advisory presentation and measurement work left to later steps.

## Why

Step 1 establishes which bare-plan findings belong to a named property versus an unselected delivery choice, but saved reports currently have no stable way to point an operator at a likely mechanism-only correctness finding. A deterministic classifier over the finding text provides that signal without trusting a model-generated label or weakening the existing correctness bar.

## Input

- **Step 1 policy boundary:** Step 1 supplies the settled property-versus-mechanism rule and the two-stage replay cases this classifier must reflect.
- **Persisted recommendation text:** `plan_tool/review.py:Recommendation` supplies `title`, `body`, and optional `suggested_action`; `plan_tool/review_persistence.py:save_review()` and `load_review()` already round-trip those fields.
- **History handoff:** `plan_tool/convergence_diagnosis.py:_finding_from_recommendation()` converts a loaded `Recommendation` into `RunFinding`, which is the suitable place to retain a derived advisory signal for later convergence work.
- **Verification limit:** Unit tests can prove identical stored text produces the same result. They cannot measure how often a future conceptual audit writes mechanism-shaped prose.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Add the pure recommendation-text classifier beside `classify_finding_domain()`.
  - `plan_tool/convergence_diagnosis.py` — Add a derived `RunFinding` signal and populate it in `_finding_from_recommendation()`.
  - `tests/test_review.py` — Cover positive, protected, ambiguous, and repeatable classifier cases.
  - `tests/test_convergence_diagnosis.py` — Cover the recommendation-to-history handoff and prove the signal does not affect diagnosis behavior in this step.

## Implementation

- **Foundational logic: conservative text-only mechanism classification.** Add a dedicated helper, such as `classify_likely_bare_mechanism()`, that reads only `Recommendation.title`, `Recommendation.body`, and `Recommendation.suggested_action`. It must not inspect the plan, detail files, repository state, audit stage, annotations, or a new model response.

- **Require a clear internal-delivery request for a positive result.** Classify text only when it asks for an implementation choice such as an attachment, carrier, rewrite, parser arrangement, fixture shape, serializer choice, or similar detail-owned delivery mechanism.

- **Protect plan-level obligations first.** Return the unlabelled result when the same text states a named property, route-coverage obligation, or an explicit compatibility, safety, ordering, ownership, or bypass contract. Do not treat a mechanism word alone as enough to override an observable commitment.

- **Leave uncertainty unlabelled.** Ambiguous prose must produce the same unlabelled result as protected text. A false positive would tell an operator to defer a real plan-level defect, so prefer a small, explainable positive set over broad keyword matching.

- **Keep this separate from domain classification.** `plan_tool/review.py:classify_finding_domain()` is a related text-reading helper, but its result reaches the existing blocking policy. Do not extend its vocabulary, domains, precedence, or consumers for this feature. The new classifier should remain an independent advisory signal.

- **Carry a derived signal, not a new persisted schema field.** Extend `plan_tool/convergence_diagnosis.py:RunFinding` with a clearly named boolean derived from the loaded recommendation, with a safe default for direct test construction. Set it in `_finding_from_recommendation()` using the new classifier. Keep `Recommendation` and the `plan_tool/review_persistence.py` sidecar shape unchanged; persisted text remains the source from which the signal is recomputed.

- **Reserve eligibility and presentation for later steps.** This step only makes the signal available. Step 3 decides which open bare `plan-correctness` findings qualify, combines matching `edit_drift` evidence, and renders advice. Do not add advisory lines to `diagnose_convergence()` or `render_diagnosis()` here.

- **Keep enforcement untouched.** Do not pass the new signal to `plan_tool/convergence.py:is_blocking_finding()`, `is_blocking_impact()`, `should_continue()`, or completeness result handling. A positive classification must have no effect until an operator reads the later advisory.

## Tests

### Tests for this step

- `test_classify_likely_bare_mechanism_labels_internal_delivery_choice` — verifies a persisted request for an internal delivery choice receives the positive label.
- `test_classify_likely_bare_mechanism_rejects_named_property_or_route_coverage` — verifies a named property or missing route remains unlabelled even when the prose mentions a possible mechanism.
- `test_classify_likely_bare_mechanism_rejects_explicit_observable_contract` — verifies parametrized compatibility, safety, ordering, ownership, and bypass contracts remain unlabelled.
- `test_classify_likely_bare_mechanism_leaves_ambiguous_text_unlabelled` — verifies uncertain prose does not receive a guessed label.
- `test_classify_likely_bare_mechanism_is_repeatable_for_identical_persisted_text` — verifies repeated calls with the same title, body, and suggested action return the same result.
- `test_classify_likely_bare_mechanism_ignores_nontext_recommendation_metadata` — verifies identifiers, severity, source, step, anchor, and path metadata cannot change a text-only result.
- `test_finding_from_recommendation_carries_likely_bare_mechanism_signal` — verifies `_finding_from_recommendation()` records the classifier result on `RunFinding`.
- `test_loaded_history_recomputes_likely_bare_mechanism_from_saved_recommendation_text` — verifies a saved and reloaded recommendation produces the expected derived history signal without a sidecar schema addition.
- `test_diagnosis_ignores_likely_bare_mechanism_signal_until_advisory_step` — verifies otherwise identical history produces the same convergence and blocking result whether the derived signal is true or false.

Every listed test and the affected existing tests must be green before this step is complete:

`uv run pytest tests/test_review.py tests/test_convergence_diagnosis.py -q`

## Acceptance criteria

- The classifier reads only persisted recommendation text and returns the same result for identical text on repeated calls.
- A clear internal delivery-mechanism request receives the positive label.
- A named property, route obligation, explicit observable contract, or ambiguous request remains unlabelled.
- `plan_tool/convergence_diagnosis.py:RunFinding` carries the derived signal from `_finding_from_recommendation()` without adding a field to `plan_tool/review.py:Recommendation` or its saved-review schema.
- `classify_finding_domain()` and all existing blocking and continuation predicates remain unchanged.
- `uv run pytest tests/test_review.py tests/test_convergence_diagnosis.py -q` passes.

## References

- [re — Regular expression operations — Python 3.13 documentation](https://docs.python.org/3.13/library/re.html) — Use for deterministic, bounded text matching if regular expressions fit the final classifier.
- [dataclasses — Data Classes — Python 3.13 documentation](https://docs.python.org/3.13/library/dataclasses.html) — Use for the derived immutable `RunFinding` field.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use for the protected contract and ambiguous-text matrix.
- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use when proving the new classifier cannot enter existing enforcement paths.

## Applicable guardrails

- **The plan’s “## Plan intent”, deterministic enforcement:** Keep the classifier deterministic and advisory-only; no blocking decision may read its result.
- **The plan’s “## Step intent”, conservative classification:** Do not label named properties, route obligations, explicit observable contracts, or ambiguous text.
- **The plan’s “## Out of scope”, enforcement behavior:** Do not add a response field, automatic deferral or apply behavior, exit-code path, or new gate.
- **The plan’s “## Out of scope”, existing audit policy:** Do not change blocking predicates, convergence continuation, failure behavior, audit-pass behavior, or the detail-grounded bar.
- **The plan’s “## Out of scope”, domain and provenance policy:** Keep `classify_finding_domain()` unchanged and do not infer causality from an eventual `edit_drift` match.
- **The plan’s “## Risks”, conservative policy boundary:** Prefer an unlabelled result whenever the persisted text does not prove a detail-only mechanism request.

## Deferred

- **Eligibility, `edit_drift` composition, and convergence rendering** — Step 3 consumes this derived signal for completed bare-plan findings and presents the operator guidance.
- **Completeness stderr and grade-specific presentation** — Step 4 owns the run-grade output surface and preserves Jira-grade suppression.
- **Live-audit hit-rate measurement** — Unit cases prove deterministic classification, not real-model wording frequency.
