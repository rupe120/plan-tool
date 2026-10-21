"""Persistent lifecycle state for seeds derived from a roadmap.

The roadmap artifacts are committed, reviewable documents.  A derived seed has
one additional, deliberately small bit of state that is not suitable for its
prose: whether feedback has made it stale.  This module owns that state and
the portable marker used when a draft is promoted into ``plan-seeds/``.

It is a stdlib-only leaf so both the roadmap orchestrator and ``create`` can
consult it without creating an import cycle.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


# Mirrors roadmap_artifacts directory names; this stdlib leaf cannot import it.
_DRAFT_SEED_DIRNAMES = ("plan-seed-drafts", "seeds")


SEED_STATE_FILENAME = "seed-state.json"
SEED_REFRESH_REPORT_FILENAME = "seed-refresh-report.md"
SEED_STATE_VERSION = 1

_MARKER_PREFIX = "<!-- plan-tool-roadmap-seed-state: "
_MARKER_SUFFIX = " -->"
_MARKER_RE = re.compile(
    r"<!-- plan-tool-roadmap-seed-state: (?P<payload>\{[^\n]*\}) -->"
)


class RoadmapSeedStateError(ValueError):
    """The seed lifecycle sidecar or a seed marker is malformed."""


@dataclass(frozen=True)
class SeedContinuation:
    """An invalidated roadmap seed that ``create`` must confirm explicitly."""

    plan_id: str
    roadmap_slug: str
    state_path: Path


@dataclass(frozen=True)
class TrackedSeedLocation:
    """A roadmap seed source resolved to its lifecycle sidecar.

    ``via_marker`` records which of :func:`locate_tracked_seed`'s two lookup
    strategies found it: ``True`` for a promoted ``plan-seeds/`` copy (or its
    archive), resolved through the durable HTML marker; ``False`` for a direct
    roadmap draft, resolved structurally by its parent directory. A promoted
    copy's own bytes are what a consumer will read, so its validity turns on
    the sidecar's persisted lifecycle status, not on whether the *draft* that
    originally produced it still exists on disk — the two kinds need
    different liveness checks, and this field is how a caller tells them
    apart without re-deriving the lookup strategy itself.
    """

    plan_id: str
    roadmap_slug: str
    state_path: Path
    via_marker: bool


def seed_state_path(roadmap_root: Path) -> Path:
    """Return the lifecycle sidecar that belongs to one roadmap directory."""
    return Path(roadmap_root) / SEED_STATE_FILENAME


def seed_refresh_report_path(roadmap_root: Path) -> Path:
    """Return the current refresh report path for one roadmap directory."""
    return Path(roadmap_root) / SEED_REFRESH_REPORT_FILENAME


def digest_text(text: str) -> str:
    """The stable content digest recorded for a generated draft seed."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def empty_seed_state() -> dict[str, Any]:
    """A new, validated lifecycle document."""
    return {"version": SEED_STATE_VERSION, "seeds": {}}


def load_seed_state(path: Path) -> dict[str, Any]:
    """Read a lifecycle sidecar, or return an empty state when it is absent."""
    path = Path(path)
    if not path.exists():
        return empty_seed_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoadmapSeedStateError(f"cannot read roadmap seed state {path}: {exc}") from exc
    return validate_seed_state(raw, path=path)


