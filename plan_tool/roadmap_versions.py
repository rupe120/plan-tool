"""Read-only contracts for exact immutable roadmap versions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError as PydanticValidationError
from pydantic import field_validator, model_validator

from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    DOMAIN_FILENAME,
    PLANS_FILENAME,
    roadmap_dir,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    _reject_duplicate_json_keys,
)


ROADMAP_VERSION_SCHEMA_VERSION = 1
ROADMAP_VERSION_NAMESPACE_DIRNAME = ".roadmap-versions"
STORED_VERSION_RECORD_FILENAME = "version.json"
ACCEPTED_HEAD_FILENAME = "accepted-head.json"
STORED_BRIEF_FILENAME = "brief.md"
SHA256_DIGEST_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)


class RoadmapVersionError(ValueError):
    """A persisted immutable roadmap version cannot be trusted."""


@dataclass(frozen=True)
class VersionArtifactInventoryEntry:
    """One fixed staged artifact member in immutable version storage."""

    artifact_key: str
    member_name: str


# This leaf inventory intentionally mirrors the orchestrator's stage table.
VERSION_ARTIFACT_INVENTORY: tuple[VersionArtifactInventoryEntry, ...] = (
    VersionArtifactInventoryEntry("domain", DOMAIN_FILENAME),
    VersionArtifactInventoryEntry("constraints", CONSTRAINTS_FILENAME),
    VersionArtifactInventoryEntry("components", COMPONENTS_FILENAME),
    VersionArtifactInventoryEntry("plans", PLANS_FILENAME),
)

# The shared projection every caller otherwise recomputed independently.
VERSION_ARTIFACT_KEYS: tuple[str, ...] = tuple(
    entry.artifact_key for entry in VERSION_ARTIFACT_INVENTORY
)

INITIAL_EMPTY_REVIEW_LINEAGE_ID = hashlib.sha256(
    b'{"review_lineage_version":1,"questions":[],"answers":[]}'
).hexdigest()


class _FrozenRecord(BaseModel):
    """Base model for closed immutable version records."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _require_schema_version(value: object, *, field_name: str) -> int:
    if type(value) is not int or value != ROADMAP_VERSION_SCHEMA_VERSION:
        raise ValueError(f"{field_name} is unsupported")
    return value


def sha256_digests(items: Sequence[bytes]) -> tuple[str, ...]:
    """Hex-digest each item in order — the shared digest-tuple projection."""
    return tuple(hashlib.sha256(item).hexdigest() for item in items)


