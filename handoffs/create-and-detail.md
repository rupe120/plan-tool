# Create, detail and plan files

Seeds, step descriptions, concept sync, detail authoring and plan-file preservation. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Detail deferrals-envelope repair — code review ledger](#detail-deferrals-envelope-repair--code-review-ledger) | 2026-09-25 |
| [Leftover top-level 0N-*.md warning — review ledger](#leftover-top-level-0n-md-warning--review-ledger) | 2026-10-10 |
| [Multi-line finding bullets — review ledger](#multi-line-finding-bullets--review-ledger) | 2026-10-10 |
| [Unpublished seed overwrite — review ledger](#unpublished-seed-overwrite--review-ledger) | 2026-10-10 |
| [Concept-sync H1 boundary preservation](#concept-sync-h1-boundary-preservation) | 2026-10-22 |
| [Plan body newline preservation](#plan-body-newline-preservation) | 2026-10-22 |
| [Scope-out rollback ownership](#scope-out-rollback-ownership) | 2026-10-22 |
| [New-seed default placement](#new-seed-default-placement) | 2026-10-22 |
| [Step description alias: implementation review ledger](#step-description-alias-implementation-review-ledger) | 2026-10-22 |
| [Step description diagnostic repair](#step-description-diagnostic-repair) | 2026-10-22 |
| [Detail empty-heading refusal: code review ledger](#detail-empty-heading-refusal-code-review-ledger) | 2026-11-13 |
| [Files-coherence extensionless Dockerfile: code review ledger](#files-coherence-extensionless-dockerfile-code-review-ledger) | 2026-11-13 |
| [Multiline concept decisions: code review ledger](#multiline-concept-decisions-code-review-ledger) | 2026-11-13 |

## Detail deferrals-envelope repair — code review ledger

*Opened 2026-09-25.*

### Summary

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

### Settled decisions (hand these to every reviewer)

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

### Findings

Severity and CONFIRMED/PLAUSIBLE tags were not produced by the review.

#### Pass 1 (`f514cb07..HEAD`)

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

#### Pass 2 (`8491289f..518cb087`)

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

#### Pass 3 (`518cb087..8b3aec90`)

- _(no findings)_ — the review read the diff, ran the 10 selected envelope tests (passed), and confirmed that the
  cut-off-envelope comment, `DETAIL_FORMAT.md`, and `test_cut_off_envelope_uses_full_regeneration` agree, that the
  no-marker branch keeps stub parity, and that the malformed-repair-reply rejection is pinned. Nothing is pending.

### Out-of-range / recall-mode findings

_(none)_

### Convergence status

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

## Leftover top-level 0N-*.md warning — review ledger

*Opened 2026-10-10.*

| Field | Value |
| --- | --- |
| Change | BUG_BACKLOG "Roadmap-derived plans cite bare `0N-*.md` names" part 2: a stderr warning names inert top-level `0N-*.md` files beside an accepted head |
| Branch | `fix/stale-0n-roadmap-citations` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

### Settled decisions

- Warning only; never an exit-code or rendered-output change. Existence check only, never a read.
- Silent without an accepted head (the no-published-version refusal already names the files).
- Part 1 (draft seeds cite the accepted version) stays in BUG_BACKLOG, route plan.

### Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Warning missing on the routes that hand a seed to `create` | **Fixed in part.** Added to `--accept-seed` and `--apply`. **Declined** for `create --from-existing <seed>`: a different module, and part 1 removes the bare name there. Recorded in the entry |
| 2 | `.roadmap-versions` hard-coded | **Fixed.** `version_namespace_path` |
| 3 | The existence scan written twice | **Fixed.** One `leftover_top_level_artifacts`; the tuple is private again |
| 4 | Materialize test claims an ordering it does not pin | **Fixed.** Renamed to the route it covers; accept/apply routes pinned by a parametrized test |
| 5 | Singular/plural grammar | **Fixed**, asserted by exact phrase |
| 6 | Undated history in the backlog entry | **Fixed.** Dated 2026-10-10 |

Process note: the foreground full-suite run beside a background review hit one load-sensitive failure in `tests/cli/test_direct_cmd.py::test_direct_jira_relocated_root_preexisting_dirt_aborts_before_detail`; it passes alone and in the clean runs. Not changed.

## Multi-line finding bullets — review ledger

*Opened 2026-10-10.*

| Field | Value |
| --- | --- |
| Change | BUG_BACKLOG "A completeness report puts a finding's multi-line body on its bullet without indenting it": every finding bullet indents its continuation lines under the bullet |
| Branch | `fix/multiline-report-bullets` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

### Settled decisions

- One helper, `review.indent_bullet_body`, beside `confidence_label`. Fence delimiter lines (found by `jira_grade.fenced_spans`, the repo's one scanner) are set to the bullet's margin; every other continuation line is dedented by their common margin, so relative indentation inside a fence survives. Blank lines stay empty; the cited text is never rewritten or escaped.
- One bullet formatter, `completeness_report.format_finding_bullet(rec, key)`, serves the two `_fmt_*` functions and the six grouped-report buckets, so the bullet shape changes in one place.
- An applied-outcome bullet whose body is multi-line carries its note and confidence on their own line, so text is never appended to a closing fence.

### Class enumeration

Class: a finding body rendered onto a markdown bullet (or a bullet inside a model prompt) without continuation indentation. Searched by identifier (`rec.body`, `.body.strip()`, `{body}`) and by vocabulary (`- {...}` bullets built from findings).

| Site | Disposition |
| --- | --- |
| `completeness_report._fmt_finding_line`, `_fmt_pending_line` | Fixed, via `format_finding_bullet` |
| `completeness_report` applied-outcome bullet | Fixed (note on its own line) |
| `completeness_phases._render_grouped_report` x6 | Fixed, via `format_finding_bullet`; each site reverted in turn turns a test red |
| `review._render_extract_lessons_prompt` | Fixed (round 1 finding 2; the first enumeration missed it because the body is `.strip()`ed inline) |
| `cli/inspect.py` `validate` console `_emit` | Stays: terminal print, not a markdown list |
| `detail.py` audit print | Stays: collapses the body to one line already |

### Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | A fence indented 4+ spaces beside a column-0 line is pushed to 6+ and reads as an indented code block | **Fixed.** Fence-aware via `fenced_spans`; mixed-margin and `~~~` cases pinned; an unclosed fence's last line stays content |
| 2 | The extract-lessons prompt builder is the same class and was not swept | **Fixed**, pinned by `test_review_lesson_prompt_keeps_a_multiline_body_inside_its_list_item` |
| 3 | Comments still argue "one or two sentences, body sits inline" | **Fixed.** Both comments rewritten |
| 4 | Nine hand-edited formatter sites | **Fixed.** One `format_finding_bullet` |
| 5 | Applied bullet keyed on "multi-line" with a nested conditional | **Fixed.** Explicit if/else; the multi-line rule is documented in place |
| 6 | Import order and line width | **Fixed.** The helper moved out of `completeness_report.py`, taking `textwrap` with it |

Process note: reverting a mutation with `git checkout <file>` discarded the file's uncommitted fixes. Restore mutations from a saved copy, and commit before mutating.

## Unpublished seed overwrite — review ledger

*Opened 2026-10-10.*

| Field | Value |
| --- | --- |
| Change | BUG_BACKLOG "`--refresh-seeds` and `--accept-seed` overwrite an existing `plan-seeds/` file for a seed that was never published": refresh and accept rewrite a promoted copy only when the seed state records `published: true` |
| Branch | `fix/seed-overwrite-unpublished` |
| Review range | `c4c936029..HEAD` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

### Settled decisions

- The recorded `published` flag is the only publication proof, for apply, refresh, and accept (`_seed_recorded_published`). An existing destination or a same-named archive is not proof: it may be hand-written or another roadmap's.
- An unpublished seed's existing `plan-seeds/` file is left untouched, not refused; `--apply` still refuses it as a collision.

### Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `--apply` links copies before recording `published`; a failure between leaves an unrecoverable file the tool wrote | **Filed** in BUG_BACKLOG (with 2). Accepting the in-file marker as proof needs a new parser; the window is narrow |
| 2 | `--accept-seed` writes the sidecar before the promoted copy | **Fixed in the follow-up branch `fix/accept-seed-write-order`** (copy first, sidecar second; `test_accept_failed_copy_write_leaves_the_draft_re_acceptable`). Pre-existing order, not introduced by this change |
| 3 | The flag rule is hand-copied at three sites | **Fixed.** `_seed_recorded_published` |
| 4 | Refresh reads and reports an unpublished seed's foreign `plan-seeds/` file (non-UTF-8 aborts refresh) | **Fixed.** Targets drop the promoted path unless recorded published; pinned by `test_an_unpublished_seeds_plan_seeds_file_is_neither_read_nor_reported`, red under mutation |
| 5 | Module docstring and ROADMAP_FORMAT.md still state the unconditional rule | **Fixed** |
| 6 | The skip prints nothing | **Fixed.** Accept names the untouched file and why; pinned by a CLI test, red under mutation |
| 7 | No refresh-route test | **Fixed** with 4 |

Mutation: restoring the old predicates turns the three round-0 tests red; dropping the target filter and the message turns the two round-1 tests red.

### Follow-up review: accept write order (`fix/accept-seed-write-order`)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `--accept-seed` hard-codes `status: current`, so accepting a hand edit of an invalidated seed clears the invalidation | **Filed** (BUG_BACKLOG, decision-needed). Pre-existing (`bf3a546b3` already hard-codes it); whether a hand edit after invalidation counts as re-review is a design call |
| 2 | A failed copy write surfaces as a bare `OSError` with no retry hint | **Fixed.** Wrapped in `RoadmapError` stating nothing was recorded and re-running is safe |
| 3 | The recovery test checks retry only, not that the sidecar is byte-identical; the mirror failure is untested | **Fixed.** Bytes asserted unchanged; `test_accept_failed_sidecar_write_after_the_copy_is_re_acceptable` added |
| 4 | This ledger listed finding 2 as filed | **Fixed** (row above) |

## Concept-sync H1 boundary preservation

*Opened 2026-10-22.*

| Item | Record |
| --- | --- |
| Base | `702c767c8`, merged PR #144 |
| Branch | `fix/concept-sync-h1-boundaries` |
| Scope | BUG_BACKLOG “Concept sync deletes an unowned H1 after an owned H2” |
| Route | Bounded parser boundary correction |
| Current state | Complete: 15,118 tests pass; two independent final clean Claude Code reviews |

### Property and pre-edit sites

Invariant: replacing an owned H2 body stops at the same real H1/H2 boundary as reading it, preserving every unowned slice including H1 headings and content. Keep existing raw LF/CRLF/CR offsets and opt-in fence semantics.
Identifier search: replace_body_sections is consumed by concept_sync.synchronize_concepts only; parse_body_sections supplies its owned-section comparisons. parser._real_h2_matches selects replaceable headings, while parse_body_sections's higher_matches supplies H1/H2 body ends. Tests mirror parser and concept_sync.
Vocabulary search: H1/H2, boundaries, unowned, fenced in parser/concept_sync and their tests confirms that the reader ends at H1/H2 but replacement ends only at the next H2. Share the reader's existing boundary matcher with replacement; preserve its whitespace semantics and source offsets rather than add another recognizer.
Excluded: concept decision rendering/ownership, plan/frontmatter serialization, publication/rollback, scope selection, append policy and broader Markdown parsing. No change to the default opt-in fence behavior or unmatched-fence policy.

The reader's existing matcher is shared with replacement. H2 selection,
normalization, default fence behavior and owned-section rendering stay the same.
Replacement uses original source slices around H1/H2 boundaries; no text
normalization is added.

### Verification

Before the fix, **23 new cases fail** across LF/CRLF/CR: H1 content between
owned sections and at EOF, empty/whitespace boundary forms, explicit fence opt-in,
and actual concept-sync publication with or without concurrent unowned edits.
Raw output assertions prove the unowned bytes survive while fenced pseudo-H1
content inside an owned section is replaced. Sync tests check the selected
step scope and the persisted fingerprint against the actual published bytes.

After correction, **516 affected tests pass** in 0.82s (parser, concept sync and
scope-review CLI). Existing owned-edit refusal and unmatched-fence tests stay
green. No new model call, publication behavior or Markdown policy is introduced.

Full suite: **15,118 passed, 67 skipped** in 76.67s. Diff whitespace check
passes. Production change: `d5991b6cd`.

### Claude Code review 1

Range `702c767c8..d5991b6cd3091255fa9fb7e8515b3c3bafea0c0d`;
actual built-in `code-review` Skill at high effort plus independent verification.
Session `38829ab4-68c2-4791-84d2-3bc97f3874b8`.
Clean: no introduced or in-scope invariant failure. The reviewer runs **516
affected tests** in 0.80s and a broader selection with 580 passes. It compares
old/new implementations on 11 body shapes in both fence modes, confirming
H1 preservation and unchanged reader/H2/append semantics. It does not reproduce
the author's 23-case pre-fix failure count; the session-owned run above does.

Six candidates are checked. Owned rendering with LF, performance suggestions,
helper defaults, the deliberately retained whitespace pattern and a separate
detail-schema reader do not require changes. The unescaped multiline decision
text concern is a real, pre-existing rendering issue: the session independently
runs actual sync with `why\n# Injected heading\nmore rationale`, observes success,
and confirms the Deferred body is only `- Delayed — why`. BUG_BACKLOG
“Multiline concept decisions can create document headings outside their owned
section” owns the follow-up. This repair does not expand into rendering/schema
policy. The reader's original inline regex/filter is extracted unchanged.

### Claude Code review 2 and convergence

Range `702c767c8..9a9c850007528b2d5262938cdb1e6bc1b3f0cdec`;
actual built-in `code-review` Skill at high effort plus independent verification.
Session `611c2e03-f2c9-4205-a302-801b495982de`.
Clean for the bounded fix, with no introduced/in-scope invariant failure and an
explicit low-yield advisory tail. The reviewer independently runs the full suite:
**15,118 passed, 67 skipped** in 89.40s. Its parser/concept-sync/scope-review/
duplication suite passes **526 tests** in 4.11s. Side-by-side old/new probes
cover seven hand-built bodies in both fence modes. Of 30,000 generated bodies,
8,279 qualified LF/CRLF/CR cases produce zero reader/writer parity or unowned
section preservation violations. The reviewer does not independently replay the
23-case pre-fix count; that evidence remains the session-owned run above.

Advisory dispositions:

- A1, a proposed additional section-end helper, is declined as unnecessary
  abstraction. The high-risk regex/filter is shared. The reader retains a
  matching object before taking its offset; the writer retrieves an offset
  directly. Neither lookup diverges today, and no exact duplicate function is
  introduced (the duplication guard passes). No consolidation is claimed or
  folded into the repair.
- A2, the in-progress handoff headline, is updated on completed review here.
- Owned LF rendering, the deliberately retained whitespace matcher, explicit
  fence opt-in and globally selected owned H2 names are current pinned policies,
  not new defects. Selecting an owned-named H2 below an H1 remains the same
  ownership policy; hierarchy-aware selection would require a separate scope
  decision, not a bug fix inferred from this review.

Reviews 1 and 2 are two independent clean final passes after the sole production
change `d5991b6cd`; only evidence/backlog/changelog records follow. The original
H1-loss backlog item is removed after completed verification and review. The
separate multiline concept-rendering defect and create-helper investigation
remain. Diff whitespace is clean, and all work is committed locally.

## Plan body newline preservation

*Opened 2026-10-22.*

| Item | Record |
| --- | --- |
| Base | `75aa0a7e5`, merged PR #142 |
| Branch | `fix/plan-body-newline-preservation` |
| Scope | BUG_BACKLOG “Concept sync and scope-out rollback normalize existing plan body newlines” |
| Route | Bounded direct I/O and heading-boundary correction |
| Current state | Complete: 15,068 tests pass; two consecutive independent clean Claude Code reviews after the final logic change |

### Settled decisions

Invariant: concept synchronization retains unowned body bytes, and failed narrowing restores the original plan bytes and matching provenance.

- Raw UTF-8 reads and a newline-translation-free atomic publisher at every site that republishes original plan bytes: concept_sync's current source, create's two snapshots, scope_review_cmd's snapshot, scope_out's `original_plan_text` snapshot and restore. `compute_frontmatter_hash` hashes the same raw frontmatter as parser provenance.
- Parser `_real_h2_matches` and `parse_body_sections` use CR-aware offsets; unowned slices are preserved, not normalized.
- Excluded by design: sidecar JSON reads, seed/detail/reference reads (they do not republish plan bytes), read-only normalization, scope selection, archive moves, publication ownership.
- Mixed owned-section endings and canonical LF frontmatter are permitted output. Raw frontmatter hashes deliberately invalidate newline-only stale narrowing previews. Helper extraction is a preference, not applied.

### Verification

- Before the fix (dated 2026-10-22): six raw-byte regressions fail (four concept-sync CRLF/CR combinations with and without source snapshots; two rollback cases after real plan publication); LF controls pass.
- Affected module suite 1,733 tests pass, including the real scope-review handler, scope-out sidecar-save failure after publication, and both create snapshot seams; assertions inspect bytes, owned-section replacement, fences, concurrent owned/unowned edits, fingerprints, restored details and provenance. Four further cases (successful narrowing keeps raw body bytes; newline-only frontmatter change invalidates a stale preview) pass in the 605-test parser/scope-out run.
- Implementation commits: `c80e96dad` (concept sync, source snapshots, raw heading boundaries), `778fabcdd` (scope-out snapshots, restoration, CAS). Final production logic `35173d3f8`; full suite **15,068 passed, 67 skipped**. `git diff --check` passes.

### Findings

Review 1, range `75aa0a7e5..778fabcdde4dffb78e48f82d305eb896d76abbcf`, built-in `code-review` Skill at high effort, session `5b24ca95-9688-4811-aa2c-38e42bd6fda9`.

- F-1 fixed `35173d3f8`: narrowing higher-heading whitespace changed existing empty/non-ASCII boundaries; nine new cases failed before the fix; original `\s+` semantics restored while keeping raw CR/LF anchors (all 1,746 affected-module tests pass).
- F-2 tracked BUG_BACKLOG “Concept sync deletes an unowned H1 after an owned H2”: pre-existing; H1 content after an owned H2 is deleted (reproduced for LF/CRLF/CR).
- F-3 tracked BUG_BACKLOG “Scope-out rollback overwrites the concurrent edit rejected by provenance”: pre-existing; an injected concurrent priority edit raises ConcurrentModificationError but unconditional rollback overwrites it. Data loss despite the review's low-severity label.
- Import-order nit fixed (`35173d3f8`).
- EOF and repeat-sync coverage suggestions: declined, advisory; no reproduced defect.

Review 2, range `75aa0a7e5..35173d3f8ecf52a53f1b568a96659d48ba7b76c4`, session `338eec86-3699-49d0-9dd6-2578d9d7cd5f`: clean for introduced defects. Differential probes against the previous LF parser (80,000 cross-ending, 40,000 LF cases) show zero mismatches; replacement is idempotent. Seven raw recommendations checked: owned/frontmatter LF allowed (declined); read-only normalization excluded (declined); F-2/F-3 stay tracked; raw CR line starts reproduce prior universal-newline behavior (refuted as defect). The separate create body patch/References helpers still use normalizing I/O: tracked in BUG_BACKLOG for investigation (no public-path reproduction claimed).

Review 3, range `75aa0a7e5..82ab0765977cdafb95358357ba4431047962de9a`, session `84af0abf-87f1-44e1-ba73-0635e245ecfd`: clean for introduced defects. 1,746 tests pass; raw-prefix/suffix and missing-section append probes preserve bytes; a 5,000-sequence parser differential finds zero mismatches. Eight recommendations: F-2/F-3 and create patch helpers tracked; mixed owned sections and LF frontmatter declined (allowed); trimming CR/LF section-edge terminators refuted (restores prior translated semantics); raw frontmatter hashes declined (deliberate); helper extraction declined (preference).

### Closure

Reviews 2 and 3 are two consecutive independent clean reviews after final logic `35173d3f8`; only evidence, changelog and backlog records follow it. The original newline-normalization entry is removed after verified completion; three separately scoped follow-ups remain tracked (F-2, F-3, create patch helpers). The changelog describes only the normalization repair; it does not claim the H1-deletion or concurrent-rollback defects are fixed.

## Scope-out rollback ownership

*Opened 2026-10-22.*

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

### Settled decisions

- Invariant: a failed narrowing restores only its own published plan/concept bytes, preserves other edits, and reports incomplete recovery. Publication failure leaves no unidentified partial canonical plan write.
- Mechanism: an optional publisher seam on `parser.write_plan` and `concept_tree.save_concepts` hands the exact validated payload to `scope_out.apply_narrow`, whose local publisher rechecks the live frontmatter/body or sidecar preimage, records a receipt, and writes via the existing durable `fileio.atomic_write_bytes`. Rollback compares receipts before each restore, attempts all independent undos, and collects errors. Plan provenance refreshes only for verified restored bytes. Sidecar snapshots are raw bytes; other callers keep default behavior.
- The detail journal's undo also refuses an occupied destination (a reproduced conflict otherwise overwrites a new detail file) and continues all inverse operations while returning failures. Forward archive/scope selection is unchanged.
- Boundary: guarded recovery, not a lock. A writer racing inside the comparison/replace interval is not serialized; no cross-process transaction guarantee is claimed (stated in ARCHITECTURE). Excluded: unrelated concept-sync publishers, archive and scope selection, seed generation, schema/alias semantics, cross-process locking.
- A body edit observed before serialization is kept by recovery rather than reverted.

### Verification

- Before the fix, seven plan/sidecar concurrency regressions and a detail-undo collision regression fail; no existing test pinned the overwritten edit as intended.
- Affected suite 671 passed (scope-out, parser, concept tree, atomic I/O), covering custom publisher gates, LF/CRLF/CR restoration, before/after publication failures, concurrent change/deletion, provenance and detail recovery. One test premise was wrong (a lone step with id 2 is valid) and now uses duplicate ids, rejected before publication. Full suite then 15,088 passed, 67 skipped in 65.08s.

### Findings

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

### Closure

**Converged (low-yield):** reviews 3 and 4 are two consecutive independent clean final passes after `bcf3b8bb7`; only documentation/evidence follows. Their verdicts retain the no-lock/metadata residuals and the operator-inspection requirement rather than implying a filesystem transaction. The original backlog item is removed after completed verification and review. The separate H1-deletion and create-helper investigations are untouched. No tracked or pending items remain.

## New-seed default placement

*Opened 2026-10-22.*

| Item | Record |
| --- | --- |
| Base | `330441789`, branch `fix/seed-default-location`, independent of PR #136 |
| Intent | New seeds default to `docs/implementation-plans/plan-seeds/`; existing seed files stay at their current paths; both directories get an explanatory README |
| Reviews | Three Claude Code `/code-review` passes (built-in skill, high effort, Sonnet 5.5): ranges `330441789..562820563`, `..808c80e03`, `..f08c6190f`; reports `.tmp/seed-default-location.review-N.md` |
| Closure | **Low-yield convergence**, not zero-findings clean: reviews 2 and 3 are consecutive independent passes with only low/advisory findings after the last placement/collision logic change (`f53201887`) |
| Checks | Full suite at `f08c6190f`: 14,717 passed, 67 skipped in 55.00s; after merging main `176ce30a5` (merge `42922cdc0`): 14,717 passed, 67 skipped in 74.19s; `git diff --check` clean |

### Settled decisions

- `seed_paths.py` is a stdlib-only placement leaf. Scope-out (single/region), reground, roadmap promotion and annotate share the nested default. Explicit annotate output/seed destinations stay authoritative and its report default stays beside the source; `create --from-existing` keeps explicit path semantics.
- Existing roadmap publications keep root placement, even if archived or absent. New promotions persist optional `publication_layout: nested`; a missing layout means legacy root. Normalization validates the closed root/nested vocabulary, accept/materialize rewrites preserve it, and refresh/apply-skip follow the recorded destination, not folder existence. Presence of an unpublished file never grants publication ownership.
- Not shipped: seed migration, configurable directory. BACKLOG #184 keeps project-level configuration as separate future work and its former root-default assumption is superseded by this user-directed change. CLAUDE.md changes only the seed authoring path (architect-tier PR review required). PR #136 owns iteration guidance and is not absorbed here.
- The live root-seed preflight excludes `README.md`; no existing seed is renamed, deleted or rewritten. Site enumeration: `.tmp/seed-default-location.sites.md`.
- Validation evidence: mutation reverting the nested constant fails the new-default invariant; forcing legacy publications into the nested folder fails all legacy-placement cases and the legacy accept/apply-skip tests; a parametrized root/nested test leaves the other same-named file byte-identical; layout roundtrip/invalid/malformed-field tests pin persistence and fail-closed parsing.

### Findings

| Review | Finding | Disposition |
| --- | --- | --- |
| 1 | Medium: shared annotate output can overwrite a different same-named source | fixed: default output refuses an existing seed before backend invocation and uses exclusive creation at write time; same-stem batches fail preflight; explicit destination replacement stays compatible. Tests cover pre-existing files, concurrent creation, same-stem batches, explicit replacement; truncating-write mutation fails the concurrent-file test. Full suite 14,714 plus one intentional help-snapshot mismatch, regenerated |
| 1 | Low-medium: authoring docs still direct new seeds to root | fixed: TRACKING recipes, starting-point/demo guides, capability summary and contributor routing use the nested default; roadmap contract names publication layout; existing references unmoved |
| 1 | Low: accept preview ignores an unrelated root file for an unpublished seed | declined: the nested default is the collision destination; the root file is neither owned nor a collision |
| 1 | Low: import grouping, long strings | fixed (import grouping); path literals kept explicit, no abstraction |
| 1 | Info: target enumeration reads state more than once | declined: bounded guarded reads, no demonstrated cost |
| 2 | Low: seed-create race can leave a fresh report without a new seed | declined: annotate already permits partial report/seed writes on I/O failure; it returns failure, does not archive, and the existing seed is protected; no atomic report/seed transaction added |
| 2 | Low: legacy apply-skip and accept not directly pinned | fixed: two tests (skip returns root destination without moving bytes; accept updates only the root publication, preserves a same-named nested file and the absent layout field). Fresh full suite at `808c80e03`: 14,715 passed |
| 2 | Nits: target docstring ambiguity, collision-remedy wording | fixed: clarified as recorded/default destination; remedy says choose a new explicit path or pass the existing path to permit replacement |
| 2 | Nit: state change between two CLI handoff reads | declined: unchanged narrow race, no demonstrated failure |
| 2 | Nit: import alphabetization | declined: no linter contract, style churn |
| 3 | N1 low: an unrecorded root file no longer blocks a nested promotion | declined: intended default-new behavior; presence is not ownership; collision docstring clarified |
| 3 | N2 low: directory-wide annotate also sees more seed Markdown | tracked BACKLOG #516 (input-selection policy; recursive traversal already includes nested seeds) |
| 3 | Repeated overwrite/partial-report/preview advisories | declined: prior dispositions stand |
| 3 | Optional stale path vocabulary in docstrings | fixed: reworded once to default/recorded publication directory; marker and ownership semantics unchanged |
| 3 | Optional import ordering, path literals | declined: avoid unrelated churn |

Reviews 2 and 3 ran affected suites independently (1,394 passed, 65 skipped; 2,844 passed, 66 skipped).

### Closure

**Low-yield convergence**, not zero-findings clean. The final sweep changed explanatory prose and tracking only; no further full review is claimed after it. Seed-directory changes are the two added READMEs only. Tracked Claude skill copies byte-match canonical sources; user-level copies are not refreshed from this branch, to avoid replacing PR #136's separately reviewed iteration guidance.

Integration after the PR #136 merge (2026-10-22): main `176ce30a5` merged as `42922cdc0` without conflicts; the two tracked Claude copies were regenerated from the combined sources; no runtime or test-source change relative to the reviewed branch. The change is committed locally on `fix/seed-default-location`, ready for its own architect-tier PR; no push, PR, migration, configuration feature or merge is part of this action.

Tracked: BACKLOG #516 (annotate directory input selection). Pending: none.

## Step description alias: implementation review ledger

*Opened 2026-10-22.*

| Item | Record |
| --- | --- |
| Base | `b2e46f5a4` (merged plan PR #139) |
| Branch | `feat/step-description-alias` |
| Scope | BACKLOG #517, four approved steps; plan-canonical reconciliation and review tail |
| Execution | All four steps green and committed (Codex / gpt-6.1-sol, `-y`, `--commit`) |
| Reviews | Three `reconcile-code --all --no-walk --no-reuse -y` sweeps; two Claude Code `/code-review` passes (built-in skill, high effort, Sonnet 5.5), reports `.tmp/step-description-alias.review-N.md`; saved reconcile reports (nine `*-run-reconcile.json`, 2026-10-22, three per sweep, `20261022-145151` through `20261022-150003`) in `docs/implementation-plans/archive/plan-details/step-description-alias/reports/` |
| Closure | **Logic convergence confirmed** (two independent consecutive passes against ranges containing the latest logic change `06ee36b41`); low documentation tail, not a completely clean all-prose audit |
| Checks | Last complete suite 14,996 passed, 67 skipped; `git diff --check` clean |

### Settled decisions

- Keep format v1; legacy title input/writes keep working without an upgrade. Preferred authored output is description, including ordinary legacy rewrites.
- Equal valid dual-key strings succeed; conflicts and invalid peers fail (pinned by existing tests).
- `Step.title`/default model dumps stay internal contracts; plan and feature titles, unrelated schema/version checks and execution semantics are unchanged. Older installations rejecting newly emitted description plans is documented.
- No bulk migration or upgrade command.

### Execution record

Each code subprocess committed its own implementation and tests, so the tracked BUG_BACKLOG issue "Run's test-authoring gate misses tests committed inside the backend call" refused advancement. No gate was disabled and no status hand-edited; each recovery inspected the committed diff, ran the full suite, then `run --step N --accept --commit` (which reruns the gate). The gate defect is not repaired here. Every accepted step was pushed after its pre-push full suite passed. Logs: `.tmp/step-description-alias.{run,accept,step-N-recovery-tests,push}-N.log`.

| Step | Implementation | Recovery suite | Accepted checkpoint |
| --- | --- | --- | --- |
| 1 | `9ef7859e6` | 14,911 passed, 67 skipped | `24bec3d0b` |
| 2 | `ced7f8ab1` | 14,959 passed, 67 skipped | `d28e647f0` |
| 3 | `6941fd103` | 14,989 passed, 67 skipped | `183065759` |
| 4 | `891c48995` | ordinary run gate passed | `cbf788665` |

### Findings

| Source | Finding | Disposition |
| --- | --- | --- |
| Reconcile 1, step 2 | `step2-run-reconcile-52952d9c` medium: ordinary rewrite loses body bytes (CRLF/CR); `TestRoundTrip.test_body_preserved_byte_for_byte` reads normalized text | fixed `06ee36b41`: raw UTF-8 bytes read at `parse_plan` provenance read and `write_plan` current-file read and published raw; six-case LF/CRLF/CR newline test (both step key spellings) had four failures before; focused parser/consumer suites 2,812 passed; full 14,996 passed |
| Reconcile 1 | Steps 1 and 3: no findings (non-code step 4 excluded) | none |
| Reconcile 2, 3 | Zero recommendations on all three code steps (after `06ee36b41` and `cd23db696`); the final two full sweeps are clean | none; no further full sweep without a material code correction |
| CR 1 (`09338c987`) | D1 low: stale annotate raw-key instructions and a create comment | fixed: prompt/comment accuracy only (annotate/create 1,132 passed; full 14,996 passed); sibling raw-key comments in `annotate.py` and `annotate_render.py` finished under DOC-1 below |
| CR 1 | D2 low: diagnostics advertise only legacy `title` | tracked BUG_BACKLOG "Step-field diagnostics advertise only legacy title after description alias support" (a formatter-only remedy would leave raw Pydantic errors different) |
| CR 1 | M1 key order | declined: canonical position is not an acceptance property |
| CR 1 | M2 mixed frontmatter/body newlines | declined: frontmatter is reserialized; the property preserves body bytes |
| CR 1 | M3 other callers normalize body newlines | tracked BUG_BACKLOG "Concept sync and scope-out rollback normalize existing plan body newlines" (no end-to-end reproduction claimed) |
| CR 2 (`db6e63807`) | C2 rejected conflicting/invalid peers | refuted: the approved dual-key rule requires rejection; existing tests pin it |
| CR 2 | C4 cross-flow provenance mismatch | refuted: each flow captures and compares its own representation; remaining separate-path newline loss is the filed bug |
| CR 2 | DOC-1 low: two sibling raw-key comments | fixed: description/legacy-title wording in both; no runtime change (annotate/annotate-render 83 passed) |
| CR 2 | Key position, error shapes, colon-quoting examples | declined: wording/preferences |

Review 1 ran 4,138 targeted tests (1 skipped) with throwaway-input probes; review 2 ran 4,322 (1 skipped) and verified the D1 prompt correction and maintained format docs accurate.

### Closure

**Logic convergence confirmed.** Review 2 covers `db6e63807`, not the later comment/bookkeeping commit; repository policy lets advisory prose corrections finish without resetting the logic window. BACKLOG #517 is removed after four green steps, complete reconciliations, full tests and both reviews. Retired the plan-only pickup handoff and routed the index here; plan PR #139 preserves authoring provenance. Runtime code, the version-1 exception and compatibility decisions are unchanged by the closing bookkeeping.

Tracked: the two BUG_BACKLOG follow-ups above. Pending: none.

## Step description diagnostic repair

*Opened 2026-10-22.*

| Item | Record |
| --- | --- |
| Base | `2445c3740`, merged gate repair PR #141 |
| Branch | `fix/step-description-diagnostics` |
| Scope | BUG_BACKLOG “Step-field diagnostics advertise only legacy title after description alias support” |
| Route | Bounded direct formatter correction; no schema or alias change |
| Current state | Complete: 15,032 tests pass; two independent actual Claude Code reviews confirm logic convergence |

### Property and sites

Concise validation diagnostics expose preferred step description and accepted
legacy title. Missing step text must be distinguished from missing plan/feature
titles; typo lists include both spellings and plan-level description points to
a step. Preserve structured errors, raw ValidationError text, internal Step.title,
validation outcomes, exit codes and unsupported-version ordering.

Pre-edit identifier search: format_validation_errors, _explain_extra_field,
model_fields, missing required errors and their validate consumer. Vocabulary
search: allowed fields, missing/typo/misplaced fields, title and description in
parser/tests/CLI validation and the format reference.

- parser.format_validation_errors renders structured errors. Remap only an
  actual missing error at (steps, integer index, title); do not mutate the
  payload or rewrite invalid/conflicting values.
- parser._explain_extra_field lists Step.model_fields, which intentionally
  lacks the input-only alias. Include description before legacy title in the
  step allowed list, and recognize the alias when explaining misplacement.
- cli.inspect.cmd_validate renders the concise format; locator and sweep
  also consume the same renderer, as review 1 verifies. Preserve its
  default findings exit 0 and opt-in --fail-on-findings exit 1.
- Tests mirror parser and exercise real main([...]) validation calls. Plan and
  feature title errors remain their original locations/messages.
- The Step validator, serialization, parser exception constructors and schema
  models remain unchanged. Other surfaces retaining raw Pydantic diagnostics
  are outside the concise-formatter scope; this change does not claim to
  normalize every application error.

### Validation

Affected parser/validation CLI/inspection checks: 497 passed in 1.54s.
Restoring the complete pre-change parser makes the new unit/CLI regressions
fail while existing carve-outs remain asserted; source is restored after the
mutation. Exact mutation counts and full-suite/review evidence are recorded below.

Old-formatter mutation: 5 failed, 13 passed in 0.57s. Full suite after restoring
the fix: 15,030 passed, 67 skipped in 74.77s. Diff whitespace check passes.

### Claude Code review 1

Range `2445c3740..4ab08849d`; actual built-in code-review Skill at high effort,
Sonnet 5.5, session `51fb5c33-dbe5-46ef-bc4a-746d56c2f53d`, CLI exit zero. Consolidated
report `.tmp/step-description-diagnostics.review-1.md`. Six candidates receive
independent code/caller/test verification and real-parser probes. Reviewer
runs 290 targeted checks; it does not claim another full suite or mutation.
**No introduced logic defect**; first clean pass against `fedb8ff44`.

- F1 pre-existing feature-container label/list error is confirmed; file
  “Feature-container unknown fields are mislabeled as plan-level fields” in
  BUG_BACKLOG with the actual probe/source evidence. Do not widen this repair
  into feature-container normalization.
- F2 stale status/evidence phrasing is corrected in this record.
- F3 optional coverage is added as two cases: legacy/preferred valid step text
  plus a typo must produce only unknown-key advice, never missing-field advice.
  This strengthens the intended missing-vs-typo distinction without changing
  production behavior.
- Speculative internal-field rename/wrapper changes are refuted by the preserved
  schema and tests. Display versus structured location differences are intended
  and payload preservation is pinned. The backlog entry stays until convergence.
- Plan/feature missing titles, invalid aliases, conflicts, version/exit behavior,
  raw exception constructors and the changelog are verified unchanged/accurate.

This round adds tests and tracking only. Production logic stays at `fedb8ff44`.

Review-1 follow-up checks: 499 affected tests pass in 1.21s; full suite 15,032
passed, 67 skipped in 73.79s. Production formatter is unchanged; new coverage
and tracking do not reset the logic review window.

### Claude Code review 2 and closure

Range `2445c3740..78740f1cd`, actual built-in code-review Skill at high effort,
Sonnet 5.5, session `0ef7a12a-0014-4bc2-b1a6-335039425d2b`, CLI exit zero. Consolidated
report `.tmp/step-description-diagnostics.review-2.md`. Four candidates receive
independent source/caller/test verification and 15 real-parser probes. Tests:
973 passed, 1 skipped, including parser, CLI, locator and sweep consumers.
No introduced logic defect or regression; review 1's correction is independently
confirmed against the latest full diff.

- Feature-container label/list issue remains separately filed and verified as
  pre-existing; this fix adds only an accurate step-placement hint for that key.
- Missing text plus a typo correctly emits both errors; actual parser and CLI
  regressions pin it. Correlating/suppressing errors via typo heuristics is
  declined new scope, not a missing implementation.
- Hypothetical internal Step.title renames are not a current defect; the schema
  and tests explicitly preserve the field. No alias metadata refactor is needed.
- Displayed versus structured locations differ deliberately; structured payload
  and raw exception text stay unchanged. No in-repo consumer parses the old text.
- Close source tracking now that the second confirmation is complete. Keep the
  deferred feature-container entry rather than silently broadening this repair.

**Logic convergence:** reviews 1 and 2 independently find no introduced defect
against latest production change `fedb8ff44`; later changes add tests and
tracking only. Last full suite: 15,032 passed, 67 skipped in 73.79s. The closing
commit removes the source BUG_BACKLOG entry and indexes this evidence; no claim
is made that those bookkeeping bytes receive a third Claude review.

## Detail empty-heading refusal: code review ledger

*Opened 2026-11-13.*

One bounded change, reviewed headlessly (`claude-personal -p`, report-only):
`detail` refuses a plan body that holds a heading whose name is empty after
normalization (`## :`, `## .`) with a `DetailError` that names the heading and
the plan, through one helper (`empty_concept_headings_message` in
`plan_tool/concept_bootstrap.py`) that `create` now shares. The drain procedure
lives in [`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head; the branch carries one unrelated handoff-trim commit (`c3fd86f38`) |
| Heads reviewed | Pass 1: `f7c5afc13`. Pass 2: `ef923fdf8`. Corrections to pass 2: `4a9979704`, then this ledger revision (the next commit) |
| Checks | Full suite 14,915 passed, 67 skipped, 2026-11-13, with `4a9979704`'s code. The reviewers could not run tests; the author ran them. The one extra skip is `tests/test_cli.py:3277`, a run-log scope proxy that skips whenever a branch's diff touches a test file outside its allowlist; it passes on `main` |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/detail-empty-heading-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Closed at low-yield convergence, 2026-11-13: not a clean audit.** Pass 1 returned three low findings and pass 2 six low plus one info, none material |

### Settled decisions

- Refuse rather than skip or rename an empty-named section; the empty-name
  predicate is `not section.name` (the parser strips whitespace before dropping
  trailing `:`/`.`, so a name is empty exactly when `concept_id` would raise).
- `scope-review` has no guard (see pass 2, finding 1): its legacy route only
  reaches the bootstrap with a record that matches the plan, and a plan holding
  such a heading cannot have had one written.
- `detail` and the `scope-review` legacy route do not run the repeated-heading
  check from the `create` refusal; they collapse silently or exit cleanly, as
  recorded earlier.
- The CLI handler that prints `DetailError` (`cli/authoring.py`) was traced by a
  reviewer, not run.

### Evidence (this session's runs; the reviewers could not execute code)

- Before the fix, the two `derive_candidate_buckets` refusal cases failed with
  the bare `ValueError`; the zero-width carve-out passed. The helper's own unit
  tests could not import before the helper existed.
- Mutants, measured: skipping the refusal in `create` fails 8; skipping it in
  `detail` fails 3 (the `generate_detail` test and the two bucket cases);
  widening the helper to a zero-width name fails 3; silently dropping a
  zero-width-named section fails the zero-width test; dropping the plan-path
  prefix fails the `generate_detail` test.
- Probe behind pass 2's finding 1: a full-tree record written while the plan was
  clean, then `## :` hand-added, makes `scope-review` exit 4 with "stored plan
  fingerprint is stale" and never reach the bootstrap.

### Findings and dispositions

Pass 1 (three low findings):

1. The zero-width carve-out test in `detail` asserted only a truthy dict —
   `fixed 84d9aae57` (it asserts the invisible-named bucket exists).
2. The helper docstring overstated "every command" — `fixed 84d9aae57`.
3. No test drove the refusal through the real `detail` entry point —
   `fixed 84d9aae57` (a `generate_detail` test: `DetailError` naming the heading,
   no model call, plan and detail directory untouched).

Pass 2 (six low findings and one info):

1. The `scope-review` legacy-route guard was unreachable by any real flow, and
   its test forged a state no tool can produce — `fixed 4a9979704`: the guard and its
   two tests are removed and the `scope-review` files match `main`. Verified by
   running a realistic hand-edit (stale-record exit). The earlier command-level
   reproduction had used a forged record, and the backlog entry had overstated it.
2. The review record was embedded in the drain handoff instead of a ledger —
   `fixed` in this ledger revision.
3. The branch carries an unrelated commit and the range was miscounted —
   accepted: the trim is a separate, separately described commit and the pull
   request body states the true range; the Dockerfile ledger stays indexed in
   `handoffs/README.md`.
4. The refusal is applied at opt-in call sites, not at the bootstrap
   precondition — `fixed 4a9979704` for the documentation (a note on `bootstrap_concepts`
   that callers run the helper first). `declined`: making `bootstrap_concepts`
   itself raise a descriptive error, a more general design change.
5. The `detail` refusal did not name the plan — `fixed 4a9979704` (the error carries the
   plan path; the `generate_detail` test asserts it).
6. The flat carve-out test pinned only the return code — moot: removed with the
   guard it protected.
7. Handoff verification claims were partly unverifiable (the pre-fix claim and a
   missing mutant) — `fixed` in this ledger revision.

### Closure

**Closed at low-yield convergence on 2026-11-13; not a clean audit.** Two
consecutive passes returned only low and info findings, none material. The
largest outcome of review was removing a guard that protected no real flow.

## Files-coherence extensionless Dockerfile: code review ledger

*Opened 2026-11-13.*

One bounded change, reviewed headlessly (`claude-personal -p`, report-only):
the path and filename mention extractors in `plan_tool/detail.py` recognize an
exact, case-sensitive `Dockerfile` through one fixed list, and an identical
`Dockerfile` basename in another directory is never a near-miss in
`plan_tool/review.py`. The drain procedure lives in
[`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head (the branch carries one unrelated handoff-trim commit, `9e0173ede`) |
| Heads reviewed | Pass 1: `4abcb9171`. Pass 2: `8bc109c46`. Pass 3: `f8a8c9f42`. Corrections to pass 3: `ef4ef9202`, then this ledger revision (the next commit) |
| Checks | Full suite 14,906 passed, 67 skipped, 2026-11-13, with `ef4ef9202`'s code. The reviewers could not run tests; the author ran them. One skip is `tests/test_cli.py:3277`, a run-log scope proxy that skips whenever the branch diff touches a test file outside its allowlist (here `tests/test_review.py`); it passes on `main`. The other skips are unchanged (`tests/test_roadmap.py`, one unresolvable plan title) |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/files-coherence-dockerfile-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

### Settled decisions

- The supported extensionless set is exactly `Dockerfile`: no `Makefile`,
  `Jenkinsfile` or `Procfile`, and no `Dockerfile.<suffix>`. It is a fixed list,
  not a pattern.
- The class-wide effect on every consumer of the extractors is intended.
- A bare backticked `Dockerfile` credits every declared Dockerfile in the step
  (the existing basename rule, as for a bare `__init__.py`); a test states it.
- The `docs/` Dockerfile classification change is a recorded verdict change.
- The five `F811` lint errors in `tests/test_detail.py` and `tests/test_review.py`
  and the two `F821` in `plan_tool/launcher.py` exist on `main` and are out of
  scope.

### Evidence for the fix (this session's runs; the reviewers could not execute code)

- Before the fix, exactly the two tests that need the new recognition failed.
- Final mutants, measured on the final tests: dropping the path arm fails 10;
  dropping the bare arm fails 4; neutralizing the repeated-by-design skip fails 7;
  the first remedy (`dockerfile` in the generic set) fails 5; substring matching
  and case-insensitivity are each caught.
- Sibling-directory scores that motivated the skip, reproduced by running
  `_nearest_declared_match`: `docker/web` vs `docker/api` 0.857, `services/web`
  vs `services/api` 0.870, `worker-b` vs `worker-a` 0.947 (bar 0.85). Generic
  names keep the existing tradeoff and can reach the same route: `index.ts` in
  the same layouts scores 0.842, 0.857 and 0.941, so only the first stays under
  the bar. A cited `Dockerfile` vs a declared `Dockerfile.dev` in one directory
  also cleared the near-miss rules before the dotted-variant clause.

### Findings and dispositions

Pass 1 (seven findings):

1. A context citation such as `api/Dockerfile` drew a new `detail_only` "did
   you mean" finding — `fixed 50f35c48a` (`dockerfile` as a generic basename),
   found incomplete by pass 2 finding 1 and completed in `52d26f957`.
2. Consumers other than `check_files_coherence` unpinned — `fixed 50f35c48a`
   (near-miss, plan-level orphan deferral, claim-vs-delivery trip and no-trip,
   domain cells).
3. A medium finding citing only a `docs/` Dockerfile flips from blocking to
   non-blocking — `fixed 50f35c48a`: `docs/` and `tests/` cells pinned as a
   recorded verdict change.
4. Stale comment and docstrings saying a known extension is required —
   `fixed 50f35c48a`.
5. A bare `Dockerfile` credits every declared Dockerfile — `declined` as a
   defect (the existing basename rule); pinned by a test in `50f35c48a`.
6. Handoff log inaccuracies (test count, `lessons.py`, the near-miss direction,
   a stray blank line) — `fixed 8bc109c46`.
7. The handoff trim dropped the only record of a residual `detail` /
   `scope-review` empty-heading crash — `fixed 1acb52485`: reproduced on
   `derive_candidate_buckets` and filed in `BUG_BACKLOG.md`.

Pass 2 (five findings, one medium):

1. (medium) The generic-basename entry did not close the sibling-directory
   route: a long basename pushes full-path similarity over the 0.85 bar —
   `fixed 52d26f957`. Verified by running the scores above. `dockerfile` now
   lives in its own repeated-by-design set; an identical basename there never
   reaches either near-miss rule, and the generic names are unchanged.
2. The recorded bare-arm mutant count was not reproducible, and the skipped
   count moved — `fixed 52d26f957`: the bare-arm count is re-measured (4) and the
   skip is explained above.
3. A pre-existing test was renamed inside this change — `fixed 52d26f957`: the
   original name `test_claim_vs_delivery_no_trip_when_step_declares_it` is
   restored.
4. Consumer coverage the log claimed but tests did not pin — `fixed 52d26f957`
   for a repo-root `Dockerfile` cited bare and as `./Dockerfile`, and for a bare
   token in the classify test. `declined`: orphan condition 2 (a consuming
   step's citation). A test for it passed without the Dockerfile arm, because
   the step is already recognized through the path-derived symbol, so the
   extractor does not decide that outcome; the vacuous test was removed.
5. Pass-1 record not enumerable in the drain log — `fixed` in this ledger
   revision.

Pass 3 (four low findings, confirming pass; verified by running the scores):

1. `_claim_delivered` still fuzzy-matches a sibling-directory Dockerfile as
   delivered — `declined`: it only reduces the recall of an info advisory and
   produces no false finding, and Dockerfile claims were not extracted at all
   before this change, so nothing regressed. Not filed.
2. A cited `Dockerfile` against a declared `Dockerfile.<suffix>` in one
   directory still drew a near-miss (`services/api/Dockerfile` vs
   `services/api/Dockerfile.dev`, reproduced) — `fixed ef4ef9202`: the repeated-by-design
   skip also covers a dotted variant of the cited basename; a unit case and a
   files-coherence case pin it, and dropping the clause fails both.
3. The test docstring and this ledger claimed `index.ts` stays under the
   similarity bar in the same layouts — `fixed ef4ef9202` and this revision:
   reproduced at 0.842, 0.857 and 0.941; the claim now states the existing
   tradeoff for generic names. Not filed: it is documented behavior.
4. The range row named a head that was not the branch head, and the README
   entry said "the open pass" — `fixed` in this ledger revision.

### Closure

**Stopped at exit 2 on 2026-11-13; not converged, not clean.** Pass 2's one
medium finding reset the low-yield streak, and pass 3 was the only low-only pass
after it, so the two-consecutive-passes condition was not met. Most of pass 2's
and pass 3's findings describe this branch's own earlier edits (the first
remedy, its tests and claims, and this ledger), the shape `CLAUDE.md` calls the
loop auditing its own edits, so every finding is applied or dispositioned above
and no fourth pass is planned unless the owner asks for one. The extractor
change itself drew no material finding after pass 1's regression and pass 2's
incomplete-remedy finding were fixed.

## Multiline concept decisions: code review ledger

*Opened 2026-11-13.*

One bounded change, reviewed headlessly (`claude-personal -p`, report-only):
`render_scope_decisions` renders a concept's title and rationale on one line so
a heading- or fence-looking line inside them cannot start a document boundary.
The drain procedure lives in [`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review ranges | Passes 1–2: `282e75b9f..af59e779c`. Passes 3–4: `origin/main..` the branch head named in the next row |
| Head reviewed by pass 4 | `7beb3090b`. Corrections to pass 4: `9be9acf65`, then this ledger revision (the next commit) |
| Checks | Full suite 14,859 passed, 67 skipped, 2026-11-13, at `0b20bcbb1` (code unchanged since); `tests/test_concept_sync.py` 36 passed, run by the pass-2, pass-3 and pass-4 reviewers |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/multiline-concept-decisions-code-review-N.*`, gitignored); the findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

### Settled decisions

- Flattening multi-line rationales to one line is intended; the source entry
  excluded broader Markdown sanitization, schema tightening, parser boundary
  rules and publication protocols.
- `foundational_logic.py:474` builds a prompt-advice block, not an owned plan
  section, and is unchanged. `detail.py:2374` already collapses whitespace.
- The whitespace-collapse idiom is not consolidated here.
- `U+2028` and `U+0085` are not boundaries to this parser; a bare CR is.
- The test's repeat-sync block is a labeled smoke check.

### The fix itself

- **Behavior:** `render_scope_decisions` (`plan_tool/concept_sync.py`) collapses
  whitespace in each concept's title and rationale, so a heading-, fence- or
  bare-CR-looking line inside them stays inside the owned `## Deferred` /
  `## Out of scope` body. Fixed in `a0cda5b53`; the test is tightened in
  `0b20bcbb1`.
- **Evidence (this session's runs; no reviewer could re-run mutants, because
  the reviewers' sandboxes refused them):** the four cases in the original
  test failed on the pre-fix code and passed with it; after the bare-CR case
  was added, a `\n`-only mutant failed on that case and a `.strip()` mutant
  failed on all five.

### Findings and dispositions

Pass 1 (code and tests; no material defect):

- Test pinned only `\n` — `fixed 0b20bcbb1` (bare-CR case). `declined`: the
  `U+2028`/`U+0085` cases (not boundaries here) and the `wont_do` /
  nested-concept cases (same code path as the fix).
- Repeat-sync assertion was vacuous — `fixed 0b20bcbb1` (each case asserts the
  exact one-line rendering).
- Another copy of the whitespace-collapse idiom — `declined` (no shared helper
  is importable without a cycle; a consolidation needs AST evidence and a
  `BACKLOG.md` entry).

Pass 2 (low-yield; two low documentation findings):

- Handoff omitted the commit that removed the backlog entry — `fixed 10bb51757`.
- Handoff counted "four" cases after a fifth was added — `fixed 10bb51757`.

Pass 3 (documentation accuracy; nine findings, four medium):

1. Handoff said "Nothing is pushed" after the branch was pushed — `fixed 7beb3090b`.
2. Queue rule "a `Priority` line goes first" was not a repo rule — `fixed 7beb3090b`
   (see pass-4 finding 1 for the replacement).
3. `needs investigation` is not a Readiness label — `fixed 7beb3090b`.
4. The `source_seed` entry's Fix covered the plain case its own evidence says
   needs no fix — `fixed 12bb69d52`.
5. The duplicate-ID entry said the normalized path "does not append the raw
   seed's sections", but it appends the raw `## References` — `fixed 12bb69d52`.
6. The same entry still said "the joining code has not been read" — `fixed 12bb69d52`.
7. Evidence for two entries rested only on a gitignored scratch log —
   `fixed 12bb69d52`.
8. The session log embedded review passes without a ledger shape —
   `fixed 7beb3090b` (this file).
9. Imprecise citation for the "measures vocabulary" rule — `fixed 12bb69d52`.

Pass 4 (ten findings: three medium, seven low):

1. Drain rule 4 imported the lead's Jira-promotion order, contradicting rule 1 —
   `fixed 9be9acf65`: rule 4 now says the handoff drains `BUG_BACKLOG.md` only
   and cross-file ordering is the lead's call.
2. Procedure step 6 restated the stopping rule as one low-yield round —
   `fixed 9be9acf65`: it now points at `CLAUDE.md` § "Severity-aware
   conceptual-audit stopping rule" (two consecutive low-yield passes).
3. The duplicate-ID entry parked a reproducible clause behind the
   unreproducible one — `fixed 9be9acf65`. **Verified by probe, 2026-11-13:** a
   direct-ready seed repeating `## Notes` crashes `create` with "concept scope
   contains duplicate IDs", and the same seed with `## Notes` once does not.
   It is now its own `ready` entry; the 0.1.0 distill-side cause stays
   `evidence-gated`. The bug itself is **not** fixed on this branch
   (`tracked`: `BUG_BACKLOG.md`, the repeated-heading entry).
4. Ledger used a moving `HEAD` range, no current-head row, and relative
   "this commit" dispositions — `fixed` in this ledger revision.
5. Ledger claimed "pre-push suite passed" with no date or count — `fixed` in
   this ledger revision: replaced by a dated full-suite row.
6. Moving the record dropped the fix's own evidence and the caveat that the
   mutation claims are this session's — `fixed` in this ledger revision (section
   "The fix itself").
7. Date-less review-status claims in three files — `fixed` in `9be9acf65` (README
   and drain log are status-free) and this ledger revision (status is dated and
   anchored in the table).
8. The duplicate-ID entry cited "the same-day throwaway run" without
   identifying it — `fixed 9be9acf65`: the run is described by its seed shape,
   version and scope.
9. Stale line numbers in the duplicate-ID entry — `fixed 9be9acf65` (cited by
   symbol). `declined`: relabeling the untouched entry that carries
   `Readiness: needs investigation` — it is not part of this change; the drain
   handoff's rule 6 covers unlabeled and non-standard labels by surfacing them.
10. Trim rule had no exit for `refuted`/`declined`/`tracked` lines, and the
    `source_seed` entry's Files cited archive constants instead of the code that
    archives — `fixed 9be9acf65` (both).

### Closure

**Stopped at exit 2 on 2026-11-13; not converged, not clean.** Pass 3 returned
four medium findings and pass 4 three, so the low-yield condition (two
consecutive diminishing passes) never held after pass 2. Most of pass 4's
findings describe this branch's own earlier documentation edits (the ledger,
the queue and stopping rules, the entries' evidence wording), the shape
`CLAUDE.md` calls the loop auditing its own edits; pass 4's one new defect
(finding 3) is a real bug in a neighboring code path, filed rather than fixed
here. All ten pass-4 findings are applied or dispositioned above. The code and
test change (`a0cda5b53`, `0b20bcbb1`) drew no material finding in any pass. No
fifth pass is planned.
