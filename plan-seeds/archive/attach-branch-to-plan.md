# Plan seed: branch-aware plans (derived names, multi-prefix, ad-hoc override, graduated enforcement)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/attach-branch-to-plan.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition; the author then runs
`plan-tool detail` per step.

---

## Guiding principle

**Stay out of developers' way while guiding best practice around branch
usage.** The tool is hands-off by default and nudges toward the right
branch; it only becomes *strict* when an unambiguous local signal says a
branch is owned by a specific plan. Strictness is *earned by signal*, not
imposed by a global setting.

> **Gated by a project-config flag that defaults to OFF.** With the flag
> off (the default, and the state of every existing repo) `plan-tool`
> behaves exactly as today: nothing is derived, no guard fires, the
> branch commands refuse as disabled. Everything below is contingent on
> the flag being explicitly turned on.

## How a plan associates with a branch

A registered plan's branch is **derived from its unique slug**, with an
optional explicit override — no plan→branch binding is persisted in any
tracked file.

- **Derived (default, zero storage).** For slug `<slug>` and configured
  prefixes, the canonical branch is `<primary-prefix><slug>` (default
  prefix `plan/` → `plan/<slug>`). Because the slug is unique, the
  slug→branch map is injective: one-plan-per-branch / one-branch-per-plan
  hold **structurally**, with nothing to scan.
- **Multiple project prefixes.** `branch_prefixes` is a configurable
  **list** (default `["plan/"]`). The asymmetry is the point:
  - **Create** uses the **primary** (first) prefix — one canonical name.
  - **Match / enforce** accepts **any** configured prefix — so a dev who
    made `bugfix/<slug>` instead of `feature/<slug>` is still recognized
    as that plan's branch, not flagged.
- **Ad-hoc override (optional, untracked, per-clone).** `attach-branch
  <plan> <branch>` records an arbitrary branch in **local git config**
  (`git config --local plan-tool.binding.<slug>`), for teams/branches
  that don't fit the convention (e.g. a ticket-named branch). Untracked =
  branch-independent and never the git-tracked, branch-varying binding a
  prior audit flagged. Lost on a machine switch → the plan simply falls
  back to its derived name (fails safe); `detach-branch` clears it.

Why derive-by-default instead of always storing a binding: it **deletes**
the storage problem rather than relocating it — no tracked-vs-untracked
dilemma, machine-switch is moot for convention plans, and two devs on one
plan compute the *same* name so git surfaces the collision. The override
buys back arbitrary-name flexibility, and its only cost (machine-switch
re-attach) is confined to the plans that opted into it.

## Two lookups (keep them separate)

