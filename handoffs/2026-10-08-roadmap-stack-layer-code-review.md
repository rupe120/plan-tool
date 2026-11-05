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
  `stack-row-state` gate, not the parser. The
  `concern` field is fixed on edit. Rows can be added, replaced, and revised, never
  removed.
- Stack rows have no row-owned prose (`allow_prose=False`). A candidate `add-row`
  for a prose-less row type therefore treats `prose_amendment` as optional and
  refuses it when supplied (`_add_row_key_contract`). Prose-eligible row types still
  require it.
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

- Step 1: the tool's test-authoring gate misfired (the model had modified a test
  file); recovered by hand, full suite green, step committed `e7f80792`, flipped
  `done` as a separate commit.
- Step 2: failed the full suite on two sibling tests pinning the old gate set;
  fixed by hand (`bb7a94e9`).
- Step 3: first attempt failed on two tests. A bare `git checkout` of one file then
  discarded the model's uncommitted edits to it; the step was reset and re-run. The
  re-run wrote no tests (gate failed correctly); tests were applied from the first
  attempt's saved patch and adapted, one stale invariant test rewritten
  (`test_every_addable_row_type_has_a_valid_add_row_shape`, mutation-checked)
  (`9269f33a`).
- Step 4: green, committed by the tool.
- Step 5: failed 8 index tests because the fixtures wrote no recorded brief; fixed
  in the fixtures (`e21d0be6`). The `done` flip is a replacement when the previous
  step's commit has already written `status: current`; a first attempt inserted a
  duplicate key and was caught in `git diff`.
- Steps 6–8: green, committed by the tool.
- `reconcile-code` sweep 1 findings were missing detail-promised tests. Writing them
  exposed two code defects, both fixed: the candidate route refused the first stack
  add (`_prepare_operations`), and `artifact_row_diffs` raised pairing a stack-less
  artifact with a stack-bearing one.

## Review pass 1 — headless /code-review, 2026-10-08, `8ce4516c..b8420509`

Probes were refused in the reviewer's sandbox, so every finding was a static trace; each
was reproduced here before it was accepted.

1. **A candidate stack add could not be stored or replayed** (HIGH). The wire form of a
   parsed op carried `prose_amendment: null`, which the parser cannot read back.
   `roadmap_candidate.py:_operations_wire_for_reparse`. Reproduced
   (`candidate add-row prose amendment must be a JSON object`). **fixed fe6b5e38**.
2. **Candidate context crashed on any roadmap recording a stack** (HIGH).
   `_project_members` reached `_row_label` with a `StackRow`
   (`TypeError: unsupported impact row type`). Reproduced. **fixed fe6b5e38** (skipped in
   the inventory as stores are). The reviewer's related point, that an existing stack row
   cannot be targeted by ledger feedback, is the documented ledger limit (design rows
   only; stores and hosting likewise): **refuted as a defect**, settled below.
3. **`roadmap compare` crashed on a stack card** (HIGH). `display_label` had no
   `StackRow` branch. **fixed fe6b5e38**.
4. **A decision anchored to a stack row read "undefined"** in the review views (MEDIUM).
   `_constraints_entries` omitted stack. **fixed fe6b5e38**.
5. **An anchorless stack add is authorized by any bound feedback item** (MEDIUM),
   including feedback aimed at an unrelated row; the revision route requires an
   artifact-level target. **declined** (decided 2026-10-08): the wider authority is
   deliberate and pinned by the docstring of
   `test_candidate_introduces_a_complete_stack_on_a_stackless_roadmap`.
6. **The candidate route never enforces fixed fields** (LOW), so two `replace-row` ops
   can swap the concerns of two stack rows; hosting's `facet` has the same gap.
   **fixed** (decided 2026-10-08: enforced for every policy-declared fixed field, hosting
   included; no existing test replaced a hosting `facet` through a candidate;
   mutation-checked).
7. **Gate and parser disagreed on a blank `choice`** (LOW). **fixed fe6b5e38**
   (mutation-checked).
8. **Candidate prompts still said every `add-row` carries `prose_amendment`** (LOW).
   **fixed fe6b5e38**.

The class behind 2–4 is row-type dispatch that predates `StackRow`
(`_row_label`, `display_label`, `_constraints_entries`); the sweep by `StoreRow` /
`HostingRow` dispatch found no further sites.


## Review pass 2 — headless /code-review, 2026-10-08, `8ce4516c..da28b61c`

Static traces again (probes refused). Severity ceiling fell from three HIGH to two MEDIUM.

1. **`--view html` linked a stack anchor to a missing element** (MEDIUM). **fixed** (a
   Stack block, rendered only when a stack is recorded).
2. **`duplicate-stack-concern` was told to rename an id** (MEDIUM-LOW). **fixed**
   (`_DROP_EXTRA_ROWS_GATE_KINDS`).
3. **The stack summary printed model text unsanitized** into `INDEX.md` and the
   terminal (LOW-MEDIUM). **fixed** (one-line collapse).
4. **The inherited-decision gate rejects a stack-row anchor the authored-decision gate
   accepts** (LOW). **declined**: the same asymmetry already holds for hosting, and an
   inherited anchor names a design row by design.
5. **A both/neither `choice`/`open` row can never reach `stack-row-state` on the
   candidate route** (LOW). A consumer of the open owner question's other reading;
   **open — owner decision**.
