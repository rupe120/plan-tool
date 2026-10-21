# Detail deferrals-envelope repair — code review ledger

## Summary

| Field | Value |
| --- | --- |
| Change | `plan-tool detail` retries a reply whose Markdown body parses but whose trailing `<!-- plan-tool-detail-deferrals … -->` envelope is missing or has invalid JSON with an envelope-only `## Repair` prompt, instead of regenerating the whole file. Direct change (no plan). Source entry: the `BUG_BACKLOG.md` entry filed at `f514cb07` and removed at `8491289f`. |
| Review range | `f514cb07..8491289f` |
| Code commit | `89dd8ce9` (`plan_tool/detail.py`, `tests/test_detail.py`) |
| Backlog commit | `8491289f` (removes the source entry) |
| Current head | `8e6e2bdb` (pass-1 fixes: `e7e99999`, `6e0c3095`; pass-2 fixes: `c15063fc`, `8e6e2bdb`) |
| Checks run | `uv run pytest tests/test_detail.py tests/test_duplication.py -q -n auto`: 639 passed. After the pass-1 fixes: full suite `uv run pytest tests/ -q -n auto` 13985 passed, 189 skipped. Final: full suite passed (log: `.tmp/detail-envelope-repair.final-suite.log`). |
| `/code-review` | Pass 1 (`high`, report-only, `f514cb07..HEAD`): 7 findings. Pass 2 (`high`, report-only, `8491289f..518cb087`): 3 findings. Pass 3 (`high`, report-only, `518cb087..8b3aec90`): clean, 0 findings. The review produced no severity or `[CONFIRMED]`/`[PLAUSIBLE]` tags. |
| Current disposition | **Converged (2026-09-25).** Pass 3 is clean; see § Convergence status. |

## Settled decisions (hand these to every reviewer)

These come from the source backlog entry's Fix and its "Deliberately not included" list.

- **Scope of the repair branch.** It applies only when the body parses and the envelope is missing or its JSON is
  invalid. Every other failure keeps today's full regeneration.
- **The repair asks for the envelope only,** in `create.py`'s `## Repair` shape (original prompt, rejection reason,
  rejected reply). The joined text is validated through `parse_structured_detail_response` with step, plan, and bucket
  context, and the joined text is the checkpoint payload so replay passes the envelope check.
- **Deliberately not included** (a finding proposing one is invalid, not deferrable):
  - a deterministic auto-append of an empty envelope, because the envelope exists so the model states its deferrals
    explicitly;
  - resubmitting the full reply for missing sections;
  - the jira-grade path, the `review.py` plan-audit retry, and the roadmap retries;
  - any change to `_MAX_INVOKE_ATTEMPTS`.
- **Provenance note.** The source entry was `evidence-gated` (build once envelope-only failures show up in three more
  parse-failure dumps). The change shipped ahead of that gate by the owner's direct decision; reviewers judge the fix on
  its merits, not the gate.

## Findings

Severity and CONFIRMED/PLAUSIBLE tags were not produced by the review.

### Pass 1 (`f514cb07..HEAD`)

- **P1.1 — Repair reply must start with the marker at offset 0** (severity not recorded): the envelope-only repair check is
  stricter than the normal parse, so a fenced or preamble-prefixed repair reply fails, both attempts are spent, and the
  step fails where a full regeneration might have recovered. **Disposition:** declined — the strict reply is the
  contract: `test_invalid_envelope_repair_exhausts_existing_retry` pins the rejection on purpose, the source entry
  requires that "a repair reply that is still invalid fails with today's error", and a fallback needs a third attempt,
  which the settled decisions exclude. Known trade-off; revisit only if parse-failure dumps show it.
- **P1.2 — Repair chosen for a body whose `## Deferred` section names concept ids** (severity not recorded): repair is
  chosen although the envelope-required validator could reject the body, so a `{"deferrals":[]}` reply would fail
  permanently. **Disposition:** refuted — the repair prompt carries the rejected reply, so the model can restate the
  concept ids the body names; the scenario assumed an empty envelope. `test_repair_reply_can_state_deferrals_named_in_the_body`
  pins a repairable body that names a bucket id.
- **P1.3 — Body silently truncated at an unfenced marker-like line** (severity not recorded): with an unfenced marker-like
  line in the body and no valid trailing envelope, the body was cut at the last marker and the remainder dropped, so
  repair could write a file that silently lost later sections. **Disposition:** fixed e7e99999 —
  `_body_for_deferrals_repair` returns `None` (full regeneration) unless the last marker opens one comment that runs to
  end-of-text (`_DETAIL_DEFERRALS_COMMENT_TAIL_RE`); `test_marker_quoted_in_body_uses_full_regeneration_not_truncation`
  goes red when the guard is disabled (mutation-checked).
