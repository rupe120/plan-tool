---
title: Deferred Concept Signoff Gate
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: 'Add the concept-tree sidecar leaf: ConceptNode/ConceptTree dataclasses,
    concepts_path, save/load, and its data contract'
  files:
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  creates:
  - plan_tool/concept_tree.py
  - tests/test_concept_tree.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/01-concept-tree-sidecar-leaf-conceptnode.md
  status: current
- id: 2
  title: Add the concept-emit round-trip producer and its prompt behind an injected
    invoker= seam
  files:
  - plan_tool/concept_tree.py
  - tests/test_concept_tree.py
  - TESTING.md
  creates:
  - plan_tool/prompts/concept-emit.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/02-concept-emit-round-trip-producer-its.md
- id: 3
  title: Add the interactive navigate_concepts walker with drill-down level stack
    and per-selection persistence
  files:
  - plan_tool/concept_tree.py
  - tests/test_concept_tree.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/03-interactive-navigate-concepts-walker.md
- id: 4
  title: Wire the concept sign-off gate into create and render Out-of-scope/Deferred
    from the tree
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/04-wire-concept-sign-off-gate-create.md
- id: 5
  title: 'Wire concepts into detail: pre-authoring scope sign-off and one consolidated
    candidate-deferral sign-off after authoring'
  files:
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/05-wire-concepts-detail-inline-sign-off.md
- id: 6
  title: Add the two completeness concept checks (concept-coverage blocking, concept-unsigned-deferral
    advisory) with slug-recomputed coverage, plus a parallel-apply no-loss regression
    test
  files:
  - plan_tool/completeness_report.py
  - plan_tool/review.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_apply_parallel.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/06-two-completeness-concept-checks-concept.md
- id: 7
  title: Make scope_out_step flip a carved step's concepts include→defer and carry
    them into the rendered forward-seed with an all-or-recoverable transaction
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/07-make-scope-out-step-flip-carved-step.md
- id: 8
  title: Add the standalone scope-review command (create-if-missing, unconditionally
    mutating) and register it across every drift-guard surface
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/__init__.py
  - plan_tool/cli/parser.py
  - CAPABILITIES.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  creates:
  - plan_tool/cli/scope_review_cmd.py
  - tests/cli/test_scope_review_cmd.py
  - docs/cli/scope-review.md
  allowed_mentions:
  - plan_tool/cli/scope_out_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/08-standalone-scope-review-command-create.md
- id: 9
  title: 'Reconcile the docs and BACKLOG #121: register the new leaf in CLAUDE.md,
    add the RUNBOOK walkthrough, and close #121'
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  - 5
  - 6
  - 7
  - 8
  detail: docs/implementation-plans/plan-details/deferred-concept-signoff-gate/09-reconcile-docs-backlog-121-register-new.md
---
# Deferred Concept Signoff Gate

## Overview

Turn the deferral decision — today made silently by Claude in three places — into an explicit, operator-gated, machine-recorded choice over a **hierarchical concept tree**. The operator starts at high-level concepts and drills into an indeterminate depth of sub-concepts, selecting at every level which aspects are **included** vs **deferred** vs **won't-do**. The tree is persisted as a single VCS-tracked JSON sidecar (`plan-details/<slug>/concepts.json`), signed off by the operator, and enforced by a completeness coverage audit so an included concept can never be silently dropped.

Three surfaces consume one shared navigator: `create` (a sign-off gate beside the existing change-type / gate review gates), `detail` (inline for a single step; **one consolidated sign-off at the end** of a full/batch run), and a standalone re-runnable `plan-tool scope-review <name>` command. This is a new operator sign-off gate over the concepts a plan defers, **not** a new planning stage — it does not auto-mint steps, redesign the step model, or replace the `## Out of scope` / `## Deferred` prose (which becomes a one-directional *render* of the tree). Source: BACKLOG #121.

## Problem statement

An operator missed a critical aspect of a complex plan because the tool marked it deferred when it should have been included, with **no point at which the operator signed off** on that deferral. Deferral is decided by Claude in three ungated places:

- Evidence-only `## Out of scope` / `## Deferred` synthesis (`create.py:282-295`).
- The "a branch with no namable live scenario is NOT a step — defer it" decomposition instruction (`create.py:1958`).
- `## Deferred` routing when detail generation can't absorb a shared-location find (`detail.py:378-406`).

The schema only records deferral at **step** granularity (`StepScope`, `schema.py:26-38`). A concept Claude drops *before* it becomes a step leaves no structured trace beyond a prose bullet — and neither existing interactive gate in `create` (change-type, `create.py:3905`; step gates, `create.py:4238`/`:5651`) ever asks about concept scope. There is no confirmation flag anywhere that an operator reviewed a given deferral.

