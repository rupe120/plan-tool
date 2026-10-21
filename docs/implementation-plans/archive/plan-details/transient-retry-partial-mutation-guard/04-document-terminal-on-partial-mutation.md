> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document the terminal-on-partial-mutation behavior and close the BUG_BACKLOG RISK entry

## Summary

This step is the plan's docs-and-bookkeeping tail. It records the new streaming-run behavior — a transient **or rate-limit** retry now stops instead of re-driving when the aborted turn left uncommitted edits — in `docs/RUN_FLOW.md` and `RUNBOOK.md`, then reconciles the two backlog files. It removes the now-shipped `RISK` entry from `BUG_BACKLOG.md` ("Transient retry re-drives the `acceptEdits` streaming run over a partially-mutated tree") because response A closes the corruption on **every** re-invoke arm (transient and rate-limit), leaving no residual hole, and files a forward-looking `BACKLOG.md` entry for the deferred response B (snapshot-restore) so the resilience follow-up isn't lost. It changes no production code; the deletion of the `RISK` entry is a claim that steps 1–3 shipped, so it is gated on verifying those surfaces exist at HEAD first. On green, the docs describe the terminal-on-partial-mutation trade, `BUG_BACKLOG.md` has no outstanding `RISK`, and `BACKLOG.md` names the restore-policy follow-up.

## Table of Contents

