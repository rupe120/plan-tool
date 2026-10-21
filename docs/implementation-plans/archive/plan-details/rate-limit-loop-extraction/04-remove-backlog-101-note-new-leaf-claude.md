> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Remove BACKLOG #101 and register the `rate_limit_loop.py` leaf in CLAUDE.md

## Summary

This step retires the tracking entry that motivated the plan and records the new module in the architecture doc. It deletes BACKLOG #101 (the duplicated rate-limit retry loop) in full — the entry block plus its one cross-reference in the Readiness-lens Concrete list — because steps 1–3 shipped the extraction that closes it. It then adds a short paragraph to `CLAUDE.md`'s Architecture section registering `plan_tool/rate_limit_loop.py` as a stdlib-only leaf below `shell`/`launcher`. This is a **non-code** step: no production code changes, no tests. On green, `grep -n '#101' BACKLOG.md` returns nothing outside archived copies, and `CLAUDE.md` names `rate_limit_loop.py` as the single home of the 429-detect / wait-or-switch recovery loop.

## Table of Contents

- [Why](#why) — why the entry is retired now and the leaf gets documented
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs this step edits
- [Implementation](#implementation) — verify-then-retire #101, and where the leaf paragraph goes
- [Tests](#tests) — verification-by-inspection for a non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the source files to grep before writing
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

BACKLOG #101 tracks the duplicated 429-detect / wait-or-switch recovery loop that `shell.claude_invoke` and `launcher.shell_invoker` each carried. Steps 1–3 extract that loop into `plan_tool/rate_limit_loop.py` and route both callers through it, so the debt #101 names is paid — leaving the entry in `BACKLOG.md` would advertise forward-looking work that no longer exists. At the same time, the new leaf is invisible in the architecture doc: `CLAUDE.md`'s Architecture section registers every cycle-sensitive leaf (`backend.py`, `granularity.py`, `telemetry.py`, …) so a future author knows the import boundary before touching it, and `rate_limit_loop.py` needs the same one-line home so its stdlib-only-below-`shell`/`launcher` rule is discoverable.

## Files (creates vs edits)

**New files:**
- None.

**Existing files (edits only):**
- `BACKLOG.md` — delete the **#101** entry block in full (`**#101 — Factor out the duplicated rate-limit retry loop …**` through its `**Recurrence:**` bullet), and remove `**#101**` from the Readiness-lens Concrete list's `hygiene (…)` group, repairing the surrounding commas so the remaining members read cleanly.
- `CLAUDE.md` — add one Architecture paragraph registering `plan_tool/rate_limit_loop.py` as a stdlib-only leaf below `shell`/`launcher`.

## Implementation

**First, verify the work #101 tracked actually shipped at HEAD — this is the gate before any deletion.** Removing #101 asserts the extraction landed. Grep to confirm the shipped surfaces exist before editing:
- `plan_tool/rate_limit_loop.py` exists and the shared entry point (step 1 owns the final name — `generate_detail`'s sibling detail proposes `run_with_rate_limit_recovery`) is defined in it.
- `plan_tool/shell.py:claude_invoke` imports and calls that entry point (step 2's reroute).
- `plan_tool/launcher.py:shell_invoker` imports and calls that entry point (step 3's reroute).
- The leaf stays first-party-import-free: `grep -E '^(from|import) plan_tool' plan_tool/rate_limit_loop.py` returns nothing.

**On any gap, STOP and route back to the owning code step (1, 2, or 3) — never patch code inside this docs step.** If the entry point or a reroute is missing, deleting #101 would silently lose the only forward-looking record of unfinished work, and adding code here turns a non-code step into an unscoped code change with no convergence loop. Follow steps 1–3's shipped contract for the exact symbol names; this step does not re-specify the leaf.

**Delete #101 whole — do not keep a slimmed-down version.** #101 is a single-purpose entry with no live arm remaining once the loop is extracted, so it is deleted entirely (contrast the multi-arm `#70`, which keeps a `SHIPPED` note and sheds only the shipped arm). The plan's own `## Deferred` section survives via plan archival and is the durable record of any residue, so no fresh backlog entry or trimmed #101 stub is needed.

**Grep the entire `BACKLOG.md` for `#101`, not just the entry block.** The ID appears in two places today:
- The entry block itself (near the `**#101 — Factor out …**` heading).
- The Readiness lens → Concrete (ready to implement) list, in the `hygiene (**#109**, **#101**, **#79**–**#81**, **#89**)` group.

Remove `**#101**` from that hygiene group and fix the comma run so the surviving members (`#109`, `#79`–`#81`, `#89`) still read as a clean list. After editing, `grep -n '#101' BACKLOG.md` must return nothing. Treat any `#101` hits under `plan-seeds/archive/` or `docs/implementation-plans/archive/` as historical artifacts outside this step's file scope — leave them untouched.

**Register the leaf in `CLAUDE.md`'s Architecture section.** Add one bold-titled paragraph in the same style as the neighboring leaf registrations (e.g. `**Backend abstraction (\`backend.py\`).**`, `**Decision telemetry (\`telemetry.py\`).**`). It should state:
- `plan_tool/rate_limit_loop.py` owns the shared 429-detect / wait-or-switch / transient-backoff recovery loop that `shell.claude_invoke` (batch) and `launcher.shell_invoker` (streaming) both route through.
- It is a **stdlib-only leaf below `shell`/`launcher`** — no first-party imports, so it forms no `shell`↔`launcher` edge and no cycle through `backend`/`claude_errors`.
- Caller-specific concerns (the run-once closure, sleep/clock seams, the `EXEC_NOT_FOUND` path guard, the two per-invoke backend-scope ContextVars) stay caller-side and are **injected**, not unified.

One way that keeps the doc coherent: place the new paragraph right after the `**Backend abstraction (\`backend.py\`).**` paragraph, since that paragraph already describes rate-limit policy selection and the "stdlib-only leaf below `shell`/`launcher`" boundary the new leaf shares. Folding a sentence into the backend paragraph instead is acceptable, but a dedicated paragraph matches how every other cycle-sensitive leaf is registered and is easier to find. The exact wording is the implementer's; keep it terse per the Code-comments rule.

## Tests

### Verification (non-code step)

This step changes no production code, so there are no unit tests. Verify the artifacts by inspection:

- `grep -n '#101' BACKLOG.md` returns nothing — proves both the entry block and the hygiene-list cross-reference are gone.
- Read the Readiness-lens Concrete list — the `hygiene (…)` group reads as a clean comma-separated list with no dangling comma or orphaned `#101`.
- `grep -n 'rate_limit_loop' CLAUDE.md` returns the new Architecture paragraph.
- The pre-deletion verification grep (before editing) confirms `plan_tool/rate_limit_loop.py`, its shared entry point, and both callers' routes exist at HEAD; the leaf's `grep -E '^(from|import) plan_tool' plan_tool/rate_limit_loop.py` returns nothing.
- The full suite stays green after all four steps land: `uv run pytest tests/ -q` exits 0 (this step adds no code, so it neither fixes nor breaks tests).

## Acceptance criteria

- `grep -n '#101' BACKLOG.md` returns no matches.
- The `**#101 — Factor out the duplicated rate-limit retry loop …**` entry block is absent from `BACKLOG.md`.
- The Readiness-lens Concrete list's `hygiene (…)` group no longer contains `#101` and its punctuation is intact.
- `CLAUDE.md`'s Architecture section names `plan_tool/rate_limit_loop.py` and states it is a stdlib-only leaf below `shell`/`launcher` that both callers route through.
- `plan_tool/rate_limit_loop.py`, its shared recovery-loop entry point, and both `shell.claude_invoke` / `launcher.shell_invoker` routes exist at HEAD (the deletion is not made on a gap).
- `uv run pytest tests/ -q` exits 0.

## References

The load-bearing pointers for this step are the source files the prose must match at HEAD, not library docs: `plan_tool/rate_limit_loop.py` (the leaf and its entry point), `plan_tool/shell.py` (`claude_invoke`), and `plan_tool/launcher.py` (`shell_invoker`) — grep each before writing the CLAUDE.md paragraph and before deleting #101.

## Deferred

- **Editing archived copies of #101** (under `plan-seeds/archive/`, `docs/implementation-plans/archive/`) — historical artifacts outside this step's file scope; their deferral/history language was true when written.
- **Documenting the rate-limit leaf in any doc other than `CLAUDE.md`** (e.g. `docs/RUN_FLOW.md`, `TESTING.md`) — this step's file list is `BACKLOG.md` and `CLAUDE.md` only; if a seam-neutralization row or flow diagram needs updating, that is a separate reconcile follow-up.
- **Any change to `plan_tool/rate_limit_loop.py`, `shell.py`, or `launcher.py`** — the extraction and reroutes are owned by steps 1–3; on a verification gap this step stops and routes back rather than touching code.
