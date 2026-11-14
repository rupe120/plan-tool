# Committed test authorship gate repair

| Item | Record |
| --- | --- |
| Base | `db0b81151`, merged alias PR #140 |
| Branch | `fix/committed-test-authorship` |
| Route | Bounded direct fix; existing BUG_BACKLOG condition permits direct repair when no evidence redesign is needed |
| Reviews | Six Claude Code `/code-review` passes (built-in skill, high effort, Sonnet 5.5, report-only), reports `.tmp/committed-test-authorship.review-N.md` |
| Closure | **Converged for logic** (two consecutive independent clean passes against the latest production snapshot `b8064b023`) |
| Checks | Last complete suite 15,020 passed, 67 skipped in 81.86s; `git diff --check` clean |

## Settled decisions

- A test added or modified in commits between the pre-call HEAD and post-call HEAD satisfies the file-authorship gate; it need not stay dirty when the backend returns.
- Pre-call dirty-path subtraction stays for both evidence sources (pinned contract, not a defect). Enforcement eligibility, mode exclusions, test/gate execution, failure persistence and advancement are unchanged.
- Evidence boundary: capture a readable pre-call commit only when the gate applies; union post-call working-tree paths with the net pre-call-HEAD/post-call-HEAD added/modified paths, subtract all pre-call dirty paths, filter test paths. The captured HEAD must be an ancestor of the post-call HEAD. The commit diff uses `--no-relative`; NUL-delimited output keeps spaces and rename destinations; committed deletions are excluded; path readers preserve undecodable bytes. An unknown pre-call HEAD or failed diff adds no evidence.
- Deliberately not here: coverage-quality judgment, automatic acceptance, test-ordering contract, retry-guard redesign, exemption expansion, unborn/no-HEAD commit-only execution, provenance or author-identity checking.
- Documented residuals: a fast-forward/import of existing descendant history gives the same path delta as new backend commits (binary path-delta observable); amend/rebase can lose proof and fail closed; an enforced step outside git cannot advance.
- Sites: `launcher.py` (single enforcement consumer, pre-call snapshot plus post-call set difference), `git_state.py` (commit snapshot/delta reads; launcher dirty-read monkeypatch seam unchanged), `tests/test_launcher.py` and `tests/test_git_state.py`, `docs/how-to/pipeline/run.md` gate diagram, `docs/ARCHITECTURE.md`. Protected CLAUDE.md and driving directives need no change.
- Source defect: BUG_BACKLOG entry "Run's test-authoring gate misses tests committed inside the backend call", plus three alias-step reproductions from PR #140. The entry was removed after delivery verification.

## Findings

| Review (range head) | Id | Disposition |
| --- | --- | --- |
| 1 (`b877be0d9`) | D1 low: stale non-git-skip claims in `git_state.changed_paths`, `launcher._git_changed_paths`, a launcher test comment | fixed: comments/docs corrected, run guide states the existing enforced-gate failure; new `run_step` regression (test created outside git supplies no evidence, cannot advance) fails when unreadable HEAD is made an exemption (1 mutation failure). 52 focused pass; full 15,017 passed |
| 1 | (Provenance) first clean logic pass was against `59e13bc32`; the later ancestry/decoder fixes (`33f5c7996`) reset the window | none | 
| 1 | D2 info: module summary | fixed: names working-tree and commit reads |
| 1 | Unborn HEAD, retry-guard redesign, subprocess factoring, diff short-circuit, test formatting | declined: out of bounded scope or maintenance preference |
| 2 (`9a626fd7e`) | B1: false pass when the pre-call branch diverges and the backend only checks out existing test history | fixed: ancestry check before accepting the commit delta; real-git `run_step` regression fails before, passes after. Fail-closed on amend/rebase documented |
| 2 | B2: `UnicodeDecodeError` from the path decoder on raw-byte output | fixed: `surrogateescape` at all three git subprocess readers; real-subprocess raw-byte regression fails before, passes after (an on-disk invalid-UTF-8 fixture is impossible on macOS, so it is not counted). Post-correction 54 focused, full 15,019 passed |
| 2 | C1 dirty exclusion, C2 unborn commit-only, diagnostic taxonomy, factoring | declined: pinned/deferred scope or preference |
| 2 | Known-limit comment's porcelain wording | fixed: reworded with the contract |
| 3 (`f92ba61ba`) | No logic defect; ancestry and decoder corrections verified (decoder also via a raw-byte filename committed through the index) | refuted/none: imported-history residual documented in the run guide, not provenance machinery; generic failure messages declined (no error taxonomy) |
| 3 | Stale ledger header, run-guide wrapping | fixed: bookkeeping only; production logic stays at `f92ba61ba` |
| 4 (`ca9221876`) | `diff.relative=true` from a subdirectory makes the committed diff root-relative to cwd while porcelain is git-root-relative, so subtraction leaves evidence (reviewer labeled speculative; reproduced) | fixed: `--no-relative` on the single committed-path diff; real-git regression fails before correction. 55 focused, full 15,020 passed in 81.86s. Reset the confirmation window |
| 4 | run.md normal-path/exceptions readability | fixed with the path-contract record |
| 4 | Factoring, optimizations, exhaustive branch coverage | declined: preferences; a diff read failure already adds no evidence |
| 5, 6 (`b8064b023`) | No logic defect (git-state/duplication 29 passed, gate tests 36 passed; review 5 independently reproduced the relative-path mismatch and the flag closing it; review 6 ran no fresh probes) | none; convergence window |
| 5, 6 | Universal-newline handling shared with the existing reader, unmeasured git-version concerns, diagnostic taxonomy, subprocess factoring, extra-call optimization, snapshot concurrency | declined: not reproduced in-scope defects |
| 5, 6 | Reviewer attribution-policy note | refuted: the repository requires recording the actual review method and session |

Mutation evidence: restoring dirty-only logic fails both multi-commit regressions (2 failures); removing dirty-path subtraction fails 9 of the 16-case matrix; sources restored after each mutation. Initial full suite 15,016 passed, 67 skipped in 70.41s.

## Closure

**Converged for logic:** reviews 5 and 6 are two consecutive independent clean passes over `db0b81151..b8064b023`, the latest production snapshot. Reviews 1-4 do not supply this window; their findings and corrections stay recorded above. The closing commit changes tracking/evidence only and claims no further Claude review of those bytes. Production code remains the reviewed `b8064b023` snapshot; the changelog and this ledger accompany the ready PR. No tracked or pending items remain.
