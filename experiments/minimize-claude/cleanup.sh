#!/usr/bin/env bash
# Cleanup for the minimize-Claude experiment scratch. See CLEANUP.md.
# Dry-run by default; pass --force to delete, --purge-logs to also drop the
# experiment run logs + checkpoints. Safe: only touches untracked/local scratch.
set -euo pipefail

FORCE=0
PURGE_LOGS=0
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    --purge-logs) PURGE_LOGS=1 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

# Resolve repo root from this script's location (experiments/minimize-claude/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Scratch always removed.
TARGETS=(
  "experiments/minimize-claude/plans"
  "experiments/minimize-claude/plans-ab"
  "experiments/minimize-claude/runseeds"
  "experiments/minimize-claude/seeds"
  "experiments/minimize-claude/manifest"
  "experiments/minimize-claude/manifest-ab"
  "plan-seeds/archive/archive"
)
# Experiment checkpoints (slug-prefixed).
for d in .plan-tool/checkpoints/instr-* .plan-tool/checkpoints/ab-*; do
  [ -e "$d" ] && TARGETS+=("$d")
done
# Run logs only with --purge-logs.
if [ "$PURGE_LOGS" -eq 1 ]; then
  for d in .plan-tool/runs/instr-* .plan-tool/runs/ab-*; do
    [ -e "$d" ] && TARGETS+=("$d")
  done
fi

action="WOULD REMOVE"
[ "$FORCE" -eq 1 ] && action="REMOVING"
for t in "${TARGETS[@]}"; do
  if [ -e "$t" ]; then
    echo "$action  $t"
    [ "$FORCE" -eq 1 ] && rm -rf "$t"
  fi
done

if [ "$FORCE" -eq 0 ]; then
  echo
  echo "(dry-run) re-run with --force to delete; add --purge-logs to also drop run logs."
fi
