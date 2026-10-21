> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Depends On Consumes Note
intent: 'Every `depends_on` edge a plan''s step graph declares either names, in `depends_on_notes`,
  what the dependent step consumes from its antecedent, or is silently absent from
  that map (key omitted — never `{id: ""}`). The only structural check is that every
  note key is a member of the same step''s `depends_on`; whether an edge carries a
  note at all is never required, gated, scored, or graded. Turning "verify this plan''s
  cohesion" from inferring intent out of narrative into a concrete lookup a reader,
  or the shipped cohesion-ordering grounding (BACKLOG #252), can check against real
  code.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a `depends_on_notes` field to `Step` and reject a key that isn't in `depends_on`
  intent: Give every dependency edge a place to name what the dependent step consumes,
    while every plan already on disk keeps parsing untouched.
  files:
  - plan_tool/schema.py
  - tests/test_parser.py
  - tests/test_fingerprint.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/depends-on-consumes-note/01-depends-on-notes-field-step-reject-key.md
  status: done
- id: 2
  title: Carry the notes with their edges through split, merge, a scope-out's surviving-plan
    renumbering, and a carved seed's upstream-prerequisites rendering, per the fan-out/fan-in
    policy in Architecture
  intent: Keep a plan that carries notes valid after a split, merge, or carve instead
    of failing validation on keys naming ids the transform just renumbered away, and
    never let a note silently become false when an edge doesn't survive one-to-one
    — mirroring `intent`'s own "prefer absent over a quietly false carry-over" rule.
    Narrower than the split/merge/scope-out/reground scope this step started with,
    but not as narrow as the first correction made it — only the carved region's own
    internal graph (re-derived by fresh `create` synthesis, no deterministic hook)
    and `reground.py` (renders no `depends_on` at all) are excused explicitly (Architecture);
    the carved seed's upstream-prerequisites path has a real, already-existing deterministic
    remap (`_resolve_upstream_context`) and stays in scope. A threading bug anywhere
    in this policy aborts the transform via the existing dry-run `Plan` validation
    rather than silently corrupting a note — surface that abort with a diagnosable
    message, don't just let it raise raw.
  files:
  - plan_tool/create.py
  - plan_tool/scope_out.py
  - tests/test_create.py
  - tests/test_scope_out.py
  - tests/test_detail.py
  - tests/test_launcher.py
  - tests/test_fingerprint.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/depends-on-consumes-note/02-carry-notes-their-edges-through-split.md
  status: done
- id: 3
  title: Ask create's step proposal and the manual step wizard for a per-edge note,
    and drop any note key the step doesn't depend on
  intent: Let the same proposal turn that writes `depends_on` say what each edge delivers,
    with no extra question and no second round-trip; give the manual wizard's own
    `depends_on` prompt (`_ask_int_list`) a matching optional note prompt, since a
    human is already answering by hand there — unlike the Claude-free canonical path,
    which stays deliberately note-less.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  - tests/test_fingerprint.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/depends-on-consumes-note/03-ask-create-step-proposal-manual-step.md
  status: done
- id: 4
  title: Show each proposed step's `depends_on` ids and their notes in create's interactive
    step review
  intent: Put what an edge delivers in front of the operator at the moment they confirm
    or split the proposed step graph — `_ask_change_type`'s interactive review renders
    neither `depends_on` nor a note today, so both must appear together, not the note
    alone next to an already-invisible edge.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  - tests/test_fingerprint.py
  complexity: low
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/depends-on-consumes-note/04-show-each-proposed-step-depends-on-ids.md
  status: done
- id: 5
  title: Re-author the withdrawn `audit-trajectory-instrumentation` step graph as
    a notes fixture
  intent: 'Prove on the plan that motivated this work that each of its four bridging
    edges (BACKLOG #252 / `_bridging_dependency_edges` — also called cross-cluster
    in earlier prose) either states what it delivers or is visibly silent, never silently
    indistinguishable from a justified edge.'
  files:
  - tests/test_create.py
  creates:
  - tests/fixtures/withdrawn_audit_trajectory_depends_on_notes.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/depends-on-consumes-note/05-re-author-withdrawn-audit-trajectory.md
  status: done
- id: 6
  title: 'Document `depends_on_notes` in PLAN_FORMAT.md and mark BACKLOG #253 shipped'
  intent: Give a reader the field's contract and its hard fence — structural key-in-`depends_on`
    membership only; note-on-edge presence is never required or gated; note wording
    is never graded — in the one doc that owns plan frontmatter, and close out the
    backlog entry that asked for it.
  files:
  - PLAN_FORMAT.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/depends-on-consumes-note/06-document-depends-on-notes-plan-format.md
  status: done
---
# Depends On Consumes Note

## Overview

Add an optional `depends_on_notes: dict[int, str]` field to `Step`, letting a plan's step graph name, per `depends_on` edge, what the dependent step consumes from its antecedent. The field is purely additive: every key must be a member of that same step's `depends_on` (an existence-only structural validation, mirroring `depends_on`'s own id-existence check), and omitting the field entirely — the case for every existing plan — parses exactly as it does today. A silent edge omits its antecedent key from the map (never `{id: ""}` from authoring); whether an edge carries a note is never required or gated. `create`'s step-proposal round-trip may name the per-edge consumption in the same prompt turn that proposes `depends_on`, with no new question and no new round-trip. Note *wording* is never graded, scored, or gated on by any pass in this codebase — the structural key-membership check is the only checked property.

## Problem statement

`depends_on` is the only structural field in `PLAN_FORMAT.md` with no accompanying *why*: it is a bare `list[int]`, validated only for id existence, no self-reference, and no cycles — nothing asks why step 4 depends on step 1. The schema already demands a justification for a step's *existence* (`intent`) but not for its *dependencies*, and dependencies are exactly what carried the withdrawn `audit-trajectory-instrumentation` plan's false cohesion: its four bridging edges (the same fixture BACKLOG #251/#252 measured by hand) were authored purely from the seed's narrative, and no surface ever asked what any of them actually delivered. Three turned out false; the fourth ("hand-resolution feeds region closure") was a provable no-op that took until audit round 3 to catch. The result is that "verify this plan's cohesion" means inferring intent out of narrative rather than performing a concrete lookup a reader can check against real code — the shipped cohesion-ordering grounding (BACKLOG #252) orders which edges deserve that scrutiny first, by a structural file-overlap signal, but it does not itself read or verify a note's claim.

A related, narrower existing mechanism deserves a name here so it isn't mistaken for overlap: `completeness_report.py`'s `SoftEdge`/`PlanMass.soft_edges` (BACKLOG #238) scans a step's detail-body prose for markers like "ordering-only"/"test-only" naming a `depends_on_id`, recording the matched sentence as that edge's `note`. It answers a narrower question — is this edge load-bearing — than `depends_on_notes`'s "what does this edge deliver," and it is reporting-only the same way `depends_on_notes` is. This plan is deliberately separate from and does not replace that heuristic; a later change could let `_find_soft_edges` read `depends_on_notes` instead of scanning detail prose, but that is not this plan's job.

## Architecture

**The binary observable, stated once so it is never re-derived as something richer:** a `depends_on` edge either carries a note or it does not. **Silent means the antecedent key is absent from `depends_on_notes`** — never a present key with an empty string. Authoring paths (Claude proposal parser, manual wizard) omit the key on blank/silent edges; they never write `{id: ""}`. Parse-time acceptance of an empty-string value remains allowed only because note *content* is never graded (step 1), and rewrite/`exclude_defaults` plus step 4's display treat a residual empty string the same as absence (id shown, no note text). Step 5's fixture contract uses the same rule: visible silence is a missing key, not `{id: ""}`. Nothing about the note's wording, plausibility, or correctness is ever checked by any pass in this codebase.

**Field shape (a decision, not a derivation — pin it here so `detail` doesn't reinvent it):** a new optional `Step` field, `depends_on_notes: dict[int, str]`, sibling to `depends_on` rather than a restructuring of it — every key must be a member of that same step's `depends_on`, and a key that is not is a structural validation error (existence-only, mirroring `depends_on`'s own id-existence check — not a content check). `depends_on: list[int]` itself is untouched: its ids, ordering, self-reference rule, and cycle rejection all stay exactly as they are. Omitting `depends_on_notes` entirely — the case for every existing plan — parses exactly as it does today.

**Authoring:** when `create`'s step-proposal round-trip proposes a step carrying `depends_on`, the same prompt turn may also name, per edge, what that step consumes from its antecedent — no new question, no new round-trip, the same discipline `intent` already established for a step's existence. A proposed edge with no note is accepted unchanged (key omitted, not `{id: ""}`); nothing in this plan may turn a missing note into a re-prompt, a warning treated as a refusal, or a lower-quality verdict. `create --from-existing` also populates `depends_on` through a second, Claude-free path — `plan_tool/canonical.py`'s `extract_canonical_steps`, reading a canonical seed's `Depends on: N, M` line directly — and that path stays exactly as Claude-free as it is today: a plan lifted through it carries zero `depends_on_notes` by construction, deliberately, the same way any other optional field can be absent. This is not a gap step 3 closes.

A *third* path exists too, and it is not deliberately excluded: `create.py`'s manual step wizard (`prompt_steps`/`_prompt_one_step`, which runs when both the Claude proposal and canonical extraction return no steps and `--yes` is not set) already asks the operator for `depends_on` via `_ask_int_list`, with a human answering in real time — unlike the canonical path, where no human is present to ask. Step 3 adds one more optional prompt there, mirroring the Claude-proposal round-trip: "what does step N deliver to this step? (optional)". A blank answer omits the key for that edge — accepted exactly like a proposed edge with no note.

**`create --iterate` note preservation:** `_preserve_on_disk_step_fields` already carries forward same-title `intent` across re-proposal merges. Step 3 extends that helper the same way for `depends_on_notes`: when the on-disk step has notes and the new proposal **omits** the `depends_on_notes` key entirely, keep the on-disk notes; when the proposal **includes** the key (even as `{}`), use the proposal's value. Preserved notes are **intersected with the proposal step's current `depends_on`** (same orphan-key drop `_parse_steps_json` applies) — a re-proposal that drops an edge while omitting `depends_on_notes` must not restore a stale note key that would fail step 1's membership check at `write_plan`. Pin omit-vs-`{}` and shrunk-`depends_on` cases beside the existing intent-preservation tests.

A *fourth* edge-producing path is also note-less by construction and stays that way: `plan_tool/foundational_logic.py:merge_sweep_into_steps` may append a consolidation `Step` with a wired `depends_on` when the opt-in foundational sweep runs inside `create`'s proposal path. Like canonical extraction, it never invents `depends_on_notes`; documenting the carve-out here is the whole obligation — do not teach the sweep to author notes.

**The trap this must not fall into (name it so it cannot be quietly reintroduced later).** A justification string invites the same prose-conformance failure that killed the `change_type` test-ordering contract (~85% false positives, CLAUDE.md § "Withdrawn: the per-`change_type` test-ordering contract"): a model will cheerfully write a plausible-sounding reason for a genuinely vacuous edge. The note's existence proves a question was asked; it does not and cannot prove the coupling is real. BACKLOG #252's shipped grounding orders which edges deserve scrutiny first, by a structural file-overlap signal — it never reads note text. Automatically checking a note's *named* claim against actual code is unbuilt future work, not something #252 already performs and not something this plan builds either.

**Fan-out/fan-in policy under structural edits — mirrors `PLAN_FORMAT.md`'s existing `intent`-under-mutation table and its governing rule, "prefer absent over a quietly false carry-over":**

| Verb | Rule |
|---|---|
| split | never copy an edge's note onto the surviving repointed edge — `_apply_step_split`'s remap always repoints an external dependent to exactly one id (the *terminal* replacement), and a note written for the whole target cannot be trusted on that one edge. Separately: always set `depends_on_notes={}` on **both** replacement halves in the transform's `model_copy` (HEAD today only overwrites `id`/`depends_on`/`status`, so proposer-supplied notes would otherwise survive), and forbid `depends_on_notes` in `_propose_step_split`'s JSON contract beside the existing `depends_on` forbid — the transform owns wiring, not the model |
| merge (outbound) | keep the merged step's collapsed edge note only when every merging member **that depended on that antecedent** carried identical note text (`_apply_step_merge` unions members' external `depends_on` onto one edge); members with no edge to that antecedent are out of the vote. Otherwise clear it |
| merge (inbound) | the same rule in the opposite direction — when an external dependent's several edges into the merge set collapse onto one survivor id (`_remap_external`'s `dict.fromkeys` dedup), keep that dependent's note only if every collapsing edge carried identical note text; otherwise clear it |
| scope-out (surviving plan) | `scope_out.py`'s narrowing renumbers the *remaining* plan's `id`/`depends_on` after a carve exactly like split/merge do for their survivors — covered by the "any renumbering elsewhere" row below, not a separate mechanism |
| scope-out (carved seed's upstream prerequisites) | `_resolve_upstream_context` already deterministically walks each carved step's *external* `depends_on`, drops in-region edges, and remaps every survivor through the narrow's own old-id→new-id map into `(id, title, status)` triples that `_upstream_block` renders as "Upstream prerequisites" in both `render_carved_seed` and `render_carved_region_seed` (split into **done** and **external** sections — notes render in both when present). Extend that tuple with the carved step's note for the edge and render it there too — a real, existing deterministic hook, unlike the carved region's own internal graph below. When several carved steps share one external prerequisite, keep today's first-seen `dep_id` dedupe: the first carved step that contributes that dep wins for title *and* note (including "no note" if that first step has none) — a later carved step's note for the same dep never overrides. Do not invent unanimous-or-prefer-absent logic that title lacks |
| any renumbering elsewhere | every renumbering site (`_apply_step_split`'s and `_apply_step_merge`'s surviving-step `model_copy`, `scope_out.py`'s narrowing) today updates `id` and `depends_on` together but leaves `depends_on_notes` keys unmapped — so after a split/merge/carve elsewhere in the plan, a survivor whose *own* edges were not the transform target still holds stale pre-renumber note keys and fails step 1's existence check. Step 2's job is to thread `depends_on_notes` through the exact same old-id→new-id map already computed for `depends_on`, for every survivor, not only the steps the transform names directly |

**Explicitly excluded — no deterministic mechanism to hook into, the same way the canonical-extraction path is already excused:** the *carved region's own internal graph only* — edges between two steps carved out together are never a structural `depends_on` copy (`render_carved_seed` renders no such copy for them), because that graph is re-derived by a fresh `create --from-existing` synthesis pass, not a deterministic transform. (The carved seed's *upstream prerequisites* are a different, already-deterministic path — see the table row above, now in scope.) Also excluded: `plan_tool/reground.py`'s `render_rebaseline_seed`, which renders no `depends_on` edges at all today (only `intent`/`concept_ids` per step). Threading a note into either excluded case is future work, not this plan's.

**The real failure mode when a fan-out/fan-in rule has a bug, stated precisely rather than assumed.** Step 1's existence-only validator runs inside the dry-run graph construction each transform already performs. A note-threading bug that leaves a stale or unmapped key does not quietly lose or misdescribe a note — it fails that validation and **aborts the whole structural edit**. The abort surface differs by verb, matching HEAD today and what step 2 must keep diagnosable: `_apply_step_split` / `_apply_step_merge` wrap the failure as `CreateError` carrying `_summarize_step_graph_error` text; `scope_out.py:compute_narrow` today uses bare `Plan.model_validate(...)` (an uncaught Pydantic `ValidationError`), and step 2 wraps that the same way as a `NarrowError` (or equivalent narrow refusal) carrying the same summarized validator text — never leave scope-out as a raw traceback while split/merge get a clean message. No verb ever *invents* a note to fill a gap it creates, and a threading bug is loud, not silent — it blocks the command rather than corrupting a note. Callers of `_apply_step_split` / `_apply_step_merge` inherit the same abort without a second wrapper: `plan-tool split`/`merge`, `detail.py:split_step`/`merge_steps`, `create`'s interactive review split, and `launcher.py:escalate_to_split` (the mid-run bridge).

**In scope:** `plan_tool/schema.py` (the new `Step` field and its existence-only validator), `PLAN_FORMAT.md` (documented; verified by hand — that doc owns authored plan frontmatter, and unlike `DATA_CONTRACT.md` it has no automated field-coverage drift guard at HEAD), `create`'s step-proposal prompt, the manual step wizard, and step parsing/review, `plan_tool/scope_out.py` (surviving-plan renumbering and the carved seed's upstream-prerequisites rendering, per the fan-out/fan-in table), tests. **`DATA_CONTRACT.md` is not in scope** — it owns persisted runtime sidecars, not plan frontmatter; `depends_on_notes` is documented in `PLAN_FORMAT.md` only. **Not in scope:** `plan_tool/reground.py` and the carved region's own internal graph — see Architecture's explicit exclusion.

**Purity-cache neutrality.** `plan_tool/fingerprint.py` hashes `step.depends_on` into the purity-cache key as verdict-affecting frontmatter, while deliberately excluding `title`/`complexity` because they don't affect the verdict. `depends_on_notes` joins the **excluded** set: it is metadata about an edge's rationale, never something a step's own code changes, so a note-only edit must leave the cached purity key unchanged.

**Source entry:** BACKLOG #253. This plan inherits its scope contract verbatim; its final docs/status step marks BACKLOG #253 shipped, citing the commit.

## References

- [Pydantic v2 — Fields](https://docs.pydantic.dev/latest/concepts/fields/) — Covers optional fields, `Field(default_factory=dict)`, and alias/default semantics — the exact shape needed to add `depends_on_notes: dict[int, str]` to `Step` without changing how existing plans parse.
- [Pydantic v2 — Validators](https://docs.pydantic.dev/latest/concepts/validators/) — Documents `field_validator` and `model_validator(mode="after")`, which is the mechanism for the existence-only cross-field check that every note key is a member of the same step's `depends_on`.
- [Pydantic v2 — Serialization](https://docs.pydantic.dev/latest/concepts/serialization/) — Explains `exclude_defaults`/`exclude_none` and round-trip dumping, which is what keeps a plan with no `depends_on_notes` rewriting byte-identically to today.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — The reference for `safe_load`/`safe_dump` and the YAML↔Python type mapping, including how mapping keys are resolved to `int` — relevant because the new field is an int-keyed mapping in frontmatter.
- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — Primary spec for mapping-key rules and core-schema scalar resolution, worth checking when frontmatter gains a block mapping whose keys are bare integers rather than strings.
- [Python `typing` — standard library reference](https://docs.python.org/3/library/typing.html) — Authoritative reference for `Optional[...]` and builtin generic annotations such as `dict[int, str]`, matching the annotation style already used in `plan_tool/schema.py`.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Requiring `depends_on_notes` on existing plans — 99+ plans with no note stay valid, unmodified, forever if never touched again.
- Any validation of a note's *content*: wording, length, plausibility, or whether it is actually true.
- Any gate, exit-code flip, refusal-to-advance, or lowered severity keyed on a note's presence or absence.
- Changing `depends_on`'s own semantics, ordering, self-reference rule, or cycle detection.
- Retroactively adding notes to any plan already on disk, including the withdrawn `audit-trajectory-instrumentation` plan itself (its own archived frontmatter is history, not a rewrite target).
- Any weighting of "edges with a note" vs. "edges without" in materiality or severity calibration — a possible future use, not this seed's.

## Risks

- **Durable-contract growth.** A new frontmatter field is a permanent contract this plan documents in `PLAN_FORMAT.md` (verified by hand — no automated drift guard exists for that doc). Grows every future plan file that uses it modestly. Accepted cost for a field that is optional and additive.
- **The trap above, if a later change quietly starts grading the note.** Any future finding proposing content-checking, plausibility-scoring, or a gate on this field is invalid per this seed's own fence, not a gap to fill — route it back to this document, not applied as plan expansion.

## Testing

- `depends_on_notes` parses when every key is a member of the step's `depends_on`; a key naming an id absent from `depends_on` is rejected.
- Omitting `depends_on_notes` on 99+ existing plan fixtures parses byte-identically to today (backward-compat fixture).
- `create`'s step-proposal round-trip: a proposed step with a `depends_on` edge and a note renders the note into the written plan frontmatter verbatim; a proposed step with `depends_on` and no note is accepted unchanged — no re-prompt, no refusal.
- `PLAN_FORMAT.md` documentation for the new field is verified by hand at review time — no automated guard exists for that doc (`DATA_CONTRACT.md`'s registry-driven checks do not apply: plan frontmatter is outside that doc's scope).
- Fixture verification (this seed's scope-contract requirement): re-author the withdrawn `audit-trajectory-instrumentation` plan's step graph as a test fixture — its four bridging edges (4→1, 4→2, 4→3, 5→1; also called cross-cluster in earlier prose) either state what they deliver or are left visibly silent (absent key, never `{id: ""}`), with the fixture demonstrating both outcomes (three annotated, one silent), never silently indistinguishable from a justified edge.
- **(step 4) Interactive step review:** a proposed step's `depends_on` ids are rendered alongside any note for each edge; an edge with no note still renders its id. A residual empty-string note value (parse-only; authoring never writes one) displays as silent — id only, no empty quote. This review renders neither today — the baseline gap this step closes.
- **(step 1) Purity-cache neutrality:** a `depends_on_notes`-only edit to a step leaves `fingerprint.py`'s cached purity-verdict key byte-identical — proving the field joined the deliberately-excluded set (`title`/`complexity`), not the hashed `depends_on` set.
- **(step 1) Never-graded regression check:** a coarse sweep asserting every reference to `depends_on_notes` outside `schema.py` and `create.py`'s authoring path only *reads* or *carries* the field — never scores, ranks, or gates on it. Trivially true when step 1 lands (no consumer exists yet) and must stay green as steps 2–6 add real ones — the test that would fail if a later change quietly wired the note into a scoring or gating path (the exact failure mode CLAUDE.md's "Withdrawn: the per-`change_type` test-ordering contract" section records); a "deliberately not" claim in prose alone is not enforced. Owned by step 1, not step 6, which is `change_type: non-code` with no test file to carry it. **Each later step that adds a legitimate `depends_on_notes` reference under `plan_tool/` extends that allowlist in `tests/test_fingerprint.py` in the same change** (steps 2, 3, and 4 as each lands) — Deferred prose alone is not enough.
- Split/merge/scope-out fan-out/fan-in policy (Architecture): a split never copies a note onto a repointed inbound edge, always sets `depends_on_notes={}` on both replacement halves (transform-owned, not proposer-owned), and forbids the field in `_propose_step_split`'s JSON; merge outbound keeps a note only when every merging member that declared that edge carried identical text (else clear); merge inbound keeps a note only when every collapsing edge an external dependent holds into the merge set carried identical text (else clear); every renumbering site (including a scope-out's surviving-plan narrowing) threads `depends_on_notes` through the same id-remap `depends_on` gets, for every survivor, even when that step's own edges aren't the ones being transformed; and a carved seed's upstream-prerequisites rendering (`_upstream_block`) carries each surviving edge's note through `_resolve_upstream_context`'s existing remap (done and external sections). Coverage includes the production callers of `_apply_step_split` that inherit the policy without a second wrapper — at least `detail.py:split_step` (already end-to-end tested) and `launcher.py:escalate_to_split` (add a focused test proving mid-run escalate inherits the same note fan-out / abort rules).
- Negative-space fixture: the carved region's own internal graph, a `reground` run, **canonical extraction** (`extract_canonical_steps` / `extract_steps_from_canonical`), and the foundational-logic consolidation path (`merge_sweep_into_steps`) each leave `depends_on_notes` empty / untouched — proving those exclusions are real, not merely unstated. (The carved seed's upstream prerequisites are *not* part of this negative-space fixture — they're in scope per the Architecture table.)
- Abort-path coverage: a `depends_on_notes` threading bug that leaves a stale or unmapped key fails dry-run graph validation and aborts — `CreateError` with `_summarize_step_graph_error` text on split **and** merge, and a `NarrowError` (or equivalent narrow refusal) carrying the same summarized text on scope-out after step 2 wraps `compute_narrow`'s bare `Plan.model_validate` — covered by a dedicated stale-key abort test per verb, not left as an unverified side effect of step 1's validator.
- (step 3) The manual step wizard's new optional per-edge note prompt: a blank answer omits the key (no `{id: ""}`), mirroring the Claude-proposal round-trip's silent-edge behavior.
- (step 3) `create --iterate` note preservation: same-title re-proposal that **omits** `depends_on_notes` keeps on-disk notes intersected with the proposal's `depends_on`; proposal that sends `{}` clears them; a shrunk `depends_on` never restores orphan note keys.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A plan authored via `plan-tool create` can carry a per-`depends_on`-edge note naming what the dependent step consumes from its antecedent.
- Omitting a note is valid and produces no gate, warning-as-refusal, or exit-code change anywhere in the pipeline — silent edges omit the antecedent key (never `{id: ""}` from authoring).
- No pass in this codebase grades, scores, or checks a note's content for plausibility — key-in-`depends_on` membership only; note-on-edge presence is never required or gated.
- Every existing plan with no `depends_on_notes` field remains valid, unmodified.
- A split, merge, or scope-out that changes an edge's endpoints follows the Architecture fan-out/fan-in table exactly — a note never survives onto an edge it no longer accurately describes; a threading bug aborts with diagnosable `CreateError` (split/merge) or `NarrowError` (scope-out), not a raw pydantic traceback.
- `create`'s interactive step review renders every proposed step's `depends_on` ids together with any note it carries — for edges with a note and edges without.
- The withdrawn `audit-trajectory-instrumentation` step graph is re-authored as `tests/fixtures/withdrawn_audit_trajectory_depends_on_notes.md` with its four bridging edges (4→1, 4→2, 4→3, 5→1): three annotated with consumption notes and one visibly silent (absent key), so both first-class outcomes appear in the motivational fixture.
- Each step that adds a legitimate `depends_on_notes` reference under `plan_tool/` extends step 1's never-graded allowlist in `tests/test_fingerprint.py` in the same change.
- A same-title `create --iterate` re-proposal keeps on-disk `depends_on_notes` when it omits the key, drops them when the proposal sends `{}`, and never restores keys for antecedent ids no longer in `depends_on`.
- This plan's final step marks BACKLOG #253 shipped, citing the landing commit.

## Deferred

- Automatically checking a note's named claim against real code — BACKLOG #252's shipped grounding orders which edges get scrutiny by a structural file-overlap signal regardless of whether a note exists, but it never reads note text; comparing a note's stated claim to code is unbuilt future work, not a trivial extension of #252.
- Any future weighting curve for materiality/severity calibration keyed on note presence.
- Backfilling notes onto any plan already on disk.
