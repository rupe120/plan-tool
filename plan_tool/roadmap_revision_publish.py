"""Serialized, recoverable publication of roadmap semantic generations."""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plan_tool.fileio import durable_write_bytes
from plan_tool.roadmap_artifacts import (
    PlansArtifact,
    RoadmapArtifactError,
    parse_plans_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_feedback_ledger import (
    initial_ledger,
    render_ledger,
    roadmap_feedback_ledger_path,
)
from plan_tool.roadmap_gates import Violation
from plan_tool.roadmap_seed_state import (
    RoadmapSeedStateError,
    invalidated_seed_state,
    render_seed_state,
    seed_state_path,
    validate_seed_state,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    RoadmapSourceIdentityError,
    load_pending_generation,
    pending_generation_path,
    render_pending_generation,
)
from plan_tool.roadmap_versions import (
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    RoadmapVersionError,
    accepted_head_path,
    is_roadmap_enrolled,
    load_accepted_version,
    parse_accepted_head,
    render_accepted_head,
    render_stored_version,
    stored_artifact_path,
    stored_brief_path,
    stored_version_members,
    stored_version_record_path,
    version_directory_path,
)

try:  # POSIX advisory locking.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised on Windows.
    _fcntl = None

try:  # Windows advisory byte-range locking.
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX.
    _msvcrt = None


# The one enrolled decision-settlement generation kind, recognized below and
# reused by plan_tool.roadmap_decision_settlement_enrolled so the literal
# lives in exactly one place.
DECISION_SETTLEMENT_GENERATION_KIND = "decision-settlement"


class RoadmapWriterGuardError(RuntimeError):
    """A nested roadmap writer does not hold its expected guard."""


class RoadmapRevisionPublishError(ValueError):
    """A local revision candidate did not clear its publication contract."""

    def __init__(self, message: str, *, violations: Sequence[Violation] = ()) -> None:
        super().__init__(message)
        self.violations = tuple(violations)


class RoadmapPublicationRecoveryError(RoadmapRevisionPublishError):
    """An interrupted generation cannot be safely recovered."""


@dataclass(init=False)
class RoadmapWriterToken:
    """An active guard lease for one roadmap's participating writers."""

    _root: Path
    _file_descriptor: int
    _lock_implementation: str
    _active: bool = True

    @classmethod
    def _new(
        cls, root: Path, file_descriptor: int, lock_implementation: str
    ) -> "RoadmapWriterToken":
        token = object.__new__(cls)
        token._root = root
        token._file_descriptor = file_descriptor
        token._lock_implementation = lock_implementation
        token._active = True
        return token


def roadmap_writer_lock_path(plans_dir: Path, slug: str) -> Path:
    """Return the persistent advisory lock path for one roadmap."""
    roadmap_dir(Path(plans_dir), slug)
    return Path(plans_dir).resolve() / f".roadmap-{slug}.writer.lock"


# ``msvcrt.locking(LK_LOCK)`` retries contention internally roughly once a
# second for ~10s per call before raising. This many outer retries is a
# generous ~10-minute ceiling on genuine contention — long enough that any
# realistic roadmap-writer hold releases well before it, while still turning
# a permanent failure (lock file deleted/unwritable, not just contended)
# into a raised error instead of a silent, unbounded hang.
_MSVCRT_LOCK_MAX_ATTEMPTS = 60


def _acquire_writer_lock(file_descriptor: int) -> str:
    """Acquire the platform's cross-process advisory lock, blocking until held.

    ``roadmap_writer_guard`` promises to hold this guard "until exit", so a
    contended lock must wait, never fail. ``msvcrt.locking(LK_LOCK)`` alone
    does not honor that: it retries once a second for ~10s and then raises
    ``OSError``, which a contended second writer would otherwise surface as
    a spurious, misdiagnosable failure instead of the wait the fcntl branch
    gives for free. Looping around it restores the same indefinite-block
    contract on Windows, bounded by ``_MSVCRT_LOCK_MAX_ATTEMPTS`` so a
    non-contention failure (the lock file itself becomes unwritable, say)
    surfaces as an error rather than hanging forever — ``msvcrt.locking``
    raises the same ``OSError`` for both, so this cannot distinguish them
    by type; the bound is the guard against the permanent case.
    """
    if _fcntl is not None:
        _fcntl.flock(file_descriptor, _fcntl.LOCK_EX)
        return "fcntl"
    if _msvcrt is not None:
        if os.fstat(file_descriptor).st_size < 1:
            os.ftruncate(file_descriptor, 1)
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        for _attempt in range(_MSVCRT_LOCK_MAX_ATTEMPTS):
            try:
                _msvcrt.locking(file_descriptor, _msvcrt.LK_LOCK, 1)
                return "msvcrt"
            except OSError:
                continue
        raise RoadmapWriterGuardError(
            f"roadmap writer lock could not be acquired after {_MSVCRT_LOCK_MAX_ATTEMPTS} attempts"
        )
    raise RoadmapWriterGuardError("no cross-process file-lock implementation is available")


def _acquire_reader_lock(file_descriptor: int) -> str:
    """Acquire an existing lock without initializing its lock byte."""
    if _fcntl is not None:
        _fcntl.flock(file_descriptor, _fcntl.LOCK_SH)
        return "fcntl"
    if _msvcrt is not None:
        if os.fstat(file_descriptor).st_size < 1:
            raise RoadmapWriterGuardError(
                "roadmap reader lock must contain an initialized lock byte"
            )
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        for _attempt in range(_MSVCRT_LOCK_MAX_ATTEMPTS):
            try:
                _msvcrt.locking(file_descriptor, _msvcrt.LK_LOCK, 1)
                return "msvcrt"
            except OSError:
                continue
        raise RoadmapWriterGuardError(
            f"roadmap reader lock could not be acquired after {_MSVCRT_LOCK_MAX_ATTEMPTS} attempts"
        )
    raise RoadmapWriterGuardError("no cross-process file-lock implementation is available")


def _release_writer_lock(file_descriptor: int, implementation: str) -> None:
    """Release the advisory lock acquired by :func:`_acquire_writer_lock`."""
    if implementation == "fcntl" and _fcntl is not None:
        _fcntl.flock(file_descriptor, _fcntl.LOCK_UN)
    elif implementation == "msvcrt" and _msvcrt is not None:
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        _msvcrt.locking(file_descriptor, _msvcrt.LK_UNLCK, 1)


@contextlib.contextmanager
def roadmap_writer_guard(plans_dir: Path, slug: str) -> Iterator[RoadmapWriterToken]:
    """Hold the cross-process writer guard for one roadmap until exit."""
    root = roadmap_dir(Path(plans_dir), slug).resolve()
    lock_path = roadmap_writer_lock_path(plans_dir, slug)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    body_error: BaseException | None = None
    try:
        implementation = _acquire_writer_lock(descriptor)
        token = RoadmapWriterToken._new(root, descriptor, implementation)
        try:
            yield token
        except BaseException as exc:
            body_error = exc
            raise
        finally:
            token._active = False
            try:
                _release_writer_lock(descriptor, implementation)
            except OSError as exc:
                if body_error is not None:
                    body_error.add_note(f"roadmap writer lock could not be released: {exc}")
                else:
                    raise
    finally:
        try:
            os.close(descriptor)
        except OSError as exc:
            if body_error is not None:
                body_error.add_note(f"roadmap writer lock could not be closed: {exc}")
            else:
                raise


@contextlib.contextmanager
def roadmap_reader_guard(plans_dir: Path, slug: str) -> Iterator[None]:
    """Serialize a read-only inspection with writers without creating a lock."""
    lock_path = roadmap_writer_lock_path(plans_dir, slug)
    body_error: BaseException | None = None
    try:
        descriptor = os.open(lock_path, os.O_RDWR)
    except OSError as exc:
        raise RoadmapWriterGuardError(
            "roadmap reader requires an existing usable writer lock"
        ) from exc
    try:
        try:
            implementation = _acquire_reader_lock(descriptor)
        except OSError as exc:
            raise RoadmapWriterGuardError("roadmap reader lock could not be acquired") from exc
        try:
            yield
        except BaseException as exc:
            body_error = exc
            raise
        finally:
            try:
                _release_writer_lock(descriptor, implementation)
            except OSError as exc:
                if body_error is not None:
                    body_error.add_note(f"roadmap reader lock could not be released: {exc}")
                else:
                    raise RoadmapWriterGuardError(
                        "roadmap reader lock could not be released"
                    ) from exc
    finally:
        try:
            os.close(descriptor)
        except OSError as exc:
            if body_error is not None:
                body_error.add_note(f"roadmap reader lock could not be closed: {exc}")
            else:
                raise RoadmapWriterGuardError(
                    "roadmap reader lock could not be closed"
                ) from exc


def bootstrap_roadmap_reader_lock(plans_dir: Path, slug: str) -> None:
    """Create the persistent lock needed by a legacy reader observation.

    Call this before acquiring a reader lease; writer guards are non-reentrant.
    """
    if roadmap_writer_lock_path(plans_dir, slug).exists():
        return
    try:
        with roadmap_writer_guard(plans_dir, slug):
            pass
    except OSError as exc:
        raise RoadmapWriterGuardError("roadmap writer lock bootstrap failed") from exc


def require_roadmap_writer_token(token: RoadmapWriterToken, *, plans_dir: Path, slug: str) -> None:
    """Reject a nested write that is not covered by its owner's lease."""
    expected_root = roadmap_dir(Path(plans_dir), slug).resolve()
    if (
        not isinstance(token, RoadmapWriterToken)
        or not token._active
        or token._root != expected_root
    ):
        raise RoadmapWriterGuardError(
            f"roadmap writer for {slug!r} must reuse its active writer token"
        )


def build_enrolled_promotion_seed_state_member(
    *,
    plans_dir: Path,
    slug: str,
    promoted_plans: PlansArtifact,
    writer_token: RoadmapWriterToken,
) -> GenerationMember:
    """Prepare, without writing it, the enrolled promotion's seed invalidation."""
    require_roadmap_writer_token(writer_token, plans_dir=plans_dir, slug=slug)
    if not is_roadmap_enrolled(plans_dir=plans_dir, slug=slug):
        raise RoadmapRevisionPublishError(
            "promotion seed invalidation requires an enrolled roadmap"
        )
    root = roadmap_dir(plans_dir, slug)
    state_file = seed_state_path(root)
    previous = _member_state(state_file)
    state = _seed_state_from_member_bytes(previous, path=state_file)
    return GenerationMember(
        state_file.relative_to(root).as_posix(),
        previous,
        render_seed_state(
            invalidated_seed_state(
                state,
                draft_seed_paths=_plan_draft_seed_paths(promoted_plans),
                path=state_file,
            ),
            path=state_file,
        ),
    )


def recover_roadmap_publication(
    *, plans_dir: Path, slug: str, writer_token: RoadmapWriterToken
) -> None:
    """Recover only the recorded generation, never an unrecorded disk edit."""
    require_roadmap_writer_token(writer_token, plans_dir=plans_dir, slug=slug)
    root = roadmap_dir(plans_dir, slug)
    journal_path = pending_generation_path(root)
    try:
        generation = load_pending_generation(journal_path)
    except RoadmapSourceIdentityError as exc:
        raise RoadmapPublicationRecoveryError(str(exc)) from exc
    if generation is None:
        return

    try:
        accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
    except RoadmapVersionError as exc:
        raise RoadmapPublicationRecoveryError(
            "roadmap accepted-head state is invalid; refuse publication recovery"
        ) from exc
    if accepted is not None:
        if not _is_completed_version_owned_generation(
            generation,
            plans_dir=plans_dir,
            slug=slug,
            accepted=accepted,
        ):
            raise RoadmapPublicationRecoveryError(
                "enrolled roadmap refuses recovery of a non-version-owned generation"
            )
        states = [_member_state(root / member.relative_path) for member in generation.members]
        expected = [member.new_bytes for member in generation.members]
        if states != expected:
            raise RoadmapPublicationRecoveryError(
                "enrolled roadmap refuses incomplete version-owned publication recovery"
            )
        journal_path.unlink(missing_ok=True)
        return

    states = [_member_state(root / member.relative_path) for member in generation.members]
    old = [member.old_bytes for member in generation.members]
    new = [member.new_bytes for member in generation.members]
    if states == new or states == old:
        journal_path.unlink(missing_ok=True)
        return
    if any(
        state not in {member.old_bytes, member.new_bytes}
        for state, member in zip(states, generation.members, strict=True)
    ):
        raise RoadmapPublicationRecoveryError(
            "roadmap publication recovery found an unrecorded member change"
        )
    _replace_generation_members(root, generation.members, old)
    if [_member_state(root / member.relative_path) for member in generation.members] != old:
        raise RoadmapPublicationRecoveryError(
            "roadmap publication recovery could not restore its recorded generation"
        )
    journal_path.unlink(missing_ok=True)


def _is_completed_version_owned_generation(
    generation: PendingGeneration,
    *,
    plans_dir: Path,
    slug: str,
    accepted: object,
) -> bool:
    """Recognize only a selected, fully written root, selector, or decision-
    settlement version-storage-plus-selector generation."""
    record = getattr(accepted, "record", None)
    brief_bytes = getattr(accepted, "brief_bytes", None)
    artifact_bytes = getattr(accepted, "artifact_bytes", None)
    version_id = getattr(record, "version_id", None)
    artifact_members = getattr(record, "artifact_members", None)
    if not (
        isinstance(version_id, str)
        and isinstance(brief_bytes, bytes)
        and isinstance(artifact_bytes, tuple)
        and isinstance(artifact_members, tuple)
        and len(artifact_members) == len(artifact_bytes)
    ):
        return False

    root = roadmap_dir(plans_dir, slug)
    selector_path = accepted_head_path(plans_dir, slug)
    selector_relative_path = selector_path.relative_to(root).as_posix()
    try:
        selected_head = parse_accepted_head(_member_state(selector_path) or b"")
    except RoadmapVersionError:
        return False
    if selected_head.roadmap_slug != slug or selected_head.version_id != version_id:
        return False

    if generation.kind == "root-enrollment":
        if getattr(record, "version_kind", None) != "root":
            return False
        expected_members = [
            GenerationMember(
                stored_version_record_path(plans_dir, slug, version_id)
                .relative_to(root)
                .as_posix(),
                None,
                render_stored_version(record),
            ),
            GenerationMember(
                stored_brief_path(plans_dir, slug, version_id).relative_to(root).as_posix(),
                None,
                brief_bytes,
            ),
        ]
        expected_members.extend(
            GenerationMember(
                stored_artifact_path(plans_dir, slug, version_id, member.artifact_key)
                .relative_to(root)
                .as_posix(),
                None,
                data,
            )
            for member, data in zip(artifact_members, artifact_bytes, strict=True)
        )
        # The root publisher inserts exactly one initial ledger ahead of the selector.
        expected_members.append(
            GenerationMember(
                roadmap_feedback_ledger_path(plans_dir, slug).relative_to(root).as_posix(),
                None,
                render_ledger(initial_ledger(slug)),
            )
        )
        expected_members.append(
            GenerationMember(
                selector_relative_path,
                None,
                render_accepted_head(selected_head),
            )
        )
        return generation.members == tuple(expected_members)

    if generation.kind == DECISION_SETTLEMENT_GENERATION_KIND:
        if getattr(record, "version_kind", None) != "candidate":
            return False
        try:
            expected_version_members = stored_version_members(
                PreparedRoadmapVersion(
                    record=record,
                    content=RoadmapVersionContent(
                        brief_bytes=brief_bytes, artifact_bytes=artifact_bytes
                    ),
                )
            )
        except RoadmapVersionError:
            return False
        version_dir = version_directory_path(plans_dir, slug, version_id)
        expected_settlement_members = tuple(
            GenerationMember(
                (version_dir / member.member_name).relative_to(root).as_posix(),
                None,
                member.data,
            )
            for member in expected_version_members
        )
        if len(generation.members) != len(expected_settlement_members) + 1:
            return False
        if generation.members[: len(expected_settlement_members)] != expected_settlement_members:
            return False
        settlement_selector_member = generation.members[-1]
        if (
            settlement_selector_member.relative_path != selector_relative_path
            or settlement_selector_member.old_bytes is None
            or settlement_selector_member.new_bytes != render_accepted_head(selected_head)
        ):
            return False
        try:
            settlement_old_head = parse_accepted_head(settlement_selector_member.old_bytes)
        except RoadmapVersionError:
            return False
        return (
            settlement_old_head.roadmap_slug == slug
            and settlement_old_head.version_id == getattr(record, "predecessor_version_id", None)
        )

    if generation.kind != "review-seal-promotion":
        return False
    if not generation.members:
        return False
    member = generation.members[0]
    if member.relative_path != selector_relative_path or member.old_bytes is None:
        return False
    try:
        old_head = parse_accepted_head(member.old_bytes)
        new_head = parse_accepted_head(member.new_bytes or b"")
    except RoadmapVersionError:
        return False
    if not (
        old_head.roadmap_slug == slug
        and new_head.roadmap_slug == slug
        and new_head.version_id == version_id
        and member.new_bytes == render_accepted_head(selected_head)
    ):
        return False

    expected_members = [member]
    requires_release = _selected_promotion_requires_active_pointer_release(
        plans_dir=plans_dir, slug=slug, version_id=version_id
    )
    structural = _selected_promotion_is_structural(
        plans_dir=plans_dir, slug=slug, version_id=version_id
    )
    if requires_release is None or structural is None:
        if not _is_legacy_selector_only_promotion(plans_dir=plans_dir, slug=slug, record=record):
            return False
        requires_release = False if requires_release is None else requires_release
        structural = False if structural is None else structural
    release_member = _expected_completed_promotion_release_member(
        plans_dir=plans_dir, slug=slug, version_id=version_id
    )
    if requires_release and release_member is None:
        return False
    if release_member is not None:
        expected_members.append(release_member)

    if structural:
        if len(generation.members) <= len(expected_members):
            return False
        seed_member = _expected_completed_promotion_seed_member(
            plans_dir=plans_dir,
            slug=slug,
            accepted=accepted,
            previous_seed_state=generation.members[len(expected_members)].old_bytes,
        )
        if seed_member is None:
            return False
        expected_members.append(seed_member)
    return generation.members == tuple(expected_members)


def _expected_completed_promotion_release_member(
    *, plans_dir: Path, slug: str, version_id: str
) -> GenerationMember | None:
    """Rebuild the required batch-pointer release from its published bytes."""
    # Import lazily: candidate publication imports this module for its writer.
    from plan_tool.roadmap_candidate_run import (
        candidate_admission_path,
        load_candidate_admission,
        render_candidate_admission,
    )

    try:
        released = load_candidate_admission(plans_dir=plans_dir, slug=slug)
    except (OSError, ValueError):
        return None
    if released is None or released.root_version_id is None:
        return None
    if released.candidate_version_id is not None or released.active_candidate_version_id is not None:
        return None
    previous = released.model_copy(
        update={"candidate_version_id": version_id, "active_candidate_version_id": version_id}
    )
    root = roadmap_dir(plans_dir, slug)
    return GenerationMember(
        candidate_admission_path(plans_dir, slug).relative_to(root).as_posix(),
        render_candidate_admission(previous),
        render_candidate_admission(released),
    )


def _selected_promotion_is_structural(*, plans_dir: Path, slug: str, version_id: str) -> bool | None:
    """Ask the stack-route derivation about the promoted candidate's stack; ``None`` when it cannot tell.

    The writer asks with the same two ids, so an underivable stack is never read as "not structural".
    """
    # Import lazily: candidate publication depends on the publication writer.
    from plan_tool.roadmap_candidate_run import candidate_stack_route, load_stored_candidate_proposal

    try:
        candidate = load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=slug, candidate_version_id=version_id
        )
        return candidate_stack_route(
            plans_dir=plans_dir, slug=slug,
            tip_version_id=version_id, root_version_id=candidate.evidence.root_version_id,
        ).is_structural
    except (OSError, ValueError):
        return None


