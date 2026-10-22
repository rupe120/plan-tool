# Concept-sync H1 boundary preservation

| Item | Record |
| --- | --- |
| Base | `702c767c8`, merged PR #144 |
| Branch | `fix/concept-sync-h1-boundaries` |
| Scope | BUG_BACKLOG “Concept sync deletes an unowned H1 after an owned H2” |
| Route | Bounded parser boundary correction |
| Current state | Complete: 15,118 tests pass; two independent final clean Claude Code reviews |

## Property and pre-edit sites

Invariant: replacing an owned H2 body stops at the same real H1/H2 boundary as reading it, preserving every unowned slice including H1 headings and content. Keep existing raw LF/CRLF/CR offsets and opt-in fence semantics.
Identifier search: replace_body_sections is consumed by concept_sync.synchronize_concepts only; parse_body_sections supplies its owned-section comparisons. parser._real_h2_matches selects replaceable headings, while parse_body_sections's higher_matches supplies H1/H2 body ends. Tests mirror parser and concept_sync.
Vocabulary search: H1/H2, boundaries, unowned, fenced in parser/concept_sync and their tests confirms that the reader ends at H1/H2 but replacement ends only at the next H2. Share the reader's existing boundary matcher with replacement; preserve its whitespace semantics and source offsets rather than add another recognizer.
Excluded: concept decision rendering/ownership, plan/frontmatter serialization, publication/rollback, scope selection, append policy and broader Markdown parsing. No change to the default opt-in fence behavior or unmatched-fence policy.

The reader's existing matcher is shared with replacement. H2 selection,
normalization, default fence behavior and owned-section rendering stay the same.
Replacement uses original source slices around H1/H2 boundaries; no text
normalization is added.

## Verification

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

## Claude Code review 1

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

## Claude Code review 2 and convergence

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