- **P1.4 — `rejected_raw` / `repair_body` lifecycle depends on `attempt == 1`** (severity not recorded): `rejected_raw`
  was bound only on the repair path, a latent `UnboundLocalError` and stale-state risk if the loop guard changes.
  **Disposition:** fixed e7e99999 (binding only) — `rejected_raw = ""` is bound next to `repair_body`; the attempt-3
  reuse scenario is unreachable because `_MAX_INVOKE_ATTEMPTS` stays 2, so the loop guard is not widened.
- **P1.5 — Repair-prompt budget block duplicates the initial pre-send block** (severity not recorded): the two copies can
  drift and a repair warning prints a second advisory. **Disposition:** fixed e7e99999 — one local
  `_measure_prompt_budget` serves both measurements; `budget_covered` semantics are unchanged.
- **P1.6 — `DETAIL_FORMAT.md` still describes the old retry** (severity not recorded): the doc claimed every rejected parse
  retries with `_REPROMPT_SUFFIX`, contradicting the `## Repair` path. **Disposition:** fixed 6e0c3095 —
  `DETAIL_FORMAT.md` § retry names the `## Repair` exception; a sweep by identifier (`_REPROMPT_SUFFIX`) and vocabulary
  (retry, rejected parse, invoke attempts, regenerat*) found no other live restatement (`DETAIL_FORMAT.md:158` concerns
  the marker slot and stays true).
- **P1.7 — Rejected-attempt `raw` is no longer structural-stripped** (severity not recorded): on a parse failure `raw` stays
  unstripped and only `parsed_raw` is stripped, so the parse-failure dump and `raw_bytes` now include a volunteered
  Structural findings block. **Disposition:** declined — the unstripped reply is what a parse-failure dump exists to
  record; an accepted attempt's payload is unchanged (`raw = parsed_raw` on success); no test pins the old stripped dump.

### Pass 2 (`8491289f..518cb087`)

- **P2.1 — A cut-off envelope now gets full regeneration, not repair** (severity not recorded): a truncated or
  unterminated envelope comment fails `_DETAIL_DEFERRALS_COMMENT_TAIL_RE.fullmatch` (introduced by the P1.3 fix), so the
  token-heavy path runs; the docs said "missing or invalid JSON" and no test pinned it. **Disposition:** fixed c15063fc,
  8e6e2bdb — full regeneration is the deliberate answer: accepting an unterminated tail would reopen P1.3's
  silent-truncation hazard, and a cut-off reply is the less trustworthy reply. The regex comment, `DETAIL_FORMAT.md`
  § retry, and `test_cut_off_envelope_uses_full_regeneration` (mutation-checked) now say so.
- **P2.2 — Malformed repair reply has no fallback to full regeneration** (severity not recorded): same as P1.1, plus a
  claim that no test covers a malformed repair reply. **Disposition:** declined — duplicate of P1.1 (strict reply, no
  third attempt, both settled); the "no test" claim is refuted: `test_invalid_envelope_repair_exhausts_existing_retry`
  pins a non-envelope reply and a preamble-prefixed one, and a fenced reply takes the same `_find_real_deferrals_match`
  path.
- **P2.3 — No-marker repair can finalise a one-section-stubbed body** (severity not recorded): a body missing exactly one
  required section, with no envelope, is repaired and written with a stub placeholder instead of regenerated.
  **Disposition:** refuted — auto-stubbing exactly one missing section is the documented rule (`DETAIL_FORMAT.md` rule 4)
  and the same body with an envelope is accepted stubbed today, so repair is no more lenient than the ordinary parse;
  P1.3 differed because the tool itself removed model-authored text.
  `test_repair_keeps_the_one_missing_section_stub_an_enveloped_reply_gets` pins the parity.

### Pass 3 (`518cb087..8b3aec90`)

- _(no findings)_ — the review read the diff, ran the 10 selected envelope tests (passed), and confirmed that the
  cut-off-envelope comment, `DETAIL_FORMAT.md`, and `test_cut_off_envelope_uses_full_regeneration` agree, that the
  no-marker branch keeps stub parity, and that the malformed-repair-reply rejection is pinned. Nothing is pending.

## Out-of-range / recall-mode findings

_(none)_

## Convergence status

- **Rounds run:** 3.
- **State:** **converged (2026-09-25).** Two consecutive rounds qualify: pass 2 added no new material correctness or
  completeness finding (P2.1 was a coverage gap left by the P1.3 fix and is now pinned; P2.2 repeated the settled P1.1
  trade-off; P2.3 was refuted), and pass 3 was clean. The loop stops; no further review pass runs.
- **Checks at the end:** `uv run pytest tests/ -q -n auto` passed (log: `.tmp/detail-envelope-repair.final-suite.log`).
- **Open trade-off, deliberately kept (P1.1, repeated as P2.2):** a malformed repair reply (fenced, or with a preamble)
  fails the step where a full regeneration might have recovered it. The settled decisions exclude a third attempt, and
  a test pins the rejection. Revisit only if parse-failure dumps show it happening.
- **Not done here:** the backlog entry's evidence gate (three more envelope-only failures) was bypassed by the owner's
  direct decision; nothing further is filed.
