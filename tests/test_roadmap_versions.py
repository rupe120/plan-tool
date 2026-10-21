"""Tests for exact immutable root/candidate records and selected-version reads."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    DOMAIN_FILENAME,
    PLANS_FILENAME,
)
from plan_tool.roadmap_revision_publish import (
    publish_roadmap_generation,
    roadmap_writer_guard,
)
from plan_tool.roadmap_versions import (
    ACCEPTED_HEAD_FILENAME,
    INITIAL_EMPTY_REVIEW_LINEAGE_ID,
    ROADMAP_VERSION_SCHEMA_VERSION,
    VERSION_ARTIFACT_INVENTORY,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    RoadmapVersionError,
    StoredRoadmapVersion,
    accepted_head_path,
    build_root_enrollment_generation,
    create_candidate_version,
    create_root_version,
    is_roadmap_enrolled,
    load_accepted_version,
    load_resolved_stored_version,
    parse_stored_version,
    prepare_root_version_from_snapshot,
    render_accepted_head,
    render_stored_version,
    stored_artifact_path,
    stored_brief_path,
    stored_version_members,
    version_directory_path,
    version_namespace_path,
)


SLUG = "storefront"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _content(suffix: bytes = b"") -> RoadmapVersionContent:
    return RoadmapVersionContent(
        brief_bytes=b"recorded brief\r\n" + suffix,
        artifact_bytes=tuple(
            f"{entry.artifact_key} artifact\n".encode("utf-8") + suffix
            for entry in VERSION_ARTIFACT_INVENTORY
        ),
    )


def _root(content: RoadmapVersionContent | None = None) -> PreparedRoadmapVersion:
    content = _content() if content is None else content
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=SLUG,
            brief_digest=_digest(content.brief_bytes),
            artifact_digests=tuple(_digest(value) for value in content.artifact_bytes),
        ),
        content=content,
    )


def _candidate(
    root: PreparedRoadmapVersion, content: RoadmapVersionContent | None = None
) -> PreparedRoadmapVersion:
    content = _content(b"candidate") if content is None else content
    return PreparedRoadmapVersion(
        record=create_candidate_version(
            roadmap_slug=SLUG,
            predecessor_version_id=root.record.version_id,
            content_identity=_digest(b"candidate-content"),
            review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
            brief_digest=_digest(content.brief_bytes),
            artifact_digests=tuple(_digest(value) for value in content.artifact_bytes),
        ),
        content=content,
    )


def _write_prepared_version(tmp_path: Path, prepared: PreparedRoadmapVersion) -> None:
    version_dir = version_directory_path(tmp_path / "plans", SLUG, prepared.record.version_id)
    for member in stored_version_members(prepared):
        path = version_dir / member.member_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.data)


def _write_head(tmp_path: Path, version_id: str) -> None:
    path = accepted_head_path(tmp_path / "plans", SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        render_accepted_head(
            AcceptedRoadmapHead(
                schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                roadmap_slug=SLUG,
                version_id=version_id,
            )
        )
    )


def _canonical_payload(record: StoredRoadmapVersion) -> dict[str, object]:
    return json.loads(render_stored_version(record))


def _render_payload_with_matching_identity(payload: dict[str, object]) -> bytes:
    identity_payload = {key: value for key, value in payload.items() if key != "version_id"}
    payload["version_id"] = hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_root_and_candidate_records_round_trip_through_one_closed_schema() -> None:
    root = _root()
    candidate = _candidate(root)

    assert parse_stored_version(render_stored_version(root.record)) == root.record
    assert parse_stored_version(render_stored_version(candidate.record)) == candidate.record
    assert root.record.version_kind == "root"
    assert candidate.record.version_kind == "candidate"


def test_root_requires_explicit_null_candidate_bindings_and_candidate_requires_non_null_bindings() -> None:
    root_payload = _canonical_payload(_root().record)
    root_payload["predecessor_version_id"] = "a" * 64
    with pytest.raises(RoadmapVersionError, match="malformed"):
        parse_stored_version(_render_payload_with_matching_identity(root_payload))

    root_payload = _canonical_payload(_root().record)
    del root_payload["content_identity"]
    with pytest.raises(RoadmapVersionError, match="malformed"):
        parse_stored_version(_render_payload_with_matching_identity(root_payload))

    candidate_payload = _canonical_payload(_candidate(_root()).record)
    candidate_payload["review_lineage_identity"] = None
    with pytest.raises(RoadmapVersionError, match="malformed"):
        parse_stored_version(_render_payload_with_matching_identity(candidate_payload))


def test_version_identity_changes_or_refuses_when_any_bound_record_field_changes() -> None:
    root = _root().record
    payload = _canonical_payload(root)
    payload["roadmap_slug"] = "other-roadmap"
    changed_slug = parse_stored_version(_render_payload_with_matching_identity(payload))
    assert changed_slug.version_id != root.version_id

    candidate = _candidate(_root()).record
    for field, replacement in (
        ("predecessor_version_id", "b" * 64),
        ("content_identity", "c" * 64),
        ("review_lineage_identity", "d" * 64),
        ("brief_digest", "e" * 64),
    ):
        payload = _canonical_payload(candidate)
        payload[field] = replacement
        changed = parse_stored_version(_render_payload_with_matching_identity(payload))
        assert changed.version_id != candidate.version_id

    payload = _canonical_payload(candidate)
    members = payload["artifact_members"]
    assert isinstance(members, list)
    members[0]["digest"] = "f" * 64
    changed_member_digest = parse_stored_version(_render_payload_with_matching_identity(payload))
    assert changed_member_digest.version_id != candidate.version_id

    payload = _canonical_payload(root)
    payload["version_kind"] = "candidate"
    with pytest.raises(RoadmapVersionError, match="malformed"):
        parse_stored_version(_render_payload_with_matching_identity(payload))

    payload = _canonical_payload(candidate)
    members = payload["artifact_members"]
    assert isinstance(members, list)
    members.reverse()
    with pytest.raises(RoadmapVersionError, match="malformed"):
        parse_stored_version(_render_payload_with_matching_identity(payload))

    payload = _canonical_payload(candidate)
    members = payload["artifact_members"]
    assert isinstance(members, list)
    members[0]["member_name"] = "substituted.md"
    with pytest.raises(RoadmapVersionError, match="malformed"):
        parse_stored_version(_render_payload_with_matching_identity(payload))


def test_version_record_requires_the_configured_stage_order_and_fixed_member_names() -> None:
    payload = _canonical_payload(_root().record)
    members = payload["artifact_members"]
    assert isinstance(members, list)

    for malformed_members in (
        members[:-1],
        [members[0], members[0], *members[2:]],
        [*members[1:], members[0]],
        [
            {**member, "member_name": f"arbitrary-{index}.md"}
            for index, member in enumerate(members)
        ],
    ):
        malformed_payload = _canonical_payload(_root().record)
        malformed_payload["artifact_members"] = malformed_members
        with pytest.raises(RoadmapVersionError, match="malformed"):
            parse_stored_version(_render_payload_with_matching_identity(malformed_payload))


def test_leaf_version_inventory_matches_the_orchestrator_stage_table() -> None:
    assert tuple(entry.artifact_key for entry in VERSION_ARTIFACT_INVENTORY) == tuple(
        stage.artifact_key for stage in STAGES
    )
    assert tuple(entry.member_name for entry in VERSION_ARTIFACT_INVENTORY) == (
        DOMAIN_FILENAME,
        CONSTRAINTS_FILENAME,
        COMPONENTS_FILENAME,
        PLANS_FILENAME,
    )
    import plan_tool.roadmap_versions as roadmap_versions

    assert "from plan_tool.roadmap import" not in inspect.getsource(roadmap_versions)


@pytest.mark.parametrize("member_kind", ("brief", "artifact", "missing"))
def test_load_version_refuses_digest_mismatched_or_missing_exact_members(
    tmp_path: Path, member_kind: str
) -> None:
    root = _root()
    _write_prepared_version(tmp_path, root)
    _write_head(tmp_path, root.record.version_id)
    if member_kind == "brief":
        stored_brief_path(tmp_path / "plans", SLUG, root.record.version_id).write_bytes(b"changed")
    elif member_kind == "artifact":
        stored_artifact_path(
            tmp_path / "plans", SLUG, root.record.version_id, "domain"
        ).write_bytes(b"changed")
    else:
        stored_artifact_path(tmp_path / "plans", SLUG, root.record.version_id, "plans").unlink()

    with pytest.raises(RoadmapVersionError):
        load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG)


def test_load_accepted_version_reads_only_the_head_named_root_or_candidate(tmp_path: Path) -> None:
    root = _root()
    candidate = _candidate(root)
    _write_prepared_version(tmp_path, root)
    _write_prepared_version(tmp_path, candidate)
    _write_head(tmp_path, candidate.record.version_id)
    sibling = version_directory_path(tmp_path / "plans", SLUG, "a" * 64)
    sibling.mkdir(parents=True)
    (sibling / "version.json").write_bytes(b"malformed sibling that is never selected")

    resolved = load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG)

    assert resolved is not None
    assert resolved.record == candidate.record
    assert resolved.brief_bytes == candidate.content.brief_bytes
    assert resolved.artifact_bytes == candidate.content.artifact_bytes


def test_load_explicit_stored_version_returns_complete_root_bundle_without_a_head(
    tmp_path: Path,
) -> None:
    root = _root()
    _write_prepared_version(tmp_path, root)

    resolved = load_resolved_stored_version(
        plans_dir=tmp_path / "plans", slug=SLUG, version_id=root.record.version_id
    )

    assert resolved.record == root.record
    assert resolved.brief_bytes == root.content.brief_bytes
    assert resolved.artifact_bytes == root.content.artifact_bytes
    assert resolved.artifact_keys == tuple(entry.artifact_key for entry in VERSION_ARTIFACT_INVENTORY)


def test_load_explicit_stored_version_returns_complete_candidate_bundle(tmp_path: Path) -> None:
    root = _root()
    candidate = _candidate(root)
    _write_prepared_version(tmp_path, root)
    _write_prepared_version(tmp_path, candidate)

    resolved = load_resolved_stored_version(
        plans_dir=tmp_path / "plans", slug=SLUG, version_id=candidate.record.version_id
    )

    assert resolved.record == candidate.record
    assert resolved.brief_bytes == candidate.content.brief_bytes
    assert resolved.artifact_bytes == candidate.content.artifact_bytes


def test_load_explicit_stored_version_ignores_unselected_malformed_sibling(tmp_path: Path) -> None:
    root = _root()
    _write_prepared_version(tmp_path, root)
    sibling = version_directory_path(tmp_path / "plans", SLUG, "a" * 64)
    sibling.mkdir(parents=True)
    (sibling / "version.json").write_bytes(b"malformed sibling")

    assert load_resolved_stored_version(
        plans_dir=tmp_path / "plans", slug=SLUG, version_id=root.record.version_id
    ).record == root.record


@pytest.mark.parametrize("member_path", ("brief", "artifact", "missing"))
def test_load_explicit_stored_version_refuses_missing_or_corrupt_members(
    tmp_path: Path, member_path: str
) -> None:
    root = _root()
    _write_prepared_version(tmp_path, root)
    if member_path == "brief":
        stored_brief_path(tmp_path / "plans", SLUG, root.record.version_id).write_bytes(b"\xff")
    elif member_path == "artifact":
        stored_artifact_path(tmp_path / "plans", SLUG, root.record.version_id, "domain").write_bytes(
            b"changed"
        )
    else:
        stored_artifact_path(tmp_path / "plans", SLUG, root.record.version_id, "plans").unlink()

    with pytest.raises(RoadmapVersionError):
        load_resolved_stored_version(
            plans_dir=tmp_path / "plans", slug=SLUG, version_id=root.record.version_id
        )


def test_load_explicit_stored_version_refuses_unknown_or_path_mismatched_record(
    tmp_path: Path,
) -> None:
    root = _root()
    mismatched_id = "a" * 64
    record_path = version_directory_path(tmp_path / "plans", SLUG, mismatched_id) / "version.json"
    record_path.parent.mkdir(parents=True)
    record_path.write_bytes(render_stored_version(root.record))

    for version_id in ("b" * 64, mismatched_id, "not-a-version-id"):
        with pytest.raises(RoadmapVersionError):
            load_resolved_stored_version(
                plans_dir=tmp_path / "plans", slug=SLUG, version_id=version_id
            )


def test_load_accepted_version_uses_complete_explicit_version_contract(tmp_path: Path) -> None:
    root = _root()
    _write_prepared_version(tmp_path, root)
    _write_head(tmp_path, root.record.version_id)

    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG) == load_resolved_stored_version(
        plans_dir=tmp_path / "plans", slug=SLUG, version_id=root.record.version_id
    )

    stored_artifact_path(tmp_path / "plans", SLUG, root.record.version_id, "domain").write_bytes(b"changed")
    with pytest.raises(RoadmapVersionError):
        load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG)


def test_load_accepted_version_surfaces_specific_corruption_diagnostic_not_generic_invalid_id(
    tmp_path: Path,
) -> None:
    """The accepted-head pointer is never operator-supplied, so a corrupt stored
    record behind it must fail with its own specific reason, not the generic
    "requested stored version id is invalid" message meant for a bad explicit id."""
    root = _root()
    _write_prepared_version(tmp_path, root)
    _write_head(tmp_path, root.record.version_id)
    record_path = version_directory_path(tmp_path / "plans", SLUG, root.record.version_id) / "version.json"
    record_path.write_bytes(record_path.read_bytes() + b" ")

    with pytest.raises(RoadmapVersionError, match="exact canonical JSON bytes"):
        load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG)


def test_complete_explicit_version_loading_does_not_write_or_repair_storage(tmp_path: Path) -> None:
    root = _root()
    _write_prepared_version(tmp_path, root)
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert load_resolved_stored_version(
        plans_dir=tmp_path / "plans", slug=SLUG, version_id=root.record.version_id
    ).record == root.record
    with pytest.raises(RoadmapVersionError):
        load_resolved_stored_version(
            plans_dir=tmp_path / "plans", slug=SLUG, version_id="a" * 64
        )

    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_missing_head_is_unversioned_but_invalid_present_head_fails_closed(tmp_path: Path) -> None:
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG) is None
    assert not is_roadmap_enrolled(plans_dir=tmp_path / "plans", slug=SLUG)

    head = accepted_head_path(tmp_path / "plans", SLUG)
    head.parent.mkdir(parents=True)
    head.write_bytes(b"not an accepted head")

    with pytest.raises(RoadmapVersionError):
        load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG)
    with pytest.raises(RoadmapVersionError):
        is_roadmap_enrolled(plans_dir=tmp_path / "plans", slug=SLUG)


def test_version_contract_validation_and_resolution_do_not_create_or_repair_storage(
    tmp_path: Path,
) -> None:
    root = _root()
    _write_prepared_version(tmp_path, root)
    _write_head(tmp_path, root.record.version_id)
    source = tmp_path / "plans" / "roadmaps" / SLUG / "01-domain.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"live artifact remains untouched\n")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert parse_stored_version(render_stored_version(root.record)) == root.record
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG) is not None

    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert ACCEPTED_HEAD_FILENAME in {path.name for path in version_namespace_path(tmp_path / "plans", SLUG).iterdir()}


def test_prepare_root_version_requires_complete_raw_bound_snapshot() -> None:
    class Snapshot:
        brief_bytes = b"brief\r\n"
        brief_raw_digest = _digest(brief_bytes)
        artifact_keys = tuple(entry.artifact_key for entry in VERSION_ARTIFACT_INVENTORY)
        artifact_texts = tuple(f"{entry.artifact_key}\n" for entry in VERSION_ARTIFACT_INVENTORY)
        artifact_digests = tuple(_digest(text.encode("utf-8")) for text in artifact_texts)

    prepared = prepare_root_version_from_snapshot(Snapshot(), roadmap_slug=SLUG)

    assert prepared.content.brief_bytes == Snapshot.brief_bytes
    assert prepared.record.brief_digest == Snapshot.brief_raw_digest


def test_root_enrollment_stores_exact_complete_stage_and_raw_brief_bytes(tmp_path: Path) -> None:
    prepared = _root()
    generation = build_root_enrollment_generation(
        prepared,
        plans_dir=tmp_path / "plans",
        slug=SLUG,
    )

    assert all(member.old_bytes is None for member in generation.members)
    assert generation.members[-1].relative_path.endswith(ACCEPTED_HEAD_FILENAME)
    assert all(
        ACCEPTED_HEAD_FILENAME not in member.relative_path for member in generation.members[:-1]
    )
    with roadmap_writer_guard(tmp_path / "plans", SLUG) as writer_token:
        publish_roadmap_generation(
            generation,
            plans_dir=tmp_path / "plans",
            slug=SLUG,
            writer_token=writer_token,
        )

    resolved = load_accepted_version(plans_dir=tmp_path / "plans", slug=SLUG)
    assert resolved is not None
    assert resolved.brief_bytes == b"recorded brief\r\n"
    assert resolved.artifact_bytes == prepared.content.artifact_bytes


def test_root_enrollment_refuses_existing_storage_or_selector_without_replacement(
    tmp_path: Path,
) -> None:
    prepared = _root()
    generation = build_root_enrollment_generation(
        prepared,
        plans_dir=tmp_path / "plans",
        slug=SLUG,
    )
    root_member = generation.members[0]
    root_path = tmp_path / "plans" / "roadmaps" / SLUG / root_member.relative_path
    root_path.parent.mkdir(parents=True, exist_ok=True)
    root_path.write_bytes(b"prior immutable bytes")

    with pytest.raises(RoadmapVersionError, match="cannot replace"):
        build_root_enrollment_generation(prepared, plans_dir=tmp_path / "plans", slug=SLUG)
    assert root_path.read_bytes() == b"prior immutable bytes"