This aligns with MISSION.md's "the structured artifact is the machine contract; the prose is for the human" — the fix makes the concept tree the machine contract and demotes the `## Out of scope` / `## Deferred` prose to a render of it.

## Architecture

### A. The concept-tree sidecar (`plan_tool/concept_tree.py`, NEW leaf)

A stdlib-only leaf (dataclasses + save/load + the navigator; no CLI, no Claude imports) modeled on `review_persistence.py`. Persisted as a **single, VCS-tracked, versioned JSON sidecar** `plan-details/<slug>/concepts.json`, beside `grounding.json`. Add `CONCEPTS_SCHEMA_VERSION = 1`.

Node shape is a **flat list + `parent_id`** (not nested — easier to fingerprint/diff/drift-guard, like the manifest and telemetry): `id` (stable content hash of title + parent path, the annotations/coverage key), `path` (materialized dotted path, e.g. `auth.mfa.totp`), `title`, `depth` (int, 0 = top), `parent_id` (str | None), `order` (int sibling order), `state` (`include` | `defer` | `wont_do` — its own vocabulary, sharing only the keep/defer/reject axis with `StepScope`, not its value strings `committed` / `deferred` / `wont_do`), `rationale` (one-line **evidence-only** note), `source` (`create` | `detail` | `manual`), `signed_off` (bool), `signed_off_at` (ISO-8601 UTC | None), and `covered_by` (`list[str]`, **reserved/advisory, default empty** — coverage is recomputed heuristically by slug every audit and never reads this field, so no step populates it).

Top-level `ConceptTree`: `plan_slug`, `schema_version`, `updated_at`, `plan_fingerprint` (via `compute_plan_fingerprint`), `nodes`. Reads distinguish an absent sidecar from an invalid persisted tree: absence is the treeless state, while unreadable, malformed, schema-mismatched, or field-invalid content raises a typed integrity error. **Drift-guarded** like `Grounding`: every read surface compares the stored fingerprint with the current plan fingerprint, reports a stale tree, and must not silently consume its decisions. `create` and `detail` stop the concept gate with an actionable `scope-review --rederive` message; completeness emits a blocking `concept-integrity` finding for an invalid tree, or an advisory `concept-stale` finding for a valid stale tree, and skips coverage/sign-off evaluation in either case; `scope-out` aborts its concept mutation before changing either artifact; and `scope-review` refuses to navigate the stale tree unless the operator supplied `--rederive`. Step 8 owns that flag and the only stale-tree refresh path. Register a `PersistedDataclassContract` for `ConceptTree` / `ConceptNode` in `data_contract.py` with a paired `DATA_CONTRACT.md` section so `tests/test_data_contract.py` guards it.

**Path resolution mirrors `grounding.py`, not `locator.py`.** Add a `concepts_path(plan_path)` helper computing `plan_path.parent / "plan-details" / slug / "concepts.json"` (reusing `locator.slug_from_filename`), exactly as `grounding.py:99-111` does — `locator.py` resolves only plan `.md` paths, never the detail-bundle dir. Because the sidecar lands **inside** `plan-details/<slug>/`, every archive/move/rename path (`create.py:687-710` from-existing, `sweep.py:321-413`, `annotate --archive`, the slug-rename `create.py:788-815`) moves the whole directory and byte-copies non-`.md` files verbatim, so `concepts.json` travels for free. **Known shared limitation:** `_archive_duplicate_plans` (`manifest.py:645-667`) moves only the plan `.md` and strands the bundle — already true for `grounding.json`; not this feature's job to fix.

Relationship to existing scope machinery is **one-directional (tree is source of truth)**: `state=defer` → rendered into `## Deferred`; `state=wont_do` → `## Out of scope` (matching `create.py:260-264`); a deferred concept mapping to an existing step sets that `steps[].scope=deferred` + `status_note`; an included concept with no owning step is the coverage obligation of §E.

**Canonical parent/child state semantics are independent, with no inheritance or cascade.** Every node's persisted `state` is authoritative for that node alone: changing or accepting a parent never changes its descendants, and descendant states never rewrite the parent's state. The navigator's `[-]` marker is display-only, derived when a node's descendants contain more than one state; the uniform descendant markers likewise summarize descendants without replacing the node's own persisted state. Rendering and auditing always evaluate each node independently: every `defer` node renders in `## Deferred`, every `wont_do` node renders in `## Out of scope`, and every signed-off `include` node participates in coverage, regardless of ancestor or descendant state. Thus a deferred parent with an included child renders the parent as deferred while the child remains an included coverage obligation. Sign-off also applies to each node's own current state; mixed subtrees are signable after the existing explicit frame-review rule and require no normalization.