- [Why](#why) — why the docs and backlog must catch up once A ships
- [Input](#input) — the shipped surfaces from steps 1–3 this step verifies before editing
- [Files (creates vs edits)](#files-creates-vs-edits) — the four docs/backlog files this step edits
- [Implementation](#implementation) — what each doc gets, the deletion gate, and the response-B entry
- [Tests](#tests) — verification for a non-code step (no unit tests)
- [Acceptance criteria](#acceptance-criteria) — checkable end states
- [References](#references) — the docs relevant to this step
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

Steps 1–3 change observable behavior: on the streaming `run` path a transient or rate-limit failure whose aborted turn left uncommitted edits no longer re-drives the prompt — it surfaces as a terminal failure. Two docs describe the old always-retry behavior and now read stale: `docs/RUN_FLOW.md`'s **Rate-limit / transient recovery seam** section (its seam table has no `retry_guard` row) and `RUNBOOK.md`, which has no operator recovery entry for the new partial-mutation surface. An operator who hits the new terminal failure has nowhere to look for what to do. Separately, the whole plan exists to close the single outstanding `RISK` in `BUG_BACKLOG.md`; leaving that entry in place after A ships would wrongly assert the corruption is still live, and the deferred response B (the resilience-restoring snapshot-restore) needs a home in `BACKLOG.md` so it isn't forgotten. This step is the backlog reconciliation the plan's seed requires: the work came from that `RISK` entry, so shipping it means retiring the entry.

## Input

This step depends on steps 1, 2, and 3 and asserts, by deleting the `RISK` entry, that their code shipped. Before editing any doc, confirm these surfaces exist at HEAD (grep, don't trust the plan text):

- **Step 1 — the `retry_guard` seam** in `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`, consulted whenever the loop predicts a re-invoke (`will_retry_rate_limit or will_retry_transient`) so it covers the transient **and** rate-limit arms, returning step 1's decision value (a `RetryDecision` carrying a `RetryPolicy` of `RETRY`/`STOP` — no `RESTORE` member; restore is caller-side). Follow step 1's shipped names; this step only describes the seam, it does not re-specify it.
- **Step 2 — the streaming git-delta guard** in `plan_tool/launcher.py:shell_invoker`, which snapshots the changed-paths set before attempt 1 and returns `STOP` with the partial-mutation hint when any retry (transient or rate-limit) would re-drive a dirty tree.
- **Step 3 — the batch opt-out** in `plan_tool/shell.py:claude_invoke`, which passes step 1's always-retry constant explicitly.

If any surface is missing or differs, **stop and route back to the owning step** — do not patch code in this docs step (an unscoped code change here gets no convergence loop). The deletion gate is "no code surface is missing," not "the plan says it's done."

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `docs/RUN_FLOW.md` — in the **Rate-limit / transient recovery seam** section, add a `retry_guard` row to the seam table and a short note on the terminal-on-partial-mutation behavior plus the A-only resilience trade.
  - `RUNBOOK.md` — add one operator recovery entry under `## Recovery: common failures` describing the partial-mutation terminal surface and how to recover (inspect, revert, re-run the step).
  - `BUG_BACKLOG.md` — delete the transient-retry `RISK` entry (its heading block under `## RISK`), leaving `## RISK` as `_(none outstanding)_`.
  - `BACKLOG.md` — add a forward-looking entry for the deferred response B (snapshot-restore policy) under the fitting category per the file's own "Adding a new entry" rules (no roll-up edit is mandated for a deferred item).

## Implementation

**`docs/RUN_FLOW.md` — extend the recovery-seam section, don't restate the leaf.**
- **Add a `retry_guard` row to the seam table.** The section already lists caller-injected seams (`run_once`, `classify`, `notify`, `on_nonsuccess`, …) with a "shell ↔ launcher difference" column. Add one row for the new seam: what the caller injects (a decision consulted whenever a re-invoke is predicted — so it covers both the transient backoff and the rate-limit wait/switch arms — before that backoff or wait) and the difference (launcher wires the git-delta guard; shell wires the always-retry constant). Step 1 owns the seam's exact name and return type — cite it, don't re-specify it here.
- **State the new terminal behavior in one or two lines.** A transient or rate-limit failure whose aborted turn left uncommitted tracked or untracked-non-ignored edits is now returned as a terminal failure with an actionable hint instead of being re-driven, so the double-apply can't corrupt the committed diff.
- **Name the trade plainly.** This is response A only: refusing the retry turns some previously-recovered transients into surfaced failures. That is the deliberate correctness-over-resilience choice; response B (snapshot-restore) is the resilience-restoring follow-up (now tracked in `BACKLOG.md`).
- **Keep it terse.** Match the section's existing table-plus-short-paragraph style. Do not duplicate the git porcelain / ignored-file details — those live in step 2's detail and the code.

**`RUNBOOK.md` — add one operator recovery entry.**
- **Home it under `## Recovery: common failures`**, alongside `### Step exited non-zero — plan not advanced`. Match that entry's tone: a short "what you saw / why / how to recover" block with a fenced `plan-tool run … --step <id>` re-run line.
- **Describe the surface honestly.** On the streaming `run` path, a transient or rate-limit abort that left partial edits now surfaces as a terminal failure naming the uncommitted edits, rather than silently retrying. Cover the sibling case too: a failure that goes terminal *without* a retry (a transient past its budget, or a second rate-limit) can also leave partial edits, but with only the generic failure hint — the recovery below applies to **any** terminal step failure that left uncommitted edits, not only the guard's `STOP`.
- **Give the recovery steps — and operationalize both branches.** Inspect (`git status` / `git diff`), then choose:
  - **Revert and re-run (the default).** An aborted turn's edits are usually *incomplete*, so this is the normal path: discard the partial edits — `git checkout` / `git restore` for modified files (cite the git-restore doc) **and** `git clean -f` / `rm` for newly-created files, since restore/checkout leave untracked files in place and the guard counts untracked-non-ignored paths — then re-run the step. **Do not commit-then-re-run**, and do not re-run *without reverting first*: a bare re-run snapshots the leftover partial edits into its own baseline, so the guard no longer catches them and the re-drive double-applies (the re-guard-after-`STOP` known limit — revert is what resets the baseline).
  - **Accept as complete (only if inspection confirms it).** If the partial edits genuinely constitute the finished step, **do not re-run** (re-running would re-drive them). Instead advance the plan by hand: commit the edits, then flip that step's `status:` to `done` in the plan frontmatter (the manual step-status edit RUNBOOK already documents) so the launcher moves on. This branch is the exception, not the default — reserve it for a turn that aborted *after* completing the work.
  Note the automatic backstop: a **`--commit`** run's clean-tree preflight refuses to start over the dirty tree, so the silent re-baseline can only happen on a `--commit`-less bare re-run — that's where reverting first is load-bearing. This is the intended A-only behavior, not a regression, so the operator resolves the tree rather than expecting auto-recovery.

**`BUG_BACKLOG.md` — delete the shipped `RISK` entry (gated).**
- **Precondition:** the Input grep confirms steps 1–3 shipped. On any gap, stop (see Input).
- **Delete the whole entry**, not a trimmed version — A guards **every** re-invoke arm (transient backoff and rate-limit wait/switch), so no live arm of the corruption remains (the RISK's own "every transient class … 429 …" enumeration is fully covered). After deletion `## RISK` reads `_(none outstanding)_` (it currently holds only this entry). Response B is forward-looking work, not an outstanding bug, so it goes to `BACKLOG.md`, not a slimmed `RISK` stub.
- **Sweep for lingering mentions.** Grep `BUG_BACKLOG.md` (and `BACKLOG.md`) for phrases like "transient retry", "partially-mutated", "double-apply", "acceptEdits" and classify each hit: an open-work assertion about this bug gets removed/repaired; an origin or shipped-context citation stays. Do not scrub accurate provenance.

**`BACKLOG.md` — file the deferred response-B follow-up.**
- **Add one entry** for response B: same detection as A, but on a dirty tree restore to the pre-attempt snapshot and re-drive — idempotent recovery that keeps transient/rate-limit resilience. Name that B is a **caller-side** branch in the launcher guard closure (which already has git): it restores then returns `RETRY`, so the stdlib-only leaf needs no change (its contract stays `RETRY`/`STOP`) — B is a later branch, not a rewrite. Note the constraint the plan flagged: the restore must not clobber a `--commit`-less run's earlier legitimate dirty edits.
- **Pick the category and next free #ID** per the file's `## Adding a new entry` rules — likely `### A. New capability, well-scoped`. Use the next unused number (the latest filed is #118, so #119 unless taken).
- **Just add it under its category — no roll-up edit is mandated.** Follow `## Adding a new entry`: the Readiness lens's "Concrete (ready to implement)" is a catch-all covering every other open entry, so it needs no explicit list edit, and the only conditionally-mandated roll-up is the Quality/accuracy lens — which applies solely to items bearing on output accuracy, not this snapshot-restore follow-up. So the operative action is simply adding the entry under its category; a deferred item is not the highest open concrete pick, so leave the "Next concrete pick" / "Highest open by tier" lines untouched.

## Tests

### Verification (non-code step)

This step changes no production code, so there are no unit tests. Verify the artifacts instead:

- **Surface-existence gate (before editing)** — grep confirms `retry_guard` in `plan_tool/rate_limit_loop.py`, the streaming guard in `plan_tool/launcher.py:shell_invoker`, and the always-retry wire in `plan_tool/shell.py:claude_invoke` all exist at HEAD; a gap stops the step.
- **`BUG_BACKLOG.md` well-formed** — grep confirms `## RISK` reads `_(none outstanding)_` (or names only the deferred response-B follow-up); no line still asserts the transient-retry bug as open. (`plan-tool validate` does not apply — it schema-checks a plan's frontmatter, not the backlog files.)
- **`BACKLOG.md` well-formed** — the new #ID is unique (grep the number returns only the new entry and any intentional citations), the entry sits under a real category heading, and roll-up lists stay comma-clean.
- **Doc accuracy** — every symbol named in the new `docs/RUN_FLOW.md` / `RUNBOOK.md` prose (`retry_guard`, `run_with_rate_limit_recovery`, `shell_invoker`, `claude_invoke`) resolves to a real symbol at HEAD; internal links and fenced `plan-tool` commands are valid.
- **No stale cross-references** — grep across the four edited files for lingering "double-apply / partially-mutated / transient retry" open-work phrasing; each remaining hit is a deliberate origin/context citation, not a stale open-bug claim.

## Acceptance criteria

- `docs/RUN_FLOW.md`'s recovery-seam section lists a `retry_guard` seam and states the terminal-on-partial-mutation behavior plus the A-only resilience trade.
- `RUNBOOK.md` has one recovery entry, under `## Recovery: common failures`, that operationalizes **both** branches of the partial-mutation terminal surface: revert-and-re-run (the default), and accept-as-complete (commit, then flip the step's `status:` to `done` by hand) — plus the note that a `--commit` run's clean-tree preflight auto-refuses a dirty re-run.
- `BUG_BACKLOG.md` no longer contains the transient-retry `RISK` entry; `## RISK` reads `_(none outstanding)_`.
- `BACKLOG.md` contains a new entry for response B (snapshot-restore) with a unique #ID, registered per the file's "Adding a new entry" rules.
- No edited file still asserts the transient-retry double-apply as open, unfixed work; provenance citations (if any) remain intact.
- The `RISK` deletion was made only after grep confirmed steps 1–3's surfaces exist at HEAD; no production code changed in this step.

## References

- `plan_tool/rate_limit_loop.py` — step 1's `retry_guard` seam in `run_with_rate_limit_recovery`; the surface the `docs/RUN_FLOW.md` seam-table row must match, and the first grep target of the deletion gate.
- `plan_tool/launcher.py` — step 2's streaming git-delta guard in `shell_invoker`; the surface the terminal-on-partial-mutation prose describes, and the second grep target of the deletion gate.
- `plan_tool/shell.py` — step 3's batch always-retry wire in `claude_invoke`; the "shell wires the always-retry constant" half of the seam-table row, and the third grep target of the deletion gate.
- [Git - git-status Documentation](https://git-scm.com/docs/git-status) — the porcelain changed-paths format the streaming guard reads; ground the `docs/RUN_FLOW.md` note on why gitignored writes don't false-trigger.
- [Git - git-restore Documentation](https://git-scm.com/docs/git-restore) — reverting working-tree files (`--worktree`, `--staged`, overlay semantics); the basis for the `RUNBOOK.md` recovery steps (`git restore` / `git checkout`).

## Deferred

- **Response B (snapshot + restore + retry) itself** — this step only files the `BACKLOG.md` follow-up; building the caller-side restore branch is out of scope (owned by that new backlog entry).
- **Any production-code change** — this is a non-code step; a missing step 1–3 surface routes back to the owning step, it is not patched here.
- **Broader `docs/RUN_FLOW.md` / `RUNBOOK.md` restructuring** — only the recovery-seam note and the one recovery entry are in scope; unrelated doc cleanup is not.
