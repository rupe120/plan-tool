# Step 3 — Add a pure narrative-evidence function and a stored-candidate adapter

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step creates `plan_tool/roadmap_candidate_narrative.py`, a leaf-style module that computes a candidate's narrative evidence from the candidate and its predecessor artifact, both supplied by the caller. It wraps step 2's removed-id check in a pure function with no model call, no filesystem access, no loading of the predecessor, and no stored result; the adapter (not the function) loads the predecessor, and an unreadable predecessor surfaces as the error the existing candidate paths already raise, never as an empty evidence list. Each finding names its artifact, row or span, defect class and correction path. The ambiguous reference comes back as a non-blocking evidence item. One adapter turns stored candidate content (bytes per artifact member) into the same input the in-memory path uses, so a stored candidate and its in-memory form give identical evidence. On green, steps 4 and 5 can call one function from the approval paths and the CLI.

## Table of Contents

- [Why](#why) — what the approval paths and CLI cannot do today
- [Input](#input) — what steps 1 and 2 hand this step, and the limits on checking it
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — the function, the adapter, the result types, and the fixed constraints
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — pointers for fence handling and parametrization
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — what other steps and backlog entries own

## Why

Step 2's check is a gate-module function over a parsed `ArtifactEnvelope`. A candidate reaches the approval paths and the CLI in two shapes:

- the in-memory shape: `plan_tool/roadmap_candidate.py:GateCleanCandidate` and `BatchGateCleanCandidate`, each carrying `CandidateArtifact` members (`artifact_key`, `data`, `text`, `artifact`, `digest`)
- the stored shape: candidate bytes read back from disk

If steps 4 and 5 each adapt a candidate to the check in their own way, the refusal text and the CLI display can disagree on the same candidate. This step puts one function and one adapter in one place, so every consumer asks the same question and gets the same answer.

## Input

- **Step 2** owns the check in `plan_tool/roadmap_gates.py` and the two class names (`removed-id-in-live-prose`, `removed-id-ambiguous-reference`). It also owns the check's result record, which names the artifact, row id and span. Read the landed names off HEAD. They win over any name in this file.
- **Step 1** owns the contract in `ROADMAP_FORMAT.md` § "Narrative review evidence": which class blocks approval, the operator exit for each blocking class, and the rule that evidence is recomputed and never stored. This step mirrors the exit wording from that section and does not invent its own.
- **Candidate content** comes from `plan_tool/roadmap_candidate.py:CandidateArtifact`. The `artifact` field is typed `object`, so the adapter must not rely on it being a specific artifact type. The parsers (`plan_tool/roadmap_artifacts.py:parse_domain_artifact`, `parse_constraints_artifact`, `parse_components_artifact`, `parse_plans_artifact`) are the typed path.
- **Predecessor:** the check's removed-id source depends on the predecessor and the removal records, per step 1. Read at HEAD how the candidate paths already load the predecessor (`plan_tool/roadmap_versions.py:load_stored_version` and `load_resolved_stored_version`).
- **Limits on checking this step:**
  - The exact stored-candidate read path used by `plan_tool/roadmap_candidate_review.py` (`StoredCandidateReviewReplacement`) is not read here. Confirm at HEAD what a stored candidate holds before fixing the adapter's input type.
  - Steps 4 and 5 are not written yet. Cite them by owning step id only.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_narrative.py`
  - `tests/test_roadmap_candidate_narrative.py`
- **Existing files (edits only):** none. The check stays in `plan_tool/roadmap_gates.py` (step 2). No caller is wired here (steps 4 and 5).

## Implementation

**What must hold when done**

- **One pure function.** For example `compute_candidate_narrative_evidence(candidate_envelope)`, where the input is already-parsed material (an `ArtifactEnvelope` plus whatever step 2's check needs). It makes no model call, no storage read or write and no clock read. It never raises on a defective candidate. It returns an evidence record.
- **Evidence record.** A frozen result with two tuples:
  - `blocking_findings`: the step 1 blocking class (`removed-id-in-live-prose`). Each finding carries artifact, row id or span, defect class and correction path.
  - `evidence_items`: the non-blocking `removed-id-ambiguous-reference` entries, with the same fields.
  - Add a small `has_blocking_findings` property so approval callers do not re-filter.
  - Order is deterministic: artifact, then row, then span. Equal inputs must give equal records.
- **Correction path is data on the finding, not prose built by the caller.** Fill it from step 1's per-class exit (the IPPT-18 correction operation, or the structural historical marker). Name IPPT-18's operation by ticket and plan only, as step 1 does, and cite no symbol of it.
- **Message shape.** Make each message self-contained: it names every identifier involved, names the artifact by filename, and uses no line numbers. Steps 4 and 5 quote it directly.
- **One adapter.** For example `candidate_envelope_from_stored(...)`, which takes stored member bytes and produces the same input as the in-memory path.
  - Parse bytes through the existing `roadmap_artifacts.py` parsers and build the envelope.
  - Do not add a second parser.
  - Recommended: give the in-memory side a matching one-line helper over `CandidateArtifact.text`, so both paths funnel through one function and cannot drift.
  - A parse failure is not swallowed. Let the parser's existing error surface, since the adapter must not invent a clean result for content it cannot read.
- **Same-evidence property.** For one candidate, the stored path and the in-memory path must give equal evidence. This is the property step 4 and step 5 rely on. Build the in-memory side from the same bytes the stored side reads, so the test can compare directly.
- **Never stored.** The module has no write path and keeps no cache. Per step 1, evidence is recomputed on every call, and a candidate with no earlier evidence behaves identically.
- **Import discipline.** Import only what this step needs from `plan_tool/roadmap_gates.py` and `plan_tool/roadmap_artifacts.py`. Do not import `plan_tool/roadmap.py`, `plan_tool/roadmap_candidate_review.py`, the CLI layer, or any backend or shell module. Keep the module free of `invoker=` seams.
- **Rejected alternatives:**
  - Doing the work inside `roadmap_gates.py`. That module stays a set of pure checks over an envelope (step 2); candidate-shaped inputs would widen it.
  - Having each approval path adapt the candidate itself. That is the drift this step exists to prevent.
  - Computing evidence once and carrying it on `GateCleanCandidate`. That would be stored evidence, which the plan forbids.

## Tests

All cases go in `tests/test_roadmap_candidate_narrative.py`. Build artifacts directly with the `roadmap_artifacts.py` record types for the pure-function cases. Add exactly one group that goes through the parsers, as the declared seam test.

- `test_no_removed_ids_gives_empty_evidence` — a candidate with no removals returns empty blocking and evidence tuples.
- `test_removed_id_in_live_prose_is_a_blocking_finding` — the finding names artifact, row id or span, class and correction path, and `has_blocking_findings` is true.
- `test_ambiguous_reference_is_evidence_not_blocking` — an ambiguous reference lands in `evidence_items` and leaves `has_blocking_findings` false. This pins the non-blocking carve-out.
- `test_historical_marker_prose_produces_no_finding` — prose inside step 1's marker raises no finding.
- `test_finding_order_is_deterministic` — shuffled equal inputs give equal records.
- `test_function_never_raises_on_defective_candidate` — the defect is reported as data.
- `test_stored_and_in_memory_candidate_yield_identical_evidence` — one candidate, both paths, equal records. This pins the same-evidence property.
- `test_legacy_candidate_without_prior_evidence_gets_same_evidence` — nothing is read from storage, so a candidate created before this step ships behaves the same.
- `test_adapter_surfaces_parser_error_instead_of_clean_result` — unreadable stored bytes raise the parser's error and do not produce an empty record. This pins that the adapter does not hide failures.
- `test_integration_decisions_paragraph_fixture_yields_expected_finding` — runs the IPPT-18 Integration fixture from `tests/fixtures/roadmap/` that step 2 pins. If the fixture is missing, stop and go to the user; do not substitute `integration-scale-domain.md`.
- `test_module_imports_no_backend_or_cli` — a source-text scan of the module for forbidden imports, covering lazy imports inside functions as well.
- `test_module_has_no_write_or_cache_path` — a source scan for file writes and module-level caches, pinning "never stored".

### Tests for this step

Every case above must be green before this step is done. The fixture-backed case depends on IPPT-18's fixture and is the only external dependency. Run `uv run pytest tests/test_roadmap_candidate_narrative.py -q` and then `uv run pytest -m "not integration" tests/ -q`. `tests/test_duplication.py` must stay at zero groups.

## Acceptance criteria

- `plan_tool/roadmap_candidate_narrative.py` exists and exposes one pure evidence function and one stored-candidate adapter.
- A candidate with a removed id named in live prose returns a blocking finding that names artifact, row or span, defect class and correction path.
- An ambiguous reference returns a non-blocking evidence item and no blocking finding.
- The stored path and the in-memory path return equal records for the same candidate (test passes).
- The module has no import of `plan_tool/roadmap.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/cli`, or a backend or shell module.
- The module writes nothing and caches nothing; a second call recomputes.
- `plan_tool/roadmap_gates.py` is unchanged by this step.
- `tests/test_roadmap_candidate_narrative.py` is green, and the full non-integration suite stays green.

## References

- [CommonMark Spec 0.31.2: Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — read for what counts as a fenced span, since the check from step 2 skips them. This step reuses that behavior and does not define its own.
- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — read for writing the stored-versus-in-memory comparison as one parametrized case over several candidates.

## Applicable guardrails

- **The plan's "## Scope guardrails", evidence only:** this step computes evidence and does not remedy a defect. It must not rewrite prose, close feedback, or build the IPPT-18 correction operation. Correction paths are names, not actions.
- **The plan's "## Scope guardrails", not-allowed list:** this step must not add a semantic judgment, keyword-matching rule, or agreement check between two prose artifacts. The adapter's temptation point is deciding whether prose is "pending" or "settled" from its wording. It must not; only step 1's marker and the removed-id match decide.
- **The plan's "## Out of scope", stored evidence:** no evidence record, identity stamp or disposition is written. The no-write and no-cache tests enforce this.
- **The plan's "## Out of scope", behavior changes:** this step wires no caller and changes no approval, feedback-eligibility or recovery behavior. Steps 4 and 5 own that.

## Deferred

- Refusing blocking defects at the approval paths (`seal_review`, `decide_structural_candidate` approve) — step 4.
- Showing the evidence in the CLI review surface — step 5.
- The check itself and its classification of removed ids — step 2 (`plan_tool/roadmap_gates.py`).
- The contract, the blocking-class choice and the operator exits — step 1 (`ROADMAP_FORMAT.md`).
- Model-judged narrative review, stored evidence and reviewer dispositions — BACKLOG #435.
- Reconciliation-response basis fields and their checks — BACKLOG #437.
- Folding this adapter with any similar stored-candidate loading elsewhere — file a BACKLOG entry with machine-verified identity evidence if one is found; do not fold it here.