def _require_digest(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or SHA256_DIGEST_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be lowercase SHA-256")
    return value


def _require_roadmap_slug(value: object) -> str:
    if not isinstance(value, str) or not value or "/" in value or "\\" in value:
        raise ValueError("roadmap slug must be one nonempty path component")
    path = Path(value)
    if path.parts != (value,) or ".." in path.parts:
        raise ValueError("roadmap slug must be one nonempty path component")
    return value


class StoredArtifactMember(_FrozenRecord):
    """The exact stored name and digest for one staged artifact."""

    artifact_key: str
    member_name: str
    digest: str

    @field_validator("artifact_key", "member_name")
    @classmethod
    def _requires_nonempty_name(cls, value: str) -> str:
        if not value:
            raise ValueError("stored artifact member binding must be nonempty")
        return value

    @field_validator("digest")
    @classmethod
    def _requires_digest(cls, value: str) -> str:
        return _require_digest(value, field_name="stored artifact member digest")


class StoredRoadmapVersion(_FrozenRecord):
    """One root or candidate record in the shared immutable namespace."""

    schema_version: int
    roadmap_slug: str
    version_kind: Literal["root", "candidate"]
    version_id: str
    predecessor_version_id: str | None
    content_identity: str | None
    review_lineage_identity: str | None
    brief_member_name: str
    brief_digest: str
    artifact_members: tuple[StoredArtifactMember, ...]

    @field_validator("schema_version", mode="before")
    @classmethod
    def _requires_supported_schema_version(cls, value: object) -> int:
        return _require_schema_version(value, field_name="stored version schema version")

    _requires_safe_roadmap_slug = field_validator("roadmap_slug")(_require_roadmap_slug)

    @field_validator("version_id")
    @classmethod
    def _requires_version_id(cls, value: str) -> str:
        return _require_digest(value, field_name="stored version id")

    @field_validator(
        "predecessor_version_id", "content_identity", "review_lineage_identity"
    )
    @classmethod
    def _requires_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_digest(value, field_name="stored version identity")

    @field_validator("brief_member_name")
    @classmethod
    def _requires_fixed_brief_member_name(cls, value: str) -> str:
        if value != STORED_BRIEF_FILENAME:
            raise ValueError("stored brief member name is not configured")
        return value

    @field_validator("brief_digest")
    @classmethod
    def _requires_brief_digest(cls, value: str) -> str:
        return _require_digest(value, field_name="stored brief digest")

    @field_validator("artifact_members", mode="before")
    @classmethod
    def _retains_tuple_inventory(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (tuple, list)):
            raise ValueError("stored artifact members must be an ordered sequence")
        return tuple(value)

    @model_validator(mode="after")
    def _requires_closed_record_shape(self) -> StoredRoadmapVersion:
        expected_inventory = tuple(
            (entry.artifact_key, entry.member_name)
            for entry in VERSION_ARTIFACT_INVENTORY
        )
        actual_inventory = tuple(
            (member.artifact_key, member.member_name) for member in self.artifact_members
        )
        if actual_inventory != expected_inventory:
            raise ValueError("stored artifact members do not match the configured inventory")
        candidate_bindings = (
            self.predecessor_version_id,
            self.content_identity,
            self.review_lineage_identity,
        )
        if self.version_kind == "root" and any(
            binding is not None for binding in candidate_bindings
        ):
            raise ValueError("root versions require explicit null candidate bindings")
        if self.version_kind == "candidate" and any(
            binding is None for binding in candidate_bindings
        ):
            raise ValueError("candidate versions require predecessor and lineage bindings")
        if self.version_id != stored_version_id(self):
            raise ValueError("stored version id does not match its immutable fields")
        return self


class AcceptedRoadmapHead(_FrozenRecord):
    """The sole selector for an enrolled roadmap's immutable content."""

    schema_version: int
    roadmap_slug: str
    version_id: str

    @field_validator("schema_version", mode="before")
    @classmethod
    def _requires_supported_schema_version(cls, value: object) -> int:
        return _require_schema_version(value, field_name="accepted head schema version")

    _requires_safe_roadmap_slug = field_validator("roadmap_slug")(_require_roadmap_slug)

    @field_validator("version_id")
    @classmethod
    def _requires_version_id(cls, value: str) -> str:
        return _require_digest(value, field_name="accepted head version id")


@dataclass(frozen=True)
class RoadmapVersionContent:
    """Exact complete bytes for one stored version's fixed members."""

    brief_bytes: bytes
    artifact_bytes: tuple[bytes, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.brief_bytes, bytes):
            raise RoadmapVersionError("stored brief content must be bytes")
        if not isinstance(self.artifact_bytes, tuple) or len(self.artifact_bytes) != len(
            VERSION_ARTIFACT_INVENTORY
        ):
            raise RoadmapVersionError("stored artifact content must match the configured inventory")
        try:
            self.brief_bytes.decode("utf-8")
            for artifact_bytes in self.artifact_bytes:
                if not isinstance(artifact_bytes, bytes):
                    raise RoadmapVersionError("stored artifact content must be bytes")
                artifact_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RoadmapVersionError("stored version content must be strict UTF-8") from exc


@dataclass(frozen=True)
class PreparedRoadmapVersion:
    """One record paired with the exact bytes its storage members contain."""

    record: StoredRoadmapVersion
    content: RoadmapVersionContent

    def __post_init__(self) -> None:
        _require_content_matches_record(self.record, self.content)


@dataclass(frozen=True)
class StoredVersionMember:
    """One fixed relative member name and its exact byte content."""

    member_name: str
    data: bytes


@dataclass(frozen=True)
class ResolvedRoadmapVersion:
    """The exact selected record and stage-ordered byte streams."""

    record: StoredRoadmapVersion
    brief_bytes: bytes
    artifact_bytes: tuple[bytes, ...]

    @property
    def artifact_keys(self) -> tuple[str, ...]:
        """Return the fixed keys paired with ``artifact_bytes``."""
        return VERSION_ARTIFACT_KEYS


def version_namespace_path(plans_dir: Path, slug: str) -> Path:
    """Return the one fixed immutable-version namespace for ``slug``."""
    try:
        return roadmap_dir(plans_dir, slug) / ROADMAP_VERSION_NAMESPACE_DIRNAME
    except ValueError as exc:
        raise RoadmapVersionError(str(exc)) from exc


def version_directory_path(plans_dir: Path, slug: str, version_id: str) -> Path:
    """Return the fixed storage directory for one validated version id."""
    _require_digest(version_id, field_name="version id")
    return version_namespace_path(plans_dir, slug) / version_id


def stored_version_record_path(plans_dir: Path, slug: str, version_id: str) -> Path:
    """Return the fixed record path for one immutable version."""
    return version_directory_path(plans_dir, slug, version_id) / STORED_VERSION_RECORD_FILENAME


def stored_brief_path(plans_dir: Path, slug: str, version_id: str) -> Path:
    """Return the fixed raw-brief path for one immutable version."""
    return version_directory_path(plans_dir, slug, version_id) / STORED_BRIEF_FILENAME


def stored_artifact_path(
    plans_dir: Path, slug: str, version_id: str, artifact_key: str
) -> Path:
    """Return one configured staged-member path without accepting a member name."""
    return version_directory_path(plans_dir, slug, version_id) / artifact_member_name(
        artifact_key
    )


def accepted_head_path(plans_dir: Path, slug: str) -> Path:
    """Return the one fixed accepted-head selector path."""
    return version_namespace_path(plans_dir, slug) / ACCEPTED_HEAD_FILENAME


def artifact_member_name(artifact_key: str) -> str:
    """Return the fixed stored member name for one configured artifact key."""
    for entry in VERSION_ARTIFACT_INVENTORY:
        if entry.artifact_key == artifact_key:
            return entry.member_name
    raise RoadmapVersionError(f"unknown configured roadmap artifact key {artifact_key!r}")


def create_root_version(
    *, roadmap_slug: str, brief_digest: str, artifact_digests: Sequence[str]
) -> StoredRoadmapVersion:
    """Build one immutable root record from exact member digests."""
    return _create_stored_version(
        roadmap_slug=roadmap_slug,
        version_kind="root",
        predecessor_version_id=None,
        content_identity=None,
        review_lineage_identity=None,
        brief_digest=brief_digest,
        artifact_digests=artifact_digests,
    )


def create_candidate_version(
    *,
    roadmap_slug: str,
    predecessor_version_id: str,
    content_identity: str,
    review_lineage_identity: str,
    brief_digest: str,
    artifact_digests: Sequence[str],
) -> StoredRoadmapVersion:
    """Build one immutable candidate record from its fixed lineage bindings."""
    return _create_stored_version(
        roadmap_slug=roadmap_slug,
        version_kind="candidate",
        predecessor_version_id=predecessor_version_id,
        content_identity=content_identity,
        review_lineage_identity=review_lineage_identity,
        brief_digest=brief_digest,
        artifact_digests=artifact_digests,
    )


def prepare_root_version_from_snapshot(
    snapshot: object, *, roadmap_slug: str
) -> PreparedRoadmapVersion:
    """Prepare exact root members from a complete raw-bound impact snapshot."""
    brief_bytes = getattr(snapshot, "brief_bytes", None)
    brief_raw_digest = getattr(snapshot, "brief_raw_digest", None)
    artifact_keys = getattr(snapshot, "artifact_keys", None)
    artifact_texts = getattr(snapshot, "artifact_texts", None)
    artifact_digests = getattr(snapshot, "artifact_digests", None)
    if not isinstance(brief_bytes, bytes) or not isinstance(brief_raw_digest, str):
        raise RoadmapVersionError("impact snapshot lacks a raw recorded-brief binding")
    if hashlib.sha256(brief_bytes).hexdigest() != brief_raw_digest:
        raise RoadmapVersionError("impact snapshot raw recorded-brief digest is invalid")
    try:
        brief_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoadmapVersionError("impact snapshot recorded brief is not strict UTF-8") from exc
    if (
        not isinstance(artifact_keys, tuple)
        or artifact_keys != VERSION_ARTIFACT_KEYS
        or not isinstance(artifact_texts, tuple)
        or not isinstance(artifact_digests, tuple)
        or len(artifact_texts) != len(VERSION_ARTIFACT_INVENTORY)
        or len(artifact_digests) != len(VERSION_ARTIFACT_INVENTORY)
    ):
        raise RoadmapVersionError("impact snapshot does not contain the complete stage inventory")
    if any(not isinstance(text, str) for text in artifact_texts):
        raise RoadmapVersionError("impact snapshot artifact content must be decoded text")
    content = RoadmapVersionContent(
        brief_bytes=brief_bytes,
        artifact_bytes=tuple(text.encode("utf-8") for text in artifact_texts),
    )
    expected_digests = sha256_digests(content.artifact_bytes)
    if artifact_digests != expected_digests:
        raise RoadmapVersionError("impact snapshot artifact digests are invalid")
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=roadmap_slug,
            brief_digest=brief_raw_digest,
            artifact_digests=expected_digests,
        ),
        content=content,
    )


