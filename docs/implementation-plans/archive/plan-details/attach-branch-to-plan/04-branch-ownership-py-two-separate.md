> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add `branch_ownership.py`: the two separate lookups + the pure 4-tier classifier

## Summary

Creates `plan_tool/branch_ownership.py`, the ownership-decision layer that sits above the step-1 config leaf (`plan_tool/project_config.py`) and the step-3 override store (`plan_tool/branch_binding.py`). It exposes the two **deliberately-separate** lookups — `expected_branch(P)` ("where should plan P run?" = override-else-derive) and `branch_owner(B)` ("who owns branch B?" = reverse-binding-else-convention-owner) — plus the **pure 4-tier classifier** `classify_branch` that grades a current branch B against a plan P into Tier 1 (ad-hoc-owned) / Tier 2 (convention-owned, locally-registered) / Tier 3 (orphan-pattern) / Tier 4 (unowned). The load-bearing decisions are **ad-hoc-beats-convention** (`reverse_binding` is consulted before convention ownership), the **registered-locally condition** (Tier 2 fires only when the convention-owning slug is in the caller-supplied registered set), and the **forfeit-when-bound-elsewhere rule** (`branch_owner` drops a convention result whose slug is ad-hoc-bound to a *different* branch, so a plan bound away from its derived name no longer convention-owns it). The classifier is **pure** — it consumes the lookup's result as data and does zero I/O — so the run guard (step 5) does the git-config read once via `branch_owner`, then classifies without re-reading. Adds `tests/test_branch_ownership.py`.

## Table of Contents

