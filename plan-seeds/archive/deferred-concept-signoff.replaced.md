> **Replaced**: this file has been superseded by `docs/implementation-plans/2-deferred-concept-signoff-gate.md`.
> Preserved here for history; do not edit.

# Plan seed: operator sign-off of a hierarchical deferred-concept tree

This file is a `plan-tool create` input. Use it via:

    plan-tool create --from-existing plan-seeds/deferred-concept-signoff.md --iterate

It is **not** itself a plan — `plan-tool create` consumes the prose below and proposes a step
decomposition; the author then runs `plan-tool detail` per step.

> **Scope boundary — this seed adds an operator sign-off gate over the concepts a plan defers,
> not a new planning stage.** It introduces one machine artifact (a concept-tree sidecar), wires a
> sign-off gate into `create` and `detail`, adds a re-runnable `scope-review` command, and enforces
> coverage of signed-in concepts through the existing completeness audit. It does **not** auto-mint
> steps, redesign the plan schema's step model, or replace the `## Out of scope` / `## Deferred`
> prose (which becomes a one-directional *render* of the tree).

Source: BACKLOG #121 (New capability). When this work ships, its final docs/status step must update
`BACKLOG.md` — remove #121 (or mark it plan-authored if follow-ups remain) per BACKLOG.md's rule.

---

## Overview

Turn the deferral decision — today made silently by Claude in three places — into an explicit,
operator-gated, machine-recorded choice over a **hierarchical concept tree**. The operator starts
at high-level concepts and drills into an indeterminate depth of sub-concepts, selecting at every
level which aspects are **included** vs **deferred** vs **won't-do**. The tree is persisted as a
sidecar, signed off by the operator, and enforced by a coverage audit so an included concept can
never be silently dropped.

Three surfaces consume one shared navigator:

- `create` — a sign-off gate beside the existing change-type / gate review gates.
- `detail` — inline for a single step; **one consolidated sign-off at the end** of a full/batch run.
- `plan-tool scope-review <name>` — a standalone, re-runnable command to change your mind on any
  plan at any time.

## Problem statement — grounded in a real case

An operator missed a critical aspect of a complex plan because the tool marked it deferred when it
should have been included, with **no point at which the operator signed off** on that deferral.
Deferral is decided by Claude in three ungated places:

- Evidence-only `## Out of scope` / `## Deferred` synthesis (`create.py:282-295`).
- The "a branch with no namable live scenario is NOT a step — defer it" decomposition instruction
  (`create.py:1958`).
- `## Deferred` routing when detail generation can't absorb a shared-location find (`detail.py:378-406`).

The schema only records deferral at **step** granularity (`StepScope`, `schema.py:26-38`). A concept
Claude drops *before* it becomes a step leaves no structured trace beyond a prose bullet — and neither
existing interactive gate in `create` (change-type, `create.py:3905`; step gates,
`create.py:4238`/`:5651`) ever asks about concept scope. There is no confirmation flag anywhere that
an operator reviewed a given deferral.

This aligns with MISSION.md's "the structured artifact is the machine contract; the prose is for the
human" — the fix makes the concept tree the machine contract and demotes the `## Out of scope` /
`## Deferred` prose to a render of it.

## Architecture

### A. The concept-tree sidecar (`plan_tool/concept_tree.py`, NEW leaf)

A stdlib-only leaf (dataclasses + save/load + the navigator; no CLI, no Claude imports) modeled on
`review_persistence.py`. Persisted as a **single, VCS-tracked, versioned JSON sidecar**
`plan-details/<slug>/concepts.json`, beside `grounding.json` (the existing precedent for a single
evolving fingerprint-carrying sidecar — the right cardinality, unlike the many timestamped
saved-review sidecars). Add `CONCEPTS_SCHEMA_VERSION = 1`.

Node shape (**flat list + `parent_id`**, not nested — easier to fingerprint/diff/drift-guard, like
the manifest and telemetry):