### B. Producing the tree — evidence-only (`create` and `detail`)

**Invoker seam (required).** The concept-emit round-trip is a new real-backend shell-out, so every function that runs it takes an `invoker=` / `claude_invoker=` kwarg defaulting to the real-CLI shell-out (as `shell_claude_invoker` etc. do), routed through the shared backend / rate-limit-recovery path — never a bare `subprocess`. Add its seam to **TESTING.md's neutralization table** and confirm the conftest autouse gate covers it.

- **create:** one Claude round-trip emits a hierarchical candidate-concept JSON with a *suggested* state + one-line evidence rationale per node — folded into the distill discriminator (`prompts/distill-seed.md`) or a sibling checkpoint. Shape: `{"concepts": [{"title","suggested_state","rationale","children":[…]}]}`. This **replaces the silent drop** at `create.py:1958`: a branch with no namable live scenario is emitted as a `defer`-suggested node the operator *sees*. Concepts + defer suggestions are **evidence-only** (like risks/scope/deferrals at `create.py:288-291`), never derive-from-intent.
- **detail:** `render_detail_prompt` → `prompts/detail.md` gets a parallel JSON block — whatever the body would route to `## Deferred` (including the foundational-logic route at `detail.py:378-406`) is *also* emitted as a candidate-deferral node scoped to that step.

### C. The interactive tree navigator (in the leaf, reused by all three surfaces)