- [Why](#why) — what the ownership layer unblocks and why the classifier must be pure
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — the two lookups, the pure classifier, the precedence rules, and the import contract
- [Tests](#tests) — per-tier and per-lookup unit cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git ref/config docs underpinning derivation and the override store
- [Deferred](#deferred) — call-site wiring and registered-slug sourcing left to steps 5–7

## Why

- **The run guard (step 5), `attach-branch`/`detach-branch` (step 6), and the create-collision warning (step 7) all need two distinct questions answered, and answering them in one tangled function produces wrong ownership.** "Where should P run?" (`expected_branch`) and "who owns B?" (`branch_owner`) are genuinely different: a plan overridden to `JIRA-1` runs at `JIRA-1`, and because it is ad-hoc-bound elsewhere it forfeits the convention claim on `plan/<slug>`, so `plan/<slug>` is owned by nobody (Tier-3 orphan-pattern, *not* P-owned) — collapsing the two would mis-route the guard or silently treat the foreign `plan/<slug>` as P-owned. Keeping them separate is what the plan's "Architecture" calls deliberate.
- **Tier misclassification is a load-bearing risk (plan "Risks → Tier misclassification").** The ad-hoc-beats-convention precedence and the registered-locally condition decide which plan owns a branch; a single wrong branch could block the right developer or silently allow a run on someone else's branch. A pure, data-in/verdict-out classifier is the only thing that makes each tier and the both-claimed edge testable without a real repo.
- **`depends_on: [1, 3]` only.** This step builds on step 1's `derive_branch` / `convention_names` and step 3's `get_binding` / `reverse_binding`; it needs **no** git reader (step 2) — the current branch is read by the step-5 guard, not here — and imports **nothing** from `locator`, so the registered-plan set is supplied by the caller.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/branch_ownership.py` — the ownership layer: the `Tier` enum, the `BranchOwner` / `BranchClassification` dataclasses, the two lookups `expected_branch` / `branch_owner`, the pure `classify_branch`, and the pure helpers `convention_owner` / `matches_convention_pattern`.
  - `tests/test_branch_ownership.py` — unit coverage for both lookups, each of the four tiers in isolation, the ad-hoc-beats-convention precedence, and the registered-locally condition.
- **Existing files (edits only):** none. This step adds no call sites; steps 5–7 import these symbols.

## Implementation

All work lands in `plan_tool/branch_ownership.py`. Keep it a **mid-tier leaf**: import only `dataclasses`, `enum.IntEnum`, `pathlib.Path`, typing, and the two upstream leaves — `from plan_tool.project_config import derive_branch, convention_names` (step 1) and `from plan_tool.branch_binding import get_binding, reverse_binding` (step 3). Import **nothing** from `plan_tool.create` / `launcher` / `locator` / `cli.*` / `gitcommit` so the run guard (step 5) and the branch verbs (step 6) depend on it without a cycle. The registered-plan slug set is a **parameter**, never read from `locator` here — that read is the caller's job (see Deferred).

### Tier enum and result dataclasses

- **`class Tier(IntEnum)`** with `AD_HOC_OWNED = 1`, `CONVENTION_OWNED = 2`, `ORPHAN_PATTERN = 3`, `UNOWNED = 4`. Use `IntEnum` (not the codebase's `(str, Enum)` config-vocab pattern in `plan_tool/schema.py:PlanStatus`) because the tiers are an ordered severity ladder — Tier 1 strictest, Tier 4 most permissive — and integer ordering makes the guard's "block at ≤ Tier 2" predicate natural. Self-descriptive member names so the guard reads without a glossary.
- **`OWNER_AD_HOC = "ad-hoc"` / `OWNER_CONVENTION = "convention"`** — string constants naming the ownership kind a `BranchOwner` carries.
- **`@dataclass(frozen=True) class BranchOwner`** with `slug: str` and `kind: str` (one of the two `OWNER_*` constants). Returned by `branch_owner` to say *who* owns B and *how*; `None` means no Tier-1/Tier-2 owner.
- **`@dataclass(frozen=True) class BranchClassification`** with `tier: Tier`, `owner: str | None`, and `is_owned_by_plan: bool`. Returned by `classify_branch`. `owner` is the owning slug for Tier 1/2, `None` for Tier 3/4. `is_owned_by_plan` is `owner == plan_slug` (always `False` for Tier 3/4) — the single field the guard reads to decide block-unless-mine vs warn vs nudge.

### Lookup 1 — `expected_branch(repo_root: Path, slug: str, prefixes: Sequence[str]) -> str`

- **Override-else-derive.** Return the ad-hoc override if one exists, else the canonical derived name:
  - `override = get_binding(repo_root, slug)` (step 3). `get_binding` already returns the stripped value or `None`.
  - If `override` is truthy → return `override`; else return `derive_branch(slug, prefixes)` (step 1's primary-prefix derivation, `prefixes[0] + slug`).
- **Take `prefixes` as a parameter** (the caller computes `project_config.branch_prefixes(repo_root)` once) — mirrors step 1's pure-derivation convention so this stays testable with a literal list.
- **This is the guard's "where should P run?"** — used by step 5's Tier-4 nudge ("your expected branch is elsewhere — switch?") and by `--switch-branch`.

### Lookup 2 — `branch_owner(repo_root: Path, branch: str, registered_slugs: Collection[str], prefixes: Sequence[str]) -> BranchOwner | None`

- **Reverse-binding-else-convention-owner, in that order — this is the ad-hoc-beats-convention precedence.**
  1. `rev = reverse_binding(repo_root, branch)` (step 3). If `rev is not None` → return `BranchOwner(slug=rev, kind=OWNER_AD_HOC)`. **An ad-hoc owner need not be locally registered** — the explicit binding is itself the strongest ownership signal (plan "Architecture": "most intentional signal").
  2. Else `co = convention_owner(branch, registered_slugs, prefixes)`. If `co is not None` **and `co` is not ad-hoc-bound to a different branch** — i.e. `get_binding(repo_root, co)` is `None` or equals `branch` — → return `BranchOwner(slug=co, kind=OWNER_CONVENTION)`.
  3. **Forfeit-when-bound-elsewhere:** when `co is not None` but `get_binding(repo_root, co)` is set to some branch ≠ `branch`, **drop the convention result** and fall through to `None` — a plan ad-hoc-bound to a different branch forfeits the convention claim on its derived name (plan "Architecture"). `branch_owner` (not the pure `convention_owner`) applies this because only `branch_owner` has `repo_root` to call `get_binding`. Concretely: after a `create`-collision disambiguation binds P to `plan/<slug>-2`, `branch_owner(plan/<slug>)` returns `None` rather than `BranchOwner(P, OWNER_CONVENTION)`, so a developer on the foreign `plan/<slug>` who runs P classifies as Tier-3 (orphan-pattern), not Tier-2 P-owned; likewise an `attach-branch P JIRA-1` override leaves `plan/P` reading as Tier-3, not Tier-2 P-owned.
  4. Else return `None` (no Tier-1/Tier-2 owner; the Tier-3-vs-Tier-4 distinction is the classifier's, not this lookup's).
- **I/O is confined to the two lookups (`expected_branch`/`branch_owner`); `classify_branch`, `convention_owner`, `matches_convention_pattern` are pure.** Keeping the `reverse_binding` read here (not in `classify_branch`) is what lets the classifier stay pure.

### Pure helper — `convention_owner(branch: str, registered_slugs: Collection[str], prefixes: Sequence[str]) -> str | None`

- **Return the locally-registered slug whose convention name set contains `branch`, else `None` — this encodes the registered-locally condition.**
  - Iterate `sorted(registered_slugs)` (deterministic); for each `slug`, if `branch in convention_names(slug, prefixes)` → return `slug`.
- **Duplicate-slug case — assumed manifest-scoped slug uniqueness, with a deterministic tie-break as the failsafe.** A slug is the plan filename stem (`locator.py:slug_from_filename`) and the manifest is a list of paths across arbitrary directories, so two registered plans in different dirs *can* share a slug and derive to the same `<prefix><slug>` — the Architecture's injectivity premise holds only under manifest-scoped slug uniqueness, which `plan-tool` does not currently enforce. `convention_owner` takes `registered_slugs` as a de-duplicated set of slug strings, so colliding plans collapse to one entry and the lookup returns that single slug; the `sorted(...)` first-match scan makes the result deterministic even if a caller passes a non-deduped collection, so two plans deriving to `B` never yield a non-deterministic or raising owner. Resolving the returned slug back to a specific plan path (and surfacing a genuine duplicate-slug manifest as a pathology) is the step-5 caller's concern, not this pure layer's.
- **Reuse step 1's `convention_names(slug, prefixes)` as the single match rule** rather than re-implementing prefix-stripping — `convention_names` already produces `[p + slug for p in prefixes]`, so a dev who used a secondary configured prefix (`bugfix/<slug>`) is still recognized, and the match rule lives in exactly one place.
- **A slug not in `registered_slugs` is never returned** — that is precisely the Tier-2 "locally-registered plan Q" gate; an orphan pattern-match falls through to `None` → Tier 3 in the classifier.
- **`convention_owner` stays pure (no `repo_root`, no `get_binding`).** The forfeit-when-bound-elsewhere check is *not* applied here — it lives in `branch_owner`, which has `repo_root`. `convention_owner` reports the structural name match; `branch_owner` is what demotes a match whose slug is bound to a different branch.

### Pure helper — `matches_convention_pattern(branch: str, prefixes: Sequence[str]) -> bool`

- **Return `True` when `branch` has a configured prefix with a non-empty tail** — `any(branch.startswith(p) and len(branch) > len(p) for p in prefixes)`. Distinguishes Tier 3 (looks like a convention branch but nobody local owns it) from Tier 4 (matches no pattern at all). The non-empty-tail check stops a bare prefix string from counting as a pattern match.

### Pure classifier — `classify_branch(branch: str, plan_slug: str, owner: BranchOwner | None, prefixes: Sequence[str]) -> BranchClassification`

- **Pure: takes the `owner` from `branch_owner` as data and performs zero I/O.** The run guard composes `owner = branch_owner(...)` then `classify_branch(..., owner=owner, ...)`; tests construct `BranchOwner(...)` by hand to exercise every tier without a repo.
- **Branch order encodes the tier ladder:**
  - `owner is not None` and `owner.kind == OWNER_AD_HOC` → `Tier.AD_HOC_OWNED`, `owner=owner.slug`, `is_owned_by_plan = owner.slug == plan_slug`.
  - `owner is not None` and `owner.kind == OWNER_CONVENTION` → `Tier.CONVENTION_OWNED`, same owner/ownership fields.
  - `owner is None` and `matches_convention_pattern(branch, prefixes)` → `Tier.ORPHAN_PATTERN`, `owner=None`, `is_owned_by_plan=False`.
  - else → `Tier.UNOWNED`, `owner=None`, `is_owned_by_plan=False`.
- **The both-claimed edge is resolved upstream in `branch_owner`** (reverse-binding wins), so by the time `classify_branch` sees an `OWNER_AD_HOC` owner the convention claim is already shadowed — the classifier never has to break the tie itself. Surfacing the shadowed convention conflict to the user (plan acceptance criterion) is the guard's message concern, not this layer's.

### Foundational logic and shared locations

- **Foundational logic:** "grade a current branch against a plan by the strongest ownership signal, ad-hoc over convention, convention only when locally registered." Grepping `plan_tool/` and `tests/` for `branch_owner` / `expected_branch` / `classify_branch` / `convention_owner` returns nothing — no existing duplicate of this rule.
- **The branch-derivation match rule** lives in `plan_tool/project_config.py:convention_names` / `derive_branch` (step 1); this module **consumes** it and adds no second copy of prefix logic beyond the thin `matches_convention_pattern` shape check.
- **The override store** lives in `plan_tool/branch_binding.py:get_binding` / `reverse_binding` (step 3); this module consumes it and re-derives nothing about git-config storage.
- **No consolidation owed** — this is a clean new layer composing two existing leaves; there is no parallel block to fold in.

## Tests

All cases land in `tests/test_branch_ownership.py` (unit, unmarked, fast). The two lookups (`expected_branch` / `branch_owner`) touch git config through step 3, so add a module-local `_init_git_repo(root)` helper that runs `git init -q` + `git config user.email/user.name` (copied from `tests/cli/test_gitcommit.py:_init_git_repo`; the `tests/conftest.py` real-backend gate blocks only the registered *claude*/*codex* binaries, not `git`). `classify_branch` / `convention_owner` / `matches_convention_pattern` are pure — drive them with literal lists and hand-built `BranchOwner` objects, no repo. Use a fixed prefix list `["plan/", "bugfix/"]` to exercise the multi-prefix match.

### `expected_branch`
- `test_expected_branch_derives_when_no_override` — no binding → `derive_branch` result (`plan/<slug>`).
- `test_expected_branch_returns_override` — after `branch_binding.set_binding(repo_root, slug, "JIRA-1")`, `expected_branch` returns `"JIRA-1"`, not the derived name.

### `branch_owner` (ad-hoc-beats-convention + registered-locally)
- `test_branch_owner_ad_hoc` — branch ad-hoc-bound to a slug → `BranchOwner(slug, OWNER_AD_HOC)`, even when the slug is **not** in `registered_slugs`.
- `test_branch_owner_convention_registered` — `plan/<slug>` of a slug present in `registered_slugs`, no binding → `BranchOwner(slug, OWNER_CONVENTION)`.
- `test_branch_owner_convention_secondary_prefix` — `bugfix/<slug>` of a registered slug under the `["plan/","bugfix/"]` list → convention owner (secondary prefix still recognized).
- `test_branch_owner_unregistered_convention_is_none` — `plan/<slug>` whose slug is **not** registered → `None` (registered-locally gate).
- `test_branch_owner_ad_hoc_beats_convention` — branch is both ad-hoc-bound to `Q` and the convention name of registered `R` → returns `Q` with `OWNER_AD_HOC` (precedence).
- `test_branch_owner_convention_forfeited_when_bound_elsewhere` — registered slug `P` whose `plan/<slug>` matches but which is ad-hoc-bound (`set_binding`) to a *different* branch → `branch_owner(plan/<slug>)` returns `None` (forfeit → Tier-3), not `BranchOwner(P, OWNER_CONVENTION)`.
- `test_branch_owner_no_owner` — unbound, non-convention branch → `None`.

### `convention_owner` (pure)
- `test_convention_owner_matches_registered` — returns the registered slug for its `plan/<slug>` / `bugfix/<slug>` name.
- `test_convention_owner_skips_unregistered` — a pattern-matching name whose slug isn't registered → `None`.
- `test_convention_owner_deterministic` — two registered slugs that would both map (defensive) → sorted-first slug.

### `classify_branch` (pure, all four tiers + ownership)
- `test_classify_tier1_ad_hoc_other_plan` — `BranchOwner(Q, OWNER_AD_HOC)`, `plan_slug != Q` → `Tier.AD_HOC_OWNED`, `is_owned_by_plan=False`.
- `test_classify_tier1_ad_hoc_same_plan` — owner slug == `plan_slug` → `Tier.AD_HOC_OWNED`, `is_owned_by_plan=True`.
- `test_classify_tier2_convention` — `BranchOwner(Q, OWNER_CONVENTION)` → `Tier.CONVENTION_OWNED`, ownership reflects `Q == plan_slug`.
- `test_classify_tier3_orphan_pattern` — `owner=None`, branch starts with a configured prefix → `Tier.ORPHAN_PATTERN`, `owner=None`, `is_owned_by_plan=False`.
- `test_classify_tier4_unowned` — `owner=None`, branch matches no prefix (e.g. `main`) → `Tier.UNOWNED`.

### `matches_convention_pattern` (pure)
- `test_matches_pattern_true_with_tail` — `plan/foo` with `["plan/"]` → `True`.
- `test_matches_pattern_false_bare_prefix` — `plan/` (empty tail) → `False`; `main` → `False`.

### Test-creation order (feature step)
- **This is a feature step — new behavior.** Write each test above alongside the symbol it covers in `tests/test_branch_ownership.py`.
- **Green-before-done gate:** every new test must pass (`uv run pytest tests/test_branch_ownership.py -q`) before this step is complete. This step touches no existing module, so the full suite (`uv run pytest -m "not integration" tests/ -q`) must stay green unchanged.

## Acceptance criteria

- `plan_tool/branch_ownership.py` imports only `plan_tool.project_config` and `plan_tool.branch_binding` from the package — nothing from `create` / `launcher` / `locator` / `cli.*` / `gitcommit` (verifiable by inspection).
- `expected_branch` returns the ad-hoc override when one is set, else `derive_branch(slug, prefixes)`.
- `branch_owner` returns an `OWNER_AD_HOC` owner when `reverse_binding` matches (regardless of registration), an `OWNER_CONVENTION` owner only when the convention-owning slug is in `registered_slugs` **and is not itself ad-hoc-bound to a different branch** (a plan bound elsewhere forfeits its convention claim → `None`/Tier-3), and `None` otherwise.
- A branch both ad-hoc-bound to `Q` and a convention name of registered `R` resolves to `Q` (ad-hoc-beats-convention).
- `classify_branch` returns `Tier.AD_HOC_OWNED` / `Tier.CONVENTION_OWNED` / `Tier.ORPHAN_PATTERN` / `Tier.UNOWNED` exactly per the four-way branch above, with `is_owned_by_plan == (owner == plan_slug)` and `False` for the no-owner tiers.
- `convention_owner` and `matches_convention_pattern` perform no I/O and are correct against literal prefix/slug lists.
- Every test in `tests/test_branch_ownership.py` passes; the full non-integration suite stays green.

## References

- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — The ref-name rules every `<prefix><slug>` derived/matched name must satisfy; enforced upstream in step 1's `_is_valid_ref`, relied on here as a precondition.
- [Git - git-config Documentation](https://git-scm.com/docs/git-config) — `--local` storage semantics for the `plan-tool.binding.<slug>` override that `branch_owner` / `expected_branch` read via step 3's `get_binding` / `reverse_binding`.

## Deferred

- **Sourcing `registered_slugs` from the manifest** — `branch_owner` / `convention_owner` take the registered-slug set as a parameter; the step-5 run guard builds it from `plan_tool/locator.py:load_manifest_plan_paths` + `slug_from_filename` (or `PlanEntry.slug`) and passes it in. Reading `locator` here would invert the leaf direction and risk a cycle.
- **Reading the current branch / repo state** — `classify_branch` takes `branch` as a string; the actual `gitcommit.current_branch` read, the non-git / detached-HEAD no-op, and the `branch_prefixes(repo_root)` read all happen in the step-5 guard, not here.
- **Block / warn / nudge UX and `--switch-branch`** — this module only classifies; mapping Tier 1–2 → block-unless-mine, Tier 3 → warn+proceed, Tier 4 → nudge/switch, and surfacing the shadowed-convention conflict message are the step-5 run guard's concern.
- **Create-time collision disambiguation** (`plan/<slug>-2` from default) — step 7's `cmd_create` work; it consumes `expected_branch` / `branch_owner` but owns the first-free-suffix search.
