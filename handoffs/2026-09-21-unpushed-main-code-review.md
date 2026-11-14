# Unpushed `main` code review

## Summary

| Field | Value |
| --- | --- |
| Review range | `origin/main..main`, then each round's own fix commits |
| Range base (origin/main) | `f0f4c3ab` |
| Round 1 head (initial review target) | `ded951aa` |
| Review purpose | Preserve the finding explanations, dispositions and settled decisions below |
| Checks run | `/code-review` (report-only, no `--fix`), effort `high` every round; final full unit/component suite: 12365 passed, 158 skipped |
| Reviewer/session | `code-review-loop` skill |
| Current disposition | **Converged** after 4 rounds — see Convergence status |

The ledger covers the 69 commits on `main` not yet on `origin/main`, edited in
place across rounds (convention: `handoffs/README.md` § "Review ledgers").
Reports carried no severity or `CONFIRMED`/`PLAUSIBLE` tag, so none is recorded
below. Finding ids are `R<round>-<n>`; round 2 is the full report (its partial
report is R2P). All 15 round-1 findings cluster in the roadmap
terminal-disposition/lifecycle machinery (`roadmap.py`, `roadmap_cmd.py`,
`roadmap_revision_run.py`, `roadmap_versions.py`, `roadmap_candidate.py`) and
`ROADMAP_FORMAT.md`.

## Settled decisions (hand to the next reviewer)

*Compression note (added 2026-11-13; the ledger was compressed 2026-09-29): this ledger had no original settled-decisions list; the list below was assembled from its own declined and refuted findings.*

- Materialize exception tracking uses the `materialize_disposition_emitted`
  tag on the exception object (`d795b3f6`), accessed via
  `_materialize_disposition_emitted` / `_mark_materialize_disposition_emitted`
  (`8004bd95`). A superseding exception is a distinct failure and gets its own
  "unexpected-error" disposition.
- `run_roadmap`'s writer-teardown `OSError` (R2-1 / R4-1) is pre-existing and
  needs a disposition-contract decision; it is filed in `BUG_BACKLOG.md`
  (`ab04f4e6`), not patched in-loop.
- `RoadmapEnvironmentalError` (unreadable-but-existing template) stays rc=1
  regardless of timing; pinned by
  `test_escaping_environmental_prompt_read_failure_returns_incomplete`.
- The pre-existing "stale writer token" comment in `roadmap_revision_run.py`
  keeps its original wording: CLAUDE.md says match the terse style when
  touching a pre-rule module rather than extending it.
- `run_local_feedback_revision` does not consult `roadmap_stage_started`.
- Comment-length terseness is no longer an audit axis (self-seeded-finding
  rule).

## Fix guidance (applies to every disposition in this ledger)

A change that closes a finding as `fixed` must:

- Be true and proportional to the intent of the code it touches — no bigger,
  smaller, or more general than the defect calls for.
- Apply the smallest proof that completes the intent, not the eventual
  capability the finding gestures toward.
- Stay at the altitude the finding names (do not fold detail-level mechanics
  into a plan/bare-level concern or the reverse).
- Run an identifier + vocabulary sweep for sibling sites, then check the remedy
  against the goal of the bug rather than replaying one patch verbatim at every
  match.

## Round 1 — `origin/main..main` (`f0f4c3ab..ded951aa`, 69 commits)

