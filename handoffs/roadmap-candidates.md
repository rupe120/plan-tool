# Roadmap candidates

Candidate collection, capsules, envelopes, context ceilings and model-failure receipts in the `roadmap` verb. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Roadmap model-failure-receipts code review](#roadmap-model-failure-receipts-code-review) | 2026-09-22 |
| [Roadmap candidate vocabulary retry — plan review pickup](#roadmap-candidate-vocabulary-retry--plan-review-pickup) | 2026-09-25 |
| [Roadmap candidate envelope diagnostics — post-run review ledger](#roadmap-candidate-envelope-diagnostics--post-run-review-ledger) | 2026-09-26 |
| [Candidate anchor/gate correction — review ledger](#candidate-anchorgate-correction--review-ledger) | 2026-09-27 |
| [Row-linked prose amendments in version comparison — code review ledger](#row-linked-prose-amendments-in-version-comparison--code-review-ledger) | 2026-09-29 |
| [Candidate capsule fixes — code review ledger](#candidate-capsule-fixes--code-review-ledger) | 2026-10-05 |
| [Roadmap candidate context ceiling — code review ledger](#roadmap-candidate-context-ceiling--code-review-ledger) | 2026-10-09 |

## Roadmap model-failure-receipts code review

*Opened 2026-09-22.*

### Summary

| Field | Value |
| --- | --- |
| Review range | `origin/main..HEAD`, then each round's own fix commits |
| Range base (origin/main) | `271e82e4` |
| Round 1 head (initial review target) | `3f0d5c6e` |
| Current head | `df51b906` (round 5 fix commit) |
| Checks run | `/code-review` (report-only, no `--fix`), effort `high` every round |
| Reviewer/session | `code-review-loop` skill |
| Current disposition | **Converged, loop stopped** — code clean since round 2 (round 3's residual filed to `BUG_BACKLOG.md`); rounds 4-5 were self-referential ledger-bookkeeping findings, now fixed; see Convergence status |

Convergence loop over the 12 commits on `main` (`403e5fb5..3f0d5c6e`, the
`roadmap-model-failure-receipts` plan, BACKLOG #217) not yet on `origin/main`.
This is a new ledger, not a continuation of
`tracking-and-jira.md` § "Unpushed `main` code review", whose range (the
`roadmap-concept-comparison` work) converged and is on `origin/main`.

### Settled decisions (hand to the next reviewer)

*Compression note (added 2026-11-13; the ledger was compressed 2026-09-29): this ledger had no original settled-decisions list; the list below was assembled from its own declined and refuted findings.*

- The receipt's `ValueError` guards in `RunLogWriter.model_failure_receipt()`
  are invariant assertions and stay uncaught; "best-effort" in the plan docs
  scopes to the sidecar file write only.
- The `getattr(run_logger, "repo_root", None)` guard in
  `record_model_failure_receipt` stays: lightweight test doubles
  (`_CallRecorder` in `tests/test_roadmap.py`) exercise it.
- `retain_response` is deliberately asymmetric between `roadmap.py` and
  `roadmap_revision_run.py` (detail doc `05-record-local-feedback-revision-failures.md`,
  line 51).
- `store_model_response_sidecar` cannot raise `UnicodeEncodeError` on its
  `.encode("utf-8")` (upstream `Popen(..., text=True)` decodes strictly).
- The sidecar-namespace collision with a `register`-adopted plan is an open
  design choice in `BUG_BACKLOG.md`; no further narrowing of the prefix string.
- Ledger-bookkeeping prose is not a review target (see Convergence status).

### Fix guidance (applies to every disposition in this ledger)

A `fixed` closure must:

- Be true and proportional to the intent of the code it touches: no bigger,
  smaller, or more general than the defect calls for.
- Apply the smallest proof that completes the intent, not the eventual
  capability the finding gestures toward.
- Stay at the altitude the finding names (no detail-level mechanics in a
  plan/bare-level concern, or the reverse).
- Run an identifier + vocabulary sweep for sibling sites, then check the
  remedy against the goal of the bug rather than replaying one patch verbatim
  at every matched site.

### Round 1 (2026-09-22, `271e82e4..3f0d5c6e`)

Full suite before review: 13306 passed, 189 skipped. Fixes landed as two
commits split by file overlap: `ab6908ac` and `19dd3cdb`.

- **R1-1 — receipt `ValueError` uncaught** (severity not recorded):
  `RunLogWriter.model_failure_receipt()` can raise `ValueError` (negative
  `response_bytes`, malformed SHA-256, sidecar path outside `repo_root`) with
  no caller catching it, against the best-effort design. **Disposition:**
  declined — these are invariant assertions, and both callers build the values
  adjacent to the call from inputs that satisfy them by construction (`len()`
  is non-negative; `hexdigest()` matches the SHA-256 regex; the sidecar path
  is built from the same `run_logger.repo_root`). Swallowing a future
  assembly bug would trade a loud crash for a silently missing receipt, and
  the step-2 design doc never calls for catching them.
- **R1-2 — `repo_root` guard silently drops the event** (severity not
  recorded): `_record_stage_failure_receipt` returns early on
  `getattr(run_logger, "repo_root", None) is None` while sibling
  `run_logger` calls access attributes directly. **Disposition:** declined —
  the guard is not hypothetical: `_CallRecorder` in
  `tests/test_roadmap.py::TestRevisionInTheAttemptLoop` is a live stand-in with
  no `repo_root`; production always passes a `RunLogWriter` whose `repo_root`
  is required. Removing the guard would force retrofitting every test double
  for a diagnostic-only feature.
- **R1-3/4 — digest recomputed; receipt assembly duplicated** (severity not
  recorded): `store_model_response_sidecar` returned a digest only on
  `WRITTEN` and neither caller read it, so each producer re-encoded and
  re-hashed the reply, and the two assembly functions had diverged in style.
  **Disposition:** fixed `ab6908ac` — `ModelResponseSidecarResult` always
  carries `digest` and a new `response_bytes` once a response exists;
  `record_model_failure_receipt` (renamed, producer-neutral, public) reads
  both from `sidecar_result`; `roadmap_revision_run._record_local_failure_receipt`
  is a thin wrapper.
- **R1-5 — `_emit()` hand-special-cases `sidecar_path`** (severity not
  recorded): an `isinstance(event, ModelFailureReceipt)` branch duplicated
  the `conditionally_persisted` declaration in `data_contract.py`. **Disposition:**
  fixed `19dd3cdb` — a generic `omit_when_none: ClassVar[frozenset[str]]` on
  `_BaseEvent` (overridden on `ModelFailureReceipt`) that `_emit()` reads via
  `getattr(event, "omit_when_none", frozenset())`; deriving one from the other
  would create an import cycle (`data_contract.py` imports `run_log.py`). The
  `getattr` is required because `_emit()` also receives the producer-local
  `_RedactedClaudeStreamEvent`, which is outside the `Event` union (the first
  attribute-access version broke
  `tests/test_roadmap.py::TestMaterializationRealInvoker::test_materialization_observer_omits_tool_and_reply_derived_text`).
  Pinned by `test_run_log_event_omit_when_none_matches_conditionally_persisted`
  in `tests/test_data_contract.py`.
- **R1-6 — `conditionally_persisted`/`in_memory_only` names unvalidated**
  (severity not recorded): a typo'd entry silently leaves the real field
  "always required". **Disposition:** fixed `19dd3cdb` — added
  `test_conditionally_persisted_and_in_memory_only_name_real_fields`,
  parametrized over every registered `PersistedDataclassContract`; no
  existing registration was wrong.
- **R1-7 — duplicated reason literals** (severity not recorded):
  `"source-admission-rejected"` (3 sites) and `"invalid_detail"` (2 sites)
  were raw literals unlike the `FAILURE_*` constants. **Disposition:** fixed
  `ab6908ac` — `REASON_SOURCE_ADMISSION_REJECTED` and `REASON_INVALID_DETAIL`
  constants in `roadmap.py`, all sites swept, imported by
  `roadmap_revision_run.py`.
- **R1-8 — identical `except` bodies** (severity not recorded): the
  `StageRevisionLimitError` and `StageRevisionSourceError` clauses in
  `_run_bounded_stage_feedback` were byte-identical. **Disposition:** fixed
  `ab6908ac` — merged into one `except (StageRevisionLimitError,
  StageRevisionSourceError)`.
- **R1-9 — sidecar producer-slug prefix collision** (severity not recorded):
  the `"roadmap-"` string prefix could share a directory with a plan slugged
  `roadmap-foo`. **Disposition:** fixed `ab6908ac` — path-separator prefix
  `roadmap/{slug}`; the claim that this made collision impossible for any slug
  was false and is superseded by R2-1.
- **R1-10 — `run_log.py` header contradicts a new import** (severity not
  recorded): the "no first-party `plan_tool.*` imports" bullet was falsified
  by a new `TYPE_CHECKING` import of `ModelResponseSidecarResult`.
  **Disposition:** fixed `19dd3cdb` — bullet reworded to state the
  `TYPE_CHECKING` exception and the function-local `plan_tool.shell`/
  `plan_tool.telemetry` imports.

Sibling-test fallout (expected red siblings in a class sweep): three tests
stubbed `store_model_response_sidecar` with a bare `WRITE_FAILED` result and
misclassified the disposition as `"no-response"`
(`tests/test_roadmap_revision_run.py::test_sidecar_write_failure_does_not_change_local_revision_result`;
`tests/test_roadmap.py::TestFreshStageModelFailureReceipts::test_fresh_sidecar_write_failure_does_not_block_a_recovered_retry`;
`tests/test_roadmap.py::TestBoundedFeedbackModelFailureReceipts::test_bounded_feedback_sidecar_write_failure_does_not_block_accepted_revision`);
they now patch `model_response_sidecar.atomic_write_bytes` to raise `OSError`.
Full suite: 13341 passed, 190 skipped.

### Round 2 (2026-09-22, `3f0d5c6e..HEAD`: `ab6908ac`, `19dd3cdb`, docs commit `8bd2b8f9`)

Fix commit: `8c0ffead`. Full suite: 13342 passed, 190 skipped.

- **R2-1 — `roadmap/{slug}` collides with a plan slugged `roadmap`**
  (severity not recorded; three of four finder angles converged): `detail.py`
  writes flat under `parse-failures/<plan-slug>/`, so a plan slugged `roadmap`
  shares the directory now serving as the roadmap-family namespace root.
  **Disposition:** fixed `8c0ffead` — root changed to `_roadmap/{slug}`; `SLUG_RE`
  has no underscore. That fix's "genuinely structural" claim was also false
  (see R3-1); the residual is tracked, not patched a third time.
- **R2-2 — `_record_local_failure_receipt` now silently skips on missing
  `repo_root`** (severity not recorded): delegation to the shared function
  turned a loud `AttributeError` into a silent drop. **Disposition:** declined —
  the only caller path (`run_local_feedback_revision`, `roadmap_revision_run.py`
  line ~109) always supplies a genuine `RunLogWriter`, and no lightweight
  logger double exists in `tests/test_roadmap_revision_run.py`; the branch is
  unreachable today. Splitting the function into strict and permissive
  variants would reintroduce the duplication R1-3/4 removed.
- **R2-3 — new non-written-outcome guarantee unasserted in the leaf's tests**
  (severity not recorded): `digest`/`response_bytes` for `NOT_RETAINED` and
  `WRITE_FAILED` were only covered indirectly. **Disposition:** fixed
  `8c0ffead` — added `test_digest_and_response_bytes_survive_a_non_written_outcome`.

### Round 3 (2026-09-22, range `19dd3cdb..HEAD`; chain-correct base was `8bd2b8f9`)

The stated range re-included `8bd2b8f9`, already reviewed in round 2; findings
are unaffected. Fix commit: `14e6dc5c`; docs commits `2393f51e`, `7bf0f530`,
`8d13b49c`. Full suite: 13343 passed, 189 skipped (the one skip-to-pass shift
versus round 2 is unrelated to this comment-only diff).

- **R3-1 — `_roadmap/{slug}` still collides with a `register`-adopted plan**
  (severity: low, low-likelihood; CONFIRMED by direct trace): `register`
  (`cli/manifest.py:64`) never validates the slug against `SLUG_RE`, and
  `slug_from_filename()` (`locator.py:669`) returns the bare stem, so a plan
  registered as `_roadmap.md` has slug `_roadmap` and `detail.py` writes its
  sidecars into the shared root. Rounds 1, 2 and 3 are one collision through
  three narrower surfaces; no fixed literal prefix can close it. **Disposition:**
  tracked `BUG_BACKLOG.md` — MINOR entry "No fixed `producer_slug` prefix can
  structurally rule out a sidecar-directory collision with a `register`-adopted
  plan" (open design choice: tighten `register` slug validation, or move
  roadmap sidecars out of the shared `parse-failures/` namespace); the
  overclaiming `roadmap.py` comment was corrected in `14e6dc5c`. Classified as
  non-converging exit 3. Soundness caveat: the exit-3 classification is asserted
  rather than shown by a `git log -S` trace, and rounds 1-2 never swept
  `register`/`cmd_register`/`slug_from_filename`, so the recurrence is partly
  self-seeded by an incomplete round-1 sweep; both readings give the same
  outcome (out-of-scope structural rework, filed).

### Round 4 (2026-09-22, range `8c0ffead..HEAD`; chain-correct base was `2393f51e`)

The stated range re-included `2393f51e`; findings are unaffected. Round 3's
fix `14e6dc5c` and docs commits `7bf0f530`, `8d13b49c` were in range. Two
verification agents confirmed every technical claim in the new comment and
backlog entry.

- **R4-1 — R2-1's superseded rationale left in present tense** (severity:
  low; a documentation-accuracy defect confined to this ledger): R2-1's
  "genuinely structural" claim stayed uncorrected although R3-1 disproves it.
  **Disposition:** fixed `93129a35` — dated correction note on R2-1 pointing to
  R3-1, plus the exit-2/exit-3 soundness caveat on R3-1. Docs follow-up: `3ea3503c`.
  Ledger-text-only; no suite re-run.

### Round 5 (2026-09-22, range `14e6dc5c..HEAD`: `93129a35`, `3ea3503c`)

Five findings, all defects in this ledger's own bookkeeping about rounds 3-4,
each confirmed by `git log -S` / range checks before applying:

- **R5-1 — correction note misattributed to round 3** (severity not recorded):
  the note on R2-1 was added by `93129a35` (round 4), not round 3. **Disposition:**
  fixed — attribution corrected.
- **R5-2 — round 3 scope range wrong** (severity not recorded): stated base
  `19dd3cdb` instead of `8bd2b8f9`. **Disposition:** fixed — correction note added.
- **R5-3 — round 4 scope range wrong** (severity not recorded): stated base
  `8c0ffead` instead of `2393f51e`. **Disposition:** fixed — correction note added.
- **R5-4 — R4-1 lacked a severity** (severity not recorded): the low-yield
  convergence call was unverifiable against it. **Disposition:** fixed — severity
  stated as low.
- **R5-5 — R4-1 missing its commit-hash line** (severity not recorded).
  **Disposition:** fixed — `93129a35` recorded.

Fixed in commit `df51b906`; ledger-text-only, no suite re-run.

### Convergence status

**Converged on the code; the loop stops here.** Round 5 was not clean (five
real findings), but every finding since round 3's code fix (`14e6dc5c`)
describes this ledger's own bookkeeping about a prior round, never the shipped
code. This is the `self-seeded-finding` shape, generalized from auditing a
prior code edit to auditing a prior doc edit about that code: rounds 4 and 5
caught real defects, now fixed, but re-scoping `/code-review` against a ledger
that records its own review history is an unbounded regress. Each correction
becomes new prose the next round can fault (mislabeled attribution, circular
justification, missing severity) regardless of whether the code has a defect
left. Per the stopping rule for this shape: finish applying (done), then stop
auditing that dimension.

By object:

- **Shipped code** (`ab6908ac`, `19dd3cdb`, `8c0ffead`, `14e6dc5c`, including
  the round-3 `roadmap.py` comment correction): clean since round 2 fixed its
  last material finding. Round 3's one code-level issue (the sidecar-namespace
  residual) is filed to `BUG_BACKLOG.md` as an open design choice. No later
  round found anything new in the code.
- **This ledger**: accurate and internally consistent after round 5's
  corrections. It is not the deliverable the loop exists to converge, so
  further rounds scoped at its growth audit a different, self-referential
  artifact.

**Open item, deliberately not closed by this loop:** the `BUG_BACKLOG.md`
entry "No fixed `producer_slug` prefix can structurally rule out a
sidecar-directory collision with a `register`-adopted plan" — real,
low-severity, low-likelihood, needing a design decision outside this plan's
scope. Surfaced to the user.

Full suite last run at round 3: 13343 passed, 189 skipped; rounds 4-5 touched no source.

### Out-of-range / recall-mode findings

_(none)_

## Roadmap candidate vocabulary retry — plan review pickup

*Opened 2026-09-25.*

The plan for `IPPT-10` (resolve the site from `.claude/local/project-context.json`) is on branch `plan/structural-candidate-vocabulary-retry`. It is ready for the required plan pull request and architect review before `run`. The plan and all three detail files are committed; implementation has not started.

### Current artifacts

- Plan: `docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md`.
- Details: `docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/` (3 of 3).
- Source seed: `plan-seeds/archive/roadmap-candidate-vocabulary-retry.replaced.md`.
- Tracking: `BUG_BACKLOG.md` retains the IPPT-10 promotion stub until implementation ships.
- Remote plan branch: `origin/plan/structural-candidate-vocabulary-retry`.

### Audit gate evidence

These are 2026-09-25 observations, not current checkout qualification. Captures
and sidecars are omitted; the retained summaries preserve their limits.

The bare-plan gate uses `plan-tool --backend codex --model gpt-5.6-terra completeness-audit § "Roadmap candidate vocabulary retry — plan review pickup" --iterate --commit --audit-passes 1 -y`. Three committed snapshots move from two correctness findings, through two newly exposed correctness findings, to zero. The final bare report is [retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions): 0 of 3 details, confirmed coverage, current revision, converged, no correctness or completeness findings. Detail-level axes are withheld at this gate.

`plan-tool --backend codex --model gpt-5.6-terra detail § "Roadmap candidate vocabulary retry — plan review pickup" -y --commit` writes all three details. Its built-in conceptual check finds two detail contradictions: overlapping retry ownership in step 1 and missing source-bound hints in stored-candidate review calls. The session-directed correction assigns all retry behavior to step 2 and covers both review replacement and structural edit prompts in step 1.

The detail-grounded gate uses the same `completeness-audit --iterate --commit --audit-passes 1 -y` command. The final report is [retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions): 3 of 3 details, confirmed coverage, current revision, converged, zero correctness and completeness findings. The four claim-versus-footprint INFO heuristics are advisory and do not describe an unowned contract. The branch push runs and passes the repository's pre-push test suite.

### Next action

Open a Bitbucket pull request from `plan/structural-candidate-vocabulary-retry` to `main`, link it on IPPT-10, and obtain the plan review and merge. The available Atlassian MCP tools in this session do not expose Bitbucket pull-request creation, so the PR is not opened here. After merge, branch from updated `main`, run the plan with `--commit`, then drive `reconcile-code --all` and code review to convergence. Do not bypass the plan merge check.

## Roadmap candidate envelope diagnostics — post-run review ledger

*Opened 2026-09-26.*

### Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-candidate-envelope-diagnostics` (`docs/implementation-plans/archive/2-roadmap-candidate-envelope-diagnostics.md`), 7 steps (5 code, 6 and 7 non-code). Source: `BUG_BACKLOG.md` § "Candidate proposal retries still emit incompatible row-operation envelopes…" (`PLAN-AUTHORED`). |
| Branch | `impl/roadmap-candidate-envelope-diagnostics`, based on `main` at `24b32aff`, pushed to `origin`. |
| Review range | `24b32aff..HEAD`; `plan_tool/` and `tests/` only. |
| Run | Steps 1–5 green, each through the full-suite gate; step 6 green (tests only). Step 7 is marked done without its edit; the closure is a direct edit (see "Decisions"). |
| Checks run | Bare and detail-grounded `completeness-audit --iterate` gates, both converged. `reconcile-code --all`: sweep 1 found 2 medium (fixed `48af5acb`, `205b3878`), sweep 2 found 0. Full suite after the last fix: 14022 passed, 190 skipped. |
| `/code-review` | Three independent `high` report-only passes. Pass 1 (`24b32aff..183b8d2b`): 1 high, 1 medium, 3 low, 2 nit, plus owner-note discrepancy P1.0. Pass 2 (`..7c52de70`): 2 low. Pass 3 (`..e59e5336`): 2 low. |
| Current disposition | **Converged (2026-09-27).** Passes 2 and 3 returned only low findings; see "Convergence status". |

### Settled decisions (hand these to every reviewer)

A finding that proposes the opposite is invalid, not deferrable.

- **The strict parser stays strict.** A known class name selects a row schema for diagnosis only; the response is still rejected. No parse-time coercion, dropping, or repair of unknown fields, class names, or `source`.
- **The hint is reshaped, never removed.** `PatternRow` maps to `system_patterns` and `component_patterns`; the hint's `collection` is the only disambiguator. No hint record carries `artifact_key`, `row_type`, `row_id`, or `collection` at its top level.
- **One correction names every defect.** The retry has one correction, so operation-field defects and an invalid `row_type` are reported together. An unknown field is named when the tool defines the name: operation keys, row and nested-record keys, `DecisionRow` fields (so `source`), and the discovery keys (`collection`, `source_collection`, `issued_row`, `row_digest`). Any other name is `other`, so a correction never repeats arbitrary model text. Names of one kind share a clause.
- **Unchanged on purpose.** The two-attempt bound, the capsule's class-name `identity` records, receipts and digests, replay identity, the run-log schema. Rejected responses keep their exact bytes.
- **Prompt shapes come from the parser's own key sets** (shared constants).
- **Existing value-echoing messages are not reworded** (unknown `op`, duplicate JSON key).
- **Per-row-type example bodies beyond `entities` are out of scope.** `DecisionRow.source` is the only mismatch between a row dataclass and the parser's accepted keys.
- **Deliberately not:** a run-log schema change, receipt redaction, a third attempt, any check of model content beyond the closed wire vocabulary.

### Decisions (owner)

- **Step 7 and the Integration re-run — closed on deterministic proof (2026-09-27).** The `PLAN-AUTHORED` entry is removed from `BUG_BACKLOG.md`. Evidence: steps 1–6, both `reconcile-code` sweeps, and three review passes, all committed, suite green. The Integration `--propose-candidate` re-run is deliberately not run: it needs a build containing this branch in the canonical checkout, calls a live model, and writes into Integration's files, so it stays a separate, unrecorded acceptance check. If a later Integration run still emits `collection` or a class-name `row_type`, file a new entry with that run's stored responses and do not add parse-time repair.

### Findings

#### Reconcile-code sweeps

- **RC1 — `PatternRow` correction named one collection** (medium): the `invalid-row-type` correction for `PatternRow` named only `system_patterns`. **Disposition:** fixed `48af5acb` — the new test fails when reverted.
- **RC2 — stored `add-row` shape unproven end to end** (medium): the only run-level retry fixture malformed a `replace-row`, where `row_id` is legitimate. **Disposition:** fixed `205b3878` — new test beside the existing one.
- Sweep 2: 0 findings on steps 1–5; a third sweep is not run (it would resample unchanged code).

#### Pass 1

- **P1.0 — `collection` reported as `other`** (owner-note discrepancy): the plan says tool-defined names, `collection` included, are named; the settled wording (this ledger's own) was wrong and the code reported the stored Integration defect as `other`. **Disposition:** fixed `2c993f91` — `_DISCOVERY_FIELD_NAMES` joins the reportable names at all six operation-level sites (naming only, accepted keys unchanged); two tests that pinned `other` changed, and a parametrized test pins each name plus the invented-names-stay-`other` carve-out.
- **P1.1 — corrected `decisions` row cannot be stored** (high, CONFIRMED): dropping `source` parses as `DecisionRow(source=None)`, but evidence re-serialization writes `"source": null`, which the strict parser refuses, so a compliant reply never stores (the stored-evidence replay had the same defect). **Disposition:** fixed `2c993f91` — `_operations_wire_for_reparse` drops only a null `source` at all three re-parse sites; identity and digest wire form unchanged, a supplied `source` stays refused; the retry test now stores the corrected row.
- **P1.2 — class-name `row_type` on a relationless collection hides the reached-anchor defect** (medium, CONFIRMED): `HostingRow`, `PatternRow`, `AttributeDispositionRow` were checked as raw class names, so the retry was spent on the anchor rule. **Disposition:** fixed `2c993f91` — the check reads the resolved schema; parametrized test, red when reverted.
- **P1.3 — some operation defects surface one at a time** (low, PLAUSIBLE): malformed `ordering`, `replace-row` `row.id` differing from `row_id`, or a non-string id are checked only by `_parse_operation`. **Disposition:** tracked `BUG_BACKLOG.md` (`a7fd01dc`, "The single candidate correction still names only the first of several operation defects…") — outside the plan's three-reason vocabulary and absent from stored Integration replies.
- **P1.4 — no operation index; identical clauses repeat** (low, PLAUSIBLE): **Disposition:** declined — the plan requires naming every defect, not locating each; no stored reply or test shows a retry failing for want of an index.
- **P1.5 — examples show `"ordering": null` while prose says omit** (low, PLAUSIBLE): **Disposition:** fixed `2c993f91` — prose says to keep `ordering` `null` unless changing the plans ordering entry (superseded in part by P3.1).
- **P1.6 — dead `if "op" not in record` guard; each valid row parsed twice** (nit, CONFIRMED): **Disposition:** guard fixed `2c993f91` (deleted); double parse declined — merging the pre-pass and `_parse_operation` is a refactor the plan does not ask for.
- **P1.7 — `_ROW_TYPE_BY_CLASS_NAME` restates the inverse of the canonical collection map** (nit, CONFIRMED): **Disposition:** fixed `2c993f91` as a test (table keys equal the canonical class names, each maps to a collection assigned to that class), not a derivation, which would change `PatternRow`'s two-collection handling.
- **P1.R — `remove-row` with a non-collection `row_type` now fails at parse time** (reviewer-rejected candidate): **Disposition:** refuted by the reviewer — materialization already refuses such a `row_type`, so stored evidence cannot hold one.

#### Pass 2

- **P2.1 — a `remove-row`'s forbidden `row` body diagnosed as an intended row** (low, CONFIRMED): a stray malformed `row: {}` drew both `unknown-field row` and `entities row has missing-field …`, so acting on the second clause wastes the retry. **Disposition:** fixed `931b6625` — the row-body check runs only for operations whose parser key sets include `row`; test asserts `unknown-field row` and no `entities row has …` clause, red when reverted.
- **P2.2 — root-level key defect hides operation defects** (low, CONFIRMED behavior): root checks raise before the operation pre-pass, so both cannot appear in one correction. **Disposition:** tracked `BUG_BACKLOG.md` (the entry filed for P1.3, extended; the source gives no separate commit for the extension) — collecting root diagnostics changes `parse_candidate_delta` control flow for a defect with no observed instance.
- Re-checked: P1.0, P1.1, P1.2, P1.5 verified complete; the reviewer rejected two of its own candidates as contradicting settled decisions or already dispositioned.

#### Pass 3

- **P3.1 — prompt calls `ordering` optional, but a `plans` row requires it** (low, CONFIRMED): materialization requires a matching `ordering` on a `plans` `add-row` and `remove-row` (removal equals the predecessor entry exactly) and refuses it elsewhere. Partly self-seeded by P1.5. **Disposition:** fixed `5a59ae7e` — the prose says `ordering` is `null` except for `plans`, where an add or removal requires an `ordering` object naming the plan and a removal repeats the existing entry; a prompt test pins the three claims, red on the old prose.
- **P3.2 — `_render_batch_operation_shapes` raises a bare `KeyError` if a parser key set grows** (low, PLAUSIBLE): **Disposition:** declined — the trigger is a developer editing shared key sets, not model or operator input, and `test_batch_prompt_renders_parser_owned_operation_shapes` fails loudly first; moving the call under the `try` would turn that drift signal into a quiet run-time refusal.
- Considered and not reported: row-level unknown fields other than `DecisionRow` fields report as `other` (the rule names discovery names only at operation level); the selector-shaped prompt gets no operation shapes since only the batch route retries.

### Out-of-range findings

_(none)_

### Convergence status

**Converged after three passes (2026-09-27).** Pass 1 returned a high and a medium finding, so the streak begins at pass 2. Passes 2 and 3 each returned two low findings and nothing material, with no sibling regression in earlier fixes: the stopping rule's two consecutive low-only passes. This is low-yield convergence, not a clean audit. The advisory tail is the tracked `BUG_BACKLOG.md` entry (P1.3, P2.2) and the declined P1.4, P1.6 (double parse), and P3.2. P3.1 was partly seeded by the P1.5 edit, so its fix is prose plus a test, and no further pass is run. The last full suite ran after the P3.1 fix: 14022 passed, 190 skipped.

## Candidate anchor/gate correction — review ledger

*Opened 2026-09-27.*

| Range | Head | Checks | Reviewer | Disposition |
| --- | --- | --- | --- | --- |
| `f9d3d2c4~1..f9d3d2c4` | `f9d3d2c4` | Final full suite (`uv run pytest tests/ -q -n auto`): 14050 passed, 190 skipped, exit 0 under `pipefail` | `/code-review high`, 8 passes | Converged, low-yield, after eight passes (2026-09-27) |

### Change under review

`f9d3d2c4` — "Name the non-addable collection and gate violation in candidate
corrections". The add-row-on-relationless-type refusal and the gate-failed
refusal now name the specific collection or violation kind and its remediation,
derived from closed gate facts (`roadmap_gates.VIOLATION_*` kinds,
`outcome.stage`, a validated `row_id`) and never from a violation's free-form
message, so a retry prompt never echoes model-authored prose.

### Settled decisions for the reviewer

- `_gate_correction` must never surface a `Violation`'s own `message` field —
  that field can carry arbitrary prior model output, and echoing it into a
  correction/prompt is the injection surface this change closes. Only the
  closed `kind` (checked against `_KNOWN_GATE_KINDS`), the stage's
  `artifact_key`, and a shape-validated `row_id` may appear.
- An unrecognized `kind` (a future `VIOLATION_*` not yet in the
  `kind`→condition mapping, or any value not in `_KNOWN_GATE_KINDS`) must not
  raise or leak. **Superseded by P1.2 (pass 1):** the bullet originally said
  the whole call falls back to the generic refusal text; that discarded every
  specific correction already built for the violation's siblings. The current,
  tested rule is per-violation degradation, not a whole-call fallback.
- `NON_ADDABLE_ROW_TYPES` is the public, sorted mirror of the existing
  `_RELATIONLESS_ADD_ROW_TYPES` set; the prompt's non-addable-collections
  notice must stay in sync with the parser's own rejection rule, not a
  restated list.

### Findings

The source records no fix commit ids per finding; "fixed" means fixed on the
review branch, with the named test where one exists.

#### Pass 1

- **P1.1 — `_gate_correction` named the checked stage, not the violation's artifact** (high, CONFIRMED): `artifact_key` is a bare stage name while `Violation.artifact` is the filename, so retries were sent to the wrong location. **Disposition:** fixed — uses `violation.artifact`; `test_gate_correction_names_the_violations_own_artifact_not_the_checked_stage`.
- **P1.2 — an unrecognized kind discarded every already-built sibling correction** (medium, CONFIRMED, defensive only). **Disposition:** fixed — appends a fallback line and continues; `test_gate_correction_keeps_specific_guidance_beside_an_unrecognized_violation`.
- **P1.3 — the row-id regex duplicated `RECEIPT_SAFE_ID_RE` with a wider set (allowed `:`)** (medium, CONFIRMED). **Disposition:** fixed — reuses the constant; `test_gate_correction_treats_a_colon_bearing_row_id_as_unsafe_to_echo`.
- **P1.4 — the legacy selector prompt lacked the non-addable warning** (medium, CONFIRMED, framing corrected: the selector path never had a retry loop, so nothing regressed). **Disposition:** fixed — `test_selector_prompt_also_warns_about_non_addable_collections`.
- **P1.5 — five same-shape kinds missed their buckets on vocabulary** (medium, CONFIRMED for 5 of ~20 cited): `unanchored-constraint`, `uncited-removal`, `unreasoned-alternative`, `redundant-disposition`, `redundant-hosting-facet`; the cited `no-entity-reference`/`undefined-entity-reference` pair is correct. **Disposition:** fixed for the five (`test_gate_correction_routes_zero_content_and_redundant_kinds_to_their_matching_condition`); declined for ~15 idiosyncratic kinds — forced bucketing gives worse guidance than the generic fallback.
- **P1.6 — the relationless-add-row check in `_parse_operation` was unreachable** (low, CONFIRMED). **Disposition:** fixed — removed.
- **P1.7 — a shape-mismatched, violation-free `outcomes` tuple gets generic text indistinguishable from an ordinary refusal** (low, PLAUSIBLE). **Disposition:** declined — pre-existing; distinguishing tool-broken from candidate-wrong is a new capability. Not tracked; `test_candidate_returns_no_candidate_when_the_complete_gate_bundle_fails` pins today's behavior.
- **P1.8 — no test covered the mixed known/unknown-kind path** (low, CONFIRMED). **Disposition:** fixed with P1.2.

#### Pass 2

- **P2.1 — `redundant-*` kinds got rename-shaped "keep unique" text; the fix is dropping extra rows** (medium, CONFIRMED). **Disposition:** fixed — own condition; `test_gate_correction_tells_a_redundant_kind_to_drop_the_extra_rows_not_rename_them`.
- **P2.2 — the docstring described the wrong branch of `check_duplicate_row_ids`** (medium, CONFIRMED). **Disposition:** fixed — states only the verified fact and points to the gate.
- **P2.3 — the unrecognized-kind fallback used the bare stage key as location** (low, CONFIRMED). **Disposition:** fixed — `test_gate_correction_uses_the_violations_own_artifact_for_an_unrecognized_kind_too`.
- **P2.4 — the docstring was a multi-line block against the terse-comment rule** (low, CONFIRMED). **Disposition:** fixed with P2.2.
- **P2.5 — the notice paragraph was duplicated into both templates with no equality test** (low, CONFIRMED). **Disposition:** fixed — shared fragment; `test_batch_and_selector_prompts_share_the_non_addable_collections_notice`. The fragment was later replaced (P5.x).
- **P2.6 — nothing tied the kind table to the `VIOLATION_*` set; `undisposed-attribute` still fell to generic** (medium, CONFIRMED). **Disposition:** fixed — `_INTENTIONALLY_GENERIC_GATE_KINDS` (15 kinds); `test_gate_correction_classifies_every_known_kind_by_name`. Full per-kind rewrite stays declined.

#### Pass 3

- **P3.1 — four drop-shaped `duplicate-*` kinds still got rename-shaped guidance** (medium, CONFIRMED): `duplicate-inherited-decision`, `duplicate-feedback-id`, `duplicate-store-reference`, `ordering-plan-id-duplicate` — the P2.1 defect unswept on siblings. **Disposition:** fixed — `_DROP_EXTRA_ROWS_GATE_KINDS`; `test_gate_correction_tells_a_drop_shaped_duplicate_kind_to_drop_not_rename`.
- **P3.2 — a 6-line `_INTENTIONALLY_GENERIC_GATE_KINDS` comment** (low, CONFIRMED). **Disposition:** fixed — two lines.
- **P3.3 — the fragment read had no missing-file guard (bare `FileNotFoundError`)** (low, CONFIRMED). **Disposition:** fixed for both template reads via `_read_candidate_prompt_file`; `test_missing_candidate_prompt_file_is_a_domain_error_not_a_bare_file_not_found`. Caused P4.1.
- **P3.4 — the fragment is re-read on every call** (low, PLAUSIBLE). **Disposition:** declined — the main template is equally uncached and a module-level cache breaks `prompts_dir()` monkeypatching; superseded by P5.x.

#### Pass 4

- **P4.1 — pass 3's guard let a missing template escape `request_replacement`** (high, CONFIRMED, self-inflicted): `CandidateProposalError` is a `ValueError`, not the `OSError` the old `except` caught; the only unswept caller of three. **Disposition:** fixed — except tuple `(OSError, CandidateProposalError)`; `test_request_replacement_surfaces_a_missing_prompt_template_as_failed_not_uncaught`. Changing an exception type is class-wide: sweep from "who catches the old type".
- **P4.2 — the fragment's `Template.substitute()` sat outside the domain-error mapping** (medium, CONFIRMED). **Disposition:** fixed — own try/except; `test_non_addable_collections_fragment_substitution_failure_is_a_domain_error` (removed with the fragment).
- **P4.3 — the `is_file()` guard missed permission/TOCTOU/encoding failures and reinvented `roadmap.read_roadmap_text`** (medium, CONFIRMED). **Disposition:** fixed — delegates to `read_roadmap_text`.
- **P4.4 — `render_candidate_question_prompt` uses a bare `read_text()`** (low, CONFIRMED). **Disposition:** declined — pre-existing, correctly handled by its caller's `except OSError`, outside scope. Re-raised as P5.5.

#### Pass 5

- **P5.1 — the fragment's missing-file error was relabeled by pass 4's `except (KeyError, ValueError)`** (high, CONFIRMED, self-inflicted). **Disposition:** fixed by removing the mechanism (below).
- **P5.2 — `correction_reason`'s error sat inside the substitution try and was relabeled** (medium, CONFIRMED, pre-existing). **Disposition:** fixed — validation moved before the `try`; `test_correction_reason_on_a_non_batch_capsule_raises_its_own_specific_message`.
- **P5.3 — the kind→remedy classifier is a prefix matcher with hand-curated exceptions; no test catches a future kind in the wrong bucket** (medium, CONFIRMED). **Disposition:** tracked #431 — a `remedy_shape` field at ~90 `Violation(...)` sites is out of this diff's module scope; the current kind set is verified by execution.
- **P5.4 — the fragment re-templated a static string per call** (medium, CONFIRMED; reframes P3.4). **Disposition:** fixed by removing the mechanism (below).
- **P5.5 — `render_candidate_question_prompt`'s bare `read_text()` (raised twice, with P4.4)** (low, CONFIRMED). **Disposition:** tracked #432.
- **P5.6 — `_INTENTIONALLY_GENERIC_GATE_KINDS` was a production constant read only by a test** (low, CONFIRMED). **Disposition:** fixed — moved to `tests/test_roadmap_candidate.py`.

P5.1/P5.2/P5.4 were closed together: three passes each patched the same ~10-line piece, so the fragment file, `Template`, and error mapping were replaced by `_non_addable_collections_notice()`, a plain string function (`plan_tool/prompts/roadmap-candidate-non-addable-collections.md` deleted). Pass 5 was a "the loop is auditing its own edits" signal, answered by removing the class rather than patching a fourth time.

#### Pass 6 — zero correctness bugs; first low-yield round

- **P6.1 — a branch comment restated the module comment** (low, CONFIRMED). **Disposition:** fixed.
- **P6.2 — `_non_addable_collections_notice()`'s docstring cited an inapposite precedent** (low, CONFIRMED). **Disposition:** fixed — states its own reason; the Python-string decision is not reverted.
- **P6.3 — `_DROP_EXTRA_ROWS_GATE_KINDS` dispatches by two mechanisms in one `elif`** (low, CONFIRMED). **Disposition:** tracked #431 — no new item.
- **P6.4 — the ledger's settled-decision bullet was stale against P1.2** (low, CONFIRMED). **Disposition:** fixed — annotated as superseded.

#### Pass 7 — zero correctness bugs; five advisory findings

- **P7.1 — `_read_candidate_prompt_file` was a single-use wrapper against the inline-closure idiom** (low, CONFIRMED). **Disposition:** fixed — inlined with `unreadable_template`; `BACKLOG.md` #432's suggested approach updated.
- **P7.2 / P7.4 / P7.5 — three paragraph-length comments/docstrings** (low, CONFIRMED). **Disposition:** fixed — trimmed; the `_DROP_EXTRA_ROWS_GATE_KINDS` comment points at #431.
- **P7.3 — `isinstance(capsule, CandidateContextBatchCapsule)` evaluated three times** (low, CONFIRMED). **Disposition:** fixed — cached as `is_batch`.

#### Pass 8 — zero new correctness bugs; four low findings

Prior tracked/declined items (#431, P1.7, the load-bearing `getattr(violation, ...)` reads) were re-checked and not re-reported.

- **P8.1 — the `PatternRow` anchor diagnostic named only `system_patterns`** (low, CONFIRMED). **Disposition:** fixed — same two-collection substitution as `_invalid_row_type_diagnostic`; `test_candidate_delta_pattern_row_anchor_diagnostic_names_both_collections`.
- **P8.2 — `_gate_correction` inlined the safe-to-echo predicate** (low, CONFIRMED). **Disposition:** fixed — calls `roadmap_feedback.is_receipt_safe_id`; no import-cycle risk.
- **P8.3 — the notice string was rebuilt per call** (low, CONFIRMED). **Disposition:** fixed — module-level `_NON_ADDABLE_COLLECTIONS_NOTICE`.
- **P8.4 — three more over-long comments (the P7.2 class, unswept at siblings)** (low, CONFIRMED). **Disposition:** fixed.

### Out-of-range / recall-mode findings

_(none)_

### Convergence status

**Converged after eight passes (2026-09-27), low-yield.** Pass 6 was clean
(zero correctness findings). Pass 7 and pass 8 were each clean of correctness
bugs — 5 and 4 low-severity cleanup findings respectively, all fixed. Three
consecutive passes each added only low/advisory-severity findings, meeting the
stopping rule's low-yield exit. Passes 1–5 each found and fixed genuine,
material defects, including two self-inflicted regressions (P4.1 from pass 3's
fix; P5.1 from pass 4's fix); passes 6–8 found none. Pass 5 carried the
non-converging signal (three passes correcting the same fragment mechanism) and
was resolved by removing the mechanism. No further pass is warranted; the next
`/code-review` on this area treats this diff's baseline as converged and
reviews only its own new changes.

Open items: `tracked` #431 (P5.3, P6.3) and #432 (P5.5, P4.4). No `pending` findings.

Final full-suite result: 14050 passed, 190 skipped in 135.49s, exit 0 under
`pipefail`.

## Row-linked prose amendments in version comparison — code review ledger

*Opened 2026-09-29.*

| Field | Value |
| --- | --- |
| Change | `roadmap --compare` reports candidate row-linked prose amendments (BUG_BACKLOG "Version comparison omits row-linked candidate prose amendments") |
| Branch | `run/roadmap-candidate-row-prose-amendments` |
| Review range | `56ab19db..e81ec269` (pass 1 `3c355c63`; fixes `5c650a40`, `54c143af`, `970ea924`, `e81ec269`) |
| Reviewer | headless `claude -p` session, report-only (`.tmp/prose-amendments-code-review-1.stream.log`) |
| Disposition | converged after pass 5 (see Convergence status) |

### Settled decisions (hand to each reviewer)

- Patch output stays a byte-faithful Git patch; no renderer-added metadata.
- Binding rule (from the backlog entry): amendments bind only when the target is a
  stored candidate whose **direct** predecessor is the selected base. Any other
  candidate/base pair reports `not-directly-bound`; binding is never inferred from
  changed bytes. Deliberately not a multi-hop chain walk.
- Outcomes: `bound` (possibly empty), `not-applicable`, `not-directly-bound`.
- Malformed or unbindable candidate evidence refuses the comparison.

### Review pass 1 — /code-review (sonnet, headless), 2026-09-29

Scope: commit `3c355c63`. Method: read-only; the reviewer did not run the suite.

#### 1. Chain walk binds across many hops, contrary to the entry's direct-predecessor rule — medium
`plan_tool/roadmap_compare_run.py:129`. The commit's multi-hop test and
`ROADMAP_FORMAT.md` pinned the broader behavior.
**Disposition:** fixed (pass-1 fix commit) — replaced the walk with a single
direct-predecessor check; `ROADMAP_FORMAT.md` and its test now state the entry's rule.
This overrides the multi-hop wording committed in `3c355c63`, in favor of the spec.

#### 2. Fragments from a row added and later removed across hops would still be reported — medium, plausible
`plan_tool/roadmap_compare_run.py:141`.
**Disposition:** fixed — removed with finding 1 (single hop cannot reconcile against later hops).

#### 3. Non-ancestor case validated every candidate to the root before answering — low
`plan_tool/roadmap_compare_run.py:140`.
**Disposition:** fixed — removed with finding 1; a non-direct pair loads only the target candidate.

#### 4. Verification cases from the entry lacked tests — medium
`tests/test_roadmap_compare_run.py`.
**Disposition:** fixed — tests now cover direct binding with ordering, non-adjacent,
no-predecessor, base-is-the-candidate, row-only candidate (`bound`, empty), working/root/no-base
targets loading no candidate evidence, and malformed evidence refusing `run_roadmap_comparison`.
Verified by mutation: disabling the predecessor check turns 3 tests red. The cycle-guard
cases are gone with the walk. Raw-patch faithfulness is pinned by the existing renderer tests
(`render_patch_comparison` returns the captured patch unchanged).

#### 5. Outcome meanings undocumented; card escapes multi-line fragments — low
`plan_tool/roadmap_compare_render.py:53`.
**Disposition:** fixed (docs) — `ROADMAP_FORMAT.md` and `docs/reference/commands.md` define
each outcome. Card JSON-quoting is deliberate (one line per item); JSON output carries the
exact fragment, and the format doc says so.

### Review pass 2 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..5c650a40` (whole feature). Method: read-only; the reviewer ran the three
comparison test files (52 passed) and checked binding, refusal, patch isolation, renderers,
and generated docs.

#### 6. `docs/ARCHITECTURE.md` read-only import-graph claim is now false — medium (docs)
`docs/ARCHITECTURE.md:300-311`. `roadmap_compare_run.py` imports `roadmap_candidate_run`, which
imports writer-layer modules. Verified against the imports (`roadmap_revision_publish`,
`roadmap_feedback_ledger`, `shell`, `fileio`, `RunLogWriter`).
**Disposition:** fixed (pass-2 fix commit) — the section names the second edge and the binding
rule; the extraction (moving the loader into a read-only leaf) is **tracked BACKLOG #406**,
deliberately not taken here (out of scope, per the consolidation-finding rule).

#### 7. `CAPABILITIES.md` `--compare` entry omits the new evidence — low
`CAPABILITIES.md:54-58`. **Disposition:** fixed — clause added, sibling of the other three docs.

#### 8. Full candidate validation runs for a `not-directly-bound` pair — low
`plan_tool/roadmap_compare_run.py:131-141`. **Disposition:** declined — validating the stored
candidate before answering is what makes "malformed evidence refuses" hold on every candidate
target; a cheap-predecessor-first read would silently let malformed evidence through for
non-adjacent pairs. Cost is one candidate load per comparison; no correctness effect.

### Review pass 3 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..54c143af` (whole feature, probing the pass-1/2 fixes). Method: read-only; the
reviewer ran 685 comparison and CLI tests. No regression from the pass-1/2 fixes.

#### 9. A candidate with no stored operation evidence is reported `bound` with an empty list — medium
`plan_tool/roadmap_compare_run.py:143`. Verified: `normalized_operations` is `None` for
selector-era and pre-route batch candidates (`roadmap_candidate_run.py:260,318,947`), and
`candidate_prose_amendment_diffs(None)` returns `()`. That rendered "admitted none" for
"unknown", breaking the never-inferred invariant.
**Disposition:** fixed (pass-3 fix commit) — new explicit outcome `no-operation-evidence`;
documented in `ROADMAP_FORMAT.md`, `docs/reference/commands.md`, `docs/how-to/roadmap.md`,
`CAPABILITIES.md`, `docs/ARCHITECTURE.md`. Unit test pins it; verified by mutation (removing the
guard turns it red).

#### 10. Binding tests stub the loader; no end-to-end case with a real stored candidate — low
`tests/test_roadmap_compare_run.py:98-113`. **Disposition:** fixed — 
`test_comparison_binds_a_real_stored_candidates_prose_amendment_to_its_root` (in
`tests/test_roadmap_candidate_run.py`, where the stored-candidate fixtures live) stores a real
prose-bearing batch candidate and compares its root to it through the real loader; verified by
mutation (emptying the projection turns it red). A real legacy (`None`-evidence) candidate is
covered by the unit stub only: the shape (`normalized_operations=None`) is the field's real
default, and no fixture stores a pre-route candidate.

#### 11. "Empty collection means admitted none" overstated what an empty result proves — low (docs)
`ROADMAP_FORMAT.md`. **Disposition:** fixed with finding 9 — the wording now scopes it to the
candidate's stored operations.

### Review pass 4 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..970ea924`. Method: read-only; the reviewer ran 89 tests and probed the full
base/target kind matrix and the never-inferred invariant. Both clean; no correctness findings.

#### 12. Shipped BUG_BACKLOG entry still present — medium (bookkeeping)
`BUG_BACKLOG.md:1190`. **Disposition:** fixed — entry removed (fully shipped; the loader-edge
remainder is tracked as BACKLOG #406). Provenance: Integration Group 3 compliance-boundary candidate
review, 2026-09-29.

#### 13. `commands.md` / `how-to/roadmap.md` called `no-operation-evidence` an "other pair" — low (docs)
**Disposition:** fixed — both reworded: the directly bound no-evidence candidate is named
separately from the `not-applicable` / `not-directly-bound` pairs.

#### 14. No drift guard tying the outcome vocabulary to the docs — low (tests)
**Disposition:** fixed —
`test_every_prose_amendment_outcome_is_named_in_each_comparison_guide` reads the `Literal` and
requires every outcome in all five guides. It immediately caught two real gaps (`bound` missing
from `commands.md` and `how-to/roadmap.md`), fixed; verified by mutation on `ARCHITECTURE.md`.
A cosmetic over-long line in `docs/ARCHITECTURE.md` is deliberately left unwrapped.

### Review pass 5 — /code-review (sonnet, headless), 2026-09-29

Scope: `56ab19db..e81ec269`, probing the pass-3/4 fixes. Method: read-only; 295 focused and 4687
wider tests passed. **Clean: no correctness, docs, or bookkeeping findings.** Two cosmetic ledger
points (header range, a test's file location) were corrected in this ledger.

### Convergence status

**Converged — low-yield then clean.** Pass 1: 5 findings (3 medium). Pass 2: 3 (no correctness
bugs). Pass 3: 3 (1 medium correctness). Pass 4: 3 (bookkeeping and low docs/tests, no correctness).
Pass 5: clean. Two consecutive passes (4, 5) were low-yield/clean, so the loop stops.

Deliberately not done: no push, no PR (not requested). Tracked follow-up: BACKLOG #406 (moving the
stored-candidate loader into a read-only leaf). Declined: finding 8. Left: one over-long line in
`docs/ARCHITECTURE.md`.

## Candidate capsule fixes — code review ledger

*Opened 2026-10-05.*

| Field | Value |
| --- | --- |
| Change | Two `BUG_BACKLOG.md` entries: "Stored candidate capsules cannot restore any Decision row" and "Candidate source-span evidence duplicates shared text until an approved full feedback batch exceeds the context ceiling" |
| Branch | `docs/candidate-capsule-bugs` |
| Review range | pass 1: `d4f1833c..ce4976fe` (Decision-row restore `918fe02a`; changelog `8c3c23e0`; span table `ce4976fe`); pass 2: `d4f1833c..6720212a` |
| Checks run | Full suite `uv run pytest tests/ -q -n auto`: 14,362 passed, 190 skipped; the two route tests below were added after that run and pass with the three candidate test files (`-n auto`). Both fixes verified by mutation (reverting each turns its new tests red). Behavior checks that the static reviews could not make: see "Behavior checks". |
| Reviewer | headless `claude -p` session, report-only, `high` effort (`.tmp/candidate-capsule-code-review-N.stream.log`) |
| Disposition | passes 1 and 2 triaged; pass 3 pending (convergence needs two consecutive clean or low-yield passes) |

### Settled decisions (hand to each reviewer)

- `_parse_stage_row` stays strict for model-proposed rows; it rejects `source` on a
  decisions row, and `tests/test_roadmap_candidate_run.py` pins that.
- Stored rows restore through `_restore_stored_stage_row`: a Decision row has its own
  restore that admits `source`, and every restored row must round-trip to its stored
  wire form. The restored row id must match the member identity.
- Batch payloads are schema 2: a top-level `shared_source_spans` table holds each
  shared span once, keyed by `(artifact_key, span_id)`, and a member names its shared
  spans in `shared_source_span_ids` (absent when it has none). Single-owner spans stay
  inline in the member's `source_spans` in their schema-1 form, so a batch with no
  shared span is no larger than before. Selector payloads stay schema 1 because stored
  ones are verified by exact recompilation.
- Stored batch capsules are bound by digest and member receipts and are never
  re-rendered, so schema-1 batch capsules keep verifying. A test covers this.
- Member `source_spans` stay on `CandidateContextFullMember` and the receipts; only the
  rendered payload changed. Edit authority, receipts, and the 192 KiB ceiling are unchanged.
- Deliberately not in the span-table fix: filtering spans to those eligible for the
  admitted feedback batch, and a per-section size breakdown on `payload-over-budget`.
- The clean structural seal pin in `tests/test_roadmap_candidate_review.py` was
  re-recorded twice with the narrative check disabled, as originally recorded (the pre-change
  code reproduces the original id). Payload bytes changed, approval behavior did not.

### Review pass 1 — /code-review (high, headless), 2026-10-05

Scope: `d4f1833c..ce4976fe`. Method: static reading plus grep over every consumer of capsule
`source_spans` and `schema_version`; the reviewer did not run the suite and no permission denial
thinned the review (stream log `.tmp/candidate-capsule-code-review-1.stream.log`, findings
`.tmp/candidate-capsule-code-review-1.md`). No bug in the primary paths of either fix.

#### 1. The span table made single-owner spans larger, so an unshared batch could newly exceed the ceiling — medium
`plan_tool/roadmap_candidate_context.py:1114`. Each single-owner span gained a member id entry, a
repeated `span_id`, and an `artifact_key`: about 100 bytes per span, and only shared spans got cheaper.
**Disposition:** fixed 6720212a — the table holds only shared spans (`shared_source_spans`);
single-owner spans stay inline in their schema-1 form, and a member with no shared span carries no
extra key. A batch with no shared span differs from schema 1 only by `"shared_source_spans":[]`.
Pinned by `test_batch_payload_without_a_shared_span_is_no_larger_than_the_schema_one_layout` and
`test_batch_payload_keeps_single_owner_spans_inline_and_omits_the_empty_shared_id_list`; reverting to
the all-in-table layout turns those and three sibling tests red. The seal pin was re-recorded again.
This corrects the earlier schema-2 design in the settled decisions above.

#### 2. `_hydrate_capsule` refuses stored rows of 5 of 12 row types — medium
`plan_tool/roadmap_candidate_run.py:2056`.
**Disposition:** refuted — `_DELTA_ROW_TYPES` has all 12 row types (Entity, BusinessRule, Workflow,
Decision, AttributeDisposition, Constraint, Hosting, Pattern, Store, Component, Plan, Assumption); the
reviewer counted 6. No row type reaches the "unsupported row type" raise. Not run: the reviewer's
reachability scenario, since there is no unmapped type to build it from.

#### 3. Batch re-entry compares the whole receipt, so an upgrade changes the answer for an existing active candidate — low
`plan_tool/roadmap_candidate_run.py:1581`.
**Disposition:** declined — receipt equality is the existing contract: any change to the compiled
context (an earlier ceiling change included) makes a re-run build a fresh candidate instead of
returning the stored one. Reachable only by re-running `--propose-candidate` on an unchanged ledger
after the upgrade, and the outcome is a new candidate, not a wrong one. The reviewer could not confirm a
live path and neither could we; this has not been exercised end to end.

#### 4. `ROADMAP_FORMAT.md` still states the per-owner repetition as current — low
`ROADMAP_FORMAT.md:977`.
**Disposition:** fixed 6720212a — the clause is removed; the replacement byte ceiling is the
lasting reason a large shared block is not issued.

#### 5. The restore error embeds stored identity strings unescaped — low
`plan_tool/roadmap_candidate_run.py:2058`.
**Disposition:** declined — `where` is the artifact key and row id of a capsule that already passed
`_capsule_is_intact`, and both come from the artifact parser's id rules, not free text.

### Review pass 2 — /code-review (high, headless), 2026-10-05

Scope: `d4f1833c..6720212a`. Method: static reading and grep over every consumer of the span and
schema-version fields. A permission denial blocked the reviewer's Python runs, so it executed
nothing and its runtime question (finding 2) was checked afterward in the driving session (stream
log `.tmp/candidate-capsule-code-review-2.stream.log`, findings `.tmp/candidate-capsule-code-review-2.md`).

#### 1. Decision rows stored before `DecisionRow.source` existed now refuse instead of restoring — medium, plausible
`plan_tool/roadmap_candidate.py:1285`.
**Disposition:** declined — a stored row's `row_digest` was computed before `source` joined the row
wire form, so it can never equal the live `_row_digest`, and `candidate_collection_hints`
(`roadmap_candidate_context.py:311`) refuses that mismatch on the proposal-prompt path. Accepting the
row at restore would move the refusal to a later site rather than make the candidate usable. Reasoned
from the code; a pre-2026-09-16 stored candidate was not built and run. The `missing-source` test case
stays, and its name says "malformed".

#### 2. Decision-row restore is only tested on a hand-built wire dict, never on the persisted form — medium-low
`tests/test_roadmap_candidate_run.py:4167`.
**Disposition:** fixed 9d6a48f1 — the reviewer's worry that `exclude_none=True` strips
`source: null` is refuted by running it: the persisted row keeps `"source": null`, authored and inherited.
The missing coverage was real: `test_decision_row_survives_the_persisted_evidence_round_trip` dumps a
capsule with `exclude_none=True`, reloads it as dicts, and hydrates it. Swapping the restore back to
`_parse_stage_row` turns both cases red.

#### 3. The prompt does not say how a shared-table entry maps to the operation's `artifact_key` — low
`plan_tool/prompts/roadmap-candidate-delta.md:38`.
**Disposition:** fixed 9d6a48f1 — one sentence: a table entry belongs to the artifact in its
`artifact_key`; copy that and its `span_id` into the operation. No code change.

#### 4. Per-owner repetition wording disagrees across four sites after pass 1 finding 4 — low
`plan_tool/roadmap_revision.py:1354`, two test docstrings, `ROADMAP_FORMAT.md:977`.
**Disposition:** fixed 9d6a48f1 — an incomplete vocabulary sweep in the pass 1 fix. One
statement now holds at all four sites: a selector capsule repeats a shared span per owner and a batch
capsule issues it once, and the replacement ceiling is why a larger shared block is not issued.

#### 5. The schema-1 batch compatibility test cannot see a layout change in a consumer — low
`tests/test_roadmap_candidate_context.py:1085`.
**Disposition:** declined — the proposal prompt renders the stored payload bytes verbatim and no
consumer parses the payload JSON (the reviewer's own Method says so), so the suggested extension tests a
hypothetical consumer.

#### 6. Three passes over `member.source_spans` repeat one predicate — low (simplification)
`plan_tool/roadmap_candidate_context.py:1115`.
**Disposition:** declined — three one-line uses of `owning_row_ids is None`; a helper adds an indirection
for no current behavior difference, and the smallest change that closes the span-size finding is the one
already landed.

#### 7. Both backlog entries remain and the span-table entry describes a design that did not ship — low
`BUG_BACKLOG.md:1286`, `:1354`.
**Disposition:** tracked — removed at close-out, after the Integration check below and review convergence, in
the PR that ships the fixes. Until then the span-table entry's single-table description is stale.

#### 8. A machine-specific launcher alias is written into the shared directive — low
`integrations/shared/DIRECTIVES.md:1072`.
**Disposition:** declined for now — the owner asked for this edit directly (2026-10-05, "update the
directives to either use claude or claude-personal"); moving the alias name to the machine-local
`~/.claude/CLAUDE.md` is the owner's call and is raised in the pass summary.

### Behavior checks (run in the driving session, 2026-10-05)

Both review passes were static reads; these ran the changed code on the paths a user takes.

- **Decision-row restore, real routes.** A stored batch candidate on the Integration decisions root has five
  Decision rows as full members. Through `decide_structural_candidate(..., "edit")` and
  `request_replacement`, with the restore fix reverted, each refuses with `stored capsule row
  domain decision-config-vs-run-split cannot be restored: decisions row has unknown-field source` — the
  message Integration reported. With the fix both proceed. Approval does not restore rows, so the existing Integration
  end-to-end test stays green without the fix (checked by reverting it); the two new route tests
  (`..._can_be_edited_after_reload_from_disk`, `..._can_request_a_replacement_after_reload`) are the
  coverage that was missing.
- **Persisted form.** A capsule dumped with `exclude_none=True` keeps `"source": null` on a Decision row,
  so the restore matches what is written to disk.
- **Payload size on the Integration paragraph fixture** (5 references to 1 unique 1,288-byte span): 16,457
  bytes before the span table, 10,310 after, about 1,540 bytes per removed copy. Real Group 5 (99
  references, 31 unique spans) is an extrapolation from this, not a measurement; recompiling the
  reopened Integration batch is still the owner's check.
- **Not run:** a pre-2026-09-16 stored candidate (pass 2 finding 1), and a real batch of the reported
  shape.

### Review pass 3 — pending

## Roadmap candidate context ceiling — code review ledger

*Opened 2026-10-09.*

| Field | Value |
| --- | --- |
| Change | BACKLOG #469 (removed on merge, PR #58; its sizing text is in `docs/evidence/integration-context-budget-2026-10-09/sizing.md`): new candidate contexts admit up to 384 KiB (was 192 KiB), and a stored selector capsule is reproduced at the ceiling it recorded |
| Branch | `fix/roadmap-context-ceiling` |
| Review range | pass 1: `acdceacb..c0481d10` (fix `3e35be85`; backlog record `c0481d10`); pass 2: `c0481d10..35220609`; pass 3: `acdceacb..13ab814f` (whole change) |
| Checks run | Full suite `uv run pytest tests/ -q -n auto` on the final head: 13,670 passed, 67 skipped (one skip is the working-tree-dependent `tests/test_review.py` plan-title test) |
| Reviewer | headless `claude-personal -p`, report-only, `high` effort (`.tmp/roadmap-context-ceiling-code-review-N.stream.log`); reviewers could not run programs, so their test claims are by reading and each fix was checked by mutation in the driving session |
| Disposition | pass 1: 3 fixed, 1 measured, 1 deferred, 1 declined; pass 2: 3 fixed, 1 measured by Codex run, 1 declined, 1 comment; pass 3: 5 fixed in docs or tests; converged (passes 2 and 3 are two consecutive low-yield passes against logic head `c66f7361`) |

### Settled decisions (hand to each reviewer)

- The ceiling is 384 KiB (`docs/evidence/integration-context-budget-2026-10-09/sizing.md`; formerly BACKLOG #469 § "Sizing the new ceiling"): Claude reports a 1,000,000-token
  window, but Codex's catalog lists `gpt-6.1-sol` at 272,000 (95% effective), and 512 KiB was
  rejected against that. It stays a module constant: a per-project or operator setting would
  reverse `ROADMAP_FORMAT.md`'s "callers cannot override it" and is out of scope.
- The supported ceilings are exactly 64 KiB, 192 KiB and 384 KiB; 256 KiB and 512 KiB are refused. A forged `ceiling_bytes`
  must not validate a capsule, and a test pins the refused values.
- A ceiling is part of the payload and its digest. A stored **selector** capsule therefore
  reproduces only at its recorded ceiling: `roadmap_candidate._verify_bindings` calls
  `rebuild_candidate_context_at_recorded_ceiling`. `build_candidate_context` still takes no
  ceiling parameter (an existing test pins that).
- Stored **batch** capsules are bound by digest and member receipts and are never re-rendered
  (`roadmap_candidate_run.py` "Not recomputed for batch evidence"), so the batch route needs
  no change. The receipt-equality re-entry in `_run_batch_candidate_proposal` cannot match an
  existing active candidate by construction; a reviewer who disagrees must show the reproduction.
- A lineage stored under 64 KiB already failed re-entry on unmodified code after the 192 KiB
  bump; this change fixes that too, and a parametrized test covers both prior ceilings.
- Three tests pin values stored under 192 KiB (the selector-era seal and replacement bytes, the
  pre-batch candidate identity and admission bytes, and the clean structural seal id). They now
  issue under a literal 192 KiB ceiling on purpose; the selector-era review test then continues
  the lineage under the current ceiling.
- Deliberately not in this change: the budget warning's fixed 200K window (BACKLOG #470),
  relation-node compaction (#471), a token preflight, fallback-backend capacity checks, and any
  prose-only context route.
- `c0481d10` edits `BACKLOG.md` only; review it for accuracy of the claims it records, not as logic.

### Findings

Pass 1 (2026-10-09, `acdceacb..c0481d10`): six findings, all Low or Info. Sweep for the class "stored value compared with the current constant" found `_verify_bindings` to be the only offender; the current-constant consumers are only the new-issuance sites (selector `build_candidate_context`, batch compile and payload render).

1. Low, docs: `ROADMAP_FORMAT.md:1250-1253` overstated recorded-ceiling reproduction for batch capsules, which are verified by digest only and whose new hops compile at the current ceiling. Disposition: fixed `c66f7361` (rule scoped to selector capsules; `tests/test_roadmap_format.py` pins four phrases).
2. Low, capacity: prompt overhead is not flat (the receipt scales with payload) and the prompt travels as one argv element on every backend. Disposition: measured, not a code change. BACKLOG #469 fits overhead as about 76 KB plus 0.34 × payload and sizes 384 KiB at a prompt of about 605 KB; a 1,000,000-byte argument spawns on this macOS host (`ARG_MAX` 1,048,576, about 400 KB headroom; the rejected 512 KiB would be about 780 KB). Linux's per-argument limit is unverified and recorded as such in #469; moving the prompt to stdin is out of scope.
3. Low, diagnostics: `_verify_bindings` reported an unsupported recorded ceiling as `invalid-predecessor`. Disposition: fixed `c66f7361` (returns `invalid-capsule` with the rebuild's detail; `test_a_stored_capsule_with_an_unissued_ceiling_is_refused_as_an_invalid_capsule_not_a_predecessor_fault` fails without the mapping, checked by mutation).
4. Low, validation gap: for batch capsules `_capsule_is_intact` trusts the ceiling on allowlist membership and never cross-checks the payload's embedded `ceiling_bytes` or `payload_bytes <= ceiling_bytes`. Disposition: tracked: `BUG_BACKLOG.md` ROADMAP entry "A stored batch candidate capsule is accepted when its payload's embedded ceiling disagrees with its recorded ceiling" (`35220609`). Pre-existing gap that fixing would widen a validator outside this change; see open follow-ups.
5. Low, tests: two stored-era pin tests patched the 192 KiB constant for the whole test (so could not detect a recompute against the current constant), and the `_verify_bindings` expansion branch under a prior ceiling was uncovered. Disposition: fixed `c66f7361` (patches scoped to issuance; `test_an_expanded_capsule_stored_under_an_earlier_ceiling_still_verifies_after_a_raise` covers 64 KiB and 192 KiB and goes red when the initial capsule is rebuilt at the current ceiling; promotion/review re-verification already covered via `_selector_era_review`).
6. Info, naming: `_LEGACY_`/`_PRIOR_CANDIDATE_CONTEXT_MAX_BYTES` are named relative to "now". Disposition: declined; a naming nit with no behavior effect and more than the smallest change. Revisit when a fourth ceiling is added.

Pass 2 (2026-10-09, `c0481d10..35220609`): five findings, four Low and one Info.

1. Low, diagnostics: the `invalid-capsule` mapping never reaches an operator, because `_validate_candidate_evidence` (`roadmap_candidate_run.py:812-818`) and `_recompute_replacement_impact_atoms` (`roadmap_candidate_review.py:2976-2984`) wrap every refusal in fixed text. Disposition: declined as a behavior change. Pass-1 finding 3 was scoped to `_verify_bindings`' return value and no caller reads `reason` by value; both callers deliberately use one operator-facing message, the case needs a forged or corrupted stored record, and threading the detail is a logic edit that would reset the two-clean-pass window.
2. Low, docs: `ROADMAP_FORMAT.md:1250-1261` still said a batch capsule "stays re-enterable" and a replay "re-enters the stored lineage"; on the batch route a replay is a new hop (receipt equality cannot match). Disposition: fixed `43640a7e` (a capsule "stays readable", only a stored selector capsule is "also re-enterable", batch is verified by digest and receipts and never re-rendered; pinned in `tests/test_roadmap_format.py`). The #469 Outcome line was scoped the same way in `13ab814f`. The pre-existing "Replaying the same proposal re-enters the stored lineage" sentence describes the fixed-selector route and stays.
3. Low, docs: BACKLOG roll-up, #469 Quality and #470 Evidence still argued from a 1M-token model after #469 was re-based on Codex's 272K window, and #470 conflated the two lanes. Disposition: fixed `13ab814f` (1M rationale removed; #470 Evidence has a Claude lane, 1M window, 605 KB prints `high` today, and a Codex lane, 272K window, about 147K measured tokens, 54%, where the 3.5-bytes-per-token estimator reads `warn`; Verification asserts both).
4. Low, capacity: at the pessimistic 2.8 bytes per token the 384 KiB margin was about 0.4K tokens, extrapolated 1.86× past the measured range. Disposition: fixed by measurement in `13ab814f`; no code change. 2.8 was Claude's non-isolated ratio, not Codex's: on Codex 0.162.0 with `gpt-6.1-sol` the real 211,712-byte Integration payload costs 51,307 input tokens (70,471 with it, 19,164 bare), 4.13 bytes per token, so a 605 KB prompt is about 147K tokens (166K–189K with the 19K–42K harness), 64–73% of the 258K effective window. 512 KiB would fit at 81–90%; 384 KiB is chosen for headroom for output, a retry's correction and the review pair. One payload, one run; recorded as such in #469.
5. Info, tests: narrowing the patch in `test_approval_without_removed_ids_is_unchanged` is behavior-neutral (a batch test; batch capsules are never re-rendered). Disposition: comment added in `43640a7e` stating the narrowing is for symmetry and `_selector_era_review` guards the recorded-ceiling rule.

Pass 3 (2026-10-09, `acdceacb..13ab814f`, independent, pass-1/2 findings excluded): five findings, three Low and two Info.

1. Low, docs/contract: "callers cannot override it" had an undocumented counterexample, `rebuild_candidate_context_at_recorded_ceiling`, which the exact-name signature pin (`ceiling`) never inspects. Disposition: fixed (docs and pin only). `ROADMAP_FORMAT.md` names the one caller-supplied ceiling, accepted only if the module issued it and used to reproduce a stored selector capsule; `tests/test_roadmap_format.py` pins both phrases. The function keeps one caller, `_verify_bindings`; reading the ceiling from the capsule would be an unneeded signature change.
2. Low, tests: the motivating Integration case (a new batch hop at 384 KiB over a candidate stored under 192 KiB) had no end-to-end test. Disposition: fixed (test only). `test_a_new_batch_hop_over_a_candidate_stored_under_an_earlier_ceiling_uses_the_current_ceiling` stores under 192 KiB, runs a second hop under the real constant, and asserts the new ceiling, the source's bytes unchanged, and the source still reloading at 192 KiB. It passed on first run; recording the prior ceiling in the hop's receipt turns it red.
3. Low, docs: #469 Verification listed checks not performed (replay of `canonical-payload.json`, run-level over-ceiling refusal) while Status said "implemented". Disposition: fixed (backlog text). Verification now lists what was done; it states `canonical-payload.json` is a rendered output and cannot be replayed, and that a run-level over-ceiling refusal test is not added because that path is unchanged.
4. Info, docs: #470 "In scope" omitted the `review.py` caller with `context_window=None`. Disposition: fixed (backlog text). #470 lists nine sites found by grepping the literal across `plan_tool/`: `shell.py` 1, `review.py` 1, `create.py` 1, `detail.py` 3, `launcher.py` 3.
5. Info, measurement: the 43,174 and 41,662 harness token figures in #469 did not reconcile. Disposition: fixed (backlog text). 43,174 was taken on the 106,151-byte `CLAUDE.md`, 41,662 on the evidence-split branch's 98,637-byte file; #469 says so and the 1.5K difference is that 7.5 KB.

Areas the reviewers traced and found holding: stored selector capsule admission, evidence and replacement verification use the recorded `capsule.ceiling_bytes`, and `_verify_bindings` is the only rebuild site; `type(value) is int` refuses `True`, numeric strings and `None`; no stored batch capsule, receipt or seal id is recomputed against the current constant; BACKLOG arithmetic recomputes (about 605 KB at 384 KiB, 4.13 bytes per token, warning thresholds 420 KB and 595 KB from `WARN_HEADROOM_RATIO` 0.40 and `HIGH_HEADROOM_RATIO` 0.15, `ae35bcb8` confirmed as 2026-09-03); the changelog fragment matches the behavior; commit messages carry no attribution lines.

### Convergence status

Converged, 2026-10-09. The logic head is `c66f7361` and has not changed since. Pass 2 (four Low, one Info) and pass 3 (three Low, two Info) are two independent consecutive low-yield passes against it, with no new material correctness or completeness issue in either; every finding of passes 1 to 3 has a disposition. Everything after `c66f7361` is documentation, backlog text, tests and test comments, which does not reset the logic window. Pass 3's one substantive probe, the new batch hop over a 192 KiB candidate, passed when written. The loop stops here; no pass 4 is launched.

Open follow-ups, none blocking: the deferred batch-ceiling consistency gap (`BUG_BACKLOG.md`, ROADMAP section; pass-1 finding 4), BACKLOG #470 (budget warning window) and #471 (relation compaction), and the Linux per-argument limit, unverified.
