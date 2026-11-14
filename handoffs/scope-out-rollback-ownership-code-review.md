# Scope-out rollback ownership

| Item | Record |
| --- | --- |
| Base | `c330cbb2e`, merged PR #143 |
| Branch | `fix/scope-out-rollback-ownership` |
| Scope | BUG_BACKLOG "Scope-out rollback overwrites the concurrent edit rejected by provenance" |
| Route | Bounded publication/recovery repair; no transaction framework |
| Implementation | `d7807797c` (validated publisher seams), `2b77724b2504af9c6aa9c8491073f9f71e3183ca` (scope-out guarded recovery) |
| Reviews | Four Claude Code `/code-review` passes (built-in skill, high effort, Sonnet 5.5, with supervising verification) |
| Closure | **Converged (low-yield)**: reviews 3 and 4 are two consecutive independent clean passes after source snapshot `bcf3b8bb7` |
| Checks | 678 affected tests; full suite 15,095 passed, 67 skipped; `git diff --check` clean; all changes committed, no push or PR |

## Settled decisions

- Invariant: a failed narrowing restores only its own published plan/concept bytes, preserves other edits, and reports incomplete recovery. Publication failure leaves no unidentified partial canonical plan write.
- Mechanism: an optional publisher seam on `parser.write_plan` and `concept_tree.save_concepts` hands the exact validated payload to `scope_out.apply_narrow`, whose local publisher rechecks the live frontmatter/body or sidecar preimage, records a receipt, and writes via the existing durable `fileio.atomic_write_bytes`. Rollback compares receipts before each restore, attempts all independent undos, and collects errors. Plan provenance refreshes only for verified restored bytes. Sidecar snapshots are raw bytes; other callers keep default behavior.
- The detail journal's undo also refuses an occupied destination (a reproduced conflict otherwise overwrites a new detail file) and continues all inverse operations while returning failures. Forward archive/scope selection is unchanged.
- Boundary: guarded recovery, not a lock. A writer racing inside the comparison/replace interval is not serialized; no cross-process transaction guarantee is claimed (stated in ARCHITECTURE). Excluded: unrelated concept-sync publishers, archive and scope selection, seed generation, schema/alias semantics, cross-process locking.
- A body edit observed before serialization is kept by recovery rather than reverted.

## Verification

- Before the fix, seven plan/sidecar concurrency regressions and a detail-undo collision regression fail; no existing test pinned the overwritten edit as intended.
- Affected suite 671 passed (scope-out, parser, concept tree, atomic I/O), covering custom publisher gates, LF/CRLF/CR restoration, before/after publication failures, concurrent change/deletion, provenance and detail recovery. One test premise was wrong (a lone step with id 2 is valid) and now uses duplicate ids, rejected before publication. Full suite then 15,088 passed, 67 skipped in 65.08s.

## Findings

| Review (range head) | Id | Disposition |
| --- | --- | --- |
| 1 (`2b77724b2504af9c6aa9c8491073f9f71e3183ca`) | F-1: NarrowError prose, orchestrator comment and RUNBOOK promise unconditional restoration | fixed: wording corrected across those sites, docstrings and ARCHITECTURE; archived plans stay historical |
| 1 | F-2: plain atomic writer drops the saver's fsync-before-replace guarantee | fixed: scope-out publishes and restores through the durable byte writer; fsync-observation regression covers plan, concept and directory sync and fails (1 failed) with the non-durable writer |
| 1 | F-3: six restricted-mode/symlink cases fail on apply/rollback | fixed: publisher records the resolved destination, keeps the symlink and restores mode after replacement; receipts bind recovery to that destination, provenance refreshes only if the plan path still resolves there; all six pass |
| 1 | O-1: reporting gap on incomplete detail undo | fixed: message states whether detail moves are restored or undo is incomplete and directs inspection; undo ordering unchanged (pinned by existing tests); concurrent-plan test pins it. 678 affected pass; production snapshot `be87521a1`, full suite 15,095 passed in 72.04s |
| 1 | Check/replace interval, target deletion | declined: outside the no-lock contract; deletion already pinned |
| 2 (`be87521a1aebf481566fce5f92f81c02e5f95948`) | L-1: optional-publisher paragraph precedes its antecedent | fixed: moved after the provenance guard's body-only-edit explanation |
| 2 | L-2: detail-undo error prints tuple order for both tags though rename undo runs reverse | fixed: formats source/destination; new assertion fails before and pins the failed move direction |
| 2 | L-3: durable replacement briefly exposes the new 0600 mode before the original mode is reapplied | declined: accepted residual (final modes and symlink targets pinned; ARCHITECTURE records the window and the lack of inode/hardlink/extended-metadata preservation); atomic replacement is needed to avoid partial writes |
| 2 | Detail undo ordering, body comparison, plan discriminator, exact-preimage restoration, dated lessons/archived plans, pre-fingerprint body edit | refuted/retained: pinned behavior, real late-edit protection, or inside the no-lock boundary |
| 3 (`9821b481b9bbec9ad78aeee33d097de80ef49fcc`) | No material bug; six candidates (mode and check-replace windows, KeyboardInterrupt unchanged at base, provenance-refresh objections, local closures/discriminator style, sibling split rollback already guards occupied destinations) | refuted/declined: accepted residuals, guards/tests, or preferences; "mirroring scope_out._rollback" wording means best-effort continuation, which both implement. Reviewer ran 678 tests and the full suite (15,095 passed, 70.18s; 70.53s after the arrow correction); its mutation attempt was blocked, so no independent mutation claim |
| 4 (`e44316a747e65c297388230703232bef589e4417`) | Clean, low-yield; five candidates (O-1, exists/rename races within no-lock interval, L-3 metadata limits, sidecar discriminator style, "detail moves restored" wording for an empty undo journal) | declined: pinned or advisory wording only. Reviewer ran 678 tests and full suite 15,095 passed in 69.77s |

## Closure

**Converged (low-yield):** reviews 3 and 4 are two consecutive independent clean final passes after `bcf3b8bb7`; only documentation/evidence follows. Their verdicts retain the no-lock/metadata residuals and the operator-inspection requirement rather than implying a filesystem transaction. The original backlog item is removed after completed verification and review. The separate H1-deletion and create-helper investigations are untouched. No tracked or pending items remain.
