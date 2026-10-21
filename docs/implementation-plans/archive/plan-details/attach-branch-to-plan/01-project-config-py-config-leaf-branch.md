> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `project_config.py`: branch-awareness flag, prefixes, and slug→branch derivation

## Summary

Creates `plan_tool/project_config.py`, a stdlib-only leaf that answers three questions any branch-aware code path needs without importing `create`/`launcher`/`locator`:

- *is branch-awareness on?* (`branch_awareness_enabled`)
- *what branch prefixes are configured?* (`branch_prefixes`)
- *what branch(es) correspond to a slug?* (`derive_branch` / `convention_names`)

The load-bearing decision is **per-level tolerance**: each config level (env → project → user) is an independent fallback, so a malformed user file never crashes an otherwise-fine project — the reader swallows malformed levels and returns a "level unset" sentinel rather than raising (diverging from the single-source `backend_config.py` / `jira_config.py` posture). On green:

- `branch_awareness_enabled(repo_root)` returns `False` for every repo with no config (the off-by-default guarantee)
- `branch_prefixes` returns `["plan/"]` with a stderr warning on a bad list
- `derive_branch`/`convention_names` are pure functions over a prefix list

Adds `tests/test_project_config.py`.

## Table of Contents

- [Why](#why) — what the config leaf unblocks and why it must be a pure leaf
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — symbols, precedence chains, and the tolerant-per-level decision
- [Tests](#tests) — per-behavior unit cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git ref-format rules and stdlib config patterns
- [Deferred](#deferred) — work explicitly left to later steps

## Why

- **Every downstream branch step needs a single, cycle-free place to ask "is it on?" and "what's the branch for this slug?".** The run guard (step 5), `branch_ownership.py` (step 4), `attach-branch`/`detach-branch` (step 6), and the create-collision warning (step 7) all gate on `branch_awareness_enabled` and derive names from a slug. Without a leaf, that logic would scatter or force a cycle through `locator`/`create`.
- **The off-by-default guarantee is load-bearing.** With no config the tool must behave byte-for-byte as today (plan "Risks → Flag-check leakage"). A reader that defaults to `False` and never raises is what lets every caller check the flag *first* and short-circuit before deriving or reading any branch.
- **A multi-level reader must not let one bad fallback level poison the others.** A broken `~/.plan-tool/config.json` must not crash `run`/`create` in a repo whose own config is fine — hence per-level tolerance, unlike the single-authoritative-source config readers that raise.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/project_config.py` — the config leaf: path helpers, the tolerant per-level reader, `branch_awareness_enabled`, `branch_prefixes`, `derive_branch`, `convention_names`, plus the pure ref-validity predicate and `ProjectConfigError`.
  - `tests/test_project_config.py` — unit coverage for precedence, malformed-tolerance, env coercion, prefix validation/fallback, derivation, and lazy `Path.home()`.

- **Existing files (edits only):** none. `depends_on` is empty; this step adds no call sites.

## Implementation

All work lands in `plan_tool/project_config.py`. Keep it a **stdlib-only leaf** — import only `json`, `os`, `sys`, `pathlib.Path`, and typing. Import **nothing** from `plan_tool.create`/`launcher`/`locator`/`scenario_capture` so any command can depend on it without a cycle (mirrors the leaf contract of `plan_tool/backend_config.py` and `plan_tool/jira_config.py`).

### Module constants

- **`_TRUTHY` / `_FALSY` — copy the literal, do not import.** `plan_tool/scenario_capture.py` defines `_TRUTHY = frozenset({"1", "true", "yes", "on"})`; copy that frozenset verbatim and add `_FALSY = frozenset({"0", "false", "no", "off"})`. `scenario_capture` is an orchestrator-tier module imported by create/detail/authoring; depending on it from a config leaf inverts the dependency direction / risks a cycle — copy the four-element set instead and leave a shared truthy-env helper as a deferred refactor.
- **`DEFAULT_BRANCH_PREFIXES = ("plan/",)`** — the canonical default. Public accessors return a fresh `list` so callers can't mutate the constant.
- **`BRANCH_AWARENESS_ENV = "PLAN_TOOL_BRANCH_AWARENESS"`** — the env override name.
- **`PROJECT_CONFIG_SUBPATH = Path(".plan-tool") / "config.json"`** — repo-relative project config location.

### `ProjectConfigError(Exception)`

- **Define it for symmetry with `BackendConfigError` / `JiraConfigError`, but do not raise it from any resolver in this step.** A future strict config *writer* is its intended raiser. Define-but-unraised documents the tolerant posture explicitly and gives later strict callers a type to catch.

### Path helpers

- **`project_config_path(repo_root: Path) -> Path`** — return `(repo_root / PROJECT_CONFIG_SUBPATH).resolve()`. `repo_root` is a parameter (never call `locator`) to keep the leaf hermetic and testable against a `tmp_path`, exactly as `backend_config.py:default_backends_config_path` takes `repo_root`.
- **`user_config_path() -> Path`** — return `Path.home() / ".plan-tool" / "config.json"` with **`Path.home()` evaluated lazily inside the function body**, never as a module constant. `tests/conftest.py`'s autouse `_isolate_known_roots_cache` redirects `$HOME` and patches `Path.home()` at test time; a module-level capture would freeze the real home at import and break hermetic user-level tests. This mirrors `plan_tool/lessons.py:general_lessons_dir`, which computes `Path.home().joinpath(*GENERAL_LESSONS_REL)` in-body.

### `_read_level(path: Path) -> dict | None` (the tolerant per-level reader)

- **Return the validated `branch_awareness` mapping for one config file, or `None` ("level unset") on any of:** file absent, `json.JSONDecodeError`, top-level value not a `dict`, or `branch_awareness` missing / not a `dict`. **Never raise** — swallow every malformed shape so the remaining levels still resolve.
- **This is the deliberate divergence from `backend_config.load_backend_overrides` / `jira_config.load_jira_config`**, which raise `*ConfigError` because each is the single authoritative parse of one file. Here one broken fallback level among several must not crash a consumer that only needed a lower-priority level — so the sentinel (`None` = "this level unset") is a legitimate domain value, not a swallowed error.
- **Per-key type validation lives in the accessors, not here.** `_read_level` returns the raw block; `branch_awareness_enabled` and `branch_prefixes` each independently validate their own key's type. A level with a malformed `enabled` but a valid `branch_prefixes` therefore contributes its prefixes while its `enabled` falls through — the two keys are independent fallbacks.

### `branch_awareness_enabled(repo_root: Path) -> bool`

- **Resolve env → project → user → `False` (first explicitly set wins):**
  1. **Env (`PLAN_TOOL_BRANCH_AWARENESS`)** — read the raw string, `.strip().lower()`; if in `_TRUTHY` → `True`, if in `_FALSY` → `False`, **otherwise fall through** (unrecognized/empty = "not set"). Env values are always strings, so they need truthy-token coercion.
  2. **Project block** — `_read_level(project_config_path(repo_root))`; if its `enabled` value `isinstance(..., bool)` use it. A JSON `"true"` string or `1` int is malformed config → treated as unset (fall through). **Do not route the typed field through `_TRUTHY`** — that would let `"enabled": "yes"` silently flip behavior.
  3. **User block** — same `isinstance(bool)` check against `_read_level(user_config_path())`.
  4. **Default `False`.**
- **Env affects only `enabled`**, never the prefixes.

### `branch_prefixes(repo_root: Path) -> list[str]`

- **Resolve project → user → default, project-over-user** (no env axis): take the first level whose `branch_awareness.branch_prefixes` is present.
- **Validate the resolved list; on a bad/empty list warn to stderr and return `list(DEFAULT_BRANCH_PREFIXES)` — never crash.** "Bad" = not a `list`, empty, or any element that is not a non-empty `str` or fails `_is_valid_branch_prefix`. Write a one-line diagnostic naming the offending file to `sys.stderr` (e.g. `branch_awareness.branch_prefixes in <path> is invalid; using ['plan/']`).
- **Return a fresh list** (copy of the default or the validated config list).

### `_is_valid_ref(ref: str) -> bool` / `_is_valid_branch_prefix(prefix: str) -> bool` (pure ref-format guard)

- **Implement the `git check-ref-format` rules as a pure Python predicate — do not shell out to git.** This step has no git dependency (`depends_on` empty; the git readers land in step 2 on `plan_tool/cli/gitcommit.py`), and a pure predicate is the only thing that keeps the leaf self-contained and unit-testable without a real repo.
- **`_is_valid_ref(ref)` rejects** (per plan "Risks → Slug → ref validity"): any ASCII control char or space, any of `~ ^ : ? * [ \`, a `..` sequence, an `@{` sequence, a trailing `.lock`, a leading or trailing `/`, and a `//` run. Require at least one `/` so single-component refs aren't produced by a degenerate prefix.
- **`_is_valid_branch_prefix(prefix)`** — `prefix` is a non-empty `str` and `_is_valid_ref(prefix + "probe-slug")` holds (a representative slug token proves `<prefix><slug>` yields a valid ref).

### `derive_branch(slug: str, prefixes: Sequence[str]) -> str` and `convention_names(slug: str, prefixes: Sequence[str]) -> list[str]`

- **Keep both pure: take the prefix list as a parameter, do not re-read config inside.** Callers compute `prefixes = branch_prefixes(repo_root)` once and pass it in — deferring disk reads to the caller keeps these functions filesystem-agnostic and testable by handing a literal list.
- **`derive_branch(slug, prefixes)` → `prefixes[0] + slug`** — the single canonical name from the **primary (first) prefix**; used by `create` (step 7) and the guard's "expected branch" (step 4).
- **`convention_names(slug, prefixes)` → `[p + slug for p in prefixes]`** — the full match set; used by enforcement/matching (step 4) so a dev who used a secondary prefix is still recognized.
- **The slug is trusted as an already-sanitized identifier** (produced by `create`'s slug resolver). These functions concatenate only; ref validity is enforced upstream on the *prefixes* by `branch_prefixes`. Note this trust boundary so a later step doesn't double-sanitize.

### Foundational logic and shared locations

- **Core rule added:** "resolve a branch-awareness setting across env/project/user fallback levels, tolerantly." Grepping the codebase, the **single-source** config readers `plan_tool/backend_config.py:load_backend_overrides` and `plan_tool/jira_config.py:load_jira_config` implement the *opposite* (raising) posture for their single authoritative file — they are siblings to contrast against, **not** to change here. A shared multi-vs-single config-reader abstraction would be a refactor this step cannot mint → see Deferred.
- **Truthy-env coercion** is duplicated from `plan_tool/scenario_capture.py:_TRUTHY` by deliberate copy (leaf contract) — consolidating into a shared helper is deferred.

## Tests

All cases live in `tests/test_project_config.py`. Drive every level against a `tmp_path` repo root and the conftest-pinned temp `$HOME`; no real git, no `claude`. Use `capsys` for the bad-prefix warning.

- `test_disabled_by_default` — `branch_awareness_enabled(tmp_path)` is `False` with no config files present.
- `test_env_truthy_enables` — `PLAN_TOOL_BRANCH_AWARENESS` ∈ {`1`,`true`,`yes`,`on`} (case/space-insensitive) → `True`.
- `test_env_falsy_overrides_project_true` — env ∈ {`0`,`false`,`no`,`off`} → `False` even when the project file sets `enabled: true`.
- `test_env_unrecognized_falls_through` — env `"maybe"` falls through to the project/user/default chain.
- `test_project_enabled_true` — project `{"branch_awareness":{"enabled":true}}` → `True`.
- `test_project_false_overrides_user_true` — project `enabled:false` beats user `enabled:true`.
- `test_user_default_when_no_project` — user `enabled:true`, no project file → `True`.
- `test_malformed_project_json_swallowed` — unparseable project JSON + valid user `enabled:true` → resolves to `True`, no exception raised.
- `test_non_object_top_level_swallowed` — top-level JSON array → that level unset.
- `test_missing_branch_awareness_block` — config object without a `branch_awareness` key → level unset.
- `test_non_bool_enabled_treated_unset` — `"enabled":"true"` (string) at project → that level's `enabled` ignored; falls through to user/default.
- `test_prefixes_default` — no config → `branch_prefixes(tmp_path) == ["plan/"]`.
- `test_prefixes_project_over_user` — project `["feature/"]` beats user `["bugfix/"]`.
- `test_prefixes_bad_list_warns_and_defaults` — non-list / empty list → returns `["plan/"]` and emits one stderr warning naming the file.
- `test_prefixes_invalid_element_falls_back` — element with a forbidden char/space/`..` → default + warning.
- `test_enabled_independent_of_bad_prefixes` — project with valid `enabled:true` but malformed `branch_prefixes` → `enabled` still `True`, prefixes default with warning (per-key independence).
- `test_derive_branch_uses_primary_prefix` — `derive_branch("my-slug", ["plan/","bugfix/"]) == "plan/my-slug"`.
- `test_convention_names_all_prefixes` — `convention_names("my-slug", ["plan/","feature/"]) == ["plan/my-slug","feature/my-slug"]`.
- `test_user_config_path_lazy_home` — `user_config_path()` resolves under the fixture-pinned temp `$HOME`, proving `Path.home()` is evaluated in-body.
- `test_project_config_path` — `project_config_path(tmp_path)` ends with `.plan-tool/config.json` under `tmp_path`.
- `test_project_config_error_is_exception` — `ProjectConfigError` is a subclass of `Exception` and is never raised by the malformed-input cases above.
- `test_is_valid_branch_prefix` — `plan/`/`feature/` valid; `""`, `"plan"` (no `/`), `"pl an/"`, `"plan~/"`, `"plan/../"` invalid.

### Test-creation order (feature step)

- **This is a feature step — new behavior.** Write each test above alongside the symbol it covers in `tests/test_project_config.py`.
- **Green-before-done gate:** every new test in `tests/test_project_config.py` must pass (`uv run pytest tests/test_project_config.py -q`) before this step is considered complete. No existing suite is touched, so the full suite must remain green unchanged.

## Acceptance criteria

- `branch_awareness_enabled(tmp_path)` returns `False` when no config file exists.
- Precedence holds: `PLAN_TOOL_BRANCH_AWARENESS` (truthy/falsy tokens) overrides project, project overrides user, user overrides the `False` default; an unrecognized env value falls through.
- A typed `enabled` that is not a JSON boolean is treated as unset (not coerced); a string config value never flips behavior.
- A malformed project or user config file is swallowed (returns "level unset"); `branch_awareness_enabled` and `branch_prefixes` never raise.
- `branch_prefixes(tmp_path)` returns `["plan/"]` by default; project list overrides user list; a bad/empty/invalid list returns `["plan/"]` and writes exactly one stderr warning naming the file.
- `derive_branch("s", ["plan/","x/"]) == "plan/s"` and `convention_names("s", ["plan/","x/"]) == ["plan/s","x/s"]`.
- `user_config_path()` resolves under `Path.home()` evaluated at call time (passes under the conftest temp-HOME fixture).
- `ProjectConfigError` exists as an `Exception` subclass and is defined but unraised.
- `plan_tool/project_config.py` imports nothing from `plan_tool.create`/`launcher`/`locator`/`scenario_capture` (leaf contract).

## References

- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — The exact ref-name rules `_is_valid_ref` / `_is_valid_branch_prefix` must enforce so every `<prefix><slug>` is a valid branch.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — `json.load` / `JSONDecodeError` handling for the per-level tolerant reader.
- [pathlib — Object-oriented filesystem paths (Python docs)](https://docs.python.org/3/library/pathlib.html#pathlib.Path.home) — `Path.home()` semantics, relevant to the lazy-evaluation requirement.

## Deferred

- **Shared truthy-env helper** — `_TRUTHY` is copied from `plan_tool/scenario_capture.py` to preserve the leaf contract; consolidating the two into one helper is a separate refactor, not in this footprint.
- **A unified multi-vs-single config-reader abstraction** — `backend_config.py` / `jira_config.py` raise on their single authoritative file; reconciling that with this tolerant multi-level reader is a refactor `detail` cannot mint → route to reconcile.
- **A strict config writer that raises `ProjectConfigError`** — the type is defined now but no writer exists; the `plan-tool` config writer is its intended future raiser.
- **Git ref validation via the real `git check-ref-format`** — step 2's `plan_tool/cli/gitcommit.py` owns git shell-outs; this step uses a pure Python predicate so it stays git-free with no `depends_on`.
- **All call sites** — gating `run`/`create`, ownership classification, and the branch commands on these functions land in steps 4–7; step 1 ships the leaf inert (nothing imports it yet).