- **R1-1 — preflight prompt errors marked "stage started"** (`roadmap.py`): a missing prompt template returned rc=1 (retryable) instead of rc=2. **Disposition:** fixed 02463e41 — `_preflight_prompt_error` marks `False` at origin, guard fills only when absent; tests `test_render_stage_prompt_missing_template_marks_stage_not_started`, `test_render_stage_feedback_prompt_missing_template_marks_stage_not_started`, two `TestStageRunGuard` cases.
- **R1-2 — stale writer token escapes revision publish** (`roadmap_revision_run.py`): `RoadmapWriterGuardError` uncaught instead of `publication-failed`. **Disposition:** fixed a82cb7b4 — added to the `except OSError` clause; `test_publication_failed_when_publish_raises_stale_writer_token`.
- **R1-3 — materialize preflight lifecycle can raise `OSError`** (`roadmap_cmd.py`): nested `except RoadmapError` missed `RunLogWriter.start()` errors. **Disposition:** fixed a4359236 — `(RoadmapError, OSError)`; `test_materialize_preflight_lifecycle_survives_a_broken_run_log`.
- **R1-4 — writer-guard teardown failure after success gets no disposition** (`roadmap_cmd.py`). **Disposition:** fixed a4359236 — flags `owned_call_entered`/`owned_call_returned` (superseded by the R2-2 tag); `test_materialize_emits_unexpected_error_when_writer_teardown_fails_after_success`.
- **R1-5 — second contradictory lifecycle from outer `RoadmapError` handler** (`roadmap_cmd.py`, latent). **Disposition:** fixed a4359236 — re-raises while inside the owned call; `test_materialize_does_not_double_report_a_roadmap_error_from_the_owned_call`.
- **R1-6 — trailing `except BaseException` omits the disposition emit** (`roadmap_cmd.py`). **Disposition:** fixed a4359236 — merged into the `except Exception:` clause; `test_materialize_owned_emits_disposition_for_a_baseexception_escape`.
- **R1-7 — `_ordered_stage_collections` hand-copies the collection table** (`roadmap_candidate.py`): drift from `stage_row_collections()`. **Disposition:** fixed 08000ee5 — delegates; `test_ordered_stage_collections_matches_the_shared_dispatch_table`, `test_ordered_stage_collections_refuses_an_unsupported_artifact_type`.
- **R1-8 — unreachable `record.version_id` check** (`roadmap_versions.py`). **Disposition:** fixed 4c4551f4 — deleted; sibling call sites swept, none have it.
- **R1-9 — duplicated category-to-disposition mapping** (`roadmap_cmd.py`): `_cmd_roadmap_revise_feedback` duplicated `_terminal_disposition()`. **Disposition:** fixed 7cd1c19b — reuses it and `_result_return_code`; parametrized over all 4 categories plus an interrupted-skips-emission test.
- **R1-10 — six copies of the preflight-refusal pairing** (`roadmap_cmd.py`). **Disposition:** fixed 0bc732a9 — `_refuse_materialize_preflight`.
- **R1-11 — shared digest helpers inlined at five sites** (`roadmap_versions.py`, `roadmap_candidate_context.py`). **Disposition:** fixed 45d54826 — `VERSION_ARTIFACT_KEYS` and `sha256_digests()` restored verbatim from `origin/main`.
- **R1-12 — duplicated dict-by-id diff loops** (`roadmap_candidate.py`). **Disposition:** fixed 5b9e549a — `_diff_by_id`.
- **R1-13 — stale "later roadmap steps" sentence** (`ROADMAP_FORMAT.md`), violating forward-looking docs. **Disposition:** fixed 3e6f3c55 — deleted.
- **R1-14 — opposite `getattr` defaults for `roadmap_stage_started`** (`roadmap_cmd.py`). **Disposition:** fixed b828499c — `_roadmap_stage_started(exc, default=...)`; pinned by `test_escaping_disk_failure_returns_incomplete_not_usage`, `test_escaping_preflight_error_emits_refusal_terminal_status`.
- **R1-15 — no-op `try/except: raise`** (`roadmap.py`). **Disposition:** fixed 4c4551f4 — deleted.

## Round 2 — partial report (conventions angle only; `ded951aa..HEAD`, fixes `d1a10a70`..`b828499c`)

All one class: comments added while fixing round 1 ran past "a line or two". This partial result was wrongly taken as the whole round (see Convergence status).

- **R2P-1..R2P-5 — over-long comments/docstrings** in `_roadmap_stage_started`, the `except OSError` comment (`roadmap_revision_run.py`, pre-rule module: revert to original wording), `_stage_run_guard`, the `owned_call_*` comment, `_ordered_stage_collections`. **Disposition:** fixed 6cade212 — each trimmed to 1-2 lines.
- **R2P-sweep — 7 uncited instances** across round-1 fix commits (revise-feedback and materialize comments, `except BaseException:` comment, docstrings of `_refuse_materialize_preflight`, `_preflight_prompt_error`, `_diff_by_id`). **Disposition:** fixed 6cade212.

## Round 2 — full report (`ded951aa..HEAD`)