- `id` — stable content hash (title + parent path); the annotations/coverage key.
- `path` — materialized dotted path, e.g. `auth.mfa.totp` (display + stable ordering).
- `title` — one-line concept name.
- `depth` — int level (0 = top).
- `parent_id` — str | None.
- `order` — int sibling order.
- `state` — `include` | `defer` | `wont_do` (mirrors the `StepScope` 3-way axis).
- `rationale` — one-line **evidence-only** note.
- `source` — `create` | `detail` | `manual`.
- `signed_off` — bool.
- `signed_off_at` — ISO-8601 UTC | None.
- `covered_by` — list[str] owning **step-title slugs** (`derive_step_slug(step.title)`, `detail.py:281`)
  — stable across renumber *and* available on a step with no detail file yet (see §E/§H); never raw step
  ids (renumbered by the structural remedies) and never the detail-*filename* slug (absent on a bare plan).

Top-level `ConceptTree`: `plan_slug`, `schema_version`, `updated_at`, `plan_fingerprint`
(via `compute_plan_fingerprint`), `nodes`. **Drift-guarded** like `Grounding`: a stale
`plan_fingerprint` reads as "re-derive". Register a `PersistedDataclassContract` for
`ConceptTree` / `ConceptNode` in `data_contract.py` with a paired `DATA_CONTRACT.md` section so
`tests/test_data_contract.py` guards it (both the field-documentation and schema-constant assertions
— see the drift-guard checklist in Testing below).

**Path resolution — mirror `grounding.py`, not `locator.py`.** Add a `concepts_path(plan_path)` helper
that computes `plan_path.parent / "plan-details" / slug / "concepts.json"` (reusing
`locator.slug_from_filename`), exactly as `grounding.py:99-111` does for `grounding.json` —
`locator.py` resolves only plan `.md` paths, never the detail-bundle dir. Because the sidecar lands
**inside** the same `plan-details/<slug>/` directory, every archive/move/rename path
(`create.py:687-710` from-existing, `sweep.py:321-413`, `annotate --archive`, the slug-rename
`create.py:788-815`) moves the whole directory and byte-copies non-`.md` files verbatim, so
`concepts.json` travels with the plan for free — no new wiring. **Known shared limitation:**
`_archive_duplicate_plans` (`manifest.py:645-667`, from `sweep --archive-duplicates`) moves only the
plan `.md` and strands the whole bundle — already true for `grounding.json` today; not this feature's
job to fix, called out so it is not a surprise.

Relationship to existing scope machinery is **one-directional (tree is source of truth)**:
`state=defer` → rendered into `## Deferred`; `state=wont_do` → `## Out of scope` (matching the
existing distinction at `create.py:260-264`); a deferred concept mapping to an existing step sets
that `steps[].scope=deferred` + `status_note`; an included concept with no owning step is the
coverage obligation of §E.

### B. Producing the tree — evidence-only (`create` and `detail`)

**Invoker seam (required).** The concept-emit round-trip is a new real-backend shell-out, so every
function that runs it takes an `invoker=` / `claude_invoker=` kwarg defaulting to the real-CLI
shell-out (as `shell_claude_invoker` etc. do), routed through the shared backend / rate-limit-recovery
path like every other orchestrator — never a bare `subprocess`. Add its seam to **TESTING.md's
neutralization table** and confirm the conftest autouse gate covers it, or tests silently spawn the
real `claude` binary. Tests stub the emit via the injected `invoker` (see Testing).

- **create:** one Claude round-trip emits a hierarchical candidate-concept JSON with a *suggested*
  state + one-line evidence rationale per node — folded into the distill discriminator
  (`prompts/distill-seed.md`, already models `outcome: single|split`) or a sibling checkpoint.
  Shape: `{"concepts": [{"title","suggested_state","rationale","children":[…]}]}`. This **replaces
  the silent drop** at `create.py:1958`: a branch with no namable live scenario is emitted as a
  `defer`-suggested node the operator *sees*, not dropped in prose. Concepts + defer suggestions are
  **evidence-only** (like risks/scope/deferrals at `create.py:288-291`), never derive-from-intent —
  the prompt forbids inventing concepts absent from the seed/code.
