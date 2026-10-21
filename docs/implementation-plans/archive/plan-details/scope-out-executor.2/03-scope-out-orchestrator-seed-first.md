> **Auto-archived**: this plan was swept on 2026-06-25 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the scope-out orchestrator: seed-first apply-or-recommend gate returning a frozen `ScopeOutResult`

## Summary

Adds the policy layer that turns steps 1 and 2's deterministic pieces into one operator-facing actuator in `plan_tool/scope_out.py`: a `scope_out_step(...)` orchestrator plus a frozen `ScopeOutResult` (an `EscalateResult`-style return). It re-parses the plan from disk, runs `compute_narrow` once, refuses on any blocker (mapping `step-missing` / `empty-plan` / the two graph blockers → outcomes), and on a safe, opted-in, confirmed carve **writes the forward-seed to disk first, then narrows the plan** — seed-first so the durable re-plannable artifact survives even if the narrow is rolled back. A post-seed `apply_narrow` exception is explicitly outside the returned `ScopeOutResult` outcomes: the exception propagates, no result is returned, and the orphan seed remains on disk. The key design decision is that scope-out spends **zero Claude**: both halves (`render_carved_seed` + `compute_narrow`/`apply_narrow`) are deterministic, so `scope_out_step` takes **no `invoker=`** — unlike its sibling bridge `launcher.py:escalate_to_split`, which has a Claude proposer seam. On green, `tests/test_scope_out.py` proves the happy path writes the seed before mutating the plan, each blocker maps to its outcome with nothing written, and the opt-in/confirm gates recommend-only on every non-applied path.

## Table of Contents

