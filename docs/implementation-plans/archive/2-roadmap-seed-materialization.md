> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Seed Materialization
intent: Stage 4 roadmap plan derivation will keep the canonical roadmap manifest and
  each roadmap-derived draft plan seed independently materialized, validated, and
  traceable. A roadmap revision will no longer need to carry or re-emit every seed
  body in `draft_seed_bundle`, while `--apply` will promote only a complete, verified
  set of drafts that matches the accepted roadmap.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Share draft-seed content validation between the stage-4 gates and the new
    seed materializer
  intent: Gives the new per-plan materializer and the manifest module one shared implementation
    of seed-content validity — provenance/component-reference validation, and the
    plan-row basename-collision check `check_draft_seed_bundle_alignment` already
    implements, generalized to compare plan rows alone (no bundle required) so it
    survives as a live stage-4 gate after step 9 drops bundle-dependent gating — instead
    of a second, drifting copy of either. Also renames the draft-seed directory constant
    `DRAFT_SEEDS_DIRNAME` from `"seeds"` to `"plan-seed-drafts"` — distinct from,
    and not to be confused with, the existing top-level `plan-seeds/` promoted-copy
    directory this plan does not rename — so every new write lands under the new name,
    while widening `_validate_draft_seed_path` to accept the legacy `seeds/` prefix
    too, read-only, so no existing roadmap's `04-roadmap.md` or `seed-state.json`
    needs a rewrite. Sweeps every other hardcoded `"seeds"` match to the same widened
    rule — `roadmap_seed_state.py`'s `_structural_state_path` and `_matching_plan_id`
    (which `invalidated_seed_continuation` and the stale-seed confirmation gate depend
    on) must recognize a draft under either directory name, tested against both prefixes.
    Bundles a real, observable behavior change (the rename) with a behavior-preserving
    extraction, so this step is `feature`, not `refactor`; `detail` keeps the two
    halves' tests distinguishable within the step. (Considered splitting into two
    steps joined by `depends_on` instead — declined a third time across three audit
    rounds, same reasoning each time — the extraction and the rename touch the same
    file for the same reason, both halves are small, and a split would ripple `depends_on`
    renumbering across every later step to fix a change_type label, not a scope problem.
    Recorded here so a future round recognizes the repeat rather than re-litigating
    it.) Its shared validator becomes step 6's eventual replacement for `_apply_roadmap_seeds`'s
    separate ad hoc provenance check, so that promotion preflight stops being a second
    consumer step 1 doesn't know about. Also updates `roadmap-plans.md`'s `draft_seed_path`
    prefix example/prose from `seeds/order-core.md` to `plan-seed-drafts/order-core.md`
    in this same step, ahead of step 9's larger prompt rewrite (which removes seed-fence
    generation entirely) — the still-live inline stage-4 writer that step 9 eventually
    retires reads its physical write directory from the constant this step just renamed,
    so without this, every stage-4 run between step 1 and step 9 would have the model
    keep emitting `seeds/`-prefixed `draft_seed_path` values while the writer physically
    drops files under `plan-seed-drafts/` instead — a path no plan row declares, invisible
    to the in-run gates (which check only the in-memory bundle) but making every such
    draft read `missing` to `--apply`, `--view walk`, and `create --from-existing`
    alike.
  files:
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_seed_state.py
  - plan_tool/prompts/roadmap-plans.md
  - tests/test_roadmap_gates.py
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_seed_state.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/01-share-draft-seed-content-validation.md
  status: done
- id: 2
  title: Add a call that generates and validates one plan's draft seed
  intent: Creates the one-seed-at-a-time primitive every later step (refresh, on-demand
    materialize, stage-4 decoupling) is built on. A failed attempt never publishes
    a new draft or sidecar change — a first-time attempt (no prior file) leaves the
    row `missing`; a re-materialization attempt (step 4 or step 5 regenerating an
    existing `stale`/`digest-mismatched`/`malformed` draft) leaves the prior file
    and its prior classification untouched rather than deleting it. A successful attempt
    commits the draft file and its `seed-state.json` entry (status, digest) together
    as one atomic per-plan unit, never a separate later write, so every multi-plan
    loop built on this primitive (step 4, step 5, step 9) can be interrupted between
    plans without leaving a generated file the sidecar doesn't yet know about. When
    regenerating a plan already promoted (a `plan-seeds/<id>.md` copy exists), also
    re-syncs that copy the same way today's `refresh_roadmap_seeds` does, so step
    4 and step 5 inherit promoted-copy sync automatically rather than each reimplementing
    it.
  files:
  - plan_tool/roadmap.py
  - TESTING.md
  creates:
  - plan_tool/prompts/roadmap-seed.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: supplies the shared provenance/component-reference validator this call uses
      to judge its own reply
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/02-call-that-generates-validates-one-plan.md
  status: done