- **detail:** `render_detail_prompt` → `prompts/detail.md` gets a parallel JSON block — whatever the
  body would route to `## Deferred` (including the foundational-logic route at `detail.py:378-406`)
  is *also* emitted as a candidate-deferral node scoped to that step.

### C. The interactive tree navigator (in the leaf, reused by all three surfaces)

`navigate_concepts(tree, *, prompt_fn: InputFn, yes: bool, save_fn: Callable[[ConceptTree], None]) ->
ConceptDecision` (frozen result, mirroring `ScopeOutResult` / `EscalateResult`). The `save_fn` seam is
what lets the walk persist mid-loop (below) while keeping the leaf pure — the caller injects a closure
bound to `concepts_path(plan_path)` (leaf's own `save`), so the navigator writes through the caller's
persistence without importing a path resolver. Lives in the leaf so `create`, `detail`, and the command
reuse it with **zero import cycle** — it reimplements the ~10-line choice/int-list/y-n logic locally
(the accepted leaf-status duplication, as `scope_out.py`'s confirm helper does) rather than importing
`_ask*` from `create.py`.

Loop shape: a **level stack for indeterminate depth**, generalizing the `_SPLIT` sentinel
(`create.py:3430`, today "drill-in vs leaf-select") into a `_DRILL` action. Each frame renders the
current parent's children numbered with `[x]` include / `[ ]` defer / `[-]` mixed-descendants
markers and the rationale beside each (the "hint beside an action" idiom of `_granularity_split_hints`
+ `_ask_change_type`). Keystrokes: comma-separated numbers toggle include/defer (reuse `_ask_int_list`
semantics); `d N` drills into node N (push frame); `u` / Enter pops up; `a` accepts this level as
suggested; `c` confirms & signs off (`signed_off=True`, stamp `signed_off_at`).

Gating `yes → non-TTY → interactive`: under `yes` or non-TTY, accept the suggested states as the
safe default but **leave `signed_off=False`** (there is no operator, and this is *operator* sign-off);
only the interactive `c` path sets `signed_off=True`.

**Persist on each selection — no all-or-nothing at the end.** The walk is *indeterminate-depth* and
can be long, so the navigator calls the injected `save_fn` **after every state change** (each toggle /
level `a`ccept), not once at a terminal `c`. An interrupt (SIGINT, crash, closed TTY) therefore never
loses a deep sign-off session: the persisted tree already carries every decision made so far, and
re-entering `navigate_concepts` (via re-run or resume) **seeds from that saved state and continues** the
walk rather than restarting it. Only the sign-off stamp is terminal: `c` sets `signed_off=True` +
`signed_off_at`; a mid-walk save leaves `signed_off=False` on not-yet-confirmed nodes (consistent with
the auto-mode rule — an unconfirmed decision is a state, never a sign-off). Because both the incremental
and the terminal writes go through the one injected `save_fn`, there is a single writer, not two.

### D. Wiring the gate

- **create:** run as a third decision gate in `create_plan`, immediately after `_review_step_gates`
  (~`create.py:5651`), under the same `yes` / resume / checkpoint discipline as
  `_review_step_change_types`. Persist `concepts.json`; feed the `defer` / `wont_do` subtree into the
  `## Deferred` / `## Out of scope` synthesis (replacing evidence-only re-derivation) and set
  `scope=deferred` + `status_note` on any mapped step.
- **detail single step:** run `navigate_concepts` inline over the small per-step tree, then persist + route.
- **detail batch / `--all`:** during the serial loop (`detail.py:2627`) **accumulate** each step's
  candidate concepts into a union tree — **do not prompt per step**. After the loop completes, run
  **one consolidated `navigate_concepts`** over the union tree (the single end-of-process sign-off),
  then persist + route. The `jobs > 1` concurrent path collects concepts in workers and runs the one
  consolidated gate serially after join (consistent with detail's serial-mutation invariant at
  `detail.py:1993-1998` — cross-step / shared-state writes belong in the post-join serial tail).

**A hard rule for the parallel `completeness-apply` path — never mutate `concepts.json` inside a
worker.** `completeness-apply --jobs N` runs each `apply_finding` in an isolated git worktree and
writes results back through a serial replay tail whose captured change-set is a **closed, frontmatter-
derived set** — the plan `.md` plus each step's `detail:` file, and nothing else (`launcher.py:2852-2863`,
`completeness_apply_parallel.py:87-102`). A sidecar like `concepts.json` is untracked, so a worker's
write to it is **never captured, never replayed, and is destroyed on worktree teardown** — silently
lost. Therefore any concept-tree mutation (a `scope_out` `include → defer` flip, a coverage-driven
`covered_by` stamp) must run **only in a serial context**: the interactive walks, `scope_out_step`, and
completeness's **serial** apply tail — never the plan-mutation-free parallel worker. (The structural
remedies already dispatch serial-walk-only, so this is a guardrail, not a redesign.) Documented as a
Risk below with a regression test.

