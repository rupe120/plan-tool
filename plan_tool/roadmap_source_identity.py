"""Publication journal shapes and the ephemeral feedback snapshot."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from plan_tool.roadmap_json import unwrap_enum_value


SOURCE_IDENTITY_VERSION = 1
PENDING_GENERATION_FILENAME = ".roadmap-publication-pending.json"
SHA256_DIGEST_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)


class RoadmapSourceIdentityError(ValueError):
    """A pending publication record cannot be trusted."""


@dataclass(frozen=True)
class FeedbackSnapshot:
    """One ordered, ephemeral review-input value for a publication attempt."""

    projection: list[Any]
    digest: str


@dataclass(frozen=True)
class GenerationMember:
    """One recoverable member with explicit old and new byte states."""

    relative_path: str
    old_bytes: bytes | None
    new_bytes: bytes | None


@dataclass(frozen=True)
class PendingGeneration:
    """A complete generation recorded before any of its members change."""

    kind: str
    members: tuple[GenerationMember, ...]


def pending_generation_path(roadmap_root: Path) -> Path:
    """Return the one active recoverable-publication journal path."""
    return Path(roadmap_root) / PENDING_GENERATION_FILENAME


def feedback_snapshot(artifact: Any) -> FeedbackSnapshot:
    """Capture ordered feedback for one bounded publication attempt only."""
    if dataclasses.is_dataclass(artifact):
        feedback = getattr(artifact, "feedback", ())
    elif isinstance(artifact, Mapping):
        feedback = artifact.get("feedback", ())
    else:
        raise RoadmapSourceIdentityError("roadmap artifact feedback must be addressable")
    projection = _canonical_value(feedback)
    if not isinstance(projection, list):
        raise RoadmapSourceIdentityError("roadmap artifact feedback must be a sequence")
    return FeedbackSnapshot(projection=projection, digest=_digest_value(projection))


def render_pending_generation(generation: PendingGeneration) -> bytes:
    """Serialize a complete, path-contained publication journal."""
    _validate_generation(generation)
    return _json_bytes(
        {
            "version": SOURCE_IDENTITY_VERSION,
            "kind": generation.kind,
            "members": [
                {
                    "path": member.relative_path,
                    "old": _encode_member_bytes(member.old_bytes),
                    "new": _encode_member_bytes(member.new_bytes),
                }
                for member in generation.members
            ],
        }
    )


def load_pending_generation(path: Path) -> PendingGeneration | None:
    """Load one journal, retaining explicit absence for each member state."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        raw = _strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RoadmapSourceIdentityError(
            f"cannot read roadmap publication journal {path}: {exc}"
        ) from exc
    if (
        not isinstance(raw, dict)
        or type(raw.get("version")) is not int
        or raw["version"] != SOURCE_IDENTITY_VERSION
    ):
        raise RoadmapSourceIdentityError(
            f"roadmap publication journal {path} has unsupported format"
        )
    members_raw = raw.get("members")
    if not isinstance(raw.get("kind"), str) or not isinstance(members_raw, list):
        raise RoadmapSourceIdentityError(f"roadmap publication journal {path} is malformed")
    try:
        generation = PendingGeneration(
            kind=raw["kind"],
            members=tuple(
                GenerationMember(
                    relative_path=member["path"],
                    old_bytes=_decode_member_bytes(member["old"]),
                    new_bytes=_decode_member_bytes(member["new"]),
                )
                for member in members_raw
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RoadmapSourceIdentityError(
            f"roadmap publication journal {path} is malformed"
        ) from exc
    _validate_generation(generation)
    return generation


def _canonical_value(value: Any) -> Any:
    unwrapped = unwrap_enum_value(value)
    if unwrapped is not value:
        return _canonical_value(unwrapped)
    if dataclasses.is_dataclass(value):
        return {
            field.name: _canonical_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise RoadmapSourceIdentityError("roadmap artifact projection keys must be strings")
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise RoadmapSourceIdentityError(
        f"roadmap artifact projection has unsupported value {type(value).__name__}"
    )


def _digest_value(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RoadmapSourceIdentityError(
            "roadmap source identity JSON must not contain non-finite values"
        ) from exc
    return (text + "\n").encode("utf-8")


def _strict_json_loads(text: str) -> Any:
    """Reject JSON forms that cannot be faithfully trusted as state."""
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_nonfinite_json_constant,
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")


def _encode_member_bytes(value: bytes | None) -> dict[str, str | bool]:
    if value is None:
        return {"present": False}
    return {"present": True, "data": base64.b64encode(value).decode("ascii")}


def _decode_member_bytes(raw: Any) -> bytes | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("present"), bool):
        raise ValueError("member state is malformed")
    if not raw["present"]:
        if set(raw) != {"present"}:
            raise ValueError("absent member has data")
        return None
    data = raw.get("data")
    if set(raw) != {"present", "data"} or not isinstance(data, str):
        raise ValueError("present member has no data")
    try:
        return base64.b64decode(data.encode("ascii"), validate=True)
    except ValueError as exc:
        raise ValueError("member data is not base64") from exc


def _validate_generation(generation: PendingGeneration) -> None:
    if not isinstance(generation.kind, str) or not generation.kind or not generation.members:
        raise RoadmapSourceIdentityError("roadmap publication journal is malformed")
    paths: set[str] = set()
    for member in generation.members:
        path = member.relative_path
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or path in paths
            or not isinstance(member.old_bytes, (bytes, type(None)))
            or not isinstance(member.new_bytes, (bytes, type(None)))
        ):
            raise RoadmapSourceIdentityError("roadmap publication journal member is malformed")
        paths.add(path)
