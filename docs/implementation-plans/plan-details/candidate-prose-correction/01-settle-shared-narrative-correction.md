# Step 1 — Settle the shared-narrative correction contract in ROADMAP_FORMAT.md

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step writes the contract for correcting an existing shared narrative block in a roadmap artifact through candidate feedback. It edits only `ROADMAP_FORMAT.md`. The contract defines a shared span and its owning set, how authority binds to the issued span, the refusal values, which typed-row operations may share a candidate, the application order, and the one body state the gates see. It also fixes how a retained removed-row reference is treated, the byte ceiling, and the routes that carry the operation. On green, steps 2–6 can build against fixed definitions. The step also checks the stop condition: if the widened span cannot be defined without authority beyond the named block, work stops and goes to the user.

## Table of Contents

- [Why](#why) — what the doc cannot say today and why it must be settled first
- [Input](#input) — the landed code and doc facts the contract builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the one doc edited
- [Implementation](#implementation) — the decisions to write down and the stop check
- [Tests](#tests) — non-code verification
- [Acceptance criteria](#acceptance-criteria) — observable doc properties
- [References](#references) — standards relevant to span and byte definitions
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to later steps

## Why

`ROADMAP_FORMAT.md` § "Reviewer feedback and candidate lifecycle" says `CandidateAddRow` is the only candidate operation with row-owned prose authority. It also says replacement and removal have no candidate prose-edit authority. Issued spans carry exactly one `row_id`: `plan_tool/roadmap_revision.py:StageProseSpan` and `project_row_owned_prose_spans` skip any block that names a second live row. So a stale paragraph naming several rows cannot be corrected without a typed-row change. Steps 2–7 each depend on a decision about span ownership, authority, ordering, or the gate state. Settling these in the format doc first stops code from deciding them by accident.

## Input

- **Span issuance today:** `plan_tool/roadmap_revision.py:project_row_owned_prose_spans` issues a span only when exactly one selected, unambiguous live row id appears in a blank-line block (`_prose_blocks`) and no other live id does. `stage_prose_span_id` hashes the single `row_id` and the block text. `_select_row_owned_prose_spans` is the local revision selector and stays narrow (step 3 owns that).
- **Application precedent:** `plan_tool/roadmap_revision_patch.py:_apply_stage_prose_amendments` splices exact spans, refuses overlap with "stage prose amendments overlap", requires a nonempty trimmed replacement for edits, treats removal as a separate delete operation, and then appends add-row fragments through `append_row_prose_fragments`. Step 2 extracts the splice. This step only states the contract.
- **Candidate side today:** `plan_tool/roadmap_candidate.py:CandidateAddRowProseAmendment` carries `{row_id, fragment}`. Its parser, `_parse_add_row_prose_amendment`, bounds the fragment by `plan_tool/project_config.py:HARD_MAX_PROSE_AMENDMENT_BYTES` (4 KiB, UTF-8 bytes).
- **The gate:** `plan_tool/roadmap_gates.py:check_inventory_has_prose` requires every prose-inventory row id to appear as a whole token somewhere in the body. It never judges prose quality.
- **Doc layout:** the contract belongs in § "Reviewer feedback and candidate lifecycle", next to the add-row prose paragraphs. The § "The prose body" candidate-additions paragraph needs a pointer to it. Step 8 syncs the doc to landed symbols; this step names code symbols only if they already exist at HEAD. Symbols that steps 3–7 will create are named by module path only.
- **Limit on verification:** no code exists for the new operation yet. Nothing here can be checked against a running implementation.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — add a subsection under § "Reviewer feedback and candidate lifecycle" holding the contract below. Add a one-line pointer from § "The prose body". Leave the existing add-row-only sentence in place; step 8 replaces it once the code lands.

## Implementation

Write each item below as a stated rule in the new subsection. Wording and exact heading are the implementer's choice. Plain-language rules with the reason beside each are enough. One way: a short mapping table for the refusal values and a numbered list for the application order.

**1. Shared span and owning set**
- A **shared span** is one blank-line-delimited non-blank block of the predecessor body, using the same block definition as `_prose_blocks`.
- Its **owning set** is the full set of live rows whose ids appear in the block as whole tokens, using the same token rule as `contains_whole_row_id`. Live means present in the predecessor artifact's design rows.
- A span whose owning set has one row is the legacy single-row span. It must load and behave unchanged, and it is a valid correction target: an owning set of one is a valid owning set. A block naming one live row plus a removed-row reference is the common stale-paragraph case after a row removal, so it must not be excluded.
- A span is **issued only when every live row in its owning set is visible in the candidate context**. If any is not visible, the span is not issued, because the interaction refusal below cannot be checked. Do not issue a partial span.
- A reference to a **removed** row (an id in the block that is not a live row) does not join the owning set and is not required of it.
- The span-id binding must cover the whole owning set and the block text. The representation in context is for step 3 to choose; the contract states only what the binding must cover.

**2. Authority binding**
- A correction is authorized only by an issued span. A reference to a removed row never grants authority, and an omitted amendment is never read as a deletion.
- Each correction binds to: the predecessor version, the artifact key, the span's exact source text and its digest, the admitted feedback, and the owning-set row ids.
- State that a removed-row reference is not part of the binding: it never expands the owning set and grants no authority.

**3. Replacement and removal**
- Replacement must be nonempty trimmed text, as in `_apply_stage_prose_amendments`.
- Removal is never an empty replacement; the candidate correction offers no delete operation, and the stage revision path's delete amendment is unchanged.
- The doc states the choice at the contract level and leaves the operation's record shape to step 4. A candidate batch does not adopt the stage-revision one-material-operation rule. One feedback item may carry a correction beside its other operations.

**4. Refusal list**
Give each value one sentence of meaning. A refusal publishes no candidate.
- **unknown** — the span id names no issued span.
- **ambiguous** — the span id cannot select exactly one issued span.
- **stale** — the span's bound predecessor version, text, or digest no longer matches the source.
- **duplicate** — two corrections target the same span.
- **overlapping** — two corrections cover intersecting byte ranges.
- **oversized** — the replacement exceeds the byte ceiling below.
- **unauthorized** — the span was not issued for the admitted feedback, or the correction relies on authority from a removed-row reference.
- Also state two further refusals that this contract introduces: **owning-set interaction** (item 5) and **gate failure** (item 7). Say whether each reuses a value above or is named separately. The rule is to name them separately, so an operator can tell them apart.

**5. Interaction with typed-row operations**
- A correction is refused when the same candidate adds, edits, or removes any row in its owning set.
- The owning set is computed from the predecessor's live rows only. Naming a row the same candidate adds is allowed because an added row is never in the owning set; an add of an id already in the owning set is refused. Issuance, application, and replay all use that one computation.
- Operations on rows outside the owning set may share the candidate.
- A correction may name a row the same candidate adds, because its add-row append is part of the body state in item 7. That row is not in the owning set (it is not live in the predecessor), so the interaction refusal does not fire for it.

**6. Application order**
- One order, used by issuance, application, and replay: (1) splice every correction into the predecessor body at its issued span, (2) append add-row fragments after the corrected body.
- Body text outside the issued spans and the frontmatter delimiters stays unchanged.

**7. The one body state the gates see**
- The existing artifact gates, `check_inventory_has_prose` included, run against the **final candidate body**: corrections applied and the same candidate's add-row appends included.
- That one state is used at issuance, application, and replay. A stored candidate therefore replays to the accept or refuse result it had when published.
- If the corrected body fails the gates, no candidate is published. Example failure: a live row's only description dropped. The gates (`check_inventory_has_prose`) do not check that prose references resolve to known rows, and this step adds no such check.
- A retained removed-row reference gets no special handling. The correction neither must remove it nor is exempt, and the existing gates decide.
- State that no gate is weakened and no candidate-only exception is added.

**8. Byte ceiling**
- Ceiling on each correction's replacement text, in UTF-8 bytes. Recommended value: the same 4 KiB as `HARD_MAX_PROSE_AMENDMENT_BYTES`, defined directly for candidates in step 4.
- State plainly that the value is candidate-local and measured on encoded bytes, as the add-row fragment ceiling is.
- Do not add a project-config knob.

**9. Routes**
- **Carries it:** the batch candidate route (`plan_tool/prompts/roadmap-candidate-delta.md`, step 5) and the edit route, which stores a replacement candidate. Any edit requires a fresh approval. Step 7 confirms the edit route carries the operation.
- **Does not carry it:** the selector-era prompt, and the local stage-revision selector, which stays narrow.
- **Fallback:** discarding and re-running the same batch is the fallback only if the edit route cannot carry the operation.

**10. Stop condition**
- Before finishing, check that the shared-span definition grants authority only over the named block. A correction replaces one issued block's bytes and nothing outside it.
- If the definition needs authority beyond that (for example, spans that cross blocks or are selected by marker), stop and raise it with the user. Do not paper over it in the doc.

## Tests

### Verification (non-code step)

This step changes no production code, and the test-authoring gate does not apply, because it keys on `change_type` and fires only for `feature` and `refactor`. The substitute checks are:

1. Read `ROADMAP_FORMAT.md` and confirm each of items 1–10 has an explicit rule. Confirm the refusal values each carry a meaning sentence.
2. `rg -n 'HARD_MAX_PROSE_AMENDMENT_BYTES|contains_whole_row_id|_prose_blocks|check_inventory_has_prose|StageProseSpan' ROADMAP_FORMAT.md` — every symbol the new text cites exists at HEAD (`rg` each in `plan_tool/`).
3. Confirm symbols that steps 3–7 create appear by module path only, not by function name.
4. Confirm no raw line numbers appear in the new text.
5. Confirm the new text does not contradict the existing "Replacement and removal operations have no candidate prose-edit authority" sentence in a way a reader would miss. Either the sentence is left for step 8 with an explicit note that the new subsection extends it, or it is qualified in place.
6. Confirm the rules for items 1, 5, and 7 are mutually consistent, with the owning set defined once and referenced elsewhere.
7. Confirm any relative links added resolve to real files.
8. `git status` shows only `ROADMAP_FORMAT.md` changed.

## Acceptance criteria

- `ROADMAP_FORMAT.md` states the shared-span definition and owning set, and that a span is issued only when every live row in its owning set is visible in the candidate context.
- It states that a removed-row reference neither joins nor is required of the owning set and never grants authority.
- It lists every refusal value with its meaning, and a refusal publishes no candidate.
- It states that a correction is refused when the same candidate adds, edits, or removes any row in its owning set.
- It states that the owning set is computed from the predecessor's live rows only, and that naming a row the same candidate adds is allowed.
- It states the application order: corrections first, add-row appends second, the same at issuance, application, and replay.
- It states the one body state for gates, including the same candidate's add-row appends, and that a failing corrected body publishes no candidate.
- It states that replacement is nonempty trimmed text and that removal is never an empty replacement (the candidate correction offers no delete).
- It states the candidate-local byte ceiling, unit and value.
- It lists which routes carry the operation, including the edit route requiring fresh approval, and which do not.
- Verification checks 1–8 pass.
- If the stop condition fires, the step ends with the question raised to the user instead of a settled contract.

## References

- [CommonMark Spec — defines paragraphs and fenced code blocks; read it to keep the shared block definition aligned with the blank-line rule in `_prose_blocks`.](https://spec.commonmark.org/)
- [RFC 3629 — UTF-8 — read it for the byte-ceiling unit, since the ceiling counts encoded bytes.](https://www.rfc-editor.org/rfc/rfc3629)
- [hashlib — SHA-256 digest API — the source-text digest the authority binding names.](https://docs.python.org/3/library/hashlib.html)

## Applicable guardrails

- **The plan's "## Scope guardrails" and "## Out of scope", arbitrary body replacement and marker-based editing:** the contract defines span authority narrowly. It states no rule that edits arbitrary body text, selects spans by marker, or relaxes the described-row gate.
- **The same sections, stale-row authority:** the contract states in item 2 that a removed-row reference never grants authority, and in item 7 that it gets no special gate handling.
- **The same sections, Group 4 and IPPT-19:** the doc text does not rewrite accepted Group 4 feedback and does not describe a contradiction-detection layer.
- **The plan's "## Architecture", stop condition:** item 10 applies it. This step is where that check runs.
- **The plan's `files:` list for this step:** only `ROADMAP_FORMAT.md` is edited. Code symbols for later steps are named by module path only.

## Deferred

- Implementing the shared-span issuance and the context representation of the owning set — step 3.
- Extracting the exact-span splice and overlap helper — step 2.
- The operation record, parser, diagnostics, and byte-ceiling enforcement in code — step 4.
- Prompt changes for the batch route — step 5.
- Persistence, replay, and interrupted-publication recovery — step 6.
- Review display, stack digest, and edit-route confirmation — step 7.
- Structured comparison evidence — carved to BACKLOG #436.
- Replacing the add-row-only prose-authority sentence, syncing to landed symbols, and removing the IPPT-18 stub — step 8.
- Narrative-consistency review evidence (IPPT-19) — out of the plan.
