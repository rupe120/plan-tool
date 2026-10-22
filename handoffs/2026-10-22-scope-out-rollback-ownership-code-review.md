# Scope-out rollback ownership

| Item | Record |
| --- | --- |
| Base | `c330cbb2e`, merged PR #143 |
| Branch | `fix/scope-out-rollback-ownership` |
| Scope | BUG_BACKLOG “Scope-out rollback overwrites the concurrent edit rejected by provenance” |
| Route | Bounded publication/recovery repair; no transaction framework |
| Current state | Complete: 15,095 tests pass; two consecutive independent clean final Claude Code reviews |

## Property and pre-edit sites

Invariant: a failed narrowing restores only its own published plan/concept bytes, preserves other edits, and reports any incomplete recovery. Publication failure cannot leave an unidentified partial canonical plan write.
Identifier search: apply_narrow/_rollback/original_sidecar_text/write_plan/save_concepts identifies scope_out's plan write, sidecar write, unconditional snapshot restores and detail journal undo. _ConceptNarrowUpdate is ephemeral and has one producer/consumer pair; both require a raw sidecar snapshot.
Vocabulary search: rollback/restore/compare-and-swap/publication in scope_out, parser and concept_tree identifies parser's provenance guard, concept_tree's validated atomic saver, and swallowed undo errors. Keep their existing guards/validation; add a narrow optional publisher seam so scope_out receives exact bytes before publication, with default behavior unchanged for other callers.
Sites: parser.write_plan and concept_tree.save_concepts hand exact payload to the supplied publisher; apply_narrow uses one local publisher to recheck preimages, record receipts and atomically publish with existing fileio.atomic_write_bytes. Rollback compares receipts before restoring and collects errors. Plan provenance refreshes only for verified restored bytes. The detail journal continues all inverse operations while returning failures.
Excluded: unrelated concept-sync publishers, archive selection, scope selection, seed generation, schema/alias semantics and cross-process locking. No global transaction framework; this is local guarded recovery, not a filesystem CAS guarantee between comparison and replace.

The detail journal's occupied-destination check extends the same invariant to
undo: a reproduced conflict otherwise overwrites a new detail file. It does not
change forward archive/scope selection. The current publisher preimage can
include a body edit observed before serialization, so recovery keeps that edit
rather than reverting to an earlier snapshot. Sidecar snapshots use raw bytes.

## Verification

Pre-fix run: seven new plan/sidecar concurrency regressions fail. A separate
detail-undo collision regression fails before its guard. Neither has an existing
test pinning the overwritten edit as intended. The corrected affected suite
passes 671 tests (scope-out, parser, concept tree, atomic I/O), including custom
publisher validation gates, LF/CRLF/CR restoration, before/after publication
failures, concurrent changes/deletion, provenance and detail recovery.

Exact writer payloads come from existing validated serializers via optional
publisher hooks. Other callers retain their existing write paths. Scope-out's
local publisher rechecks the live frontmatter/body or sidecar preimage before
recording a receipt and calling the existing atomic byte writer. Recovery
checks the receipt before each restore and attempts all independent undos.

This is guarded recovery, not a lock across external writers: a writer racing
inside a comparison/replacement interval is not serialized. The architecture
reference states that boundary; no cross-process transaction guarantee is claimed.

Initial full verification identifies one incorrect new test premise: a lone step
with id 2 is valid. The regression uses duplicate IDs instead, which are rejected
before publication. After that test-only correction, the affected suite is
**671 passed**, and the full suite is **15,088 passed, 67 skipped** in 65.08s.
`git diff --check` passes. Implementation commits: `d7807797c` (validated
publisher seams) and `2b77724b2` (scope-out guarded recovery).

## Claude Code review 1 and verified dispositions

Range `c330cbb2e..2b77724b2504af9c6aa9c8491073f9f71e3183ca`;
actual built-in `code-review` Skill at high effort plus supervising verification.
Session `c960b6c8-39ab-45dc-a23e-dcee449b2efa`.
The reviewer reruns all 671 affected tests and confirms the recovery invariant.
The first review is not counted as a final clean pass: it identifies three
introduced low-severity items, all corrected rather than accepted as tradeoffs.

- F-1 confirmed: NarrowError prose, the orchestrator comment and RUNBOOK still
  promise unconditional restoration. The vocabulary sweep covers those sites,
  the module/apply docstrings and ARCHITECTURE. Archived plans remain historical.
- F-2 confirmed against the existing saver: concept publication syncs its file
  before replacement; the new plain atomic writer drops that guarantee. Scope-out
  uses the existing durable byte writer for publication and restoration. An
  fsync-observation regression covers plan, concept and directory sync; replacing
  that writer with the non-durable variant makes the test fail (1 failed).
- F-3 confirmed through actual apply/rollback: six restricted-mode/symlink cases
  fail before correction. The publisher records the resolved destination, keeps
  the symlink intact and restores the mode after durable replacement. Receipts
  bind recovery to that resolved destination; provenance refreshes only if the
  logical plan path still resolves there. All six cases pass after correction.