- id: 3
  title: Add a module that classifies every plan's draft seed into a named state
  intent: Gives apply, the roadmap views, the materialize flag, and `create --from-existing`'s
    stale-draft confirmation (`cli/authoring.py`'s `_confirm_invalidated_roadmap_seed`,
    today the only other reader of `seed-state.json` outside `roadmap.py`/`roadmap_seed_state.py`/`roadmap_cmd.py`,
    and today blind to every state but the sidecar's raw `current`/`invalidated` status
    — a `digest-mismatched` unreviewed hand edit or a `malformed` draft both pass
    its confirmation with no prompt at all) one shared, trustworthy classification
    of each plan's draft into exactly one of `current`, `missing`, `stale`, `malformed`,
    `path-escaping`, `duplicate`, or `digest-mismatched`, in the priority order Architecture
    states, computed fresh each run from the sidecar entry when one exists plus a
    live file/row check — `missing` means no file exists on disk, independent of whether
    a sidecar entry exists — never stored as a new sidecar `status` value, so a `seed-state.json`/`seeds/`
    tree written under the current schema classifies as `current` unmodified with
    no migration step. Owns the sidecar `draft_seed_path` escape check directly (extending
    `_validate_draft_seed_path`'s coverage to `seed-state.json`, which nothing validates
    today) since it is this module's only consumer. Classifies a plan row whose stored
    `draft_seed_path` still begins with the legacy `seeds/` prefix exactly as it would
    a `plan-seed-drafts/`-prefixed one — no rename or rewrite of the canonical roadmap
    artifact, per Architecture. The plan row's own `draft_seed_path` is authoritative
    for the live file/digest check whenever it disagrees with the sidecar entry's
    stored path; materialization rewrites the entry's stored path to match the row's.
    A well-formed on-disk file with no known-good digest to compare against — its
    sidecar entry records a null `digest` (permitted by `validate_seed_state` for
    a row a revision added before any file existed), or it has no sidecar entry at
    all despite a file already sitting at its `draft_seed_path` (a hand-placed draft,
    or a new row's basename landing on a retired row's leftover file) — classifies
    `digest-mismatched`, not `stale` or `missing` — nothing here is ever silently
    treated as `current` or regenerated without the diff-report safety every other
    content-bearing state gets, and `digest-mismatched` is the state step 10's accept
    action exists to resolve. Documents the seven-state classification, its precedence
    order, and this module's position as a leaf below `roadmap.py` and `roadmap_view.py`
    (like `roadmap_gates.py`) in `ROADMAP_FORMAT.md` and `CLAUDE.md`'s module-edge
    list, alongside step 9's edit for the gates it removes — the `CLAUDE.md` edit
    also corrects the existing "Roadmap's five modules" headline count to six, not
    only adding the new module's own entry. Routes `_confirm_invalidated_roadmap_seed`
    through this classification directly (confirming on any non-`current` state, not
    only the sidecar's raw `invalidated`), so `create --from-existing` stops silently
    trusting content this plan's own Architecture says a user hasn't necessarily reviewed.
  files:
  - ROADMAP_FORMAT.md
  - CLAUDE.md
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  creates:
  - plan_tool/roadmap_seed_manifest.py
  - tests/test_roadmap_seed_manifest.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: reused to classify a draft as malformed or duplicate (plan-row basename collision)
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/03-module-that-classifies-every-plan-draft.md
  status: done
- id: 4
  title: Make explicit seed refresh generate each plan's seed independently
  intent: Lets an explicit refresh continue past one plan's failed generation call
    — completing every other plan and reporting which landed versus which stayed invalidated
    — instead of aborting the whole run and discarding already-succeeded plans the
    way today's single multi-plan call does. Retires `plan_tool/prompts/roadmap-refresh-seeds.md`'s
    multi-seed reply protocol ("one block for every plan"), replacing it with step
    2's per-plan `roadmap-seed.md` prompt — this must land before step 9, which deletes
    the `STAGES[-1].side_output_seed_paths`-based bundle plumbing `_refresh_stage_for_artifact`
    reads today; landing step 9 first breaks `--refresh-seeds` outright. Adds a third
    outcome distinct from today's binary `SEED_REFRESH_OUTCOME_APPLIED`/ `SEED_REFRESH_OUTCOME_EXHAUSTED`,
    for a batch where some plans succeed and others fail, with its own exit code —
    step 5's `--materialize`, sharing this per-plan failure-isolation policy, reports
    the same three-way outcome for its own batch runs, so neither command leaves an
    automated caller guessing what a mixed result means.
  files:
  - plan_tool/roadmap.py
  - plan_tool/prompts/roadmap-refresh-seeds.md
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: refresh now calls this per-plan primitive once per plan id instead of assembling
      one multi-seed reply itself
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/04-make-explicit-seed-refresh-generate.md
  status: done
- id: 5
  title: Add a CLI flag to materialize recoverable draft-seed states
  intent: Lets an operator materialize exactly the plan ids step 3 classifies `missing`,
    `stale`, `malformed`, `path-escaping`, or `digest-mismatched` — every state regeneration
    can actually fix — one at a time, without regenerating an already-`current` draft
    or touching `duplicate`, which is a plan-row collision no regeneration fixes.
    Genuinely deliverable now for a fresh roadmap's first materialization and for
    resuming a partial or content-drift failure. A separate, coexisting entry point
    from `--refresh-seeds` (step 4), not a replacement for it; skipping drafts a revision
    left genuinely unaffected additionally needs `roadmap-incremental-revision.md`
    (see Architecture, Deferred) — until it ships, a revision still invalidates every
    tracked draft together, so this flag has nothing to skip right after one. Materializing
    any state where a prior draft file exists — `stale`, `malformed`, `path-escaping`,
    or `digest-mismatched`, all distinguished from `missing` by that prior file —
    writes the same before/after diff `--refresh-seeds` already produces (`seed-refresh-report.md`),
    so a hand edit's loss is never invisible. One invocation processes every currently
    recoverable plan id by default, sharing step 4's per-plan failure-isolation policy
    — one plan's failed regeneration doesn't abort the rest — so a batch materialize
    behaves predictably. An optional plan-id argument targets exactly one, leaving
    every other draft untouched, and refuses in one of two ways — an id absent from
    the roadmap (no plan row, so no classification exists to name) refuses with "no
    such plan in this roadmap"; a known id classified `current` or `duplicate` refuses
    naming that actual classification — mirroring step 6's promotion refusal — rather
    than silently no-opping or regenerating something already fine.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  - 4
  depends_on_notes:
    2: used to generate each targeted plan's seed
    3: used to select every plan id classified missing, stale, malformed, path-escaping,
      or digest-mismatched
    4: reuses step 4's landed refresh symbols (RoadmapSeedRefreshChange/Failure/Result,
      SEED_REFRESH_OUTCOME_PARTIAL, _RC_PARTIAL, _render_seed_refresh_result) verbatim
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/05-cli-flag-materialize-recoverable-draft.md
  status: done
