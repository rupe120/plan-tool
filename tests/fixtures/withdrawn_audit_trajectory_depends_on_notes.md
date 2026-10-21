---
title: Audit Trajectory Instrumentation (depends_on_notes fixture)
intent: BACKLOG #253 proof fixture — not an executable plan.
status: planning
priority: medium
steps:
- id: 1
  title: Add hand-resolution telemetry event kind, recorder, and reader
  files:
  - plan_tool/telemetry.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  - tests/test_data_contract.py
- id: 2
  title: Add sidecar content-diff helper (plan/code fingerprint comparison)
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
- id: 3
  title: Add sidecar-to-sidecar finding-id diff that infers hand-resolutions
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
- id: 4
  title: Record inferred hand-resolutions when a completeness audit saves its sidecar
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: consumes `record_hand_resolution` from step 1
    2: consumes sidecar fingerprint diff gate from step 2
    3: consumes sidecar finding-id diff from step 3
- id: 5
  title: Feed hand-resolution events into analyze_finding_drift calibration evidence
  files:
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  depends_on:
  - 1
- id: 6
  title: Widen recurring_regions to conceptual sources and split by finding id
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  depends_on:
  - 3
- id: 7
  title: Replay jira-grade-01 sidecar history as a fixture
  files:
  - tests/test_convergence_diagnosis.py
  - tests/test_telemetry_analysis.py
  creates:
  - tests/fixtures/convergence/jira-grade-01-hand-resolution-history.json
  - tests/fixtures/convergence/id-stability-schema-versions.json
  depends_on:
  - 4
  - 6
- id: 8
  title: Update architecture and flow docs and close out BACKLOG #172
  files:
  - docs/ARCHITECTURE.md
  - docs/AUDIT_FLOW.md
  - CLAUDE.md
  - BACKLOG.md
  depends_on:
  - 7
---
# Audit Trajectory Instrumentation (depends_on_notes fixture)

BACKLOG #253 step 5 proof fixture derived from withdrawn `audit-trajectory-instrumentation`; not a plan to run.
