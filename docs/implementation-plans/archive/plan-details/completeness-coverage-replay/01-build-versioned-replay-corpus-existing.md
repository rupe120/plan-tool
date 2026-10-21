# Step 1 — Build a versioned replay corpus from existing audit snapshots and predeclare schedules

> **Withdrawn 2026-08-20 (user-confirmed).** This detail remains provenance only,
> not an implementation instruction. Do not execute it; a future measurement
> requires a new, bounded design after measured operational audit cost.

## Summary

Create the versioned corpus contract, its initial schedule manifest, and a deterministic loader/validator in `plan_tool/completeness_coverage_corpus.py`. Extend the audit capture surfaces only enough to bind a corpus case to the exact prompt-visible inputs and fresh audit observations without changing normal audit behavior or saved-review meaning. Use `plan_tool/review_persistence.py:AuditInputSnapshot` and `plan_tool/fingerprint.py:audit_input_revision` as the existing identity sources, with complete clean-worktree identity as the admission boundary. On green, step 3 has a documented, validated format for adding real labelled cases, while step 2 can read pre-ranked schedules without guessing a cadence.

## Table of Contents

- [Summary](#summary) — Reviewer-level description of the delivered corpus contract.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why existing saved reports cannot yet select a reuse cadence.
- [Input](#input) — Existing audit snapshots and report fields the corpus reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New contract artifacts and bounded changes to audit capture.
- [Implementation](#implementation) — Corpus admission rules, identity rules, and schedule declaration approach.
- [Tests](#tests) — Deterministic test roster and completion gate.
- [Acceptance criteria](#acceptance-criteria) — Observable results required before the step is done.
- [References](#references) — Serialization, hashing, and test references.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that constrain this step.
- [Deferred](#deferred) — Follow-on capture, replay, and cache work outside this step.

## Why

Current `SavedReview` sidecars can retain plan, detail, and scoped-code fingerprints, but they do not prove a clean full repository state, every prompt attempt in an audit series, or authoritative fresh labels. Treating those incomplete snapshots as coverage evidence could make a skipped discovery look safe when it is only unmeasured. This step creates the fail-closed contract that preserves useful current capture facts while excluding any report that cannot support the later replay decision.

## Input

- **Captured audit inputs:** Read `plan_tool/review_persistence.py:AuditInputSnapshot`, including its `capture()` and `revision` behavior, as the source for the selected plan, detail bundle, source seed, project context, and grade captured for an audit. The corpus must preserve the captured state, not re-read these inputs later.

- **Rendered audit prompt:** Use `plan_tool/review.py:render_plan_audit_prompt` as the model-visible prompt boundary. Capture an ordered identity for every prompt attempt, including its rendered-prompt digest, carried-finding digest, and retry-suffix state; `AuditInputSnapshot.revision` alone does not identify that series.

- **Audit observations:** Keep `plan_tool/review.py:check_plan_audit`, `audit_plan_until_stable`, `_AuditSampleEvidence`, and `_AuditTagObservation` as the current source of attempt/pass outcome and finding attribution. The capture hand-off must record retry attempts, skipped or failed/malformed outcomes, ordered pass outcomes, and final coverage. `_AuditTagObservation` is attribution only, not a separate scan or reuse boundary.

- **Backend recovery attempts:** Use `plan_tool/review.py:shell_review_invoker` and `plan_tool/shell.py:claude_invoke` as the recovery boundary. The opt-in hand-off records every backend call and retry, raw output, and outcome before `claude_invoke` collapses them to its ordinary final result; an unobservable recovery attempt excludes the fresh series.

- **Saved reports:** Read `plan_tool/review_persistence.py:SavedReview`, `load_review`, and `save_review` only as historical input. Require all corpus-specific evidence separately; absent legacy fields make a case excluded rather than clean.

- **Scoped code fingerprints:** Preserve `plan_tool/fingerprint.py:compute_code_fingerprint` as supplementary provenance. Its watched-file map must never stand in for the committed worktree identity required for corpus admission.

## Files (creates vs edits)

- **New files:**
  - `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md` — Define the versioned manifest and future case-file contract, identity fields, admissibility rules, and canonical JSON requirements.
  - `benchmarks/corpus/completeness-coverage/manifest.json` — Declare the corpus version, the non-selectable always-fresh control, ranked candidate schedules, corpus diversity floor, and each candidate’s interval witness requirement before any case is captured.
  - `plan_tool/completeness_coverage_corpus.py` — Provide deterministic corpus models, parsing, validation, identity checks, and canonical serialization helpers.
  - `tests/test_completeness_coverage_corpus.py` — Cover the corpus contract and fail-closed admission rules.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Add an opt-in observational hand-off around `check_plan_audit` and `audit_plan_until_stable` so a fresh capture can bind every rendered prompt attempt, carried/retry state, attempt and pass outcomes, final coverage, and finding attribution without changing normal findings, prompts, invocation count, or convergence behavior.
  - `plan_tool/shell.py` — Add the capture-only recovery-boundary observer and prompt-budget suppression that link every `claude_invoke` backend attempt to its rendered review-prompt attempt without changing normal retries, results, or telemetry.
  - `plan_tool/backend.py` — Add a capture-only read-only backend profile rooted at the sealed source inventory; reject a backend that cannot supply that profile rather than falling back to its normal writable transport.
  - `tests/test_shell.py` — Prove capture sees every transient or rate-limit retry, suppresses shell telemetry, and leaves the ordinary invocation path observationally unchanged when no observer is installed.
  - `tests/test_backend.py` — Prove the capture profile uses the sealed root and read-only permissions rather than the normal writable transport.
  - `plan_tool/review_persistence.py` — Add a narrow corpus-facing projection from `AuditInputSnapshot`; preserve `SavedReview`, `save_review`, `load_review`, existing sidecar versions, and their legacy-reader behavior.
  - `plan_tool/fingerprint.py` — Add any corpus-only identity helper beside `audit_input_revision`; keep the version-3 audit revision and `compute_code_fingerprint` semantics unchanged.

## Implementation

- **Foundational logic: fail-closed corpus admission.** A case is admissible only when its record supplies every identity and label required by `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md`. Missing evidence is an exclusion with a machine-readable reason, never an empty value that replay can treat as unchanged or covered.

- **Separate full worktree identity from scoped provenance.** Record a clean disposable worktree’s commit and tree identity, and reject dirty or untracked repository state. Retain `plan_tool/fingerprint.py:compute_code_fingerprint` as useful scoped provenance, but do not accept it as proof of the repository state the model could inspect.

- **Seal and retain the visible worktree.** Build the audit's Read/Grep surface from a source-root inventory that exactly matches the committed tree, then run every captured backend attempt under a fixed read-only profile rooted at that inventory. Every ignored or untracked model-readable path, unavailable profile, attempted mutation, or fence failure excludes the case; Git administration and capture runtime remain outside that surface. Recheck the inventory after every backend attempt, not only before the run. Require a future verifier to resolve every eligible commit and tree from step 3's committed `fixtures.bundle` after its linked worktree is removed.

- **Use a capture-only audit lifecycle.** Invoke the same `audit_plan_until_stable` discovery engine directly, not the `completeness-audit` CLI path. The runner therefore cannot create saved reports or call `record_audit_coverage`. Suppress the review-level `record_prompt_budget` and shell-backstop telemetry writers for the entire captured lifecycle; retain only their non-writing calculations and place capture evidence and temporary state outside the sealed Read/Grep root. No telemetry, transport, or retry behavior changes when capture is not enabled.

- **Capture the exact model-visible inputs and attempt series.** Build the corpus projection from the frozen `AuditInputSnapshot` inputs and every prompt rendered by `plan_tool/review.py:render_plan_audit_prompt`. Bind the plan, selected detail artifacts, source seed, project context, audit stage, grade, each rendered-prompt digest, carried-finding digest, retry suffix, and sampler/audit configuration to the same capture; do not reconstruct them from a report filename or current disk state.

- **Capture recovery below the review wrapper.** Thread the capture-only observer through `plan_tool/shell.py:claude_invoke` and associate every backend call, retry, raw output, and outcome with its rendered review-prompt attempt. Exclude a series when any recovery attempt lacks this record; the existing `shell_review_invoker` return contract and normal retry policy remain unchanged.

- **Keep normal audit behavior unchanged.** Make the new capture path opt-in and observational outside its explicit access fence. `plan_tool/review.py:check_plan_audit` and `audit_plan_until_stable` must retain their existing parsing, retry, union, pass-budget, and report behavior when no corpus capture is requested; do not add a CLI flag, cache decision, or new model call.

- **Define one whole-prompt observation unit.** The declared unit is one complete fresh audit run. Its pre-run reuse key contains every initial prompt-visible identity, complete repository state, and audit configuration known before discovery; its ordered trace records later carried-finding and retry inputs. Preserve stable recommendation IDs and `_AuditTagObservation` only as finding attribution; neither can create a step-scoped observation or independently permit reuse.

- **Make authoritative labels explicitly confirmed.** Admit a fresh label set only when the complete ordered series is captured, every prompt attempt conforms, no attempt is skipped or failed/malformed, and the final coverage records `confirmation_kind` as `confirmed-dry` or `confirmed-low-yield`. A merely non-budget-limited, one-pass, or otherwise unconfirmed run is an exclusion. Its later comparison is unresolved and cannot contribute an empty label set. The observation unit's labels enter only through full discovery or the terminal confirmation; reuse cannot manufacture labels by inference.

- **Make label identity evidence-bound.** Version the manifest's label registry before capture. Each assignment names one registry id and points to its recorded raw response bytes and digest, prompt-attempt index, and parsed recommendation reference. A reviewer may make that explicit mapping, but IDs, anchors, or prose never automatically establish cross-snapshot equality; an unmapped or ambiguous fresh finding stays unresolved.

- **Predeclare schedules and the evidence universe in the manifest.** Require the manifest to define one always-fresh control and a finite ranked candidate set before `benchmarks/corpus/completeness-coverage/cases.json` exists. Every selectable candidate needs a full-discovery interval of at least two, a mandatory terminal full-discovery confirmation, and a unique priority rank. It must also name eligible ordered evidence of its own unchanged non-terminal reuse and its own later unchanged non-terminal interval-due full-discovery decision. The manifest requires at least three independent trajectories covering reuse, changed-input, periodic full-discovery, and terminal-confirmation branches as corpus diversity, but an eligible case is never assigned to a candidate subset: the evidence universe for every candidate is the complete eligible corpus.

- **Record policy facts, derive candidate decisions.** The manifest requires snapshot zero to be full discovery; for later snapshots terminal confirmation wins, then a changed pre-run reuse key forces full discovery, then the candidate interval forces full discovery when due, and only otherwise may the whole fresh-audit observation reuse. Cases retain candidate-independent ordered position, terminal flag, and pre-run reuse key, not a single selected policy outcome. The loader validates those facts and the replay derives one policy result for each candidate; missing or contradictory facts remain unresolved.

- **Carry a whole reused label set.** Full discovery introduces or refreshes the whole label set for its observation. A valid reuse carries that exact most-recent predecessor set; it does not discard labels because their findings had plan-level attribution. A changed key, missing predecessor, or non-authoritative predecessor is unresolved instead.

- **Keep schedule validation separate from selection.** Validate that schedule declarations, candidate interval witnesses, eligible-case ordering, candidate-independent policy facts, and the complete per-candidate evidence universe are well formed in `plan_tool/completeness_coverage_corpus.py`; leave replay simulation, losses, `insufficient-evidence`, `no-safe-cadence`, and candidate selection to step 2.

- **Use stable JSON deliberately.** Serialize corpus data with a documented canonical form and hash the exact serialized identity inputs. Preserve array order where it represents trajectory, pass, or rank order; do not sort semantic sequences merely to make output convenient.

- **Document code as the enforcing source.** Start `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md` with the root-format source-of-truth banner naming the corpus parser and validator. Document `manifest.json` now and the `cases.json` shape that step 3 will write; code wins if the document and validator disagree.

- **Do not merge with scenario capture.** `plan_tool/scenario_capture.py:repo_sha`, `working_tree_dirty`, and `capture_scenario` record experimental JSONL telemetry and permit states this corpus must exclude. Keep the coverage corpus independent rather than broadening that unrelated capture format or weakening this admission rule.

## Tests

### Tests for this step

- `test_manifest_requires_a_versioned_nonselectable_always_fresh_control` — Asserts the control is present for reporting but cannot receive a selectable candidate rank.

- `test_manifest_requires_ranked_candidates_with_reuse_and_terminal_confirmation` — Asserts every selectable candidate declares an interval of at least two, terminal confirmation, and a unique priority rank.

- `test_manifest_requires_three_independent_trajectories_without_a_candidate_subset` — Asserts the corpus has the diversity floor and branch coverage while every eligible case remains in every candidate's evidence universe.

- `test_case_requires_clean_commit_and_tree_identity` — Rejects a case missing either committed identity, tree identity, or a clean-worktree assertion.

- `test_case_rejects_an_ignored_or_untracked_model_readable_path` — Rejects a visible source-root inventory that differs from the committed tree.

- `test_capture_mode_is_read_only_and_suppresses_every_audit_runtime_writer` — Proves the direct capture runner avoids reports and audit-coverage telemetry, suppresses review and shell prompt-budget telemetry, and rejects a source-root mutation while ordinary audits remain unchanged.

- `test_case_requires_a_retained_bundle_resolving_its_commit_and_tree` — Rejects a case unless its declared `fixtures.bundle` resolves both recorded Git objects after worktree cleanup.

- `test_case_requires_every_model_visible_attempt_identity` — Rejects a case missing the captured plan, selected detail, source seed, project context, stage, grade, any rendered prompt, carried context, retry state, or audit-configuration identity.

- `test_case_requires_a_complete_confirmed_attempt_series` — Rejects an absent attempt, skipped or failed/malformed attempt, missing final coverage, a budget-limited series, or a series without `confirmed-dry` / `confirmed-low-yield` as authoritative fresh evidence.

- `test_capture_records_or_excludes_every_claude_invoke_recovery_attempt` — Proves transient and rate-limit retries retain their raw outcome linkage and source-inventory recheck, while an unobservable retry excludes the case.

- `test_manifest_requires_a_label_registry_and_raw_response_backed_assignments` — Rejects an undeclared, ambiguous, or output-unlinked label; proves recommendation identity and prose are evidence references rather than cross-run matching keys.

- `test_scoped_code_fingerprint_cannot_replace_complete_worktree_identity` — Asserts a case with only `compute_code_fingerprint` provenance remains excluded.

- `test_observation_unit_is_the_whole_fresh_audit_not_step_attribution` — Rejects a step tag or partial pre-run identity as a reuse key, requires the post-run attempt trace, and retains `_AuditTagObservation` only as label provenance.

- `test_manifest_requires_candidate_independent_policy_facts` — Rejects a case missing ordered position, terminal state, or pre-run reuse key, and rejects a stored candidate policy result that would make replay ambiguous.

- `test_selectable_candidate_has_its_own_reuse_and_interval_due_witness` — Rejects an interval below two or a candidate without eligible ordered evidence of both an unchanged non-terminal reuse and that candidate’s non-terminal interval-due discovery.

- `test_reuse_carries_the_complete_predecessor_label_set` — Proves a valid reuse retains all labels from its authoritative predecessor regardless of finding attribution.

- `test_legacy_saved_review_without_corpus_evidence_is_excluded` — Asserts an otherwise readable `SavedReview` sidecar cannot become a labelled case when required corpus evidence is absent.

- `test_corpus_serialization_is_canonical_and_reproducible` — Asserts equivalent validated corpus objects produce the same JSON bytes and identity digest while preserving declared sequence order.

- `test_corpus_validation_never_invokes_a_model_backend` — Monkeypatches the review invoker boundary and proves loading or validating corpus data performs no model call.

Every test above must be green before this step is considered complete.

## Acceptance criteria

- `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md` names the enforcing corpus code and defines versioned manifest and case records, including exclusions and canonical serialization.

- `benchmarks/corpus/completeness-coverage/manifest.json` declares the always-fresh control, every candidate schedule, unique ranks, candidate interval witnesses, corpus diversity floor, the complete eligible evidence universe for every candidate, and no selected cadence.

- A corpus case without clean commit/tree identity, a complete confirmed prompt-attempt series, or authoritative fresh labels is excluded with a stated reason.

- A corpus case with a model-readable ignored/untracked path, an unresolvable retained commit/tree, an undeclared label, or raw-output evidence that does not support its assignment is excluded with a stated reason.

- Capture mode calls the discovery engine without the completeness CLI, uses only a proven read-only backend profile, creates no model-readable runtime state under the source root, rechecks that root after every backend attempt, and records every `claude_invoke` recovery attempt; an opaque retry, mutation, or fence failure excludes the case.

- The manifest fixes snapshot-zero, changed-input, interval, and terminal-confirmation observation order before capture; cases retain only candidate-independent policy facts, each selectable candidate has its own reuse and interval-due witness, selectable intervals are at least two, and reuse carries the whole predecessor label set.

- A scoped code fingerprint is stored only as supporting provenance and cannot make an otherwise incomplete case eligible.

- Existing `SavedReview` JSON files remain readable with their current schema and semantics; incomplete legacy sidecars are not upgraded into corpus evidence.

- `plan_tool/review.py:check_plan_audit` and `audit_plan_until_stable` preserve their current behavior when the corpus capture path is unused.

- `uv run pytest tests/test_completeness_coverage_corpus.py -q` passes with no model backend invocation.

## References

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use deterministic JSON encoding options for persisted corpus identities.

- [Python 3.13 hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 for captured input and canonical-record digests.

- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Review canonical JSON rules when defining stable corpus serialization.

- [JSON Schema Draft 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its structural-validation concepts when documenting required versioned fields.

- [pytest — Parametrizing Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Build the manifest and exclusion matrix without duplicate test logic.

- [pytest — Monkeypatching Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Prove the corpus path stays deterministic and model-free.

## Applicable guardrails

- **The plan’s “## Plan intent”, evidence-bound measurement:** Produce corpus evidence only. Do not make a cache, change audit behavior, or select a cadence in this step.

- **The plan’s “## Step intent”, admissible capture boundary:** Accept only cases with complete clean-worktree, prompt-visible, whole-fresh-audit, label, and evidence-threshold records.

- **The plan’s “## Out of scope”, audit and CLI behavior:** Do not alter completeness prompts, pass budgets, gates, exit codes, saved-report semantics, or add a CLI surface.

- **The plan’s “## Out of scope”, label and decision policy:** Do not add content-based matching, inferred labels, automatic cadence decisions, or unrelated benchmark expansion.

## Deferred

- `plan_tool/completeness_coverage_replay.py` and `tests/test_completeness_coverage_replay.py` — Step 2 owns deterministic schedule replay, exclusions, missed-label reporting, and the terminal result table.

- `benchmarks/corpus/completeness-coverage/cases.json` — Step 3 owns real disposable-worktree captures and explicit labels using this step’s contract.

- BACKLOG #173 cache and re-check implementation — Remains blocked until the later replay result selects and justifies a cadence.