`navigate_concepts(tree, *, prompt_fn: InputFn, yes: bool, save_fn: Callable[[ConceptTree], None]) -> ConceptDecision` (frozen result, mirroring `ScopeOutResult` / `EscalateResult`). The `save_fn` seam lets the walk persist mid-loop while keeping the leaf pure — the caller injects a closure bound to `concepts_path(plan_path)` (leaf's own `save`). Lives in the leaf so `create`, `detail`, and the command reuse it with **zero import cycle** — it reimplements the ~10-line choice/int-list/y-n logic locally rather than importing `_ask*` from `create.py`.

Loop shape: a **level stack for indeterminate depth**, generalizing the `_SPLIT` sentinel (`create.py:3430`) into a `_DRILL` action. Each frame renders the current parent's children numbered with `[x]` include / `[ ]` defer / `[!]` won't-do / `[-]` mixed-descendants markers and the rationale beside each; markers summarize descendant state for navigation but do not alter the node's independent state. Keystrokes: comma-separated numbers cycle only the named nodes `include → defer → wont_do → include` (reuse `_ask_int_list` validation semantics), never their descendants, so every state is operator-selectable at every level and an existing `wont_do` remains `wont_do` until the operator explicitly cycles it; `d N` drills into node N (push frame); `u` / Enter pops up; `a` explicitly accepts this frame's current states without propagation or normalization; `c` confirms & signs off (`signed_off=True`, stamp `signed_off_at`) only after every descendant-bearing frame has been displayed for explicit review or accepted at that frame. Until then, `c` reports the unresolved frames and keeps the walk open, so root confirmation cannot approve unseen descendants.

Gating `yes → non-TTY → interactive`: under `yes` or non-TTY, accept the suggested states as the safe default but **leave `signed_off=False`** (there is no operator, and this is *operator* sign-off); only the interactive `c` path sets `signed_off=True`.

**Persist on each selection — no all-or-nothing at the end.** The navigator calls the injected `save_fn` **after every state change** (each toggle / level `a`ccept), not once at a terminal `c`. Before persisting any changed decision, it invalidates that node's prior approval by setting `signed_off=False` and `signed_off_at=None`; only a subsequent interactive `c` restores the stamp for the affected approval scope. An interrupt (SIGINT, crash, closed TTY) never loses a deep sign-off session: re-entering `navigate_concepts` **seeds from that saved state and continues** rather than restarting. Only the sign-off stamp is terminal: `c` sets `signed_off=True` + `signed_off_at`; a mid-walk save leaves changed decisions unsigned. Both writes go through the one injected `save_fn` — a single writer.

### D. Wiring the gate

- **create:** run as a third decision gate in `create_plan`, immediately after `_review_step_gates` (~`create.py:5651`), under the same `yes` / resume / checkpoint discipline as `_review_step_change_types`. Before the plan markdown exists, persist each navigator change only as unsigned resume state with an unset fingerprint. Feed the `defer` / `wont_do` subtree into the `## Deferred` / `## Out of scope` synthesis, set `scope=deferred` + `status_note` on any mapped step, write the finalized plan, then refresh `concepts.json` with the fingerprint of that written artifact and the completed navigator sign-off.
- **detail, before authoring:** load the persisted tree or, on a treeless run, derive the plan-level scope, then run `navigate_concepts` once over that scope before rendering any per-step prompt. Every serial and concurrent prompt receives the resulting scope decisions.
- **detail, after authoring:** accumulate each step's candidate deferrals into a union tree — **do not prompt per step**. After the loop or concurrent join, deterministically merge that union into the persisted tree, save it, and run **one consolidated `navigate_concepts`** over the merged candidates. This post-authoring walk is inline for a single-step run and consolidated for full/batch.

**A hard rule for the parallel `completeness-apply` path — never mutate `concepts.json` inside a worker.** `completeness-apply --jobs N` runs each `apply_finding` in an isolated git worktree and writes results back through a serial replay tail whose captured change-set is a **closed, frontmatter-derived set** — the plan `.md` plus each step's `detail:` file, nothing else (`launcher.py:2852-2863`, `completeness_apply_parallel.py:87-102`). A sidecar like `concepts.json` is untracked, so a worker's write is **never captured, never replayed, destroyed on worktree teardown** — silently lost. Any concept-tree mutation (a `scope_out` `include → defer` flip) must run **only in a serial context**: the interactive walks, `scope_out_step`, and completeness's **serial** apply tail. Documented as a Risk with a regression test.

### E. Closing the root-cause gap — guaranteed coverage

Two deterministic checks added to the completeness audit, emitted as ordinary `Recommendation`s:

Both checks evaluate each node's own persisted state independently of its ancestors; in particular, an included child beneath a deferred or won't-do parent remains a coverage candidate.

1. **`concept-coverage` (medium/blocking; not auto-appliable):** a `state=include`, `signed_off=True` concept **not covered by any committed step** → a finding that fails the audit under `--fail-on-findings` and re-surfaces every audit until covered or explicitly re-deferred (with sign-off) via `scope-review`. Its only two resolutions — author a covering step, or re-defer via `scope-review` — are both **operator actions**; `completeness-apply` has no auto-mutation for it (MVP never auto-mints a step), so it is **blocking-but-recommend-only**, *not* apply-eligible. Coverage matching is **recomputed every audit** (never a pinned id): a heuristic title/feature cross-reference against step titles, `features` (`schema.py:87`), and detail bodies — coverage is **derived, never read from a persisted `covered_by`** (no step maintains that field).
2. **`concept-unsigned-deferral` (advisory/info):** a `defer` / `wont_do` concept with `signed_off=False` (Claude-decided under `--yes`, never gated) → surfaced so an operator eventually signs off.

Both partition through `partition_findings_for_triage` (`convergence.py`): the coverage finding is blocking but recommend-only; the unsigned-deferral is triage-deferred advisory. Neither flips the exit code unless `--fail-on-findings`.

**Not gated on the detail bundle — concepts live at step altitude.** Unlike completeness's *detail-level* actions (restricted by the `is_bare` / detail-bundle gate to structure-only until a full detail bundle exists), the concept tree and its two checks key on **plan + steps + evidence**, which a bare plan already has. So the concept checks run on a **bare, detail-less plan** exactly as on a detailed one. This is deliberate: the deferral decision happens at `create`/decomposition time, *before* detail. The one thing detail adds is a *richer* coverage-match corpus (detail bodies).

### F. The standalone `scope-review` command

New `plan_tool/cli/scope_review_cmd.py`, cloned from `scope_out_cmd.py` (imports `cli.context`, `cli.parser`, and the `concept_tree` leaf — never `cli.app`). Watch the one-keystroke collision with **`scope-out`**: different verbs (out = carve a step to a seed; review = sign off the concept tree) — help text must disambiguate them explicitly.

**Behavior: inherently mutating, create-if-missing.** Loads `concepts.json` and presents **all** concepts with `include` / `defer` / `wont_do` selection at every level via `navigate_concepts`, re-runnably. If **no tree exists yet**, `scope-review` **derives and creates one** rather than erroring: it first deterministically seeds every existing `## Out of scope` bullet as `wont_do`, every `## Deferred` bullet as `defer`, and every committed step as `include`, all unsigned; one concept-emit round-trip may then enrich that guaranteed seed with hierarchy or additional evidence-backed concepts but must not omit or replace any seeded node. This is runnable on any plan, including a bare plan straight out of `create` with **no detail files**. Step 8 registers and owns `--rederive`: on an existing current tree the command spends no Claude and navigates it; on an existing stale tree without the flag it reports the fingerprint mismatch, writes nothing, and exits non-zero with an instruction to rerun with `--rederive`; with the flag it runs the emit, appends new nodes, preserves existing decisions, flags conflicts for operator review, saves a current fingerprint, and only then navigates the refreshed tree. Unlike `scope-out`, `scope-review` has **no recommend-only mode and no `--apply` gate**: the interactive walk *is* the edit, and every state change persists immediately via `save_fn` (§C). So the command is **unconditionally mutating** (hence its unconditional place in `_LOCKED_MUTATING_COMMANDS`). Always exits 0 after a successfully created or reviewed tree, including a deterministically seeded tree that receives no emit enrichment; refusing a stale tree without `--rederive` exits non-zero. **Claude cost:** the optional enrichment emit runs only on first-run create-if-missing or `--rederive` on an existing tree to catch code drift (append new, preserve existing, flag conflicts).

**Registration / drift-guard checklist** (each test-enforced):
1. `COMMAND_MODULES` tuple + module/handler import in `cli/app.py` (`:381`, `:169-290`).
2. `cmd_scope_review` in `cli/__init__.py` `__all__` (`:105`) — `test_package_surface.py:288`.
3. `_LOCKED_MUTATING_COMMANDS` frozenset (`cli/app.py:404`) — mutates unconditionally, needs no `_requires_repo_mutation_lock` carve-out.
4. `CANONICAL_COMMAND_ORDER` (`cli/parser.py:39`) for `--help` order; re-seed the golden help snapshot (`UPDATE_CLI_GOLDEN=1` → `tests/cli/package_surface_help.golden.txt`, `test_package_surface.py:182`).
5. **`CAPABILITIES.md`** — list `scope-review` in a capability's `surfaces:` mapped to a valid MISSION principle id, or `test_capability_catalog.py:267` + `test_split_criteria.py:858` fail with an `orphan-subcommand` finding.
6. **Generated CLI reference** — `python -m plan_tool.cli_reference --write` to emit `docs/cli/scope-review.md` + refresh the index, or the four `tests/cli/test_cli_reference.py` drift tests fail.

### G. Existing plans — passive checks stay inert; only explicit derivation creates a tree

The split that keeps pre-existing plans quiet is **who derives**: the passive completeness checks **never** derive a tree, so they stay inert on any plan with no `concepts.json`; only an **explicit, operator-invoked** derivation (`create`'s gate, `detail`, or `scope-review`) creates one.

- Both completeness checks (§E) **no-op** when the sidecar is absent — matching branch-awareness's "inert unless enabled". Completeness **never auto-derives** a tree — it only reads one. When the sidecar exists but is invalid, completeness reports one blocking `concept-integrity` finding and skips coverage/sign-off evaluation; when it is valid but its fingerprint is stale, completeness reports one advisory `concept-stale` finding with the `scope-review --rederive` remedy and likewise skips decision evaluation.
- `scope-review` is the create-if-missing bootstrap (§F): on a treeless plan it deterministically seeds every existing scope bullet and committed step as an unsigned node, then allows one emit pass only to enrich that guaranteed seed with hierarchy or additional evidence-backed concepts, and presents the result. Because the derived nodes are all `signed_off=False`, the follow-up audit stays quiet on `concept-coverage` (which needs `signed_off=True`) and surfaces only advisory `concept-unsigned-deferral`.

Cold-start derivation deterministically seeds from current evidence: each `## Out of scope` bullet → a `wont_do` node, each `## Deferred` bullet → a `defer` node, each committed step → an `include` node. Every such item must remain represented; the emit pass may only enrich this guaranteed seed with hierarchy or additional evidence-backed concepts. On a plan that **already** has a tree, `--rederive` re-runs the emit with append-new + preserve-existing + flag-conflicts semantics (the 3-way-merge refinement is deferred). So the emit may fire on exactly two occasions: first-run create-if-missing, and `--rederive` drift-catch.

### H. Structural-remedy integration — coverage survives split / merge / scope-out / re-ground

The audit converts findings into the four structural remedies (`escalate_to_split` / `plan-tool split`, `scope_out_step`, `merge_bridge`, `reground_bridge`), and **every one of them renumbers step ids** — the scope-out `old_to_new` remap (`scope_out.py:480`), the split "renumber every step from the target onward" (`detail.py:3710`), the merge/re-ground collapse. Pinning coverage as a `list[int]` of raw step ids would be `depends_on`-shaped and would go **stale on the first remedy** — and produce a non-converging spin. Two rules close this:

- **Coverage is recomputed each audit from replacement-step identity, not a pinned id.** §E's coverage match runs against the current steps' title slugs (`derive_step_slug(step.title)`, `detail.py:281`) and authoritative `features` ownership. (Do **not** key on the detail-*filename* slug `_detail_slug_key`, `detail.py:3956`.) Structural-remedy executors must preserve that match explicitly: **split** partitions the original step's matching feature ids among the replacement children so every formerly covered concept matches at least one child (and a child may also match through its new title); **merge** assigns the replacement the union of the source steps' feature ids, so it covers the union of their concepts; **re-ground** preserves the step's title and feature ids when changing its grounding/status, or carries their union to any replacement step. After each remedy, coverage is recomputed against those resulting titles/features; no raw step id or `covered_by` link is persisted.
- **scope-out is the one remedy with a semantic transition.** Carving a step to a forward-seed *is* a deferral, so `scope_out_step` (both entry points — `plan-tool scope-out --apply` and `convergence … --apply-scope-out`) must use an **all-or-recoverable multi-artifact commit**: capture the exact pre-operation bytes or absence of the plan, forward-seed, and `concepts.json`; compute and stage the narrowed plan, rendered seed, and concept transition before publishing; then publish the seed, plan narrow, and sidecar in that order. If any publish fails, restore every artifact already published to its captured bytes or delete it if it was absent, and report failure only after rollback completes; if rollback itself fails, raise an actionable recovery error naming the unrestored artifacts while retaining the captured recovery material. On success, coverage is recomputed via the same §E slug heuristic, any concept covered only by the carved step flips **`include → defer`**, and that concept appears in the rendered forward-seed (a `## Deferred` bullet in `render_carved_seed`). The transition **preserves `signed_off`** — an operator-signed carve stays signed; an unattended one stays `signed_off=False`.

Because coverage is recomputed (not pinned), the concept sidecar does **not** need to be a write-party to `apply_narrow` / the split executor / `merge_bridge`'s renumber transaction — among the four structural-remedy actuators, **only `scope_out_step`** writes `concepts.json` (the `include → defer` flip).

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — Official reference for the dataclass decorator, field defaults, and frozen instances used to model ConceptTree/ConceptNode and the frozen ConceptDecision result.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — Primary reference for computing the stable content-hash node id from title + parent path.
- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — Official guide to add_subparsers and argument wiring needed to register the new scope-review command and its flags.
- [concurrent.futures — ThreadPoolExecutor (Python docs)](https://docs.python.org/3/library/concurrent.futures.html) — Reference for the ThreadPoolExecutor fan-out that the parallel completeness-apply path uses, relevant to the serial-only concept-write invariant.
- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — Authoritative git reference for the isolated worktrees the parallel apply path creates, explaining why untracked sidecars like concepts.json are lost on teardown.
- [RFC 3339 — Date and Time on the Internet: Timestamps](https://www.rfc-editor.org/rfc/rfc3339) — Primary spec for the ISO-8601/RFC 3339 UTC format used for signed_off_at and updated_at fields.
- [datetime — Basic date and time types (Python docs)](https://docs.python.org/3/library/datetime.html) — Reference for producing timezone-aware UTC isoformat timestamps for the sign-off stamp.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Auto-minting steps from included concepts — MVP records a coverage obligation only (§E), never fabricates a step from a bare title (evidence-only principle).
- A real 3-way merge of a `--rederive`d tree against prior decisions — step 8's MVP refresh appends new nodes, preserves existing states, and flags conflicts.
- Concept-decision telemetry — a natural `kind="concept-signoff"` `DecisionEvent` later.
- Jira export of deferred concepts.
- Any change to the `Step` / `Plan` frontmatter schema — the tree lives entirely in the sidecar.

## Risks

- **Import cycle** if the navigator reaches into `create.py` — mitigated by the leaf module + injected `prompt_fn` (the navigator imports nothing first-party above `schema`).
- **Concept over-generation** bloating prompts/UX — bound depth/breadth in the emit prompt and run it through `prompt_budget`.
- **Coverage-match false positives** creating audit noise — the heuristic match starts conservative; the finding is blocking-under-`--fail-on-findings` but not exit-flipping by default.
- **Sidecar drift** vs plan edits — `plan_fingerprint` guard + stale→re-derive prompt.
- **Two sources of truth** (prose `## Deferred` vs tree) — resolved by making prose a one-directional render of the tree.
- **Silent sidecar-write loss in parallel `completeness-apply`** — a `concepts.json` mutation inside a `--jobs N` worker worktree is untracked by the replay tail and destroyed on teardown (`completeness_apply_parallel.py:87-102`). Mitigated by the §D hard rule: concept-tree writes run only in serial contexts, plus a regression test asserting a parallel apply never mutates `concepts.json`.
- **Partial scope-out commit** across the plan, forward-seed, and `concepts.json` — mitigated by §H's pre-image rollback protocol and failure-injection tests at every publish boundary.
- **`scope-review` / `scope-out` conflation** — one keystroke apart, similar shape. Mitigated by distinct help text and a `--help` summary that states the difference.

## Testing

- **Navigator unit tests** (`tests/test_concept_tree.py`): `_queue_input`-scripted `prompt_fn` driving toggle / `d N` drill-in (3+ levels, for indeterminate depth) / `u` up / `a` frame acceptance / `c` confirm; assert root `c` remains blocked while any descendant-bearing frame is unseen or unaccepted, then assert returned `ConceptDecision` states + `signed_off` / `signed_off_at` after every such frame is reviewed or accepted.
- **Parent/child state semantics:** toggle or accept a parent and assert descendants remain unchanged; assert a mixed marker is display-only; for a deferred parent with an included child, render only the parent into `## Deferred`, retain the child's included coverage obligation, and allow sign-off after both frames satisfy the review rule.
- **Gating matrix:** `monkeypatch.setattr("sys.stdin.isatty", …)` × `yes` True/False → assert suggested-accept states, and `signed_off` False on `yes` / non-TTY, True only on interactive `c`.
- **create wiring:** fake invoker returns concept JSON; scripted navigator input; assert incremental sidecar saves are unsigned with an unset fingerprint, the finalized `concepts.json` fingerprints the written plan, `## Deferred` / `## Out of scope` are rendered from the deferred subtree, and `scope:deferred` is set on mapped steps.
- **detail batch:** on a treeless run, assert plan-level scope is derived and navigated before any prompt is rendered; then emit fresh candidate deferrals from every result and assert deterministic union with **exactly one** consolidated post-authoring prompt, not one per step.
- **scope-review command:** dispatch via `build_parser`; load persisted tree; scripted flips; assert each flip **persists immediately** (no `--apply` gate — the command is unconditionally mutating) and that prior decisions seed the navigator on re-run.
- **coverage audit:** signed-off included uncovered node → `concept-coverage` finding; unsigned deferral → `concept-unsigned-deferral`; present invalid sidecar → blocking `concept-integrity` finding.
- **treeless inert + create-if-missing:** a plan with no `concepts.json` → completeness audit emits neither concept finding and spends no Claude (completeness never derives); `scope-review` on the same plan deterministically seeds **every** `## Out of scope` / `## Deferred` bullet and committed step with `signed_off=False`, merges any hierarchy or additional evidence-backed concepts from a fake invoker without dropping seeded nodes, then presents it.
- **bare plan, no detail files:** a plan with steps but zero `NN-*.md` detail files → `scope-review` derives + presents a tree, and the completeness concept checks run (keyed on steps, not detail).
- **incremental persistence / resume (§C):** scripted walk that toggles a few nodes, including a previously signed node, then raises mid-walk (simulated interrupt) → assert `concepts.json` on disk already carries those toggles with `signed_off=False` and `signed_off_at=None`; re-enter `navigate_concepts` → assert it seeds from the saved state, not a reset, and only a subsequent interactive confirmation restores the stamp.
- **parallel-apply no-loss (§D):** drive `completeness-apply --jobs N` over a finding set and assert no worker path mutates `concepts.json` (concept writes are serial-only) — guards against the silent worktree-teardown loss.
- **invoker seam (§B):** assert the concept-emit is reached only via the injected `invoker`, and that the conftest real-backend gate raises if the seam is left defaulting to the real CLI.
- **command drift-guards (§F):** `check_capabilities(repo_root) == []` (capability registered), `docs/cli/scope-review.md` present + index-linked, golden `--help` matches, and dispatch/registration surface tests green.
- **structural-remedy coverage survival** (§H): apply a `split` and assert matching feature ownership is partitioned so every formerly covered concept matches a child; apply a `merge` and assert the replacement unions source feature ownership and covers their concept union; apply a `re-ground` and assert its resulting step preserves the covering title/features; in each case assert no `concept-coverage` finding. Apply a `scope-out` of a covering step and assert the concept flips `include → defer`, appears in the carved seed's `## Deferred`, retains its prior `signed_off`, and raises no coverage finding. Inject a failure after each scope-out publish boundary and assert the plan, seed, and sidecar all return byte-for-byte to their pre-operation state (including restoring absence); inject rollback failure and assert the recovery error names the unrestored artifact and preserves recovery material.
- **data-contract drift:** `tests/test_data_contract.py` green with the registered contract + new `DATA_CONTRACT.md` section.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool create --from-existing … --iterate` emits a candidate concept tree and, on an interactive TTY, runs a drill-down sign-off gate before the plan is finalized; incremental sidecar saves remain unsigned resume state with an unset fingerprint, then `plan-details/<slug>/concepts.json` is refreshed after the finalized plan write with its current fingerprint and per-node `state` / `signed_off` / `signed_off_at`.
- The former silent drop at `create.py:1958` no longer drops a branch in prose — it surfaces it as a `defer`-suggested concept node the operator can flip to `include`.
- A full/batch `plan-tool detail` run derives and navigates plan-level scope before rendering any detail prompt when no tree exists, feeds those decisions into every authoring prompt, then collects and merges candidate deferrals and prompts **once at the end** for consolidated candidate-deferral sign-off, never per step.
- `plan-tool scope-review <name>` presents a current tree with `include` / `defer` / `wont_do` selection at every level, preserves prior `wont_do` decisions unless the operator explicitly changes them, is re-runnable, seeds from prior decisions, and exits 0 after a successfully created or reviewed tree, including an intentionally empty tree. It is **unconditionally mutating** — no recommend-only mode and no `--apply` gate; every state change persists immediately (§C). On a **treeless** plan it **derives one (create-if-missing)** rather than erroring by deterministically representing every existing scope bullet and committed step; an emit may enrich but never remove that seed, so an emit/parse miss does not discard or block review of the guaranteed nodes. On a plan with a current tree it spends **no Claude**. A stale tree is reported and refused without mutation; `--rederive` refreshes it with append-new, preserve-existing, flag-conflicts semantics before navigation. The emit fires only on create-if-missing or explicit `--rederive`.
- `plan-tool scope-review <name>` runs on a **bare plan with no detail files** (steps only), deriving and signing off a concept tree before any `detail` exists.
- Under `--yes` / non-TTY, suggested states are accepted but every deferral stays `signed_off=false`.
- A `state=include`, `signed_off=true` concept with no owning committed step raises a blocking `concept-coverage` completeness finding that re-surfaces until covered or re-deferred, and flips the rc under `--fail-on-findings`.
- The `## Out of scope` / `## Deferred` plan sections are rendered from the tree's `wont_do` / `defer` subtrees, not independently synthesized.
- Parent and child states are independent: selection never propagates, mixed markers are display-only, rendering uses each node's own `defer` / `wont_do` state, and coverage checks every signed-off included node even beneath a deferred or won't-do ancestor.
- Concept coverage **survives every structural remedy** (§H): split replacements partition matching feature ownership across children, a merge replacement unions its sources' feature ownership, and a re-ground preserves the covering title/features (or carries their union to its replacement), so recomputation finds every formerly covered concept. A `scope-out` of a covering step uses the all-or-recoverable commit protocol to flip its concept `include → defer` and write it into the carved forward-seed; any failed publish restores all three artifacts to their pre-operation bytes or absence, and a rollback failure reports the unrestored paths while preserving recovery material. A successful carve raises no blocking finding on the just-deferred concept and preserves `signed_off`.
- `tests/test_data_contract.py` passes with `ConceptTree` / `ConceptNode` registered and documented in `DATA_CONTRACT.md`.
- A plan with no `concepts.json` **audits inert** — completeness never auto-derives a tree, so it emits no `concept-coverage` / `concept-unsigned-deferral` findings and spends no Claude. Only an explicit `create` gate / `detail` / `scope-review` invocation derives one (cold-start nodes all `signed_off=false`).
- A present unreadable, malformed, schema-mismatched, or field-invalid `concepts.json` raises a typed integrity error and produces a blocking `concept-integrity` completeness finding; it is never treated as an absent tree.
- A concept-tree mutation is **never lost to the parallel apply path**: a regression test drives `completeness-apply --jobs N` and asserts no worker mutates `concepts.json` (writes are serial-only).
- The new `scope-review` command keeps the suite green across every drift-guard: capability catalog, generated `docs/cli/` reference, golden `--help`, and the `ConceptTree`/`ConceptNode` data contract (§F checklist).
- The concept-emit round-trip runs through an injected `invoker=` seam (no bare subprocess) and is covered by the conftest real-backend gate + TESTING.md neutralization table.
- The interactive navigator **persists on each selection**: every changed decision clears its prior `signed_off` / `signed_off_at` before persistence, an interrupt mid-walk loses no prior decision, re-entry resumes from the saved tree rather than restarting, and only a subsequent interactive confirmation after every descendant-bearing frame was reviewed or explicitly accepted restores the affected approval stamp; root confirmation cannot sign unseen descendants.
- The final step updates `BACKLOG.md` to reconcile #121.

## Deferred

- Full 3-way merge semantics for `--rederive` **on a plan that already has a tree** (MVP in step 8: append new nodes, preserve existing decisions, and flag conflicts for operator review).
- **Reconcile → stale-tree linkage (flag-only).** The concept tree is code-evidence-derived, so it can go stale exactly when grounding does. A future `reconcile-plan --refresh` / `reconcile-code` could reuse the existing `plan_fingerprint` / `code_fingerprint` drift signal to **flag** (never mutate) a stale tree, hinting `scope-review --rederive`. MVP leaves `--rederive` an explicit manual step; the `plan_fingerprint` guard (§A) already marks a stale tree "re-derive" on read.
- Concept-decision telemetry event.
- Auto-minting steps from included concepts.