- id: 6
  title: Make seed promotion refuse missing, stale, malformed, path-escaping, duplicate,
    or digest-mismatched drafts
  intent: Closes the gap where a promoted seed could be invalidated-but-unrefreshed,
    hand-edited, or otherwise non-`current` on disk without --apply ever noticing
    — refuses on any classification but `current`. Replaces `_apply_roadmap_seeds`'s
    existing ad hoc preflight — its `source.is_file()` missing check and its bare
    `parse_draft_seed_provenance` unparseable check — with step 3's classification,
    keeping only that preflight's unrelated destination-collision check (`dest.exists()`);
    a hand-edited-but-well-formed draft that today's loop calls fine must not stay
    promotable once this step's refusal ships beside it. Re-runs step 3's classification
    immediately before the atomic commit, after `_confirm_apply_seeds`'s interactive
    prompt returns, and refuses anything no longer `current` at that point — the prompt
    can block for as long as an operator takes to answer, and without a second check,
    a draft that turned `stale` or `digest-mismatched` while it sat open (a concurrent
    `--refresh-seeds`, `--materialize`, or hand edit) would still promote on the preflight's
    now-stale verdict. Extends `RoadmapApplyResult` and `_render_apply_result` to
    name each refused draft's actual classification for all six non-`current` states
    — today only `missing_drafts` and `unparseable_drafts` exist, so `stale`, `path-escaping`,
    `duplicate`, and `digest-mismatched` would otherwise refuse with no reason line,
    unlike step 5's `--materialize`, which already commits to naming the real classification
    on refusal. Extends the same naming to `RoadmapSeedApplyResult`'s telemetry fields
    and their `DATA_CONTRACT.md` documentation, so all six states are counted, not
    only the original two.
  files:
  - plan_tool/roadmap.py
  - plan_tool/run_log.py
  - DATA_CONTRACT.md
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  - 5
  depends_on_notes:
    1: supplies the shared content check `_apply_roadmap_seeds`'s bare `parse_draft_seed_provenance`
      call is replaced by
    3: supplies the per-plan classification apply refuses on (anything but `current`)
    5: the refusal-rendering hint line points operators at `--materialize`, which
      this step's flag builds
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/06-make-seed-promotion-refuse-missing.md
  status: done
- id: 7
  title: Route the roadmap view's seed summary through the new manifest module
  intent: Routes `summarize_seed_lifecycle`'s plain current/invalidated/untracked-retired
    counts through step 3's classification — `current` maps to `current`, every other
    classification folds into `invalidated`, and `untracked` is retired as a reachable
    bucket since step 3 classifies every plan row. This is a real behavior change,
    not a pure refactor — a draft whose sidecar still says `current` but that step
    3's live file/digest check finds drifted now shows `invalidated`, catching exactly
    the mistracked-drift case this plan exists to fix. The fold is for those coarse
    counts only — the existing `_summary_attention` guidance line reads step 3's classification
    directly, the same source step 8 reads, so it can recommend the specific tool
    that clears each state — `missing`/`stale`/`malformed`/ `path-escaping` recommend
    `--materialize`; `digest-mismatched` gets its own line, distinct from the other
    four — review the diff, then choose `--accept-seed` (keep the edit) or `--materialize`
    (discard it) — since it is, by Architecture's own description, the one state step
    10's accept action exists to save, and folding it into the same one-line `--materialize`
    recommendation as the other four would steer an operator toward destroying exactly
    what accept preserves; `duplicate` recommends resolving the colliding plan rows
    in a roadmap revision, since no seed regeneration fixes a plan-row collision;
    `--refresh-seeds` stays the recommendation only where an operator wants every
    draft regenerated together. Step 8 adds its own new per-state report lines, also
    reading step 3 directly, beside this routed summary.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  complexity: low
  change_type: feature
  depends_on:
  - 3
  - 5
  depends_on_notes:
    3: becomes the source summarize_seed_lifecycle reads from
    5: the routed `_summary_attention` lines recommend `--materialize <plan-id>` for
      four of the six non-`current` states
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/07-route-roadmap-view-seed-summary-through.md
  status: done
- id: 8
  title: Show missing, stale, malformed, path-escaping, duplicate, and digest-mismatched
    seed states in roadmap views
  intent: Lets an operator see from `roadmap --view` alone exactly which drafts are
    missing, stale, malformed, path-escaping, duplicate, or digest-mismatched before
    running apply, reading step 3's per-plan classification directly rather than step
    7's folded three-bucket summary. Also reports any sidecar entry or on-disk file
    matching no current plan row — an orphan left behind by a roadmap rewrite that
    dropped that plan — visibly, though cleanup stays out of scope. The directory-file
    half of this scan walks both `plan-seed-drafts/` and, when present, a roadmap's
    legacy `seeds/` directory — every pre-existing roadmap stays on the legacy prefix
    forever per Architecture, so a scan naming only the new directory would never
    catch an orphan left in the old one. Routes `roadmap_view.py`'s existing `_render_draft_seed`
    (the `--view walk` per-plan warning, today its own digest-blind file-exists-and-parse
    check printing "missing"/"unparseable") through step 3's classification too, so
    `--view walk` and this step's new report lines never call the same draft two different
    things — a digest-mismatched hand edit no longer renders as clean in one view
    and flagged in another.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 7
  depends_on_notes:
    3: supplies the per-plan classification this step's new report lines read directly
    7: the routed-through manifest read this step's lines sit alongside in the same
      view module
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/08-show-missing-stale-malformed-path.md
  status: done