### E. Closing the root-cause gap — guaranteed coverage

Two deterministic checks added to the completeness audit, emitted as ordinary `Recommendation`s:

1. **`concept-coverage` (high, blocking; **not** auto-appliable):** a `state=include`, `signed_off=True`
   concept **not covered by any committed step** → a finding that fails the audit under
   `--fail-on-findings` and re-surfaces every audit until covered or explicitly re-deferred (with
   sign-off) via `scope-review`. Its only two resolutions — author a covering step, or re-defer via
   `scope-review` — are both **operator actions**; `completeness-apply` has no auto-mutation for it (MVP
   never auto-mints a step), so it is a **blocking-but-recommend-only** finding, *not* apply-eligible.
   This makes the silent drop impossible — the exact failure the operator hit. Coverage matching is
   **recomputed every audit** (never a pinned id): explicit `covered_by` **step-title-slug** links
   **plus** a heuristic title/feature cross-reference against step titles, `features` (`schema.py:87`),
   and detail bodies. Title-slug-keying is what lets coverage survive the structural remedies'
   renumbering (§H) *and* work on a step that has no detail file yet.
2. **`concept-unsigned-deferral` (advisory/info):** a `defer` / `wont_do` concept with
   `signed_off=False` (Claude-decided under `--yes`, never gated) → surfaced so an operator
   eventually signs off. Names the original gap directly.

Both partition through `partition_findings_for_triage` (`convergence.py`): the coverage finding is
**blocking but recommend-only** (surfaced and gate-failing, never auto-applied); the unsigned-deferral
is triage-deferred advisory. Neither flips the exit code unless `--fail-on-findings` (per the exit-code
convention).

**Not gated on the detail bundle — concepts live at step altitude.** Unlike completeness's *detail-
level* actions (which the `is_bare` / detail-bundle gate restricts to structure-only until a full
detail bundle exists — "a completeness action can only target what exists"), the concept tree and its
two checks key on **plan + steps + evidence**, which a bare plan already has. So the concept checks run
on a **bare, detail-less plan** (steps but no `NN-*.md` files) exactly as on a detailed one — a plan
freshly out of `create` is a fully supported target. This is deliberate: the deferral decision the
feature gates happens at `create`/decomposition time, *before* detail, so gating it behind detail
presence would reintroduce the blind spot. The one thing detail adds is a *richer* coverage-match
corpus (detail bodies); its absence just means the heuristic matches against titles + `features` only.

### F. The standalone `scope-review` command

New `plan_tool/cli/scope_review_cmd.py`, cloned from `scope_out_cmd.py` (imports `cli.context`,
`cli.parser`, and the `concept_tree` leaf — never `cli.app`). Watch the one-keystroke collision with
the existing **`scope-out`** command: they are different verbs (out = carve a step to a seed; review =
sign off the concept tree) — the help text and `--help` summary must disambiguate them explicitly.

