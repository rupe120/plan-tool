"""Repo-wide duplication guards.

Two complementary invariants, because a count alone protects only one
direction:

* :func:`test_no_exact_duplicate_functions` fails when a **new** duplicate
  appears — the regression guard for the 2026-08-02 sweep that took
  ``plan_tool/`` from 6 duplicate groups to 0.
* :class:`TestDeliberatelySeparate` fails when something on BACKLOG #79's
  do-not-merge list **disappears** — i.e. when a well-meaning cleanup folds
  two helpers that are duplicated on purpose. Those live below the line
  threshold, so the count guard cannot see them.

Identity is established by normalizing away docstrings, function names, and
parameter names (including their uses in the body — renaming only the
signature under-reports, which is how a fourth copy of the atomic writer hid
for months). Scope is ``plan_tool/`` only: duplication in ``tests/`` is
frequently deliberate so each failure reads standalone.
"""

from __future__ import annotations

import ast
import collections
import copy
import hashlib
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "plan_tool"

# Bodies shorter than this are ignored: two-line helpers collide by
# coincidence (``return x.strip() if isinstance(x, str) else ""``) and the
# genuinely-duplicated short ones are all deliberate — see
# ``TestDeliberatelySeparate``, which covers them by name instead.
MIN_BODY_LINES = 4

# Deliberate duplicates allowed above the threshold. Empty today.
#
# This is the anti-creep escape hatch, and it is a first-class outcome, not a
# cop-out. CLAUDE.md's rule is that a consolidation opportunity found mid-task
# gets *filed*, not taken — so this test must never force a merge into an
# unrelated change. It asks for a decision, and "not now" is one of the
# answers. Add the entry, state the reason, keep going.
#
# Two kinds of reason, and they route differently:
#   * correct forever (contracts differ, a seam must stay) -> also add the
#     do-not-merge bullet to BACKLOG #79.
#   * worth merging, just not inside this change -> file a BACKLOG entry per
#     the anti-creep rule and cite it here.
# An allowlist entry with neither is a disabled test.
#
#   key:   frozenset of "<module>:<function>" strings
#   value: why the duplication stands, and where it is tracked
ALLOWED_DUPLICATE_GROUPS: dict[frozenset[str], str] = {
    frozenset(
        {
            "plan_tool/roadmap_revision_publish.py:_release_writer_lock",
            "plan_tool/telemetry.py:_release_append_lock",
        }
    ): "not yet merged, not deliberately separate; see "
    "DO_NOT_MERGE['advisory-lock-release-boundaries'] below",
}


