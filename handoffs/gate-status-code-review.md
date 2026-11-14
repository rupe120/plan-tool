# Gate-status Claude Code review

## Scope and method

Review the complete `main...HEAD` change for #500 on `direct/gate-status`.
The baseline is `main` at `55297a7c06262e15c34d394691509fed97f00c5d`;
the first reviewed head is `ddcbb4ee5b24d968f50a9601c4faaf9ad64ba19c`.
Claude Code invokes the installed `engineering:code-review` Skill tool with
`claude-sonnet-5-5`, high effort, in report-only mode. The driving session
verifies findings, applies bounded fixes, runs tests, and commits before the
next review. No publication is authorized.

## Review pass 1 — 2026-10-19

Claude session: `afac78d4-a07b-4381-8434-da34fa83e25f`.
Scope: `55297a7c0...ddcbb4ee5`. The reviewer reads code, contracts, tests,
registration, and bookkeeping. Its pytest command is denied by the child
permission configuration, so this pass supplies static review evidence only.
The driving session's full-suite evidence is 14,691 passed, 67 skipped.

| ID | Reported finding | Severity | Disposition |
| --- | --- | --- | --- |
| C1 | Jira-grade audits persist no final sidecar, but the new grade contract omits that limitation; plan-quota also withholds the final sidecar. Synthetic Jira sidecars do not establish producer behavior. | medium | Confirmed documentation and producer-coverage gap. Keep grade isolation; document the absent evidence and test the real Jira audit route. |
| C2 | Four known follow-ups disappear with the retired handoff. | medium | Confirmed loss of pickup context, partly refuted as untracked work: see the per-item decisions below. Preserve those decisions here. |
| C3 | `docs/ARCHITECTURE.md` and the canonical driver's subcommand catalog omit the new command. | low–medium | Confirmed. Complete the command catalogs. |
| C4 | Consumers must index `stages[current_stage]`; a top-level convergence field could simplify that. | optional | Decline the added field: the requested contract is per stage. Clarify the lookup and unknown cases in the existing schema. |
| C5 | A sibling command imports the private stage helper. | optional | Decline reorganization: the #500 fence allows none, and the helper's fail-closed result is already documented. |
| C6 | CLI coverage omits grade forwarding, failed stage derivation, resolution errors, and external paths. | optional | Add focused contract coverage, including the real Jira producer path. |
| C7 | Unknown roles and not-sampled results lack explicit rejection tests. | optional | Confirmed coverage gap. Add both exclusions. |
| C8 | `--json` is a no-op but its help reads as an output switch. | optional | Clarify that the flag is accepted for explicit JSON requests; output is always JSON. |
| C9 | Schema version uses literal `1` instead of a named constant. | optional | Decline: the exact document test pins version 1. A new constant adds no required behavior. |
| C10 | Tests use single quotes and long lines. | optional | Decline a formatting-only sweep: no formatter or lint contract applies, and it does not affect this change's behavior. |

### Follow-up decisions (C2)

- **Detail partial results after an exception:** intentionally not filed as a
  new defect. `DATA_CONTRACT.md` § `run_end.result` explicitly defines null as
  unknown when authoring raises; it never claims no files exist. Reporting
  exact partial results requires a separate authoring-result capability and
  is outside #500. No such extension is selected.
- **`manifest_updated` success/failure semantics:** intentionally not filed.
  The same contract explicitly defines added-this-run on success and current
  registration on failure. This is documented compatibility, not an
  unacknowledged contract violation. No semantics change is selected.
- **Private `_bounded_violations` import:** intentionally decline the cleanup.
  The helper is internal to this package; the handoff identifies no failure.
  Adding a public wrapper solely to change the name is unnecessary scope.
- **Calls without a run-log sink:** already tracked in `BUG_BACKLOG.md`,
  “Ten model-backed calls still write no start or end record to the run log, so run-log token totals undercount” (the entry naming
  `tests/test_run_log_call_coverage.py` and `DEFERRED_SITES`).
  `DATA_CONTRACT.md` § `run_end.usage` explicitly limits totals to recorded
  calls. Do not duplicate that tracked defect or silently expand #500.

### Sites enumerated before the repair

Defect class: saved gate verdict documentation and tests must describe the
actual final-sidecar evidence boundary and expose the command in existing
command catalogs.

Identifier search: `gate-status`, `qualified_result`,
`is_pre_apply_checkpoint`, `_bounded_violations`, `manifest_updated`.
Vocabulary search: “no findings sidecar”, “jira-grade sidecar”, “gate
verdict”, “Subcommands by intent”, “Command layer”, and “no sink”.

Sites: `DATA_CONTRACT.md` saved verdict section; CLI flag help and generated
`docs/cli/gate-status.md`; `tests/test_gate_status.py` grade and exclusion
fixtures; `tests/cli/test_gate_status_cmd.py` public contract;
`tests/cli/test_completeness_cmd.py::TestGradeJiraReportSurfaces` actual
producer coverage; `docs/ARCHITECTURE.md` command table;
`integrations/shared/DIRECTIVES.md` Discovery and Audit catalogs.
The producer and loader policies stay unchanged: existing tests pin the
intentional Jira sidecar suppression and final-role eligibility.

### Repair evidence

- `0fe3e5c45` closes C1, C4, C6, C7, and C8: evidence limitations, real Jira
  producer coverage, reader exclusions, CLI error/path contracts, and flag help.
- `3433ea22d` closes C3 in the architecture and driver command catalogs.
- C2's four dispositions are recorded above; C5, C9, and C10 are explicitly
  declined with reasons.
- Focused checks: 32 passed (`tests/test_gate_status.py`, the CLI contract,
  and `TestGradeJiraReportSurfaces`).
- Mutation: bypassing `is_reusable_audit_sidecar` makes the new unknown-role
  regression fail; the original implementation is restored afterward.
- Full suite: `uv run pytest tests/ -q -n auto` — 14,697 passed, 67 skipped.
- Identifier and vocabulary searches repeat after the edit; no additional
  command-catalog or saved-evidence restatement requires a change.

## Review pass 2 — 2026-10-19

Claude session: `3c56b9e3-f8a9-485c-b657-4cc1c02f2b9a`.
Skill: `engineering:code-review`, `claude-sonnet-5-5`, high effort, report-only.
Reviewed HEAD: `551af0a75a316d49cf5781f0b9023946fcf558d9`.
Scope: the complete `55297a7c0...551af0a75` change, including all repairs and
the first review's dispositions.

**Verdict: no remaining actionable findings.** The reviewer verifies selection,
qualification, freshness, read-only behavior, exit semantics, producer evidence
limits, command registration and catalogs, bookkeeping, and test coverage.
It verifies C2's existing backlog pointer and accepts the per-item decisions.
It also checks the selective README/command-guide synopses and does not treat
their omission as a defect: those synopses omit `convergence` as well, while
the generated reference and the complete catalogs include `gate-status`.

This is a static review; the child session's pytest attempt is denied. Test
execution evidence comes from the driving session's completed 14,697-pass
full suite and the mutation check recorded above. There are no open findings
or pending dispositions from either pass.

## Convergence status

**Converged after two Claude Code review passes.** Pass 1's confirmed gaps
are repaired or explicitly dispositioned; pass 2 reviews the latest committed
implementation snapshot and finds no remaining actionable defect. This meets
the repository's clean-review exit. No further code change follows that
review; this final record update only records its result. Changes remain
local on `direct/gate-status`; no push or PR is authorized.
