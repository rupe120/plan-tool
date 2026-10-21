"""Read-only snapshot resolution and Git evidence for roadmap comparisons."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    RoadmapArtifact,
    RoadmapArtifactError,
)
from plan_tool import roadmap_candidate
from plan_tool.roadmap_candidate_run import (
    load_candidate_admission,
    load_stored_candidate_proposal,
)
from plan_tool.roadmap_compare import (
    ComparisonProseAmendment,
    ComparisonProseAmendmentEvidence,
    RoadmapComparison,
    build_roadmap_comparison,
)
from plan_tool.roadmap_diff import build_roadmap_diff
from plan_tool.roadmap_seed_manifest import (
    NoPublishedRoadmapVersionError,
    no_published_version_message,
)
from plan_tool.roadmap_versions import (
    VERSION_ARTIFACT_INVENTORY,
    VERSION_ARTIFACT_KEYS,
    ResolvedRoadmapVersion,
    RoadmapVersionError,
    StoredRoadmapVersion,
    load_accepted_version,
    load_resolved_stored_version,
    sha256_digests,
)


class RoadmapComparisonRunError(ValueError):
    """A requested comparison cannot bind two complete trusted snapshots."""


@dataclass(frozen=True)
class RoadmapComparisonSnapshot:
    """One complete captured snapshot, with bytes and parsed values in inventory order."""

    kind: Literal["root", "candidate"]
    version_id: str | None
    brief_digest: str | None
    record: StoredRoadmapVersion | None
    brief_bytes: bytes | None
    artifact_keys: tuple[str, ...]
    artifact_bytes: tuple[bytes, ...]
    artifact_digests: tuple[str, ...]
    parsed_artifacts: Mapping[str, RoadmapArtifact]


@dataclass(frozen=True)
class RoadmapGitPatch:
    """One controlled Git no-index result for a configured artifact pair."""

    artifact_key: str
    status: Literal[0, 1]
    patch: str


@dataclass(frozen=True)
class RoadmapComparisonRun:
    """Complete comparison facts for rendering layers without presentation policy."""

    base: RoadmapComparisonSnapshot
    target: RoadmapComparisonSnapshot
    patches: tuple[RoadmapGitPatch, ...]
    comparison: RoadmapComparison


# Derived from STAGES (the single source for artifact_key -> parser), not
# hand-duplicated — a second hand-written table would drift if a stage's
# parser ever changed there without a matching edit here.
_ARTIFACT_PARSERS = {stage.artifact_key: stage.parse for stage in STAGES}


def run_roadmap_comparison(
    *,
    plans_dir: Path,
    slug: str,
    base_version_id: str | None = None,
    target_version_id: str | None = None,
) -> RoadmapComparisonRun:
    """Compare an accepted or stored base with a stored target.

    An omitted base means the accepted immutable head; an omitted target means
    the active candidate and is refused when none is active. Only the version
    store is read; no roadmap or Git state is modified by this operation.
    """
    try:
        base = _resolve_base_snapshot(
            plans_dir=Path(plans_dir), slug=slug, version_id=base_version_id
        )
        target = _resolve_target_snapshot(
            plans_dir=Path(plans_dir), slug=slug, version_id=target_version_id
        )
        prose_amendment_evidence = _bound_prose_amendment_evidence(
            plans_dir=Path(plans_dir), slug=slug, base=base, target=target
        )
        patches = _capture_patches(base=base, target=target)
        typed_diff = build_roadmap_diff(
            predecessor_artifacts=base.parsed_artifacts,
            candidate_artifacts=target.parsed_artifacts,
            predecessor_bytes=base.artifact_bytes,
            candidate_artifacts_bytes=target.artifact_bytes,
            stages=STAGES,
        )
        comparison = build_roadmap_comparison(
            typed_diff=typed_diff,
            raw_patches={patch.artifact_key: patch.patch for patch in patches},
            prose_amendment_evidence=prose_amendment_evidence,
        )
    except (RoadmapComparisonRunError, NoPublishedRoadmapVersionError):
        raise
    except (OSError, UnicodeError, TypeError, ValueError, RoadmapVersionError, RoadmapArtifactError) as exc:
        raise RoadmapComparisonRunError(str(exc)) from exc
    return RoadmapComparisonRun(base=base, target=target, patches=patches, comparison=comparison)


def _bound_prose_amendment_evidence(
    *, plans_dir: Path, slug: str, base: RoadmapComparisonSnapshot, target: RoadmapComparisonSnapshot
) -> ComparisonProseAmendmentEvidence:
    """Bind fragments only when ``base`` is the stored target candidate's direct predecessor."""
    if target.kind != "candidate" or target.version_id is None or base.version_id is None:
        return ComparisonProseAmendmentEvidence(outcome="not-applicable", amendments=())

    candidate = load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=slug, candidate_version_id=target.version_id
    )
    if candidate.record.predecessor_version_id != base.version_id:
        return ComparisonProseAmendmentEvidence(outcome="not-directly-bound", amendments=())
    if candidate.evidence.normalized_operations is None:
        # Selector-era and pre-route batch candidates stored no operation evidence.
        return ComparisonProseAmendmentEvidence(outcome="no-operation-evidence", amendments=())
    return ComparisonProseAmendmentEvidence(
        outcome="bound",
        amendments=tuple(
            ComparisonProseAmendment(
                artifact_key=item.artifact_key, row_id=item.row_id, fragment=item.fragment
            )
            for item in roadmap_candidate.candidate_prose_amendment_diffs(
                candidate.evidence.normalized_operations
            )
        ),
    )