class _StripDocstring(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
        return node


class _RenameParams(ast.NodeTransformer):
    """Alpha-rename parameters throughout the body, not just the signature."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self.mapping:
            node.id = self.mapping[node.id]
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        if node.arg in self.mapping:
            node.arg = self.mapping[node.arg]
        return node


def _fingerprint(node: ast.FunctionDef) -> tuple[str, ast.FunctionDef]:
    fn = copy.deepcopy(node)
    _StripDocstring().visit(fn)
    fn.name = "F"
    args = fn.args
    every = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    _RenameParams({a.arg: f"a{i}" for i, a in enumerate(every)}).visit(fn)
    text = ast.dump(fn, include_attributes=False)
    return hashlib.sha1(text.encode()).hexdigest()[:12], fn


def _scan() -> dict[str, list[tuple[str, str, int, int]]]:
    """hash -> [(relpath, funcname, lineno, body_lines)] for every function."""
    groups: dict[str, list[tuple[str, str, int, ast.FunctionDef]]] = collections.defaultdict(list)
    for path in sorted(PACKAGE.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - defensive
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            digest, normalized = _fingerprint(node)
            groups[digest].append((rel, node.name, node.lineno, normalized))
    return {
        digest: [
            (rel, name, lineno, ast.unparse(normalized).count("\n") + 1)
            for rel, name, lineno, normalized in members
        ]
        for digest, members in groups.items()
        if len(members) > 1
    }


def test_no_exact_duplicate_functions() -> None:
    """No two functions in ``plan_tool/`` share a body above the threshold.

    Baseline 2026-08-02: 0 groups (was 6 groups / 7 redundant copies before
    the sweep). Because the baseline is 0 and enforced continuously, a
    failure is always duplication introduced by *this* change — never a
    pre-existing pair you happened to walk past. That is what keeps this
    test compatible with CLAUDE.md's anti-creep rule: the rule governs
    duplication you **find** (file it), this governs duplication you **add**
    (don't, or say why).

    It never demands the merge. ``ALLOWED_DUPLICATE_GROUPS`` is the
    supported answer when consolidating would drag an unrelated change into
    scope.
    """
    offenders = []
    for members in _scan().values():
        if len(members) < 2 or members[0][3] < MIN_BODY_LINES:
            continue
        key = frozenset(f"{rel}:{name}" for rel, name, _, _ in members)
        if key in ALLOWED_DUPLICATE_GROUPS:
            continue
        offenders.append(
            "  "
            + " == ".join(f"{rel}:{line} {name}" for rel, name, line, _ in members)
        )
    assert not offenders, (
        f"{len(offenders)} duplicate function group(s) with >= {MIN_BODY_LINES}-line "
        "bodies (baseline is 0):\n" + "\n".join(offenders) + "\n\n"
        "Two supported answers, both fine:\n"
        "  * use the helper that already exists, if that is a small edit; or\n"
        "  * add the group to ALLOWED_DUPLICATE_GROUPS with a reason, and file "
        "the consolidation per CLAUDE.md's anti-creep rule.\n"
        "Merging is NOT required — do not drag a refactor into an unrelated "
        "change. Identical bodies tell you where to look, never what the "
        "remedy is."
    )


# Each entry: label -> (reason, [(module, function), ...]).
# These are duplicated *on purpose*. Merging any of them is a regression;
# the reason is quoted back in the failure message so it survives the
# reader who finds this test in the way. Full rationale: BACKLOG #79.
DO_NOT_MERGE: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "advisory-lock-release-boundaries": (
        "the release bodies are policy-free — each just dispatches on "
        "implementation ('fcntl'/'msvcrt') and unlocks; the real difference "
        "(roadmap publication requires an exclusive writer lock and rejects "
        "unavailable lock support, telemetry treats its append lock as "
        "best-effort) lives entirely in the paired _acquire_* functions, "
        "which stay separate. A shared _release_advisory_lock leaf is "
        "plausible; not done here — filed as BACKLOG #273",
        [
            ("plan_tool/roadmap_revision_publish.py", "_release_writer_lock"),
            ("plan_tool/telemetry.py", "_release_append_lock"),
        ],
    ),
    "invoker-seam": (
        "the per-orchestrator invoker seam that tests/conftest.py's autouse "
        "gate overrides one module at a time; unifying it removes the seam",
        [
            ("plan_tool/annotate.py", "shell_annotate_invoker"),
            ("plan_tool/create.py", "shell_claude_invoker"),
            ("plan_tool/detail.py", "shell_detail_invoker"),
            ("plan_tool/jira.py", "shell_jira_invoker"),
            ("plan_tool/review.py", "shell_review_invoker"),
            ("plan_tool/roadmap.py", "shell_roadmap_invoker"),
        ],
    ),
    "backend-argv-pairs": (
        "batch and streaming argv are two distinct contract points pinned by "
        "docs/reference/contracts/codex-cli.md and docs/reference/contracts/cursor-agent-cli.md; "
        "they are identical today and are expected to diverge",
        [
            ("plan_tool/backend.py", "_claude_batch_argv"),
            ("plan_tool/backend.py", "_claude_streaming_argv"),
            ("plan_tool/backend.py", "_codex_batch_argv"),
            ("plan_tool/backend.py", "_codex_streaming_argv"),
            ("plan_tool/backend.py", "_cursor_batch_argv"),
            ("plan_tool/backend.py", "_cursor_streaming_argv"),
        ],
    ),
    "atomic-write-contracts": (
        "three different durability contracts: atomic_write_text is atomic "
        "but not durable and mkdirs; durable_write_text fsyncs and does not; "
        "lessons' uses mkstemp without fsync",
        [
            ("plan_tool/fileio.py", "atomic_write_text"),
            ("plan_tool/fileio.py", "durable_write_text"),
            ("plan_tool/lessons.py", "_atomic_write_text"),
        ],
    ),
    "utc-timestamps": (
        "per-artifact wire-format choices, not one utility — "
        "review_persistence already emits a trailing Z where the others emit "
        "a +00:00 offset, and several feed drift-guarded persisted schemas",
        [
            ("plan_tool/annotate.py", "_utc_timestamp"),
            ("plan_tool/checkpoint.py", "_utc_now_iso"),
            ("plan_tool/run_log.py", "utc_now_iso"),
            ("plan_tool/telemetry.py", "_utc_now_iso"),
            ("plan_tool/review_persistence.py", "_utc_now_iso"),
        ],
    ),
    "archive-move-policies": (
        "deliberately opposite failure policies: scope_out's raises so the "
        "apply journal rolls back, detail's is best-effort so a permissions "
        "error cannot derail the write the caller is about to perform",
        [
            ("plan_tool/scope_out.py", "_archive_file_strict"),
            ("plan_tool/detail.py", "_archive_existing_detail"),
        ],
    ),
    "file-hash-contracts": (
        "different contracts — a whole-file digest returning Optional[str] vs "
        "a fold-into-a-caller's-hash returning None",
        [
            ("plan_tool/drift_detection.py", "compute_content_hash"),
            ("plan_tool/review_persistence.py", "_hash_file_into"),
        ],
    ),
    "rate-limit-can-prompt": (
        "the duplication IS the injected seam — both are passed as "
        "run_with_rate_limit_recovery(can_prompt=...), and caller-side "
        "concerns there stay injected rather than unified into the leaf",
        [
            ("plan_tool/launcher.py", "_can_prompt_on_rate_limit"),
            ("plan_tool/shell.py", "_can_prompt_on_rate_limit"),
        ],
    ),
    "soft-str-family": (
        "_soft_str is half of a local two-function family whose sibling "
        "_soft_str_list is not duplicated; extracting one half orphans it",
        [
            ("plan_tool/foundational_logic.py", "_soft_str"),
            ("plan_tool/foundational_logic.py", "_soft_str_list"),
            ("plan_tool/jira.py", "_optional_stripped_str"),
        ],
    ),
}


def _defines(relpath: str, name: str) -> bool:
    path = REPO_ROOT / relpath
    if not path.is_file():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover - defensive
        return False
    return any(
        isinstance(n, ast.FunctionDef) and n.name == name for n in ast.walk(tree)
    )


class TestDeliberatelySeparate:
    """Helpers that look duplicated and must stay that way (BACKLOG #79)."""

    @pytest.mark.parametrize("label", sorted(DO_NOT_MERGE))
    def test_still_separate(self, label: str) -> None:
        reason, members = DO_NOT_MERGE[label]
        missing = [f"{rel}:{name}" for rel, name in members if not _defines(rel, name)]
        assert not missing, (
            f"{label}: {len(missing)} of {len(members)} deliberately-separate "
            f"definitions are gone — {', '.join(missing)}.\n\n"
            f"These are duplicated on purpose: {reason}.\n\n"
            "If the removal is intentional, update BACKLOG #79's do-not-merge "
            "list and this table together — and say in the commit why the "
            "reason above no longer holds. A rename lands here too; re-point "
            "the entry rather than deleting it."
        )
