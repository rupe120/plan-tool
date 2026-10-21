# Structural rewrite safety backlog arc

## File intent

This file recorded the execution guide for the bounded structural-rewrite
remediation. **The arc is complete (2026-08-18); do not reopen it.** It is
kept only as the historical record of the completed route and its scope
fence — read it to confirm what shipped, not to select work.

## Details

`roadmap-structural-review-remediation` (`docs/implementation-plans/archive/2-roadmap-structural-review-remediation.md`)
is `status: completed`, progress 3/3. Its durable correction anchors are
`1dd8c4e0` (receipt-safe feedback rejection), `7854dc6d` (patchable canonical
scalar production), `d415c502` (stable evaluator isolation proof), and
`7405399c` (accurate route documentation); earlier post-run anchors
`1b7c3ef4`, `c95333e0`, `6e68b47b`, and `967f0cfd` retain the common gate,
stage-table, operation/renderer, and real-boundary test contracts.

## Choose this arc when

**Never — this route is finished.** Do not re-select it for decoder, cache,
or representation cleanup. A genuinely new need (multiline replacement
support, an alternative evaluator proof) is a separately scoped plan, not a
reopening of this one.

## Delivered route (historical record)

1. Step 1: reject any target scalar span that crosses a physical YAML line,
   including a naturally folded plain scalar emitted by the production
   renderer. **Done.**
2. Step 2: the macOS evaluator probe selects a repository-owned, non-symlink
   regular file and proves ordinary host access before its Seatbelt denial
   proves the protected-root boundary; it fails closed when no such sentinel
   exists. **Done.**
3. Step 3: every named public route guide describes bounded candidate
   construction for both admitted route classes, while only the structural
   writer refuses `requires-scope-review` at preflight. **Done.**

## Verification gates (satisfied)

- Each step's focused regression coverage landed before completion, and the
  full parallel suite passed before the plan closed.
- The scalar test uses the real renderer rather than an artificial YAML style.
- The evaluator test proves host access, link rejection, data denial, and
  metadata denial without relaxing the sandbox profile.
- The documentation sweep preserves the single-artifact write set. Candidate
  construction never implies a multi-artifact transaction.

## Exit — met

Malformed multiline targets fail closed, evaluator isolation works in a
generic repository or fails closed, and public route selection has one
accurate contract. The bounded full-plan post-run review and remediation
also completed 2026-08-18; see the plan's own reports for evidence.

## Out of scope (still binding on any future related work)

This arc never changed evidence storage, receipt semantics, snapshot binding,
roadmap stage order, or generic patch language, and a future plan touching
this area inherits the same fence.

## Related follow-up (a separate plan — not a reopening)

**2026-08-19:** auditing BACKLOG #242's bare plan surfaced a real, pre-existing
gap in the render-canonicality check this arc's `roadmap_structural_revision_patch.py`
relies on (`_require_preflight`, `_parse_canonical_candidate`): it compares
on-disk bytes to `render(parse(bytes))` and refuses on *any* mismatch, even
one that changes nothing semantically — already documented as a live
limitation at `ROADMAP_FORMAT.md:731-736`, with no operator recovery path.
#242's planned closed-row render sort would make this common in ordinary
reviewer use. **The affected surface is wider than this arc alone** — it
spans two other independently-scoped, already-archived plans too
(`roadmap-escalation-impact-routing`'s `roadmap_impact_snapshot.py`, and
`roadmap-incremental-revision`'s `roadmap_revision.py`), five enforcement
points in total. Filed as a BUG_BACKLOG RISK entry ("Every roadmap revision
route rejects a render-canonical mismatch outright..."). This is **not** a
reopening of this arc's settled scope — the fix is scoped to a shared leaf
check each of the three plans calls, never their patch/publish/proof
semantics.

**Update (2026-08-19).** The replacement plan was created —
`roadmap-canonical-source-identity` — and reached bare-plan audit before
being paused. A separate finding, traced from the first real-world `roadmap`
run failing on feedback iteration (`integration`, three failed revision attempts on
a 35 KB real artifact), shows a material share of that plan's threat model is
a consequence of stage-level revision regenerating the whole artifact rather
than applying bounded, code-owned operations — the same pattern this arc's
own `roadmap_structural_revision_patch.py` already uses safely. Full record:
[`analysis/roadmap-feedback-revision-architecture.md`](../analysis/roadmap-feedback-revision-architecture.md).
`roadmap-canonical-source-identity` was re-scoped for its remaining reader-only
work after the bounded stage-feedback route shipped. This does not reopen this
arc — structural revision's own
patch/publish/proof semantics are unaffected and were already the pattern
being generalized.

**Update (2026-08-21).** The re-scoped reader-only work is complete. #242
remains paused until the Integration receipt preflight establishes whether an
exact-pair structural retry is admitted; only then can its retention design
resume against the bounded merge layer.