**Behavior: inherently mutating, create-if-missing.** Loads `concepts.json` and presents **all**
concepts select/deselect at every level via `navigate_concepts`, re-runnably. If **no tree exists yet**,
`scope-review` **derives and creates one** (one concept-emit round-trip → all nodes `signed_off=False`)
rather than erroring, then presents it — you can run it on any plan at any time, including a bare plan
straight out of `create` with **no detail files** (the emit derives from plan + steps + evidence; §E).
Unlike `scope-out`, `scope-review` has **no recommend-only mode and no `--apply` gate**: the interactive
walk *is* the edit, and every state change persists immediately via the navigator's `save_fn` (§C). So
the command is **unconditionally mutating** (hence its unconditional place in `_LOCKED_MUTATING_COMMANDS`
— the mutation lock does not hinge on a flag). Always exits 0 (non-zero only on failure-to-complete).
**Claude cost:** the emit runs only when a tree must be *derived* — first-run create-if-missing, or
`--rederive` on an existing tree to catch code drift (append new nodes, preserve existing states, flag
conflicts). Presenting/editing an already-derived tree spends **no Claude**. Re-running seeds the
navigator with each node's current `state` + `signed_off` — prior decisions are the starting point, not
reset; confirming re-stamps `signed_off_at`.

**Registration / drift-guard checklist** (each is test-enforced — omit one and the suite goes red):

1. `COMMAND_MODULES` tuple + module/handler import in `cli/app.py` (`:381`, `:169-290`).
2. `cmd_scope_review` in `cli/__init__.py` `__all__` (`:105`) — `test_package_surface.py:288`.
3. `_LOCKED_MUTATING_COMMANDS` frozenset (`cli/app.py:404`) — `scope-review` mutates unconditionally
   (no `--apply` gate; the walk itself persists), so it needs no `_requires_repo_mutation_lock`
   carve-out.
4. `CANONICAL_COMMAND_ORDER` (`cli/parser.py:39`) for `--help` order; re-seed the golden help
   snapshot (`UPDATE_CLI_GOLDEN=1` → `tests/cli/package_surface_help.golden.txt`,
   `test_package_surface.py:182`).
5. **`CAPABILITIES.md`** — list `scope-review` in a capability's `surfaces:` mapped to a valid
   MISSION principle id, or `test_capability_catalog.py:267` + `test_split_criteria.py:858` fail with
   an `orphan-subcommand` finding. (`plan-tool validate`'s catalog check is advisory-only and does
   **not** flip rc, but the two tests hard-assert `check_capabilities() == []`.)
6. **Generated CLI reference** — `python -m plan_tool.cli_reference --write` to emit
   `docs/cli/scope-review.md` + refresh the index, or the four `tests/cli/test_cli_reference.py`
   drift tests fail (the `--rederive` flag lands in the generated Options table).

### G. Existing plans — passive checks stay inert; only explicit derivation creates a tree

