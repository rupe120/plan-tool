"""Post-apply scope guard for iterative correctness/completeness loops.

Wraps ``apply_finding`` so edits to files outside the plan's declared
scope are detected via filesystem snapshot/diff. The contract:

- **In scope** = the plan markdown file + each step's detail file +
  every entry in ``step.files`` (annotations like ``(new)`` are stripped).
- After ``apply_finding`` runs, any file that changed and is NOT in
  scope is classified by type:
  - **Documentation** (``.md``/``.txt``/``.rst``): always **kept**.
    Tracked separately as ``kept-documentation`` so the final report
    highlights doc drift for human review without blocking the loop.
  - **Code**: checked for "direct impact" — is the file's path or
    basename referenced in any in-scope file? If yes, the edit is
    **kept** (scope expanded by necessity, flagged ``kept-by-impact``).
    If no, the edit is **reverted** from a pre-snapshot and the
    finding is queued for compilation into a follow-up plan.
- The accumulated buffer of out-of-scope findings can be written to a
  new ``docs/implementation-plans/<N>-out-of-scope-findings-from-<slug>.md``
  via :func:`write_out_of_scope_plan` at end of loop. Code edits land
  in an actionable section; documentation edits land in an
  informational section.

Pure file I/O + heuristics. No claude shell-out, no first-party imports
beyond ``schema`` (for the ``Plan`` type) and ``launcher`` snapshot
helpers (reused for revert).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from plan_tool.pathutil import is_within, literal_path, normalize_declared_path
from plan_tool.launcher import _restore_text_files
from plan_tool.schema import Plan


def compute_in_scope_paths(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
) -> set[Path]:
    """Return absolute paths considered in-scope for the given plan.

    Union of the plan markdown file, every step's ``detail`` (when set),
    and every entry in ``step.all_files`` — the merged ``files`` (modified)
    plus ``creates`` (new) footprint (annotations like ``(new)`` /
    ``(delete)`` are stripped before resolving against ``repo_root``).
    Non-existent paths are still included — a step that declares a new
    or created file is in scope even before that file lands.
    """
    paths: set[Path] = {plan_path.resolve()}
    for step in plan.steps:
        if step.detail is not None:
            paths.add((repo_root / step.detail).resolve())
        for entry in step.all_files:
            clean = normalize_declared_path(entry)
            if clean:
                paths.add((repo_root / clean).resolve())
    return paths


def compute_plan_tool_artifact_paths(
    plan_path: Path,
    repo_root: Path,
) -> set[Path]:
    """Return plan-tool-owned artifact roots ignored by scope classification.

    These paths are runtime/reporting state that may be written by the
    iteration loop itself. They are deliberately separate from
    :func:`compute_in_scope_paths` so snapshot selection does not walk broad
    runtime directories like ``.plan-tool``.
    """
    paths: set[Path] = {(repo_root / ".plan-tool").resolve()}
    try:
        plan_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return paths
    plan_dir = plan_path.resolve().parent
    slug = plan_path.stem
    if "-" in slug:
        slug = slug.split("-", 1)[1]
    paths.add((plan_dir / "plan-details" / slug / "reports").resolve())
    return paths


def compute_drift_watched_paths(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
) -> set[Path]:
    """Return the in-scope paths that should be watched for live-edit
    drift, EXCLUDING the plan markdown and per-step detail files.

    The iteration loop's ``apply_finding`` step legitimately rewrites
    the plan and detail files -- watching them with the live-edit
    drift detector would false-positive on every successful iteration,
    naming the iteration's own edits as "drift." Implementation files
    declared in ``step.files`` should NOT change during an iteration
    loop (apply_finding doesn't touch code -- ``plan-tool run`` is
    the dedicated path for that), so a content change on a step.files
    entry (detected via SHA-256 hash, #31) is genuine user-side
    live-edit drift worth surfacing.

    This is the right ``watched_paths`` argument to pass to
    :func:`plan_tool.drift_detection.acquire_lock`. The broader
    :func:`compute_in_scope_paths` set remains the right input for
    :func:`compute_snapshot_dirs` (the scope guard's per-finding
    snapshot covers the full surface, since claude can wander
    anywhere during apply).
    """
    return compute_in_scope_paths(plan, plan_path, repo_root) - _plan_owned_paths(
        plan, plan_path, repo_root
    )


def build_file_to_step_map(
    plan: Plan, repo_root: Path,
) -> dict[Path, tuple[int, str]]:
    """Map every ``step.all_files`` entry (resolved absolute) to the owning
    step's ``(id, title)``.

    Used by drift warnings and claude-finding attribution so
    operator-facing output can name which step a flagged file belongs
    to. Covers both modified (``files``) and created (``creates``) paths.
    First-occurrence wins on duplicates -- in the unusual case
    where two steps declare the same file, attribution sticks with the
    earlier step. Entry annotations like ``(new)`` are
    stripped before resolving, matching :func:`compute_in_scope_paths`.

    Lives in ``scope_guard`` rather than ``review`` so it stays
    importable from any iteration-lock-adjacent code without pulling
    review.py's heavier dependency graph in.
    """
    mapping: dict[Path, tuple[int, str]] = {}
    for step in plan.steps:
        for entry in step.all_files:
            clean = normalize_declared_path(entry)
            if not clean:
                continue
            resolved = (repo_root / clean).resolve()
            if resolved not in mapping:
                mapping[resolved] = (step.id, step.title)
    return mapping


def _plan_owned_paths(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
) -> set[Path]:
    """Return the paths that the iteration loop's apply step
    legitimately edits: the plan markdown + every step's detail file
    (when set).
    """
    owned: set[Path] = {plan_path.resolve()}
    for step in plan.steps:
        if step.detail is not None:
            owned.add((repo_root / step.detail).resolve())
    return owned


def compute_snapshot_dirs(
    in_scope_paths: set[Path],
    repo_root: Path,
    *,
    max_depth: int = 3,
) -> list[Path]:
    """Heuristic: pick directories at depth ≤ ``max_depth`` under repo_root
    that contain in-scope files. These bound the snapshot scope without
    requiring a full-repo walk.

    For each in-scope path, take its parent (when the path looks like
    a file) or itself (when it's a dir), then truncate the
    repo-relative path to ``max_depth`` components and add the
    resulting directory. Returns sorted directories that exist on
    disk.
    """
    dirs: set[Path] = set()
    for p in in_scope_paths:
        anchor = (p.parent if p.suffix else p)
        try:
            anchor_rel = anchor.relative_to(repo_root)
        except ValueError:
            continue
        truncated = anchor_rel.parts[:max_depth]
        if truncated:
            dirs.add(repo_root / Path(*truncated))
    return sorted(d for d in dirs if d.is_dir())


def snapshot_subtrees(
    dirs: Iterable[Path],
    *,
    exclude_parts: frozenset[str] = frozenset(
        {".venv", ".pytest_cache", "dist", "__pycache__", ".git", "node_modules"}
    ),
    text_suffixes: frozenset[str] = frozenset(
        {".py", ".md", ".toml", ".json", ".yml", ".yaml", ".txt", ".cfg", ".ini"}
    ),
) -> dict[Path, Optional[str]]:
    """Snapshot text-file contents for every file under ``dirs``.

    ``exclude_parts`` filters out vendored/cache directories. Only
    files with extensions in ``text_suffixes`` are read — keeps the
    snapshot bounded and binary-safe. Returns a mapping suitable for
    :func:`plan_tool.launcher._restore_text_files`.
    """
    snap: dict[Path, Optional[str]] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if any(part in exclude_parts for part in p.parts):
                continue
            if p.suffix not in text_suffixes:
                continue
            try:
                snap[p.resolve()] = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    return snap


def diff_changed(
    pre: dict[Path, Optional[str]],
    post: dict[Path, Optional[str]],
) -> list[Path]:
    """Return paths whose content differs between pre and post snapshots."""
    changed: list[Path] = []
    for path in pre.keys() | post.keys():
        if pre.get(path) != post.get(path):
            changed.append(path)
    return sorted(changed)


SKILL_AGENT_ROOTS: tuple[str, ...] = (".agents", ".claude")


def classify_plan_scope(
    files: Iterable[Path],
    repo_root: Path,
) -> tuple[str, Path]:
    """Classify a set of files by whether they belong to a skill, an
    agent, or project code, and return the corresponding plans dir.

    Skill/agent roots checked: every entry in ``SKILL_AGENT_ROOTS``
    (currently ``.agents`` and ``.claude``).

    Returns ``(kind, dest_dir)`` where ``kind`` is one of:

    - ``"skill"`` — every file lives under
      ``<root>/skills/<name>/`` for one specific (root, name) pair;
      ``dest_dir`` is ``<repo_root>/<root>/skills/<name>/implementation-plans``.
    - ``"agent"`` — every file lives under ``<root>/<name>/`` for one
      specific (root, name) pair where ``<name>`` is not ``skills``;
      ``dest_dir`` is ``<repo_root>/<root>/<name>/implementation-plans``.
    - ``"project"`` — any file outside the configured roots, files
      span multiple skills/agents/roots, or no files were supplied;
      ``dest_dir`` is ``<repo_root>/docs/implementation-plans``.

    The plans dir is **not** created by this helper; callers do so
    when they need to write. The path is returned even when it
    doesn't exist on disk so callers can decide on creation policy.

    Callers that pass a buffer spanning multiple scopes should
    partition the buffer per-record (each record's files run through
    this helper individually) and emit one plan per distinct
    ``dest_dir`` -- see ``_emit_scope_guard_plan`` in ``cli.py``.
    """
    # (root, name) keys keep `.agents/skills/foo` and `.claude/skills/foo`
    # in different buckets even when they share a basename.
    skill_keys: set[tuple[str, str]] = set()
    agent_keys: set[tuple[str, str]] = set()
    has_project_file = False
    saw_any = False
    for f in files:
        saw_any = True
        try:
            rel = f.relative_to(repo_root)
        except ValueError:
            # File outside repo root — treat as project for safety.
            has_project_file = True
            continue
        parts = rel.parts
        if len(parts) >= 1 and parts[0] in SKILL_AGENT_ROOTS:
            root = parts[0]
            if len(parts) >= 3 and parts[1] == "skills":
                skill_keys.add((root, parts[2]))
            elif len(parts) >= 2 and parts[1] != "skills":
                agent_keys.add((root, parts[1]))
            else:
                # Bare ``<root>/<file>`` or ``<root>/skills/<file>`` (no
                # skill name) — treat as project; the user can sort it
                # out manually.
                has_project_file = True
        else:
            has_project_file = True
    project_dir = repo_root / "docs" / "implementation-plans"
    if has_project_file or not saw_any:
        return "project", project_dir
    if len(skill_keys) == 1 and not agent_keys:
        root, skill = next(iter(skill_keys))
        return (
            "skill",
            repo_root / root / "skills" / skill / "implementation-plans",
        )
    if len(agent_keys) == 1 and not skill_keys:
        root, agent = next(iter(agent_keys))
        return "agent", repo_root / root / agent / "implementation-plans"
    # Mixed scope across multiple skills, agents, or roots — punt to
    # project; the caller's per-record partitioning is what actually
    # splits a mixed buffer into separate plans.
    return "project", project_dir


def is_referenced_by_in_scope(
    target: Path,
    in_scope_paths: set[Path],
    repo_root: Path,
) -> bool:
    """True if any in-scope file mentions ``target`` by path or basename.

    Heuristic for the "direct impact" exception: an out-of-scope edit
    is kept (not reverted) when at least one in-scope file references
    the target's repo-relative path or basename. Misses semantic
    impact that doesn't appear in text (e.g., dynamic imports), but
    covers the typical case where an in-scope module imports an
    out-of-scope module by name.
    """
    target_rel = literal_path(target, repo_root)
    needles = (target_rel, target.name)
    for in_scope in in_scope_paths:
        if not in_scope.exists():
            continue
        try:
            content = in_scope.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(n in content for n in needles):
            return True
    return False


DOCUMENTATION_SUFFIXES: frozenset[str] = frozenset({".md", ".txt", ".rst", ".adoc"})


def is_documentation(path: Path) -> bool:
    """True when ``path`` has a documentation suffix (kept on out-of-scope edits)."""
    return path.suffix.lower() in DOCUMENTATION_SUFFIXES


@dataclass
class OutOfScopeRecord:
    """One out-of-scope finding deferred to a follow-up plan or flagged.

    ``impact_status`` is one of:

    - ``"reverted"`` — code edit with no in-scope reference; reverted
      to the pre-snapshot. Action: include in the new plan's
      actionable section.
    - ``"kept-by-impact"`` — code edit referenced by at least one
      in-scope file; kept as scope-expansion-by-necessity. Action:
      flag in the new plan for human review.
    - ``"kept-documentation"`` — out-of-scope ``.md``/``.txt``/``.rst``
      edit; always kept by policy. Action: list in the informational
      section of the final report.
    """

    finding_id: str
    finding_body: str
    step_id: Optional[int]
    out_of_scope_files: list[Path]
    impact_status: str
    diff_preview: str = ""


@dataclass
class ScopeGuardBuffer:
    """Accumulator passed across multiple ``apply_finding`` calls."""

    records: list[OutOfScopeRecord] = field(default_factory=list)

    def add(self, record: OutOfScopeRecord) -> None:
        self.records.append(record)

    def is_empty(self) -> bool:
        return not self.records


@dataclass
class ReconcileScopeGuard:
    """Per-finding scope-guard state for ``_iterate_reconcile_loop``.

    Bundles the parameters and accumulators that the reconcile-mode
    ``action_fn`` needs to wrap each ``apply_finding`` dispatch with
    its own pre/post snapshot + ``evaluate_apply_scope`` +
    ``revert_out_of_scope`` + ``scope_buffer.add``. Mirrors the
    per-finding pattern ``cmd_completeness`` uses inline.

    Fields:

    - ``scope_dirs``: list of in-scope subtree roots; fed to
      ``snapshot_subtrees`` for the pre/post pair.
    - ``in_scope``: set of in-scope absolute paths (plan + detail +
      step.files).
    - ``scope_buffer``: the loop-wide accumulator. Records added here
      surface in the end-of-loop ``_emit_scope_guard_plan`` stub.
    - ``file_to_step``: map for ``_print_attributed_files`` attribution
      in the kept/reverted stderr lines.
    - ``repo_root``: passed through to attribution + ``evaluate_apply_scope``.
    - ``apply_pre_snapshots``: each ``apply_finding`` dispatch appends its
      ``result.pre_snapshot`` here so the post-walk drift halt's
      collision-sidecar wiring has the (first-seen-per-path) baseline
      to restore against. Cleared by callers if needed across iterations.

    Per-finding drift halt fields:

    - ``iter_lock``: the iteration lock to query via ``check_drift``.
      Typed as ``object`` to dodge the
      ``scope_guard ↔ drift_detection`` import cycle (drift_detection
      already imports ``build_file_to_step_map`` from this module).
      ``None`` keeps the per-finding drift checks inert.
    - ``allow_drift``: when ``True``, per-finding pre/post drift
      checks are skipped (mirrors the ``--allow-drift`` CLI flag).
    - ``collision_sidecar_enabled``: when ``True`` (default), post-
      apply drift fires the change-collision sidecar + pause-for-merge
      flow against the finding's ``apply_result.pre_snapshot``; when
      ``False`` (``--no-collision-sidecar``), the halt path falls
      through to legacy auto-reconcile + scope-guard plan emit.
    """

    scope_dirs: list[Path]
    in_scope: set[Path]
    scope_buffer: ScopeGuardBuffer
    file_to_step: dict
    repo_root: Path
    ignored_artifact_paths: set[Path] = field(default_factory=set)
    apply_pre_snapshots: list[dict[Path, Optional[str]]] = field(
        default_factory=list,
    )
    iter_lock: Optional[object] = None
    allow_drift: bool = False
    collision_sidecar_enabled: bool = True

    def record_apply(
        self, pre_snapshot: dict[Path, Optional[str]],
    ) -> None:
        """Record an ``apply_finding`` call's ``pre_snapshot`` so the
        post-walk drift halt can compose a merged baseline for the
        collision-sidecar's ``handle_drift_collision`` call.

        First-seen content per path wins on merge -- subsequent
        applies' "pre" state already carries the earlier applies'
        edits, so they don't reflect the iteration's true start state.
        """
        self.apply_pre_snapshots.append(dict(pre_snapshot))

    def merged_apply_pre_snapshot(
        self,
    ) -> dict[Path, Optional[str]]:
        """Compose a single Path → Optional[str] dict covering every
        file touched by any recorded apply, with the FIRST-SEEN
        pre-content per path.

        ``save_collision_sidecars`` skips paths whose current content
        matches the snapshot, so this composition is safe even when
        the merged baseline is over-broad (extra unchanged paths
        produce no sidecars).
        """
        merged: dict[Path, Optional[str]] = {}
        for snap in self.apply_pre_snapshots:
            for path, content in snap.items():
                if path not in merged:
                    merged[path] = content
        return merged


def evaluate_apply_scope(
    *,
    finding_id: str,
    finding_body: str,
    step_id: Optional[int],
    pre_snapshot: dict[Path, Optional[str]],
    post_snapshot: dict[Path, Optional[str]],
    in_scope_paths: set[Path],
    repo_root: Path,
    ignored_artifact_paths: Optional[set[Path]] = None,
) -> list[OutOfScopeRecord]:
    """Inspect a pre/post snapshot pair for out-of-scope edits.

    Returns a list (possibly empty) of records, one per impact bucket
    that was triggered. Splitting by bucket keeps the caller's revert
    logic simple: only records with ``impact_status == 'reverted'``
    need to be undone via :func:`revert_out_of_scope`. Code edits go
    through the in-scope-reference check; documentation edits always
    bypass the check and are tracked as ``kept-documentation``.
    """
    changed = diff_changed(pre_snapshot, post_snapshot)
    ignored_artifact_paths = ignored_artifact_paths or set()
    out_of_scope_all = [
        p
        for p in changed
        if p not in in_scope_paths
        and not any(is_within(p, scoped) for scoped in in_scope_paths)
        and not any(is_within(p, ignored) for ignored in ignored_artifact_paths)
    ]
    if not out_of_scope_all:
        return []

    doc_files = [p for p in out_of_scope_all if is_documentation(p)]
    code_files = [p for p in out_of_scope_all if not is_documentation(p)]

    code_keep: list[Path] = []
    code_revert: list[Path] = []
    for p in code_files:
        if is_referenced_by_in_scope(p, in_scope_paths, repo_root):
            code_keep.append(p)
        else:
            code_revert.append(p)

    def _build_record(
        bucket_files: list[Path], status: str
    ) -> Optional[OutOfScopeRecord]:
        if not bucket_files:
            return None
        preview_lines: list[str] = []
        for p in bucket_files[:3]:
            rel = literal_path(p, repo_root)
            pre_text = pre_snapshot.get(p) or ""
            post_text = post_snapshot.get(p) or ""
            delta = abs(len(post_text) - len(pre_text))
            preview_lines.append(
                f"  - {rel} ({len(pre_text)} → {len(post_text)} bytes; Δ{delta})"
            )
        if len(bucket_files) > 3:
            preview_lines.append(f"  - … and {len(bucket_files) - 3} more")
        return OutOfScopeRecord(
            finding_id=finding_id,
            finding_body=finding_body,
            step_id=step_id,
            out_of_scope_files=bucket_files,
            impact_status=status,
            diff_preview="\n".join(preview_lines),
        )

    records: list[OutOfScopeRecord] = []
    rec = _build_record(code_revert, "reverted")
    if rec is not None:
        records.append(rec)
    rec = _build_record(code_keep, "kept-by-impact")
    if rec is not None:
        records.append(rec)
    rec = _build_record(doc_files, "kept-documentation")
    if rec is not None:
        records.append(rec)
    return records


def revert_out_of_scope(
    record: OutOfScopeRecord,
    pre_snapshot: dict[Path, Optional[str]],
) -> None:
    """Restore the out-of-scope files in ``record`` from pre-snapshot.

    No-op when ``record.impact_status == 'kept-by-impact'``.
    """
    if record.impact_status != "reverted":
        return
    subset = {p: pre_snapshot.get(p) for p in record.out_of_scope_files}
    _restore_text_files(subset)


_STATUS_SECTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "reverted",
        "Reverted code edits — actionable follow-up",
        "These code edits were reverted because no in-scope file references "
        "the touched path. They represent genuine out-of-scope work that "
        "should be planned and executed separately.",
    ),
    (
        "kept-by-impact",
        "Kept code edits — scope expanded by necessity",
        "These code edits were kept because at least one in-scope file "
        "references the touched path. Human review recommended to confirm "
        "the scope expansion was appropriate.",
    ),
    (
        "kept-documentation",
        "Documentation edits — informational",
        "These ``.md`` / ``.txt`` / ``.rst`` edits were kept by policy "
        "(documentation never goes through the scope-revert gate). Listed "
        "here so doc drift outside the plan's declared scope is visible.",
    ),
)


def write_out_of_scope_plan(
    buffer: ScopeGuardBuffer,
    *,
    source_plan_slug: str,
    output_dir: Path,
    next_id: int,
) -> Optional[Path]:
    """Write the buffered records to a new implementation plan stub.

    Returns the path of the new plan markdown, or ``None`` when the
    buffer is empty. Records are grouped into three sections by
    ``impact_status`` (reverted / kept-by-impact / kept-documentation)
    so a human reviewer can triage actionable code work separately
    from informational doc drift.
    """
    if buffer.is_empty():
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{next_id}-out-of-scope-findings-from-{source_plan_slug}.md"
    out_path = output_dir / fname

    lines: list[str] = []
    lines.append("---")
    lines.append(
        f"title: Out-of-scope findings surfaced while iterating on "
        f"{source_plan_slug}"
    )
    lines.append("status: planning")
    lines.append("priority: medium")
    lines.append("steps: []")
    lines.append("---")
    lines.append(
        f"# Out-of-scope findings surfaced while iterating on `{source_plan_slug}`"
    )
    lines.append("")
    lines.append(
        "Generated by the iterative correctness/completeness loop's scope "
        "guard. Each finding below produced filesystem edits outside the "
        "source plan's declared `step.files` + plan + detail-file set."
    )
    lines.append("")

    counter = 0
    for status, heading, blurb in _STATUS_SECTIONS:
        bucket = [r for r in buffer.records if r.impact_status == status]
        if not bucket:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(blurb)
        lines.append("")
        for rec in bucket:
            counter += 1
            lines.append(f"### Finding {counter} — `{rec.finding_id}`")
            lines.append("")
            step_label = (
                rec.step_id if rec.step_id is not None else "plan-level"
            )
            lines.append(f"- **Step:** {step_label}")
            if rec.diff_preview:
                lines.append("- **Touched files:**")
                lines.append("")
                lines.append(rec.diff_preview)
                lines.append("")
            lines.append("- **Finding body:**")
            lines.append("")
            for body_line in rec.finding_body.splitlines():
                lines.append(f"  > {body_line}")
            lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
