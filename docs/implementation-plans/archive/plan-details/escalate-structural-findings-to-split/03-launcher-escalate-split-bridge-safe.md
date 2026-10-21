# Step 3 — Add `launcher.escalate_to_split`: safe-gate → propose → apply (interactive opt-in) or recommend (unattended), reusing the Phase-B split engine via body-local imports

## Summary

- **Adds one bridge function** to `plan_tool/launcher.py`: `escalate_to_split(plan_path, *, step_id, repo_root, invoker, allow_split=False, prompt_fn=None)`. Given a structural finding's target step, it re-parses the plan, runs the safety gate, asks Claude to propose a refactor+feature pair, and then **either applies the split** (interactive session + the `allow_split` opt-in flag) **or surfaces a recommendation** (everything else).
- **Reuses the existing split engine unchanged** through body-local imports — `create._propose_step_split` / `create._apply_step_split` and `detail._split_is_safe` / `detail._confirm_split` / `detail._migrate_downstream_details_after_split` — mirroring `detail.py`'s Phase-B sequence. No new split algorithm.
- **Most important design decision:** a structural plan edit happens **only** when `sys.stdin.isatty()` is true AND `allow_split` is set AND the operator confirms. Every other path (non-TTY, no opt-in, declined, downstream run state present) mutates nothing and returns a structured `review.Recommendation`.
- **Adds `EscalateResult`** (frozen dataclass) carrying the outcome label, the new ids/titles on a real split, the blocking ids on an unsafe gate, and the `Recommendation` to fold into the findings report.
- **On green:** a safe + interactive + opt-in + confirmed call renumbers the plan on disk and returns `outcome="applied"` with the new ids; an unattended call returns `outcome="recommended"` with proposed titles + rationale and leaves every file unchanged; an unsafe call returns `outcome="unsafe"` with the blocking downstream ids and no mutation; a mid-apply `CreateError` returns `outcome="split-failed"` with a re-plan recommendation and no mutation.

## Table of Contents