The split that keeps pre-existing plans quiet is **who derives**: the passive completeness checks
**never** derive a tree, so they stay inert on any plan with no `concepts.json`; only an **explicit,
operator-invoked** derivation (`create`'s gate, `detail`, or `scope-review`) creates one. This gives
adoption without dumping a finding flood or surprise Claude spend on every old plan:

- Both completeness checks (§E) **no-op** when the sidecar is absent — they key on a loaded tree, so a
  treeless plan yields no findings and spends no Claude. This matches branch-awareness's "inert unless
  enabled". Completeness **never auto-derives** a tree — it only ever reads one.
- `scope-review` is the create-if-missing bootstrap (§F): run on a treeless plan it **derives** one
  (one emit pass, all nodes `signed_off=False`) and presents it — the deliberate, explicit adoption
  entry point. Because the derived nodes are all `signed_off=False`, the follow-up audit stays quiet on
  `concept-coverage` (which needs `signed_off=True`) and surfaces only advisory `concept-unsigned-
  deferral` — no blocking flood. Cold-start never fabricates operator sign-off (the §C auto-mode rule).

Cold-start derivation seeds from current evidence: each `## Out of scope` bullet → a `wont_do` node,
each `## Deferred` bullet → a `defer` node, each committed step → an `include` node (`covered_by` that
step's title slug). On a plan that **already** has a tree, `--rederive` re-runs the emit to catch code
drift with append-new + preserve-existing + flag-conflicts semantics (the 3-way-merge refinement is
deferred — see Deferred). So the emit fires on exactly two occasions: first-run create-if-missing, and
`--rederive` drift-catch; every other `scope-review` invocation is pure re-navigation, no Claude.

### H. Structural-remedy integration — coverage survives split / merge / scope-out / re-ground

The audit converts findings into the four structural remedies (`escalate_to_split` / `plan-tool split`,
`scope_out_step`, `merge_bridge`, `reground_bridge`), and **every one of them renumbers step ids** — the
scope-out `old_to_new` remap (`scope_out.py:480`), the split "renumber every step from the target onward"
(`detail.py:3710`), the merge/re-ground collapse. A `covered_by: list[int]` of raw step ids is
`depends_on`-shaped and would go **stale on the first remedy** — and worse, produce a non-converging spin
(scope-out carves a covering step → its concept goes uncovered → next audit re-raises the blocking
`concept-coverage` finding → the convergence diagnostic reads it as spinning). Two rules close this:

- **Coverage is slug-keyed and recomputed each audit, not a pinned id.** `covered_by` records the owning
  step's **title slug** (`derive_step_slug(step.title)`, `detail.py:281`) — renumber-stable (a split /
  merge / scope-out rewrites only the `NN-` filename prefix, never the title) and present even on a step
  with no detail file. (Do **not** key on the detail-*filename* slug `_detail_slug_key`, `detail.py:3956`,
  which needs an on-disk `NN-*.md` and so is absent on a bare plan.) §E's coverage match is **recomputed**
  against current steps every audit rather than trusting a stored id, so renumbering cannot corrupt
  coverage — there is no id to remap. This is the primary mechanism; it makes three of the four remedies
  integrate for free:
  - **re-split** (1 step → 2): both children conservatively inherit the covering slug, so coverage stays
    satisfied (audit quiet) until an operator narrows it.
  - **merge** (2 → 1): the union of the two steps' concepts maps to the merged step's slug.
  - **re-ground** (mark steps done): concepts now covered by DONE steps — coverage already satisfied.
- **scope-out is the one remedy with a semantic transition.** Carving a step to a forward-seed *is* a
  deferral, so `scope_out_step` (both entry points — `plan-tool scope-out --apply` and
  `convergence … --apply-scope-out`) must, in the same transaction, flip any concept covered only by the
  carved step **`include → defer`** and **carry that concept into the rendered forward-seed** (a `## Deferred`
  bullet in `render_carved_seed`). Without this the carve would instantly re-raise a blocking coverage
  finding on the concept it just legitimately deferred. The transition **preserves `signed_off`** — an
  operator-signed carve stays signed; an unattended one stays `signed_off=False` (surfacing later as
  `concept-unsigned-deferral`, per §C's auto-mode rule).

Because coverage is recomputed (not pinned), the concept sidecar does **not** need to be a write-party to
`apply_narrow` / the split executor / `merge_bridge`'s renumber transaction — among the four structural-
remedy actuators, **only `scope_out_step`** writes `concepts.json` (the `include → defer` flip). (Other
surfaces write it too — the create/detail gates, the navigator's incremental saves, cold-start
derivation — but none of the other three *renumber* actuators do.) Keep the remap burden off split /
merge / re-ground.

## Out of scope

- Auto-minting steps from included concepts — MVP records a coverage obligation only (§E), never
  fabricates a step from a bare title (evidence-only principle).
- A real 3-way merge of a `--rederive`d tree against prior decisions — MVP appends new nodes,
  preserves existing states, flags conflicts (or defers `--rederive` entirely to a follow-up).
- Concept-decision telemetry — a natural `kind="concept-signoff"` `DecisionEvent` later.
- Jira export of deferred concepts.
- Any change to the `Step` / `Plan` frontmatter schema — the tree lives entirely in the sidecar.

## Risks

- **Import cycle** if the navigator reaches into `create.py` — mitigated by the leaf module + injected
  `prompt_fn` (the navigator imports nothing first-party above `schema`).
- **Concept over-generation** bloating prompts/UX — bound depth/breadth in the emit prompt and run it
  through `prompt_budget`.
- **Coverage-match false positives** creating audit noise — explicit `covered_by` links are exact;
  the heuristic match starts conservative; the finding is blocking-under-`--fail-on-findings` but not
  exit-flipping by default.
- **Sidecar drift** vs plan edits — `plan_fingerprint` guard + stale→re-derive prompt.
- **Two sources of truth** (prose `## Deferred` vs tree) — resolved by making prose a one-directional
  render of the tree.
- **Silent sidecar-write loss in parallel `completeness-apply`** — a `concepts.json` mutation inside a
  `--jobs N` worker worktree is untracked by the replay tail and destroyed on teardown
  (`completeness_apply_parallel.py:87-102`). Mitigated by the §D hard rule: concept-tree writes run only
  in serial contexts, plus a regression test asserting a parallel apply never mutates `concepts.json`.
- **`scope-review` / `scope-out` conflation** — one keystroke apart, similar shape. Mitigated by
  distinct help text and a `--help` summary that states the difference.

## Testing

- **Navigator unit tests** (`tests/test_concept_tree.py`): `_queue_input`-scripted `prompt_fn` driving
  toggle / `d N` drill-in (3+ levels, for indeterminate depth) / `u` up / `c` confirm; assert returned
  `ConceptDecision` states + `signed_off` / `signed_off_at`.
- **Gating matrix:** `monkeypatch.setattr("sys.stdin.isatty", …)` × `yes` True/False → assert
  suggested-accept states, and `signed_off` False on `yes` / non-TTY, True only on interactive `c`.
- **create wiring:** fake invoker returns concept JSON; scripted navigator input; assert `concepts.json`
  written, `## Deferred` / `## Out of scope` rendered from the deferred subtree, `scope:deferred` set
  on mapped steps.
- **detail batch:** multi-step fake; assert **exactly one** consolidation prompt at end (count
  `prompt_fn` invocations), not per-step; routing applied once.
- **scope-review command:** dispatch via `build_parser`; load persisted tree; scripted flips; assert
  each flip **persists immediately** (no `--apply` gate — the command is unconditionally mutating) and
  that prior decisions seed the navigator on re-run.
- **coverage audit:** signed-off included uncovered node → `concept-coverage` finding; unsigned
  deferral → `concept-unsigned-deferral`.
- **treeless inert + create-if-missing:** a plan with no `concepts.json` → completeness audit emits
  neither concept finding and spends no Claude (completeness never derives); `scope-review` on the same
  plan (fake invoker) **derives a fresh tree** from `## Out of scope` / `## Deferred` / committed steps
  with every node `signed_off=False`, then presents it.
- **bare plan, no detail files:** a plan with steps but zero `NN-*.md` detail files → `scope-review`
  derives + presents a tree, and the completeness concept checks run (keyed on steps, not detail).
- **incremental persistence / resume (§C):** scripted walk that toggles a few nodes then raises mid-walk
  (simulated interrupt) → assert `concepts.json` on disk already carries those toggles with
  `signed_off=False`; re-enter `navigate_concepts` → assert it seeds from the saved state, not a reset.
- **parallel-apply no-loss (§D):** drive `completeness-apply --jobs N` over a finding set and assert no
  worker path mutates `concepts.json` (concept writes are serial-only) — guards against the silent
  worktree-teardown loss.
- **invoker seam (§B):** assert the concept-emit is reached only via the injected `invoker`, and that
  the conftest real-backend gate raises if the seam is left defaulting to the real CLI.
- **command drift-guards (§F):** `check_capabilities(repo_root) == []` (capability registered),
  `docs/cli/scope-review.md` present + index-linked, golden `--help` matches, and dispatch/registration
  surface tests green.
- **structural-remedy coverage survival** (§H): apply a `split` / `merge` / `re-ground` that renumbers a
  covering step → assert the concept stays covered (no `concept-coverage` finding); apply a `scope-out`
  of a covering step → assert the concept flips `include → defer`, appears in the carved seed's
  `## Deferred`, retains its prior `signed_off`, and raises no coverage finding.
- **data-contract drift:** `tests/test_data_contract.py` green with the registered contract + new
  `DATA_CONTRACT.md` section.

## Acceptance criteria

- `plan-tool create --from-existing … --iterate` emits a candidate concept tree, and on an interactive
  TTY runs a drill-down sign-off gate before the plan is finalized; a `plan-details/<slug>/concepts.json`
  sidecar is written with per-node `state` / `signed_off` / `signed_off_at`.
- The former silent drop at `create.py:1958` no longer drops a branch in prose — it surfaces it as a
  `defer`-suggested concept node the operator can flip to `include`.
- A full/batch `plan-tool detail` run prompts for sign-off **exactly once, at the end** of the run
  (verified by counting `prompt_fn` calls in a multi-step test), never per step.
- `plan-tool scope-review <name>` presents the full tree with select/deselect at every level, is
  re-runnable, seeds from prior decisions, and exits 0 for every outcome. It is **unconditionally
  mutating** — no recommend-only mode and no `--apply` gate; every flip persists immediately (§C). On a
  **treeless** plan it **derives one (create-if-missing)** rather than erroring; on a plan that
  **already has a tree** it spends **no Claude** (pure re-navigation) — the emit fires only on
  create-if-missing or `--rederive`.
- `plan-tool scope-review <name>` runs on a **bare plan with no detail files** (steps only), deriving
  and signing off a concept tree before any `detail` exists.
- Under `--yes` / non-TTY, suggested states are accepted but every deferral stays `signed_off=false`.
- A `state=include`, `signed_off=true` concept with no owning committed step raises a blocking
  `concept-coverage` completeness finding that re-surfaces until covered or re-deferred, and flips the
  rc under `--fail-on-findings`.
- The `## Out of scope` / `## Deferred` plan sections are rendered from the tree's `wont_do` / `defer`
  subtrees, not independently synthesized.
- Concept coverage **survives every structural remedy** (§H): a split / merge / re-ground that renumbers
  steps leaves a covered concept still covered (no spurious `concept-coverage` finding), and a
  `scope-out` of a covering step flips its concept `include → defer` and writes it into the carved
  forward-seed **in the same transaction** (no re-raised blocking finding on the just-deferred concept),
  preserving `signed_off`.
- `tests/test_data_contract.py` passes with `ConceptTree` / `ConceptNode` registered and documented in
  `DATA_CONTRACT.md`.
- A plan with no `concepts.json` **audits inert** — completeness never auto-derives a tree, so it emits
  no `concept-coverage` / `concept-unsigned-deferral` findings and spends no Claude. Only an explicit
  `create` gate / `detail` / `scope-review` invocation derives one (cold-start nodes all
  `signed_off=false`, so the follow-up audit surfaces at most advisory unsigned-deferrals, never a
  blocking-coverage flood).
- A concept-tree mutation is **never lost to the parallel apply path**: a regression test drives
  `completeness-apply --jobs N` and asserts no worker mutates `concepts.json` (writes are serial-only).
- The new `scope-review` command keeps the suite green across every drift-guard: capability catalog,
  generated `docs/cli/` reference, golden `--help`, and the `ConceptTree`/`ConceptNode` data contract
  (§F checklist).
- The concept-emit round-trip runs through an injected `invoker=` seam (no bare subprocess) and is
  covered by the conftest real-backend gate + TESTING.md neutralization table.
- The interactive navigator **persists on each selection**: an interrupt mid-walk loses no prior
  decision, and re-entry resumes from the saved tree rather than restarting.
- The final step updates `BACKLOG.md` to reconcile #121.

## Deferred

- `--rederive` 3-way merge semantics **on a plan that already has a tree** (MVP: append + preserve +
  flag; cold-start on a *treeless* plan is in scope — §G).
- **Reconcile → stale-tree linkage (flag-only).** The concept tree is code-evidence-derived, so it can
  go stale exactly when grounding does. A future `reconcile-plan --refresh` / `reconcile-code` could
  reuse the existing `plan_fingerprint` / `code_fingerprint` drift signal to **flag** (never mutate) a
  stale tree, hinting `scope-review --rederive`. MVP leaves `--rederive` an explicit manual step; the
  `plan_fingerprint` guard (§A) already marks a stale tree "re-derive" on read.
- Concept-decision telemetry event.
- Auto-minting steps from included concepts.
