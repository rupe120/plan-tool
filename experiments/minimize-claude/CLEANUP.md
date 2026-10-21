# Cleanup plan — minimize-Claude experiment artifacts

The Opp 3 experiment produced scratch outputs (plan files, isolated
manifests, per-run seed copies) and local run logs. This documents what to
keep vs remove and ships a safe script (`cleanup.sh`, dry-run by default).

## KEEP (deliverables — do NOT remove)

- **Code**: the Opp 3 flag + instrumentation in `plan_tool/create.py`,
  `plan_tool/cli/authoring.py`, and tests in `tests/test_create.py`; the
  regenerated `docs/cli/create.md`.
- **`scripts/analyze_run_log.py`** — reusable run-log analyzer.
- **`experiments/minimize-claude/LESSONS.md`** — methodology + findings.
- **This file (`CLEANUP.md`) and `cleanup.sh`.**
- **The 3 real plans** under `docs/implementation-plans/` (merge-steps-
  executor, escalate-structural-findings-to-split, step-granularity-
  advisor) and their entries in the real `.plan-tool/plans.json`. These
  were the originally-requested deliverables, created with un-instrumented
  baseline behavior; the experiment never polluted the real manifest
  (isolated manifests were used).
- **The 5 seeds** in `plan-seeds/` (the two `minimize-claude-*` plus the
  pre-existing ones).
- **Run logs** `.plan-tool/runs/{instr-*,ab-*}` — kept by default as the
  evidence behind LESSONS.md (tiny JSONL). Remove only with `--purge-logs`.

## REMOVE (regenerable scratch)

- `experiments/minimize-claude/{plans,plans-ab,runseeds,seeds,manifest,manifest-ab}/`
  — scratch plan outputs, isolated manifests, per-run + canonical seed
  copies.
- `plan-seeds/archive/archive/` — doubly-archived seed cruft created when
  the experiment re-fed already-archived seeds.
- `.plan-tool/checkpoints/{instr-*,ab-*}/` — experiment checkpoints
  (already discarded on clean completion; only empty dirs linger).

## Optional (with `--purge-logs`)

- `.plan-tool/runs/{instr-*,ab-*}/` — the experiment run logs. Drop these
  only if you don't need to re-run `analyze_run_log.py` against the raw
  evidence; the analyzed numbers are preserved in LESSONS.md.

## How to run

```bash
# dry-run (default): prints exactly what would be removed
bash experiments/minimize-claude/cleanup.sh

# execute the scratch removal (keeps run logs as evidence)
bash experiments/minimize-claude/cleanup.sh --force

# also remove the experiment run logs + checkpoints
bash experiments/minimize-claude/cleanup.sh --force --purge-logs
```

All targets are untracked/local, so cleanup touches nothing in git history
and nothing the real plan workflow depends on.
