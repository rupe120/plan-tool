# Step 5 — Add the completeness-audit --seed option

## Summary

Add `--seed <path>` to `plan-tool completeness-audit` in `plan_tool/cli/completeness_cmd.py:register`. The option is an explicit provenance override marker: it must force a fresh conceptual audit, even when a saved audit would otherwise be reused. Regenerate `docs/cli/completeness-audit.md` from the live parser and cover parsing and reuse behavior in `tests/cli/test_completeness_cmd.py`. On green, the command accepts the option, never reuses a saved audit when it is supplied, and the generated CLI reference stays current.

## Table of Contents

- [Summary](#summary) — The CLI behavior this step adds.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why an explicit seed must prevent audit reuse.
- [Input](#input) — The provenance and saved-audit contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed and verified by the work.
- [Implementation](#implementation) — The option, fresh-audit rule, and scope boundary.
- [Tests](#tests) — Focused parser, reuse, and reference coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Official argparse guidance.
- [Deferred](#deferred) — Scope-contract handling owned by step 6.

## Why

`plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` can reuse a saved conceptual audit when plan and code fingerprints match, but an operator-supplied seed changes the intended audit input without changing either fingerprint. Reusing that report would return findings made against different provenance. Step 4 supplies durable `Plan.source_seed` for new plans; this step gives older or exceptional plans an explicit CLI override and makes freshness honest before step 6 consumes the override in the audit prompt.

## Input

- **Step 4 provenance** — Step 4 adds optional `Plan.source_seed` for verified durable seed provenance. This step does not read, validate, or serialize that field.

- **Saved-audit reuse** — `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` decides whether `cmd_completeness` can substitute saved conceptual findings for a new call. An explicit seed must take precedence over `--reuse-audit`, `--reuse-audit-id`, interactive reuse, and non-interactive auto-reuse.

- **Generated CLI reference** — `plan_tool/cli_reference.py:render_reference` builds `docs/cli/completeness-audit.md` from `plan_tool.cli.build_parser()`. Treat the Markdown file as generated output, not separately authored help text.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — register `--seed` on `completeness-audit` and make its presence require a fresh conceptual audit.
  - `docs/cli/completeness-audit.md` — regenerate the command reference after the argparse change.
  - `tests/cli/test_completeness_cmd.py` — add parser and reuse-policy coverage for the override.
  - `tests/cli/test_cli_reference.py` — keep the generated-reference drift gate passing; add a focused assertion only if the existing generic render comparison cannot make a missing `--seed` entry clear.

## Implementation

- **Foundational logic: explicit seed disables saved-audit reuse.** Treat the presence of `--seed`, including an empty value that later fails normal path validation, as a request to audit against a different provenance input. `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` must return the fresh-audit path before it loads, prompts for, or accepts a saved report.

- **Add one audit-only option.** Define `--seed <path>` on the `p_completeness` parser in `plan_tool/cli/completeness_cmd.py:register`, with a clear help string that says it overrides stored seed provenance and forces a fresh audit. Do not add it to `completeness-apply` or shared parser parents.

- **Preserve the option value for step 6.** Store the supplied path on the parsed namespace under a stable, self-explanatory destination such as `seed`. Step 6 owns resolving the path, applying repository-boundary rules, and supplying source text to `plan_tool/review.py:render_plan_audit_prompt`; do not duplicate that policy in this step.

- **Force freshness by presence, not by path interpretation.** A supplied override must bypass reuse even if `--reuse-audit` is explicit or a saved report is otherwise fresh. Do not infer a seed from a plan slug, scan seed directories, or decide here whether the path is readable; the option changes the audit input contract before later resolution decides whether a usable contract exists.

- **Keep existing no-override behavior unchanged.** When `--seed` is absent, retain the existing `_resolve_audit_reuse` ordering for `--no-reuse-audit`, `--reuse-audit`, `--reuse-audit-id`, explicit `--audit-passes`, TTY prompts, and automatic reuse.

- **Regenerate rather than hand-edit documentation.** Run `python -m plan_tool.cli_reference --write` after the parser is complete so `docs/cli/completeness-audit.md` reflects the live usage and help output. `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` remains the drift guard.

## Tests

- `test_seed_option_parses_to_seed_namespace_field` — `completeness-audit <name> --seed <path>` stores the supplied path, while an invocation without the option keeps the field unset.

- `test_seed_option_forces_fresh_audit_even_with_reuse_audit` — `_resolve_audit_reuse` does not accept or load a reusable saved audit when both options are supplied.

- `test_seed_option_forces_fresh_audit_before_interactive_or_headless_reuse` — an override bypasses the prompt and automatic reuse paths without changing their behavior when absent.

- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — regenerated `docs/cli/completeness-audit.md` matches the live parser and includes the new option.

### Test-creation order (feature step)

1. Add parser tests in `tests/cli/test_completeness_cmd.py` for the default and explicit `--seed` namespace values.

2. Add reuse-policy tests in `tests/cli/test_completeness_cmd.py` proving `--seed` wins over every saved-audit reuse mode.

3. Regenerate `docs/cli/completeness-audit.md` and run the existing `tests/cli/test_cli_reference.py` drift gate.

4. Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan-tool completeness-audit <name> --seed <path>` parses successfully and exposes the supplied path to the command handler.

- Supplying `--seed` prevents `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` from returning saved conceptual findings, including with `--reuse-audit`.

- Supplying `--seed` does not add a path lookup, source-content read, provenance inference, or audit-prompt change in this step.

- Invocations without `--seed` retain the existing saved-audit reuse behavior.

- `docs/cli/completeness-audit.md` shows `--seed` in generated usage and options output.

- `tests/cli/test_completeness_cmd.py` and `tests/cli/test_cli_reference.py` pass.

## References

- [argparse — Python Standard Library](https://docs.python.org/3/library/argparse.html) — Use for option declaration, argument destinations, and generated help behavior.

## Deferred

- Source-contract path resolution and prompt grounding — step 6 owns reading the explicit override or step 4’s `Plan.source_seed`, enforcing path safety, and adding the resolved contract to the conceptual-audit prompt.