- id: 9
  title: Stop stage 4 from generating any seed body inline
  intent: Drops inline seed-body generation from stage 4's own call entirely — every
    draft now materializes only through step 2's per-plan primitive — so `04-roadmap.md`
    publishes as soon as its own gates pass. Stage 4 is the only stage that ever sets
    `RoadmapStage.side_output_seed_paths`, so clearing it there makes the whole bundle-write
    machinery unreachable for every stage, not just retired for stage 4 — `_write_stage_outputs`'s
    staged-seed-tree/atomic-swap branch and its `preserve_existing_seeds` parameter,
    `ArtifactEnvelope.draft_seed_bundle`, `_StageOutcome.draft_seed_bundle`, `_plans_side_output_seed_paths`,
    and the bundle half of `_lift_stage_reply`'s return value. This step deletes all
    of it rather than leaving it as inert generality, but only once step 4 has already
    migrated `refresh_roadmap_seeds`/`_refresh_stage_for_artifact` off of `STAGES[-1].side_output_seed_paths`
    — that helper is the one other reader, and stripping the field before step 4 stops
    consuming it makes `_lift_stage_reply` lift no bundle for the refresh call either,
    so `refresh_roadmap_seeds` returns `SEED_REFRESH_OUTCOME_EXHAUSTED` on every call
    and `--refresh-seeds` breaks outright. Without retiring the write path at all,
    an ordinary `--from-stage 4` regeneration would still hit the existing stage-and-replace
    path with an empty bundle and wipe every independently materialized seed file
    — exactly what `## Out of scope` forbids. Removes `check_draft_seed_provenance`
    and the bundle-dependent half of `check_draft_seed_bundle_alignment` from `PLANS_GATES`
    (no bundle ever reaches the envelope again), while keeping that check's plan-row-vs-plan-row
    basename-collision half live as step 1's generalized, bundle-free gate. Deletes
    `_mark_roadmap_seeds_current` outright — its "mark every row current" behavior
    has no caller once generation moves entirely off the stage-4 write path, and keeping
    it as dead code beside the invalidation path below would be exactly the ambiguity
    this fix removes. The no-feedback-rerun invalidation this step's acceptance criterion
    promises cannot key on `side_output_seed_paths` (deleted above) or on the `feedback_applied`
    branch alone (today's only trigger, and the gap this step exists to close) — it
    keys on stage identity and `_write_artifact`'s existing `replaced` return value
    instead — any stage-4 write that replaces an existing `04-roadmap.md`, with or
    without feedback, calls `_invalidate_roadmap_seeds` unconditionally on every pre-existing
    sidecar entry; a fresh (non-replacing) stage-4 write has nothing to invalidate.
    This new trigger is additive, not a replacement — `run_roadmap`'s existing per-stage
    (any stage 1-4) immediate invalidation the moment a stage writes with open feedback
    in its predecessor stays exactly as it is today, so a run interrupted after an
    earlier stage's feedback-driven write but before stage 4 ever runs still invalidates
    — losing that trigger would silently reopen this plan's own stale-reads-as-current
    defect for an interrupted run instead of only a completed no-feedback rerun. This
    closes the no-feedback rerun gap where stale drafts would otherwise still classify
    `current` against a roadmap version they no longer match, and a freshly-published
    row (nothing to invalidate) gets no sidecar entry until step 2 materializes it,
    which step 3 classifies `missing`. `_invalidate_roadmap_seeds` itself stops recomputing
    an entry's digest from the live file when invalidating — it flips `status` only
    and leaves the recorded digest exactly as it was, for both this new stage-4 trigger
    and the existing earlier-stage feedback path that already calls it unmodified.
    Without this, invalidation would silently overwrite a hand-edited draft's recorded
    digest with the hand edit's own hash, laundering it from `digest-mismatched` to
    plain `stale` and costing it step 10's accept eligibility and the signal that
    a human touched it. Changes the `draft_seed_count` computation (or its replacement)
    to count seeds actually written this run rather than every plan row's declared
    path, so it reads zero for every stage-4 write; updates `DATA_CONTRACT.md`'s `draft_seed_count`
    line to say the field is always zero now (not "zero for stages 1-3", since no
    stage generates seeds inline anymore). Routes `cli/roadmap_cmd.py`'s `_create_handoff_lines`
    through step 3's classification so it only prints a `create --from-existing` handoff
    for a plan whose draft classifies `current`, and otherwise reports the roadmap
    not-seed-ready and names `--materialize`/`--refresh-seeds`. Rewrites `roadmap-plans.md`
    to stop asking the model for seed-fence output entirely — the worked example and
    the "rules your artifact is checked against" section currently describe the two
    removed gates — so the model authors plan rows and their `draft_seed_path` values
    only (step 1 already moved the prefix itself to `plan-seed-drafts/`). Rewrites
    `roadmap_cmd.py`'s `_overwrite_summary_lines`/`copy_aside_for` stage-4 copy-aside
    advice, which today tells an operator a stage-4 rewrite "also replaces the slug
    `seeds/` tree atomically" — the opposite of this step's own acceptance criterion
    once it ships — and updates the three tests pinning that wording. Updates `ROADMAP_FORMAT.md`'s
    default-location prose ("the default draft directory is `.../seeds/`"), its `draft_seed_path`
    prefix rule ("must begin with `seeds/`"), and its worked examples to the new `plan-seed-drafts/`
    name, and drops its gate table's now-removed `check_draft_seed_bundle_alignment`-against-`draft_seed_bundle`
    row alongside the violations it names — a reference doc describing checks that
    no longer run is stale documentation, not a live-loaded contract, so this can
    land here rather than needing step 1's earlier timing. Also rewrites ROADMAP_FORMAT.md's
    "Feedback invalidation and explicit refresh" subsection to add `--materialize`
    as a regeneration path alongside `--refresh-seeds`, instead of the current "only
    regeneration path" claim, and updates its `seeds/archive/` reference to track
    the rename — step 10's accept action does not exist yet when step 9 lands, so
    step 11 (which depends on step 10) later extends this same subsection with the
    accept-action sentence rather than step 9 writing it prematurely. Sweeps every
    other "invalidation means feedback" statement to the new any-stage-4-replace trigger,
    since invalidation is no longer feedback-exclusive once this step ships — `RoadmapResult.invalidated_seed_count`'s
    docstring, `cli/roadmap_cmd.py`'s module docstring and `_seed_invalidation_summary_lines`
    wording ("N roadmap seed(s) are invalidated by applied feedback"), `cli/authoring.py`'s
    `_confirm_invalidated_roadmap_seed` prompt text ("is invalidated by applied feedback"),
    and `CAPABILITIES.md`'s `architecture-roadmap` entry ("feedback invalidates rather
    than overwrites those seeds") — all five would misreport why an ordinary no-feedback
    rerun's drafts went invalid otherwise.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_gates.py
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/authoring.py
  - plan_tool/prompts/roadmap-plans.md
  - plan_tool/prompts/roadmap-revision.md
  - ROADMAP_FORMAT.md
  - CAPABILITIES.md
  - CLAUDE.md
  - DATA_CONTRACT.md
  - tests/test_roadmap.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap_format.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  - 4
  - 5
  depends_on_notes:
    2: is the replacement path seeds now materialize through once stage 4 no longer
      produces them inline
    3: reports the not-yet-seed-ready state stage 4 can now legitimately leave behind
    4: refresh must stop consuming the stage-4 bundle plumbing before this step retires
      it, or `--refresh-seeds` breaks outright
    5: the ROADMAP_FORMAT.md subsection this step rewrites now names `--materialize`
      as a regeneration path
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/09-stop-stage-generating-any-seed-body.md
  status: done
- id: 10
  title: Add a CLI action to accept a hand-edited draft as current
  intent: Gives an operator a way to promote a deliberately edited `digest-mismatched`
    draft without losing the edit — records the file's live digest as `current` in
    `seed-state.json` directly, calling neither step 2's generation primitive nor
    step 4's refresh, so a reviewed hand edit has a path to promotion that today's
    only remedies (step 4's refresh, step 5's materialize) would otherwise overwrite.
    Refuses on every classification but `digest-mismatched` — accepting a `missing`
    or `malformed` draft as current would promote a broken or absent file. Because
    Architecture's precedence checks `digest-mismatched` before `malformed`, *any*
    hand edit lands in `digest-mismatched` regardless of whether its content is well-formed
    — a broken edit (bad YAML, a missing required field) never reaches `malformed`
    to be caught there. Accept therefore runs the draft through step 1's shared content/provenance
    validator before writing `current`, and refuses (reporting the validation failure)
    when it fails, rather than trusting `digest-mismatched` alone as proof of a reviewed,
    valid edit. When the plan is already promoted (sidecar `published` true, `plan-seeds/<id>.md`
    already on disk), also re-syncs that copy directly with the accepted content,
    the same mechanical way `refresh_roadmap_seeds` already does — `--apply`'s unconditional
    destination-collision refusal would otherwise block a second promotion of an already-promoted
    plan regardless of the draft's new `current` classification, so without this the
    accept action would have no path to the outcome its own reason for existing promises.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  - 5
  depends_on_notes:
    1: supplies the shared validator accept runs the draft through before writing
      `current`
    3: supplies the classification this action checks before accepting (must be digest-mismatched)
    5: the `--accept-seed` mutual-exclusion wiring needs `--materialize` already registered
      in `run_mode_group`
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/10-cli-action-accept-hand-edited-draft.md
  status: done
- id: 11
  title: Update roadmap docs for per-seed draft materialization
  intent: Keeps the roadmap walkthrough's call-count claim and stage-4/seeds description
    accurate now that seeds materialize independently instead of inside stage 4's
    single call, including the new accept action for hand-edited drafts. Sweeps the
    same staleness in `docs/ROADMAP_DEMO_ORCHESTRATION.md` — its call-count line,
    its `04-roadmap.md + seeds/` table row, and its `seeds/<plan-id>.md` worked-example
    path all describe today's one-call stage 4, the same claim this step already corrects
    in the walkthrough doc. Also updates `docs/ARCHITECTURE.md`'s Roadmap paragraph
    ("five modules" becomes six once step 3 adds `roadmap_seed_manifest.py`; the "default
    completion prints runnable `create --from-existing` lines" claim becomes conditional
    on step 3 classifying the draft `current`) and `CAPABILITIES.md`'s `architecture-roadmap`
    entry, which repeats the same two claims. Also finishes ROADMAP_FORMAT.md's "Feedback
    invalidation and explicit refresh" subsection that step 9 rewrites — step 9 can
    only add `--materialize` there since step 10 doesn't exist yet when step 9 lands;
    this step adds the sentence naming step 10's accept action as the third regeneration/promotion
    path, now that step 10 has landed.
  files:
  - docs/ROADMAP_WALKTHROUGH.md
  - docs/ROADMAP_DEMO_ORCHESTRATION.md
  - docs/ARCHITECTURE.md
  - CAPABILITIES.md
  - ROADMAP_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  - 5
  - 6
  - 8
  - 9
  - 10
  depends_on_notes:
    9: changes the call-count and stage-4 behavior this doc currently describes as
      one combined call, and leaves ROADMAP_FORMAT.md's regeneration-paths subsection
      one sentence short of naming the accept action
    10: adds the accept action to the roadmap seed lifecycle this doc narrates, and
      supplies the sentence this step adds to ROADMAP_FORMAT.md's regeneration/promotion-paths
      subsection
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization/11-update-roadmap-docs-per-seed-draft.md
  status: done
---
# Roadmap Seed Materialization

## Overview

Stage 4 roadmap plan derivation will keep the canonical roadmap manifest and each roadmap-derived draft plan seed independently materialized, validated, and traceable, so a roadmap revision no longer needs to carry or re-emit every seed body in `draft_seed_bundle`. A dedicated draft-seed materialization flow generates and validates one plan seed at a time — against its plan row, upstream roadmap context, and the current repository — making independent backend calls and recording each draft's status (`current`/`invalidated`) and output digest; a failed attempt publishes nothing durable, and call-level observability for these backend calls is deliberately out of scope (see Deferred). The stage-4 manifest contract maps every roadmap plan row to its expected draft-seed path and a content identity, so a roadmap is seed-ready only when every manifest entry has a matching valid draft; `roadmap --apply` promotes only a complete, verified set of drafts that matches the accepted roadmap, and its preflight plus the roadmap views report manifest completeness and stale/missing/mismatched seed state.

## Problem statement

Today's stage-4 write couples `04-roadmap.md` to an all-or-nothing `seeds/` tree: producing any file requires one backend call to generate every plan's seed body via `draft_seed_bundle` before any file lands, and a canonical revision blanket-invalidates every tracked draft rather than only the ones it actually changed. This makes partial materialization impossible to represent, forces a single all-or-nothing regeneration call even to backfill one missing or failed draft, and gives `roadmap --apply` no way to distinguish a missing, stale, or mismatched draft from a promotable one without re-deriving everything from the bundle. Skipping regeneration of drafts a revision left genuinely unaffected additionally needs per-plan-id targeted invalidation, which is out of this plan's scope (see Architecture, Deferred): until `roadmap-incremental-revision.md` ships, a revision still invalidates every draft together, so this plan's near-term win is backend-call independence, resumability, and first-time/missing-seed backfill, not skipping revision-unaffected drafts.

## Architecture

Stage 4 has two distinct responsibilities and represents them separately: the canonical roadmap decides *which* implementation plans exist and their ordering, while draft-seed materialization supplies the independently reviewable `create --from-existing` input for each plan. The manifest is their durable join, using stable plan IDs and content identity rather than positional list order or a bundle copied into YAML. It extends the roadmap directory's existing `seed-state.json` lifecycle sidecar (already tracking each plan id's `draft_seed_path`, status, digest, and promotion state) rather than introducing a parallel store — the sidecar's fields are the join's foundation, not a new concept to invent.