Refuted leads: R1-8 and R1-15 deletions are genuinely redundant/no-op; R1-9's refactor is exactly equivalent for all 4 `LocalRevisionResult.category` values.

- **R2-1 — `run_roadmap` teardown `OSError` replaces a successful result** (`roadmap.py`): `return _run_roadmap(...)` inside `with _roadmap_writer_owner(...)` turns a finished run into `error`/rc=1. **Disposition:** tracked `BUG_BACKLOG.md` (`ab04f4e6`; no numeric id cited) — pre-dates the range; `ROADMAP_FORMAT.md`'s matrix has no row for "completed, then teardown failed", so the fix is a contract decision.
- **R2-2 — flags cannot tell a superseding exception apart** (`roadmap_cmd.py`): `_roadmap_command_lifecycle`'s unguarded `run_end(...)` can replace the pending exception. **Disposition:** fixed d795b3f6 — `materialize_disposition_emitted` tag on the exception replaces the flags.
- **R2-3 — post-return `RoadmapError` treated as preflight (rc=2)** (`roadmap_cmd.py`, latent). **Disposition:** fixed d795b3f6 — `test_materialize_treats_a_fresh_roadmap_error_after_entry_as_unexpected`.
- **R2-4 — `_rebind_failure_error` forwards only a truthy `roadmap_stage_started`** (`roadmap.py`). **Disposition:** fixed de16b43d — forwards whenever present; `TestRebindFailureError` (3 tests).
- **R2-5 — rc literals in `_result_return_code` duplicated** (`roadmap_revision_run.py`; shared import would be circular). **Disposition:** fixed — test-only, `test_result_return_code_matches_roadmap_cmd_rc_constants` (moved in R4-14).
- **R2-6 — hand-listed `isinstance` tuple** (`roadmap_candidate.py`). **Disposition:** fixed 0e32dcdf — `isinstance(artifact, RoadmapArtifact)`.
- **R2-7 — hand-looped digests at 4 sites** (`roadmap_candidate_run.py`, `roadmap_candidate_review.py`): the R1-11 sweep stopped early. **Disposition:** fixed c8e12584 — repointed to `sha256_digests`; no other site remains.
- **R2-8 — timing-inferred "already dispositioned" state** (`roadmap_cmd.py`): root cause of R2-2, R2-3, R2-11. **Disposition:** fixed d795b3f6 — closed by the tag redesign.
- **R2-9 — `_roadmap_stage_started` docstring 11+ lines.** **Disposition:** refuted — stale snapshot; 6cade212 (R2P-1) already trimmed it. Source label: `no_change_needed`.
- **R2-10 — `render_local_revision_prompt` missing-template raise not marked** (`roadmap_revision_run.py`, latent). **Disposition:** declined — its outcome model never reads `roadmap_stage_started`, so wiring it builds for a capability nothing consumes; revisit only if that flow adopts the convention.
- **R2-11 — outer net swallows a dispositioned error** (`roadmap_cmd.py`, latent). **Disposition:** fixed d795b3f6 — the net re-raises a tagged exception; `test_materialize_owned_does_not_let_its_outer_net_swallow_a_dispositioned_error`.

Suite after round 2 fixes: 12365 passed, 158 skipped.

## Round 3 — `b828499c..HEAD` (`6cade212`, ledger update `bc7305ad`)

No executable line changed. It excluded the round-2 full-report fixes, so it is not convergence evidence.

- **R3-1 — ledger sweep count typo** ("4 more instances", 7 listed). **Disposition:** fixed — corrected to 7 (recorded in R2P-sweep).

## Round 4 — `b828499c..HEAD` (`d795b3f6`, `0e32dcdf`, `c8e12584`, `de16b43d`, `ab04f4e6`, `7aee4e10`)

14 findings; 10 describe the loop's own prior edits (self-seeded-finding shape).

