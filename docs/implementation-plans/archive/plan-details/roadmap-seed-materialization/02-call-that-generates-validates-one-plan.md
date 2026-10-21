> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add a call that generates and validates one plan's draft seed

## Summary

Adds `materialize_plan_seed`, a new function in `plan_tool/roadmap.py` that generates one plan's draft seed independently of the four-stage roadmap loop: it loads the roadmap's four accepted artifacts, resolves the one requested plan row, calls the backend against a new prompt (`plan_tool/prompts/roadmap-seed.md`), lifts the reply, and validates it through step 1's `validate_draft_seed_content`. A clean reply writes the draft file and its `seed-state.json` entry together, and re-syncs an already-promoted `plan-seeds/<id>.md` copy the same way `refresh_roadmap_seeds` already does; an exhausted attempt writes nothing and leaves whatever was there before untouched. Unlike the four staged prompts, `roadmap-seed.md` explicitly invites the model to inspect the current repository, mirroring `plan_tool/prompts/roadmap-refresh-seeds.md`'s existing stance rather than the stage 1–4 "do not read the repository" rule. This call is not wired into any CLI flag or into stage 4's own write path yet — it is the primitive steps 4, 5, and 9 build on.

## Table of Contents

- [Why](#why) — what this primitive replaces and why it needs to exist standalone
- [Input](#input) — the step 1 validator, the seed-state schema, and the shipped stage table this step reads but does not join
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files plus one necessary test-file addition
- [Implementation](#implementation) — the new call, its prompt, its retry loop, and its atomic per-plan write
- [Tests](#tests) — the prompt-pinning and retry-loop coverage this step adds
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Today the only way to (re)generate a draft seed is `refresh_roadmap_seeds`, which makes one combined backend call asking for every plan's seed at once (via `_run_stage` over a synthetic `_refresh_stage_for_artifact` and the multi-fence lift `_lift_multi_fence_reply`). That shape cannot back a targeted `--materialize <plan-id>` (step 5), cannot let a batch continue past one plan's failed call (step 4), and cannot be step 9's replacement for stage 4's own inline seed generation, which also currently depends on the multi-fence bundle protocol. All three of those later steps need the same smaller primitive: given one roadmap and one plan id, make one backend call, validate the reply against that plan row alone, and either land a complete draft-plus-sidecar unit or change nothing.

Step 1 makes this possible by extracting `validate_draft_seed_content(text, *, plan)` — a provenance/component-reference check that takes a plan row and seed text directly, with no `ArtifactEnvelope` and no bundle. Without that extraction this step would have to either duplicate `check_draft_seed_provenance`'s logic or force a one-plan call through the full stage-4 `ArtifactEnvelope`/`PLANS_GATES` machinery, which exists to judge a four-artifact stage-4 *write*, not a single derived file.

## Input

This step is grounded in two contracts it does not own, plus one prompt precedent it should closely model:

- **Step 1's shared validator**, `plan_tool.roadmap_gates.validate_draft_seed_content(text: str, *, plan: PlanRow) -> list[Violation]`. Parses `text` with `parse_draft_seed_provenance`, folding an unparseable-frontmatter failure into a `VIOLATION_DRAFT_SEED_PROVENANCE` violation (not an exception), and checks `roadmap_components` against `plan.component_ids` (with the cross-cutting carve), returning `VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE` violations for anything unresolved. `Violation.message` is already written to be quoted verbatim into a retry prompt (`plan_tool/roadmap_gates.py`'s module docstring). This is the *only* check this step runs — no prose-quality, section-presence, or Architecture-additions check exists or should be added here (see Applicable guardrails).
- **The `seed-state.json` schema** (`plan_tool/roadmap_seed_state.py`): `validate_seed_state`'s per-plan-id shape (`draft_seed_path`, `status` — `"current"`/`"invalidated"` — `digest`, `published`) is unchanged by this step. `load_seed_state`/`write_seed_state` already round-trip that shape atomically; this step is a new *caller*, not a schema change. By the time this step runs, step 1 has already widened `_structural_state_path`/`_matching_plan_id` to recognize both `seeds/` and `plan-seed-drafts/`, so this step needs no directory-prefix special-casing of its own — `resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)` (already prefix-agnostic after step 1) is the single source of where a plan's draft lives.
- **`refresh_roadmap_seeds`' existing promoted-copy resync** (`plan_tool/roadmap.py`): when a plan's sidecar entry is `published`, or `plan-seeds/<id>.md` already exists, or `_latest_seed_archive` finds an archived generation of it, `refresh_roadmap_seeds` also rewrites the promoted copy via `_promoted_seed_body(text, marker=render_seed_state_marker(...))`. This step's intent explicitly asks for the same behavior ("re-syncs that copy the same way today's `refresh_roadmap_seeds` does"), so mirror that branch rather than reinventing it.
- **`plan_tool/prompts/roadmap-refresh-seeds.md`**, the closest existing prompt. It already does almost everything `roadmap-seed.md` needs: takes `${slug}`, `${domain_artifact}`, `${constraints_artifact}`, `${components_artifact}`, `${plans_artifact}`; opens with "Unlike normal roadmap stages, inspect the **current repository** before you write"; and states the same scope-contract section list (`Outcome`, `In scope`, `Out of scope / Non-goals`, `Allowed behavior changes`, `Allowed reorganization`, `Verification`, `Stop / defer`) that `roadmap-plans.md`'s "Draft seed content" section and `SEED_FORMAT.md` both use. The one thing it does *not* do is scope to one plan — it asks for a multi-fence reply covering every row.

**What this step does not read from disk:** step 3's classification (`missing`/`stale`/`malformed`/…) does not exist yet — this call always (re)generates whatever `plan_id` it is given, unconditionally. Deciding *which* plan ids need regenerating is step 3's/step 5's job, not this one's.

## Files (creates vs edits)

**New files:**

- `plan_tool/prompts/roadmap-seed.md` — the per-plan seed generation prompt.

**Existing files (edits only):**

- `plan_tool/roadmap.py` — add `materialize_plan_seed`, its result type and outcome constants, and its prompt-rendering/retry helpers.
- `TESTING.md` — add an invoker-neutralization row for `materialize_plan_seed(invoker=...)`, following the existing `roadmap.py → run_roadmap(invoker=...)` row's format.
- **`tests/test_roadmap.py` (necessary addition, not in the plan's declared list — see below).**

**Why the addition is necessary:** the plan's `enforce_step_tests: true` and this step's own `change_type: feature` require a real test-authoring delta, and `tests/test_roadmap.py` is the established mirror of `plan_tool/roadmap.py` — every existing sibling primitive in this module (`refresh_roadmap_seeds`, `apply_roadmap_seeds`, `_run_stage`) is tested there, and reusing that file (rather than a new one) keeps this primitive's tests next to the fixtures it needs (`_StubInvoker`, `_seed_text`, `_plans`, `env`/`shipped_env`). Step 1's own detail file set this precedent explicitly when it added `tests/cli/test_roadmap_cmd.py` to its Files section for the same reason.

## Implementation

### Resolving the plan and its upstream context

Recommended signature, in `plan_tool/roadmap.py`:

```
def materialize_plan_seed(
    slug: str,
    plan_id: str,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: StageInvoker = shell_roadmap_invoker,
    max_attempts: int = MAX_STAGE_ATTEMPTS,
) -> RoadmapSeedMaterializeResult:
```

Load all four staged artifacts fresh off disk with `_load_stage_artifact(stage, plans_dir=plans_dir, slug=slug) for stage in STAGES` — the same call `refresh_roadmap_seeds` already makes. This is what "one seed materialization job owns one draft path... without asking a backend to reconstruct siblings" (Architecture) means in practice: every call is self-contained and re-reads its own ground truth, so a caller looping over plans (step 4, step 5) can call this once per plan id with no shared in-memory state and no ordering dependency between calls. File re-reads are cheap; only backend calls are the resource this plan is managing.

Resolve `plan_id` against `loaded[-1].artifact.plans` (the loaded `PlansArtifact`). If no row matches, raise `RoadmapError` naming the slug and the plan id — mirroring `_load_stage_artifact`'s style of raising for "the thing this call needs isn't there" rather than returning a result variant, since an unknown plan id is a caller error, not a per-attempt content failure. (Step 5's own two-way refusal — "no such plan" vs. "already current/duplicate" — is built on top of this raise plus step 3's classification; it does its own pre-check before ever calling this primitive, so this defensive raise mainly protects other callers, like step 4's per-plan loop.)

**Constraint:** this call does not build a `RoadmapStage`, does not go through `_run_stage`, `_render_stage_prompt`, `_build_envelope`, or `ArtifactEnvelope`. Those exist for the four-artifact stage table (typed parse/render/gates per stage, revision wrapping, `_authored_review_rows` refusal). A draft seed is not staged, carries no `feedback`/`removals` review rows, and is judged by a plain `text -> list[Violation]` function, not a `Gate`. Forcing it through the stage machinery would mean inventing a fifth `RoadmapStage` whose `parse`/`render` are near-identities and whose `gates` wraps a non-`ArtifactEnvelope` function — more machinery than the call needs.

### Rendering the prompt (`plan_tool/prompts/roadmap-seed.md`)

Model it closely on `plan_tool/prompts/roadmap-refresh-seeds.md` rather than starting fresh — the two prompts solve the same problem (generate seed content against the current repository) at different granularities:

- Reuse its four artifact sections (`${domain_artifact}`, `${constraints_artifact}`, `${components_artifact}`, `${plans_artifact}`) and its "inspect the current repository" framing — this is the one place in the roadmap prompt family that deliberately breaks from stage 1–4's "do not read the repository" rule, and this new prompt inherits that same break, not the stage prompts' restriction.
- Add a `${plan_id}` variable and instruct the model to draft the seed for **only** that row — `${plans_artifact}` still carries every plan row (needed for ordering/assumption/decision context), so the prompt has to say explicitly which one this call is about, the same way `roadmap-plans.md`'s worked example already frames "Plan review contract" and "Inter-plan assumptions" per plan row.
- Drop the multi-fence output protocol entirely. The reply is the seed text alone — provenance frontmatter opening on `---`, then the body — with no fence label and no other plan's content. This is what makes `_lift_artifact_text` (already used for the four staged artifacts) directly reusable for lifting this reply too: it strips a leading/trailing fence and skips to the first `---` line, which is exactly the shape a draft seed's own frontmatter needs. Do not write a second tolerant-lift routine for this call.
- Keep the scope-contract section list (`Outcome` through `Stop / defer`) and the Architecture-additions instructions (four-artifact provenance, domain binding, settled decisions as fences, discharged constraints, inter-plan assumptions, plan review contract) — `roadmap-plans.md`'s "Draft seed content" section already has this prose fully worked out; adapt it to a single-plan frame rather than re-deriving it.
- State both of `validate_draft_seed_content`'s rules explicitly, the way `roadmap-plans.md` states every `PLANS_GATES` rule: provenance frontmatter (`roadmap_components`, optional `cross_cutting`) is required, and every `roadmap_components` entry must resolve against this plan's `component_ids` (or the plan is `cross-cutting` and the seed sets `cross_cutting: true`).
- Cite no `*_FORMAT.md` path by name — `rg -l 'FORMAT\.md' plan_tool/prompts/` returns nothing at HEAD across all 27 existing templates, because plan-tool ships as an installed tool with no guarantee the consuming repo carries these docs. Restate the contract in the prompt's own words instead.
- The worked example (if you include one) uses placeholder ids (`plan-1`, `component-checkout`) exactly the way `roadmap-plans.md`'s skeleton does, and must itself parse through `parse_draft_seed_provenance` and clear `validate_draft_seed_content` with zero violations — see Tests.

### The generate → validate → retry loop

A lighter loop than `_run_stage`'s, since `validate_draft_seed_content` already folds the "unparseable frontmatter" case into a violation rather than a separate exception, collapsing what would otherwise be two failure phases (parse, then gate) into one:

1. Render the base prompt once (variables above), matching `_render_stage_prompt`'s "rendered once before the loop" shape.
2. For each attempt up to `max_attempts`: call `invoker(prompt)`. `rc != 0` or an empty reply is `FAILURE_INVOKE` (reuse the module's existing constant — do not mint a seed-specific one). Otherwise lift with `_lift_artifact_text`; `None` is `FAILURE_PARSE` (reuse it too). Otherwise call `validate_draft_seed_content(lifted, plan=plan)`; a non-empty result is `FAILURE_GATES` (reuse it), and the correction text for the next attempt is exactly the violation messages — `_corrections_block` is directly reusable here.
3. Write seed-specific correction text for the invoke/parse failure kinds (the existing `_run_stage` strings talk about "the row inventory," which doesn't describe a draft seed's shape).
4. A clean validation (`violations == []`) ends the loop successfully with the lifted text in hand.
5. Exhausting every attempt returns a result carrying whichever failure kind/detail/violations the *last* attempt produced — mirroring `_StageOutcome`'s "every other field describes the attempt that spent the last of the budget."

**Constraint — reuse the shared vocabulary, don't fork it.** `MAX_STAGE_ATTEMPTS`, `FAILURE_INVOKE`, `FAILURE_PARSE`, `FAILURE_GATES` already exist at module scope and are exactly what "one retry channel, N failure kinds... because an operator experiences them identically" (`_run_stage`'s own docstring) means for this call too. `refresh_roadmap_seeds` already reuses `MAX_STAGE_ATTEMPTS` as its own default for a non-stage call — same precedent applies here.

### Writing the draft, resyncing any promoted copy, then committing the sidecar entry — in that order

This is the step's central acceptance property, stated in its intent: a successful attempt commits the draft file, any promoted-copy resync, and the `seed-state.json` entry **in this one call**, and a failed attempt commits none of it. The three writes are deliberately **sequenced, not merely co-located in one call**: the sidecar-entry write is always last, because it is the single write that tells every other reader (step 3's classifier, `--materialize`'s targeting) "this plan is `current`" — nothing may claim that before every write it depends on being true has actually landed.

- **The draft write.** On success, write `resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)` via `atomic_write_text(target, lifted)` — the *lifted* text, not the raw reply, the same "write what was validated, never the raw response" rule `_write_artifact`'s docstring states for stage artifacts.
- **The resync condition, computed once.** Immediately after the draft write and before either remaining write depends on it: `published = bool(old.get("published", False))`, **or** `(repo_root / "plan-seeds" / f"{plan.id}.md").exists()`, **or** `_latest_seed_archive(...)` finds a prior archived generation of it. Compute it once here; both remaining writes below read this same value, neither recomputes it independently.
- **The promoted-copy write, if the resync condition holds — before the sidecar entry, not after.** Mirror `refresh_roadmap_seeds`' existing branch: write `plan-seeds/<id>.md` with `_promoted_seed_body(lifted, marker=render_seed_state_marker(state_path=..., repo_root=repo_root, roadmap_slug=slug, plan_id=plan.id))`. `_promoted_seed_body` re-parses the text through `parse_draft_seed_provenance`; since `validate_draft_seed_content` has already confirmed it's parseable, this re-parse cannot fail. **This is a resync, never a new promotion** — the branch only fires when a `plan-seeds/<id>.md` copy already exists (or the sidecar already says `published`). This call never *creates* a first promoted copy for a plan that was never promoted — that would be `--apply`'s job, gated by its own confirm flow, and is exactly the "auto-promoting drafts... treating draft materialization as user approval" out-of-scope fence (see Applicable guardrails).
- **The sidecar-entry write, last.** Only after the promoted-copy write (if any) completes: load the sidecar with `_load_roadmap_seed_state` and update **only** `entries[plan.id]` — writing the full four-key shape `_mark_roadmap_seeds_current`/`_register_roadmap_seed_promotions`/`refresh_roadmap_seeds` already write: `{"draft_seed_path": plan.draft_seed_path, "status": "current", "digest": digest_text(lifted), "published": <resync condition>}` (the same value computed above, not recomputed). The `draft_seed_path` key always comes from `plan.draft_seed_path` (the plan row's own, current path), never carried forward from the prior entry — this is the mechanism Architecture's "materialization rewrites the entry's stored path to match the row's" rule depends on, and the one step 3's `path-escaping` state relies on staying true (it reads `entry["draft_seed_path"]`, not the row's). A plan whose `plan-seeds/<id>.md` already exists but whose stale entry says `published: false` must come out of this call with `published: true`. Every other key is written fresh, unconditionally. Do not loop over `artifact.plans` the way `_mark_roadmap_seeds_current`/`_invalidate_roadmap_seeds` do; those touch every plan because a whole stage-4 write affects every row, but this call must leave every *other* plan's entry byte-for-byte as it found it.

**This ordering — sidecar entry last, not merely "all three writes in one call" — is what "atomic per-plan unit" buys, and it is what makes an interruption between any two of the three writes always recoverable, never silently stale.** An interruption after the draft write but before the sidecar-entry write (whether or not the promoted-copy write ran) leaves the sidecar's recorded digest at its pre-call value, which no longer matches the freshly-written draft — step 3's classifier reads that as `digest-mismatched` (or `missing`, if no entry existed at all), and the next `--materialize` (default targeting, no id needed) re-runs this whole call, redoing the promoted-copy resync if it didn't finish and rewriting the sidecar. The one write this ordering exists to protect against is the sidecar entry landing *before* the promoted-copy resync completes: had the sidecar-entry write run before the promoted-copy write, an interruption between them would leave the sidecar (and therefore step 3's classifier, and `--materialize`'s default targeting) reporting the plan `current` while `plan-seeds/<id>.md` still carries stale content — invisible to every consumer of `classify_draft_seeds`, and unreachable by any deliberately-targeted repair, since nothing but an unconditional full `--refresh-seeds` sweep touches a plan already believed `current`. Committing the sidecar last closes that hole structurally: the sidecar can never claim `current` (and therefore `published: true`) before the promoted copy it claims is in sync with actually is.

Also a deliberate departure from `refresh_roadmap_seeds`' own shape: refresh collects `writes`/`entries` for *every* plan across the whole batch and writes the sidecar once at the end, so an interruption mid-batch can leave draft files the sidecar doesn't know about yet. This call's contract is the opposite — every write for one plan completes, in the order above, before the call returns — so step 4's and step 5's future loops can be interrupted *between* plans (not just at the end of a batch) with no plan left in a torn state.

**Constraint — no concurrency.** This call is not designed to run for two plans at once; `seed-state.json` is one shared JSON document, and the project's standing architecture rule (see `CLAUDE.md` "Architecture") discourages in-process fan-out over shared mutable state. Step 4's and step 5's future batch loops call this serially, one plan at a time — nothing here needs a lock.

### What this call does not do

- Does not decide *whether* a plan's existing draft needs regenerating (`missing`/`stale`/`malformed`/…) — that's step 3's classification. This call always regenerates whatever `plan_id` it's handed.
- Does not check for duplicate `draft_seed_path` basenames across plan rows (`find_duplicate_draft_seed_basenames`) — that's a roadmap-wide property step 3 owns, not something one plan's own generation call can detect or fix.
- Does not touch stage 4's own inline generation, `PLANS_GATES`, or the multi-fence bundle write path itself (`_write_stage_outputs`, `_lift_multi_fence_reply`) — those stay exactly as they are until step 9. The one narrow exception is the overwrite guard immediately below, which widens an existing condition at the call site without touching `_write_stage_outputs`'s own body.
- Does not accept or wire a `run_logger` — call-level observability for this backend call is explicitly routed elsewhere (see Deferred), matching `refresh_roadmap_seeds`, which already calls `_run_stage(..., run_logger=None, ...)`.

### Closing the legacy-writer overwrite window

Once this call exists, stage 4's still-live inline writer (`_write_stage_outputs`, untouched above) can silently wipe a draft this call already produced: `run_roadmap`'s call site (`plan_tool/roadmap.py`, around the stage loop's `preserve_existing_seeds=(seeds_invalidated or feedback_applied)`) only skips the atomic `plan-seed-drafts/` swap when a stage-4 write is feedback-driven or already-invalidated — an ordinary `--from-stage 4` re-entry with no open feedback and no prior invalidation is neither, so once step 4/5 land and an operator actually calls this primitive through them, the very next plain `--from-stage 4` run atomically replaces the whole directory with a fresh model-generated bundle, discarding every independently materialized draft with no warning. Widen that condition to a third case: also skip the swap when `load_seed_state(roadmap_dir(plans_dir, slug))` reports any entry for a plan in `outcome.artifact.plans` whose `status == "current"` — i.e., a draft this call (directly, or through step 4/5's future surfaces) already independently produced. This is a **transitional** guard only: step 9 deletes `_write_stage_outputs`'s bundle-write branch entirely once stage 4 stops writing seeds at all, taking this widened condition with it — it must not grow any other caller or get promoted into the plan's permanent design, and step 9's own Implementation should note its removal alongside the rest of the branch it deletes.

## Tests

### Tests for this step

All in `tests/test_roadmap.py`, reusing existing fixtures/helpers (`_Env`/`env`/`shipped_env`, `_StubInvoker`, `_seed_text`, `_plans`/`_PLAN_ORDER`/`_PLAN_AUTH`, `read_run_events` is not needed here since this call writes no run log):

**Prompt template (mirrors `TestPlansPromptTemplate`):**

- `test_seed_prompt_template_ships_under_prompts_dir` — `plan_tool/prompts/roadmap-seed.md` exists.
- `test_seed_prompt_placeholders_are_a_subset_of_the_variable_map` — every `${...}` in the template is one this call actually supplies.
- `test_seed_prompt_renders_with_no_unresolved_placeholder` — via `shipped_env` and a real call, no leftover `${` in the rendered prompt.
- `test_seed_prompt_names_draft_seed_provenance_keys` — `roadmap_components` and `cross_cutting` both appear as whole tokens.
- `test_seed_prompt_states_the_provenance_and_component_resolution_rules` — the prompt text states both `validate_draft_seed_content` rules (frontmatter required; `roadmap_components` must resolve against this plan's `component_ids`, with the cross-cutting carve).
- `test_seed_prompt_invites_repository_inspection` — the prompt text says the model should read the current repository (mirroring `roadmap-refresh-seeds.md`'s existing phrase), not "do not read the repository."
- `test_seed_prompt_cites_no_repo_document` — no `FORMAT.md` substring anywhere in the text.
- `test_seed_prompt_names_every_scope_contract_section` — `Outcome`, `In scope`, `Out of scope / Non-goals`, `Allowed behavior changes`, `Allowed reorganization`, `Verification`, `Stop / defer` all appear.

**Prompt worked example (mirrors `TestPlansPromptExample`), only if the prompt includes one:**

- `test_prompt_example_parses_through_draft_seed_provenance` — the embedded skeleton parses via `parse_draft_seed_provenance`.
- `test_prompt_example_clears_validate_draft_seed_content` — parses with zero violations against a matching placeholder plan row.

**The retry loop (mirrors `TestRetryLoop`/`TestHalting`), unit-level with an injected `_StubInvoker` — no shipped prompt needed:**

- `test_materialize_writes_draft_and_sidecar_entry_together_on_success` — one call, clean reply: draft file exists with the lifted text, sidecar entry has `status="current"`, `digest=digest_text(lifted)`, `draft_seed_path == plan.draft_seed_path`.
- `test_materialize_rewrites_a_stale_sidecar_draft_seed_path_to_the_plan_rows_current_path` — seed a prior sidecar entry whose `draft_seed_path` disagrees with the current `plan.draft_seed_path` (e.g. a hand-edited entry, or a row whose declared path changed since the entry was last written); after a clean materialize call, the entry's `draft_seed_path` equals the plan row's current path, never the stale prior value — this is the property `path-escaping` classification (step 3) and step 5's regeneration-clears-the-state claim both depend on.
- `test_materialize_invoke_failure_retries_with_correction` — rc≠0 first, clean second: two calls, second prompt carries the invoke-failure correction, success on attempt 2.
- `test_materialize_unliftable_reply_retries_with_correction` — a reply with no `---` fence.
- `test_materialize_gate_violation_retries_with_the_violation_message_quoted` — a reply whose `roadmap_components` names an id absent from `plan.component_ids`; the next attempt's prompt contains the violation's exact message text.
- `test_materialize_exhausted_writes_nothing_on_a_first_time_attempt` — every attempt fails; no draft file, no sidecar entry for that plan id afterward.
- `test_materialize_exhausted_leaves_a_prior_draft_and_entry_untouched` — seed the draft file plus a sidecar entry, one call whose every attempt fails: the file's bytes and the entry's fields are unchanged.
- `test_materialize_unknown_plan_id_raises_without_calling_the_invoker` — `plan_id` absent from `04-roadmap.md`'s `plans`; `RoadmapError` naming the slug and plan id; invoker's `calls == 0`.
- `test_materialize_default_invoker_is_shell_roadmap_invoker` — signature/default check, mirroring how `run_roadmap`'s and `refresh_roadmap_seeds`' own defaults are pinned.

**Promoted-copy resync:**

- `test_materialize_resyncs_an_already_published_copy` — sidecar entry has `published: true`; after materialize, `plan-seeds/<id>.md` carries the new body plus the state marker.
- `test_materialize_resyncs_when_a_plan_seeds_file_exists_with_no_published_flag` — `plan-seeds/<id>.md` exists on disk but the sidecar entry (or its absence) doesn't say `published`; still resynced, and `published` becomes `true`.
- `test_materialize_never_writes_plan_seeds_for_an_unpromoted_plan` — no `plan-seeds/<id>.md`, no `published` flag, no archive: after materialize, `plan-seeds/` still has no file for this plan id.
- `test_materialize_writes_the_promoted_copy_before_the_sidecar_entry` — for an already-promoted plan, patch/spy the sidecar-write call to record call order against the `plan-seeds/<id>.md` write; assert the promoted-copy write happens first — pins the ordering, not merely both writes' end state, so a future edit that silently reverses them fails this test even though every other resync test would still pass.
- `test_materialize_interrupted_after_promoted_copy_but_before_sidecar_write_stays_recoverable` — for an already-promoted plan, inject a failure (e.g. monkeypatch `_write_roadmap_seed_state`/`_load_roadmap_seed_state` to raise, or an equivalent point after the promoted-copy write) so the call raises after `plan-seeds/<id>.md` is rewritten but before the sidecar entry lands: the sidecar's recorded digest is still the pre-call value, so a subsequent `classify_draft_seeds` call classifies the plan `digest-mismatched` (or `missing`), not `current` — proving the interruption is recoverable via a later `--materialize` rather than silently invisible. This is the regression test for `promoted-copy-resync-not-covered-by-atomic-unit`: it would have failed against the pre-fix ordering, where the same interruption point left the plan silently `current` with a stale promoted copy.

**The transitional overwrite guard:**

- `test_stage4_replace_skips_the_bundle_swap_when_a_plan_already_classifies_current` — a roadmap with one plan whose sidecar entry is `status="current"` (independently materialized via this call), then a stage-4 `--from-stage 4` re-entry with no open feedback and no invalidation, given a fresh bundle reply: `_write_stage_outputs` takes the `preserve_existing_seeds` branch (the `plan-seed-drafts/` directory and the materialized draft's bytes are unchanged after the run), the same as today's `feedback_applied`/`seeds_invalidated` cases.
- `test_stage4_replace_still_swaps_when_no_plan_classifies_current` — same setup with no sidecar entries at all (a genuinely fresh roadmap, or one where every plan is still `missing`): the bundle swap proceeds exactly as it does today, proving the widened condition doesn't regress the ordinary first-materialization case.

**Against the real validator and shipped prompt (mirrors `TestFourStageArcAgainstTheRealGates`; `@pytest.mark.integration`):**

- `TestMaterializePlanSeedAgainstTheRealValidator::test_a_conforming_reply_clears_validate_draft_seed_content_and_writes` — `shipped_env`, a real four-artifact roadmap on disk, a `_StubInvoker` returning `_seed_text(components=...)`-shaped text, asserting the real `roadmap-seed.md` prompt plus the real `validate_draft_seed_content` accept it end to end.

Every test above is green before this step is considered finished.

## Acceptance criteria

- `plan_tool.roadmap.materialize_plan_seed(slug, plan_id, *, repo_root, plans_dir, invoker=shell_roadmap_invoker, max_attempts=MAX_STAGE_ATTEMPTS)` exists and reuses `FAILURE_INVOKE`/`FAILURE_PARSE`/`FAILURE_GATES` for its failure kinds — checkable with `rg -A3 'def materialize_plan_seed' plan_tool/roadmap.py`.
- On a clean reply, the draft file and its `seed-state.json` entry (`status="current"`, `digest` of the written body, `draft_seed_path` set from `plan.draft_seed_path` — never carried forward from a prior entry) both exist after the one call returns; no other plan's sidecar entry is touched.
- On an exhausted first-time attempt, neither a draft file nor a sidecar entry for that plan id exists afterward.
- On an exhausted attempt over an existing draft, the prior file's bytes and the prior sidecar entry's fields are unchanged.
- When the plan is already promoted (sidecar `published`, an existing `plan-seeds/<id>.md`, or an archived generation of it), a successful call also rewrites `plan-seeds/<id>.md` with the new body and state marker; otherwise no `plan-seeds/` file is touched.
- The promoted-copy write, when it fires, always completes before the sidecar-entry write starts (`test_materialize_writes_the_promoted_copy_before_the_sidecar_entry`), so an interruption between the two never leaves the sidecar reporting `current`/`published: true` while `plan-seeds/<id>.md` still carries stale content — the sidecar's pre-call digest still classifies `digest-mismatched`/`missing` in that case, recoverable by a later `--materialize` rather than silently invisible (`test_materialize_interrupted_after_promoted_copy_but_before_sidecar_write_stays_recoverable`).
- Calling with a `plan_id` absent from the roadmap's current `04-roadmap.md` raises `RoadmapError` naming the slug and the plan id, and the invoker is never called.
- An ordinary `--from-stage 4` re-entry (no open feedback, no invalidation) over a roadmap where any plan's sidecar entry already classifies `current` skips the atomic `plan-seed-drafts/` swap and leaves every existing draft file's bytes unchanged; a re-entry where no plan classifies `current` still performs the swap as before.
- `plan_tool/prompts/roadmap-seed.md` exists, renders with no unresolved `${...}` placeholder, states both `validate_draft_seed_content` rules, explicitly invites reading the current repository, cites no `*_FORMAT.md` path, and names every scope-contract section.
- `TESTING.md` documents `materialize_plan_seed(invoker=...)`'s neutralization recipe.
- `uv run pytest tests/test_roadmap.py -q` is green.

## References

- `ROADMAP_FORMAT.md` — the existing `draft_seed_path`/provenance contract this call's prompt and validator target; not edited by this step.
- `SEED_FORMAT.md` — the scope-contract section shape (`Outcome` through `Stop / defer`) every generated draft body must follow; unchanged by this plan.
- `DATA_CONTRACT.md` — `seed-state.json`'s persisted shape and the `draft_seed_count` field this plan's manifest work extends rather than replaces.

## Applicable guardrails

- **Out of scope — auto-promoting drafts or treating materialization as approval.** This call writes to `plan-seeds/` only as a *resync* of an already-promoted plan, mirroring `refresh_roadmap_seeds`' existing behavior; it never creates a first promoted copy for a plan that was never promoted. Promotion itself (`--apply`, `_apply_roadmap_seeds`) is untouched — that wiring is step 6's.
- **Out of scope — a correctness gate on seed style, length, or model agreement.** `validate_draft_seed_content` (structural/provenance only) is the sole check this call runs. Do not add a check for the scope-contract sections' presence, wording, or the Architecture-additions prose — the prompt asks for them, but nothing here gates them.
- **Out of scope — general background scheduling, parallelism policy, or backend liveness instrumentation beyond the batch-observability work already under separate validation.** This call accepts no `run_logger` and is not designed for concurrent invocation across plans.
- **Out of scope — redesigning the plan-seed prose format.** `roadmap-seed.md` reuses `SEED_FORMAT.md`'s existing scope-contract section list unchanged; this step does not add, remove, or rename a section.
- **In scope, narrowly — "the one-seed-at-a-time primitive every later step... is built on."** This step is exactly that slice: one function, one new prompt, no CLI surface, no change to stage 4's own write path.

## Deferred

- **Deciding which plan ids need regenerating, and detecting duplicate `draft_seed_path` basenames.** Step 3's classification module — this call always (re)generates whatever `plan_id` it's given, unconditionally.
- **CLI wiring — `--refresh-seeds`'s per-plan migration and the new `--materialize` flag.** Steps 4 and 5 respectively; this step ships no CLI surface at all.
- **Batch looping across multiple plans and its diff-report rendering.** Steps 4 and 5's job — the existing `_seed_refresh_diff`/`_render_seed_refresh_report` helpers already exist in this module and are available for those steps to feed this call's output into; this step does not call them.
- **Accepting a hand-edited, `digest-mismatched` draft as current without regenerating it.** Step 10's accept action; this call always generates fresh content, never records a live file's digest as-is.
- **Retiring stage 4's own inline seed generation, its bundle-based gates, and the multi-fence write path.** Step 9; this step adds a new, unused-by-stage-4 function and does not touch `_write_stage_outputs`'s own body, `PLANS_GATES`, or `_lift_multi_fence_reply` — only the narrow, transitional overwrite-guard condition at its call site (see Implementation).
- **Model-call observability for this call's backend round trips.** Explicitly out of scope for this plan (see the plan's own Deferred section) — routed to the batch-authoring-observability plan lineage, not built here even as a no-op `run_logger` parameter.
- **Targeted/incremental revision marking which plan ids actually went stale.** `docs/implementation-plans/plan-seeds/roadmap-incremental-revision.md`, not yet promoted to a plan — until it ships, deciding *which* plan ids to materialize stays entirely the caller's (step 4's, step 5's) job, informed by step 3's classification, not this call's.