def _selected_promotion_requires_active_pointer_release(
    *, plans_dir: Path, slug: str, version_id: str
) -> bool | None:
    """Tell whether the stored candidate belongs to the batch pointer lifecycle."""
    # Import lazily: candidate publication depends on the publication writer.
    from plan_tool.roadmap_candidate_run import load_stored_candidate_proposal

    try:
        candidate = load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=slug, candidate_version_id=version_id
        )
    except (OSError, ValueError):
        return None
    return candidate.evidence.root_version_id is not None


def _is_legacy_selector_only_promotion(*, plans_dir: Path, slug: str, record: object) -> bool:
    """Permit absent candidate evidence only for a non-batch historical seal."""
    from plan_tool.roadmap_candidate_run import (
        candidate_evidence_path,
        load_candidate_admission,
    )
    from plan_tool.roadmap_versions import INITIAL_EMPTY_REVIEW_LINEAGE_ID

    version_id = getattr(record, "version_id", None)
    if not isinstance(version_id, str) or getattr(record, "review_lineage_identity", None) == INITIAL_EMPTY_REVIEW_LINEAGE_ID:
        return False
    path = candidate_evidence_path(plans_dir, slug, version_id)
    if path.exists() or path.is_symlink():
        return False
    try:
        admission = load_candidate_admission(plans_dir=plans_dir, slug=slug)
    except (OSError, ValueError):
        return False
    return admission is None or admission.root_version_id is None