def build_root_enrollment_generation(
    prepared: PreparedRoadmapVersion,
    *,
    plans_dir: Path,
    slug: str,
) -> PendingGeneration:
    """Build the one root-storage-before-selector enrollment generation."""
    if not isinstance(prepared, PreparedRoadmapVersion):
        raise RoadmapVersionError("root enrollment requires a prepared immutable root")
    if prepared.record.roadmap_slug != slug or prepared.record.version_kind != "root":
        raise RoadmapVersionError("root enrollment record does not match its roadmap")
    _require_content_matches_record(prepared.record, prepared.content)

    root = roadmap_dir(plans_dir, slug)
    version_dir = version_directory_path(plans_dir, slug, prepared.record.version_id)
    root_members = stored_version_members(prepared)
    members: list[GenerationMember] = []
    for member in root_members:
        path = version_dir / member.member_name
        old_bytes = _read_optional_bytes(path, description="root enrollment member")
        if old_bytes is not None:
            raise RoadmapVersionError("root enrollment cannot replace stored version members")
        members.append(
            GenerationMember(
                path.relative_to(root).as_posix(),
                None,
                member.data,
            )
        )

    selector_path = accepted_head_path(plans_dir, slug)
    selector_old_bytes = _read_optional_bytes(
        selector_path, description="accepted-head selector"
    )
    if selector_old_bytes is not None:
        raise RoadmapVersionError("root enrollment requires an unselected roadmap")
    members.append(
        GenerationMember(
            selector_path.relative_to(root).as_posix(),
            None,
            render_accepted_head(
                AcceptedRoadmapHead(
                    schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                    roadmap_slug=slug,
                    version_id=prepared.record.version_id,
                )
            ),
        )
    )
    return PendingGeneration(kind="root-enrollment", members=tuple(members))