- [Why](#why) — what's dead-ended today and what the bridge unblocks
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — `EscalateResult`, `escalate_to_split`, the import discipline, the TTY/opt-in gate
- [Tests](#tests) — unit cases for each branch, with the invoker seam neutralized
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — Python `sys`/`io` TTY semantics and pytest fixtures
- [Deferred](#deferred) — what steps 4–5 own (routing, re-authoring, the `BLOCKED-STRUCTURAL` apply-walk branch)

## Why

A finding whose only correct fix is "split this step into two" is recognized but dead-ended. The convergence loop skips `detail-purity` findings, and `apply_finding` can only revert and report. The split engine that would resolve them already exists and is already wired to this exact trigger in `detail.py` Phase B — `_propose_step_split` proposes, `_split_is_safe` gates, `_confirm_split` asks, `_apply_step_split` splices, `_migrate_downstream_details_after_split` renames downstream files — but it lives **only** inside `generate_detail` and is reachable nowhere else. This step lifts that exact sequence into a standalone, callable bridge in `plan_tool/launcher.py` so the create/detail convergence loops (step 5) and the review apply walk (step 6) can finish what they start instead of dead-ending. The bridge does the routing and plumbing only; it adds no split capability and honors the hard invariant that a structural plan edit never happens unattended.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/launcher.py` — add the `EscalateResult` frozen dataclass and the `escalate_to_split` function (which body-locally imports `_parse_steps_json` alongside `_propose_step_split` from `create` to recover the dropped rationale from the same proposal); extend the existing top-level `from dataclasses import dataclass, replace` (launcher.py:21) with `field` (the `EscalateResult` list fields use `field(default_factory=list)`); extend the existing top-level `from plan_tool.review import (...)` block with `Recommendation` and `_make_rec_id`.
  - `tests/test_launcher.py` — add a `TestEscalateToSplit` class with the per-branch unit cases.

## Implementation

### `plan_tool/launcher.py`

**Add `EscalateResult`** as a `@dataclass(frozen=True)`, placed beside `ApplyFindingResult` (both are apply-side outcome structs). Fields:

- `outcome: str` — one of:
  - `"applied"` — interactive + opt-in + confirmed; the split ran and the plan was written.
  - `"recommended"` — safe to split, but unattended or no opt-in or declined; structure unchanged, a split recommendation is returned.
  - `"unsafe"` — `_split_is_safe` reported a downstream step already run/started; structure unchanged, a re-plan recommendation is returned.
  - `"split-failed"` — `_apply_step_split` raised `CreateError` mid-apply (the proposed split produces an invalid step graph); structure unchanged, a re-plan recommendation is returned (re-running `plan-tool split` would reproduce the failure, so the advisory points at a re-plan, not a split retry).
  - `"proposal-unusable"` — Claude returned an unparseable or wrong-length proposal; nothing to apply or recommend.
  - `"step-missing"` — `step_id` is no longer in the plan (already restructured by an earlier escalation in the same loop).
- `step_id: int` — the escalation target.
- `blocking_ids: list[int] = field(default_factory=list)` — populated on `"unsafe"` (the downstream ids `_split_is_safe` named).
- `new_ids: list[int] = field(default_factory=list)` — populated on `"applied"` (the contiguous replacement ids after renumber).
- `new_titles: list[str] = field(default_factory=list)` — populated on `"applied"` and `"recommended"` (the proposed refactor + feature titles).
- `recommendation: Optional[Recommendation] = None` — the structured finding to fold into the findings report on `"recommended"`, `"unsafe"`, and `"split-failed"`; `None` otherwise.

**Add `escalate_to_split`** with this signature and body. Keep it terse per the concise-docs rule.

```
def escalate_to_split(
    plan_path: Path,
    *,
    step_id: int,
    repo_root: Path,
    invoker: Callable[[str], str],
    allow_split: bool = False,
    prompt_fn: Optional[Callable[[str], str]] = None,
) -> EscalateResult:
```

- **`invoker` is the split-proposer seam**, type `Callable[[str], str]` — it returns the raw Claude text `create._propose_step_split` parses. This is **not** launcher's own `Invoker = Callable[[str], tuple[int, str]]` (the run-step seam); do not reuse that alias. Make `invoker` a required keyword (no shell default) so tests must pass a neutralized seam and the autouse gate in `tests/conftest.py` never fires.
- **Body-local imports (mandatory — real cycle):**
  ```
  from plan_tool.create import (  # lazy: avoid create↔launcher import cycle
      CreateError,
      _apply_step_split,
      _parse_steps_json,
      _propose_step_split,
  )
  from plan_tool.detail import (  # lazy: avoid detail↔launcher import cycle
      _confirm_split,
      _migrate_downstream_details_after_split,
      _split_is_safe,
  )
  ```
  Both `plan_tool/create.py` and `plan_tool/detail.py` import `apply_finding` from `plan_tool/launcher.py` at module top, so launcher importing either at top would be a cycle. The body-local placement is genuine cycle-breaking — state that as the reason.
- **`Recommendation` / `_make_rec_id` go on the TOP-level review import**, not body-local. `plan_tool/launcher.py` already imports `plan_tool.review` at module top, and `plan_tool.review` only ever imports launcher body-locally — so launcher→review at top has **no cycle**. Extend the existing `from plan_tool.review import (...)` block rather than adding a new body-local import. (The existing body-local `from plan_tool.review import Recommendation as _Rec` inside `apply_finding`'s except arm is a separate exception-path convenience — leave it as-is; do not cite cycle-breaking for the review import.)

**Control flow (mirror `detail.py` Phase B, the `if allow_split and mixed_steps and sys.stdin.isatty()` block):**

1. **Re-parse from disk:** `plan = parse_plan(plan_path)` (already imported at top). Resolve the target via `plan.step_by_id(step_id)`; on `KeyError` return `EscalateResult(outcome="step-missing", step_id=step_id)`. Re-parsing each call (not trusting a passed-in `Plan`) is what lets a later step's escalation see the prior split's renumbering.
2. **Safety gate first:** `safe, blocking = _split_is_safe(plan, step_id)`. If not `safe`, build a re-plan `Recommendation` naming `blocking` and return `EscalateResult(outcome="unsafe", step_id=step_id, blocking_ids=blocking, recommendation=rec)`. **Do not propose** when unsafe — splitting is off the table, so spending Claude on titles is wasted.
3. **Propose (one round-trip yields titles + rationale):** `_propose_step_split` returns only `list[Step]` titles — it parses the proposal into a *local* `rationales_out` dict and discards it (`create.py:3188–3192`), so `Step` carries no rationale field. `escalate_to_split` must surface that rationale for the recommendation `body` **without a second Claude call**, so it parses the same proposal itself rather than relying on `_propose_step_split`'s return:
   - Wrap the passed `invoker` in a thin capturing shim — `def _capture(prompt): nonlocal raw; raw = invoker(prompt); return raw` — so the one underlying Claude call's raw text is retained.
   - `replacements = _propose_step_split(step, _capture, repo_root=repo_root)` (this is the single round-trip; it builds the prompt, invokes through the shim, and validates the exactly-two shape). On `None` (unparseable / not exactly two), return `EscalateResult(outcome="proposal-unusable", step_id=step_id)`.
   - `rationales: dict[int, str] = {}; _parse_steps_json(raw, rationales_out=rationales)` — re-parse the **captured** raw to recover the per-step rationale that `_propose_step_split` dropped. No extra invoke: it parses the text already returned by the single proposal call.
   The proposal runs in **both** the apply and recommend branches — the unattended recommendation needs the proposed titles + rationale, so propose before deciding apply-vs-recommend.
4. **Decide apply vs recommend** on `interactive = sys.stdin.isatty()`:
   - **Apply path** — `allow_split and interactive`:
     - `if prompt_fn is None: import builtins; prompt_fn = builtins.input` (mirror `detail.py`).
     - `if not _confirm_split(prompt_fn, step=step, replacements=replacements):` → fall through to the recommend path (operator said no; surface the recommendation rather than silently dropping).
     - On confirm: `shift = len(replacements) - 1`; `new_steps = _apply_step_split(plan.steps, step_id, replacements)` inside `try/except CreateError` — on `CreateError`, mutate nothing and return `EscalateResult(outcome="split-failed", step_id=step_id, recommendation=rec)` with a **re-plan** recommendation (mirroring the `"unsafe"` path), **not** a `plan-tool split` suggestion: the proposed split itself produces an invalid step graph, so re-running `plan-tool split --step N --into …` reproduces the failure — degrade to a re-plan advisory rather than raise.
     - `_migrate_downstream_details_after_split(new_steps, repo_root=repo_root, target_id=step_id, shift=shift)`.
     - `write_plan(plan_path, plan.model_copy(update={"steps": new_steps}))` (already imported at top).
     - Return `EscalateResult(outcome="applied", step_id=step_id, new_ids=[s.id for s in new_steps if ...the two replacements...], new_titles=[r.title for r in replacements])`. Derive the new ids from the spliced positions in `new_steps`, not a `step_id`-based range: take `pos = next(i for i, s in enumerate(plan.steps) if s.id == step_id)` (the target's index) and read the ids of the `len(replacements)` steps at `new_steps[pos : pos + len(replacements)]`. `_apply_step_split` renumbers by position (ids from 1), so on a gapped plan `step_id != pos + 1` and a `step_id .. step_id + shift` range would name the wrong ids; read them off the spliced replacements instead.
   - **Recommend path** — everything else (non-TTY, no opt-in, or declined): build a split `Recommendation` carrying the proposed titles + rationale and `suggested_action` pointing at `plan-tool split`, and return `EscalateResult(outcome="recommended", step_id=step_id, new_titles=[r.title for r in replacements], recommendation=rec)`. **Mutate nothing.**

**Building the recommendations** (both flavors) via `_make_rec_id`, mirroring the `Recommendation(...)` construction already in `apply_finding`'s except arm:

- **Source token:** use a single new advisory source string `"structural-split"` for both flavors. It is a plain label on the returned object — this step does **not** add it to any `*_SOURCES` set or to `APPLY_ELIGIBLE_SOURCES` (the recommendation is advisory and must never be re-fed to `apply_finding`, a prose editor that cannot restructure a plan). Severity `"info"` so it can never gate (exit-code convention: a surfaced recommendation keeps rc 0 unless `--fail-on-findings`).
- **Safe-unattended (recommend) rec:** `id=_make_rec_id(step_id, "structural-split", f"split:{step_id}")`, `title` ~ `"step {step_id} should be split into a refactor + feature pair"`, `body` listing the proposed titles (`r.title` for each `r in replacements`) paired with their rationale (from the `rationales` dict captured in the Propose step), `suggested_action=f"Run: plan-tool split <plan> --step {step_id} --into '<title-a>' --into '<title-b>'"` (mirror the guidance string already at `plan_tool/cli/authoring.py` near `f"finding), run \`plan-tool split {args.name} --step N --into ...\`"`).
- **Unsafe (re-plan) rec:** `id=_make_rec_id(step_id, "structural-split", f"replan:{step_id}")`, `body` naming the `blocking` downstream ids and why the split is unsafe (renumbering would orphan id-keyed run state), `suggested_action` ~ `"Re-plan: downstream step(s) {blocking} have already run/started; restructure via re-plan rather than an in-place split."`.
- **Split-failed (re-plan) rec:** built on the `CreateError` mid-apply path, mirroring the unsafe re-plan rec's shape — `id=_make_rec_id(step_id, "structural-split", f"replan-failed:{step_id}")`, `body` stating the proposed split produced an invalid step graph (so an identical `plan-tool split` would fail the same way), `suggested_action` ~ `"Re-plan: the proposed split of step {step_id} produced an invalid step graph; restructure via re-plan rather than retrying the split."`. It deliberately does **not** point at `plan-tool split`.

**`escalate_to_split` does NOT re-author the new halves.** `detail.py` Phase B re-authors the detail-less halves via `generate_detail(step_id=hid, allow_split=False, ...)` after its split loop; that re-authoring is the **caller's** job here (step 5's convergence loop re-parses the written plan, sees the two new detail-less steps, and authors them). Keeping the bridge to the five-primitive structural sequence + `write_plan` keeps its single responsibility clear and its tests free of a full `generate_detail` drive. State this in `## Deferred`.

## Tests

All cases live in a new `TestEscalateToSplit` class in `tests/test_launcher.py`. Neutralize the proposer seam in every case — pass a fake `invoker` (a `lambda prompt: '<json>'` returning a two-element array, or a string holding an unparseable / wrong-length array such as a one-element array to drive the unusable branch). Do **not** drive the unusable branch with a `None`-returning `invoker`: `create.py:_parse_steps_json` calls `raw.strip()` with no `None`-guard, so a `None` return raises `AttributeError` inside `_propose_step_split` rather than yielding the `proposal-unusable` outcome. Drive TTY with `monkeypatch.setattr("sys.stdin.isatty", lambda: True/False)` (the established pattern, e.g. `tests/test_detail.py`). Use `tmp_path` plan fixtures whose steps are canonically numbered `1..N`.

Enumerate these unit tests, added **with** the implementation; all must be green before this step is done (green-before-done gate):

- `test_safe_interactive_opt_in_applies_split` — TTY true, `allow_split=True`, `prompt_fn` returns `"y"`, fake proposer returns a valid refactor+feature pair: asserts `outcome == "applied"`, the plan on disk now has the two replacement steps with renumbered contiguous ids, `new_ids`/`new_titles` populated, `recommendation is None`.
- `test_unattended_recommends_only` — TTY false (or `allow_split=False`), valid proposal: asserts `outcome == "recommended"`, the plan file is unchanged, `recommendation` is a `Recommendation` with `source == "structural-split"`, `severity == "info"`, and proposed titles in its body.
- `test_no_opt_in_recommends_only` — TTY true but `allow_split=False`: asserts `outcome == "recommended"` and no mutation (the opt-in is required even on a TTY).
- `test_declined_confirm_recommends` — TTY true, `allow_split=True`, `prompt_fn` returns `"n"`: asserts `outcome == "recommended"`, no mutation, `_apply_step_split` never reached (plan unchanged).
- `test_unsafe_downstream_blocks_split` — a downstream step at/after the target is `DONE`/`CURRENT`: asserts `outcome == "unsafe"`, `blocking_ids` names the offending downstream id(s), no mutation, `recommendation.suggested_action` mentions re-plan. The proposer is rigged to **raise** to prove it is never called when unsafe (the safety gate short-circuits before propose).
- `test_apply_failure_recommends_replan` — TTY true, `allow_split=True`, `prompt_fn` returns `"y"`, valid proposal, but `_apply_step_split` is patched to raise `CreateError`: asserts `outcome == "split-failed"`, no mutation, and `recommendation.suggested_action` mentions re-plan and does **not** name `plan-tool split` (a failing split must not be advised to retry).
- `test_proposal_unusable_returns_no_mutation` — fake proposer returns an unparseable / wrong-length string (e.g. a one-element JSON array): asserts `outcome == "proposal-unusable"`, no mutation, `recommendation is None`.
- `test_step_missing_returns_step_missing` — `step_id` absent from the plan: asserts `outcome == "step-missing"`, no mutation, proposer never called.
- `test_apply_writes_renumbered_plan` — after an applied split, re-`parse_plan` the written file and assert ids are contiguous `1..N`, the feature half depends on the refactor half, and a downstream step's `depends_on` repointed correctly (leans on `_apply_step_split`'s invariants; this test pins that `escalate_to_split` actually persisted them).
- `test_apply_migrates_downstream_detail_pointer` — a downstream step with a `NN-slug.md` detail file present on disk: after the applied split, assert the file was renamed to its new `NN-` prefix and `step.detail` repointed (proves `_migrate_downstream_details_after_split` is wired in).
- `test_invoker_not_called_on_unsafe` — explicit negative test (overlaps the unsafe case): proposer rigged to raise, asserts it is never invoked, pinning that the safety gate runs strictly before propose.

## Acceptance criteria

- `escalate_to_split` is importable from `plan_tool.launcher` and returns an `EscalateResult`.
- Safe + TTY + `allow_split=True` + confirmed: the plan file on disk is renumbered (contiguous `1..N`, refactor-before-feature edge, downstream `depends_on` repointed) and `outcome == "applied"`.
- Non-TTY, or `allow_split=False`, or declined: the plan file is unchanged and `outcome == "recommended"` with a `Recommendation` (`source == "structural-split"`, `severity == "info"`) carrying the proposed titles + rationale and a `plan-tool split` `suggested_action`.
- A downstream step already run/started: `outcome == "unsafe"`, `blocking_ids` lists those ids, no mutation, and the proposer (`_propose_step_split`) is never called.
- `_apply_step_split` raising `CreateError` mid-apply yields `outcome == "split-failed"` with no mutation and a re-plan `Recommendation` whose `suggested_action` advises a re-plan, not a `plan-tool split` retry.
- An unparseable / wrong-length proposal yields `outcome == "proposal-unusable"` with no mutation and `recommendation is None`.
- A `step_id` absent from the plan yields `outcome == "step-missing"` with no mutation.
- `launcher.py` imports `create`/`detail` split symbols **body-locally** and `Recommendation`/`_make_rec_id` at module top; `uv run pytest tests/test_launcher.py -q` passes, and the existing launcher suite still passes.
- No new entry is added to `APPLY_ELIGIBLE_SOURCES` or any `*_SOURCES` set (greppable: `"structural-split"` appears only as a constructed-`Recommendation` label, never in a membership set).

## References

- [sys — System-specific parameters and functions (Python 3 docs)](https://docs.python.org/3/library/sys.html) — `sys.stdin.isatty()` is the gate that decides apply-the-split vs. emit-a-recommendation; tests stub it via `monkeypatch.setattr("sys.stdin.isatty", …)`.
- [io — IOBase.isatty (Python 3 docs)](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — authoritative semantics of `isatty()` on stream objects, for both the implementation and the test stubs.
- [How to use fixtures — pytest](https://docs.pytest.org/en/stable/how-to/fixtures.html) — `tmp_path` plan fixtures and `monkeypatch` overrides used to neutralize the proposer invoker so `escalate_to_split` tests never spawn the real `claude` binary.

## Deferred

- **Routing `detail-purity` findings into `escalate_to_split`** in the create/detail convergence loops behind the `allow_split` opt-in — step 5 (`plan_tool/create.py`, `plan_tool/detail.py`). This step only adds the callable bridge; nothing calls it yet.
- **Re-authoring the two new detail-less halves** after an applied split — the caller's convergence loop re-parses the written plan and authors them (as `detail.py` Phase B does); `escalate_to_split` returns `new_ids` and stops at the structural mutation.
- **Handling `BLOCKED-STRUCTURAL` in the review apply walk** — step 6 (`plan_tool/cli/review_actions.py`) calls `escalate_to_split` from the verdict branch that currently reverts + reports. The `BLOCKED-STRUCTURAL` verdict token and parser come from step 2.
- **Renaming the `detail-purity` source to `granularity-split`** across the classifier and call sites — postponed per the plan's Deferred section; this bridge stands on today's classification.
