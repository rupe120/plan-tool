# Step 5 — Emit an unconditional `plan-tool security` next-step pointer at the end of `detail` and `completeness` (no security dimension inside completeness)

## Summary

Appends a single advisory pointer line — `plan-tool security --target plan <name>` — to the tail of `detail` and `completeness-audit`, reusing the existing `plan_tool/cli/console.py:_print_next_steps` helper. The pointer lands in `plan_tool/cli/authoring.py:cmd_detail` (after the existing review/run/jira "Next steps:" block, on the wrote-success path) and in `plan_tool/cli/completeness_phases.py:_persist_and_present_report` (in **both** the `--iterate` summary branch and the audit-only branch). The load-bearing decision: security stays a **standalone command** the pointer merely advertises — `completeness` does **not** call `run_security_audit`, does **not** add a Security section to `_render_grouped_report`, and does **not** add a security bucket to `_render_completeness_json`. Emission is **unconditional** here (gated only on the same wrote/clean conditions the existing tails use); step 6 layers the cost-relevance gate and `--no-security-hint` opt-out on top. On green, a clean `detail` and a clean `completeness-audit` each print one `plan-tool security --target plan <name>` suggestion line to stderr, and the completeness `--json` payload and grouped report are byte-unchanged.

## Table of Contents

- [Summary](#summary) — what lands and the observable result on green
- [Why](#why) — why a pointer (not a dimension) and why unconditional first
- [Files (creates vs edits)](#files-creates-vs-edits) — two production edits, two test files
- [Implementation](#implementation) — the two emission sites, the import, and the deliberate non-edits
- [Tests](#tests) — emission, suppression, and the non-edit guards
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse/headless grounding carried from the plan
- [Deferred](#deferred) — the relevance gate, the opt-out flag, and other surfaces

## Why

- **The `plan-tool security` verb (steps 1–4) is discoverable only by reading `--help`.** `detail` and `completeness-audit` are the natural authoring hand-off points — a developer who just authored detail files or closed completeness gaps is exactly who should be nudged to run a plan-wide security pass before `run`/`jira`. Nothing today advertises it.
- **Security must stay a standalone auditor, not a completeness dimension.** Folding `run_security_audit` into `completeness` would spend a Claude call on every audit, add a Security bucket to the `--json` gate that headless callers parse, and conflate the plan-wide security axis with the completeness axis. A pointer keeps the two commands orthogonal — `completeness` advertises, `security` audits.
- **Land unconditional emission now; gate it in step 6.** Splitting the always-emit wiring (here) from the cost-relevance gate + `--no-security-hint` opt-out (step 6) keeps each step single-axis and lets the gate be authored against a working pointer rather than wiring and gating in one pass.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/authoring.py` — in `cmd_detail`, add one `_print_next_steps(...)` call for the security pointer immediately after the existing review/run/jira block (the `if rc == 0 and wrote and not args.dry_run:` block that emits `"Next steps:"`). `_print_next_steps` is already imported here.
- `plan_tool/cli/completeness_phases.py` — in `_persist_and_present_report`, emit the security pointer in **both** the `if iterate_enabled:` branch (after the `console_summary` print) and the `else:` audit-only branch (after the grouped-report / "saved to" print). Add a module-level `from plan_tool.cli.console import _print_next_steps` import (console is a cycle-free leaf — `authoring` already imports it; `console` imports nothing from `completeness_*`).

**Test files (edits):**

- `tests/cli/test_authoring_cmds.py` — the live authoring test module (the step's `files:` names `tests/cli/test_authoring.py`; the on-disk file is `test_authoring_cmds.py` — author the new cases there, a deliberate redirect of the declared path to the real file).
- `tests/cli/test_completeness_cmd.py` — extend `TestPersistAndPresentReport` with the pointer-emission and non-edit-guard cases.

## Implementation

### `plan_tool/cli/authoring.py:cmd_detail` (the detail tail)

- **Add a separate `_print_next_steps` call** right after the existing wrote-success block (the one whose first tuple is `f"plan-tool review {args.name}"`). Keep it a distinct call (not a fourth tuple in the existing list) so step 6 can wrap exactly the security line in its relevance gate / `--no-security-hint` check without disturbing the review/run/jira block:
  ```
  _print_next_steps(
      "Security check:",
      [(f"plan-tool security --target plan {args.name}",
        "audit the plan's design for security gaps")],
  )
  ```
- **Gate on the same condition** as the existing block (`rc == 0 and wrote and not args.dry_run`). The pointer is meaningful only when detail wrote something on a clean run — dry-run is a prompt preview, and the skipped-only path (the later `_print_next_steps` calls near the "already exists" idempotent branch) leaves state unchanged, so neither gets the pointer.
- **Stream stays the default (stderr).** `_print_next_steps` writes advisory output to `sys.stderr` so it never pollutes a stdout pipeline — the right channel for a suggestion, matching the existing block.
- **Command form:** the pointer states `--target plan` explicitly — `plan-tool security --target plan <name>` — matching the plan body's canonical pointer form, i.e. the plan-design audit, the correct axis to advertise after authoring detail. (`--target plan` is also `plan_tool/cli/security_cmd.py`'s `default`, so the explicit form is equivalent to omitting it, but the pointer spells it out to fully specify the invocation.)

### `plan_tool/cli/completeness_phases.py:_persist_and_present_report` (the completeness tail)

- **Emit in both branches** so the pointer appears regardless of `--iterate`:
  - `if iterate_enabled:` — after `print(console_summary(...))`.
  - `else:` (audit-only) — after the `print(render_markdown_for_console(grouped_md))` / "Completeness report saved to …" lines.
  Use the same call shape as the detail site (`"Security check:"`, one `(f"plan-tool security --target plan {args.name}", "audit the plan's design for security gaps")` tuple).
- **Emission is unconditional within the function** — it does not depend on `correctness_recs`, `conceptual_recs`, `has_*`, or `report_path`. A clean plan (zero findings) still gets the pointer; the relevance/`--no-security-hint` gating is step 6's job.
- **Add the import** `from plan_tool.cli.console import _print_next_steps` at module top, beside the existing `from plan_tool.style import (...)`. No cycle: `plan_tool/cli/console.py` imports only `plan_tool.style` + stdlib; `completeness_phases` is below `console` in the import graph.

### Deliberate non-edits (the standalone-command invariant)

- **`_render_grouped_report`** — do **not** add a Security section. Its existing `### Suggested next steps` block (the condition-driven `_next_steps` list) is untouched: the security pointer is a separate `_print_next_steps` emission in `_persist_and_present_report`, not a line inside the persisted markdown report.
- **`_render_completeness_json`** — do **not** add a security bucket or any security key. Headless callers parsing the `--json` payload (e.g. `has_blocking_findings`) see a byte-identical schema.
- **No `run_security_audit` import or call** anywhere in `completeness_phases.py` / `completeness_cmd.py`. The pointer is a string; it spawns nothing.

### Shared logic note

- **The "advertise the next command" pattern** already exists at four `_print_next_steps` call sites in `cmd_detail` plus the markdown `_next_steps` list in `_render_grouped_report`. This step reuses the same helper and convention rather than minting a new emitter — no consolidation needed.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Author each test below alongside the emission wiring; every new test must be green before the step is done.

**`tests/cli/test_authoring_cmds.py`** (drive `cmd_detail` via `main(["detail", …])` or the handler directly, with `generate_detail` patched so no backend fires):

- `test_detail_emits_security_pointer_on_green` — a wrote-success, non-dry-run `detail` prints a stderr line containing `plan-tool security --target plan <name>`.
- `test_detail_security_pointer_follows_review_run_jira_block` — the `plan-tool security` line appears after the `plan-tool review` / `plan-tool run` / `plan-tool jira` suggestions (ordering, so the pointer reads as the final hand-off).
- `test_detail_no_security_pointer_on_dry_run` — `--dry-run` emits no `plan-tool security` line.
- `test_detail_no_security_pointer_when_skipped_only` — the all-skipped idempotent path (no file written) emits no `plan-tool security` line.

**`tests/cli/test_completeness_cmd.py`** (extend `TestPersistAndPresentReport`, calling `_persist_and_present_report` directly with a hand-built `_IterateOutcome` and capturing stderr/stdout):

- `test_persist_present_iterate_emits_security_pointer` — `iterate_enabled=True` prints a `plan-tool security --target plan <name>` line.
- `test_persist_present_audit_only_emits_security_pointer` — `iterate_enabled=False` prints a `plan-tool security --target plan <name>` line.
- `test_persist_present_clean_plan_still_emits_pointer` — zero correctness/conceptual recs still emits the pointer (unconditional within the function).
- `test_render_completeness_json_has_no_security_bucket` — `_render_completeness_json(...)` output contains no `security` key (guards the deliberate non-edit).
- `test_render_grouped_report_has_no_security_section` — `_render_grouped_report(...)` markdown contains no `Security` heading (guards the deliberate non-edit).

## Acceptance criteria

- A clean `plan-tool detail <name>` (wrote files, non-dry-run) prints exactly one stderr line containing `plan-tool security --target plan <name>`, after the review/run/jira block.
- `plan-tool detail <name> --dry-run` and an all-skipped `detail` run print no `plan-tool security` line.
- `plan-tool completeness-audit <name>` prints a `plan-tool security --target plan <name>` pointer in both `--iterate` and audit-only modes, including on a finding-free plan.
- `_render_completeness_json` output has no `security` key; `_render_grouped_report` output has no `Security` section — both byte-unchanged from before this step.
- `completeness_phases.py` imports no `run_security_audit` symbol; `grep -L run_security_audit plan_tool/cli/completeness_phases.py` confirms it.
- All new tests in `tests/cli/test_authoring_cmds.py` and `tests/cli/test_completeness_cmd.py` pass; the existing `completeness` end-to-end contract tests in `tests/test_cli.py` (the `has_blocking_findings` assertions) remain green.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)https: — confirms the `security` subparser's `--target` `default="plan"` the pointer advertises.
- [Claude Code Headless Mode (Anthropic docs)https: — grounds the stdout-vs-stderr split: advisory pointers go to stderr so a headless caller's stdout/`--json` stays clean.

## Deferred

- **Cost-relevance gate + `--no-security-hint` opt-out** — step 6 wraps both emission sites so the pointer fires only when security is relevant and the operator hasn't suppressed it. This step emits unconditionally.
- **Pointer at other tails (`create`, `audit`/`review`, `jira`)** — out of scope; the step scopes the pointer to `detail` and `completeness` only.
- **A `completeness-audit --with-security` dimension** — explicitly rejected design; security stays standalone. Documented in step 8's doc surfaces, not implemented here.
- **Pointer wording/`--target` selection heuristics** (e.g. suggesting `--target code` after a code-heavy plan) — fixed `--target plan` form here; any smarter selection is a follow-up.