6. **The batch prompt never showed the stack row shape or the totality rule** (LOW).
   **fixed** (both templates).
7. **`prose_amendment: null` on a stack add got a misleading message** (LOW). **fixed**.
8. **The fixed-field phrase is built three times** (LOW, reuse). **declined**:
   consolidation noticed in passing; below the duplication guard's threshold.
9. **"Stack is the one creatable collection" is encoded in four places** (LOW,
   altitude). **declined**: the reviewer's own smallest-change reading is to wait for a
   second optional collection.
10. **`INDEX.md` refresh loads the head twice** (LOW, efficiency). **declined**: minor
    cost on a rare path.

## Review pass 3 — headless /code-review, 2026-10-08, `8ce4516c..51b08cd5`

Static traces again (probes refused). No crash or data-loss finding; the set was two
false-contract docs, a few display gaps and cleanup. Code changed after this pass, so
it does not count toward the two-clean-pass exit.

1. **Format docs called a stack row a ledger feedback target** (MEDIUM). **fixed**
   (`ROADMAP_FEEDBACK_FORMAT.md`, `ROADMAP_FORMAT.md`; the ledger addresses design rows only).
2. **Docs and one gate comment still said the parser rejects both/neither** (LOW-MEDIUM).
   **fixed** (vocabulary sweep: `rejects a row carrying`, `parser itself rejects`,
   `parser's definition`).
3. **"Pending concerns" ignored a pending decision authored in `04-roadmap.md`**
   (LOW-MEDIUM). **fixed** in the index and the first-run output (mutation-checked).
   Domain decisions stay out: the domain stage runs before any stack row exists.
4. **The summary sanitized `choice`/`concern` on the row line but not `id`, nor the
   open/pending lines** (LOW-MEDIUM). **fixed** (mutation-checked).
5. **`stack-row-state` got only the generic candidate correction text** (LOW). **fixed**
   (specific branch; removed from the intentionally-generic set).
6. **Renderers disagreed on a neither-choice row** (LOW). **fixed** (`no choice` in
   `display_label`, the HTML block and the seed section).
7. **The candidate callout lists `model`/`topology` hosting rows as "no product
   recorded"** (LOW). **declined**: the explicit none marker is deliberate and pinned by
   `test_hosting_and_store_products_are_listed_verbatim_with_explicit_none_marker`.
8. **The candidate callout's delta is against the source hop, not the root** (LOW).
   **declined**: the narrative evidence has the same per-hop basis; parity, not a regression.
9. **`CONSTRAINTS_OPTIONAL_ROW_KEYS` was referenced nowhere** (LOW). **fixed** (deleted).

## Review pass 4 — headless /code-review, 2026-10-08, `8ce4516c..f3fb2ef2`

Static traces (probe refused). Six LOW findings; code changed, so no clean-pass credit.

1. **`INDEX.md` stack groups rendered as one list in a Markdown viewer** (LOW-MEDIUM).
   **fixed** (the producer emits a blank line before each group heading; test pinned).
2. **Plan and step 5 detail still described a two-artifact pending read and a stack
   feedback target** (LOW). **fixed** (vocabulary sweep of the plan body and detail).
3. **The embedded `removals` route can still drop a stack row** (LOW). **declined**: that
   route is authorized by the reviewer's own open feedback, as for any design row; the
   "never reverts" sentence in `ROADMAP_FORMAT.md` is now scoped to typed operations.
4. **The seed `## Stack` lead said every row is settled** (LOW). **fixed** (names the
   open exception).
5. **Class-name `row_type` spellings (`StackRow`) draw a `prose_amendment` demand in the
   retry text** (LOW). **declined**: the same holds for `StoreRow`, it spends at most one
   retry, and the diagnostic already says `use stack`.
6. **`_one_line` keeps non-whitespace control characters** (LOW). **declined**: no other
   model text printed by the roadmap verb is filtered for them; hardening one summary
   would not close the class.

## Review pass 5 — headless /code-review, 2026-10-08, `8ce4516c..b03090c9`

Static traces. No crash, data-loss or gate-bypass finding; five LOW.

1. **Pass 4's blank separators printed as empty bullets in the first-run terminal output**
   (LOW). **fixed** (plain print, as the candidate callout does; test pinned). A regression
   from the pass 4 fix.
2. **The choice-or-open display rule is written four times and disagrees on a whitespace-only
   choice** (LOW). **declined**: reachable only on a version no gate judged, display only; a
   shared helper is a consolidation noticed in passing and belongs in the backlog if wanted.
3. **Fixed-field enforcement also runs on stored-candidate replay** (LOW). **declined**: no
   stored candidate can carry a stack row or a facet swap that the totality gate accepted
   before this range; the decision is recorded above.
4. **The format doc and plan said the candidate callout lists open and pending concerns**
   (LOW, doc). **fixed**.
5. **Step 8's detail still told the docs author that stack rows are feedback targets**
   (LOW, doc). **fixed** (step 3's text is about the embedded stage-feedback route and stays).

## Tracked

- **tracked** #465 — two optional step 6 stack-callout tests.
- **shipped** — the pre-push hook drops the repo-local git environment, so a push from a
  secondary worktree no longer lets the suite write into the shared `.git` (was #466,
  removed from the backlog).
- **shipped** — the directives' done-flip sentence now covers a replacement when the
  previous step's commit has set `status: current` (was #467, removed from the backlog).