def _expected_completed_promotion_seed_member(
    *, plans_dir: Path, slug: str, accepted: object, previous_seed_state: bytes | None
) -> GenerationMember | None:
    """Rebuild a structural promotion seed update from the accepted plans bytes."""
    record = getattr(accepted, "record", None)
    artifact_members = getattr(record, "artifact_members", None)
    artifact_bytes = getattr(accepted, "artifact_bytes", None)
    if not isinstance(artifact_members, tuple) or not isinstance(artifact_bytes, tuple):
        return None
    try:
        plans_index = next(
            index
            for index, artifact_member in enumerate(artifact_members)
            if artifact_member.artifact_key == "plans"
        )
        promoted_plans = parse_plans_artifact(artifact_bytes[plans_index].decode("utf-8"))
    except (AttributeError, IndexError, StopIteration, UnicodeError, RoadmapArtifactError, ValueError):
        return None
    root = roadmap_dir(plans_dir, slug)
    state_file = seed_state_path(root)
    try:
        previous = _seed_state_from_member_bytes(previous_seed_state, path=state_file)
    except RoadmapRevisionPublishError:
        return None
    return GenerationMember(
        state_file.relative_to(root).as_posix(),
        previous_seed_state,
        render_seed_state(
            invalidated_seed_state(
                previous,
                draft_seed_paths=_plan_draft_seed_paths(promoted_plans),
                path=state_file,
            ),
            path=state_file,
        ),
    )