def _resolve_base_snapshot(
    *, plans_dir: Path, slug: str, version_id: str | None
) -> RoadmapComparisonSnapshot:
    resolved = (
        load_resolved_stored_version(plans_dir=plans_dir, slug=slug, version_id=version_id)
        if version_id is not None
        else load_accepted_version(plans_dir=plans_dir, slug=slug)
    )
    if resolved is None:
        raise NoPublishedRoadmapVersionError(no_published_version_message(plans_dir, slug))
    return _snapshot_from_resolved(resolved)


def _resolve_target_snapshot(
    *, plans_dir: Path, slug: str, version_id: str | None
) -> RoadmapComparisonSnapshot:
    if version_id is None:
        admission = load_candidate_admission(plans_dir=plans_dir, slug=slug)
        version_id = None if admission is None else admission.active_candidate_version_id
        if version_id is None:
            raise RoadmapComparisonRunError(
                "no candidate is active to compare against; pass --comparison-target VERSION_ID"
            )
    return _snapshot_from_resolved(
        load_resolved_stored_version(plans_dir=plans_dir, slug=slug, version_id=version_id)
    )


def _snapshot_from_resolved(resolved: ResolvedRoadmapVersion) -> RoadmapComparisonSnapshot:
    return _build_snapshot(
        kind=resolved.record.version_kind,
        version_id=resolved.record.version_id,
        brief_digest=resolved.record.brief_digest,
        record=resolved.record,
        brief_bytes=resolved.brief_bytes,
        artifact_bytes=resolved.artifact_bytes,
    )


def _build_snapshot(
    *,
    kind: Literal["root", "candidate"],
    version_id: str | None,
    brief_digest: str | None,
    record: StoredRoadmapVersion | None,
    brief_bytes: bytes | None,
    artifact_bytes: tuple[bytes, ...],
) -> RoadmapComparisonSnapshot:
    keys = VERSION_ARTIFACT_KEYS
    if not isinstance(artifact_bytes, tuple) or len(artifact_bytes) != len(keys):
        raise RoadmapComparisonRunError("snapshot artifact bundle does not match configured inventory")
    parsed: dict[str, RoadmapArtifact] = {}
    for key, data in zip(keys, artifact_bytes, strict=True):
        if not isinstance(data, bytes):
            raise RoadmapComparisonRunError("snapshot artifact content must be bytes")
        try:
            text = data.decode("utf-8")
            parsed[key] = _ARTIFACT_PARSERS[key](text)
        except (RoadmapArtifactError, UnicodeError, ValueError) as exc:
            raise RoadmapComparisonRunError(f"snapshot artifact {key} is invalid") from exc
    return RoadmapComparisonSnapshot(
        kind=kind,
        version_id=version_id,
        brief_digest=brief_digest,
        record=record,
        brief_bytes=brief_bytes,
        artifact_keys=keys,
        artifact_bytes=artifact_bytes,
        artifact_digests=sha256_digests(artifact_bytes),
        parsed_artifacts=MappingProxyType(parsed),
    )


def _capture_patches(
    *, base: RoadmapComparisonSnapshot, target: RoadmapComparisonSnapshot
) -> tuple[RoadmapGitPatch, ...]:
    """Collect all fixed pairs from captured bytes, never live artifact paths."""
    with tempfile.TemporaryDirectory(prefix="plan-tool-roadmap-compare-") as directory:
        root = Path(directory)
        patches: list[RoadmapGitPatch] = []
        for entry, before, after in zip(
            VERSION_ARTIFACT_INVENTORY,
            base.artifact_bytes,
            target.artifact_bytes,
            strict=True,
        ):
            before_path = root / "before" / entry.member_name
            after_path = root / "after" / entry.member_name
            before_path.parent.mkdir(parents=True, exist_ok=True)
            after_path.parent.mkdir(parents=True, exist_ok=True)
            before_path.write_bytes(before)
            after_path.write_bytes(after)
            patches.append(
                _capture_patch(
                    entry.artifact_key,
                    entry.member_name,
                    before_path,
                    after_path,
                    cwd=root,
                )
            )
    return tuple(patches)


def _capture_patch(
    artifact_key: str,
    member_name: str,
    before_path: Path,
    after_path: Path,
    *,
    cwd: Path,
) -> RoadmapGitPatch:
    command = [
        "git", "-c", "diff.algorithm=myers", "-c", "diff.indentHeuristic=false",
        "-c", "core.autocrlf=false", "-c", "core.safecrlf=false",
        "diff", "--no-index", "--no-ext-diff", "--no-textconv", "--no-color", "--text",
        "--unified=3", "--src-prefix=a/", "--dst-prefix=b/",
        "--", f"before/{member_name}", f"after/{member_name}",
    ]
    try:
        result = subprocess.run(
            command, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, check=False
        )
    except OSError as exc:
        raise RoadmapComparisonRunError("Git patch capture could not start") from exc
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        detail = f": {stderr}" if stderr else ""
        raise RoadmapComparisonRunError(
            f"Git patch capture failed for {artifact_key} (exit {result.returncode}){detail}"
        )
    try:
        patch = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoadmapComparisonRunError(f"Git patch for {artifact_key} is not strict UTF-8") from exc
    return RoadmapGitPatch(artifact_key=artifact_key, status=result.returncode, patch=patch)
