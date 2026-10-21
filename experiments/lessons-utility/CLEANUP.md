# Cleanup plan — lessons-utility experiment artifacts

The A/B conditions produce scratch outputs (plan files, isolated manifests,
copied/sliced lessons corpora) and local run logs. This documents what to keep
vs remove and ships a safe script (`cleanup.sh`, dry-run by default).

## KEEP (deliverables — do NOT remove)

- **`DESIGN.md`, `RESEARCH.md`, `LESSONS.md`, `README.md`** — the experiment,
  the survey, the findings, the index.
- **`measure_lessons.py`** — reusable volume/salience tool (read-only, stdlib).
- **This file and `cleanup.sh`.**
- **Run logs** `.plan-tool/runs/lutil-*` — evidence behind LESSONS.md (tiny
  JSONL). Removed only with `--purge-logs`.
- **The real lessons store** `.plan-tool/lessons/` — NEVER touched by cleanup;
  the experiment only ever reads it and writes *copies* into scratch.

## REMOVE (regenerable scratch)

- `experiments/lessons-utility/scratch/` — sliced/inflated corpora, copied
  `.plan-tool/lessons/` trees, per-condition seeds and outputs.
- Isolated manifests + plan outputs created under `--output-dir`.
- `.plan-tool/checkpoints/lutil-*/` — experiment checkpoints (only empty dirs
  linger after clean completion).

## Optional (with `--purge-logs`)

- `.plan-tool/runs/lutil-*/` — experiment run logs. Drop only if you don't need
  to re-run `analyze_run_log.py` against the raw evidence; analyzed numbers are
  preserved in LESSONS.md.

## How to run

```bash
# dry-run (default): prints exactly what would be removed
bash experiments/lessons-utility/cleanup.sh

# execute the scratch removal (keeps run logs as evidence)
bash experiments/lessons-utility/cleanup.sh --force

# also remove the experiment run logs + checkpoints
bash experiments/lessons-utility/cleanup.sh --force --purge-logs
```

All targets are untracked/local scratch; cleanup touches nothing in git history,
nothing the real plan workflow depends on, and never the real lessons store.
