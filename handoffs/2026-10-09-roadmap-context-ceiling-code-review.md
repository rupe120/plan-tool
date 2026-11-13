# Roadmap candidate context ceiling — code review ledger

| Field | Value |
| --- | --- |
| Change | BACKLOG #469 (removed on merge, PR #58; its sizing text is in `docs/evidence/integration-context-budget-2026-10-09/sizing.md`): new candidate contexts admit up to 384 KiB (was 192 KiB), and a stored selector capsule is reproduced at the ceiling it recorded |
| Branch | `fix/roadmap-context-ceiling` |
| Review range | pass 1: `acdceacb..c0481d10` (fix `3e35be85`; backlog record `c0481d10`); pass 2: `c0481d10..35220609`; pass 3: `acdceacb..13ab814f` (whole change) |
| Checks run | Full suite `uv run pytest tests/ -q -n auto` on the final head: 13,670 passed, 67 skipped (one skip is the working-tree-dependent `tests/test_review.py` plan-title test) |
| Reviewer | headless `claude-personal -p`, report-only, `high` effort (`.tmp/roadmap-context-ceiling-code-review-N.stream.log`); reviewers could not run programs, so their test claims are by reading and each fix was checked by mutation in the driving session |
| Disposition | pass 1: 3 fixed, 1 measured, 1 deferred, 1 declined; pass 2: 3 fixed, 1 measured by Codex run, 1 declined, 1 comment; pass 3: 5 fixed in docs or tests; converged (passes 2 and 3 are two consecutive low-yield passes against logic head `c66f7361`) |

## Settled decisions (hand to each reviewer)

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

## Findings

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

## Convergence status

Converged, 2026-10-09. The logic head is `c66f7361` and has not changed since. Pass 2 (four Low, one Info) and pass 3 (three Low, two Info) are two independent consecutive low-yield passes against it, with no new material correctness or completeness issue in either; every finding of passes 1 to 3 has a disposition. Everything after `c66f7361` is documentation, backlog text, tests and test comments, which does not reset the logic window. Pass 3's one substantive probe, the new batch hop over a 192 KiB candidate, passed when written. The loop stops here; no pass 4 is launched.

Open follow-ups, none blocking: the deferred batch-ceiling consistency gap (`BUG_BACKLOG.md`, ROADMAP section; pass-1 finding 4), BACKLOG #470 (budget warning window) and #471 (relation compaction), and the Linux per-argument limit, unverified.
