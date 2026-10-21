> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add `--reuse` / `--no-reuse` / `--reuse-id STEM` to `reconcile-plan`, `reconcile-code`, and `detail --reconcile`

## Summary

- **Adds a tri-state reuse-flag family** (`--reuse` / `--no-reuse` as one `BooleanOptionalAction` with `default=None`, plus `--reuse-id STEM`) to the three reconcile-family commands so they match `completeness-audit`'s `--reuse-audit` family flag-for-flag, behavior-for-behavior.
- **Argparse sites (declared footprint):** `plan_tool/cli/run_cmd.py:register` (the `p_run` and `p_reconcile_code` subparsers), `plan_tool/cli/authoring.py:register` (the `p_detail` subparser), `plan_tool/cli/review_cmd.py:register` (the `p_review` / `reconcile-plan` subparser).
- **Consumption sites:** `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` (the `review`-kind path, in footprint) **and** the shared reconcile core `plan_tool/cli/reconcile.py:_prompt_reuse_saved` (drives both `detail-reconcile` and `run-reconcile` wrappers) — the latter is a **required footprint addition** because the captured rule is that any behavior change for both reconcile reuse prompts belongs in the core.
- **Load-bearing decision:** `--reuse` is `BooleanOptionalAction(default=None, dest="reuse")` — `None`=unset (prompt / auto-decide), `True`=reuse-when-fresh, `False`=never — never `default=False`, which would collapse "unset" and "`--no-reuse`" into one state and erase the interactive/auto path the flag exists for.
- **On green:** `--no-reuse` never looks up a sidecar; `--reuse` reuses a fresh save (no prompt) and warns-then-re-audits a stale one; unset prompts on a TTY and auto-accepts a fresh save under `--yes`/non-TTY; `--reuse-id STEM` pins the lookup and, when it matches nothing, prints a note and falls back to a fresh audit (never a non-zero exit).

## Table of Contents

