# Roadmap candidate context ceiling — code review ledger

| Field | Value |
| --- | --- |
| Change | BACKLOG #469 (removed on merge, PR #58; its sizing text is in `docs/evidence/integration-context-budget-2026-10-09/sizing.md`): new candidate contexts admit up to 384 KiB (was 192 KiB), and a stored selector capsule is reproduced at the ceiling it recorded |
| Branch | `fix/roadmap-context-ceiling` |
| Review range | pass 1: `acdceacb..c0481d10` (fix `3e35be85`; backlog record `c0481d10`); pass 2: `c0481d10..35220609`; pass 3: `acdceacb..13ab814f` (whole change) |
| Checks run | Full suite `uv run pytest tests/ -q -n auto` on the final head: 13,670 passed, 67 skipped (one skip is the working-tree-dependent `tests/test_review.py` plan-title test) |
| Reviewer | headless `claude-personal -p`, report-only, `high` effort (`.tmp/roadmap-context-ceiling-code-review-N.stream.log`) |
| Disposition | pass 1 triaged (3 fixed, 1 measured, 1 deferred, 1 declined); pass 2 triaged (3 fixed, 1 measured by Codex run, 1 declined, 1 comment); pass 3 triaged (5 fixed in docs or tests); converged (passes 2 and 3 are two consecutive low-yield passes against logic head `c66f7361`) |

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
  existing active candidate by construction; a reviewer who disagrees must show the
  reproduction.
- A lineage stored under 64 KiB already failed re-entry on unmodified code after the 192 KiB
  bump; this change fixes that too, and a parametrized test covers both prior ceilings.
- Three tests pin values stored under 192 KiB (the selector-era seal and replacement bytes, the
  pre-batch candidate identity and admission bytes, and the clean structural seal id). They now
  issue under a literal 192 KiB ceiling on purpose; the selector-era review test then continues
  the lineage under the current ceiling.