- **"Where should plan P run?"** (the guard's expected branch) =
  `override(P)` **if set, else** `derive(primary-prefix, P.slug)`.
- **"Who owns branch B?"** (enforcement) =
  `reverse_binding(B)` **if any plan is ad-hoc-bound to B, else**
  `convention_owner(B)` (a registered plan whose `<prefix><slug>` equals B
  under any configured prefix), **else** none.

Both consult the ad-hoc store. Keeping them distinct avoids knots like
"P is overridden to `JIRA-1` but I'm sitting on `plan/P`": `plan/P` stays
P's reserved convention name (owned), while P's *runnable* location is
`JIRA-1`.

## Graduated enforcement (the run guard) — strict only when ownership is unambiguous

On a mutating command (`run`, and reconcile under `run --iterate`) for
plan P, classify the **current branch B** by the strongest ownership
signal and act:

1. **Tier 1 — B has an explicit ad-hoc binding to a plan Q → strong
   block** (unless Q == P). The most intentional signal — the developer
   set it. "You're on Q's bound branch; run Q here, or switch."
2. **Tier 2 — B is a configured-prefix convention name of a *locally-
   registered* plan Q → strong block** (unless Q == P). Structural
   ownership; the name matches a plan you have registered.
3. **Tier 3 — B matches the pattern but *no local plan* owns it →
   advisory warning, then proceed.** Likely someone else's / unpulled —
   surfaced, not enforced.
4. **Tier 4 — B matches nothing → out of the way.** At most a gentle
   nudge when P's expected branch is elsewhere ("this plan runs on
   `plan/<slug>` — switch? [Y/n]" / `--switch-branch`).

So the tool is **strict exactly when a local signal makes ownership
unambiguous (Tier 1–2)** and **stays out of the way otherwise (Tier 3–4)**
— the guiding principle, made mechanical. Tier 1–2 blocks are not behind
a config knob; they are the protected core. (A future opt-in could harden
Tier 4 for max-strict teams; not load-bearing now.)

Non-interactive (`-y` / CI): Tier 1–2 still block (safe); Tier 3–4
warn-and-proceed or switch-if-clean — never wedge automation.

## Namespace-collision warnings (guide, don't block)

The convention makes `<prefix>*` an owned namespace; protect it from
silent cross-wiring with **advisory, overridable** warnings (remote-
aware, "as of last fetch" — scan `refs/heads` + `refs/remotes/*`, no
network):

- **`create` whose derived branch already exists with no local owner →
  strong warn** ("a branch `plan/<slug>` already exists but you have no
  local plan for it — it may be a teammate's / unpulled"). On continue,
  create the new plan's branch **from the default branch** under a
  disambiguated free name (e.g. first-free `plan/<slug>-2`) — **not** from
  the colliding branch (don't inherit another plan's WIP).
- **Ad-hoc `attach-branch P <branch>` whose `<branch>` is `<prefix><other-
  registered-slug>` → strong warn** (you're binding P to another plan's
  convention branch). On continue, **re-home**: branch the proper name
  (P's own `derive`) **from the existing branch** (you want to carry that
  work over) and bind/use that.

The two differ deliberately in fork source — **default** for a genuinely
new colliding plan, **the existing branch** for a re-home — and both name
the disambiguation rule (first-free suffix / the real plan's convention
name).

## Consented branch creation

The tool creates branches, but never surprises: creation is **clean-tree
gated**, prompts (or `--switch-branch` / `-y` to skip), and **reports what
it did**. It never deletes a branch and never switches over uncommitted
work.

## Configuration gate (two levels)

A stdlib-only leaf `plan_tool/project_config.py` (mirroring
`backend_config.py` / `jira_config.py`) reads **project**
(`<repo-root>/.plan-tool/config.json`) and **user**
(`~/.plan-tool/config.json`, lazy `Path.home()`):

```json
{ "branch_awareness": { "enabled": false, "branch_prefixes": ["plan/"] } }
```

- **`enabled` — default OFF.** Absent file/key/malformed at a level
  contributes nothing.
- **Precedence (first explicitly set wins):** `PLAN_TOOL_BRANCH_AWARENESS`
  env → project (if `enabled` present) → user (if present) → `false`. The
  user level is the cross-project default; a project setting `enabled`
  (true *or* false) overrides it per repo.
- **`branch_prefixes` — default `["plan/"]`,** same project-over-user
  precedence. Primary = first; matching uses all. Each `<prefix><slug>`
  must be a valid git ref; a bad/empty list falls back to the default
  with a warning, never a crash.
- **Single master switch.** `enabled` gates everything. When off, every
  new path short-circuits to today's behavior *before* deriving/reading
  any branch; the branch commands refuse with "branch awareness is
  disabled; enable it in `.plan-tool/config.json`" (non-zero).

Keep `project_config.py` a leaf (stdlib only, no imports from
`create`/`launcher`/`locator`) so any command can ask "is it on?", "what
are the prefixes?", "derive for this slug?" without a cycle.

## Seams already in place (verify before extending)

- **Git helpers** — `plan_tool/cli/gitcommit.py` already shells to git
  (`working_tree_dirty`, `path_is_gitignored`, `commit_all`). No
  current-branch / default-branch / branch-exists / branch-create /
  branch-list reader yet — add them here.
- **Plan resolution** — `locator.py:resolve_plan_for_context` /
  `resolve_registered_plan` map a slug to a registered plan, and
  `load_manifest_plan_paths` enumerates registered plans (the set the
  Tier-2 convention-owner scan needs). The slug is the only input the
  derivation needs.
- **Run entry** — `launcher.py:resolve_step`; `cli/run_cmd.py` is the
  `run` dispatcher and the home for the guard *before* step resolution.
- **Create entry** — `cli/authoring.py:cmd_create` is where the
  namespace-collision warning on create lands.
- **CLI registration** — each `app.py:COMMAND_MODULES` module exports
  `register(subparsers) -> dict[str, Handler]`; the branch commands join
  an appropriate group (`cli/manifest.py`).

## Scope of work

1. **Config leaf** `plan_tool/project_config.py` — two-level reader for
   `enabled` + `branch_prefixes`; accessors `branch_awareness_enabled(repo)`,
   `branch_prefixes(repo)`, `derive_branch(slug, repo)` (primary prefix),
   `convention_names(slug, repo)` (all prefixes, for matching). Validate
   prefixes/refs, fall back with a warning. Lands first.
2. **Git helpers** in `cli/gitcommit.py` — `current_branch`,
   `default_branch` (origin HEAD → local main/master → `PLAN_TOOL_DEFAULT_BRANCH`),
   `branch_exists`, `create_and_checkout_branch(*, base) -> (rc, tail)`,
   and `list_branches(repo)` (local + remote-tracking, for collision
   detection). Mirror the existing subprocess/failure style.
3. **Ad-hoc binding store** `plan_tool/branch_binding.py` over `git config
   --local` (keys `plan-tool.binding.<slug>`): `get`/`set`/`clear`,
   `all_bindings`, and **`reverse_binding(branch)`**. Untracked, branch-
   independent, worktree-safe via git's own config resolution.
4. **Ownership + expected-branch resolver** (a small pure module): pure
   functions `expected_branch(plan, repo)` (override-or-derive) and
   `branch_owner(branch, repo, registered_slugs)` (reverse-binding →
   convention-owner → none), plus the 4-tier classifier used by the
   guard. No IO beyond the store/config leaves.
5. **Branch commands** under the `manifest` group, **refuse-as-disabled
   when off**: a command that creates+checks-out plan P's branch
   (consented, clean-tree gated, reuse-if-exists); `attach-branch P
   <branch>` (set ad-hoc override, with the convention-name collision
   warning + re-home on continue); `detach-branch P` (clear the override;
   leave the branch). No stored *convention* binding — only the override
   is stored.
6. **Run guard + `--switch-branch`** in `run_cmd.py` — preflight before
   `resolve_step`, no-op unless the flag is on; apply the 4-tier model
   (Tier 1–2 block, Tier 3 warn+proceed, Tier 4 nudge/offer-switch).
   `--switch-branch` creates-if-missing + checks out P's expected branch
   on a clean tree, refuses on dirty. Scope to the mutating path; keep the
   guard one reusable function.
7. **Namespace-collision warning on `create`** in `cli/authoring.py` —
   when the new plan's derived branch already exists (local or remote-
   tracking) with no local owner, strong-warn; on continue, branch from
   **default** under a first-free disambiguated name. (The attach-time
   collision lives in step 5.)
8. **Tests.** Config reader (two-level precedence, malformed-ignored, env
   override, prefix list + bad-prefix fallback); `derive_branch` /
   `convention_names`. **Every gated behavior is a strict no-op when off.**
   Git helpers + `list_branches` against a `tmp_path` repo. Binding store
   round-trip + `reverse_binding`. The 4-tier classifier (each tier in
   isolation: ad-hoc-owned, convention-owned, orphan-pattern → warn,
   unowned → nudge; ad-hoc-beats-convention precedence). Branch command
   (create from default, reuse existing, dirty-tree refusal). `attach`/
   `detach` (override set/clear; convention-name collision warn + re-home).
   Run guard each tier (block / warn+proceed / nudge); `--switch-branch`
   (clean switches, dirty refuses); non-git / detached → no-op. `create`
   collision warn + disambiguated-from-default branch. Follow TESTING.md's
   invoker-seam discipline — no real `claude`, no real `git checkout`
   against the dev repo; drive git against a `tmp_path` repo or stub.
9. **Docs.** `RUNBOOK.md` (enable per-project/user + precedence, the
   `branch_prefixes` knob, the derive-and-run walkthrough, the 4-tier
   behavior and when it blocks vs nudges, ad-hoc attach/detach, recovery
   on the wrong branch); `PLAN_FORMAT.md` (one line: the branch is derived
   from the slug / optionally overridden in local git config — not stored
   on the plan or manifest); CLAUDE.md's command list if enumerated. Make
   default-off, opt-in, derived, and out-of-the-way explicit.

## Non-goals

- **No on-by-default.** Ships OFF; stays OFF until a repo/user opts in.
- **No global `enforcement: block` knob (not needed).** Strictness is
  earned by signal (Tier 1–2). A future Tier-4 hardening is additive.
- **Two config levels only — project and user.** No XDG, no system level.
- **No tracked binding.** Never in `plans.json` (stays a string array),
  never in `schema.py`/frontmatter. Only the *optional ad-hoc override*
  is stored, and only in untracked local git config.
- **No cross-developer enforcement / sync.** Convention plans surface
  double-staffing via the shared name + the orphan-pattern warning;
  "don't double-staff" stays a coordination concern.
- **No `create` branch gate / deflect-to-seed.** `create` works on any
  branch; it only *warns* on a namespace collision.
- **No branch deletion.** The tool creates + checks out; `detach` clears
  an override and leaves the branch.
- **No re-grounding here.** Branch creation is the trigger, but the
  fingerprint-gated plan↔code reconcile is its own plan
  (`plan-refresh-against-code`); this plan only names the hook point.
- **No guard on read-only / authoring commands** (`create`, `detail`,
  `jira`, `verify`, `inspect`, `annotate`) beyond the create collision
  warn. The guard helper is reusable so they can opt in later.
- **No remote/upstream binding, no PR linkage, no worktree-graph
  awareness.** Remote refs are read only to *warn* about collisions.

## Acceptance criteria (plan-level)

- **With no config (or `enabled:false`), the tool behaves byte-for-byte
  as before:** no derivation, `run` ignores branches, `create` works
  anywhere, branch commands refuse "disabled — enable in
  `.plan-tool/config.json`" (non-zero). Every existing test passes.
- Enabling via project/user config or `PLAN_TOOL_BRANCH_AWARENESS=1`
  activates the behaviors; project `enabled:false` overrides a user
  default; `branch_prefixes` changes the prefixes (project over user),
  primary used for create, all accepted for matching, bad list →
  warn+default.
- **Tier 1:** on a branch ad-hoc-bound to Q, running any plan ≠ Q is
  blocked (naming Q); running Q proceeds.
- **Tier 2:** on `<prefix><slug>` of a locally-registered Q, running any
  plan ≠ Q is blocked; running Q proceeds.
- **Tier 3:** on a pattern-matching branch with no local owner, running a
  plan warns and proceeds.
- **Tier 4:** on an unowned branch, running plan P whose expected branch
  is elsewhere nudges/offers to switch; `--switch-branch` creates-if-
  missing + checks out on a clean tree (refuses on dirty).
- Ad-hoc precedence: a branch both ad-hoc-bound to Q and a convention name
  of R is owned by **Q** (Tier 1 over Tier 2), and the conflict is
  surfaced.
- `create` whose derived branch already exists with no local owner warns;
  on continue it makes a first-free disambiguated branch **from default**,
  not from the colliding branch.
- `attach-branch P <branch>` where `<branch>` is another registered plan's
  convention name warns; on continue it re-homes P's work to P's own
  convention name **from the existing branch**.
- Outside a git repo / detached HEAD: no-op + note, never a crash.
- `plan-tool create` is otherwise unchanged on any branch.

## Risks

- **Flag-check leakage.** Any new path that derives/reads/creates a branch
  before checking `branch_awareness_enabled` changes off-state behavior.
  Check the flag first on every path; make off-is-a-no-op an explicit test
  per path.
- **Guard placement too broad.** Don't enforce in
  `resolve_plan_for_context` (would block read-only commands on the wrong
  branch). Keep it a `run_cmd.py` preflight.
- **Tier misclassification.** The ad-hoc-beats-convention precedence and
  "registered-locally" condition are load-bearing; test each tier and the
  both-claimed edge explicitly so a branch is never owned by the wrong
  plan.
- **Branch creation is a mutation.** Clean-tree gated, consented, reuse-
  if-exists, never over uncommitted work; `--switch-branch` strictly
  `working_tree_dirty`-gated (never stash/force).
- **Collision detection staleness / cost.** Remote-tracking scan is "as of
  last fetch" (say so; don't promise freshness); no network in the hot
  path.
- **Disambiguation safety.** The first-free suffix search must itself be
  collision-safe and bounded.
- **Branch-name normalization.** Pick one current-branch reader and
  compare normalized strings against derived/override/owner names so the
  guard and the scans can't disagree.
- **Default-branch detection fragility.** Undeterminable default → "don't
  block" (skip create-from-default / skip the gate) + honor
  `PLAN_TOOL_DEFAULT_BRANCH`.
- **Non-git / detached HEAD** must never hard-fail; the "unknown branch →
  proceed with a note" path is load-bearing — test it.
- **Slug → ref validity.** Derivation must yield a valid ref for every
  configured prefix; reject/encode anything the prefix could introduce.