def stored_version_identity_preimage(record: StoredRoadmapVersion) -> bytes:
    """Return canonical JSON over every stored-version field except its id."""
    if not isinstance(record, StoredRoadmapVersion):
        raise RoadmapVersionError("stored version identity requires a stored version record")
    return _canonical_json_bytes(_stored_version_identity_payload(record))


def stored_version_id(record: StoredRoadmapVersion) -> str:
    """Return the reproducible identity for one stored-version record."""
    return hashlib.sha256(stored_version_identity_preimage(record)).hexdigest()


def render_stored_version(record: StoredRoadmapVersion) -> bytes:
    """Render one validated stored-version record as canonical JSON bytes."""
    if not isinstance(record, StoredRoadmapVersion):
        raise RoadmapVersionError("stored version rendering requires a stored version record")
    try:
        validated = StoredRoadmapVersion.model_validate(record.model_dump(mode="json"))
    except PydanticValidationError as exc:
        raise RoadmapVersionError("stored version record is invalid") from exc
    return _canonical_json_bytes(validated.model_dump(mode="json"))


def parse_stored_version(data: bytes) -> StoredRoadmapVersion:
    """Parse one exact canonical stored-version record."""
    raw = _decode_strict_json_bytes(data, description="stored version record")
    try:
        record = StoredRoadmapVersion.model_validate(raw)
    except PydanticValidationError as exc:
        raise RoadmapVersionError("stored version record is malformed") from exc
    if render_stored_version(record) != data:
        raise RoadmapVersionError("stored version record must use exact canonical JSON bytes")
    return record