- **R4-1 — teardown defect fixed only at materialize, not `run_roadmap`** (`roadmap.py`). **Disposition:** declined — reaffirms the `ab04f4e6` entry: the lost `RoadmapResult` cannot be recovered once `__exit__` discards it, so the fix is a disposition-contract decision (new matrix row or explicit rc=1 acceptance); no new information.
- **R4-2 — `run_end()` can replace a tagged exception with an untagged one** (`roadmap.py`, untested). **Disposition:** declined — intended: a superseding exception is a distinct failure with its own disposition; root cause is pre-existing shared infrastructure, same class as R4-1.
- **R4-3 — tag read/set via hand-typed `getattr`/`setattr`** (`roadmap_cmd.py`). **Disposition:** fixed 8004bd95 — `_materialize_disposition_emitted` / `_mark_materialize_disposition_emitted` at all four sites.
- **R4-4 — `_roadmap_stage_started` docstring lost its why.** **Disposition:** fixed 8004bd95.
- **R4-5 — new 5-line `owned_call_entered` comment.** **Disposition:** fixed 8004bd95 — 2 lines.
- **R4-6 — `_preflight_prompt_error` lost the `_stage_run_guard` fill-if-absent reason** (`roadmap.py`). **Disposition:** fixed a9dd7d90.
- **R4-7 — reverted "stale writer token" comment lacks a pointer to `publish_revision_candidate`** (`roadmap_revision_run.py`). **Disposition:** declined — contradicts R2P-2 (match the terse style in pre-rule modules rather than extend); the gap pre-dates the range.
- **R4-8 — bindings hashed twice from one `content`** (`roadmap_candidate_review.py`, `roadmap_candidate_run.py`): pre-existing, no correctness impact. **Disposition:** pending — not filed; a numbered `BACKLOG.md` slot costs more than the item is worth. Do a bind-once-reuse pass when either function is next touched. (Source: "noted, not filed"; set to `pending` by the owner 2026-09-29.)
- **R4-9 — two outer except blocks reimplement "emit unless dispositioned"** (`roadmap_cmd.py`). **Disposition:** fixed 8004bd95 (via R4-3) — the remaining 3-vs-2 outcome difference is genuine.
- **R4-10 — `BaseException` handler comment lost why a fixed "unexpected-error" string is emitted** (persisted record must not expose exception text). **Disposition:** fixed 8004bd95.
- **R4-11 — revise-feedback comment lost the shared-mapping reason.** **Disposition:** fixed 8004bd95.
- **R4-12 — `_diff_by_id` docstring lost the two-part ordering contract** (`roadmap_candidate.py`). **Disposition:** fixed b87d8e7c.
- **R4-13 — dead imports `ComponentsArtifact`, `ConstraintsArtifact`, `DomainArtifact`** (`roadmap_candidate.py`; ruff F401 is disabled for an unrelated re-export pattern). **Disposition:** fixed b87d8e7c.
- **R4-14 — rc-drift test in the wrong mirror file** (`tests/cli/test_roadmap_cmd.py`). **Disposition:** fixed 8b782515 — moved to `test_roadmap_revision_run.py`.

Suite after round 4: 12365 passed, 158 skipped.

## Out-of-range / recall-mode findings

_(none)_

## Convergence status

**Converged after 4 rounds.** An earlier "Converged" call, made after round 3
on the round-2 partial report alone, was premature and is retracted: the full
round-2 report arrived afterward and held real logic fixes (the materialize
tag redesign, the rebind fact-forwarding bug, a missed duplication sweep, the
rc-drift test), one backlog filing (R2-1) and one declined item (R2-10).

Final triage: round 4's 14 findings resolve as 5 fixed genuine hygiene/accessor
gaps, 6 fixed under-trimmed or over-trimmed comments, 2 declined with reasoning
(R4-1 reaffirms a documented backlog tradeoff; R4-7 is settled by a rule a
prior round correctly applied), and 1 pending (R4-8; R4-2, R4-9 fall
in the counts above per the source). Ten of the 14 describe the loop's own
prior edits, the self-seeded-finding shape, whose stated response is to finish
applying and stop auditing that dimension. No round past round 2 found a new
runtime correctness defect; every later round was consistency polish on the
loop's own edits, which is the convergence signal here, not a zero-finding
round. The loop stops; no round 5.

Open follow-ups: `BUG_BACKLOG.md` entry for the `run_roadmap` teardown
disposition contract (R2-1 / R4-1, `ab04f4e6`), pending a contract decision;
R4-8 bind-once-reuse pass, unfiled.

Lesson: treat a background `/code-review` hand-back as provisional until the
launching call itself reports completion; a partial finder-angle result can
arrive first and read as complete.
