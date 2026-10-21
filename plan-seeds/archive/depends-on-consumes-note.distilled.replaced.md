> **Replaced**: this file has been superseded by `docs/implementation-plans/2-depends-on-consumes-note.md`.
> Preserved here for history; do not edit.

## Overview

Add an optional `depends_on_notes: dict[int, str]` field to `Step`, letting a plan's step graph name, per `depends_on` edge, what the dependent step consumes from its antecedent. The field is purely additive: every key must be a member of that same step's `depends_on` (an existence-only structural validation, mirroring `depends_on`'s own id-existence check), and omitting the field entirely — the case for every existing plan — parses exactly as it does today. `create`'s step-proposal round-trip may name the per-edge consumption in the same prompt turn that proposes `depends_on`, with no new question and no new round-trip. The single checked property is presence: the note's wording, plausibility, and correctness are never graded, scored, or gated on by any pass in this codebase.

## Problem statement

`depends_on` is the only structural field in `PLAN_FORMAT.md` with no accompanying *why*: it is a bare `list[int]`, validated only for id existence, no self-reference, and no cycles — nothing asks why step 4 depends on step 1. The schema already demands a justification for a step's *existence* (`intent`) but not for its *dependencies*, and dependencies are exactly what carried the withdrawn `audit-trajectory-instrumentation` plan's false cohesion: its four bridging edges (the same fixture BACKLOG #251/#252 measured by hand) were authored purely from the seed's narrative, and no surface ever asked what any of them actually delivered. Three turned out false; the fourth ("hand-resolution feeds region closure") was a provable no-op that took until audit round 3 to catch. The result is that "verify this plan's cohesion" means inferring intent out of narrative rather than performing a concrete lookup a reader — or the shipped cohesion-ordering grounding (BACKLOG #252) — can check against real code.

## Architecture

**The binary observable, stated once so it is never re-derived as something richer:** a `depends_on` edge either carries a note or it does not. Nothing about the note's wording, plausibility, or correctness is ever checked by any pass in this codebase.

**Field shape (a decision, not a derivation — pin it here so `detail` doesn't reinvent it):** a new optional `Step` field, `depends_on_notes: dict[int, str]`, sibling to `depends_on` rather than a restructuring of it — every key must be a member of that same step's `depends_on`, and a key that is not is a structural validation error (existence-only, mirroring `depends_on`'s own id-existence check — not a content check). `depends_on: list[int]` itself is untouched: its ids, ordering, self-reference rule, and cycle rejection all stay exactly as they are. Omitting `depends_on_notes` entirely — the case for every existing plan — parses exactly as it does today.

**Authoring:** when `create`'s step-proposal round-trip proposes a step carrying `depends_on`, the same prompt turn may also name, per edge, what that step consumes from its antecedent — no new question, no new round-trip, the same discipline `intent` already established for a step's existence. A proposed edge with no note is accepted unchanged; nothing in this plan may turn a missing note into a re-prompt, a warning treated as a refusal, or a lower-quality verdict.

**The trap this must not fall into (name it so it cannot be quietly reintroduced later).** A justification string invites the same prose-conformance failure that killed the `change_type` test-ordering contract (~85% false positives, CLAUDE.md § "Withdrawn: the per-`change_type` test-ordering contract"): a model will cheerfully write a plausible-sounding reason for a genuinely vacuous edge. The note's existence proves a question was asked; it does not and cannot prove the coupling is real — that remains BACKLOG #252's job, checking the note's *named* claim against actual code, never this seed's.

**In scope:** `plan_tool/schema.py` (the new `Step` field and its existence-only validator), `PLAN_FORMAT.md` (documented, with its own drift-guard coverage), `create`'s step-proposal prompt and step parsing/review, `DATA_CONTRACT.md` if the field's persisted shape needs a row there, tests.

**Source entry:** BACKLOG #253. This plan inherits its scope contract verbatim; its final docs/status step marks BACKLOG #253 shipped, citing the commit.

## Out of scope

- Requiring `depends_on_notes` on existing plans — 99+ plans with no note stay valid, unmodified, forever if never touched again.
- Any validation of a note's *content*: wording, length, plausibility, or whether it is actually true.
- Any gate, exit-code flip, refusal-to-advance, or lowered severity keyed on a note's presence or absence.
- Changing `depends_on`'s own semantics, ordering, self-reference rule, or cycle detection.
- Retroactively adding notes to any plan already on disk, including the withdrawn `audit-trajectory-instrumentation` plan itself (its own archived frontmatter is history, not a rewrite target).
- Any weighting of "edges with a note" vs. "edges without" in materiality or severity calibration — a possible future use, not this seed's.

## Risks

- **Durable-contract growth.** A new frontmatter field is a permanent, drift-guarded contract (`PLAN_FORMAT.md`, possibly `DATA_CONTRACT.md`) and grows every future plan file that uses it modestly. Accepted cost for a field that is optional and additive.
- **The trap above, if a later change quietly starts grading the note.** Any future finding proposing content-checking, plausibility-scoring, or a gate on this field is invalid per this seed's own fence, not a gap to fill — route it back to this document, not applied as plan expansion.

## Testing

- `depends_on_notes` parses when every key is a member of the step's `depends_on`; a key naming an id absent from `depends_on` is rejected.
- Omitting `depends_on_notes` on 99+ existing plan fixtures parses byte-identically to today (backward-compat fixture).
- `create`'s step-proposal round-trip: a proposed step with a `depends_on` edge and a note renders the note into the written plan frontmatter verbatim; a proposed step with `depends_on` and no note is accepted unchanged — no re-prompt, no refusal.
- `PLAN_FORMAT.md`'s own doc-drift guard covers the new field the same way it covers every other documented frontmatter key.
- Fixture verification (this seed's scope-contract requirement): re-author the withdrawn `audit-trajectory-instrumentation` plan's step graph as a test fixture — its four cross-cluster edges (4→1, 4→2, 4→3, 5→1) either state what they deliver or are left visibly silent, never silently indistinguishable from a justified edge.

## Acceptance criteria

- A plan authored via `plan-tool create` can carry a per-`depends_on`-edge note naming what the dependent step consumes from its antecedent.
- Omitting a note is valid and produces no gate, warning-as-refusal, or exit-code change anywhere in the pipeline.
- No pass in this codebase grades, scores, or checks a note's content for plausibility — existence and id-resolution only.
- Every existing plan with no `depends_on_notes` field remains valid, unmodified.
- This plan's final step marks BACKLOG #253 shipped, citing the landing commit.

## Deferred

- Automatically checking a note's named claim against real code — that remains BACKLOG #252's job (already shipped), which orders its grounding by bridging edges regardless of whether a note exists yet.
- Any future weighting curve for materiality/severity calibration keyed on note presence.
- Backfilling notes onto any plan already on disk.