- [Why](#why) — what the missing flags block today
- [Files (creates vs edits)](#files-creates-vs-edits) — the three argparse modules, the reconcile core, the test files
- [Implementation](#implementation) — the flag declarations, the tri-state core consumption, the `--reuse-id` pin
- [Tests](#tests) — parse-contract + consumption cases per command
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author-with-implementation, green-before-done
- [Acceptance criteria](#acceptance-criteria) — observable flag behavior
- [References](#references) — `BooleanOptionalAction`, the completeness template, the resolver
- [Deferred](#deferred) — the flag/help consolidation and the `reconcile-plan-walk` surface

## Why

- **The reconcile family has no operator-facing reuse switch.** Steps 1–4 made every reconcile and plan-wide-review sidecar carry `plan_fingerprint` + `code_fingerprint` (steps 1–2), added `resolve_reusable_reconcile` to verdict them (step 3), and gated the reuse prompts on fingerprint freshness (step 4). But the only way to drive reuse today is the interactive prompt (`[y/N]`, default no) plus the `--yes` auto-accept — there is no `--reuse` / `--no-reuse` / `--reuse-id` to script it, and no parity with `completeness-audit`, which already ships `--reuse-audit` / `--no-reuse-audit` / `--reuse-audit-id` (`plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse`).
- **`--reuse-id` is the only way to pin a specific save.** Without it, a user with several saved reconciles for a step can only reuse the newest. The completeness family already has this; the reconcile family stores the data and lacks the selector.
- **Fixing it now closes the feature.** Step 4 is the last machinery piece; step 5 exposes it on the CLI surface so the reconcile-reuse feature is invocable and scriptable end-to-end.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/run_cmd.py` — in `register`, add `--reuse`/`--no-reuse` + `--reuse-id` to **both** `p_run` (the `run` subparser, which carries `--reconcile`) and `p_reconcile_code` (the canonical `reconcile-code` subparser). Argparse only; consumption is in the reconcile core.
  - `plan_tool/cli/authoring.py` — in `register`, add the same three flags to `p_detail` (the `detail` subparser, which carries `--reconcile`). Argparse only; consumption is in the reconcile core.
  - `plan_tool/cli/review_cmd.py` — in `register`, add the three flags to `p_review` (the `reconcile-plan` subparser). **And** widen `_prompt_reuse_saved_review` to consume them (the `review`-kind path has no `resolve_reusable_*` sibling, so it owns its own tri-state branch — see [domain-shape] lesson on the absent `resolve_reusable_review`).
  - `tests/cli/test_review_cmds.py` — parse-contract gates for the `reconcile-plan` flags + `_prompt_reuse_saved_review` tri-state cases driven through `main([...])`.
  - `tests/cli/test_run_cmd.py` — parse-contract gates for the `run` / `reconcile-code` flags.

- **Required footprint addition (outside declared `files:`, noted explicitly):**
  - `plan_tool/cli/reconcile.py` — widen `_prompt_reuse_saved` (the parametrized core both `_prompt_reuse_saved_detail_reconcile` and `_prompt_reuse_saved_run_reconcile` one-line-delegate to) to consume `reuse` / `reuse_id`. **Required:** the captured rule is that any gating/verdict/behavior change for both reconcile reuse prompts lands in the core, and the two named wrappers inherit it untouched. Editing the wrappers or duplicating the logic per-command would violate that single-source rule.
  - `tests/cli/test_authoring_cmds.py` (out of declared `files:`) — the natural home for the `detail --reconcile` flag parse tests. Driven via `build_parser().parse_args([...])`.

## Implementation

### Flag declarations (all three argparse sites — identical shape)

- **`--reuse` / `--no-reuse`** — one `argparse.BooleanOptionalAction`, `default=None`, `dest="reuse"`. Mirror `plan_tool/cli/completeness_cmd.py`'s `--reuse-audit` declaration exactly, minus the `--audit-samples` cross-reference (reconcile has no sampling axis).
  - `None` (unset) = prompt interactively, auto-accept under `--yes` / non-TTY.
  - `True` (`--reuse`) = reuse the saved findings when the save is fresh; warn-then-re-audit when stale.
  - `False` (`--no-reuse`) = never look up a save; always run fresh.
- **`--reuse-id STEM`** — `default=None`, `dest="reuse_id"`, `metavar="STEM"`. Mirror `--reuse-audit-id`: pin reuse to a saved sidecar by filename stem (bare `<ts>` or full `<ts>-<kind>` form); an unresolved id prints a note and falls back to a fresh audit.
- **`default=None` is load-bearing** for `--reuse` — a `default=False` makes "unset" indistinguishable from `--no-reuse`, collapsing the tri-state to a bool and deleting the prompt/auto path. Pin it with a parse test asserting `args.reuse is None` on the unset case (see [detail-authoring] lesson on tri-state `BooleanOptionalAction(default=None)`).
- **`dest` collision check:** `reuse` / `reuse_id` are unused elsewhere; the completeness family owns `reuse_audit` / `reuse_audit_id`. No clash.
- **Help-golden:** these flags attach to **subcommand** parsers, not `make_base_parser`, so the top-level `plan-tool --help` golden at `tests/cli/package_surface_help.golden.txt` (checked by `tests/cli/test_package_surface.py::test_help_matches_golden`) is **not** perturbed — no `UPDATE_CLI_GOLDEN` regen needed. Confirm by parsing the golden's subcommand list, which names commands, not their flags.

### `plan_tool/cli/reconcile.py:_prompt_reuse_saved` (the shared reconcile core)

- **Foundational logic this step adds:** map `(reuse flag, reuse_id, freshness verdict, TTY/--yes)` → reuse-saved-path-or-`None`, the reconcile analog of `completeness_cmd.py:_resolve_audit_reuse`.
- **Insert a hard opt-out first:** when `getattr(args, "reuse", None) is False`, return `None` before any lookup (`--no-reuse` never touches a sidecar). Mirrors `_resolve_audit_reuse` step 1.
- **Thread `reuse_id` into the lookup.** Pass `getattr(args, "reuse_id", None)` to the save selection so `--reuse-id STEM` pins which sidecar is offered. Two integration points already exist:
  - `_find_saved_for_step(kind, plan_slug, repo_root, step_id=, plan_path=)` currently returns the newest of `kind`. Filter its result (or its candidate scan) by stem when `reuse_id` is set.
  - Keep step 4's freshness pin coherent: step 4 calls `resolve_reusable_reconcile(..., review_id=saved_path.stem)` pinned to the **located** save so the verdict matches the offered save (see [cross-step] lesson on pinning the resolver to the already-selected artifact). When `reuse_id` selects a different save, that same `saved_path.stem` pin still flows through — the user's id changes *which* save is located, step 4's internal pin keeps the verdict on *that* one.
- **Unresolvable `--reuse-id` warns-and-proceeds.** When `reuse_id` is set and no save matches, emit one `error(...)` line — `f"no saved {kind.noun} matched --reuse-id {reuse_id!r}; running a fresh {kind.noun}"` — and return `None` (fresh). Never raise, never non-zero. Mirror `_resolve_audit_reuse` step 3.
- **Replace the current non-TTY early gate** (`if not yes and not sys.stdin.isatty(): return None`) with a freshness-aware decision so the unset default auto-accepts a *fresh* save on non-TTY (parity with `_resolve_audit_reuse`'s `non_interactive` branch), instead of unconditionally declining. The `--no-walk`/`--no-save` suppression (`kind.honor_no_walk_no_save`) and `--dry-run` suppression stay.
- **Fresh-save dispatch by flag** (after step 4's freshness gate confirms `fresh`):
  - `reuse is True` → accept (return the saved path) with no prompt — explicit `--reuse` wins.
  - `reuse is None` → auto-accept under `getattr(args, "yes", False)` **or** non-TTY (`not sys.stdin.isatty()`); otherwise the interactive `_ask_reuse_saved` prompt.
- **Stale-save dispatch** (step 4 already warns + declines): `--reuse` over a stale save still re-audits — keep the gate **before** the `--yes`/`--reuse` accept (a force flag accepts only a still-fresh result; see [cross-step] lesson on placing the gate before the force-accept fast path). The stale-warning UX (`_warn_reuse_code_drift` + plan-stale note) is step 4's; this step does not re-emit it.

### `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` (the `review`-kind path)

- **Owns its own tri-state branch** — the plan-wide `review` kind is not a `_RECONCILE_KINDS` entry and has no `resolve_reusable_review` sibling (see [domain-shape] lesson), so it recomputes freshness inline (step 4) and gates the flags inline here.
- **Add the same three branches:** `reuse is False` → return `None` before the `list_saved_reviews` scan; `reuse_id` set → match `most_recent` by stem (after the existing `"-reconcile" not in p.name` filter) and, on no match, `error(...)` + `None`; fresh save → `reuse is True` accepts, `reuse is None` auto-accepts under `--yes`/non-TTY else prompts.
- **Replace the current non-TTY early gate here too** with the same freshness/flag-aware decision the core gets (see the core subsection above) — otherwise `reconcile-plan` returns `None` on every non-TTY run regardless of `--reuse`, breaking this command's acceptance criteria and parity claim.
- **Read the flags via `getattr(args, "reuse", None)` / `getattr(args, "reuse_id", None)`** so the helper stays callable from the `cmd_review` namespace without a hard attribute dependency (matches the existing `getattr(args, "yes", False)` posture).

### Dispatch is unchanged

- `cmd_run` (`run --reconcile`) and `cmd_reconcile_code` both forward to `reconcile.py:_cmd_run_reconcile`, which calls `_prompt_reuse_saved_run_reconcile`; that one-line-delegates to the widened core. `_cmd_detail_reconcile` (reached from `authoring.py:cmd_detail` via `app._cmd_detail_reconcile`) calls `_prompt_reuse_saved_detail_reconcile`. No handler-body edits — the flags ride `args` straight into the core via `getattr`.

## Tests

### `tests/cli/test_run_cmd.py` — parse contract (no claude call)

- `test_run_reuse_default_is_none` — `build_parser().parse_args(["run","demo","--reconcile"])` yields `args.reuse is None` and `args.reuse_id is None`.
- `test_run_reuse_and_no_reuse_parse` — `--reuse` → `args.reuse is True`; `--no-reuse` → `args.reuse is False`.
- `test_run_reuse_id_parses_stem` — `--reuse-id 20260612-120000-run-reconcile` → `args.reuse_id == "20260612-120000-run-reconcile"`.
- `test_reconcile_code_reuse_flags_parse` — same three assertions on the `reconcile-code` subparser (separate parser; must declare the flags independently).

### `tests/cli/test_review_cmds.py` — parse contract + `_prompt_reuse_saved_review` consumption

- `test_reconcile_plan_reuse_default_is_none` — `parse_args(["reconcile-plan","demo"])` → `args.reuse is None`, `args.reuse_id is None`.
- `test_reconcile_plan_reuse_flags_parse` — `--reuse`/`--no-reuse`/`--reuse-id STEM` map to `True`/`False`/the stem.
- `test_review_no_reuse_skips_lookup` — with `reuse=False`, `_prompt_reuse_saved_review` returns `None` without scanning saves (patch `list_saved_reviews` to assert it is **not** called, or assert via a recorded spy).
- `test_review_reuse_id_miss_warns_runs_fresh` — `reuse_id` matching no save returns `None` and writes the `no saved review matched --reuse-id` line to stderr.
- `test_review_reuse_true_accepts_fresh_without_prompt` — fresh seed + `reuse=True` returns the saved path with `builtins.input` patched to raise (proving no prompt fired).

### `tests/cli/test_authoring_cmds.py` (out-of-footprint addition) — detail parse contract

- `test_detail_reuse_default_is_none` — `parse_args(["detail","demo","--reconcile","--step","1"])` → `args.reuse is None`, `args.reuse_id is None`.
- `test_detail_reuse_flags_parse` — `--reuse`/`--no-reuse`/`--reuse-id STEM` parse as expected on the `detail` subparser.

### Reconcile-core consumption coverage (pointer)

- The `_prompt_reuse_saved` tri-state branches (no-reuse opt-out, `reuse_id` pin/miss, fresh-accept-by-flag, non-TTY auto-accept) are unit-tested in `tests/cli/test_reconcile_engine.py` (the reconcile-engine home, alongside step 3's `resolve_reusable_reconcile` and step 4's gate tests). Drive the **force** values (`reuse=True`/`False`), not the unset/TTY-dependent default — under pytest stdin is non-TTY, so the unset path takes the auto-accept branch and an unset-default test silently tests the capture environment (see [detail-authoring] lesson on tri-state integration tests forcing the non-interactive branch). The interactive `[y/N]`/`[Y/n]` prompt stays a unit test with `input_fn`/`builtins.input` patched.
- **Update the two pre-existing non-TTY suppress tests** that the non-TTY early-gate replacement flips: `tests/cli/test_reconcile_engine.py::TestPromptReuseDetailReconcile::test_non_tty_without_yes_suppresses` and `::TestPromptReuseRunReconcile::test_non_tty_without_yes_suppresses` (lines 363, 406) seed a save and assert `result is None` under pytest's non-TTY stdin with `yes=False` — the old early gate's behavior. Replacing that gate with the freshness-aware decision auto-accepts a *fresh* save on non-TTY, so each test's seeded-fresh save now returns the saved path. Reseed each test's save to **stale** (mutate the plan or an in-scope code file after the seed so the fingerprint mismatches) to preserve the `result is None` suppression assertion, and add a companion case asserting a *fresh* seed now auto-accepts (returns the saved path) on non-TTY (see [cross-step] lesson — gating an existing reuse path turns pre-existing suppress tests into ones that must be reseeded/updated, not left untouched). Both reseeded tests are part of the green-before-done gate below.

### Test-creation order (feature step)

- **Author each parse-contract test with the flag declaration** it pins — add `--reuse`/`--no-reuse`/`--reuse-id` to one subparser, then its `default-is-None` + parse tests, per command.
- **Author the consumption tests with the core/`_prompt_reuse_saved_review` edit** — the no-reuse opt-out, the `reuse_id` miss-warns-fresh, and the fresh-accept-by-flag cases land with the branch they exercise.
- **Green-before-done gate:** every new parse + consumption test, plus the pre-existing `_prompt_reuse_saved` / `_prompt_reuse_saved_review` reuse tests (which must stay green — the new `reuse=None` default must reproduce today's prompt/auto-accept behavior for callers that pass no flag), is green before this step is finished. The **exception** is the two `test_non_tty_without_yes_suppresses` tests (`TestPromptReuseDetailReconcile`, `TestPromptReuseRunReconcile`), which the non-TTY early-gate replacement intentionally breaks and which this step reseeds-to-stale + extends with a fresh-auto-accept case per the consumption-coverage pointer above — they are updated, not held green untouched. Run `uv run pytest -m "not integration" tests/cli/ tests/test_reconcile_engine.py -q` for the fast loop.

## Acceptance criteria

- `build_parser().parse_args([...])` yields `args.reuse is None` and `args.reuse_id is None` by default for `run`, `reconcile-code`, `detail`, and `reconcile-plan`; `--reuse`→`True`, `--no-reuse`→`False`, `--reuse-id STEM`→the stem string.
- `reuse is False` short-circuits `_prompt_reuse_saved` and `_prompt_reuse_saved_review` to `None` before any save lookup (no `list_saved_reviews` / `_find_saved_for_step` call).
- `reuse is True` over a **fresh** save returns the saved path with no `input(...)` call; over a **stale** save returns `None` and re-audits (step 4's stale-warning still emits).
- An unresolvable `--reuse-id STEM` writes one `no saved … matched --reuse-id` line to stderr and returns `None` (fresh), with the command exiting `0` (failure-to-complete convention — never non-zero on a reuse miss).
- The unset default (`reuse is None`) auto-accepts a fresh save under `--yes` / non-TTY and otherwise prompts; on a TTY the no-flag prompt path is unchanged from pre-step (the non-TTY no-`--yes` path now auto-accepts a fresh save instead of declining).
- The top-level `plan-tool --help` golden (`tests/cli/package_surface_help.golden.txt`) is unchanged (flags are on subcommand parsers).

## References

- [argparse — BooleanOptionalAction](https://docs.python.org/3/library/argparse.html#argparse.BooleanOptionalAction) — the tri-state `--reuse`/`--no-reuse` toggle with `default=None` and a paired `--reuse-id STEM` value flag.
- `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` (in-repo) — the structural template: the `(flag, freshness, TTY)` → reuse-or-fresh decision table, the hard `--no-reuse-audit` opt-out, and the unresolved-`--reuse-audit-id` warn-and-proceed.
- `plan_tool/cli/completeness_cmd.py` `--reuse-audit` / `--reuse-audit-id` `add_argument` calls (in-repo) — the exact `BooleanOptionalAction(default=None)` + `metavar="STEM"` declarations to mirror.
- `plan_tool/cli/reconcile.py:resolve_reusable_reconcile` (added by step 3, not yet at HEAD) — the freshness verdict the core consumes; pinned by the located sidecar's stem.

## Deferred

- **Consolidating `--reuse` help text into a shared parent parser** — the flag triplet is declared four times (p_run, p_reconcile_code, p_detail, p_review). A shared `reuse_parent` argparse parent would DRY it, but the four parsers differ in their `parents=` lists and `kind.noun` wording; a parent-parser refactor is a separate consolidation step `detail` cannot mint. Left as inline duplication for now.
- **`reconcile-plan-walk` / `reconcile-code` walk-only verbs** — those replay an already-saved sidecar (no claude call) and already take `--id`; they are not reuse-of-a-fresh-audit and stay out of this flag family.
- **A unified `_resolve_reconcile_reuse` helper across the review-kind and reconcile-kind paths** — `_prompt_reuse_saved_review` (inline, review kind) and `_prompt_reuse_saved` (resolver-backed, reconcile kinds) carry parallel tri-state branches but live in different import tiers; merging them needs a non-leaf common home and is a refactor for a later step.