- [Why](#why) — why the policy layer lands on top of steps 1–2 now
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step extends
- [Implementation](#implementation) — `ScopeOutResult`, `scope_out_step`, the blocker→outcome map, seed-first ordering, the confirm gate
- [Tests](#tests) — the unit cases added with the implementation and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — stdlib docs relevant to the frozen result and TTY confirm
- [Deferred](#deferred) — the CLI wiring, convergence flip, and the apply-or-recommend / confirm consolidations left for steps 4–5 and reconcile

## Why

- **Steps 1 and 2 built the parts; nothing composes them.** Step 1's `render_carved_seed` serializes a carved step into a `create --from-existing` seed string, and step 2's `compute_narrow`/`apply_narrow` drop-and-renumber the plan all-or-nothing — but no caller resolves the seed's inputs, derives and writes the seed file, or decides *whether* to mutate. This step adds that orchestrator and the safety policy.
- **The seed is the whole point of scope-out, so it must land before the plan changes.** Scope-out carves a spinning region *out* of a plan so it can be re-planned later. If the plan were narrowed first and the seed write then failed, the carved work would be lost. Writing the seed first makes the durable artifact the invariant, with the narrow as the reversible follow-on.
- **The mutation must never happen without explicit apply authorization.** Like `escalate_to_split`, a structural plan edit needs `--apply` plus either an interactive confirm or the explicit `-y/--yes` bypass; every other path recommends only and writes nothing. This step encodes the two invariants *refuse before any write when the carve is unsafe* and *never mutate structure without `--apply` plus confirm/`-y`*.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — add the frozen `ScopeOutResult` dataclass, the public `scope_out_step(...)` orchestrator, and the private helpers `_confirm_scope_out(...)`, `_resolve_upstream_context(...)`, `_resolve_carved_detail_path(...)`, `_carved_seed_path(...)` (collision-safe path derivation + write), and `_outcome_for_blockers(...)`. New first-party imports beyond step 2's `plan_tool.detail` / `plan_tool.parser`: `plan_tool.locator` (for `slug_from_filename` — the plan slug, since `schema.Plan` has no `slug` field) and a **body-local** `from plan_tool.create import slugify` inside `_carved_seed_path` (kept lazy to mirror how `launcher.py:escalate_to_split` lazy-imports from `create`/`detail` to dodge import cycles). Reuses step-1/2 module symbols `render_carved_seed`, `compute_narrow`, `apply_narrow`, `NarrowPreview`, `NarrowResult`, and `NarrowBlocker`.
  - `tests/test_scope_out.py` — add the orchestrator unit cases: seed-first ordering, each blocker→outcome, the opt-in/confirm gates, upstream-context wiring, seed-path collision, the no-`invoker` signature check, and the frozen-result check.

## Implementation

### `plan_tool/scope_out.py` — `ScopeOutResult` (new frozen dataclass)

- **Mirror `launcher.py:EscalateResult`'s shape for returned results.** Frozen, with an `outcome` that is exactly one of five strings and the applied-only / refusal-only fields kept `Optional`/empty otherwise. A post-seed `apply_narrow` failure is an exception path outside this dataclass, not a sixth outcome:
  - `outcome: str` — one of `applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing`.
  - `carved_id: int` — the step the caller asked to carve (the `EscalateResult.target_id` analog).
  - `seed_path: Optional[Path] = None` — set only on `applied`; the path the forward-seed was written to.
  - `narrow: Optional[NarrowResult] = None` — set only on `applied`; what `apply_narrow` committed.
  - `preview: Optional[NarrowPreview] = None` — set on `recommended` (and `applied`) so a recommend-only caller can show the would-be carve without re-computing.
  - `blockers: list[NarrowBlocker] = field(default_factory=list)` — the blockers that forced `unsafe` / `empty-plan` / `step-missing` (the `EscalateResult.blocking` analog); empty on `applied` / `recommended`.
- **Do not import `review.Recommendation` here.** `recommended` carries no `review` recommendation object (the convergence fork-arm in step 5 owns the prose recommendation); keeping `review` out of `scope_out.py` avoids the `review`↔leaf import-cycle question entirely.

### `plan_tool/scope_out.py` — `scope_out_step(...)` (new public orchestrator)

- **Signature — no `invoker`, an opt-in flag, a `yes` bypass, and a `prompt_fn` seam:**
  - `scope_out_step(plan_path: Path, *, carved_id: int, repo_root: Path, allow_scope_out: bool, yes: bool = False, prompt_fn: Optional[Callable[[str], str]] = None) -> ScopeOutResult`
  - **No `claude_invoker` / `invoker`.** State in the docstring that scope-out is fully deterministic — `render_carved_seed` and `compute_narrow`/`apply_narrow` shell out to nothing — so there is no Claude seam to override. This is the one structural contrast with `escalate_to_split` (which carries a `_propose_step_split` invoker).
  - `allow_scope_out` is the programmatic opt-in (the `escalate_to_split` `allow_split` analog): `False` → recommend only, no prompt, no mutation.
  - `yes` bypasses the interactive confirm (the destructive-verb `_confirm(prompt, *, yes)` idiom from `cli/manifest.py:_prompt_remove_missing`); `prompt_fn` defaults to `input` so tests inject a stub.
- **Sequence — re-parse, gate, then seed-first apply. Mirror `escalate_to_split`'s call-for-call order (re-parse → safe-gate → confirm → apply), minus the Claude proposer step:**
  1. **Re-parse the plan from disk** and capture the source frontmatter hash from the same parse snapshot on every call — never trust an in-memory `Plan` the caller passed, exactly as `escalate_to_split` re-parses. Resolve `repo_root` is supplied, not derived. Do not re-read the plan only to compute preview provenance after parsing; the hash passed into step 2 must describe the exact bytes that produced the `Plan` object.
  2. **Compute the preview** — `preview = compute_narrow(plan, carved_id=carved_id, plan_path=plan_path, repo_root=repo_root, source_frontmatter_hash=source_frontmatter_hash)`. This is deterministic and does no plan mutation (only a read to decide `archive_detail`).
  3. **Blocker gate (runs first, before the opt-in/confirm).** If `preview.blockers` is non-empty, return `ScopeOutResult(outcome=_outcome_for_blockers(preview.blockers), carved_id=carved_id, blockers=preview.blockers, preview=preview)` — write nothing. This is the deterministic refusal that holds regardless of `allow_scope_out`/`yes`, matching step 2's "refuse before touching disk" invariant.
  4. **Opt-in gate.** If `not allow_scope_out`, return `recommended` (carved_id + `preview`, no seed/narrow). No prompt.
  5. **Confirm gate.** Derive the plan slug with `plan_slug = locator.slug_from_filename(plan_path)` (`schema.Plan` has no `slug` field, so `plan.slug` raises `AttributeError`; this mirrors `completeness_report.py` and `convergence_diagnosis.py`). If `not _confirm_scope_out(prompt_fn, plan_slug=plan_slug, carved_id=carved_id, yes=yes)`, return `recommended`. A non-TTY caller without `yes` auto-declines here.
  6. **Apply branch (seed-first).** Resolve `upstream_context` through `preview.renumber`, read the carved step's detail body, render the seed, derive a collision-safe path and **write the seed**, then call `apply_narrow`. Return `applied` with `seed_path`, `narrow`, and `preview` only after `apply_narrow` succeeds; if `apply_narrow` raises, propagate the exception without returning `ScopeOutResult`, leaving the already-written seed as an orphan artifact.
- **`_outcome_for_blockers(blockers) -> str`** — map `NarrowBlocker.kind` to the result outcome with a fixed precedence (most fundamental first): a `step-missing` blocker → `"step-missing"`; else an `empty-plan` blocker → `"empty-plan"`; else (`non-canonical-numbering`, `inbound-dependent`, or `downstream-orphan`) → `"unsafe"`. Keep the blocker-kind strings as the single source from step 2 — do not re-spell them here; reference `NarrowBlocker.kind` values.

### `plan_tool/scope_out.py` — the apply-branch helpers

- **`_resolve_upstream_context(plan, carved_step, preview) -> list[tuple[int, str, str]]`** — for each id in `carved_step.depends_on`, look up the step and return `(post_narrow_id, title, status_value)` triples for the **surviving prerequisite** steps, where `status_value` is the prerequisite step's `status.value`. Do **not** assume dependency ids are lower than the carved step: `schema.Plan` permits a carved step to depend on any other non-self step, including a later PENDING survivor whose id shifts during the drop. Build an old→new map from `preview.renumber`, default unchanged ids to themselves, and report the post-narrow id so the seed does not preserve stale dependency ids. Skip any dependency id not found (defensive; compute_narrow already validated graph shape). Feed the result straight into `render_carved_seed(upstream_context=...)` so the step-1 renderer can split DONE prerequisites from non-DONE external prerequisites.
- **Read the carved step's detail body** — resolve with `_resolve_carved_detail_path(plan_path, plan, carved_step, repo_root) -> tuple[Path | None, bool]`, returning `(detail_path, detail_missing)` so the renderer can distinguish a never-detailed step from one whose body was lost. **Path parity with step 2 is mandatory** (the plan's *Carved step's own detail file → archive* decision): the body the seed captures and the file `compute_narrow` chose for `preview.archive_detail` must be the **same file**, so the seed never captures from one file while the narrow archives or orphans another. Prefer reading the body from the preview's already-resolved `preview.archive_detail` rather than re-resolving; where this helper resolves on its own (it must also return the `detail_missing` flag, which `archive_detail` alone — `None` for both never-detailed and set-but-missing — cannot carry), it resolves identically to `compute_narrow` (`Step.detail` first, canonical fallback second), pinned by a test asserting the two land on the same path. Three explicit cases — **named here so a set-but-missing pointer is not mislabeled as never-detailed** (the plan's `carved-detail-pointed-but-missing` decision):
  - `carved_step.detail` set **and** `repo_root / carved_step.detail` exists → `(that path, False)`: the authoritative pointer.
  - `carved_step.detail` set **but its file is absent** (moved/deleted/slug-drifted) → `(None, True)`: the **set-but-missing pointer** case. It is **not** a block (do not refuse a carve over a drifted detail file) and **not** an apply-failure — it is a "detail file missing" note distinct from "never detailed". Return `True` so the renderer emits a missing-detail warning, never the never-detailed note. Do not fall back to the canonical path here: a set pointer is authoritative, so a missing pointee is a lost body, not an unpointed step.
  - `carved_step.detail` unset → fall back to `detail.derive_detail_path(plan_path, plan, carved_step)` only when that canonical file exists, yielding `(canonical, False)`, else `(None, False)`: the never-detailed step.
  - Then `detail_body = detail_path.read_text(encoding="utf-8") if detail_path is not None else None`, and pass both `detail_body` and `detail_missing` to `render_carved_seed`. A `None` body with `detail_missing=False` keys step 1's "never detailed / frontmatter only" note; a `None` body with `detail_missing=True` keys its missing-detail warning. Passing `""` would silently skip both branches.
- **`_carved_seed_path(plan_path, carved_step, repo_root) -> Path`** — derive and collision-proof the seed path:
  - Base name `plan-seeds/<plan-slug>-carved-<step-slug>.md` under `repo_root`, with `<plan-slug>` from `locator.slug_from_filename(plan_path)` (not `plan.slug`, which does not exist) and `<step-slug>` from a body-local `from plan_tool.create import slugify` over `carved_step.title` (fall back to `f"step-{carved_step.id}"` when `slugify` returns `""`).
  - **Never overwrite an existing seed** — a prior carve's seed is a durable artifact. If the base path exists, append `-2`, `-3`, … before `.md` until a free path is found, and return that. State the suffix-not-clobber choice explicitly.
  - Create `plan-seeds/` with `mkdir(parents=True, exist_ok=True)` before writing, mirroring `cli/annotate_cmd.py:cmd_annotate`'s `path.parent.mkdir(...)` + `write_text(..., encoding="utf-8")`.
- **Seed-first write, then narrow.** In the apply branch, call `render_carved_seed(plan_title=plan.title, carved_step=carved_step, detail_body=detail_body, detail_missing=detail_missing, upstream_context=upstream_context, source_path=plan_path)` — step 1's renderer is keyword-only with `plan_title` leading and requires `plan_title` and `source_path` (no defaults), so pass **every argument by keyword** (`plan_title=plan.title`, `carved_step=carved_step`, `source_path=plan_path` alongside `detail_body`/`detail_missing`/`upstream_context`) → write it to `_carved_seed_path(...)` → only then `apply_narrow(plan_path, preview, repo_root=repo_root)`. Rationale and failure semantics:
  - `apply_narrow` cannot raise-on-blockers here (the gate already returned), so the only raise is a mid-apply IO error, which `apply_narrow` rolls the plan back from and re-raises. Let that propagate outside the returned-outcome contract — no `ScopeOutResult` is returned, the already-written seed stays on disk as a harmless durable artifact, and the plan is intact, so a re-run is safe.

### `plan_tool/scope_out.py` — `_confirm_scope_out(...)` (new private confirm)

- **Model it exactly on `cli/manifest.py:_prompt_remove_missing`'s branch shape** (the repo's destructive-verb confirm idiom), not on a new design:
  - `yes` true → return `True` (no prompt).
  - `not sys.stdin.isatty()` and `not yes` → print a `re-run with -y` hint to stderr and return `False`, so an unattended run without `-y` never silently mutates a plan.
  - interactive TTY → `builtins.input(f"Carve step {carved_id} out of {plan_slug}? [y/N]: ")`, returning `True` only on `y`/`yes`; catch `EOFError`/`KeyboardInterrupt`, print `cancelled`, return `False`.
- **Why a local confirm rather than reusing one** — there is no shared confirm helper (`manifest.py`, `checkpoints.py`, `bench_cmd.py`, `detail._confirm_split` each mint their own). Folding them into one shared confirm is a standing deferred reconcile item (see Deferred), not a detail-time change.

### Shared / parallel logic (no extra edits this step)

- **The apply-or-recommend gate already exists once** at `launcher.py:escalate_to_split` returning `EscalateResult` (re-parse → safe-gate → opt-in → confirm → apply/recommend). `scope_out_step` is the second instance of that shape. **Do not** try to reuse `escalate_to_split` (its safe-gate, proposer, and `EscalateResult` are split-specific) — build `scope_out_step` as its own gate and route the consolidation to reconcile (Deferred).
- **The `recommended` prose surface** (a `structural-split`-style `Recommendation`) is *not* built here — step 5 flips the convergence scope-out fork-arm to a runnable command; this step's `recommended` outcome just signals "safe but not applied" to its caller.

## Tests

All cases live in `tests/test_scope_out.py` alongside steps 1–2. They are deterministic; the apply/blocker cases build a real plan + detail files under `tmp_path`, the signature/frozen cases construct objects directly. No `invoker` stub and no `@pytest.mark.allow_real_claude` — `scope_out_step` spawns no backend, so `conftest.py`'s autouse no-Claude gate stays satisfied untouched.

### Test-creation order (feature step)

This is a **feature** step. Add every test below **with** the implementation; all must be green before the step is done (`enforce_step_tests: true` in the plan frontmatter).

- `test_applied_writes_seed_then_narrows` — `allow_scope_out=True`, `yes=True`, no blockers: outcome `applied`, `seed_path` exists under `plan-seeds/`, `narrow` is a `NarrowResult`, and the re-parsed plan has the carved step gone with contiguous ids.
- `test_seed_persists_when_narrow_fails` — monkeypatch `apply_narrow` to raise after the seed write: `scope_out_step` raises, returns no `ScopeOutResult`, the seed file still exists on disk, and the plan is unchanged (rolled back) — proves seed-first ordering and the durable-artifact invariant.
- `test_step_missing_outcome` — `carved_id` absent from the plan: outcome `step-missing`, no seed written, plan untouched, `blockers` names the `step-missing` kind.
- `test_empty_plan_outcome` — carving the lone remaining step: outcome `empty-plan`, no seed, plan untouched.
- `test_inbound_dependent_is_unsafe` — a survivor `depends_on` the carved step: outcome `unsafe`, `blockers` names that step, no seed, plan untouched.
- `test_downstream_orphan_is_unsafe` — a downstream non-`PENDING` step that would renumber: outcome `unsafe`, no seed.
- `test_not_allowed_recommends_only` — `allow_scope_out=False`: outcome `recommended`, no seed, plan untouched, `preview` populated, **no prompt shown**.
- `test_non_tty_auto_declines_to_recommended` — `allow_scope_out=True`, `yes=False`, `sys.stdin.isatty()` patched `False`: outcome `recommended`, no seed, plan untouched.
- `test_declined_confirm_recommends` — TTY with `prompt_fn` returning `"n"`: outcome `recommended`, no seed, plan untouched.
- `test_yes_bypasses_confirm` — `yes=True` with a non-TTY stdin still reaches `applied` and the seed is written (the prompt is never called).
- `test_done_upstream_context_passed_to_seed` — carved step with DONE upstream `depends_on`: the written seed contains the `## Upstream prerequisites` bullets for the resolved `(id, title, status_value)` triples.
- `test_non_done_upstream_context_passed_to_seed` — carved step with non-DONE upstream `depends_on`: the written seed contains the `## External prerequisites (not done yet)` bullets with the current status from the resolved `(id, title, status_value)` triples.
- `test_later_dependency_context_uses_post_narrow_id` — carved step depending on a later PENDING survivor: the written seed renders that prerequisite with the id from `preview.renumber`, not the stale pre-drop id.
- `test_bare_step_seed_has_empty_detail_body` — carving a never-detailed step: the seed renders with an empty detail body and no crash.
- `test_noncanonical_carved_detail_pointer_passed_to_seed` — a carved step whose `detail:` points at an existing noncanonical path has that body in the written seed instead of the "never detailed" note.
- `test_set_but_missing_detail_pointer_passes_detail_missing` — a carved step whose `detail:` pointer is set but whose file is absent resolves to `(None, True)` (no canonical fallback, no refusal, no apply-failure), so the written seed carries the missing-detail warning, not the "never detailed" note.
- `test_seed_path_collision_suffixed` — a seed already at the derived base path: the orchestrator writes a `-2`-suffixed path and never overwrites the existing file.
- `test_scope_out_step_takes_no_invoker` — `inspect.signature(scope_out_step)` has no `invoker`/`claude_invoker` parameter (the no-Claude contract).
- `test_scope_out_result_is_frozen` — assigning to a `ScopeOutResult` field raises `dataclasses.FrozenInstanceError`.

## Acceptance criteria

- `scope_out_step(plan_path, carved_id=N, repo_root=..., allow_scope_out=True, yes=True)` on a safe carve returns `outcome="applied"` with `seed_path` pointing at a written `plan-seeds/<plan>-carved-<slug>.md` file, and the re-parsed plan is narrowed (carved step gone, ids `1..N-1`).
- On a forced mid-apply failure, `scope_out_step` propagates the exception outside the returned `ScopeOutResult` outcomes; the seed file remains on disk and the plan is unchanged — the seed is written before the narrow.
- A missing `carved_id` returns `step-missing`; carving the only step returns `empty-plan`; an inbound-dependent or downstream-non-`PENDING` step returns `unsafe` — each writes no seed and leaves the plan untouched.
- `allow_scope_out=False`, a non-TTY run without `yes`, and a declined TTY confirm each return `recommended` with no seed and no plan mutation.
- A carved step with an existing noncanonical `detail:` pointer uses that body in the seed; a set-but-missing `detail:` pointer resolves to `(None, detail_missing=True)` — a "detail file missing" warning in the seed, distinct from never-detailed, never a refusal or apply-failure; unpointed steps fall back to the canonical detail path only when that file exists.
- `scope_out_step` has no `invoker`/`claude_invoker` parameter and the suite's no-Claude gate passes with no opt-out marker on these tests.
- `ScopeOutResult` is a frozen dataclass whose returned `outcome` is one of `applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing`; post-seed `apply_narrow` failures are exceptions, not result outcomes.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `frozen=True` + `FrozenInstanceError` for `ScopeOutResult`, matching `launcher.EscalateResult` / `detail.MergeResult` / step 2's `NarrowResult`.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path` for deriving the collision-safe `plan-seeds/<plan>-carved-<slug>.md` path and `mkdir(parents=True, exist_ok=True)` before the seed write.
- [sys.stdin.isatty / input — Built-in Functions](https://docs.python.org/3/library/functions.html#input) — the interactive-confirm primitives the `_confirm_scope_out` gate uses, mirroring `cli/manifest.py:_prompt_remove_missing`.

## Deferred

- **The `plan-tool scope-out --step N` CLI command** — step 4 (`scope_out_cmd.py` + `app.py`/`parser.py`/`__init__.py` dispatch + generated `docs/cli/scope-out.md`). This step ships only the library orchestrator; the CLI handler maps `--apply`→`allow_scope_out=True` and `-y`→`yes=True`.
- **Flipping the convergence scope-out fork-arm to a runnable command** — step 5 (`convergence_diagnosis.py`); the `recommended` outcome here is the programmatic signal that step 5's prose recommendation will pair with.
- **Consolidating the two apply-or-recommend gates** (`launcher.py:escalate_to_split` + `scope_out_step`) into one shared bridge — a behavior-preserving cross-module refactor `detail` cannot mint; route to reconcile.
- **Consolidating the per-module confirm idioms** (`manifest._prompt_remove_missing`, `detail._confirm_split`, `_confirm_scope_out`, and the `-y/--yes` parents) into one shared helper — a standing deferred reconcile item that strengthens with each new instance.
- **Carving a multi-step dependent sub-tree** — the inbound-dependent blocker refuses carving a step a survivor depends on; carving a whole dependent group is out of scope for this single-step executor (plan-level Deferred).