Draft seeds live under a new directory name, `plan-seed-drafts/` (renamed from `DRAFT_SEEDS_DIRNAME`'s current value, `seeds`) — distinct from, and not to be confused with, the unrelated top-level `plan-seeds/` directory `--apply` promotes into. Step 2's primitive and step 9's rewritten model prompt are asked to use the new name for every new write (a new roadmap, a newly added plan row); the widened path validator structurally accepts either prefix on any row, so this is a strong convention rather than a hard per-row gate distinguishing brand-new rows from ones carried forward from a predecessor artifact — both prefixes remain, and always will remain, structurally valid. An existing roadmap's already-stored `04-roadmap.md` and `seed-state.json` paths are never rewritten, so a pre-existing `seeds/`-prefixed path keeps resolving and classifying exactly as before. The rename changes only what new writers are asked to do going forward, never the canonical roadmap artifact and never what a reader accepts.

Per-plan draft status is a classification into exactly one of `current`, `missing`, `stale`, `malformed`, `path-escaping`, `duplicate`, or `digest-mismatched`, computed fresh each time the manifest module runs rather than stored as a new sidecar `status` value — the sidecar keeps its existing `current`/`invalidated` meaning. `missing` means no file exists on disk, independent of whether a sidecar entry exists — a row with no entry and no file classifies `missing` the same as a row whose entry exists but whose file is gone. A row with no sidecar entry yet a file already present at its `draft_seed_path` classifies `digest-mismatched` instead — the same rule as an entry recording a null digest, since neither case has a known-good digest to trust. `duplicate` reuses `check_draft_seed_bundle_alignment`'s existing plan-row basename-bijection logic, generalized to run outside the stage-4 gate context — a static, file-free comparison across the roadmap's current plan rows. `path-escaping` reuses `_validate_draft_seed_path`'s check applied to the sidecar's own `draft_seed_path` field, not the plan row's: an accepted roadmap's plan-row paths are already gated at parse time and can never carry an escaping value themselves, so the sidecar entry is the one place this state is reachable at runtime.

When more than one condition holds for the same draft, precedence resolves it in this order, first match wins: `duplicate` (a plan-row property, checked before any file read), `path-escaping` (the sidecar entry itself is untrustworthy), `missing` (no file on disk), `digest-mismatched` (file exists and its digest disagrees with the sidecar's recorded digest), `stale` (sidecar status is `invalidated` and nothing above matched — checked before content validation, so an invalidated entry never also has to run it), `malformed` (only reached when the sidecar is not `invalidated`: file exists, digest matches, but the shared content/provenance check fails — genuine unexpected corruption, not a revision-driven change the entry hasn't caught up to yet), `current`. Checking `stale` ahead of `malformed` matters: the shared content check validates a draft's `roadmap_components` against the plan row's *current* `component_ids`, which a revision can change at the same moment it invalidates the entry — without this order, an untouched, digest-matching draft would misclassify `malformed` (reads as corrupt) instead of `stale` (the true cause), and that label reaches every consumer below. This same order governs every consumer that reads a state, not only step 3's classifier — step 5's targeting, step 6's refusal, and step 8's view line all resolve the same draft to the same state. `duplicate` stays reachable mainly as defense-in-depth, the same as `path-escaping`: step 1's generalized plan-row check already excludes it from an accepted `04-roadmap.md` at stage-4 gate time, so it surfaces here only through a hand-edited artifact or a stale sidecar entry the gate never re-validated.

One seed materialization job owns one draft path. It can retry or resume without asking a backend to reconstruct siblings, and it cannot modify the canonical plan rows. The promotion path reads the manifest plus draft state and refuses any incomplete or mismatched set before copying anything into `plan-seeds/`. State updates and file writes use a publish boundary that never presents a valid-looking manifest pointing at a half-written draft.

This effort composes with `roadmap-incremental-revision.md`, not yet promoted to a plan: once a targeted canonical revision determines which plan IDs become stale, this effort's per-plan materialization can target only those IDs. Until that sibling ships, every revision still invalidates every tracked draft together (`_invalidate_roadmap_seeds`), so this plan's own deliverable value is backend-call independence, resumability, and first-time/missing-seed backfill — not skipping revision-unaffected drafts. It does not assume that a user has accepted a draft simply because the system can generate one.

Consequently, stage 4's own call stops generating seed bodies inline entirely — every draft materializes only through step 2's per-plan primitive — so `04-roadmap.md` publishes as soon as its own gates pass, clearly reporting that the roadmap is not seed-ready until materialization completes; draft seed generation becomes individually resumable and may update one selected non-`current` draft without rewriting unrelated drafts; and promotion refuses any draft step 3 classifies as anything but `current` instead of relying on a single embedded bundle as proof of completeness.

## Input

This plan reads and extends the roadmap directory's existing `seed-state.json` lifecycle sidecar, which already tracks each plan id's `draft_seed_path`, status, digest, and promotion state — these fields are the manifest/draft join's foundation, not a new concept to invent. It also consumes the existing explicit `--refresh-seeds` safety model and its before/after reports: `--refresh-seeds` stays the full, unconditional one-call-per-plan regenerate (step 4 makes that call itself per-plan and resumable); the new materialize flag (step 5) is a separate, coexisting entry point that targets only the plan ids step 3 currently classifies `missing`, `stale`, `malformed`, `path-escaping`, or `digest-mismatched`. Both retain the rule that feedback never silently overwrites a derived seed. It composes with `roadmap-incremental-revision.md`, not yet promoted to a plan: once that sibling ships, a targeted canonical revision will mark only genuinely affected plan IDs stale and this effort's materialization will target only those IDs; until then, every revision still invalidates every tracked draft together, so that particular benefit is deferred (see Problem statement, Architecture, Deferred).

## References

- `ROADMAP_FORMAT.md` — defines the current `draft_seed_bundle`/`seed-state.json` stage-4 contract this plan extends into a per-plan manifest: `draft_seed_path` validation and the bundle/plan-row bijection gate (`check_draft_seed_bundle_alignment`) survive as step 1's generalized, bundle-free plan-row check; the provenance gate (`check_draft_seed_provenance`) and the bundle-dependent half of the bijection gate are removed by step 9 and reused instead as step 3's post-hoc, per-draft validation.
- `docs/implementation-plans/plan-seeds/roadmap-incremental-revision.md` — the composing plan seed whose targeted canonical revision determines which plan IDs go stale; this plan materializes only those IDs once a revision is accepted.
- `SEED_FORMAT.md` — the plan-seed authoring format each materialized draft body must conform to, unchanged by this plan (see `Out of scope`).
- `DATA_CONTRACT.md` — persisted schema conventions for the roadmap directory's `seed-state.json` sidecar and the `draft_seed_count` field this plan's manifest extends rather than replaces.
- `docs/ROADMAP_WALKTHROUGH.md` — the existing narrative description of stage 4's single-call seed generation that step 11 updates once materialization becomes per-plan and independently resumable.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing how `create`, `detail`, Jira story generation, implementation, or plan/code reconciliation consume a promoted seed.
- Auto-promoting drafts, auto-accepting roadmap feedback, or treating draft materialization as user approval.
- Redesigning the plan-seed prose format, adding a second seed store beyond the existing `seed-state.json` sidecar, or introducing a remote database/object store for seed state.
- Regenerating every seed on a roadmap revision, deleting a stale seed to hide it, or writing a replacement without the explicit materialization/refresh action.
- General background scheduling, parallelism policy, or backend liveness instrumentation beyond the batch-observability work already under separate validation.
- A correctness gate on seed style, length, or model agreement — the binary observable is whether each manifest plan ID has exactly one valid draft with the recorded identity, and whether promotion refuses every other state.
- Reorganizing unrelated roadmap stages, `create`, or the generic plan-seed format — only the extraction necessary to separate stage-4 manifest handling from draft-seed materialization, while retaining one shared path-validation and promotion-preflight authority, is in scope.
- Folding targeted feedback revision, model-call observability, parallel job execution, seed approval workflow, or a new artifact storage system into this plan; route out-of-scope discoveries to `BACKLOG.md` or `BUG_BACKLOG.md`. (Distinct from step 10's accept action, which reconciles a `digest-mismatched` draft's recorded digest to match a live hand edit — including re-syncing an already-promoted `plan-seeds/` copy with that same content — a mechanical identity/content sync, not an approval gate.)

## Risks

- An existing roadmap's persisted `seeds/`-tracked drafts and `seed-state.json` entries — the only on-disk state involved; `draft_seed_bundle` itself is never persisted — could silently lose seed content if a content-identity decision fails to preserve them exactly. Step 3 owns this: its classification is computed fresh from existing `seed-state.json` fields and a live file check rather than stored as new sidecar `status` values, so a pre-existing tree classifies as `current` unmodified and no schema migration is required. Mitigation: if a classification genuinely needs a field the current schema lacks, stop and surface that schema decision explicitly rather than silently reinterpreting an existing field.
- Moving seed generation from stage 4's single batched call to step 2's per-plan primitive means a full `--refresh-seeds` or `--materialize` run on an N-plan roadmap issues N backend calls instead of one, each resending the upstream `01-domain.md`/`02-constraints.md`/`03-components.md` context the current combined-call prompt only sends once. Accepted: this is the direct cost of the resumability and backend-call independence this plan exists to buy, and the call count is bounded by the roadmap's own plan count, not unbounded. Trimming or caching the resent upstream context is a deliberate non-goal here (see Out of scope's model-call-observability exclusion) — a future optimization, not a defect in this design.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (feature) — tests covering the behavior this step changes; green before completion.
- step 10 (feature) — tests covering the behavior this step changes; green before completion.
- step 11 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A roadmap with several plans materializes, fails, resumes, and refreshes one draft at a time; each attempt leaves non-targeted draft files unchanged.
- Missing, stale, malformed, path-escaping, duplicate, and digest-mismatched drafts are visible in views and block promotion before any destination write.
- A complete matching set promotes exactly the manifest's drafts; a failure or interruption during materialization never leaves a manifest claiming a nonexistent or partial file is valid.
- An existing roadmap's `seeds/`-tracked (pre-rename) drafts and `seed-state.json` entries classify and promote identically under the new manifest with no file rewrite and no schema migration, passing artifact/gate checks unchanged.
- A newly written or newly added plan row's draft lands under `plan-seed-drafts/`; an existing roadmap's `seeds/`-prefixed rows keep resolving and classifying without any rewrite of `04-roadmap.md` or `seed-state.json`.
- Feedback invalidation and explicit refresh retain their current safety rule: derived prose changes only under the explicit writer, never as a side effect of a canonical roadmap revision.
- A stage-4 write — fresh or `--from-stage 4` — completes and `04-roadmap.md` publishes with zero seeds materialized, reporting the roadmap not-seed-ready separately; it never stages, replaces, or deletes an already-materialized seed file.
- A stage-4 write that replaces an existing `04-roadmap.md` — with or without feedback — invalidates every pre-existing sidecar entry; a no-feedback rerun's surviving drafts classify `stale`, never silently `current`.
- After a stage-4 write with zero seeds materialized, the run's own handoff output never suggests `create --from-existing` for a plan whose draft isn't `current`.
- Views report a sidecar entry or on-disk file, in either `plan-seed-drafts/` or a legacy `seeds/` directory, matching no current plan row, without deleting it.
- An operator can accept a `digest-mismatched` draft's live content as `current` without calling generation; if never promoted, `--apply` then succeeds on it, and if already promoted, the accept action directly re-syncs the `plan-seeds/<id>.md` copy with the accepted content. Accept refuses every other classification.
- A `--materialize <plan-id>` naming a `current` or `duplicate` draft refuses naming that classification; naming an id the roadmap doesn't have refuses with "no such plan in this roadmap." Neither case silently no-ops or regenerates.
- The roadmap view's folded current/invalidated summary reflects step 3's live classification, not the sidecar's raw stored status: a plan the sidecar still marks `current` but whose file step 3 finds drifted counts as `invalidated` in that summary.
- `roadmap --apply`'s promotion preflight and `--view walk`'s per-plan warning both resolve a draft to the same state step 3's classifier would — never a different word ("unparseable" vs. `malformed`) or a different verdict for the same file.
- A run interrupted after an earlier stage's feedback-driven write but before stage 4 ever runs this session still invalidates every tracked draft, the same as it does today; the new any-stage-4-replace trigger adds to that existing protection rather than replacing it.
- `create --from-existing` prompts for confirmation on a draft step 3 classifies anything but `current` — not only the sidecar's raw `invalidated` status — so an unreviewed hand edit or a malformed draft is never silently ingested.

## Deferred

Work postponed rather than permanently excluded — unlike `## Out of scope`, each item here can come back.

- **Targeted canonical-revision mechanics for marking plan IDs stale.** This plan consumes which plan IDs a revision marks stale but does not itself decide how a targeted revision computes that set — that belongs to the composing plan seed `docs/implementation-plans/plan-seeds/roadmap-incremental-revision.md`, not yet promoted to a plan.
- **Model-call observability for the per-plan materialization backend calls.** Run/call-level instrumentation for this flow's independent backend calls is scoped to the batch-authoring-observability lineage (`docs/implementation-plans/2-batch-authoring-observability.md` and its carved follow-on `2-batch-observability-forensics-and-view.md`), not this plan.
- **A seed approval or sign-off workflow.** Promotion here stays a mechanical completeness/identity check; a human-approval gate layered on top is a separate concern this plan does not assume is wanted.