def snapshot_seed_state(state: Mapping[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    """Return an independent validated lifecycle snapshot for publication recovery."""
    return deepcopy(validate_seed_state(dict(state), path=path))


def invalidated_seed_state(
    state: Mapping[str, Any],
    *,
    draft_seed_paths: Mapping[str, str] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Return an independent state where every derived seed is stale."""
    snapshot = snapshot_seed_state(state, path=path)
    for plan_id, entry in snapshot["seeds"].items():
        if draft_seed_paths is not None and plan_id in draft_seed_paths:
            entry["draft_seed_path"] = draft_seed_paths[plan_id]
        entry["status"] = "invalidated"
    return snapshot


def render_seed_state(state: Mapping[str, Any], *, path: Path | None = None) -> bytes:
    """Serialize a validated seed-state snapshot for a generation member."""
    clean = snapshot_seed_state(state, path=path)
    return (json.dumps(clean, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_seed_state(raw: Any, *, path: Path | None = None) -> dict[str, Any]:
    """Validate the intentionally narrow JSON shape before a caller trusts it."""
    where = f" in {path}" if path is not None else ""
    if not isinstance(raw, dict):
        raise RoadmapSeedStateError(f"roadmap seed state must be an object{where}")
    if raw.get("version") != SEED_STATE_VERSION:
        raise RoadmapSeedStateError(
            f"roadmap seed state has unsupported version {raw.get('version')!r}{where}"
        )
    seeds = raw.get("seeds")
    if not isinstance(seeds, dict):
        raise RoadmapSeedStateError(f"roadmap seed state 'seeds' must be an object{where}")
    clean: dict[str, Any] = {"version": SEED_STATE_VERSION, "seeds": {}}
    for plan_id, entry in seeds.items():
        if not isinstance(plan_id, str) or not plan_id:
            raise RoadmapSeedStateError(f"roadmap seed state has an invalid plan id{where}")
        if not isinstance(entry, dict):
            raise RoadmapSeedStateError(
                f"roadmap seed state entry {plan_id!r} must be an object{where}"
            )
        draft_seed_path = entry.get("draft_seed_path")
        status = entry.get("status")
        if not isinstance(draft_seed_path, str) or not draft_seed_path:
            raise RoadmapSeedStateError(
                f"roadmap seed state entry {plan_id!r} has no draft_seed_path{where}"
            )
        if status not in {"current", "invalidated"}:
            raise RoadmapSeedStateError(
                f"roadmap seed state entry {plan_id!r} has invalid status {status!r}{where}"
            )
        digest = entry.get("digest")
        if digest is not None and (not isinstance(digest, str) or not digest):
            raise RoadmapSeedStateError(
                f"roadmap seed state entry {plan_id!r} has invalid digest{where}"
            )
        published = entry.get("published", False)
        if not isinstance(published, bool):
            raise RoadmapSeedStateError(
                f"roadmap seed state entry {plan_id!r} has invalid published flag{where}"
            )
        clean["seeds"][plan_id] = {
            "draft_seed_path": draft_seed_path,
            "status": status,
            "digest": digest,
            "published": published,
        }
    return clean


def write_seed_state(path: Path, state: Mapping[str, Any]) -> None:
    """Atomically persist a validated lifecycle sidecar."""
    path = Path(path)
    clean = snapshot_seed_state(state, path=path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(clean, indent=2, sort_keys=True) + "\n"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def has_invalidated_seed(state: Mapping[str, Any]) -> bool:
    """Whether any tracked seed still needs an explicit refresh."""
    return any(
        entry.get("status") == "invalidated"
        for entry in state.get("seeds", {}).values()
        if isinstance(entry, Mapping)
    )


def render_seed_state_marker(
    *, state_path: Path, repo_root: Path, roadmap_slug: str, plan_id: str
) -> str:
    """Render a comment that lets a promoted (or archived) seed find its state."""
    state_path = Path(state_path).resolve()
    repo_root = Path(repo_root).resolve()
    try:
        locator = str(state_path.relative_to(repo_root))
    except ValueError:
        # A custom ``--plans-dir`` may sit outside the repository.  Keep the
        # lifecycle contract sound there too: a consumed promoted seed still
        # needs its stale-use confirmation.  Moving that seed to another
        # checkout simply degrades to an absent sidecar (and no false claim of
        # freshness), while the original checkout remains fully traceable.
        locator = str(state_path)
    payload = json.dumps(
        {"plan_id": plan_id, "roadmap_slug": roadmap_slug, "state": locator},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{_MARKER_PREFIX}{payload}{_MARKER_SUFFIX}"


def _marker_payload(text: str) -> dict[str, str] | None:
    match = _MARKER_RE.search(text)
    if match is None:
        return None
    try:
        raw = json.loads(match.group("payload"))
    except json.JSONDecodeError as exc:
        raise RoadmapSeedStateError("roadmap seed lifecycle marker is malformed") from exc
    if not isinstance(raw, dict):
        raise RoadmapSeedStateError("roadmap seed lifecycle marker must be an object")
    plan_id = raw.get("plan_id")
    roadmap_slug = raw.get("roadmap_slug")
    state = raw.get("state")
    if (
        not isinstance(plan_id, str)
        or not plan_id
        or not isinstance(roadmap_slug, str)
        or not roadmap_slug
        or not isinstance(state, str)
    ):
        raise RoadmapSeedStateError("roadmap seed lifecycle marker is incomplete")
    return {"plan_id": plan_id, "roadmap_slug": roadmap_slug, "state": state}


def _structural_state_path(source: Path) -> Path | None:
    """Find state for a draft seed or its conventional archive copy."""
    source = Path(source).resolve()
    if source.parent.name in _DRAFT_SEED_DIRNAMES:
        return seed_state_path(source.parent.parent)
    if (
        source.parent.name == "archive"
        and source.parent.parent.name in _DRAFT_SEED_DIRNAMES
    ):
        return seed_state_path(source.parent.parent.parent)
    return None


def _matching_plan_id(state: Mapping[str, Any], source: Path) -> str | None:
    """Find the tracked row for a direct draft or its archived generation."""
    source = Path(source).resolve()
    for plan_id, entry in state.get("seeds", {}).items():
        draft_path = entry.get("draft_seed_path")
        if not isinstance(draft_path, str):
            continue
        expected = Path(draft_path)
        if (
            source.parent.name in _DRAFT_SEED_DIRNAMES
            and source.name == expected.name
        ):
            return plan_id
        if (
            source.parent.name == "archive"
            and source.parent.parent.name in _DRAFT_SEED_DIRNAMES
            and source.name.startswith(f"{expected.stem}.replaced")
            and source.suffix == expected.suffix
        ):
            return plan_id
    return None


def locate_tracked_seed(source: Path, *, repo_root: Path) -> TrackedSeedLocation | None:
    """Resolve a tracked draft or promoted seed regardless of its status.

    Direct roadmap drafts can locate their sidecar structurally.  Promoted
    seeds, including their archived copies, use the durable HTML marker added
    during promotion.  Unrelated seed files retain the historical no-prompt
    behavior.
    """
    source = Path(source).resolve()
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return None
    marker = _marker_payload(text)
    if marker is not None and marker["state"]:
        state_path = (Path(repo_root).resolve() / marker["state"]).resolve()
        state = load_seed_state(state_path)
        entry = state["seeds"].get(marker["plan_id"])
        if entry is not None:
            return TrackedSeedLocation(
                plan_id=marker["plan_id"],
                roadmap_slug=marker["roadmap_slug"],
                state_path=state_path,
                via_marker=True,
            )
        return None

    state_path = _structural_state_path(source)
    if state_path is None or not state_path.exists():
        return None
    state = load_seed_state(state_path)
    plan_id = _matching_plan_id(state, source)
    if plan_id is None:
        return None
    return TrackedSeedLocation(
        plan_id=plan_id,
        roadmap_slug=state_path.parent.name,
        state_path=state_path,
        via_marker=False,
    )


def invalidated_seed_continuation(
    source: Path, *, repo_root: Path
) -> SeedContinuation | None:
    """Return stale-seed confirmation data for ``source``, if it is tracked."""
    location = locate_tracked_seed(source, repo_root=repo_root)
    if location is None:
        return None
    state = load_seed_state(location.state_path)
    entry = state["seeds"].get(location.plan_id)
    if entry is None or entry["status"] != "invalidated":
        return None
    return SeedContinuation(
        plan_id=location.plan_id,
        roadmap_slug=location.roadmap_slug,
        state_path=location.state_path,
    )
