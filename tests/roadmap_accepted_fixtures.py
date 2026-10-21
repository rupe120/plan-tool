"""Publish a roadmap's four artifacts as its accepted root version for seed-route tests."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Sequence

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DomainArtifact,
)
from plan_tool.roadmap_revision_publish import (
    RoadmapWriterToken,
    publish_roadmap_generation,
    roadmap_writer_guard,
)
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    accepted_head_path,
    build_root_enrollment_generation,
    create_candidate_version,
    create_root_version,
    load_accepted_version,
    render_accepted_head,
    stored_version_members,
    version_directory_path,
    version_namespace_path,
)

BRIEF_BYTES = b"Recorded brief\n"


def publish_accepted_root(
    plans_dir: Path,
    slug: str,
    artifact_texts: Sequence[str],
    *,
    brief_bytes: bytes = BRIEF_BYTES,
    writer_token: RoadmapWriterToken | None = None,
) -> PreparedRoadmapVersion:
    """Replace the version store with one root holding ``artifact_texts`` (stage order).

    A fixture re-seed discards any earlier version namespace, so a test that changes a
    plans artifact after setup publishes the new content as the accepted head. A caller
    already inside a writer guard (a confirm prompt, say) passes its ``writer_token``;
    taking the guard again from the same process would block on its own lock.
    """
    artifact_bytes = tuple(text.encode("utf-8") for text in artifact_texts)
    prepared = PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=slug,
            brief_digest=hashlib.sha256(brief_bytes).hexdigest(),
            artifact_digests=tuple(hashlib.sha256(b).hexdigest() for b in artifact_bytes),
        ),
        content=RoadmapVersionContent(brief_bytes=brief_bytes, artifact_bytes=artifact_bytes),
    )
    namespace = version_namespace_path(plans_dir, slug)
    if namespace.exists():
        shutil.rmtree(namespace)
    generation = build_root_enrollment_generation(prepared, plans_dir=plans_dir, slug=slug)
    if writer_token is not None:
        publish_roadmap_generation(
            generation, plans_dir=plans_dir, slug=slug, writer_token=writer_token
        )
        return prepared
    with roadmap_writer_guard(plans_dir, slug) as token:
        publish_roadmap_generation(
            generation, plans_dir=plans_dir, slug=slug, writer_token=token
        )
    return prepared


def with_minimal_upstream(plans_text: str) -> tuple[str, str, str, str]:
    """Stage-ordered texts: empty upstream artifacts plus the given plans artifact text."""
    upstream = (
        DomainArtifact(
            entities=(),
            business_rules=(),
            workflows=(),
            decisions=(),
            body="# Domain\n",
            feedback=(),
        ),
        ConstraintsArtifact(dispositions=(), constraints=(), decisions=(), body="constraints\n"),
        ComponentsArtifact(
            system_patterns=(), component_patterns=(), components=(), decisions=(), body="components\n"
        ),
    )
    rendered = tuple(stage.render(art) for stage, art in zip(STAGES, upstream))
    return (*rendered, plans_text)


def advance_accepted_head(plans_dir: Path, slug: str, artifact_texts: Sequence[str]) -> str:
    """Move the accepted head to a child version holding ``artifact_texts``; return its id.

    Plain writes with no writer guard (callable inside a held guard); scaffolding for a
    head that has moved past its root, not a test of promotion.
    """
    resolved = load_accepted_version(plans_dir=plans_dir, slug=slug)
    assert resolved is not None
    artifact_bytes = tuple(text.encode("utf-8") for text in artifact_texts)
    child = PreparedRoadmapVersion(
        record=create_candidate_version(
            roadmap_slug=slug,
            predecessor_version_id=resolved.record.version_id,
            content_identity=hashlib.sha256(b"".join(artifact_bytes)).hexdigest(),
            review_lineage_identity="c" * 64,
            brief_digest=resolved.record.brief_digest,
            artifact_digests=tuple(hashlib.sha256(b).hexdigest() for b in artifact_bytes),
        ),
        content=RoadmapVersionContent(
            brief_bytes=resolved.brief_bytes, artifact_bytes=artifact_bytes
        ),
    )
    version_dir = version_directory_path(plans_dir, slug, child.record.version_id)
    version_dir.mkdir(parents=True, exist_ok=True)
    for member in stored_version_members(child):
        (version_dir / member.member_name).write_bytes(member.data)
    head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
        roadmap_slug=slug,
        version_id=child.record.version_id,
    )
    accepted_head_path(plans_dir, slug).write_bytes(render_accepted_head(head))
    return child.record.version_id
