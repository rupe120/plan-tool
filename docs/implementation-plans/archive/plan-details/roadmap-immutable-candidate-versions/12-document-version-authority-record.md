> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 12 — Document version authority, record the remaining direct-reader migrations, and close #328 after the real-backend observation

## Summary

Update `ROADMAP_FORMAT.md`, `CLAUDE.md`, and `BACKLOG.md` to describe the landed immutable-version lifecycle and its one converted downstream reader. Keep the accepted-head selector as the only authority for enrolled roadmap content, with model output remaining inert until exact promotion. Record the remaining direct-reader migrations as deferred work rather than extending this plan. On green, the documentation guard verifies the current contract and `BACKLOG.md` records one redacted real-backend observation before closing #328.

## Table of Contents

- [Summary](#summary) — The step outcome and documentation footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the shipped authority boundary needs an updated reference.
- [Input](#input) — The upstream lifecycle and current documentation this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing documentation and drift guard to update.
- [Implementation](#implementation) — The authority reference, deferred-reader record, and closure process.
- [Tests](#tests) — Documentation-contract checks and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Identity and closed-record references used by the documented contract.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this documentation step.
- [Deferred](#deferred) — Reader migration and hardening work outside this proof.

## Why

`ROADMAP_FORMAT.md` still directs cross-artifact work toward `BACKLOG.md` #328 instead of describing the accepted-head lifecycle that steps 3 through 11 deliver. Without a current reference, an operator cannot tell the immutable candidate route from the existing bounded live-writer routes, and the remaining direct readers have no explicit migration record once #328 closes.

## Input

- **Landed lifecycle:** Steps 3 through 9 provide the implemented root enrollment, immediate writer fence, candidate, review, and exact-promotion contracts. Read their landed public symbols before documenting names; the code wins over this plan and its earlier detail files.

- **Converted reader:** Step 10 changes `plan_tool/roadmap_view.py:load_roadmap()` to select an enrolled roadmap through the accepted head while retaining its unversioned path.

- **Writer fence and CLI:** Steps 4 and 11 provide the immediate legacy-writer refusal and the operator-facing lifecycle actions. Use the landed `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` surface rather than documenting proposed flag spellings.

- **Existing route reference:** `ROADMAP_FORMAT.md:### Evidence, publication, and availability boundary` currently names #328 as future work. Replace that stale handoff without weakening its structural-rewrite and evidence boundaries.

- **Documentation guard:** `tests/test_roadmap_format.py:_DOC` and its route-reference tests establish the existing pattern for checking human-facing roadmap contracts against code and neighboring guides.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Add the accepted-head candidate-version reference, revise the obsolete #328 handoff, and keep legacy route boundaries explicit.
  - `CLAUDE.md` — Update the concise roadmap architecture and reference-document descriptions to point to the landed version-authority contract without duplicating it.
  - `BACKLOG.md` — Close #328 after the real-backend observation, remove it from the active queue, and retain the direct-reader migration inventory as deferred follow-up.
  - `tests/test_roadmap_format.py` — Add drift checks for the authority reference, deferred-reader inventory, concise `CLAUDE.md` pointer, and redacted closure record.

## Implementation

- **Foundational rule:** An enrolled roadmap’s accepted-head selector is its sole canonical content source. Document that a stored candidate, a review seal, model output, directory order, and live top-level artifact paths must not select canonical content on their own.

- **Add one current version-authority section.** In `ROADMAP_FORMAT.md`, describe enrollment, one fixed immutable roadmap admission for the representative feedback, different-feedback refusal before and after promotion, the module-owned 64 KiB capsule-payload ceiling with no caller override, exact proposal/answer re-entry, immutable candidates, the replacement prompt built from the exact stored question-and-answer pair rather than answer text alone, terminal consumption by exact review-seal promotion, and the one converted reader as one ordered lifecycle. Cite the landed public module and symbol names from `plan_tool/roadmap_versions.py`, `plan_tool/roadmap_candidate_context.py`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_version_promotion.py`, and `plan_tool/roadmap_view.py:load_roadmap()`.

- **Keep source and version roles separate.** State that unversioned roadmaps retain their present top-level artifact reads, while an enrolled roadmap supplies one complete selected version. The reference must not imply that promotion rewrites source artifacts, that a candidate becomes current by recency, or that a reader can repair or enroll state.

- **Preserve the old route boundaries.** Revise `ROADMAP_FORMAT.md:### Evidence, publication, and availability boundary` so `same-artifact` and `cross-artifact` evidence, `--revise-feedback`, and exact-pair structural rewrite remain bounded legacy routes. Remove the stale claim that #328 owns a future transaction, but do not describe either route as a candidate-version writer.

- **Record the migration boundary exactly once.** In the closed #328 record in `BACKLOG.md`, name `plan_tool/roadmap_view.py:load_roadmap()` as the completed reader proof and retain these remaining direct-reader candidates as deferred migration work: `plan_tool/create.py:_load_roadmap_research_targets()`, `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed()`, `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()`, `plan_tool/roadmap.py:_load_stage_artifact()`, `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot()`, `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt()`, `plan_tool/roadmap_feedback_reopen.py:run_confirmed_feedback_reopen()`, and `plan_tool/roadmap_revision_publish.py`’s legacy publication paths.

- **Close #328 on observation, not model-quality judgment.** Run one real-backend lifecycle attempt through the landed CLI after deterministic tests pass. Record the observation date, prompt-byte count, context membership identity or count, expansion use, and the final model-facing phase (`candidate`, `question`, or `replacement`) with its exact terminal outcome (`stored`, `response-rejected`, `failed`, or `refused`); do not store prompt text, model response text, or a claim that the output is semantically good. Any of the four outcomes is a valid observation and must not trigger prompt widening, automatic retry, or new scope.

- **Keep `CLAUDE.md` terse.** Update its roadmap architecture summary and `## Reference docs` entry to name immutable accepted-head versions and direct readers’ documented boundary, then point readers to `ROADMAP_FORMAT.md` for lifecycle detail. Do not copy the field inventories, command syntax, or deferred-reader list into `CLAUDE.md`.

- **Extend the documentation guard.** Add focused checks in `tests/test_roadmap_format.py` using headings or explicit markers rather than line positions. The checks must prove both the authority claims and the deliberate non-migration boundary, not merely that new words appear somewhere in the files.

## Tests

This is a non-code step, so the plan’s test-authoring gate does not apply. The documentation drift guard remains required because these files define an operator-facing contract.

- `test_immutable_candidate_version_reference_matches_landed_authority_contract` — the `ROADMAP_FORMAT.md` version section names the accepted head, fixed roadmap admission, different-feedback refusal, fixed 64 KiB capsule ceiling, exact proposal/answer re-entry, the stored question-and-answer replacement pair, immutable candidate and review bindings, terminal consumption, exact promotion, and the landed code owners.
- `test_immutable_candidate_version_reference_keeps_unversioned_routes_separate` — candidate versions do not broaden local feedback revision, structural rewrite, evidence readers, or unversioned reads.
- `test_version_authority_reference_lists_exactly_the_deferred_direct_readers` — the completed `plan_tool/roadmap_view.py:load_roadmap()` migration is distinct from the eight deferred module candidates.
- `test_claude_roadmap_reference_tracks_immutable_version_authority` — `CLAUDE.md` points to the current `ROADMAP_FORMAT.md` contract without copying its detailed lifecycle.
- `test_backlog_328_closure_records_redacted_real_backend_observation` — #328 is no longer active and its dated closure records only the required operational facts plus one closed phase/outcome pair, not model or roadmap prose.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py -q`; it must pass without a real backend invocation.
2. Check every documented code symbol against the landed modules from steps 3 through 11 and replace any plan-era proposed name with the implementation’s actual name.
3. Confirm the deferred-reader inventory contains every named module exactly once and does not list `plan_tool/roadmap_view.py:load_roadmap()` as still deferred.
4. Perform one real-backend attempt through the landed lifecycle and verify that `BACKLOG.md` records its bounded facts without prompt or response text.
5. Confirm the active queue no longer presents #328 as pending work and that `ROADMAP_FORMAT.md` contains no future-handoff claim for it.

## Acceptance criteria

- `ROADMAP_FORMAT.md` states that an enrolled roadmap reads one accepted immutable version and that only exact promotion changes the accepted head.
- The documented lifecycle keeps admission, feedback, candidates, questions, answers, review seals, and accepted-head selection as distinct bindings, refuses a different feedback before and after promotion, records one module-owned 64 KiB capsule ceiling with no caller override, supplies the replacement with the exact stored question-and-answer pair rather than answer text alone, and uses exact command replay without a branch or automatic retry.
- `ROADMAP_FORMAT.md` preserves the bounded unversioned local and structural routes without describing either as a candidate-version writer.
- `CLAUDE.md` points developers to the current version-authority reference in concise terms.
- `BACKLOG.md` closes #328 only after one dated, redacted real-backend observation naming the final model-facing phase and one of the shared four terminal outcomes, and records the remaining direct-reader candidates for later scope selection.
- `tests/test_roadmap_format.py` passes with the new authority and closure checks.

## References

- [Structured outputs — Claude Platform Docshttps: — Read for the boundary between model-proposed structured output and deterministic acceptance.
- [json — JSON encoder and decoderhttps: — Read for the deterministic record and strict-decoding terms used by the reference.
- [hashlib — Secure hashes and message digestshttps: — Read for the identity and digest terminology the lifecycle documents.
- [RFC 8785: JSON Canonicalization Schemehttps: — Read for canonical JSON identity terminology.

## Applicable guardrails

- **Authority and ordering — the plan’s “## Scope guardrails.”** Document model output as inert and preserve the required candidate, answer, seal, and promotion sequence.

- **Distinct bindings — the plan’s “## Scope guardrails.”** Do not describe a matching or regenerated candidate as interchangeable with the reviewed and approved identity.

- **Context boundary — the plan’s “## Scope guardrails.”** Record the real-backend observation as mechanical facts only; do not turn it into a quality verdict or a reason to widen context.

- **Reader and writer scope — the plan’s “## Scope guardrails” and “## Out of scope.”** Name the one completed reader conversion, retain the legacy writer fence, and defer every other reader migration.

- **Small happy path — the plan’s “## Scope guardrails.”** Do not add production hardening, storage management, or workflow states while documenting the shipped proof.

## Deferred

- **Migration of the remaining direct-reader inventory** — `BACKLOG.md` records the candidates for separately scoped accepted-head migration; this step documents them but changes none of their behavior.

- **Prompt-quality or model-success measurement** — the required observation records one route execution, not a benchmark or a semantic-quality claim.

- **Version lifecycle hardening and management features** — recovery, history, retention, comparison, and broader workflow work remain outside this plan.