def render_accepted_head(head: AcceptedRoadmapHead) -> bytes:
    """Render one validated accepted-head selector as canonical JSON bytes."""
    if not isinstance(head, AcceptedRoadmapHead):
        raise RoadmapVersionError("accepted-head rendering requires a selector")
    try:
        validated = AcceptedRoadmapHead.model_validate(head.model_dump(mode="json"))
    except PydanticValidationError as exc:
        raise RoadmapVersionError("accepted-head selector is invalid") from exc
    return _canonical_json_bytes(validated.model_dump(mode="json"))


def parse_accepted_head(data: bytes) -> AcceptedRoadmapHead:
    """Parse one exact canonical accepted-head selector."""
    raw = _decode_strict_json_bytes(data, description="accepted-head selector")
    try:
        head = AcceptedRoadmapHead.model_validate(raw)
    except PydanticValidationError as exc:
        raise RoadmapVersionError("accepted-head selector is malformed") from exc
    if render_accepted_head(head) != data:
        raise RoadmapVersionError("accepted-head selector must use exact canonical JSON bytes")
    return head


def stored_version_members(prepared: PreparedRoadmapVersion) -> tuple[StoredVersionMember, ...]:
    """Render the complete fixed member inventory for later publication."""
    if not isinstance(prepared, PreparedRoadmapVersion):
        raise RoadmapVersionError("stored version members require prepared version content")
    _require_content_matches_record(prepared.record, prepared.content)
    return (
        StoredVersionMember(STORED_VERSION_RECORD_FILENAME, render_stored_version(prepared.record)),
        StoredVersionMember(STORED_BRIEF_FILENAME, prepared.content.brief_bytes),
        *tuple(
            StoredVersionMember(entry.member_name, artifact_bytes)
            for entry, artifact_bytes in zip(
                VERSION_ARTIFACT_INVENTORY, prepared.content.artifact_bytes, strict=True
            )
        ),
    )


def load_stored_version(
    *, plans_dir: Path, slug: str, version_id: str
) -> StoredRoadmapVersion:
    """Load one exact stored root-or-candidate record without selecting it."""
    path = stored_version_record_path(plans_dir, slug, version_id)
    data = _read_bytes(path, description="stored version record")
    record = parse_stored_version(data)
    if record.roadmap_slug != slug or record.version_id != version_id:
        raise RoadmapVersionError("stored version record does not match its requested path")
    return record


def load_resolved_stored_version(
    *, plans_dir: Path, slug: str, version_id: str
) -> ResolvedRoadmapVersion:
    """Load and verify every fixed member for one explicit stored version."""
    try:
        record = load_stored_version(plans_dir=plans_dir, slug=slug, version_id=version_id)
    except RoadmapVersionError:
        raise
    except ValueError as exc:
        raise RoadmapVersionError("requested stored version id is invalid") from exc
    brief_bytes = _read_member_bytes(
        stored_brief_path(plans_dir, slug, record.version_id),
        expected_digest=record.brief_digest,
        description="stored recorded brief",
    )
    artifact_bytes = tuple(
        _read_member_bytes(
            stored_artifact_path(plans_dir, slug, record.version_id, member.artifact_key),
            expected_digest=member.digest,
            description=f"stored artifact {member.artifact_key}",
        )
        for member in record.artifact_members
    )
    return ResolvedRoadmapVersion(
        record=record,
        brief_bytes=brief_bytes,
        artifact_bytes=artifact_bytes,
    )


def load_accepted_head(*, plans_dir: Path, slug: str) -> AcceptedRoadmapHead | None:
    """Load the fixed selector, returning ``None`` only when it is absent."""
    path = accepted_head_path(plans_dir, slug)
    if not path.exists():
        if path.is_symlink():
            raise RoadmapVersionError("accepted-head selector is a dangling symlink")
        return None
    head = parse_accepted_head(_read_bytes(path, description="accepted-head selector"))
    if head.roadmap_slug != slug:
        raise RoadmapVersionError("accepted-head selector does not match its roadmap")
    return head


