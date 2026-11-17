#!/usr/bin/env bash
# Walk the demo branches without typing branch names.
#   ./step.sh            show the current step's card
#   ./step.sh next|prev  move one baked checkpoint, instantly
#   ./step.sh goto N     jump to step N (1-8)
#   ./step.sh transcript print the baked console output for this step
#   ./step.sh live       branch off the PREVIOUS checkpoint to run this step for real
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

branches=()
while IFS= read -r b; do branches+=("$b"); done < <(git for-each-ref --format='%(refname:short)' 'refs/heads/demo/*' | sort -t/ -k2 -n)
cur="$(git rev-parse --abbrev-ref HEAD)"
idx=-1
for i in "${!branches[@]}"; do [ "${branches[$i]}" = "${cur/#live\//demo/}" ] && idx=$i; done

go() {
  [ -z "$(git status --porcelain)" ] || { echo "working tree not clean; commit or discard first" >&2; exit 1; }
  git checkout -q "${branches[$1]}"; cat DEMO.md
}

case "${1:-show}" in
  show) [ "$idx" -ge 0 ] || { echo "not on a demo branch ($cur)"; exit 1; }; cat DEMO.md ;;
  next) [ "$idx" -lt $((${#branches[@]} - 1)) ] || { echo "already at the last step"; exit 1; }; go $((idx + 1)) ;;
  prev) [ "$idx" -gt 0 ] || { echo "already at the first step"; exit 1; }; go $((idx - 1)) ;;
  goto) n="${2:?usage: goto N}"; [ "$n" -ge 1 ] && [ "$n" -le "${#branches[@]}" ] || { echo "N is 1-${#branches[@]}"; exit 1; }; go $((n - 1)) ;;
  transcript) cat DEMO.transcript.txt ;;
  live)
    case "$cur" in live/*) echo "already on $cur; discard its changes (git checkout -f demo/N-name), then ./step.sh goto N" >&2; exit 1;; esac
    [ "$idx" -ge 0 ] || { echo "not on a demo branch ($cur)"; exit 1; }
    [ "$idx" -gt 0 ] || { echo "step 1 has no live command; it is authored with an assistant"; exit 1; }
    [ -z "$(git status --porcelain)" ] || { echo "working tree not clean" >&2; exit 1; }
    name="${branches[$idx]#demo/}"
    git show-ref --verify --quiet "refs/heads/live/$name" && { echo "live/$name already exists; delete it first: git branch -D live/$name" >&2; exit 1; }
    git checkout -q "${branches[$((idx - 1))]}"
    git checkout -q -b "live/$name"
    echo "On live/$name, starting from the state step $idx left. Run this step's command from the card:"
    echo; git show "demo/$name:DEMO.md" | sed -n '/^## Live command/,/^## /p' | sed '$d'
    echo "Compare afterwards:  git diff --stat demo/$name live/$name -- . ':!DEMO.md' ':!DEMO.transcript.txt'" ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