def _member_state(path: Path) -> bytes | None:
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        return None


def _seed_state_from_member_bytes(data: bytes | None, *, path: Path) -> dict[str, Any]:
    """Validate journaled seed bytes, treating recorded absence as empty state."""
    if data is None:
        return validate_seed_state({"version": 1, "seeds": {}}, path=path)
    try:
        return validate_seed_state(json.loads(data.decode("utf-8")), path=path)
    except (UnicodeError, json.JSONDecodeError, RoadmapSeedStateError) as exc:
        raise RoadmapRevisionPublishError(f"invalid recorded roadmap seed state: {exc}") from exc


def _plan_draft_seed_paths(artifact: Any) -> Mapping[str, str] | None:
    """Return the published plans artifact's current draft paths, if any."""
    if not isinstance(artifact, PlansArtifact):
        return None
    return {plan.id: plan.draft_seed_path for plan in artifact.plans}


def publish_roadmap_generation(
    generation: PendingGeneration,
    *,
    plans_dir: Path,
    slug: str,
    writer_token: RoadmapWriterToken,
    before_replace: Callable[[], None] | None = None,
) -> None:
    """Publish recorded member bytes under the active roadmap writer lease."""
    require_roadmap_writer_token(writer_token, plans_dir=plans_dir, slug=slug)
    root = roadmap_dir(plans_dir, slug)
    journal_path = pending_generation_path(root)
    if journal_path.exists():
        raise RoadmapPublicationRecoveryError(
            f"roadmap {slug}: an interrupted publication left its journal at "
            f"{journal_path}; recover it before publishing. Re-run "
            f"`plan-tool roadmap {slug} --from-existing <brief>`: it recovers a "
            "completed or rolled-back first-run journal, then refuses with 'already "
            "has an accepted head', which is the expected outcome; then retry this command"
        )
    durable_write_bytes(journal_path, render_pending_generation(generation))
    if before_replace is not None:
        try:
            before_replace()
        except BaseException:
            # The journal precedes the final source/feedback recheck so a
            # process cannot die between validation and replacement. A refused
            # recheck has changed no generation member, however, and leaving
            # that journal would turn a safe refusal into a false recovery.
            journal_path.unlink(missing_ok=True)
            raise
    _replace_generation_members(
        root, generation.members, [member.new_bytes for member in generation.members]
    )
    observed = [_member_state(root / member.relative_path) for member in generation.members]
    expected = [member.new_bytes for member in generation.members]
    if observed != expected:
        raise RoadmapPublicationRecoveryError(
            "roadmap publication did not commit its recorded generation"
        )
    journal_path.unlink(missing_ok=True)


def _replace_generation_members(
    root: Path, members: Sequence[GenerationMember], values: Sequence[bytes | None]
) -> None:
    for member, value in zip(members, values, strict=True):
        path = root / member.relative_path
        if value is None:
            path.unlink(missing_ok=True)
        else:
            durable_write_bytes(path, value)


