# Roadmap stack layer — code review ledger

The record of how BACKLOG #461 (plan `roadmap-stack-layer`) was executed and judged.
One ledger, updated in place. Closure label (see `handoffs/README.md` § "Retention"):
**converged** (low-yield rule: passes 4 and 5 were LOW-only display, doc and hardening findings; each changed code, so there is no clean pass).

| | |
| --- | --- |
| Review range | `8ce4516c..HEAD` on `impl/roadmap-stack-layer` (25 commits) |
| Plan | `docs/implementation-plans/archive/2-roadmap-stack-layer.md`, 8 of 8 steps `done` |
| Checks run | Full suite green at 13,591 passed, 67 skipped after review pass 5; five headless review passes; `reconcile-code --all` twice (sweep 1: 5 medium, 2 nit across steps 3, 6, 7; sweep 2: 0 critical / 0 high / 0 medium / 0 nits on all 7 code steps) |
| Reviewer | Headless `claude -p` sessions at effort `high`, report-only, each with a named findings file |
| Disposition | Closed; PR #46 |

## Settled decisions (hand to each reviewer)

- The stack is a `stack` collection in `02-constraints.md`. A missing collection
  (`ConstraintsArtifact.stack is None`) means "stack not recorded" and re-renders
  byte-for-byte as before; `()` means recorded and empty. Nothing may default a
  missing stack to `()`.
- Stack totality binds only an artifact that carries the collection, and a first
  run. It never refuses an artifact for lacking the collection.
- Stack rows carry exactly one of a non-empty `choice` or `open: true`, enforced by the
  `stack-row-state` gate, not the parser. The `concern` field is fixed on edit. Rows can
  be added, replaced, and revised, never removed.
- Stack rows have no row-owned prose (`allow_prose=False`). A candidate `add-row`
  for a prose-less row type treats `prose_amendment` as optional and refuses it when
  supplied (`_add_row_key_contract`). Prose-eligible row types still require it.
- A candidate can introduce the stack on a stack-less roadmap; candidate operations
  apply in target-id order, not the order the model listed them.
- `artifact_row_diffs` pairs collections by name, so a stack-less artifact diffs
  against a stack-bearing one without error.
- An anchorless stack add is authorized by any bound feedback item, including one
  aimed at an unrelated row (decided 2026-10-08, user-confirmed): a stack row declares
  no relation to anchor to, the totality gate refuses a partial stack, and the approver
  sees every added row in the stack callout. The revision route is stricter by design.
- A candidate `replace-row` must preserve every field its row policy fixes
  (`immutable_fields`), as the revision route does; this covers hosting's `facet` as
  well as stack's `concern`.
- The feedback ledger addresses design rows only; stores, hosting and stack rows are
  ineligible reviewer-feedback targets by design. An existing stack row reaches a
  candidate only through a relation (for example a decision anchored to it).
