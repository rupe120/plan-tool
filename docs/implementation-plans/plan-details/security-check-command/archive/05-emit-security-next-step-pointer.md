# Step 5 — Emit a `plan-tool security` next-step pointer at the tail of `detail` and `completeness` (unconditional; gate lands in step 6)

## Summary

Append a single advisory next-step line — `plan-tool security --target plan <name>` — to the end of `plan_tool/cli/authoring.py:cmd_detail` (as a fourth tuple in its existing review/run/jira `_print_next_steps` call) and to `plan_tool/cli/completeness_phases.py:_persist_and_present_report` (a new `_print_next_steps` call after the if/else presentation block, so it fires on both the `--iterate` summary path and the audit-only path). The load-bearing decision: the pointer **advertises** the standalone `security` verb (step 3) — completeness does **not** invoke `run_security_audit`, render a Security section in `_render_grouped_report`, or add a security bucket to `_render_completeness_json`; security stays a separate command. Emission is **unconditional** here — step 6 layers the cost-relevance gate and `--no-security-hint` opt-out on top. On green, a clean `detail` run and any completed `completeness-audit` each print one `plan-tool security …` suggestion to stderr, and no security audit ever runs as a side effect.

## Table of Contents

- [Why](#why) — why a pointer (not a completeness dimension) lands now
- [Files (creates vs edits)](#files-creates-vs-edits) — two production edits plus their test files
- [Implementation](#implementation) — the detail tuple, the completeness emission, the import, the deliberate non-edits
- [Tests](#tests) — pointer-present, both-paths, and no-side-effect cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse next-step grounding
- [Deferred](#deferred) — the relevance gate, the opt-out flag, the code-axis pointer

## Why

- **The `security` verb (step 3) is reachable but undiscoverable.** A developer finishing `detail` or `completeness-audit` has no signal that a plan-wide security audit exists. The pipeline tail is where the tool already advertises the next command (`review`/`run`/`jira` after `detail`; the structural/conceptual next-steps bullets after completeness) — the security pointer belongs in that same slot.
- **Security must stay a standalone command, not a completeness dimension.** Folding a security pass into `completeness-audit` would re-spend a Claude call on every audit and conflate two axes (authoring-gap completeness vs. design security). The pointer keeps them separate: completeness *advertises* `security`, it does not *run* it.
- **Unconditional now, gated next.** Landing the emission first keeps this step a thin, testable carve over the existing `_print_next_steps` helper. Step 6 adds the cost-relevance gate and the `--no-security-hint` opt-out without re-plumbing the call sites.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/authoring.py` — in `cmd_detail`, append a fourth `(command, description)` tuple to the existing `_print_next_steps("Next steps:", [...])` call (the one carrying the `plan-tool review` / `plan-tool run` / `plan-tool jira` rows, gated on `rc == 0 and wrote and not args.dry_run`). No new import — `_print_next_steps` is already imported from `plan_tool.cli.console`.
- `plan_tool/cli/completeness_phases.py` — add `from plan_tool.cli.console import _print_next_steps` to the top-import block, and add a single `_print_next_steps("Next steps:", [...])` call inside `_persist_and_present_report`, placed after the `if iterate_enabled: … else: …` presentation block and before `return report_path` so it covers both paths with one emission.
- `tests/cli/test_authoring_cmds.py` — add the `cmd_detail` pointer test (see note below on the declared `tests/cli/test_authoring.py`).
- `tests/cli/test_completeness_cmd.py` — extend `TestPersistAndPresentReport` with the both-paths pointer tests and the no-side-effect assertion.

**Declared-files note.** The step's `files:` list names `tests/cli/test_authoring.py`, which does not exist at HEAD; the live authoring-command test module is `tests/cli/test_authoring_cmds.py` (it already hosts the `cmd_detail` dispatch-guard tests in `TestDetailDispatchGuards`). Add the new `cmd_detail` test there rather than minting a near-duplicate `test_authoring.py` — a second authoring test module would fragment the suite. This is an in-footprint substitution, not a scope expansion.

## Implementation

### `plan_tool/cli/authoring.py` — `cmd_detail`

- **Append one tuple** to the existing `_print_next_steps("Next steps:", [...])` call in `cmd_detail` (the block guarded by `if rc == 0 and wrote and not args.dry_run:`, directly after the `_run_completeness_tail` call):

  ```
  (
      f"plan-tool security --target plan {args.name}",
      "audit the plan's design for security gaps",
  ),
  ```

- **Inherit the existing gate.** The tuple sits inside the same `_print_next_steps` call, so it only renders on a clean, productive, non-dry run — exactly like the review/run/jira rows. No separate conditional.
- **Plan axis, not code axis.** `detail` authored the plan's per-step files, so the relevant audit is the plan-design lens (`--target plan`), matching step 3's `plan-tool security --target plan|code <name>` surface. The code-axis pointer is deferred.
- **No new import.** `_print_next_steps`, `_short_path`, `_print_detail_summary` are already imported from `plan_tool.cli.console` at the top of the module.
- **Out-of-scope sibling emitters (do not touch):** `cmd_create`'s `_print_next_steps` call and the two `cmd_split` `_print_next_steps` calls. The step targets the `detail` and `completeness` tails only; create/split keep their current rows.

### `plan_tool/cli/completeness_phases.py` — `_persist_and_present_report`

- **Add the import** to the existing top-import block (currently `from plan_tool.style import (render_markdown_for_console, warn)`):

  ```
  from plan_tool.cli.console import _print_next_steps
  ```

  `plan_tool/cli/console.py` is a cycle-free leaf (depends only on stdlib + `plan_tool.style`); `completeness_phases` importing it is one-directional and introduces no cycle. `authoring.py` already imports `_print_next_steps` from the same leaf — this mirrors that edge.

- **Add one emission** after the `if iterate_enabled: … else: …` block and before `return report_path`:

  ```
  _print_next_steps(
      "Next steps:",
      [
          (
              f"plan-tool security --target plan {args.name}",
              "audit the plan's design for security gaps",
          ),
      ],
  )
  ```

- **One call covers both paths.** Placing the emission below the branch (not inside each arm) makes it fire identically whether the `--iterate` summary (`console_summary` → stdout) or the audit-only grouped report (`render_markdown_for_console(grouped_md)` → stdout) was just printed. `_print_next_steps` writes to stderr by default, so it never pollutes the stdout report/summary or the `--json` payload.
- **`args.name` is in scope** — `_persist_and_present_report` already reads `args.name` for the report metadata.

### Deliberate non-edits (load-bearing — completeness does NOT run security)

- **`_render_grouped_report` (`plan_tool/cli/completeness_phases.py`)** — no Security section, no security recs threaded into `_next_steps`. The grouped report keeps its current correctness/conceptual/deterministic groups.
- **`_render_completeness_json` (`plan_tool/cli/completeness_phases.py`)** — no `security` bucket; the `--json` payload and its `has_blocking_findings` gate are unchanged.
- **`run_security_audit` (`plan_tool/security_audit.py`)** — never called from the completeness or detail path. The pointer is text only; it spends zero Claude calls. This keeps the `conftest.py` real-backend gate green with no new neutralization.

### Foundational logic + shared call sites

- **Foundational logic:** advertise the standalone `security` verb at the plan-authoring/audit tail via the existing `_print_next_steps` helper.
- **Other next-step emitters in the codebase** (all via `_print_next_steps`): `cmd_create` and `cmd_split` in `plan_tool/cli/authoring.py`, and the markdown `_next_steps` list inside `_render_grouped_report`. Only `cmd_detail` and `_persist_and_present_report` are in scope here; the others deliberately stay as-is (create/split target different next commands; the grouped-report bullets are completeness-internal). No consolidation is needed — each emitter advertises a context-specific command set.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add each test alongside the implementation; every new test must be green before the step is done.

`tests/cli/test_authoring_cmds.py` (drive `main(["detail", …])` on a temp registered plan with `generate_detail` stubbed so no Claude fires; capture stderr):

- `test_detail_emits_security_pointer_on_clean_run` — a clean, productive `detail` run prints `plan-tool security --target plan <name>` in the Next-steps block on stderr.
- `test_detail_security_pointer_absent_on_dry_run` — `--dry-run` suppresses the whole Next-steps block, so no security pointer appears (inherits the existing `rc == 0 and wrote and not args.dry_run` gate).
- `test_detail_pointer_does_not_invoke_security_audit` — `plan_tool.security_audit.run_security_audit` stubbed to raise; the `detail` run still completes rc 0, proving the pointer is text-only.

`tests/cli/test_completeness_cmd.py`, extending `TestPersistAndPresentReport` (call `_persist_and_present_report(...)` directly with hand-built `_IterateOutcome` / recs on a `tmp_repo`, conceptual audit stubbed at the domain seam; capture stderr):

- `test_persist_emits_security_pointer_audit_only` — with `iterate_enabled=False`, stderr carries `plan-tool security --target plan <name>`.
- `test_persist_emits_security_pointer_iterate` — with `iterate_enabled=True`, stderr carries the same pointer (proves the single below-branch emission covers both paths).
- `test_persist_pointer_does_not_run_security_audit` — `run_security_audit` stubbed to raise; `_persist_and_present_report` returns its report path normally, proving no security audit fires.
- `test_persist_report_stdout_unchanged_by_pointer` — the stdout grouped report / summary is byte-unchanged from before (pointer goes to stderr only).

## Acceptance criteria

- A clean `plan-tool detail <name>` run prints exactly one `plan-tool security --target plan <name>` line in its Next-steps block on stderr.
- `plan-tool detail <name> --dry-run` prints no security pointer.
- Both `plan-tool completeness-audit <name>` (audit-only) and `plan-tool completeness-audit <name> --iterate` print one `plan-tool security --target plan <name>` line on stderr.
- The completeness `--json` payload and its `has_blocking_findings` gate are byte-unchanged — no `security` key added.
- `run_security_audit` is never called by `detail` or `completeness`; both complete rc 0 with the audit stubbed to raise.
- All new tests in `tests/cli/test_authoring_cmds.py` and `tests/cli/test_completeness_cmd.py` are green; the `conftest.py` real-backend gate never fires.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — confirms the `plan-tool security --target plan <name>` invocation form (step 3's subparser) that the pointer string advertises.
- [OWASP Top 10 (2021)](https://owasp.org/Top10/2021/) — grounds the "audit the plan's design for security gaps" framing the pointer's description promises the user.

## Deferred

- **Cost-relevance gate (step 6)** — suppress the pointer when the plan shows no security-relevant signal; step 5 emits unconditionally.
- **`--no-security-hint` opt-out flag** — the parser flag and its suppression branch land with step 6's gate, not here.
- **Code-axis pointer (`--target code`)** — `detail`/`completeness` advertise the plan-design lens only; a `--target code` suggestion (e.g. after `run`) is out of scope.
- **Pointer in `cmd_create` / `cmd_split` tails** — left as-is; this step scopes the pointer to the `detail` and `completeness` tails per the plan.