- O-1 is a reporting gap, not a reason to change undo ordering: existing tests pin
  attempting independent detail undos even when a later plan edit is preserved.
  Incomplete recovery now states whether detail moves are restored or their undo
  is incomplete, and directs inspection before retrying. The concurrent-plan test
  pins this operator-facing distinction. No ownership/scope decision is changed.
- The check/replace interval remains explicitly outside the no-lock contract;
  target deletion is already pinned. Neither is a missing recovery branch.

Affected suite after the review corrections: **678 passed** in 1.20s. Final
logic requires a fresh pair of independent review passes.

Production snapshot after review corrections: `be87521a1`. Full suite:
**15,095 passed, 67 skipped** in 72.04s. No logic change follows this result
unless a subsequent confirmed review finding requires it.

## Claude Code review 2 and dispositions

Range `c330cbb2e..be87521a1aebf481566fce5f92f81c02e5f95948`;
actual built-in `code-review` Skill at high effort with independent verification.
Session `e6bb3387-9464-4ece-a4f0-d1809561af95`.
All 678 affected tests pass, diff whitespace check is clean, and the reviewer
finds no correctness defect against the recovery invariant. Three low items:

- L-1 confirmed and corrected: move the optional-publisher paragraph after the
  provenance guard's body-only-edit explanation so its antecedent is clear.
- L-2 confirmed and corrected: the detail-undo error prints tuple order for
  both tags even though rename undo runs the reverse direction. Format the
  already-computed source/destination. A new assertion fails before correction
  and pins the failed move direction alongside its occupied destination.
- L-3 accepted residual: durable replacement briefly exposes the new restrictive
  0600 mode before reapplying the original mode. Retain that limited window
  rather than change the shared writer or add another implementation; final
  modes and symlink targets are pinned. ARCHITECTURE records the window and
  the lack of inode/hardlink/extended-metadata preservation. Atomic replacement
  is necessary to avoid unidentified partial canonical writes. This is a
  concrete tradeoff, not an unfinished promise to add locking or metadata APIs.

Other candidates are refuted or retained decisions: detail undo ordering/reporting
is pinned; body comparison prevents a real late-edit overwrite; actual caller
paths make the plan discriminator valid; exact preimage bytes need no restoration.
Generated dated lessons and archived plans remain historical provenance, outside
live contract ownership. A possible body edit before fingerprinting is unchanged
and lies within the documented no-lock boundary. No unrelated finding is applied.

## Claude Code review 3

Range `c330cbb2e..9821b481b9bbec9ad78aeee33d097de80ef49fcc`;
actual built-in `code-review` Skill at high effort plus independent verification.
Session `a2e83a65-fafc-4240-a02c-ebc55b856eeb`.
Clean for the invariant, with no material reproducible bug or missing route.
The reviewer independently runs **678 affected tests** in 1.62s and the full
suite: **15,095 passed, 67 skipped** in 70.18s; diff whitespace is clean.
The session's separate final full run is also **15,095 passed, 67 skipped**
in 70.53s after the arrow correction.

Six candidates are checked: restrictive mode/check-replace windows remain
explicit accepted residuals; KeyboardInterrupt handling is unchanged at base
and proposes a new abort contract; provenance-refresh objections are refuted
by the guards/tests; local closures/discriminator changes are preferences;
the sibling split rollback already guards occupied destinations. Its
“mirroring scope_out._rollback” wording specifically describes best-effort
continuation, which both still implement; no unrelated split code is changed.
No out-of-scope hardening or consolidation is added without a concrete defect.

The reviewer cannot run its attempted mutation through its permission layer;
no independent mutation claim is made. Session-owned pre-fix/mutation results
are recorded above. Its actual completed test runs independently confirm the
final committed snapshot.

## Claude Code review 4 and convergence

Range `c330cbb2e..e44316a747e65c297388230703232bef589e4417`;
actual built-in `code-review` Skill at high effort plus independent verification.
Session `b720f143-c2f7-4e52-92ae-09aa9f4a02f6`.
Clean, low-yield: no material reproducible bug or missing invariant route.
The reviewer independently runs **678 affected tests** and the full suite:
**15,095 passed, 67 skipped** in 69.77s, exit 0; diff whitespace is clean.

Five candidates are checked: O-1 remains pinned/reportable behavior;
exists/rename races are within the documented no-lock interval; replacement
metadata limitations are accepted L-3; the sidecar discriminator is a style
preference; “detail moves restored” for an empty undo journal is advisory
wording only. No source change is recommended. No new material issue remains.

Reviews 3 and 4 give two consecutive independent clean final passes after
source snapshot `bcf3b8bb7`; only documentation/evidence follows it. Their
“clean, low-yield” verdicts retain the explicit no-lock/metadata residuals and
operator inspection requirement rather than imply a filesystem transaction.
The original backlog item is removed after completed verification and review.
The separate H1-deletion and create-helper investigations remain untouched.

Final tree verification: diff whitespace check passes; all changes are committed.
No push or PR is part of this task.
