> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scope-fence-grounding.md`.
> Preserved here for history; do not edit.

# Scope-fence preservation and grounding (BACKLOG #161 + #162)

Carries BACKLOG **#161** (preserve a seed's `Scope guardrails` / `Audit
guardrails` / `Expected placement` sections through `create`) and **#162**
(render the originating scope contract into the plan-audit prompt) as one
plan. They are filed as two backlog entries because they were discovered
separately; they are one plan because they are two halves of a single
contract and neither is meaningful alone.

## Why this is one plan, not two

The audit is instructed to honor a scope contract it structurally cannot
see. Two independent gaps produce that outcome:

1. **The author's fence never reaches the plan.** `PLAN_BODY_SECTIONS`
   (`create.py:185-193`) is a closed tuple and both synthesis prompts declare
   any other key a shape error (`prompts/synthesize-body.md:57-63`,
   `prompts/distill-seed.md:49-59`), so a seed's guardrail sections have
   nowhere to land. Observed: `Scope guardrails` and `Expected placement`
   survived only as unstructured prose folded into `Architecture`, and
   **`Audit guardrails` was dropped outright** — silently, no finding.
2. **The authoritative source never reaches the audit.**
   `render_plan_audit_prompt` (`review.py:5838-5846`) substitutes exactly
   five values — `plan_title`, `plan_body_block`,
   `detail_bundle_status_block`, `detail_files_block`,
   `carried_findings_block`. The seed is not among them. Yet
   `plan-audit.md:94-98` names "plan/seed Outcome, In scope, Out of scope /
   Non-goals, …" as the contract to respect, and `docs/AUDIT_FLOW.md:36-39`
   names the seed as its real home.

Fixing only (1) leaves the audit reading a fence that survived a lossy
transform. Fixing only (2) leaves the plan body — the thing every other
consumer reads — still missing the guardrails. The shared outcome is *the
audit can see the fence it is told to honor*, and it is not provable until
both land. Splitting them reproduces the straddling-contract failure that
`impact-recurrence-01-classifier` documents.

## Outcome

A seed carrying `Scope guardrails` / `Audit guardrails` / `Expected
placement` produces a plan that still carries them under their own headings
— or a deterministic finding explaining why not — and the conceptual audit
prompt receives the originating scope contract verbatim when one is
resolvable.

## Decisions this seed settles (the plan must not re-open them)

1. **The guardrail sections are optional canonical sections, not a
   passthrough.** They go in `OPTIONAL_PLAN_BODY_SECTION_SHAPES`
   (`create.py:296`) beside `Input`, with `[conditional]` policy and
   evidence-only posture ("omit entirely when not consumed; do not return
   null just to acknowledge the rule"). A general "accept any unrecognized
   H2" reopens the section sprawl the closed tuple exists to prevent and is
   forbidden.

2. **The preservation check is deterministic and exact-heading.** Seed
   carries heading H, synthesized body lacks H → finding. Zero Claude,
   output bounded by the seed's guardrail-heading count. Judging whether
   dropped content was *materially folded* elsewhere requires a model and is
   **BACKLOG #163** — explicitly not this plan. Do not add an invoker seam.

3. **Guardrail sections are NOT deferrable.** `derive_candidate_buckets`
   (`detail.py:522-545`) turns every current body H2 into a proposable
   `defer` bucket, and `create`'s bootstrap does the same
   (`create.py:5962-5972`). Without action, a `detail` step could propose
   deferring `## Audit guardrails` — deferring the fence that constrains the
   audit — and because flat sign-off refuses `include`
   (`scope_review_cmd.py:57-66`) and there is no dismiss verb yet (BACKLOG
   #132), that deferral is retractable only by hand-editing
   `concepts.json`. **Decision: exclude the three guardrail section names
   from bucket derivation** in both producers. A fence that can be deferred
   is not a fence. This is the one genuinely open design question in #161's
   rider 2 and it is settled here.

4. **Seed provenance requires a schema field — it does not exist today.**
   `Plan` (`schema.py:180-208`) has `model_config = ConfigDict(extra="forbid")`
   and **no** field recording which seed a plan came from. #162's
   "resolve the seed via existing provenance" is therefore unimplementable
   as written. Settled design:
   - Add `source_seed: Optional[str] = None` to `Plan`, a repo-relative
     path written by `create --from-existing`, elided on rewrite when
     `None` (mirroring `registered_by`, `schema.py:196-203`).
   - Add `--seed <path>` to the completeness-audit surface as an explicit
     override for plans authored before the field existed.
   - **Do not** infer the seed by slug-matching against `plan-seeds/`.
     A silently wrong fence is worse than no fence.
   This makes `DATA_CONTRACT.md` (drift-guarded by
   `tests/test_data_contract.py`) and `PLAN_FORMAT.md` in-scope edits.

5. **The contract block is additive and fails to nothing.** The audit
   template gains a `${scope_contract_block}`. No resolvable seed → empty
   block → the rendered prompt is byte-identical to today. An oversized
   contract is truncated with an explicit marker, never silently clipped
   (the posture `annotate` already uses). Prefer emitting no block over a
   partial or guessed one.

6. **The block is originating intent, not current truth.** A plan may have
   legitimately evolved past its seed. The prompt must present the contract
   as the fence the work was commissioned under and let the plan body win on
   direct conflict. This plan does **not** build seed-vs-plan drift
   detection.

7. **Spend no additional Claude.** #162 changes what the existing audit call
   is grounded on, not how many calls run. Any step proposing a new
   invocation is out of contract.

## In scope

- `plan_tool/create.py` — the optional-section tuple, shapes dict, policy
  tagging consumed by `_render_section_shapes_block` (`create.py:2574`), the
  deterministic preservation check, and the bucket-derivation exclusion.
- `plan_tool/detail.py` — the bucket-derivation exclusion
  (`derive_candidate_buckets`, `detail.py:522-545`).
- `plan_tool/schema.py` — the additive `source_seed` field.
- `plan_tool/review.py` — `render_plan_audit_prompt` and its block collector.
- `plan_tool/prompts/synthesize-body.md`, `prompts/distill-seed.md` — JSON
  contract plus a worked example per prompt.
- `plan_tool/prompts/plan-audit.md` — the `${scope_contract_block}`
  placeholder, and adding `Audit guardrails` to the scope-contract
  enumeration at lines 94-98.
- `PLAN_FORMAT.md`, `DATA_CONTRACT.md`, `docs/AUDIT_FLOW.md`.
- Tests under `tests/`.

## Out of scope / non-goals

- Any Claude call in the preservation check (BACKLOG #163).
- Seed-vs-plan drift detection.
- Making the audit mechanically *enforce* the contract; it stays prompt-level
  guidance.
- `partition_findings_for_triage`, `convergence.is_blocking_impact`, or any
  convergence predicate.
- The `[out-of-scope-deferred]` tag wiring (BACKLOG #156).
- Changes to `concepts.json`, `scope-review`, or the concept-record schema.
  Decision 3 is an exclusion set, not an extension of that store — the
  concept record admits only `defer`/`wont_do` (`concept_tree.py:33`), stores
  no plan prose (`create.py:4577-4590` drops `ConceptNode.source`), and
  writes *into* body sections rather than reading them
  (`concept_sync.py:67-80`). It is the wrong home for a standing constraint.
- Reordering or renaming the eight canonical sections.
- Enforcing guardrail sections on seeds that lack them. This preserves; it
  does not mandate.
- Authoring guardrail *content*.

## Allowed behavior changes

- Plans created from guardrail-carrying seeds gain up to three additional H2
  sections. No change for seeds without them.
- Plans created via `--from-existing` gain a `source_seed` frontmatter key.
  Absent on every existing plan and elided when unset.
- Audits of seed-backed plans see more context and may produce different
  findings. Unchanged when no seed resolves.

## Allowed reorganization

None. The extension points already exist
(`OPTIONAL_PLAN_BODY_SECTION_SHAPES`, the `Input` precedent, the template's
`safe_substitute` block set); use them in place.

## Verification

- A fixture seed carrying all three guardrail sections round-trips through
  `create` with each retained under its own heading.
- A seed carrying none produces a plan with none — no invented sections.
- The preservation check fires when synthesis drops a section the seed
  carried, and does not fire otherwise.
- A plan carrying `## Audit guardrails` is **not** offered as a defer bucket
  by either producer (decision 3, asserted in both `create` and `detail`).
- A plan created `--from-existing` records `source_seed`; a plan created any
  other way omits the key entirely.
- `render_plan_audit_prompt` on a seed-backed plan contains the seed's scope
  contract; on a plan with no resolvable seed it is **byte-identical** to
  today's output.
- An oversized contract is truncated with a visible marker.
- `tests/test_data_contract.py` passes with the `source_seed` addition.

## Stop / defer

- If seed provenance turns out to be unrecoverable on some `create` path
  (`--from`, `--reprocess`), ship the paths where it is recordable and file
  the rest — do not absorb a provenance-plumbing project.
- Any adjacent section-schema idea (new canonical sections, per-section
  policy rework) becomes its own backlog entry.
- If the preservation check's false-positive rate on folded sections proves
  noisy in practice, that is evidence for BACKLOG #163 — file it, do not add
  a model judgment here.

## Audit guardrails

- Run at most one focused completeness audit per convergence round; this
  seed's contract is the fence, not a starting point for expansion.
- Reject findings that require work this seed's Out of scope forbids,
  including any finding that proposes a Claude call in the preservation
  check or an extension of the concept-record schema.
- Audit convergence is not an implementation-readiness requirement.
- *(This section is itself the acceptance fixture: under current `create` it
  would be silently dropped. If the resulting plan carries it, #161 works.)*

## Backlog reconciliation

Source entries: `BACKLOG.md` **#161** and **#162**. The plan's final
docs/status step must update `BACKLOG.md` when the work ships — remove #161
and #162 only after full shipment; if the plan is authored but execution is
pending, mark them plan-authored rather than removing them. **#163** stays
filed and unshipped; if decision 3 or the verification above surfaces
evidence about fold-detection noise, update #163's priority note rather than
absorbing it. If decision 3's exclusion set proves insufficient, note the
interaction on BACKLOG **#132** (concept dismiss/remove verb), which this
plan's decision deliberately routes around rather than fixes.
