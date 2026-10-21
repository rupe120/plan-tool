# Roadmap model-failure-receipts code review

## Summary

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
`2026-09-21-unpushed-main-code-review.md`, whose range (the
`roadmap-concept-comparison` work) converged and is on `origin/main`.

## Settled decisions (hand to the next reviewer)

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

## Fix guidance (applies to every disposition in this ledger)

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

## Round 1 (2026-09-22, `271e82e4..3f0d5c6e`)

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

## Round 2 (2026-09-22, `3f0d5c6e..HEAD`: `ab6908ac`, `19dd3cdb`, docs commit `8bd2b8f9`)

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

## Round 3 (2026-09-22, range `19dd3cdb..HEAD`; chain-correct base was `8bd2b8f9`)

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

## Round 4 (2026-09-22, range `8c0ffead..HEAD`; chain-correct base was `2393f51e`)

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

## Round 5 (2026-09-22, range `14e6dc5c..HEAD`: `93129a35`, `3ea3503c`)

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

## Convergence status

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

## Out-of-range / recall-mode findings

_(none)_
