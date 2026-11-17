#!/usr/bin/env bash
# Build the disposable getting-started demo repository: one cumulative branch
# per pipeline step (demo/1-seed ... demo/8-code-review). See README.md.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER=".plan-tool-demo-repo"
STEPS=(1-seed 2-plan 3-bare-audit 4-detail 5-detail-audit 6-run 7-reconcile-code 8-code-review)

usage() { echo "usage: build.sh [target-dir] [--force]   (default: \$PLAN_TOOL_DEMO_DIR or ~/plan-tool-getting-started-demo)"; }

target="${PLAN_TOOL_DEMO_DIR:-$HOME/plan-tool-getting-started-demo}"
force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -h|--help) usage; exit 0 ;;
    *) target="$arg" ;;
  esac
done

case "$target" in /*) abs_target="$target" ;; *) abs_target="$PWD/$target" ;; esac
probe="$abs_target"
while [ ! -d "$probe" ]; do probe="$(dirname "$probe")"; done
here_top="$(git -C "$probe" rev-parse --show-toplevel 2>/dev/null || true)"
kit_top="$(git -C "$KIT" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$here_top" ] && [ "$here_top" = "$kit_top" ]; then
  echo "refusing: $target would sit inside the plan-tool checkout" >&2; exit 2
fi

if [ -e "$target" ]; then
  if [ "$force" -eq 1 ] && [ -f "$target/$MARKER" ]; then
    rm -rf "$target"
  else
    echo "refusing: $target exists (rebuild with --force; only a directory this script created is removed)" >&2
    exit 2
  fi
fi

mkdir -p "$target"
cd "$target"
git init -q -b main
git config user.name "Plan Tool Demo"
git config user.email "demo@example.invalid"
touch "$MARKER"
cp -R "$KIT/fixtures/base/." .
cp "$KIT/step.sh" step.sh && chmod +x step.sh
git add -A && git commit -q -m "Scaffold the todo CLI"

for step in "${STEPS[@]}"; do
  git checkout -q -b "demo/$step"
  [ -d "$KIT/fixtures/$step/files" ] && cp -R "$KIT/fixtures/$step/files/." .
  cp "$KIT/fixtures/$step/DEMO.md" DEMO.md
  cp "$KIT/fixtures/$step/transcript.txt" DEMO.transcript.txt
  git add -A && git commit -q -m "demo: state after ${step#*-}"
done

git checkout -q demo/1-seed
echo "Built $target"
git branch --list 'demo/*'
echo "Start: cd $target && cat DEMO.md   (then ./step.sh next)"
