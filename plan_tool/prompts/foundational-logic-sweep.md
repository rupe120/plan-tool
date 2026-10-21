# Foundational-logic sweep

You are doing one focused job: find where a plan's **foundational logic**
already lives elsewhere in this codebase. This is a *divergent, repo-wide*
search — fan out across the tree; do not converge on a single file.

Use only checked-in project documentation and the code itself — do not consult
LLM-specific guidance files (e.g. CLAUDE.md, AGENTS.md, .cursor/rules,
copilot-instructions.md).

## Scope

${sweep_context}

## What to do

1. **Name the foundational logic** in one phrase — the core behavior or rule
   this work adds or changes (a validation predicate, a parse routine, a
   dispatch branch, a formatting rule).
2. **Grep the rest of the app** for *other* locations that exercise the same
   logic: duplicated blocks, parallel call sites, sibling modules implementing
   the same rule. Cite each by **full repo-root-relative path** plus a
   **symbolic anchor** (function / class / constant / section name) — never a
   raw line number.
3. **Classify semantic reach from the focused description and each proposed
   step's declared boundary.** A shared path, duplicate, parallel caller,
   relation label, or number of consumers is inspection evidence only; it does
   not prove that the focused plan changes shared semantics. Apply this order:
   - Reuse a current common owner unchanged when its existing contract already
     makes the focused property true. Do not emit that owner in
     `shared_locations` and do not propose `consolidation`: this sweep reports
     only a focused-plan mutation or a deliberate deferral.
   - Otherwise, `update-in-place` is available only for the smallest local
     adapter or bounded additive extension that keeps existing consumer
     behavior and schema interpretation unchanged. An available local adapter
     does not rule out a compatible bounded additive extension, and common
     ownership does not require a local duplicate when unchanged reuse works.
   - Otherwise, direct a required shared semantic change to `defer`: leave it
     out of this focused plan as separate work. Do not turn that deferral into
     a consolidation suggestion, a new step, or another focused-plan change.
4. For each shared location, judge the **relation** and the **recommendation**:
   - `relation`: `duplicate` (same logic copy-pasted), `parallel-call-site`
     (calls the same thing), or `sibling-implementation` (a separate
     implementation of the same rule).
   - `recommendation`: `update-in-place` only for compatible focused local
     work, `consolidate` only when it preserves the focused contract without a
     shared semantic change, or `defer` for separately intentional shared
     semantic work.
5. Propose a dedicated consolidation step only when it is compatible focused
   work and the supplied boundary identifies an observable execution handoff,
   ordering, or bypass contract. Otherwise omit `consolidation`; do not create
   a new step merely because code repeats. A consolidation may accompany an
   unrelated `defer` finding, but it must not name a deferred path. List every
   path the consolidation changes in `consolidation.files` or
   `consolidation.creates`.

## Output contract

${response_format_block}

Rules:
- `shared_locations` may be `[]` when the logic is genuinely unique to this
  work or unchanged reuse already satisfies the focused property — say nothing
  rather than invent duplication.
- `consolidation` may be `null` when no consolidation step is warranted.
- `step_id` and `consolidation.after_step_id` are either a bare step id such
  as `2` or `null`; use an id only when it identifies a step in the supplied
  scope.
- Every `path` must be verifiable on disk via Grep/Read; do not guess paths.
- These are **suggestions** for the author to weigh, not mandatory edits.
- `consolidation.rationale` and `consolidation.intent` answer different
  questions — keep them distinct. `rationale` defends the choice to
  consolidate over patching in place; `intent` states why the resulting
  step is in the plan at all, the way any other step's intent would.