- The stack callouts (first-run output, `INDEX.md`, candidate review) are display
  only: never a defect class, never an approval gate (decided 2026-10-08 under #461).
- The `INDEX.md` stack section reads the accepted head through
  `load_resolved_stored_version`, which verifies every stored member; an
  unparseable member raises and never reads as "not recorded".
- The seed `## Stack` section gains a `### Technology stack` sub-part after
  `### Stores`, rendered by `_render_stack_section`.
- Two optional step 6 tests (per-site callout printing; approval independence of
  stack content) are filed as BACKLOG #465, not written.

## Owner decision: the parser checks types, the gate owns choice/open

Decided 2026-10-08 (user-confirmed): the stack parser accepts a row carrying both
`choice` and `open`, or neither; `stack-row-state` is the single owner of the rule on
every route, matching the step 1 detail's Implementation prose. The step 1 Tests
section's parser-level shape error is superseded. Do not report as a finding.

## Run record

- Step 1: the test-authoring gate misfired (the model had modified a test file); recovered by hand, committed `e7f80792`, `done` flipped as a separate commit.
- Step 2: failed the full suite on two sibling tests pinning the old gate set; fixed by hand (`bb7a94e9`).
- Step 3: a bare `git checkout` of one file discarded the model's uncommitted edits, so the step was reset and re-run; the re-run wrote no tests (gate failed correctly), so tests were applied from the first attempt's saved patch and adapted, one stale invariant test rewritten (`test_every_addable_row_type_has_a_valid_add_row_shape`, mutation-checked) (`9269f33a`).
- Step 5: failed 8 index tests because the fixtures wrote no recorded brief; fixed in the fixtures (`e21d0be6`). The `done` flip is a replacement when the previous step's commit has already written `status: current`; a first attempt inserted a duplicate key and was caught in `git diff`.
- Steps 4, 6-8: green, committed by the tool.
- `reconcile-code` sweep 1 findings were missing detail-promised tests; writing them exposed two code defects, both fixed: the candidate route refused the first stack add (`_prepare_operations`), and `artifact_row_diffs` raised pairing a stack-less artifact with a stack-bearing one.

## Findings

Every pass was static traces (probes refused in the reviewer sandbox); each finding was reproduced in the driving session before acceptance.

Pass 1, `8ce4516c..b8420509`:

1. HIGH: a candidate stack add could not be stored or replayed (wire form carried `prose_amendment: null`; `roadmap_candidate.py:_operations_wire_for_reparse`; reproduced: `candidate add-row prose amendment must be a JSON object`). fixed fe6b5e38.
2. HIGH: candidate context crashed on any roadmap recording a stack (`_project_members` reached `_row_label` with a `StackRow`; `TypeError: unsupported impact row type`). fixed fe6b5e38 (skipped in the inventory as stores are). The related point that an existing stack row cannot be targeted by ledger feedback: refuted as a defect (settled ledger limit).
3. HIGH: `roadmap compare` crashed on a stack card (`display_label` lacked a `StackRow` branch). fixed fe6b5e38.
4. MEDIUM: a decision anchored to a stack row read "undefined" in review views (`_constraints_entries` omitted stack). fixed fe6b5e38.
5. MEDIUM: an anchorless stack add is authorized by any bound feedback item. declined (decided 2026-10-08): deliberate wider authority, pinned by the docstring of `test_candidate_introduces_a_complete_stack_on_a_stackless_roadmap`.
6. LOW: the candidate route never enforced fixed fields (two `replace-row` ops could swap stack concerns; hosting `facet` same gap). fixed (decided 2026-10-08: every policy-declared fixed field enforced, hosting included; mutation-checked).
7. LOW: gate and parser disagreed on a blank `choice`. fixed fe6b5e38 (mutation-checked).
8. LOW: candidate prompts still said every `add-row` carries `prose_amendment`. fixed fe6b5e38.

Class behind 2-4: row-type dispatch predating `StackRow` (`_row_label`, `display_label`, `_constraints_entries`); a sweep by `StoreRow`/`HostingRow` dispatch found no further sites.

Pass 2, `8ce4516c..da28b61c` (ceiling fell from three HIGH to two MEDIUM):

1. MEDIUM: `--view html` linked a stack anchor to a missing element. fixed (Stack block rendered only when a stack is recorded).
2. MEDIUM-LOW: `duplicate-stack-concern` told the model to rename an id. fixed (`_DROP_EXTRA_ROWS_GATE_KINDS`).
3. LOW-MEDIUM: stack summary printed model text unsanitized into `INDEX.md` and the terminal. fixed (one-line collapse).
4. LOW: inherited-decision gate rejects a stack-row anchor the authored-decision gate accepts. declined: same asymmetry holds for hosting; an inherited anchor names a design row by design.
5. LOW: a both/neither `choice`/`open` row can never reach `stack-row-state` on the candidate route. Open at the time pending the owner decision recorded above (parser checks types, gate owns the rule); not reported as a finding.
6. LOW: batch prompt never showed the stack row shape or totality rule. fixed (both templates).
7. LOW: `prose_amendment: null` on a stack add got a misleading message. fixed.
8. LOW (reuse): fixed-field phrase built three times. declined: incidental consolidation, below the duplication guard's threshold.
9. LOW (altitude): "stack is the one creatable collection" encoded in four places. declined: wait for a second optional collection.
10. LOW (efficiency): `INDEX.md` refresh loads the head twice. declined: minor cost on a rare path.

Pass 3, `8ce4516c..51b08cd5` (no crash or data-loss; code changed after, so no clean-pass credit):

1. MEDIUM: format docs called a stack row a ledger feedback target. fixed (`ROADMAP_FEEDBACK_FORMAT.md`, `ROADMAP_FORMAT.md`).
2. LOW-MEDIUM: docs and one gate comment still said the parser rejects both/neither. fixed (vocabulary sweep: `rejects a row carrying`, `parser itself rejects`, `parser's definition`).
3. LOW-MEDIUM: "Pending concerns" ignored a pending decision authored in `04-roadmap.md`. fixed in index and first-run output (mutation-checked); domain decisions stay out since the domain stage runs before any stack row exists.
4. LOW-MEDIUM: summary sanitized `choice`/`concern` but not `id` nor open/pending lines. fixed (mutation-checked).
5. LOW: `stack-row-state` got only generic candidate correction text. fixed (specific branch).
6. LOW: renderers disagreed on a neither-choice row. fixed (`no choice` in `display_label`, HTML block, seed section).
7. LOW: candidate callout lists `model`/`topology` hosting rows as "no product recorded". declined: explicit none marker is deliberate, pinned by `test_hosting_and_store_products_are_listed_verbatim_with_explicit_none_marker`.
8. LOW: candidate callout delta is against the source hop, not the root. declined: narrative evidence has the same per-hop basis.
9. LOW: `CONSTRAINTS_OPTIONAL_ROW_KEYS` referenced nowhere. fixed (deleted).

Pass 4, `8ce4516c..f3fb2ef2` (six LOW; code changed, no clean-pass credit):

1. LOW-MEDIUM: `INDEX.md` stack groups rendered as one list in a Markdown viewer. fixed (blank line before each group heading; test pinned).
2. LOW: plan and step 5 detail described a two-artifact pending read and a stack feedback target. fixed (vocabulary sweep).
3. LOW: the embedded `removals` route can still drop a stack row. declined: authorized by the reviewer's own open feedback as for any design row; `ROADMAP_FORMAT.md`'s "never reverts" is now scoped to typed operations.
4. LOW: seed `## Stack` lead said every row is settled. fixed (names the open exception).
5. LOW: class-name `row_type` spellings (`StackRow`) draw a `prose_amendment` demand in retry text. declined: same for `StoreRow`, at most one retry, diagnostic already says `use stack`.
6. LOW: `_one_line` keeps non-whitespace control characters. declined: no other roadmap model text is filtered for them; hardening one summary would not close the class.

Pass 5, `8ce4516c..b03090c9` (no crash, data-loss or gate-bypass; five LOW):

1. LOW: pass 4's blank separators printed as empty bullets in first-run terminal output (regression from the pass 4 fix). fixed (plain print, as the candidate callout does; test pinned).
2. LOW: choice-or-open display rule written four times, disagrees on a whitespace-only choice. declined: reachable only on a version no gate judged, display only; a shared helper belongs in the backlog if wanted.
3. LOW: fixed-field enforcement also runs on stored-candidate replay. declined: no stored candidate can carry a stack row or facet swap the totality gate accepted before this range.
4. LOW (doc): format doc and plan said the candidate callout lists open and pending concerns. fixed.
5. LOW (doc): step 8's detail still said stack rows are feedback targets. fixed (step 3's text about the embedded stage-feedback route stays).

## Tracked

- **tracked** #465 — two optional step 6 stack-callout tests.
- **shipped** — the pre-push hook drops the repo-local git environment, so a push from a
  secondary worktree no longer lets the suite write into the shared `.git` (was #466,
  removed from the backlog).
- **shipped** — the directives' done-flip sentence now covers a replacement when the
  previous step's commit has set `status: current` (was #467, removed from the backlog).