- Deliberately not in this change: the budget warning's fixed 200K window (BACKLOG #470),
  relation-node compaction (#471), a token preflight, fallback-backend capacity checks, and any
  prose-only context route.
- `c0481d10` edits `BACKLOG.md` only. Review it for accuracy of the claims it records, not as logic.

## Review pass 1 — /code-review (high, headless), 2026-10-09

Scope: `acdceacb..c0481d10`. Method and result below are the reviewer's report, copied from `.tmp/roadmap-context-ceiling-code-review-1.md` (stream log `.tmp/roadmap-context-ceiling-code-review-1.stream.log`). The reviewer could not run programs, so its test claims are by reading; each fix below was checked by mutation in the driving session. Six findings, all Low or Info; no Critical, High or Medium.

### Method

- Scope: `acdceacb..c0481d10` (fix `3e35be85`, backlog record `c0481d10`) on `fix/roadmap-context-ceiling`. I read the full diff and `handoffs/2026-10-09-roadmap-context-ceiling-code-review.md` first; its "Settled decisions" are not re-reported.
- Read: all of `plan_tool/roadmap_candidate_context.py` around the constants, `build_candidate_context`, `rebuild_candidate_context_at_recorded_ceiling`, `_build_selector_context`, `_build_context_batch`, `expand_candidate_context`, `_compile_context`, `_render_payload`, `_render_batch_payload`, `_capsule_is_intact`. In `roadmap_candidate.py`: `_verify_bindings` and its callers. In `roadmap_candidate_run.py`: admission and evidence validators, `_validate_candidate_evidence`, `_capsule_and_receipt_are_exact`, `run_initial_candidate_proposal`, `_run_batch_candidate_proposal`, `_store_batch_candidate`, `render_candidate_delta_prompt`. In `roadmap_candidate_review.py`: the replacement and expansion call sites and `_recompute_replacement_impact_atoms`. Also `backend.py` prompt transport, the new and changed tests, `ROADMAP_FORMAT.md` and its pinning test, the changelog fragment, and the `BACKLOG.md` diff.
- Sweep for the class "stored value compared with the current constant": grep for `CANDIDATE_CONTEXT_MAX_BYTES`, `ceiling_bytes`, `build_candidate_context`, `expand_candidate_context`, `is_supported_candidate_context_ceiling`, and the literals 192 KiB / 196608 / 64 KiB across `plan_tool/`, `docs/`, `*.md`. Result: outside `roadmap_candidate_context.py` no module reads the constant. `roadmap_candidate_run.py` and `roadmap_candidate_review.py` only read the stored `capsule.ceiling_bytes`. The only current-constant consumers are the new-issuance sites: selector `build_candidate_context`, the batch compile at lines 589/602/609, and the batch payload render at line 1143. No seal, replacement, promotion or ledger code recomputes against the current constant. The selector `_verify_bindings` was the only offender and is fixed. Expansion already compiles at `capsule.ceiling_bytes`.
- Programs were NOT runnable in this session. Every `uv run pytest` and `python` invocation was denied for approval, and so was any piped command. All test claims below come from reading the tests and the code under test, not from running them.
- Mutation-by-reading, which new tests would fail without the fix:
  - `test_reentry_of_a_lineage_stored_under_an_earlier_ceiling_survives_a_ceiling_raise` (run tests) fails without the fix. The second call goes admission -> `load_stored_candidate_proposal` -> `_validate_candidate_evidence` -> `_verify_bindings`, which rebuilds at the unpatched 512 KiB and returns `invalid-predecessor`/`invalid-bindings`. That surfaces as the "cannot be reproduced" error and the outcome is not `stored`.
  - `test_a_stored_capsule_reproduces_only_at_its_recorded_ceiling` and `test_rebuild_at_an_unissued_recorded_ceiling_is_refused_without_a_capsule` fail without the fix with an ImportError on the new function. They exercise the function, not the `_verify_bindings` call site (see finding 5).
  - `test_context_between_the_prior_and_current_ceiling_is_admitted_under_the_current_one` and the batch twin fail without the constant raise (200 KiB brief over 192 KiB).
  - `test_every_issued_ceiling_is_supported` goes red if either prior value is dropped from the allowlist. The refused-values test goes red if the allowlist widens to 256 KiB, 1 MiB, or bool/str.
  - The three tests that now patch the constant to 192 KiB would go red against the 512 KiB payload bytes, because the pinned hashes are literals.

### Findings

#### 1. `ROADMAP_FORMAT.md` overstates the contract for batch capsules, and its pinning test cannot catch that

- Category: documentation accuracy
- Severity: Low
- Location: `ROADMAP_FORMAT.md:1250-1253`; `tests/test_roadmap_format.py:524-526`
- Failure scenario: the new text says capsules issued under an earlier ceiling "retain that ceiling for their whole lineage: a stored capsule is reproduced at its recorded ceiling". Both halves are true only for selector-era capsules. A batch lineage does not retain its ceiling. A new batch hop stacked on a stored 192 KiB candidate is compiled by `_build_context_batch` with `CANDIDATE_CONTEXT_MAX_BYTES` unconditionally (`roadmap_candidate_context.py:589,602,609,1143`), so the lineage has mixed ceilings. A stored batch capsule is also never reproduced. It is bound by digest and member receipts only (`roadmap_candidate_run.py` "Not recomputed for batch evidence"). Since Integration's own candidates are batch candidates, a reader of the format doc would infer the wrong mixed-ceiling and recomputation behaviour. The pinning test only asserts that the substrings appear in the whitespace-normalized section, so it states no contract about which route each sentence covers.
- Suggested fix: scope the sentence. For example: "A stored selector-era capsule is reproduced at its recorded ceiling. A stored batch capsule keeps its recorded ceiling and is verified by digest, and each new batch hop uses the current ceiling." Pin that wording in the test.

- **Disposition:** fixed in `c66f7361`. `ROADMAP_FORMAT.md` now scopes the recorded-ceiling rule to selector capsules, says a stored batch capsule is verified by digest and receipts and never re-rendered, and says each new batch hop uses the current ceiling. `tests/test_roadmap_format.py` pins all four phrases.

#### 2. Prompt-size sizing assumes constant overhead, and the prompt travels as one argv element on every backend

- Category: capacity / unverified assumption
- Severity: Low (could not be run; potentially Medium on a non-macOS host)
- Location: `plan_tool/roadmap_candidate_context.py:80`; `plan_tool/roadmap_candidate_run.py:1120-1122` (receipt embedded in the prompt); `plan_tool/backend.py:598-612,1374-1380` (prompt is the final argv element, no `stdin_text` anywhere)
- Failure scenario: the #469 sizing says a 512 KiB payload yields "about 675 KB" of prompt by adding a flat 136-150 KB of templates. `render_candidate_delta_prompt` embeds `capsule_payload` and the full `capsule_receipt`. The receipt repeats the inventory, relation evidence, and per-member source-span and receipt records, so it scales with the payload. In the measured Integration case the non-payload overhead is 149 KB on a 212 KB payload. Scaling the receipt share gives roughly 750-830 KB at the ceiling, plus the replacement `review_pair` and the batch `collection_hints`. That prompt is passed as a single argv element (`claude -p ... <prompt>`, `agent -p ... <prompt>`). macOS `ARG_MAX` is 1 MiB shared with the environment, so a context near the ceiling gets thin headroom. Where `MAX_ARG_STRLEN` is 128 KiB (Linux), any prompt over 128 KiB fails with E2BIG. That already applied to the 192 KiB ceiling because the template alone is over 128 KiB, but the raise makes the ceiling a number the transport cannot carry. The change validates the ceiling against the token window but not against the exec transport. A refusal "before any model call" is replaced by a spawn failure after the proposal is admitted, reported as a generic backend failure. `Plan-tool's own subprocess calls were not measured` in the backlog, so this is open.
- Suggested fix: before shipping 512 KiB, measure the rendered prompt at a synthetic 512 KiB capsule (selector, batch, and replacement) against `getconf ARG_MAX` minus the environment size. Either record the real number in #469 and #470, or move the prompt to stdin for these invokers. If neither is done now, file an out-of-scope backlog entry for the argv transport limit.

- **Disposition:** addressed by measurement and by lowering the ceiling; not a code change. The overhead is not flat, so BACKLOG #469 now fits it (about 76 KB plus 0.34 × payload) and sizes 384 KiB at a prompt of about 605 KB. A 1,000,000-byte argument spawns on this macOS host (`ARG_MAX` 1,048,576), leaving about 400 KB of headroom; at the rejected 512 KiB it would have been about 780 KB. Linux's per-argument limit is not verified here and is recorded as unverified in #469; moving the prompt to stdin is not in scope.

#### 3. `_verify_bindings` discards the rebuild refusal and mislabels a bad recorded ceiling as a predecessor fault

- Category: diagnostics
- Severity: Low
- Location: `plan_tool/roadmap_candidate.py:1648-1652`
- Failure scenario: `rebuild_candidate_context_at_recorded_ceiling` returns `invalid-capsule` ("recorded context ceiling is not a supported value") for an unsupported stored ceiling, but `_verify_bindings` collapses every `initial.capsule is None` into `_refusal("invalid-predecessor", "predecessor cannot reproduce the selected context")`. A forged or corrupted `ceiling_bytes` (for example 256 KiB) is reported as a predecessor problem, which sends an operator to inspect the wrong artifact. The `expanded.capsule is None` branch right below it already distinguishes `invalid-capsule`. The new unsupported-ceiling test only covers the context-level function, so this mapping is unpinned.
- Suggested fix: when `initial.refusal` has reason `invalid-capsule`, return `_refusal("invalid-capsule", initial.refusal.detail)`. Add a `_verify_bindings`-level test with a capsule whose `ceiling_bytes` is unsupported.

- **Disposition:** fixed in `c66f7361`. `_verify_bindings` returns `invalid-capsule` with the rebuild's detail when the recorded ceiling is unsupported. `test_a_stored_capsule_with_an_unissued_ceiling_is_refused_as_an_invalid_capsule_not_a_predecessor_fault` fails without the mapping (checked by mutation).

#### 4. For batch capsules the ceiling is trusted on allowlist membership alone

- Category: validation gap (pre-existing, widened by a third allowed value)
- Severity: Low
- Location: `plan_tool/roadmap_candidate_context.py:1166-1171` (`_capsule_is_intact`); `plan_tool/roadmap_candidate_run.py:283-340` (batch branch returns before any ceiling check)
- Failure scenario: selector capsules are protected because `_verify_bindings` re-renders them, and `_capsule_and_receipt_are_exact` compares the payload's embedded `ceiling_bytes`. Batch capsules are never re-rendered. `_capsule_is_intact` checks only that `capsule.ceiling_bytes` is supported, that `receipt.ceiling_bytes` equals it, and that the digests match. It never checks that the payload's embedded `"ceiling_bytes"` (line 1143) equals `capsule.ceiling_bytes`, and never that `len(payload) <= ceiling_bytes`. A stored batch candidate whose capsule says 64 KiB over a 400 KB payload, or whose payload says 512 KiB while the capsule says 192 KiB, passes validation. The two record fields and the digest-covered byte string can disagree about the ceiling, which defeats the "a forged `ceiling_bytes` must not validate a capsule" decision for batch capsules. This needs write access to stored evidence and the digests are not signed, so it is not an external attack. It is a consistency hole that this change's three-value allowlist makes easier to hit by accident (a hand-edited or migrated record).
- Suggested fix: in `_capsule_is_intact`, also require `capsule.receipt.payload_bytes <= capsule.ceiling_bytes` and `json.loads(capsule.payload)["ceiling_bytes"] == capsule.ceiling_bytes`. Pin both with a batch test next to `test_only_issued_ceilings_are_supported...`.

- **Disposition:** deferred. The gap predates this change (the allowlist check is the same for two values) and fixing it widens a validator outside the ceiling change. Filed as `BUG_BACKLOG.md` ROADMAP entry "A stored batch candidate capsule is accepted when its payload's embedded ceiling disagrees with its recorded ceiling" (`35220609`).

#### 5. Test gaps and masking in the new coverage

- Category: test coverage
- Severity: Low
- Location: `tests/test_roadmap_candidate_run.py:399` and `:410-412`; `tests/test_roadmap_candidate_review.py:4652`; `tests/test_roadmap_candidate_context.py:1170-1190`
- Failure scenario:
  - (a) `test_selector_era_identity_and_admission_bytes...` and `test_approval_without_removed_ids_is_unchanged` set the 192 KiB patch for the whole test, including `load_stored_candidate_proposal` (run test, line 410) and the approval/seal steps (review test). The docstring says the point is that a stored candidate is "recomputed from its stored bytes on every review, replacement and promotion". After the patch, current == stored, so these two tests can no longer detect a recompute against the current constant. Only the new re-entry test does, and only for re-entry.
  - (b) The reproduction test calls `rebuild_candidate_context_at_recorded_ceiling` directly. Nothing exercises the `capsule.expansion is not None` branch of `_verify_bindings` under a prior ceiling, which is the branch that feeds `expand_candidate_context` an `expected_capsule` built at the recorded ceiling. A regression there, for example rebuilding the initial at the current value before expanding, would stay green. The #469 verification list asks for "re-enter, and expand with their recorded ceilings".
  - (c) Promotion and review re-verification of a stored 192 KiB selector candidate after the raise are covered only indirectly, via `_selector_era_review` (which does continue under the current ceiling, so that path is covered).
- Suggested fix: scope the patches in (a) to the issuance call with `monkeypatch.context()`, as the new tests do, so reload and approval run under the real 512 KiB constant. For (b), add a parametrized (64 KiB, 192 KiB) case that issues an expanded capsule under the prior ceiling and runs `_verify_bindings` and re-entry under 512 KiB.

- **Disposition:** fixed in `c66f7361`. (a) The two stored-era pin tests now patch only issuance, so reload and approval run under the current ceiling. (b) `test_an_expanded_capsule_stored_under_an_earlier_ceiling_still_verifies_after_a_raise` covers the expansion branch for 64 KiB and 192 KiB; rebuilding the initial capsule at the current ceiling turns it red (checked by mutation). (c) Needed no change.

#### 6. Constant naming will not survive the next raise

- Category: maintainability (nit)
- Severity: Info
- Location: `plan_tool/roadmap_candidate_context.py:78-86`
- Failure scenario: `_LEGACY_CANDIDATE_CONTEXT_MAX_BYTES` and `_PRIOR_CANDIDATE_CONTEXT_MAX_BYTES` are named by position relative to "now". The next raise has two priors, so a rename or a mixed `_LEGACY`/`_PRIOR` vocabulary follows. A reader also cannot tell from the names that the allowlist is the set of values ever issued.
- Suggested fix: name them by value (`_CEILING_64_KIB`, `_CEILING_192_KIB`), or define one `_ISSUED_CEILINGS` tuple with the current value last and derive `CANDIDATE_CONTEXT_MAX_BYTES` from it. No change is needed for correctness.

- **Disposition:** declined. A naming nit with no behavior effect; renaming the constants for a hypothetical next raise is more than the smallest change that closes the finding. Revisit when a fourth ceiling is added.

### Result

Findings 1-6 are all Low or Info. No Critical, High or Medium defect was found in the core change. The areas below were traced and hold.

- **Stored selector capsule, admission, evidence and replacement verification.** All use the recorded `capsule.ceiling_bytes`. `_verify_bindings` is the only rebuild site and now uses the recorded value. `expand_candidate_context` compiles at `capsule.ceiling_bytes` both for the reproduced initial and for the expansion.
- **Unsupported ceiling in `_verify_bindings`.** A forged ceiling is refused by the allowlist before any rebuild (diagnostic quality is finding 3). `type(value) is int` correctly refuses `True` and numeric strings.
- **Batch route.** No stored batch capsule, receipt, seal id or admission is recomputed against the current constant. The embedded `"ceiling_bytes"` is written from the same constant that sets `capsule.ceiling_bytes`, so freshly issued capsules are self-consistent. Stored ones are not cross-checked (finding 4). The receipt-equality re-entry (`active.evidence.batch_receipt == capsule.receipt`) is covered by the settled decision and I did not reopen it.
- **New issuance sites.** The only ones are selector `build_candidate_context` (via `_build_selector_context`) and the batch compile. Both correctly use the current constant. The over-budget refusal reports the ceiling it was measured against.
- **Docs and changelog.** The changelog fragment matches the behavior. The `BACKLOG.md` diff accurately records commit `ae35bcb8` (confirmed in git: 2026-09-03) and the re-entry gap, with one caveat: the "675 KB" prompt estimate is optimistic (finding 2). No stale "192 KiB is current" statement remains outside evidence and implementation-plan files. Commit messages carry no attribution lines.

## Review pass 2 — /code-review (high, headless), 2026-10-09

Scope: `c0481d10..35220609` (the pass-1 fixes `c66f7361` and the backlog records). Method and result below are the reviewer's report, copied from `.tmp/roadmap-context-ceiling-code-review-2.md` (stream log `.tmp/roadmap-context-ceiling-code-review-2.stream.log`). The reviewer could not run programs, so its test claims are by reading. Five findings: four Low, one Info; no Critical, High or Medium.

### Method

- Scope: `c0481d10..35220609` on `fix/roadmap-context-ceiling`: `c66f7361` (code, tests, `ROADMAP_FORMAT.md`, changelog fragment) and `35220609` (`BACKLOG.md`, `BUG_BACKLOG.md`). I read `handoffs/2026-10-09-roadmap-context-ceiling-code-review.md` first. Its "Settled decisions" and the pass-1 findings and dispositions are not re-reported, including the deferred batch-ceiling consistency gap and the declined naming nit.
- Read: the full diff of both commits. In `plan_tool/roadmap_candidate.py`, `_verify_bindings` and all callers of it and of `materialize_candidate`. In `plan_tool/roadmap_candidate_context.py`, `build_candidate_context`, `rebuild_candidate_context_at_recorded_ceiling`, `_build_selector_context`, `_build_context_batch`, `expand_candidate_context` and `_capsule_is_intact`. In `plan_tool/roadmap_candidate_run.py`, `_validate_candidate_evidence`, `_run_batch_candidate_proposal`, `_store_batch_candidate` and `render_candidate_delta_prompt`. In `plan_tool/roadmap_candidate_review.py`, `_recompute_replacement_impact_atoms` and the materialize call sites. The edited and neighbouring tests (`tests/test_roadmap_candidate_context.py`, `_run.py`, `_review.py`, `tests/test_roadmap_format.py`), the rewritten `ROADMAP_FORMAT.md` paragraph, the changelog fragment, and the `BACKLOG.md` #469/#470 entries and the new `BUG_BACKLOG.md` entry.
- Greps: every reader of a refusal `reason` (`refusal.reason`, `.reason ==`, the literals `invalid-capsule` and `invalid-predecessor`); every consumer of `CANDIDATE_CONTEXT_MAX_BYTES` and `build_candidate_context`; remaining `512 KiB`, `192 KiB`, `1M-token` and `1,000,000-token` statements across `*.md`, `*.py` and `*.json`.
- Permission denials / programs not runnable: `uv run pytest` was denied for approval (both a piped form and a plain form). No test, mutation or Python was executed. All test claims below come from reading the tests and the code under test. Mutation checks are reasoned by tracing, not run. The BACKLOG arithmetic was recomputed by hand. I did not re-run `codex debug models`, so the 272,000 / 95% window figures and the `ARG_MAX` measurement are unverified.

### Findings

#### 1. The invalid-capsule mapping never reaches an operator on the stored-capsule paths

- Category: diagnostics / fix does not deliver its stated goal
- Severity: Low
- Location: `plan_tool/roadmap_candidate_run.py:812-818` (`_validate_candidate_evidence`); `plan_tool/roadmap_candidate_review.py:2976-2984` (`_recompute_replacement_impact_atoms`); mapping at `plan_tool/roadmap_candidate.py:1651-1654`
- Failure scenario: pass-1 finding 3 was fixed so an unsupported recorded ceiling returns `invalid-capsule` instead of a predecessor fault, "so the operator is pointed at the capsule, not the predecessor". No caller reads `refusal.reason`. I grepped all of them, and the new reason breaks none. But the two callers that actually handle a stored selector capsule discard the refusal and raise fixed text. `_validate_candidate_evidence` raises `"candidate capsule cannot be reproduced from its predecessor"`, and `_recompute_replacement_impact_atoms` raises `"replacement capsule cannot be reproduced from its predecessor"`. A stored capsule with a forged or corrupt `ceiling_bytes` (for example 256 KiB) therefore still tells the operator to look at the predecessor at re-entry, review, replacement and promotion. The refusal detail is only surfaced through `materialize_candidate` callers (`roadmap_candidate_run.py:1396`, `roadmap_candidate_review.py:1198`), which handle freshly issued capsules or, in the replacement path, the stored one. The new test `test_a_stored_capsule_with_an_unissued_ceiling_is_refused_as_an_invalid_capsule_not_a_predecessor_fault` calls `_verify_bindings` directly, so it is green while the user-visible message is unchanged.
- Suggested fix: carry `verified.reason` and `verified.detail` into the two raised errors (for example `f"candidate capsule cannot be reproduced ({verified.detail})"`), and add one test that loads a stored candidate with a forged ceiling and asserts the message names the ceiling. Alternatively, state in the pass-1 disposition that the mapping is internal only.

- **Disposition:** declined as a behavior change. Pass-1 finding 3 was scoped to `_verify_bindings`' return value, which now classifies the refusal as `invalid-capsule`; no caller reads `reason` by value. The two stored-reload callers deliberately wrap every refusal in one operator-facing message, and the case needs a forged or corrupted stored record (write access to the store). Threading the detail through both is a logic edit that would reset the two-clean-pass window for a diagnostic nuance in a rare path. The pass-1 disposition wording stands as scoped.

#### 2. `ROADMAP_FORMAT.md` still says a batch capsule "stays re-enterable" and that replay "re-enters the stored lineage"

- Category: documentation accuracy
- Severity: Low
- Location: `ROADMAP_FORMAT.md:1250-1257`, and `ROADMAP_FORMAT.md:1260-1261` ("Replaying the same proposal re-enters the stored lineage"); pinned by `tests/test_roadmap_format.py:525`
- Failure scenario: the rewritten paragraph scopes the reproduction rule to selector capsules and says a batch capsule is verified by digest. But the lead sentence is still unscoped: "A capsule issued under an earlier ceiling (64 KiB or 192 KiB) keeps that ceiling and stays readable and re-enterable". On the batch route a replay is not a re-entry. `_run_batch_candidate_proposal` builds the new context with `source = active` (the stored candidate), so the new receipt's `source` and `predecessor` identity is the active candidate. The stored `batch_receipt` has the candidate's own source. The equality check at `roadmap_candidate_run.py:1581` therefore cannot match, which the settled decisions already accept. The consequence for the doc is that a replay of a batch proposal over a stored 192 KiB candidate makes a new model call and a new superseding hop at 384 KiB, and does not return the stored lineage. Integration's own candidates are batch candidates. This is the doc claim only; I am not asking for a code change. The pinning test pins the unscoped phrase, so the claim cannot be caught.
- Suggested fix: scope both sentences, for example "a stored selector capsule stays re-enterable; a batch capsule stays readable and valid as a source, and a replay over it is a new batch hop under the current ceiling". Change the pinned phrase to match, and scope the "Replaying the same proposal" sentence to the selector route. Optionally apply the same wording to the #469 Outcome line ("stays readable, re-enterable, and byte-identical", `BACKLOG.md` about 12838).

- **Disposition:** fixed in `43640a7e` (doc and pin only). The lead sentence now says a capsule "stays readable", that a stored selector capsule is "also re-enterable", and that a stored batch capsule is verified by digest and receipts and never re-rendered; `tests/test_roadmap_format.py` pins the narrower wording. The #469 Outcome line was scoped the same way in `13ab814f`. The pre-existing "Replaying the same proposal re-enters the stored lineage" sentence describes the fixed-selector route and is left as it was; this change asserts nothing about batch replay.

#### 3. Stale "1M-token" rationale left in BACKLOG after the sizing was re-based on Codex's 272K window, and #470 now contradicts itself

- Category: documentation (forward-looking rule: vocabulary sweep of a reversed rationale)
- Severity: Low
- Location: `BACKLOG.md:322-323` (roll-up bullet), `BACKLOG.md:12875` (#469 Quality), `BACKLOG.md:12899-12901` (#470 Evidence)
- Failure scenario: the 35220609 edit re-based #469 on Codex's 272K working window, but the roll-up still says #469 admits "a complete authorized context a 1M-token model can take", and #469's Quality line says the gate admits context "that a 1M-token model can take". Both argue for the rationale the entry just rejected for the owner's Codex deployment. The edited #470 Evidence line is internally inconsistent: it says a 605 KB prompt prints `high` "on Claude models whose window is 1,000,000 tokens (owner's deployment, e.g. `--backend codex --model gpt-6.1-sol`)". `gpt-6.1-sol` is the Codex model with the 272K window, not a Claude model with a 1M window. It also hides a consequence for #470's own Outcome. At a 272K window, 605 KB at 3.5 bytes per token is about 173K tokens, 64% of the window, so the owner's actual deployment would print `warn`, not `ok`. #470's "stops crying wolf on large-window models" holds only for the Claude lane. A future implementer of #470 would write the wrong expectation for the Codex case.
- Suggested fix: reword the roll-up and Quality lines to "a complete authorized context the supported backends' windows can take (Codex 272K working window)". In #470 Evidence, separate the two lanes: Claude (1M window, 605 KB reads `ok`) and `--backend codex --model gpt-6.1-sol` (272K window, 605 KB reads `warn`). Add a Codex-lane assertion to #470 Verification.

- **Disposition:** fixed in `13ab814f`. The roll-up bullet, #469's Outcome and Quality lines no longer argue from a 1M-token model. #470's Evidence now has a Claude lane (1M window, 605 KB prints `high` today) and a Codex lane (272K window: about 147K measured tokens, 54%, but the 3.5-bytes-per-token estimator reads `warn`), and its Verification asserts both.

#### 4. The 384 KiB capacity claim has about 0.4K tokens of headroom at the stated pessimistic ratio, and extrapolates beyond the measured range

- Category: capacity / unverified margin
- Severity: Low (Info if the 41.7K harness figure is not the working assumption)
- Location: `BACKLOG.md:12788-12806` (#469 sizing); commit message of `c66f7361` ("stays inside Codex's 272K working window at the pessimistic bytes-per-token ratio")
- Failure scenario: the computed sizes follow from the measured points. The exact two-point fit is a prompt of 75.5 KB plus 0.3485 times the payload. The quoted "76 KB plus 0.34 times" gives 603 KB at 393,216 where the exact fit gives 605.7 KB. Both agree with the stated "about 605 KB". The token ranges also follow: 605 KB divided by 4.4 is 137.5K and divided by 2.8 is 216K, matching "138K–216K". At 512 KiB the fit gives about 782 KB and 177.8K–279.3K tokens, matching "about 780 KB, 177K–279K". The weak point is the claim that this "reaches the effective window only at the pessimistic ratio". With the 41,662-token harness figure (which is the owner's raised `project_doc_max_bytes`, a machine-local setting), the worst case is 216.3K + 41.7K = 258.0K tokens against a 258.4K effective window. That leaves 0.15% margin and nothing for the output, for the second attempt's appended correction, for the replacement `review_pair`, or for `collection_hints`. `collection_hints` is computed from the source candidate, not the payload, so it does not scale with the fitted payload term. The fit is also extrapolated 1.86 times past its largest measured payload (212 KB to 393 KB). So "stays inside" is true only by arithmetic coincidence, and the ceiling is effectively at the window limit for the pessimistic case.
- Suggested fix: reword as "reaches the effective window at the pessimistic ratio" and record that the margin is under 1K tokens. If the margin matters, measure the rendered prompt for a synthetic payload near 384 KiB (selector, batch with a large source, and a retry) and replace the extrapolation with a measured point.

- **Disposition:** fixed by measurement in `13ab814f`; no code change. The pessimistic 2.8 bytes per token was Claude's non-isolated ratio, not Codex's. Measured on Codex 0.162.0 with `gpt-6.1-sol`: the real 211,712-byte Integration payload costs 51,307 input tokens (70,471 with it, 19,164 bare), 4.13 bytes per token. A 605 KB prompt is about 147K tokens, 166K–189K with the 19K–42K harness, 64–73% of the 258K effective window. 512 KiB would fit at 81–90%; 384 KiB is chosen for the headroom it leaves for output, a retry's correction and the review pair. One payload, one run; recorded as such in #469.

#### 5. Narrowing the patch in `test_approval_without_removed_ids_is_unchanged` is behavior-neutral, so it pins nothing about reload

- Category: test coverage (informational)
- Severity: Info
- Location: `tests/test_roadmap_candidate_review.py:4650-4662`
- Failure scenario: pass-1 finding 5(a) asked the stored-era pin tests to patch only issuance so that "reload and approval run under the current ceiling" and could detect a recompute against the current constant. That holds for `test_selector_era_identity_and_admission_bytes_are_the_values_stored_before_the_batch_route` (the selector reload calls `_verify_bindings`, which would rebuild at 384 KiB and fail with `invalid-bindings` if it ignored the recorded ceiling, so that test does go red under the mutation). It does not hold for `test_approval_without_removed_ids_is_unchanged`. It is a batch test, and a stored batch capsule is never re-rendered. The review module has no `build_candidate_context` call, so approval and seal use the stored payload bytes and cannot read the current constant. Narrowing the patch changes nothing observable there. If a future change did make approval recompute a batch payload at the current ceiling, this test would still depend on that being reachable at all. As written, it guards only that the seal id equals the literal. The docstring-level claim in the ledger that both tests now "run under the current ceiling" is true but vacuous for this one.
- Suggested fix: no code change needed. Optionally add a comment that batch capsules are never re-rendered, so the narrowing is for symmetry only, and keep `_selector_era_review` as the real guard for the recorded-ceiling rule.

- **Disposition:** no behavior change; comment added in `43640a7e`. `test_approval_without_removed_ids_is_unchanged` is a batch test, so narrowing its patch is for symmetry; the comment says `_selector_era_review` is the guard for the recorded-ceiling rule.

### Areas checked that hold

- `_verify_bindings`: the new branch reads `initial.refusal.reason == "invalid-capsule"` and `initial.refusal.detail`. Only `rebuild_candidate_context_at_recorded_ceiling` can produce `invalid-capsule` on that path (`_select_feedback` and `_compile_context` do not). Every other refusal still maps to `invalid-predecessor`, as before. Nothing in `plan_tool/` or the tests reads a refusal `reason` by value, so the new reason breaks no consumer (finding 1 is about message text, not logic).
- `test_an_expanded_capsule_stored_under_an_earlier_ceiling_still_verifies_after_a_raise`: both prior values issue a fitting fixture and `expand_candidate_context` compiles at `capsule.ceiling_bytes`. Rebuilding the initial capsule at the current ceiling would make the expanded capsule differ and return `invalid-bindings`, so the test goes red under that mutation. `STAGES`, `roadmap_candidate` and `roadmap_candidate_context` are imported in the test module. `model_copy(update=...)` on the frozen pydantic record does not validate, so the forged-ceiling test reaches the allowlist check, and the receipt equality check at the top of `_verify_bindings` passes first because the receipt is unchanged.
- `test_selector_era_identity_and_admission_bytes_are_the_values_stored_before_the_batch_route`: issuance is patched through the `build_candidate_context` module global, and the reload and the final assertions run at 384 KiB. If `_verify_bindings` rebuilt at the current ceiling, `load_stored_candidate_proposal` would raise, so the test still pins what its docstring says.
- `ROADMAP_FORMAT.md` pinning test: all four new substrings and "currently 384 KiB" appear in the whitespace-normalized section. The claims "a stored batch capsule is verified by its digest and receipts and never re-rendered" and "a new batch hop on a stored candidate uses the current ceiling" are true: `_build_context_batch` uses the constant for the compile, the over-budget check, the receipt, the capsule and the payload. The only open part is "re-enterable" (finding 2).
- BACKLOG numbers: the 50,432-byte headroom and 81% for 256 KiB, the 420 KB and 595 KB warning thresholds (0.6 and 0.85 of 700 KB), and the 400 KB argv headroom (1,000,000 minus about 605 KB) all recompute.
- Remaining stale literals: no `512 KiB` remains outside the intentional "rejected" sentence in #469 and the refused-values test. The `1M-token` leftovers are listed in finding 3. `docs/evidence/integration-context-budget-2026-10-09/measurements.json` still carries the owner's original 1M statement, correctly as dated evidence.
- `BUG_BACKLOG.md` entry: format, route, tier and arc fields are present and its claims match `_capsule_is_intact`.
- Commit messages carry no attribution lines.

### Result

No Critical, High or Medium defect found. Four Low findings and one Info. The code change in `c66f7361` is correct as far as tracing can show: the invalid-capsule mapping, both new tests, and the narrowed patches hold. The substantive issues are that the diagnostic improvement does not reach the stored-reload callers' error text (1), one unscoped doc sentence that overstates batch re-entry (2), a stale and self-contradictory BACKLOG rationale (3), and a capacity margin that is thinner than the text implies (4). Programs were not runnable, so none of this was confirmed by execution.

## Review pass 3 — /code-review (high, headless), 2026-10-09

Scope: `acdceacb..13ab814f`, the whole change, as an independent pass with the pass-1 and pass-2 findings excluded. Method and result below are the reviewer's report, copied from `.tmp/roadmap-context-ceiling-code-review-3.md` (stream log `.tmp/roadmap-context-ceiling-code-review-3.stream.log`). The reviewer could not run programs, so its test claims are by reading. Five findings: three Low, two Info; no Critical, High or Medium.

### Method

- Scope: `acdceacb..13ab814f` on `fix/roadmap-context-ceiling`, with attention on the logic head `c66f7361`. Report-only; no source, test or doc file was edited.
- Read first: `handoffs/2026-10-09-roadmap-context-ceiling-code-review.md`. Its settled decisions and every pass-1 and pass-2 finding with its disposition were not re-reported, including the deferred batch-ceiling consistency gap, the declined naming nit, and the declined request to thread the refusal detail through the two stored-reload callers.
- Read in full or around the change: `plan_tool/roadmap_candidate_context.py` (constants, allowlist, `build_candidate_context`, `rebuild_candidate_context_at_recorded_ceiling`, `_build_selector_context`, `_build_context_batch`, `expand_candidate_context`, `_compile_context`, `_render_batch_payload`, `_capsule_is_intact`); `plan_tool/roadmap_candidate.py:_verify_bindings`; `plan_tool/roadmap_candidate_run.py` (`run_initial_candidate_proposal`, `_run_batch_candidate_proposal`, `_store_batch_candidate`, `_validate_candidate_evidence`, `_hydrate_capsule`, `_capsule_and_receipt_are_exact`, admission and evidence validators); `plan_tool/roadmap_candidate_review.py` replacement and expansion sites and the two ceiling validators; `plan_tool/prompt_budget.py` and the shell backstop; the full test diffs; `ROADMAP_FORMAT.md`; the changelog fragment; BACKLOG #469, #470 and the roll-ups; the BUG_BACKLOG entry.
- Sweeps: `CANDIDATE_CONTEXT_MAX_BYTES`, `ceiling_bytes`, `build_candidate_context`, `expand_candidate_context`, `_compile_context`, `is_supported_candidate_context_ceiling`, and the literals 192 KiB / 196608 / 64 KiB across `plan_tool/`, `tests/`, `docs/` (non-archive), and top-level `*.md`.
- Permission denials: none hit. I did not run programs or the test suite; the mutation claims below are by tracing. The arithmetic in BACKLOG #469 and #470 was recomputed by hand, not re-measured, so the Codex catalog figures and the argv measurement are unverified.

### Findings

#### 1. The "callers cannot override it" claim now has an undocumented public counterexample, and its pinning test cannot see it

- Category: documentation accuracy / contract
- Severity: Low
- Location: `plan_tool/roadmap_candidate_context.py:426-441`; `ROADMAP_FORMAT.md:1257-1259`; `tests/test_roadmap_candidate_context.py:486-490`
- Failure scenario: `ROADMAP_FORMAT.md` says "That module owns the ceiling: callers cannot override it". `rebuild_candidate_context_at_recorded_ceiling` is a new public function that takes a caller-supplied `recorded_ceiling_bytes` and compiles a capsule at it. Any caller can mint a brand-new capsule at 64 KiB or 192 KiB, with a valid digest, receipt and `_capsule_is_intact` result. The allowlist limits the values but not the purpose. The pin `assert "ceiling" not in inspect.signature(build_candidate_context).parameters` matches the exact name `ceiling`, so it never inspects the new function (`recorded_ceiling_bytes`). Today the only caller is `_verify_bindings`, so nothing is wrong in behaviour, but the contract sentence and its test no longer describe the surface.
- Suggested fix: either name the carve-out in the format paragraph ("the only caller-supplied ceiling is the one a stored capsule recorded, and only for reproducing that capsule"), or make the function take the stored capsule and read the ceiling itself. Add one test that pins the carve-out (for example, that the function's only caller in `plan_tool/` is `_verify_bindings`, or that it refuses an unsupported value, which is already covered).

- **Disposition:** fixed (documentation and pin only). `ROADMAP_FORMAT.md` now says the one caller-supplied ceiling is `rebuild_candidate_context_at_recorded_ceiling()`'s, that it accepts only a value the module has issued, and that it exists to reproduce a stored selector capsule; `tests/test_roadmap_format.py` pins both phrases. The function still has one caller, `_verify_bindings`; reading the ceiling from the capsule instead would be a signature change not needed for the contract.

#### 2. The motivating Integration scenario, a new batch hop at 384 KiB on a candidate stored under 192 KiB, has no end-to-end test

- Category: test coverage
- Severity: Low
- Location: `tests/test_roadmap_candidate_run.py`; `tests/test_roadmap_candidate_review.py:4650-4662`; `ROADMAP_FORMAT.md:1254-1256`
- Failure scenario: the format paragraph now asserts that "a new batch hop on a stored candidate uses the current ceiling", and the Integration unblock is exactly that case (active candidate `c886d0f2…` stored under 192 KiB, follow-up compiled at 384 KiB). The only tests that issue a batch capsule under a prior ceiling (`test_approval_without_removed_ids_is_unchanged`, `_run_batch` under 192 KiB) stop at approval. The new-ceiling batch tests in `test_roadmap_candidate_context.py` compile a context but never go through `_run_batch_candidate_proposal`. Nothing stores a batch candidate under 192 KiB, loads it as `active`, runs a second batch hop under the real constant, and checks the new candidate stores with `ceiling_bytes == 384 KiB` over a 192 KiB source. A later validator that compared source and hop ceilings, or recomputed the source against the current constant, would stay green. The format test only pins the prose.
- Suggested fix: add one run-level test: issue a batch candidate with the constant patched to 192 KiB, then run a second proposal unpatched, and assert outcome `stored`, the new candidate's `evidence.capsule.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES`, and that the source evidence is untouched.

- **Disposition:** fixed (test only). `test_a_new_batch_hop_over_a_candidate_stored_under_an_earlier_ceiling_uses_the_current_ceiling` stores a batch candidate under 192 KiB, runs a second hop under the real constant, and asserts it stores with the current ceiling, the source's bytes are unchanged, and the source still reloads at 192 KiB. It passed on first run, so the Integration case works end to end. Making the hop's receipt record the prior ceiling turns it red.

#### 3. BACKLOG #469 Verification lists checks the change does not perform, while Status says "implemented"

- Category: documentation accuracy
- Severity: Low
- Location: `BACKLOG.md:12859-12871` (Verification), `BACKLOG.md:12880-12881` (Status)
- Failure scenario: the Verification list says to "load `canonical-payload.json` (assert its SHA-256) as a fixture-shaped context and assert it is admitted under the new ceiling with every member, relationship, span, and reviewer item present", and to assert that "a context over the new ceiling still refuses before any invocation with no candidate/head mutation (stub invoker)". No test references `docs/evidence/integration-context-budget-2026-10-09/` (`grep` of `tests/` and `plan_tool/` finds nothing). The admitted-between-ceilings tests use synthetic 200 KiB inputs, and the over-ceiling tests are context-level (`test_over_budget_context_reports_complete_membership…`), not run-level with a stub invoker. A reader of the entry, or whoever removes it on merge, would take those assertions as done.
- Suggested fix: either mark the two checks as not performed (and why the synthetic inputs are the substitute), or add them: a hash-pinned replay test over the committed payload, and a run-level test that a context over the ceiling produces `refused` with `call_count == 0` and no stored candidate.

- **Disposition:** fixed (backlog text). #469's Verification now lists what was done: synthetic between-ceiling inputs for both routes, selector re-entry and expansion under both prior ceilings, the batch-hop case, and unsupported-value refusal. It states that `canonical-payload.json` is a rendered output and cannot be replayed, and that a run-level over-ceiling refusal test is not added because that path is unchanged.

#### 4. BACKLOG #470 "In scope" omits the `review.py` caller that also passes `context_window=None`

- Category: documentation accuracy
- Severity: Info
- Location: `BACKLOG.md:12901-12905` (#470 What and In scope); `plan_tool/review.py:9075-9077`
- Failure scenario: #470 scopes "the shell backstop and the existing `create` / `detail` / `launcher` callers that also pass `None`". `plan_tool/review.py:9075` calls `maybe_warn_prompt_budget(..., context_window=None, ...)` as well (the other five sites are `shell.py:463`, `create.py:1958`, `launcher.py:1747`, `detail.py:2977`). An implementer working from the entry would leave the review site on the 200K default and the fix would be a partial sweep of the class.
- Suggested fix: add `review` to the caller list, or say per site why it stays.

- **Disposition:** fixed (backlog text). #470 now lists nine `context_window=None` sites: `shell.py` 1, `review.py` 1, `create.py` 1, `detail.py` 3, `launcher.py` 3, found by grepping the literal across `plan_tool/`.

#### 5. The Codex harness figures in BACKLOG #469 do not reconcile for the 128 KiB cap

- Category: unverified measurement
- Severity: Info
- Location: `BACKLOG.md:12826-12834` (Harness baseline)
- Failure scenario: the entry reports 43,174 tokens with `project_doc_max_bytes` at 400,000 and 41,662 at 128 KiB. `CLAUDE.md` (the `AGENTS.md` symlink target) is 106,151 bytes, under both caps, so both runs should read the whole file and agree. They differ by 1,512 tokens, and the 128 KiB run implies a 22.5K-token file against 24.0K in the other. The conclusions (384 KiB, 64-73% of the effective window) are not sensitive to 1.5K tokens, but the entry presents both numbers as measured facts about the same file without noting the discrepancy, for example a different set of instruction files in the two runs or an edit to `CLAUDE.md` between them.
- Suggested fix: add one clause saying the two runs are not directly comparable (or re-measure both in one session).

- **Disposition:** fixed (backlog text). The 43,174 figure was taken on the 106,151-byte `CLAUDE.md`; the 41,662 figure on the evidence-split branch's 98,637-byte file. #469 now says so; the 1.5K difference is that 7.5 KB.

### Result

No Critical, High or Medium defect found. Five findings, all Low or Info: a contract sentence and its pin that no longer cover a new public entry point (1), one uncovered end-to-end case that is the motivating scenario (2), two backlog-text claims that outrun the code and tests (3, 4), and one unreconciled measurement (5).

Areas checked that hold:

- Every path that compares a stored selector capsule or receipt with a ceiling. The only rebuild site is `roadmap_candidate._verify_bindings`, which now uses `capsule.ceiling_bytes`. `expand_candidate_context` compiles at `capsule.ceiling_bytes` (initial and expansion). The run admission validator, the replacement state and evidence validators, `_capsule_and_receipt_are_exact` and `render_candidate_delta_prompt` read only the stored ceiling. `roadmap_candidate_review.py` and `roadmap_candidate_run.py` never read `CANDIDATE_CONTEXT_MAX_BYTES`. The current-constant consumers are exactly the new-issuance sites (`build_candidate_context`, the batch compile, the batch payload render, and the over-budget refusal).
- The allowlist. `type(value) is int` refuses `True`, numeric strings and `None`. Pydantic lax coercion could only produce an allowlisted int, and a mismatching payload then fails the exact re-render. A forged unissued ceiling reaches `_verify_bindings` as `invalid-capsule`. The batch-route consistency gap is the deferred BUG_BACKLOG entry and not re-reported.
- Mutation by tracing: reverting `_verify_bindings` to `build_candidate_context` turns red `test_reentry_of_a_lineage_stored_under_an_earlier_ceiling_survives_a_ceiling_raise` (both priors), `test_an_expanded_capsule_stored_under_an_earlier_ceiling_still_verifies_after_a_raise`, the forged-ceiling `_verify_bindings` test (it would report `invalid-bindings`), and the selector-era review and admission pin tests. Dropping either prior value from the allowlist turns red `test_every_issued_ceiling_is_supported`. Widening to 256 KiB or 512 KiB turns red the refused-values tests. Patches are scoped with `monkeypatch.context()` and the constant is read at call time, so they take effect.
- `ROADMAP_FORMAT.md` final paragraph: each of its four claims (earlier ceilings stay readable; selector capsules reproduce at the recorded ceiling; batch capsules are verified by digest and receipts and never re-rendered; each new context uses the current ceiling) matches the code. The pinning test's substrings appear after whitespace normalization.
- BACKLOG arithmetic recomputed: 15,104 bytes (7.7%) over; 50,432 bytes and 81% at 256 KiB; the prompt fit (75.4 KB plus payload plus 0.3485 of payload) gives about 605 KB at 384 KiB; 4.13 bytes per token; 147K tokens and 64-73% of the 258.4K effective window; 512 KiB at 81-90%; warning thresholds 420 KB and 595 KB from `WARN_HEADROOM_RATIO` 0.40 and `HIGH_HEADROOM_RATIO` 0.15 at 3.5 bytes per token; the Codex lane reading `warn` (173K of 272K is 63.6% used). The roll-up and #469 Quality lines no longer argue from a 1M-token model.
- The changelog fragment matches the behavior. No `192 KiB` or `196,608` statement presented as current remains outside evidence, tests and the backlog's dated history. Commit messages in range carry no attribution lines.

## Convergence status

Converged, 2026-10-09. The logic head is `c66f7361` and has not changed since. Pass 2 (four Low, one Info) and pass 3 (three Low, two Info) are two independent consecutive low-yield passes against it, with no new material correctness or completeness issue in either; every finding of passes 1 to 3 has a disposition. Everything after `c66f7361` is documentation, backlog text, tests and test comments, which does not reset the logic window. Pass 3's one substantive probe, the new batch hop over a 192 KiB candidate, passed when written. The loop stops here; no pass 4 is launched.

Open follow-ups, none blocking: the deferred batch-ceiling consistency gap (`BUG_BACKLOG.md`, ROADMAP section), BACKLOG #470 (budget warning window) and #471 (relation compaction), and the Linux per-argument limit, unverified.