def load_accepted_version(*, plans_dir: Path, slug: str) -> ResolvedRoadmapVersion | None:
    """Resolve only the complete immutable version named by the accepted head."""
    head = load_accepted_head(plans_dir=plans_dir, slug=slug)
    if head is None:
        return None
    return load_resolved_stored_version(
        plans_dir=plans_dir, slug=slug, version_id=head.version_id
    )


def is_roadmap_enrolled(*, plans_dir: Path, slug: str) -> bool:
    """Report selector absence only after fully validating a present selection."""
    return load_accepted_version(plans_dir=plans_dir, slug=slug) is not None


def _create_stored_version(
    *,
    roadmap_slug: str,
    version_kind: Literal["root", "candidate"],
    predecessor_version_id: str | None,
    content_identity: str | None,
    review_lineage_identity: str | None,
    brief_digest: str,
    artifact_digests: Sequence[str],
) -> StoredRoadmapVersion:
    artifact_digests = tuple(artifact_digests)
    if len(artifact_digests) != len(VERSION_ARTIFACT_INVENTORY):
        raise RoadmapVersionError("artifact digests must match the configured inventory")
    payload: dict[str, object] = {
        "schema_version": ROADMAP_VERSION_SCHEMA_VERSION,
        "roadmap_slug": roadmap_slug,
        "version_kind": version_kind,
        "predecessor_version_id": predecessor_version_id,
        "content_identity": content_identity,
        "review_lineage_identity": review_lineage_identity,
        "brief_member_name": STORED_BRIEF_FILENAME,
        "brief_digest": brief_digest,
        "artifact_members": [
            {
                "artifact_key": entry.artifact_key,
                "member_name": entry.member_name,
                "digest": digest,
            }
            for entry, digest in zip(VERSION_ARTIFACT_INVENTORY, artifact_digests, strict=True)
        ],
    }
    payload["version_id"] = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    try:
        return StoredRoadmapVersion.model_validate(payload)
    except PydanticValidationError as exc:
        raise RoadmapVersionError("stored version fields are malformed") from exc


def _stored_version_identity_payload(record: StoredRoadmapVersion) -> dict[str, object]:
    payload = record.model_dump(mode="json")
    del payload["version_id"]
    return payload


def _require_content_matches_record(
    record: StoredRoadmapVersion, content: RoadmapVersionContent
) -> None:
    if not isinstance(record, StoredRoadmapVersion) or not isinstance(
        content, RoadmapVersionContent
    ):
        raise RoadmapVersionError("stored version content requires a version record")
    if hashlib.sha256(content.brief_bytes).hexdigest() != record.brief_digest:
        raise RoadmapVersionError("stored brief bytes do not match their record digest")
    artifact_digests = sha256_digests(content.artifact_bytes)
    if artifact_digests != tuple(member.digest for member in record.artifact_members):
        raise RoadmapVersionError("stored artifact bytes do not match their record digests")


def _read_member_bytes(path: Path, *, expected_digest: str, description: str) -> bytes:
    data = _read_bytes(path, description=description)
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoadmapVersionError(f"{description} is not strict UTF-8") from exc
    if hashlib.sha256(data).hexdigest() != expected_digest:
        raise RoadmapVersionError(f"{description} does not match its recorded digest")
    return data


def _read_optional_bytes(path: Path, *, description: str) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        if path.is_symlink():
            raise RoadmapVersionError(f"{description} is a dangling symlink") from None
        return None
    except OSError as exc:
        raise RoadmapVersionError(f"cannot read {description} at {path}") from exc


def _read_bytes(path: Path, *, description: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise RoadmapVersionError(f"cannot read {description} at {path}") from exc


def _decode_strict_json_bytes(data: bytes, *, description: str) -> Any:
    if not isinstance(data, bytes):
        raise RoadmapVersionError(f"{description} must be UTF-8 bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoadmapVersionError(f"{description} must be strict UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonfinite_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise RoadmapVersionError(f"{description} is not strict JSON") from exc


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RoadmapVersionError("immutable version JSON must be canonical") from exc


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")
