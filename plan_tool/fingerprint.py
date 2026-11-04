"""Shared code-fingerprint leaf.

Both the completeness and reconcile families need to digest a plan's
in-scope *code* surface into a reproducible map so a later run can tell
whether the code drifted since a saved audit. This module owns that
producer so neither family imports the other to reach it — it depends
only on the stdlib plus the ``scope_guard``/``drift_detection``/``schema``/
``detail_artifacts`` leaves, keeping the import graph acyclic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from plan_tool.detail_artifacts import resolve_detail_artifact
from plan_tool.drift_detection import compute_content_hash
from plan_tool.schema import Plan, Step
from plan_tool.scope_guard import compute_drift_watched_paths


def _audit_input_digest(value: bytes) -> str:
    """Return the SHA-256 digest used by a captured audit revision."""
    return hashlib.sha256(value).hexdigest()


def audit_input_detail_revision(snapshot) -> list[dict[str, object]]:
    """Serialize every selected detail from an immutable audit capture.

    The ordered entries deliberately retain missing and unreadable selections.
    A revision therefore changes when the audit's selected artifact changes,
    even when neither state has bytes to hash.
    """
    if snapshot.detail_grade != "run":
        raise ValueError("audit inputs require run-grade detail")
    entries: list[dict[str, object]] = []
    for detail in snapshot.details:
        entry: dict[str, object] = {
            "step_id": detail.step_id,
            "resolution": detail.resolution,
            "path": detail.selected_path,
            "state": detail.state,
            "digest": None,
        }
        if detail.state == "present":
            entry["digest"] = _audit_input_digest(detail.content)
        entries.append(entry)
    return entries


def audit_input_detail_fingerprint(snapshot, repo_root: Path | None = None) -> dict[str, str]:
    """Return a compatibility detail map derived from an audit capture.

    Present artifacts retain the established path→content-digest shape for
    compatibility. Non-present artifacts use a framed digest, while the full
    ordered revision remains the authoritative collision-safe identity.
    """
    out: dict[str, str] = {}
    for entry in audit_input_detail_revision(snapshot):
        path = Path(str(entry["path"]))
        if repo_root is not None:
            try:
                key = path.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                key = path.as_posix()
        else:
            key = path.as_posix()
        if key in out:
            key = f"{entry['step_id']}:{key}"
        if entry["state"] == "present":
            out[key] = str(entry["digest"])
        else:
            encoded = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            out[key] = _audit_input_digest(encoded.encode("utf-8"))
    return out


def audit_input_revision(snapshot) -> dict[str, object]:
    """Return the complete public plan/detail revision from one capture.

    ``source_seed_digest`` (v2, BACKLOG #162) and ``project_context_digest``
    (v3) are ``None`` when their optional prompt inputs are absent. Otherwise
    they digest the exact source seed and confirmed project context shown to
    the auditor, so either edit makes a saved report stale for reuse.
    """
    detail_revision = audit_input_detail_revision(snapshot)
    detail_encoded = json.dumps(
        detail_revision, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    source_seed_bytes = snapshot.source_seed_bytes
    project_context = snapshot.project_context
    return {
        "version": 3,
        "detail_grade": "run",
        "plan_digest": _audit_input_digest(snapshot.plan_bytes),
        "detail_bundle_digest": _audit_input_digest(detail_encoded),
        "details": detail_revision,
        "source_seed_digest": (
            _audit_input_digest(source_seed_bytes)
            if source_seed_bytes is not None
            else None
        ),
        "project_context_digest": (
            _audit_input_digest(project_context.encode("utf-8"))
            if project_context
            else None
        ),
    }

# Maintainer-bumped stand-in for the MIXED-STEP verdict *logic* itself —
# ``prompts/detail-quality.md``'s criteria, ``granularity.parse_mixed_step_findings``,
# and ``detail._format_tests_directive`` (the change_type-framing channel).
# Folded into ``compute_purity_cache_key`` so editing that logic (with every
# hashed input unchanged) invalidates every cached verdict at once. Bump it in
# the same change that edits any of those three; the drift-guard test
# ``test_purity_verdict_logic_version_bumped_on_logic_change`` enforces the bump.
# v2 (2026-07-30): the per-change_type test-*ordering* directive was withdrawn
# and both code types now share one tests directive. See CLAUDE.md
# "Withdrawn: the per-change_type test-ordering contract".
PURITY_VERDICT_LOGIC_VERSION = 2


@dataclass(frozen=True)
class PurityKeyComponents:
    """The individually-comparable pieces behind a purity cache key.

    The combined digest from :func:`compute_purity_cache_key` is the single
    hit-test; these components are what step 2 persists and step 4 grades one
    at a time — notably ``all_files_fingerprint``, which must stay a distinct
    sub-digest so a source-file change can be told apart from a trivial detail
    edit (a source-file change must never be graded as a trivial detail edit).
    """

    detail_hash: str | None
    all_files_fingerprint: str
    change_type: str
    depends_on: tuple[int, ...]
    logic_version: int


def compute_code_fingerprint(
    plan: Plan, plan_path: Path, repo_root: Path
) -> dict[str, str]:
    """Hash the plan's in-scope code surface into a reproducible
    ``{repo-relative-posix-path: sha256-hex}`` map.

    The watched surface is exactly
    :func:`plan_tool.scope_guard.compute_drift_watched_paths` — every
    ``step.files``/``creates`` entry minus the plan markdown and per-step
    detail files (those churn every ``apply_finding`` iteration and must
    never register as code drift). Each survivor is digested with
    :func:`plan_tool.drift_detection.compute_content_hash` (streamed
    SHA-256, ``None`` for missing/unreadable).

    A declared ``creates:`` file not yet on disk yields ``None`` and is
    *omitted* rather than crashing or storing a placeholder — its absence
    is step-5 staleness logic's call, not this producer's. Keys are
    repo-relative posix strings (``repo_root.resolve()`` so a symlinked
    root doesn't break ``relative_to``) and the map is built in sorted
    order, so it reproduces byte-for-byte across runs and machines.

    This is the persisted, cross-save counterpart to the live in-process
    snapshot ``acquire_lock`` keeps (absolute-keyed, deletion-ignoring);
    the two stay separate by design.
    """
    root = repo_root.resolve()
    fingerprint: dict[str, str] = {}
    for path in sorted(compute_drift_watched_paths(plan, plan_path, repo_root)):
        digest = compute_content_hash(path)
        if digest is None:
            continue
        fingerprint[path.relative_to(root).as_posix()] = digest
    return fingerprint


def compute_detail_bundle_fingerprint(
    plan: Plan,
    plan_path: Path,
    repo_root: Path,
) -> dict[str, str]:
    """Hash present run-grade details using pointer-or-canonical resolution."""
    root = repo_root.resolve()
    paths = [
        resolve_detail_artifact(plan_path, plan, step, repo_root).path
        for step in plan.steps
    ]
    fingerprint: dict[str, str] = {}
    for path in sorted(paths):
        digest = compute_content_hash(path)
        if digest is None:
            continue
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = path.as_posix()
        fingerprint[rel] = digest
    return fingerprint


def compute_purity_cache_key(
    plan: Plan, plan_path: Path, step: Step, repo_root: Path
) -> tuple[str, PurityKeyComponents]:
    """Produce a stable cache key for one step's MIXED-STEP purity judgment,
    plus its individually-retrievable components.

    The combined SHA-256 hex string changes iff any purity-relevant input
    changes; the returned :class:`PurityKeyComponents` carries the pieces
    later steps compare one at a time. The key covers exactly what the purity
    prompt reads plus the verdict *logic* version:

    - ``detail_hash`` — content hash of this step's detail file (resolved via
      :func:`plan_tool.detail_artifacts.resolve_detail_artifact` — the
      ``step.detail`` pointer, else the canonical path), or ``None`` when
      absent.
    - ``all_files_fingerprint`` — a sub-digest folded over both the declared
      *path set* and the ``{repo-relative-posix-path: sha256-hex}`` content map
      for every entry in ``step.all_files`` (declared ``files:`` **and**
      ``creates:`` — the exact surface ``detail._format_files_contents_block``
      folds into the prompt). Content of a missing path is omitted, but the
      path itself stays in the declared set, so adding/swapping a not-yet-on-disk
      path still moves the fingerprint (the prompt renders the declared list).
      Kept a distinct sub-digest so step 4 can compare it in isolation.
    - ``change_type`` / ``depends_on`` — the verdict-affecting frontmatter the
      prompt folds in; ``change_type`` *directs* the MIXED-STEP verdict yet
      lives outside every hashed file, so a ``refactor``→``feature``/
      ``non-code`` flip must invalidate the entry.
    - ``logic_version`` — :data:`PURITY_VERDICT_LOGIC_VERSION`, so editing the
      verdict logic invalidates every entry even with all inputs unchanged.

    ``title``/``complexity``, the ``plan.title``, and lessons-file content are
    deliberately excluded (an accepted staleness window — they feed the prompt
    but excluding them protects the hit rate; a reframing edit to them serves a
    verdict computed before the reframe, the same class as the lessons window).
    A declared ``risk_profile``/``risk_profile_rationale`` is also deliberately
    excluded here for a different reason, not a staleness tradeoff: whether it
    reaches the purity prompt at all depends on the *caller* (the
    detail-authoring write-through call renders it; the completeness-audit
    read-through call never does), not on the plan alone, so it cannot be a
    pure function of ``(plan, plan_path, step, repo_root)`` the way every
    other component is. :func:`plan_tool.detail._cached_purity_findings`
    tracks that dimension separately via each entry's
    ``risk_context_rendered`` flag rather than folding it in here. Never
    raises on a missing path —
    :func:`compute_content_hash` returns ``None`` and the path is omitted;
    omission is still change-detecting (a present-then-deleted file changes the
    key set, hence the digest). Keys are repo-relative posix strings so the key
    reproduces across clones.
    """
    root = repo_root.resolve()

    def _rel(path: Path) -> str:
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    detail_path = resolve_detail_artifact(plan_path, plan, step, repo_root).path
    detail_hash = compute_content_hash(detail_path)

    all_files_map: dict[str, str] = {}
    for rel in step.all_files:
        path = repo_root / rel
        digest = compute_content_hash(path)
        if digest is None:
            continue
        all_files_map[_rel(path)] = digest
    # Fold in the declared-path *set* (not just existing-file content): the
    # prompt renders the declared `files:`/`creates:` list, so adding or
    # swapping a path that doesn't resolve on disk must still force a re-check
    # even though its content contributes no digest. Content-only hashing would
    # leave the fingerprint byte-identical and serve a stale hit.
    declared_set = sorted(_rel(repo_root / rel) for rel in step.all_files)
    all_files_fingerprint = hashlib.sha256(
        json.dumps(
            {"declared": declared_set, "content": all_files_map},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    change_type = step.change_type.value if step.change_type else ""
    depends_on = tuple(step.depends_on)

    components = PurityKeyComponents(
        detail_hash=detail_hash,
        all_files_fingerprint=all_files_fingerprint,
        change_type=change_type,
        depends_on=depends_on,
        logic_version=PURITY_VERDICT_LOGIC_VERSION,
    )

    combined_key = hashlib.sha256(
        json.dumps(
            {
                "detail": detail_hash,
                "all_files": all_files_fingerprint,
                "change_type": change_type,
                "depends_on": sorted(depends_on),
                "logic_version": PURITY_VERDICT_LOGIC_VERSION,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    return combined_key, components


@dataclass(frozen=True)
class CodeFingerprintDiff:
    """Saved→current code-fingerprint comparison.

    ``match`` is True only when keys and digests are identical.
    ``content_drifted`` is intersection-only digest changes; membership
    deltas live in ``footprint_added`` / ``footprint_removed``.
    """

    match: bool
    content_drifted: list[Path]
    footprint_added: list[Path]
    footprint_removed: list[Path]

    @property
    def any_path_change(self) -> list[Path]:
        """Union of content + membership path changes (sorted, unique)."""
        return sorted(
            set(self.content_drifted)
            | set(self.footprint_added)
            | set(self.footprint_removed)
        )


def diff_code_fingerprint(
    saved_fp: dict[str, str], current_fp: dict[str, str], repo_root: Path
) -> CodeFingerprintDiff:
    """Diff a saved code fingerprint against the current one.

    **Content drift** is keys in the *intersection* whose digests differ —
    real on-disk edits to files that stayed in the footprint.

    **Footprint membership** is keys only in saved (removed) or only in
    current (added) — a ``files:``/``creates:`` rewrite, or a declared file
    that vanished from disk. Those are *not* content drift: reporting them
    as "code file(s) changed" with a ``reconcile-plan`` recommendation is
    the defect (plan metadata churn ≠ code drift).

    ``match`` is True iff the maps are identical (same keys and digests).
    Paths resolve absolute under ``repo_root.resolve()`` and each list is
    sorted so they align with :func:`plan_tool.scope_guard.build_file_to_step_map`.

    Pure: dicts plus ``Path`` only — it reads no ``SavedReview`` marker and
    parses no plan, so the leaf stays acyclic. Callers own the
    ``code_fingerprint_present`` gate that decides whether to diff at all.
    """
    root = repo_root.resolve()

    def _abs(rels: set[str]) -> list[Path]:
        return sorted((root / rel).resolve() for rel in rels)

    changed = {
        rel
        for rel, digest in saved_fp.items()
        if rel in current_fp and current_fp[rel] != digest
    }
    removed = set(saved_fp) - set(current_fp)
    added = set(current_fp) - set(saved_fp)
    return CodeFingerprintDiff(
        match=not (changed or removed or added),
        content_drifted=_abs(changed),
        footprint_added=_abs(added),
        footprint_removed=_abs(removed),
    )
