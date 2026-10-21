#!/usr/bin/env bash
# Point this clone's git hooks at the tracked scripts/hooks/ directory.
# Idempotent and per-clone (writes local git config, nothing global).
#
#   ./scripts/hooks/install.sh
#
# Uninstall with: git config --unset core.hooksPath
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

chmod +x scripts/hooks/pre-push
chmod +x scripts/hooks/pre-commit
git config core.hooksPath scripts/hooks

echo "Installed: core.hooksPath -> scripts/hooks"
echo "The pre-push hook now runs the full parallel test suite before every push."
echo "The pre-commit hook now scans staged changes for likely secrets."
