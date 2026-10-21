> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Attach Branch To Plan
status: completed
priority: medium
steps:
- id: 1
  title: 'Add project_config.py config leaf: branch_awareness_enabled (env→project→user→false),
    branch_prefixes (project-over-user, bad-list→warn+default), derive_branch/convention_names'
  creates:
  - plan_tool/project_config.py
  - tests/test_project_config.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/01-project-config-py-config-leaf-branch.md
  status: done
- id: 2
  title: 'Add branch readers/mutators to gitcommit.py: current_branch & default_branch
    (symbolic-ref→None / PLAN_TOOL_DEFAULT_BRANCH), branch_exists, create_and_checkout_branch
    & checkout_existing_branch ((rc,tail), never raise), list_branches (refs/heads+refs/remotes/*,
    no network)'
  files:
  - plan_tool/cli/gitcommit.py
  - tests/cli/test_gitcommit.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/02-branch-readers-mutators-gitcommit-py.md
  status: done
- id: 3
  title: 'Add branch_binding.py: git-config-backed ad-hoc override store (get/set/clear/all_bindings
    via `git config --local plan-tool.binding.<slug>`) + reverse_binding; set-loud
    / clear-quiet posture'
  creates:
  - plan_tool/branch_binding.py
  - tests/test_branch_binding.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/03-branch-binding-py-git-config-backed-ad.md
  status: done
- id: 4
  title: 'Add branch_ownership.py: the two separate lookups (expected_branch(P)=override-else-derive;
    branch_owner(B)=reverse_binding-else-convention_owner) and the pure 4-tier classifier
    (ad-hoc-beats-convention, registered-locally condition)'
  creates:
  - plan_tool/branch_ownership.py
  - tests/test_branch_ownership.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/04-branch-ownership-py-two-separate.md
  status: done
- id: 5
  title: 'Wire the run guard: add _preflight_branch_guard + --switch-branch flag to
    run_cmd.py, gated on branch_awareness_enabled and placed before _save_run_prefs;
    Tier 1-2 block, Tier 3 warn+proceed, Tier 4 nudge/clean-tree switch; non-git/detached
    HEAD → no-op note'
  files:
  - plan_tool/cli/run_cmd.py
  - tests/cli/test_run_cmd.py
  - tests/cli/package_surface_help.golden.txt
  complexity: high
  change_type: feature
  gate:
  - uv run plan-tool run --help | grep -q -- --switch-branch
  depends_on:
  - 2
  - 4
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/05-wire-run-guard-preflight-branch-guard.md
  status: done
- id: 6
  title: 'Register attach-branch / detach-branch verbs on manifest.py (register+dispatch+handlers,
    app.py re-import, parser.py CANONICAL_COMMAND_ORDER, __init__.py catalog/__all__):
    set/clear override, disabled-refusal (non-zero), convention-name collision warn
    + re-home from existing branch'
  files:
  - plan_tool/cli/manifest.py
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - tests/cli/test_manifest_cmds.py
  - tests/cli/package_surface_help.golden.txt
  complexity: high
  change_type: feature
  gate:
  - uv run plan-tool attach-branch --help >/dev/null && uv run plan-tool detach-branch
    --help >/dev/null
  depends_on:
  - 1
  - 2
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/06-register-attach-branch-detach-branch.md
  status: done
- id: 7
  title: 'Add create-time namespace-collision warning to authoring.py cmd_create:
    when enabled and branch_exists shows the derived branch already exists locally
    with no local owner, strong-warn and on continue create a first-free
    disambiguated branch (plan/<slug>-2) FROM the default branch'
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/07-create-time-namespace-collision-warning.md
  status: done
- id: 8
  title: 'Document branch-awareness across the six operator surfaces: attach-branch/detach-branch
    + run --switch-branch, the OFF-by-default opt-in canonical sentence, and project/user
    config (.plan-tool/config.json + PLAN_TOOL_BRANCH_AWARENESS)'
  files:
  - RUNBOOK.md
  - README.md
  - CLAUDE.md
  - BACKLOG.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 5
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/attach-branch-to-plan/08-document-branch-awareness-across-six.md
  status: done
---
# Attach Branch To Plan

## Overview

Adds **opt-in, branch-aware behavior** to `plan-tool`: a registered plan's branch is *derived* from its unique slug (`<primary-prefix><slug>`, default `plan/<slug>`) rather than stored, with an optional untracked ad-hoc override in local git config. Gated by a project/user config flag (`branch_awareness.enabled`) that defaults **OFF** — with it off, the tool behaves byte-for-byte as today. When on, a 4-tier run guard becomes *strict only when a local signal makes branch ownership unambiguous* (ad-hoc binding or convention name of a locally-registered plan) and stays out of the way otherwise, plus advisory namespace-collision warnings on `create` and `attach-branch`. Guiding principle: stay out of developers' way while nudging best practice; strictness is earned by signal, not imposed by a global setting.

## Problem statement

There is no association between a plan and the git branch it should run on, so `plan-tool run` executes wherever the developer happens to be checked out — risking running plan P's steps on another plan's branch or on the wrong branch entirely. A prior approach of storing a plan→branch binding was flagged because a git-tracked, branch-varying binding is itself problematic (tracked-vs-untracked dilemma, machine-switch fragility, two devs diverging). The missing capability: a way to know "where should plan P run?" and "who owns branch B?" that requires zero stored binding for convention plans, while keeping every existing repo's behavior unchanged.

## Architecture

A registered plan's branch is **derived from its unique slug**, deleting the storage problem rather than relocating it: for `<slug>` and the configured primary prefix the canonical branch is `<primary-prefix><slug>`. Because the slug is unique the slug→branch map is injective — one-plan-per-branch / one-branch-per-plan hold structurally with nothing to scan, and two devs on one plan compute the same name so git surfaces the collision. `branch_prefixes` is a configurable list (default `["plan/"]`) used asymmetrically: **create** uses the primary (first) prefix for one canonical name; **match/enforce** accepts any configured prefix so a dev who made `bugfix/<slug>` instead of `feature/<slug>` is still recognized. An optional **ad-hoc override** (`attach-branch <plan> <branch>`) records an arbitrary branch in local git config (`git config --local plan-tool.binding.<slug>`) — untracked, branch-independent, worktree-safe, lost on machine switch (falls back to the derived name, failing safe); `detach-branch` clears it.

Two lookups are kept deliberately **separate**: "Where should plan P run?" (the guard's expected branch) = `override(P)` if set, else `derive(primary-prefix, P.slug)`; "Who owns branch B?" (enforcement) = `reverse_binding(B)` if any plan is ad-hoc-bound to B, else `convention_owner(B)` (a registered plan whose `<prefix><slug>` equals B under any configured prefix. `reverse_binding(B)` is **deterministic even in a degenerate two-binding state**: should more than one plan ever be ad-hoc-bound to B, it returns the binding whose plan slug sorts first lexicographically, so Tier-1 ownership of B never flips run-to-run. `attach-branch` (step 6) **hard-refuses** binding a plan to a branch already ad-hoc-bound to a different plan, so no supported path forms the two-binding state in the first place — the lexicographic tiebreak survives only as defense-in-depth against a manually-corrupted local git config — see the namespace-collision paragraph. **and which is not itself ad-hoc-bound to a different branch** — a plan bound elsewhere forfeits the convention claim on its derived name, so its `<prefix><slug>` is not owned by it), else none. Keeping them distinct avoids knots like "P is overridden to `JIRA-1` but I'm sitting on `plan/P`": because P is ad-hoc-bound elsewhere it forfeits the convention claim on `plan/P`, so `plan/P` is owned by nobody (Tier-3 orphan-pattern, *not* P-owned) while P's runnable location is `JIRA-1` — "reserved" here means the name no other plan can convention-own, not that P still owns it.

**Graduated enforcement (the run guard)** classifies the current branch B by the strongest ownership signal on a mutating command (`run`, and reconcile under `run --iterate`) for plan P: Tier 1 — B has an explicit ad-hoc binding to plan Q → strong block unless Q == P (most intentional signal); Tier 2 — B is a configured-prefix convention name of a *locally-registered* plan Q → strong block unless Q == P (structural ownership); Tier 3 — B matches the pattern but *no local plan* owns it → advisory warning, then proceed (likely someone else's / unpulled); Tier 4 — B matches nothing → out of the way, at most a gentle nudge when P's expected branch is elsewhere (offer switch / `--switch-branch`). The tool is strict exactly at Tier 1–2 (the protected core, not behind a config knob) and out of the way at Tier 3–4. Non-interactive (`-y`/CI): Tier 1–2 still block; Tier 3–4 warn-and-proceed or switch-if-clean, never wedging automation.

**Namespace-collision warnings** protect the `<prefix>*` owned namespace with advisory, overridable warnings; steps 5–7 test individual branch names with `branch_exists` — step 7's create-time collision predicate and its first-free suffix search both probe single names rather than scanning, as do steps 5 and 6, and `list_branches` (built in step 2) has no production consumer in this plan: it is built ahead for the deferred remote-namespace scan over `refs/remotes/*` (no network): `create` whose derived branch already exists with no local owner → strong warn, and on continue create the new plan's branch **from the default branch** under a first-free disambiguated name (e.g. `plan/<slug>-2`), not from the colliding branch, **and ad-hoc-bind P to that disambiguated name** so the bind-elsewhere forfeit above demotes P's convention claim on the colliding `<prefix><slug>` — otherwise `convention_owner(<prefix><slug>)` would still return the registered P and the run guard would silently treat the foreign branch as Tier-2 P-owned. Name the residual explicitly: because P is registered, P's convention name `<prefix><slug>` could re-entangle with the foreign branch if the forfeit weren't load-bearing — so the intended posture is that the disambiguated plan is **not assigned the foreign `<prefix><slug>` as its own branch**. `create` may run on whatever feature branch the developer is sitting on, but the new colliding plan does not take the foreign convention name as its own and cannot have other processes run against it from that branch: a developer later checked out on the still-foreign `<prefix><slug>` who runs the new plan is treated as Tier-3 (orphan-pattern, no local owner — *not* Tier-2 P-owned), and `detail`/`run` are not silently permitted to operate the new plan from that foreign branch. Ad-hoc `attach-branch P <branch>` whose `<branch>` is another registered plan's convention name → strong warn, and on continue **re-home** by branching P's own `derive` name **from the existing branch** (to carry the work over) and binding/using that. The two differ deliberately in fork source — default for a genuinely new colliding plan, the existing branch for a re-home. Ad-hoc `attach-branch P <branch>` whose `<branch>` is already **ad-hoc-bound to a different plan Q** → **hard-refuse** (non-zero exit, bind nothing, name Q and point at `detach-branch Q`): forming the two-binding-on-one-branch state would make `reverse_binding(B)` a one-branch→two-slug map, so step 6 declines rather than recording P's binding and leaves the operator to resolve the desync explicitly. The lexicographic tiebreak in `reverse_binding(B)` (above) is not reached on any supported path; it remains only as defense-in-depth against a manually-corrupted local git config.

Branch creation is **clean-tree gated**, consented (prompts, or `--switch-branch`/`-y` to skip), reuse-if-exists, and reports what it did — never deleting a branch, never switching over uncommitted work. **Fork source for the run-guard `--switch-branch` create:** when Tier 4 creates P's missing expected branch, it forks **from the current HEAD** (`create_and_checkout_branch` off the developer's checkout), *not* from the default branch as `create`'s namespace-collision path does. The difference is deliberate: `create` forks from default because a genuinely new colliding plan must not be based on another plan's work, whereas the Tier-4 switch fires only on a clean tree where the current branch is unowned (matches nothing), so its HEAD is the developer's own intended starting point and is carried over rather than discarded. **Partial-failure recovery:** when a multi-step composition has already switched away from the invocation branch before failing — step 7's create-from-default path (`checkout_existing_branch(default)` succeeds, then `create_and_checkout_branch(candidate)` fails) and step 6's re-home path (`checkout_existing_branch(existing)` succeeds, then `create_and_checkout_branch(derive)` fails) both being cases in point — it restores the original invocation branch (best-effort `checkout_existing_branch` back) before returning non-zero, so a failed create never silently strands the developer on the default or colliding branch with no plan; the report names both the failure and the branch it was restored to. Steps 6 and 7 each operationalize this restore-on-failure behavior (see their acceptance criteria).

Configuration is a stdlib-only leaf `plan_tool/project_config.py` (mirroring `backend_config.py` / `jira_config.py`) reading project (`<repo-root>/.plan-tool/config.json`) and user (`~/.plan-tool/config.json`, lazy `Path.home()`) levels: `{ "branch_awareness": { "enabled": false, "branch_prefixes": ["plan/"] } }`. Precedence (first explicitly set wins): `PLAN_TOOL_BRANCH_AWARENESS` env → project (if `enabled` present) → user (if present) → `false`; the user level is the cross-project default, a project setting overrides per repo. `branch_prefixes` follows the same project-over-user precedence (primary = first; matching uses all; each `<prefix><slug>` must be a valid git ref per `git check-ref-format`; a bad/empty list falls back to the default with a warning, never a crash). `enabled` is a single master switch: when off, every new path short-circuits to today's behavior *before* deriving/reading any branch, and the branch commands refuse with "branch awareness is disabled; enable it in `.plan-tool/config.json`" (non-zero). `project_config.py` must stay a leaf (no imports from `create`/`launcher`/`locator`) so any command can ask "is it on?", "what are the prefixes?", "derive for this slug?" without a cycle.

Seams to verify before extending: git helpers already in `plan_tool/cli/gitcommit.py` (`working_tree_dirty`, `path_is_gitignored`, `commit_all`) — no current-branch/default-branch/branch-exists/branch-create/branch-list reader yet, add them there (branch listing via `git for-each-ref` over `refs/heads` + `refs/remotes/*`, branch creation+checkout via `git switch -c`/`git switch`, ref validity via `git check-ref-format`); plan resolution `locator.py:resolve_plan_for_context` / `resolve_registered_plan` and `load_manifest_plan_paths` (the set the Tier-2 convention-owner scan needs); run entry `launcher.py:resolve_step` with `cli/run_cmd.py` as the guard home before step resolution; create entry `cli/authoring.py:cmd_create` for the create-time collision warning; CLI registration via each `app.py:COMMAND_MODULES` module's `register(subparsers)`, branch commands joining the `cli/manifest.py` group.

## References

- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — Defines the exact rules for valid Git ref/branch names, which the plan's slug→branch derivation must satisfy for every configured prefix.
- [Git - git-config Documentation](https://git-scm.com/docs/git-config) — Authoritative reference for reading/writing local-scope config (`git config --local`), the storage mechanism for the untracked ad-hoc plan→branch override.
- [Git - git-symbolic-ref Documentation](https://git-scm.com/docs/git-symbolic-ref) — Explains resolving `refs/remotes/origin/HEAD` and HEAD, needed for default-branch detection and the detached-HEAD no-op path in the run guard.
- [Git - git-for-each-ref Documentation](https://git-scm.com/docs/git-for-each-ref) — Documents formatted, no-network listing of branch refs, the basis for `list_branches`, which is built ahead in step 2 for the deferred remote-namespace scan; the step 5–7 collision checks use `branch_exists` on single names.
- [Git - git-rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — Covers `--abbrev-ref HEAD`, `--is-inside-work-tree`, and ref resolution used to read the current branch and detect non-git/detached states for the guard.
- [Git - git-branch Documentation](https://git-scm.com/docs/git-branch) — Reference for creating, listing, and checking existence of branches, underpinning the clean-tree-gated, reuse-if-exists branch creation and `--switch-branch` behavior.
- [subprocess — Subprocess management (Python docs)](https://docs.python.org/3/library/subprocess.html) — Stdlib reference for safely shelling out to git with argument lists and return-code handling, matching the tool's invoker-seam discipline.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **No on-by-default** — ships OFF; stays OFF until a repo/user opts in.
- **No global `enforcement: block` knob** — strictness is earned by signal (Tier 1–2); a future Tier-4 hardening is additive.
- **Two config levels only — project and user** — no XDG, no system level.
- **No tracked binding** — never in `plans.json` (stays a string array), never in `schema.py`/frontmatter; only the optional ad-hoc override is stored, only in untracked local git config.
- **No cross-developer enforcement / sync** — convention plans surface double-staffing via the shared name + orphan-pattern warning; "don't double-staff" stays a coordination concern.
- **No `create` branch gate / deflect-to-seed** — `create` works on any branch; it only warns on a namespace collision.
- **No branch deletion** — the tool creates + checks out; `detach` clears an override and leaves the branch.
- **No re-grounding here** — branch creation is the trigger, but the fingerprint-gated plan↔code reconcile is its own plan (`plan-refresh-against-code`); this plan only names the hook point.
- **No guard on read-only / authoring commands** (`create`, `detail`, `jira`, `verify`, `inspect`, `annotate`) beyond the create collision warn; the guard helper is reusable so they can opt in later.
- **No remote/upstream binding, no PR linkage, no worktree-graph awareness** — remote refs are not consulted; collision warnings scan local `refs/heads` only.

## Risks

- **Flag-check leakage** (severity: high — silently changes off-state behavior). Any new path that derives/reads/creates a branch before checking `branch_awareness_enabled` breaks the byte-for-byte off-state guarantee. Mitigation: check the flag first on every path; make off-is-a-no-op an explicit test per path.
- **Guard placement too broad.** Enforcing in `resolve_plan_for_context` would block read-only commands on the wrong branch. Mitigation: keep the guard a `run_cmd.py` preflight only.
- **Tier misclassification** (load-bearing). The ad-hoc-beats-convention precedence and the "registered-locally" condition determine ownership. Mitigation: test each tier and the both-claimed edge explicitly so a branch is never owned by the wrong plan.
- **Branch creation is a mutation.** Mitigation: clean-tree gated, consented, reuse-if-exists, never over uncommitted work; `--switch-branch` strictly `working_tree_dirty`-gated (never stash/force) — note `git switch` itself refuses to clobber local changes absent `--discard-changes`/`--merge`, which neither is passed.
- **Disambiguation safety.** The first-free suffix search must itself be collision-safe and bounded.
- **Branch-name normalization.** Pick one current-branch reader and compare normalized strings against derived/override/owner names so the guard and the scans can't disagree.
- **Default-branch detection fragility.** Undeterminable default → "don't block" (skip create-from-default / skip the gate) + honor `PLAN_TOOL_DEFAULT_BRANCH`. A `PLAN_TOOL_DEFAULT_BRANCH` that names a branch which does not resolve (the env var is returned verbatim, so `checkout_existing_branch(default)` would fail) counts as *undeterminable* and degrades to this skip-disambiguation path — it must **not** hard-abort `create` with a non-zero rc; a misconfigured env var fails safe exactly like the `None`-default case. When step 7's collision gate skips disambiguation because the default is undeterminable, it must emit a **strong warning** (not just an info note): the plain create proceeds with no ad-hoc binding, so the foreign `<prefix><slug>` is left silently convention-owned by the new plan (Tier-2), re-exposing the run-on-foreign-work hazard the gate exists to prevent — the operator has to be told protection was skipped.
- **Non-git / detached HEAD** must never hard-fail; the "unknown branch → proceed with a note" path is load-bearing — test it.
- **Slug → ref validity.** Derivation must yield a valid ref for every configured prefix (`git check-ref-format` rules: at least one `/`, no `..`, no trailing `.lock`, no control/space/`~^:?*[`, no `@{`); reject/encode anything the prefix could introduce.

## Testing

Follow TESTING.md's invoker-seam discipline — no real `claude`, no real `git checkout` against the dev repo; drive git against a `tmp_path` repo or stub. Coverage areas:

- **Config reader** (`tests/test_project_config.py`): two-level precedence, malformed-ignored, env override, prefix list + bad-prefix fallback; `derive_branch` / `convention_names`.
- **Off-state no-op:** every gated behavior is a strict no-op when the flag is off — an explicit test per new path.
- **Git helpers + `list_branches`:** against a `tmp_path` repo.
- **Binding store** (`tests/test_branch_binding.py`): round-trip (`get`/`set`/`clear`, `all_bindings`) + `reverse_binding`.
- **4-tier classifier:** each tier in isolation (ad-hoc-owned, convention-owned, orphan-pattern → warn, unowned → nudge) and the ad-hoc-beats-convention precedence (a branch both ad-hoc-bound to Q and a convention name of R is owned by Q).
- **Branch command:** create from default, reuse existing, dirty-tree refusal.
- **`attach` / `detach`:** override set/clear; convention-name collision warn + re-home.
- **Run guard** (`@pytest.mark.integration`, driving the `run` preflight): each tier (block / warn+proceed / nudge); `--switch-branch` clean switches vs dirty refuses; non-git / detached HEAD → no-op. Include a **cross-step forfeit case** that exercises the full create→bind→run chain end-to-end (locking in the steps 4/5/7 forfeit invariant): after a `create` collision disambiguates `plan/<slug>` (binding P to `plan/<slug>-2`), run P while checked out on the foreign `plan/<slug>` and assert a **Tier-3 warn-and-proceed** (orphan-pattern, not Tier-2 P-owned). **This end-to-end forfeit test is owned by step 5** — it lives in `tests/cli/test_run_cmd.py` and drives a real `cmd_create` collision-disambiguation bind plus a real `branch_binding` round-trip (the ownership symbols are **not** monkeypatched), so the create→bind→run seam itself is verified rather than each module in isolation.
- **`create` collision** (`@pytest.mark.integration`, via `cmd_create`): collision warn + disambiguated-from-default branch.

Name the `run`/`create` guard integration tests when modifying `run_cmd.py` / `authoring.py`. Every existing test suite must still pass (the off-state guarantee).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- With no config (or `enabled:false`), the tool behaves byte-for-byte as before: no derivation, `run` ignores branches, `create` works anywhere, branch commands refuse "disabled — enable in `.plan-tool/config.json`" (non-zero exit); every existing test passes.
- Enabling via project/user config or `PLAN_TOOL_BRANCH_AWARENESS=1` activates the behaviors; project `enabled:false` overrides a user default; `branch_prefixes` changes the prefixes (project over user), primary used for create, all accepted for matching, bad list → warn+default.
- **Tier 1:** on a branch ad-hoc-bound to Q, running any plan ≠ Q is blocked (naming Q); running Q proceeds.
- **Tier 2:** on `<prefix><slug>` of a locally-registered Q, running any plan ≠ Q is blocked; running Q proceeds.
- **Tier 3:** on a pattern-matching branch with no local owner, running a plan warns and proceeds.
- **Tier 4:** on an unowned branch, running plan P whose expected branch is elsewhere nudges/offers to switch; `--switch-branch` creates-if-missing + checks out on a clean tree (refuses on dirty).
- Ad-hoc precedence: a branch both ad-hoc-bound to Q and a convention name of R is owned by Q (Tier 1 over Tier 2), and the conflict is surfaced.
- `create` whose derived branch already exists with no local owner warns; on continue it makes a first-free disambiguated branch from default, not from the colliding branch. When the default branch is undeterminable the disambiguation is skipped (plain create, no ad-hoc binding) and `create` emits a **strong warning** that protection was skipped and the foreign `<prefix><slug>` is now silently convention-owned by the new plan — never a quiet info note.
- After a `create` collision disambiguation, P is ad-hoc-bound to `plan/<slug>-2` and does **not** own the foreign colliding `plan/<slug>`: `branch_owner(plan/<slug>)` does not return P (a plan ad-hoc-bound elsewhere forfeits the convention claim on its derived name), so running P while checked out on the foreign branch is treated as Tier-3 (orphan-pattern), not silently as Tier-2 owned; `create` may run on any feature branch, but the new plan is not assigned the foreign branch as its own and `detail`/`run` are not silently permitted against it from that branch.
- `attach-branch P <branch>` where `<branch>` is another registered plan's convention name warns; on continue it re-homes P's work to P's own convention name from the existing branch.
- `attach-branch P <branch>` where `<branch>` is already ad-hoc-bound to a different plan Q is hard-refused with a non-zero exit (naming Q and pointing at `detach-branch Q`) and records no binding; `reverse_binding(<branch>)` continues to return Q. The lexicographic tiebreak in `reverse_binding` is unreachable on any supported path and guards only a manually-corrupted two-binding config.
- **Restore on partial failure:** if step 7's create-from-default disambiguation has already checked out the default branch and the disambiguated-branch create then fails, the developer is restored to the original invocation branch (best-effort) before a non-zero return, and the report names both the failure and the restored branch — never stranded on default with no plan.
- **Restore on partial failure:** if step 6's `attach-branch` re-home has already checked out the existing colliding branch and the derive-name create then fails, the developer is restored to the original invocation branch (best-effort) before a non-zero return, and the report names both the failure and the restored branch — never stranded on the colliding branch.
- Outside a git repo / detached HEAD: no-op + note, never a crash.
- `plan-tool create` is otherwise unchanged on any branch.

## Deferred

- **Opting read-only / authoring commands into the run guard** — the guard helper ships reusable, but nothing beyond `run`/reconcile wires it in; revisit once the Tier 1–2 core is proven.
- **Tier-4 hardening (a global enforcement-block knob)** — held back to keep this iteration "strict by signal, not by setting"; additive once Tier 1–3 land.
