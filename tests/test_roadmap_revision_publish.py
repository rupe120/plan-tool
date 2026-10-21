"""Tests for serialized local roadmap revision publication."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from types import SimpleNamespace
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool import roadmap_candidate_run, roadmap_revision_publish
from plan_tool.roadmap import STAGES, RoadmapStage, _with_initial_feedback_ledger
from plan_tool.roadmap_feedback_ledger import (
    LedgerState,
    initial_ledger,
    render_ledger,
    roadmap_feedback_ledger_path,
)
from plan_tool.roadmap_candidate import CandidateOperationClassification
from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    EntityRow,
    FeedbackReopenRecord,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    OrderingEntry,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RejectedAlternative,
    RoadmapArtifactError,
    constraints_path,
    domain_path,
    plans_path,
    roadmap_dir,
)
from plan_tool.roadmap_decision_settlement import (
    build_decision_settlement_candidate,
    resolve_decision_settlement_selector,
)
from plan_tool.roadmap_revision_publish import (
    RoadmapPublicationRecoveryError,
    RoadmapRevisionPublishError,
    RoadmapWriterGuardError,
    build_enrolled_promotion_seed_state_member,
    bootstrap_roadmap_reader_lock,
    publish_roadmap_generation,
    recover_roadmap_publication,
    require_roadmap_writer_token,
    roadmap_reader_guard,
    roadmap_writer_lock_path,
    roadmap_writer_guard,
)
from plan_tool.roadmap_seed_state import (
    RoadmapSeedStateError,
    digest_text,
    load_seed_state,
    seed_state_path,
    write_seed_state,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    load_pending_generation,
    pending_generation_path,
    render_pending_generation,
)
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_NAMESPACE_DIRNAME,
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
)


def _hold_writer_guard(
    plans_dir: str,
    slug: str,
    entered: multiprocessing.synchronize.Event,
    release: multiprocessing.synchronize.Event,
) -> None:
    with roadmap_writer_guard(Path(plans_dir), slug):
        entered.set()
        release.wait(5)


def _hold_reader_guard(
    plans_dir: str,
    slug: str,
    entered: multiprocessing.synchronize.Event,
    release: multiprocessing.synchronize.Event,
) -> None:
    with roadmap_reader_guard(Path(plans_dir), slug):
        entered.set()
        release.wait(5)


def _stage(
    gates,
    *,
    number: int = 1,
    artifact_key: str = "domain",
):
    return RoadmapStage(
        number=number,
        name=artifact_key,
        prompt_filename="unused",
        artifact_key=artifact_key,
        parse=lambda text: {"canonical": text},
        render=lambda candidate: f"canonical:{candidate}",
        gates=gates,
    )


def test_enrolled_promotion_seed_member_invalidates_tracked_entries_without_touching_seed_files(
    tmp_path: Path,
) -> None:
    slug = "promotion-seeds"
    _enroll_decision_settlement_root(tmp_path, slug)
    root = roadmap_dir(tmp_path, slug)
    draft = root / "plan-seed-drafts" / "renamed.md"
    promoted = tmp_path / "plan-seeds" / "plan-a.md"
    draft.parent.mkdir(parents=True)
    promoted.parent.mkdir()
    draft.write_text("draft bytes", encoding="utf-8")
    promoted.write_text("promoted bytes", encoding="utf-8")
    state_file = seed_state_path(root)
    before = _seed_state()
    write_seed_state(state_file, before)
    plans = PlansArtifact(
        plans=(
            PlanRow(
                "plan-a", "Plan A", PlanDisposition.KEEP, (), "plan-seed-drafts/renamed.md", "Keep A."
            ),
        ),
        ordering=(OrderingEntry("plan-a"),),
        assumptions=(),
        decisions=(),
        body="plans\n",
    )

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        member = build_enrolled_promotion_seed_state_member(
            plans_dir=tmp_path, slug=slug, promoted_plans=plans, writer_token=writer_token
        )

    assert member.relative_path == "seed-state.json"
    assert member.old_bytes == state_file.read_bytes()
    assert load_seed_state(state_file) == before
    assert draft.read_text(encoding="utf-8") == "draft bytes"
    assert promoted.read_text(encoding="utf-8") == "promoted bytes"
    assert member.new_bytes is not None
    updated = json.loads(member.new_bytes)
    assert updated["seeds"]["plan-a"] == before["seeds"]["plan-a"] | {
        "draft_seed_path": "plan-seed-drafts/renamed.md",
        "status": "invalidated",
    }
    assert updated["seeds"]["plan-b"] == before["seeds"]["plan-b"] | {"status": "invalidated"}


def _seed_state() -> dict[str, object]:
    return {
        "version": 1,
        "seeds": {
            "plan-a": {
                "draft_seed_path": "seeds/plan-a.md",
                "status": "current",
                "digest": digest_text("draft a"),
                "published": False,
            },
            "plan-b": {
                "draft_seed_path": "seeds/plan-b.md",
                "status": "current",
                "digest": digest_text("draft b"),
                "published": True,
            },
        },
    }


def _wait_for(process: multiprocessing.Process) -> None:
    process.join(5)
    assert process.exitcode == 0


def test_writer_guard_blocks_a_second_process_for_the_same_roadmap(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    second_entered = context.Event()
    first = context.Process(
        target=_hold_writer_guard,
        args=(str(tmp_path), "demo", entered, release),
    )
    second = context.Process(
        target=_hold_writer_guard,
        args=(str(tmp_path), "demo", second_entered, release),
    )
    first.start()
    assert entered.wait(5)
    second.start()
    try:
        assert not second_entered.wait(0.2)
        release.set()
        assert second_entered.wait(5)
    finally:
        release.set()
        _wait_for(first)
        _wait_for(second)


def test_writer_guard_does_not_block_a_different_roadmap(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    other_entered = context.Event()
    first = context.Process(
        target=_hold_writer_guard,
        args=(str(tmp_path), "one", entered, release),
    )
    second = context.Process(
        target=_hold_writer_guard,
        args=(str(tmp_path), "two", other_entered, release),
    )
    first.start()
    assert entered.wait(5)
    second.start()
    try:
        assert other_entered.wait(5)
    finally:
        release.set()
        _wait_for(first)
        _wait_for(second)


def test_reader_guard_blocks_a_writer_for_the_same_roadmap(
    tmp_path: Path,
) -> None:
    with roadmap_writer_guard(tmp_path, "demo"):
        pass
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    writer_entered = context.Event()
    reader = context.Process(
        target=_hold_reader_guard,
        args=(str(tmp_path), "demo", entered, release),
    )
    writer = context.Process(
        target=_hold_writer_guard,
        args=(str(tmp_path), "demo", writer_entered, release),
    )
    reader.start()
    assert entered.wait(5)
    writer.start()
    try:
        assert not writer_entered.wait(0.2)
        release.set()
        assert writer_entered.wait(5)
    finally:
        release.set()
        _wait_for(reader)
        _wait_for(writer)


@pytest.mark.skipif(
    roadmap_revision_publish._fcntl is None,
    reason="shared advisory locks are a POSIX capability",
)
def test_reader_guard_allows_concurrent_readers_for_the_same_roadmap(
    tmp_path: Path,
) -> None:
    with roadmap_writer_guard(tmp_path, "demo"):
        pass
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    second_entered = context.Event()
    first = context.Process(
        target=_hold_reader_guard,
        args=(str(tmp_path), "demo", entered, release),
    )
    second = context.Process(
        target=_hold_reader_guard,
        args=(str(tmp_path), "demo", second_entered, release),
    )
    first.start()
    assert entered.wait(5)
    second.start()
    try:
        assert second_entered.wait(5)
    finally:
        release.set()
        _wait_for(first)
        _wait_for(second)


def test_reader_guard_does_not_block_a_writer_for_a_different_roadmap(
    tmp_path: Path,
) -> None:
    with roadmap_writer_guard(tmp_path, "one"):
        pass
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    writer_entered = context.Event()
    reader = context.Process(
        target=_hold_reader_guard,
        args=(str(tmp_path), "one", entered, release),
    )
    writer = context.Process(
        target=_hold_writer_guard,
        args=(str(tmp_path), "two", writer_entered, release),
    )
    reader.start()
    assert entered.wait(5)
    writer.start()
    try:
        assert writer_entered.wait(5)
    finally:
        release.set()
        _wait_for(reader)
        _wait_for(writer)


def test_reader_guard_requires_an_existing_lock_without_creating_one(
    tmp_path: Path,
) -> None:
    lock_path = roadmap_writer_lock_path(tmp_path, "demo")

    with pytest.raises(RoadmapWriterGuardError, match="existing usable writer lock"):
        with roadmap_reader_guard(tmp_path, "demo"):
            pytest.fail("a missing lock must not yield a reader lease")

    assert not roadmap_dir(tmp_path, "demo").exists()
    assert not lock_path.exists()


def test_reader_lock_bootstrap_translates_an_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    @contextmanager
    def broken_writer_guard(_plans_dir: Path, _slug: str):
        raise OSError("lock creation failed")
        yield  # pragma: no cover - makes this a context-manager generator.

    monkeypatch.setattr(roadmap_revision_publish, "roadmap_writer_guard", broken_writer_guard)

    with pytest.raises(RoadmapWriterGuardError, match="lock bootstrap failed"):
        bootstrap_roadmap_reader_lock(tmp_path, "demo")


def test_reader_lock_bootstrap_skips_writer_acquisition_for_existing_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with roadmap_writer_guard(tmp_path, "demo"):
        pass
    monkeypatch.setattr(
        roadmap_revision_publish,
        "roadmap_writer_guard",
        lambda *_args, **_kwargs: pytest.fail("an existing lock must not bootstrap again"),
    )

    bootstrap_roadmap_reader_lock(tmp_path, "demo")


def test_reader_guard_preserves_lock_bytes_and_never_yields_a_writer_token(
    tmp_path: Path,
) -> None:
    with roadmap_writer_guard(tmp_path, "demo"):
        pass
    lock_path = roadmap_writer_lock_path(tmp_path, "demo")
    original = b"already initialized lock bytes"
    lock_path.write_bytes(original)

    with roadmap_reader_guard(tmp_path, "demo") as reader_token:
        assert reader_token is None
        with pytest.raises(RoadmapWriterGuardError):
            require_roadmap_writer_token(reader_token, plans_dir=tmp_path, slug="demo")

    assert lock_path.read_bytes() == original


@pytest.mark.parametrize(
    ("guard", "cleanup", "note"),
    (
        ("reader", "release", "could not be released: release failed"),
        ("reader", "close", "could not be closed: close failed"),
        ("writer", "release", "could not be released: release failed"),
        ("writer", "close", "could not be closed: close failed"),
    ),
)
def test_roadmap_guards_preserve_body_error_when_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    guard: str,
    cleanup: str,
    note: str,
) -> None:
    if guard == "reader":
        with roadmap_writer_guard(tmp_path, "demo"):
            pass

    if cleanup == "release":
        def release_failure(*_args: object) -> None:
            raise OSError("release failed")

        monkeypatch.setattr(
            roadmap_revision_publish, "_release_writer_lock", release_failure
        )
    else:
        original_close = roadmap_revision_publish.os.close

        def close_failure(descriptor: int) -> None:
            original_close(descriptor)
            raise OSError("close failed")

        monkeypatch.setattr(roadmap_revision_publish.os, "close", close_failure)

    with pytest.raises(RuntimeError, match="body failure") as caught:
        guard_context = (
            roadmap_reader_guard if guard == "reader" else roadmap_writer_guard
        )
        with guard_context(tmp_path, "demo"):
            raise RuntimeError("body failure")

    assert any(note in entry for entry in caught.value.__notes__)


def _open_lock_fd(tmp_path: Path) -> int:
    return os.open(tmp_path / "fake.lock", os.O_CREAT | os.O_RDWR, 0o644)


def test_msvcrt_lock_retries_transient_contention_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    class FlakyMsvcrt:
        LK_LOCK = 1

        @staticmethod
        def locking(_fd: int, _mode: int, _byte_count: int) -> None:
            calls.append(1)
            if len(calls) < 3:
                raise OSError("still contended")

    monkeypatch.setattr(roadmap_revision_publish, "_fcntl", None)
    monkeypatch.setattr(roadmap_revision_publish, "_msvcrt", FlakyMsvcrt)
    fd = _open_lock_fd(tmp_path)

    assert roadmap_revision_publish._acquire_writer_lock(fd) == "msvcrt"
    assert len(calls) == 3


def test_msvcrt_lock_gives_up_after_max_attempts_instead_of_hanging_forever(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A permanent failure (not just contention) must surface as an error —
    ``msvcrt.locking`` raises the same ``OSError`` for both, so an unbounded
    retry can never tell them apart and would hang forever on this one."""
    calls: list[int] = []

    class AlwaysBusyMsvcrt:
        LK_LOCK = 1

        @staticmethod
        def locking(_fd: int, _mode: int, _byte_count: int) -> None:
            calls.append(1)
            raise OSError("permanently unavailable")

    monkeypatch.setattr(roadmap_revision_publish, "_fcntl", None)
    monkeypatch.setattr(roadmap_revision_publish, "_msvcrt", AlwaysBusyMsvcrt)
    monkeypatch.setattr(roadmap_revision_publish, "_MSVCRT_LOCK_MAX_ATTEMPTS", 3)
    fd = _open_lock_fd(tmp_path)

    with pytest.raises(RoadmapWriterGuardError, match="3 attempts"):
        roadmap_revision_publish._acquire_writer_lock(fd)
    assert len(calls) == 3


def test_legacy_stage_file_publishers_and_the_unenrolled_guard_are_gone_and_recovery_remains() -> None:
    """Deliberate: the version store is the only write target, so no publisher writes a top-level
    stage file or baseline; journal recovery stays because the first-run root publication needs it."""
    missing = object()
    for removed in (
        "publish_structural_revision_proof",
        "StructuralRevisionPublicationError",
        "StaleStructuralRevisionPublicationError",
        "publish_stage_artifact",
        "enroll_stage_baselines",
        "publish_revision_candidate",
        "publish_feedback_reopen_candidate",
        "require_unenrolled_roadmap_writer",
        "EnrolledRoadmapWriteError",
        "StaleFeedbackPublicationError",
        "preinvalidate_roadmap_seeds",
        "reject_direct_artifact_deletions",
    ):
        assert getattr(roadmap_revision_publish, removed, missing) is missing, removed
    for kept in (
        "publish_roadmap_generation",
        "recover_roadmap_publication",
        "roadmap_writer_guard",
        "roadmap_reader_guard",
        "build_enrolled_promotion_seed_state_member",
    ):
        assert callable(getattr(roadmap_revision_publish, kept, missing)), kept


def test_no_production_module_writes_a_top_level_stage_file() -> None:
    """Name scan only (the broader read/write guard is a later step's): no roadmap module names a
    removed stage-file writer, stage baseline, checkpoint, or ``source.json`` writer."""
    package = Path(roadmap_revision_publish.__file__).parent
    removed = (
        "publish_stage_artifact",
        "enroll_stage_baselines",
        "capture_checkpoint",
        "_write_brief_source",
    )
    modules = sorted(package.glob("roadmap*.py"))
    assert modules
    offenders = {
        (path.name, name)
        for path in modules
        for name in removed
        if name in path.read_text(encoding="utf-8")
    }
    assert offenders == set()


def test_writer_guard_initializes_one_msvcrt_lock_byte_before_locking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_sizes: list[int] = []

    class RecordingMsvcrt:
        LK_LOCK = 1

        @staticmethod
        def locking(file_descriptor: int, _mode: int, _byte_count: int) -> None:
            observed_sizes.append(os.fstat(file_descriptor).st_size)

    monkeypatch.setattr(roadmap_revision_publish, "_fcntl", None)
    monkeypatch.setattr(roadmap_revision_publish, "_msvcrt", RecordingMsvcrt)
    file_descriptor = _open_lock_fd(tmp_path)
    try:
        assert os.fstat(file_descriptor).st_size == 0
        assert roadmap_revision_publish._acquire_writer_lock(file_descriptor) == "msvcrt"
        assert observed_sizes == [1]
        assert os.pread(file_descriptor, 1, 0) == b"\0"
    finally:
        os.close(file_descriptor)


def test_exposed_generation_publication_requires_an_active_matching_writer_token(
    tmp_path: Path,
) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    generation = PendingGeneration(
        "test-generation",
        (
            GenerationMember("01-domain.md", None, b"new artifact"),
        ),
    )
    journal = pending_generation_path(root)

    with pytest.raises(RoadmapWriterGuardError):
        publish_roadmap_generation(
            generation,
            plans_dir=tmp_path,
            slug=slug,
            writer_token=None,  # type: ignore[arg-type]
        )

    with roadmap_writer_guard(tmp_path, slug) as inactive_token:
        pass
    with pytest.raises(RoadmapWriterGuardError):
        publish_roadmap_generation(
            generation,
            plans_dir=tmp_path,
            slug=slug,
            writer_token=inactive_token,
        )

    with roadmap_writer_guard(tmp_path, "other") as foreign_token:
        with pytest.raises(RoadmapWriterGuardError):
            publish_roadmap_generation(
                generation,
                plans_dir=tmp_path,
                slug=slug,
                writer_token=foreign_token,
            )

    assert not (root / "01-domain.md").exists()
    assert not journal.exists()


def test_exposed_generation_publication_journals_before_final_recheck_and_cleans_up_after_success(
    tmp_path: Path,
) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    root.mkdir(parents=True)
    first = root / "01-domain.md"
    first.write_bytes(b"old artifact")
    generation = PendingGeneration(
        "test-generation",
        (
            GenerationMember("01-domain.md", b"old artifact", b"new artifact"),
            GenerationMember(".roadmap-baselines/domain.json", None, b"new baseline"),
        ),
    )
    journal = pending_generation_path(root)
    observed: dict[str, bytes | None] = {}

    def final_recheck() -> None:
        observed["journal"] = journal.read_bytes()
        observed["first"] = first.read_bytes()
        observed["second"] = roadmap_revision_publish._member_state(
            root / ".roadmap-baselines/domain.json"
        )

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        publish_roadmap_generation(
            generation,
            plans_dir=tmp_path,
            slug=slug,
            writer_token=writer_token,
            before_replace=final_recheck,
        )

    assert observed == {
        "journal": render_pending_generation(generation),
        "first": b"old artifact",
        "second": None,
    }
    assert first.read_bytes() == b"new artifact"
    assert (root / ".roadmap-baselines/domain.json").read_bytes() == b"new baseline"
    assert not journal.exists()


def test_version_owned_recovery_refuses_candidate_shaped_root_enrollment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "demo"
    plans_dir = tmp_path / "plans"
    version_id = "a" * 64
    root = roadmap_dir(plans_dir, slug)
    selector = roadmap_revision_publish.accepted_head_path(plans_dir, slug)
    record = SimpleNamespace(version_id=version_id, version_kind="candidate", artifact_members=())
    accepted = SimpleNamespace(record=record, brief_bytes=b"brief", artifact_bytes=())

    monkeypatch.setattr(roadmap_revision_publish, "_member_state", lambda _path: b"head")
    monkeypatch.setattr(
        roadmap_revision_publish,
        "parse_accepted_head",
        lambda _raw: SimpleNamespace(roadmap_slug=slug, version_id=version_id),
    )
    monkeypatch.setattr(roadmap_revision_publish, "render_stored_version", lambda _record: b"record")
    monkeypatch.setattr(roadmap_revision_publish, "render_accepted_head", lambda _head: b"head")
    generation = PendingGeneration(
        kind="root-enrollment",
        members=(
            GenerationMember(
                roadmap_revision_publish.stored_version_record_path(plans_dir, slug, version_id)
                .relative_to(root)
                .as_posix(),
                None,
                b"record",
            ),
            GenerationMember(
                roadmap_revision_publish.stored_brief_path(plans_dir, slug, version_id)
                .relative_to(root)
                .as_posix(),
                None,
                b"brief",
            ),
            GenerationMember(selector.relative_to(root).as_posix(), None, b"head"),
        ),
    )

    assert not roadmap_revision_publish._is_completed_version_owned_generation(
        generation,
        plans_dir=plans_dir,
        slug=slug,
        accepted=accepted,
    )


def test_version_owned_recovery_refuses_foreign_selector_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "demo"
    plans_dir = tmp_path / "plans"
    version_id = "a" * 64
    root = roadmap_dir(plans_dir, slug)
    selector = roadmap_revision_publish.accepted_head_path(plans_dir, slug)
    accepted = SimpleNamespace(
        record=SimpleNamespace(version_id=version_id, version_kind="candidate", artifact_members=()),
        brief_bytes=b"brief",
        artifact_bytes=(),
    )
    monkeypatch.setattr(roadmap_revision_publish, "_member_state", lambda _path: b"head")
    monkeypatch.setattr(
        roadmap_revision_publish,
        "parse_accepted_head",
        lambda _raw: SimpleNamespace(roadmap_slug=slug, version_id=version_id),
    )
    monkeypatch.setattr(roadmap_revision_publish, "render_accepted_head", lambda _head: b"head")
    generation = PendingGeneration(
        kind="foreign-selector-write",
        members=(
            GenerationMember(selector.relative_to(root).as_posix(), b"old", b"head"),
        ),
    )

    assert not roadmap_revision_publish._is_completed_version_owned_generation(
        generation,
        plans_dir=plans_dir,
        slug=slug,
        accepted=accepted,
    )


def test_exposed_generation_publication_preserves_exact_member_bytes_and_absent_replacements(
    tmp_path: Path,
) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    root.mkdir(parents=True)
    (root / "present.bin").write_bytes(b"old present")
    (root / "remove.bin").write_bytes(b"remove me")
    (root / "unrelated.bin").write_bytes(b"leave me")
    generation = PendingGeneration(
        "test-generation",
        (
            GenerationMember("present.bin", b"old present", b"\x00exact\r\nbytes\xff"),
            GenerationMember("remove.bin", b"remove me", None),
        ),
    )

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        publish_roadmap_generation(
            generation,
            plans_dir=tmp_path,
            slug=slug,
            writer_token=writer_token,
        )

    assert (root / "present.bin").read_bytes() == b"\x00exact\r\nbytes\xff"
    assert not (root / "remove.bin").exists()
    assert (root / "unrelated.bin").read_bytes() == b"leave me"


def test_exposed_generation_publication_recheck_refusal_keeps_members_and_cleans_journal(
    tmp_path: Path,
) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    root.mkdir(parents=True)
    artifact = root / "01-domain.md"
    artifact.write_bytes(b"old artifact")
    baseline = root / ".roadmap-baselines/domain.json"
    generation = PendingGeneration(
        "test-generation",
        (
            GenerationMember("01-domain.md", b"old artifact", b"new artifact"),
            GenerationMember(".roadmap-baselines/domain.json", None, b"new baseline"),
        ),
    )

    def refuse_final_recheck() -> None:
        assert pending_generation_path(root).read_bytes() == render_pending_generation(generation)
        raise RuntimeError("source changed")

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        with pytest.raises(RuntimeError, match="source changed"):
            publish_roadmap_generation(
                generation,
                plans_dir=tmp_path,
                slug=slug,
                writer_token=writer_token,
                before_replace=refuse_final_recheck,
            )

    assert artifact.read_bytes() == b"old artifact"
    assert not baseline.exists()
    assert not pending_generation_path(root).exists()


def test_exposed_generation_publication_failure_leaves_journal_for_guarded_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    root.mkdir(parents=True)
    first = root / "01-domain.md"
    second = root / ".roadmap-baselines/domain.json"
    first.write_bytes(b"old artifact")
    second.parent.mkdir()
    second.write_bytes(b"old baseline")
    generation = PendingGeneration(
        "test-generation",
        (
            GenerationMember("01-domain.md", b"old artifact", b"new artifact"),
            GenerationMember(
                ".roadmap-baselines/domain.json", b"old baseline", b"new baseline"
            ),
        ),
    )
    original_durable_write = roadmap_revision_publish.durable_write_bytes

    def fail_second_member_write(path: Path, value: bytes) -> None:
        if Path(path) == second:
            raise OSError("disk full")
        original_durable_write(path, value)

    monkeypatch.setattr(roadmap_revision_publish, "durable_write_bytes", fail_second_member_write)
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        with pytest.raises(OSError, match="disk full"):
            publish_roadmap_generation(
                generation,
                plans_dir=tmp_path,
                slug=slug,
                writer_token=writer_token,
            )

    assert first.read_bytes() == b"new artifact"
    assert second.read_bytes() == b"old baseline"
    assert pending_generation_path(root).read_bytes() == render_pending_generation(generation)

    monkeypatch.setattr(roadmap_revision_publish, "durable_write_bytes", original_durable_write)
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert first.read_bytes() == b"old artifact"
    assert second.read_bytes() == b"old baseline"
    assert not pending_generation_path(root).exists()


def test_recovery_restores_mixed_members_and_deletes_new_members(tmp_path: Path) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    root.mkdir(parents=True)
    generation = PendingGeneration(
        "test-generation",
        (
            GenerationMember("01-domain.md", b"old artifact", b"new artifact"),
            GenerationMember("02-components.md", b"old components", b"new components"),
            GenerationMember(".roadmap-baselines/domain.json", None, b"new baseline"),
        ),
    )
    journal = pending_generation_path(root)
    journal.write_bytes(render_pending_generation(generation))
    (root / "01-domain.md").write_bytes(b"new artifact")
    (root / "02-components.md").write_bytes(b"old components")
    (root / ".roadmap-baselines").mkdir()
    (root / ".roadmap-baselines/domain.json").write_bytes(b"new baseline")

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert (root / "01-domain.md").read_bytes() == b"old artifact"
    assert (root / "02-components.md").read_bytes() == b"old components"
    assert not (root / ".roadmap-baselines" / "domain.json").exists()
    assert not journal.exists()


def test_recovery_cleans_only_the_journal_for_wholly_old_or_wholly_new_generations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    root.mkdir(parents=True)
    member = root / "01-domain.md"
    generation = PendingGeneration(
        "test-generation",
        (GenerationMember("01-domain.md", b"old artifact", b"new artifact"),),
    )
    journal = pending_generation_path(root)

    def refuse_replacement(*_args: object) -> None:
        pytest.fail("whole generations must not be rewritten during recovery")

    monkeypatch.setattr(roadmap_revision_publish, "_replace_generation_members", refuse_replacement)
    member.write_bytes(b"old artifact")
    journal.write_bytes(render_pending_generation(generation))
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert member.read_bytes() == b"old artifact"
    assert not journal.exists()

    member.write_bytes(b"new artifact")
    journal.write_bytes(render_pending_generation(generation))
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert member.read_bytes() == b"new artifact"
    assert not journal.exists()


def test_recovery_refuses_unknown_member_bytes_without_cleanup(tmp_path: Path) -> None:
    slug = "demo"
    root = roadmap_dir(tmp_path, slug)
    root.mkdir(parents=True)
    generation = PendingGeneration(
        "test-generation",
        (GenerationMember("01-domain.md", b"old artifact", b"new artifact"),),
    )
    journal = pending_generation_path(root)
    journal_bytes = render_pending_generation(generation)
    journal.write_bytes(journal_bytes)
    member = root / "01-domain.md"
    member.write_bytes(b"unrecorded edit")

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        with pytest.raises(roadmap_revision_publish.RoadmapPublicationRecoveryError):
            recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert member.read_bytes() == b"unrecorded edit"
    assert journal.read_bytes() == journal_bytes


# --------------------------------------------------------------------------
# Enrolled decision-settlement generation recognition
#
# These cases build the settlement-shaped generation from low-level version
# primitives directly and deliberately never import
# ``roadmap_decision_settlement_enrolled`` (step 5's own module) — so a bug
# in that module's builder and a bug in this recognizer cannot hide each
# other behind a shared helper.
# --------------------------------------------------------------------------


def _decision_settlement_root(slug: str) -> PreparedRoadmapVersion:
    domain = DomainArtifact(
        entities=(EntityRow("entity-order", "Order", ()),),
        business_rules=(),
        workflows=(),
        decisions=(
            DecisionRow(
                id="decision-1",
                chosen_option="Use the order-centric model.",
                rejected_alternatives=(
                    RejectedAlternative("Use a cart-centric model.", "Rejected for clarity."),
                ),
                rationale="Keeps the domain simple.",
                anchor="entity-order",
                status=DecisionStatus.PENDING,
                source=None,
            ),
        ),
        body="# Domain\n",
        feedback=(
            FeedbackRow(
                "feedback-1",
                FeedbackTarget(FeedbackTargetKind.ROW, "decision-1"),
                "Confirm the order-centric model.",
                FeedbackState.OPEN,
            ),
        ),
    )
    constraints = ConstraintsArtifact(dispositions=(), constraints=(), decisions=(), body="constraints\n")
    components = ComponentsArtifact(
        system_patterns=(), component_patterns=(), components=(), decisions=(), body="components\n"
    )
    plans = PlansArtifact(plans=(), ordering=(), assumptions=(), decisions=(), body="plans\n")
    artifacts = (domain, constraints, components, plans)
    artifact_bytes = tuple(
        stage.render(artifact).encode("utf-8") for stage, artifact in zip(STAGES, artifacts)
    )
    brief_bytes = b"Recorded brief\n"
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=slug,
            brief_digest=hashlib.sha256(brief_bytes).hexdigest(),
            artifact_digests=tuple(hashlib.sha256(b).hexdigest() for b in artifact_bytes),
        ),
        content=RoadmapVersionContent(brief_bytes=brief_bytes, artifact_bytes=artifact_bytes),
    )


def _enroll_decision_settlement_root(plans_dir: Path, slug: str) -> PreparedRoadmapVersion:
    root = _decision_settlement_root(slug)
    with roadmap_writer_guard(plans_dir, slug) as token:
        publish_roadmap_generation(
            build_root_enrollment_generation(root, plans_dir=plans_dir, slug=slug),
            plans_dir=plans_dir,
            slug=slug,
            writer_token=token,
        )
    return root


def _hand_built_settlement_generation(
    plans_dir: Path, slug: str
) -> tuple[PreparedRoadmapVersion, PendingGeneration]:
    """Build the settlement-shaped generation using only version-store
    primitives — step 2's real (already-tested) candidate builder for the
    settled bytes, and hand-assembled members for everything else."""
    accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
    selector = resolve_decision_settlement_selector(
        "domain:decision-1",
        "domain:feedback-1",
        artifact_keys=tuple(stage.artifact_key for stage in STAGES),
    )
    candidate = build_decision_settlement_candidate(
        selector, plans_dir=plans_dir, slug=slug, stages=STAGES
    )
    member_index = accepted.artifact_keys.index(candidate.selector.artifact_key)
    artifact_bytes = tuple(
        candidate.settled_bytes if index == member_index else data
        for index, data in enumerate(accepted.artifact_bytes)
    )
    record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=accepted.record.version_id,
        content_identity="d" * 64,
        review_lineage_identity="e" * 64,
        brief_digest=accepted.record.brief_digest,
        artifact_digests=tuple(hashlib.sha256(data).hexdigest() for data in artifact_bytes),
    )
    prepared = PreparedRoadmapVersion(
        record=record,
        content=RoadmapVersionContent(brief_bytes=accepted.brief_bytes, artifact_bytes=artifact_bytes),
    )
    root_dir = roadmap_dir(plans_dir, slug)
    version_dir = version_directory_path(plans_dir, slug, record.version_id)
    members = [
        GenerationMember((version_dir / member.member_name).relative_to(root_dir).as_posix(), None, member.data)
        for member in stored_version_members(prepared)
    ]
    selector_path = accepted_head_path(plans_dir, slug)
    old_selector_bytes = selector_path.read_bytes()
    new_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION, roadmap_slug=slug, version_id=record.version_id
    )
    members.append(
        GenerationMember(
            selector_path.relative_to(root_dir).as_posix(), old_selector_bytes, render_accepted_head(new_head)
        )
    )
    generation = PendingGeneration(
        kind=roadmap_revision_publish.DECISION_SETTLEMENT_GENERATION_KIND, members=tuple(members)
    )
    return prepared, generation


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _root_generation_as_published(root, *, plans_dir: Path, slug: str) -> PendingGeneration:
    """The root generation exactly as the stage run publishes it: initial ledger ahead of the head."""
    return _with_initial_feedback_ledger(
        build_root_enrollment_generation(root, plans_dir=plans_dir, slug=slug),
        plans_dir=plans_dir,
        slug=slug,
        ledger_state=LedgerState.LEDGER_NATIVE,
    )


def test_completed_root_enrollment_journal_is_dropped_without_touching_members(tmp_path: Path) -> None:
    slug = "root-pin-demo"
    root = _decision_settlement_root(slug)
    generation = _root_generation_as_published(root, plans_dir=tmp_path, slug=slug)
    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)

    root_dir = roadmap_dir(tmp_path, slug)
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    journal_rel = journal.relative_to(root_dir).as_posix()
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=token)

    assert not journal.exists()
    assert _snapshot_tree(root_dir) == {k: v for k, v in before.items() if k != journal_rel}


def test_pending_root_generation_with_no_head_still_rolls_back(tmp_path: Path) -> None:
    """Pins the generic no-head recovery path the first stage run depends on: a crash after
    the root version members landed but before the head selector (written last) must roll
    every member back to its recorded absence, not adopt the half-written version."""
    slug = "no-head-rollback"
    root = _decision_settlement_root(slug)
    generation = build_root_enrollment_generation(root, plans_dir=tmp_path, slug=slug)
    root_dir = roadmap_dir(tmp_path, slug)
    root_dir.mkdir(parents=True)
    head_relative = accepted_head_path(tmp_path, slug).relative_to(root_dir).as_posix()
    assert generation.members[-1].relative_path == head_relative
    for member in generation.members[:-1]:
        assert member.old_bytes is None and member.new_bytes is not None
        target = root_dir / member.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(member.new_bytes)
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))

    with roadmap_writer_guard(tmp_path, slug) as token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=token)

    assert not journal.exists()
    assert load_accepted_version(plans_dir=tmp_path, slug=slug) is None
    assert _snapshot_tree(root_dir) == {}


def test_completed_version_owned_generation_is_still_recognized(tmp_path: Path) -> None:
    """Pins the ``accepted is not None`` recovery path: a root generation whose head and every
    member landed is recognized as completed and only its journal is cleared."""
    slug = "completed-version-owned"
    root = _decision_settlement_root(slug)
    generation = _root_generation_as_published(root, plans_dir=tmp_path, slug=slug)
    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)
    root_dir = roadmap_dir(tmp_path, slug)
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    accepted = load_accepted_version(plans_dir=tmp_path, slug=slug)
    assert accepted is not None
    before = {
        name: data for name, data in _snapshot_tree(root_dir).items()
        if name != journal.relative_to(root_dir).as_posix()
    }

    with roadmap_writer_guard(tmp_path, slug) as token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=token)

    assert not journal.exists()
    assert _snapshot_tree(root_dir) == before
    assert load_accepted_version(plans_dir=tmp_path, slug=slug).record.version_id == accepted.record.version_id


def test_publish_beside_a_leftover_journal_names_the_recovery_command_and_changes_nothing(
    tmp_path: Path,
) -> None:
    """The shared writer guard does not recover; its refusal must name the route that does."""
    slug = "journal-exists"
    root = _decision_settlement_root(slug)
    generation = _root_generation_as_published(root, plans_dir=tmp_path, slug=slug)
    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)
    root_dir = roadmap_dir(tmp_path, slug)
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as token:
        with pytest.raises(RoadmapPublicationRecoveryError) as excinfo:
            publish_roadmap_generation(
                generation, plans_dir=tmp_path, slug=slug, writer_token=token
            )

    message = str(excinfo.value)
    assert f"plan-tool roadmap {slug} --from-existing" in message
    assert str(journal) in message
    assert _snapshot_tree(root_dir) == before


def test_initial_ledger_bytes_are_one_construction_shared_by_publisher_and_recognizer(
    tmp_path: Path,
) -> None:
    """Both sites build the initial ledger through `initial_ledger`, so they cannot drift."""
    slug = "one-constructor"
    root = _decision_settlement_root(slug)
    generation = _root_generation_as_published(root, plans_dir=tmp_path, slug=slug)
    ledger_relative = roadmap_feedback_ledger_path(tmp_path, slug).relative_to(
        roadmap_dir(tmp_path, slug)
    )
    published = next(
        member for member in generation.members if member.relative_path == ledger_relative.as_posix()
    )
    assert published.new_bytes == render_ledger(initial_ledger(slug))
    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)
    assert roadmap_revision_publish._is_completed_version_owned_generation(
        generation,
        plans_dir=tmp_path,
        slug=slug,
        accepted=load_accepted_version(plans_dir=tmp_path, slug=slug),
    )


def test_recognizer_accepts_the_real_root_member_list_including_the_initial_ledger(tmp_path: Path) -> None:
    slug = "real-root-members"
    root = _decision_settlement_root(slug)
    generation = _root_generation_as_published(root, plans_dir=tmp_path, slug=slug)
    ledger_relative = roadmap_feedback_ledger_path(tmp_path, slug).relative_to(roadmap_dir(tmp_path, slug))
    assert generation.members[-2].relative_path == ledger_relative.as_posix()
    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)

    assert roadmap_revision_publish._is_completed_version_owned_generation(
        generation,
        plans_dir=tmp_path,
        slug=slug,
        accepted=load_accepted_version(plans_dir=tmp_path, slug=slug),
    )


@pytest.mark.parametrize("case", ("unknown-extra-member", "ledger-missing", "ledger-with-old-bytes", "ledger-after-selector"))
def test_recognizer_refuses_a_root_member_list_that_is_not_exactly_the_published_one(
    tmp_path: Path, case: str
) -> None:
    slug = "root-members-refused"
    root = _decision_settlement_root(slug)
    generation = _root_generation_as_published(root, plans_dir=tmp_path, slug=slug)
    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)
    members = list(generation.members)
    if case == "unknown-extra-member":
        members.insert(-1, GenerationMember("stray/extra.txt", None, b"x"))
    elif case == "ledger-missing":
        del members[-2]
    elif case == "ledger-with-old-bytes":
        members[-2] = GenerationMember(members[-2].relative_path, b"old", members[-2].new_bytes)
    else:
        members[-2], members[-1] = members[-1], members[-2]

    assert not roadmap_revision_publish._is_completed_version_owned_generation(
        PendingGeneration(kind=generation.kind, members=tuple(members)),
        plans_dir=tmp_path,
        slug=slug,
        accepted=load_accepted_version(plans_dir=tmp_path, slug=slug),
    )


def test_completed_review_seal_promotion_journal_is_dropped_without_touching_members(
    tmp_path: Path,
) -> None:
    slug = "seal-pin-demo"
    root = _enroll_decision_settlement_root(tmp_path, slug)

    child_record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=root.record.version_id,
        content_identity="a" * 64,
        review_lineage_identity="b" * 64,
        brief_digest=root.record.brief_digest,
        artifact_digests=tuple(member.digest for member in root.record.artifact_members),
    )
    prepared_child = PreparedRoadmapVersion(record=child_record, content=root.content)
    root_dir = roadmap_dir(tmp_path, slug)
    version_dir = version_directory_path(tmp_path, slug, child_record.version_id)
    version_dir.mkdir(parents=True)
    for member in stored_version_members(prepared_child):
        (version_dir / member.member_name).write_bytes(member.data)

    selector_path = accepted_head_path(tmp_path, slug)
    old_selector_bytes = selector_path.read_bytes()
    new_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION, roadmap_slug=slug, version_id=child_record.version_id
    )
    generation = PendingGeneration(
        kind="review-seal-promotion",
        members=(
            GenerationMember(
                selector_path.relative_to(root_dir).as_posix(), old_selector_bytes, render_accepted_head(new_head)
            ),
        ),
    )
    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)

    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    journal_rel = journal.relative_to(root_dir).as_posix()
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=token)

    assert not journal.exists()
    assert _snapshot_tree(root_dir) == {k: v for k, v in before.items() if k != journal_rel}


def test_completed_structural_promotion_seed_journal_is_dropped_without_touching_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "structural-seal-pin-demo"
    root = _enroll_decision_settlement_root(tmp_path, slug)
    child_record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=root.record.version_id,
        content_identity="a" * 64,
        review_lineage_identity="b" * 64,
        brief_digest=root.record.brief_digest,
        artifact_digests=tuple(member.digest for member in root.record.artifact_members),
    )
    prepared_child = PreparedRoadmapVersion(record=child_record, content=root.content)
    root_dir = roadmap_dir(tmp_path, slug)
    version_dir = version_directory_path(tmp_path, slug, child_record.version_id)
    version_dir.mkdir(parents=True)
    for stored_member in stored_version_members(prepared_child):
        (version_dir / stored_member.member_name).write_bytes(stored_member.data)
    write_seed_state(seed_state_path(root_dir), _seed_state())

    selector_path = accepted_head_path(tmp_path, slug)
    new_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION, roadmap_slug=slug, version_id=child_record.version_id
    )
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        seed_member = build_enrolled_promotion_seed_state_member(
            plans_dir=tmp_path,
            slug=slug,
            promoted_plans=PlansArtifact(plans=(), ordering=(), assumptions=(), decisions=(), body="plans\n"),
            writer_token=writer_token,
        )
        generation = PendingGeneration(
            kind="review-seal-promotion",
            members=(
                GenerationMember(
                    selector_path.relative_to(root_dir).as_posix(),
                    selector_path.read_bytes(),
                    render_accepted_head(new_head),
                ),
                seed_member,
            ),
        )
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    monkeypatch.setattr(roadmap_revision_publish, "_selected_promotion_is_structural", lambda **_kwargs: True)
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    journal_relative_path = journal.relative_to(root_dir).as_posix()
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert not journal.exists()
    assert _snapshot_tree(root_dir) == {
        path: data for path, data in before.items() if path != journal_relative_path
    }

    # A candidate-evidence file that exists but cannot be loaded is not legacy selector-only state.
    from plan_tool.roadmap_candidate_run import candidate_evidence_path

    journal.write_bytes(render_pending_generation(generation))
    candidate_evidence_path(tmp_path, slug, child_record.version_id).write_bytes(b"invalid evidence")
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        with pytest.raises(RoadmapPublicationRecoveryError, match="non-version-owned"):
            recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)
    assert journal.exists()


def test_structural_promotion_recovery_refuses_missing_seed_invalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "structural-seal-missing-seed"
    root = _enroll_decision_settlement_root(tmp_path, slug)
    child_record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=root.record.version_id,
        content_identity="a" * 64,
        review_lineage_identity="b" * 64,
        brief_digest=root.record.brief_digest,
        artifact_digests=tuple(member.digest for member in root.record.artifact_members),
    )
    prepared_child = PreparedRoadmapVersion(record=child_record, content=root.content)
    root_dir = roadmap_dir(tmp_path, slug)
    version_dir = version_directory_path(tmp_path, slug, child_record.version_id)
    version_dir.mkdir(parents=True)
    for stored_member in stored_version_members(prepared_child):
        (version_dir / stored_member.member_name).write_bytes(stored_member.data)
    selector_path = accepted_head_path(tmp_path, slug)
    generation = PendingGeneration(
        kind="review-seal-promotion",
        members=(
            GenerationMember(
                selector_path.relative_to(root_dir).as_posix(),
                selector_path.read_bytes(),
                render_accepted_head(
                    AcceptedRoadmapHead(
                        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                        roadmap_slug=slug,
                        version_id=child_record.version_id,
                    )
                ),
            ),
        ),
    )
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    monkeypatch.setattr(roadmap_revision_publish, "_selected_promotion_is_structural", lambda **_kwargs: True)
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        with pytest.raises(RoadmapPublicationRecoveryError):
            recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert journal.exists()
    assert _snapshot_tree(root_dir) == before


# --------------------------------------------------------------------------
# Recovery's structural predicate asks the whole unpromoted stack
# --------------------------------------------------------------------------

_PROMOTED_HEAD_ID = "a" * 64
_RECORDED_ROOT_ID = "b" * 64
_ADMISSION_ROOT_ID = "c" * 64


def _stub_promoted_candidate_and_stack(monkeypatch: pytest.MonkeyPatch, *, evidence, stack_is_structural):
    """Stub the two reads the predicate makes on `roadmap_candidate_run`, which it imports at call time.

    An `Exception` instance for `evidence` or `stack_is_structural` is raised by that read instead of
    returned. Returns the keyword sets the load and the derivation were each called with.
    """
    loads: list[dict] = []
    asks: list[dict] = []

    def load(**keywords):
        loads.append(keywords)
        if isinstance(evidence, Exception):
            raise evidence
        return SimpleNamespace(evidence=evidence)

    def derive(**keywords):
        asks.append(keywords)
        if isinstance(stack_is_structural, Exception):
            raise stack_is_structural
        return SimpleNamespace(is_structural=stack_is_structural)

    monkeypatch.setattr(roadmap_candidate_run, "load_stored_candidate_proposal", load)
    monkeypatch.setattr(roadmap_candidate_run, "candidate_stack_route", derive)
    return loads, asks


def test_promotion_structural_predicate_asks_for_the_promoted_id_and_its_recorded_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The head, the active pointer, and the recorded root are three different ids here. The writer asks
    with the promoted candidate's own id and its recorded root, so recovery must too: promotion moves
    the head and releases the pointer, and only the two ids the writer used give the same answer."""
    monkeypatch.setattr(
        roadmap_candidate_run, "load_candidate_admission",
        lambda **_keywords: SimpleNamespace(
            root_version_id=_ADMISSION_ROOT_ID, candidate_version_id=None, active_candidate_version_id=None
        ),
    )
    loads, asks = _stub_promoted_candidate_and_stack(
        monkeypatch, evidence=SimpleNamespace(root_version_id=_RECORDED_ROOT_ID), stack_is_structural=True
    )

    structural = roadmap_revision_publish._selected_promotion_is_structural(
        plans_dir=tmp_path, slug="demo", version_id=_PROMOTED_HEAD_ID
    )

    assert structural is True
    assert loads == [{"plans_dir": tmp_path, "slug": "demo", "candidate_version_id": _PROMOTED_HEAD_ID}]
    assert asks == [{
        "plans_dir": tmp_path, "slug": "demo",
        "tip_version_id": _PROMOTED_HEAD_ID, "root_version_id": _RECORDED_ROOT_ID,
    }]


@pytest.mark.parametrize(
    ("own_route", "stack_is_structural"),
    (
        pytest.param(
            CandidateOperationClassification.PRESENTATION_ONLY, True,
            id="presentation-only-top-over-a-structural-hop",
        ),
        pytest.param(None, False, id="route-less-top-over-a-stack-with-no-structural-hop"),
    ),
)
def test_promotion_structural_predicate_returns_the_stack_answer_not_the_tops_own_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    own_route: CandidateOperationClassification | None, stack_is_structural: bool,
) -> None:
    """The top's own stored route is what the predicate used to return; a presentation-only top over a
    structural hop is the shape that made that wrong, and a route-less top must not read as structural
    for that reason."""
    _stub_promoted_candidate_and_stack(
        monkeypatch,
        evidence=SimpleNamespace(root_version_id=_RECORDED_ROOT_ID, operation_classification=own_route),
        stack_is_structural=stack_is_structural,
    )

    structural = roadmap_revision_publish._selected_promotion_is_structural(
        plans_dir=tmp_path, slug="demo", version_id=_PROMOTED_HEAD_ID
    )

    assert structural is stack_is_structural


@pytest.mark.parametrize("failure", ("derivation-raises", "load-raises-proposal-error", "load-raises-os-error"))
def test_promotion_structural_predicate_reports_an_underivable_stack_as_unknown_never_as_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """`None` is recovery's "cannot tell" channel and `False` would finish a promotion without its seed
    effect, so every unreadable case must be `None`. A failed load never reaches the derivation."""
    evidence: object = SimpleNamespace(root_version_id=_RECORDED_ROOT_ID)
    stack: object = True
    if failure == "derivation-raises":
        stack = roadmap_candidate_run.CandidateProposalError("candidate stack hop is unreadable")
    elif failure == "load-raises-proposal-error":
        evidence = roadmap_candidate_run.CandidateProposalError("candidate is unreadable")
    else:
        evidence = OSError("candidate evidence is unreadable")
    _loads, asks = _stub_promoted_candidate_and_stack(
        monkeypatch, evidence=evidence, stack_is_structural=stack
    )

    structural = roadmap_revision_publish._selected_promotion_is_structural(
        plans_dir=tmp_path, slug="demo", version_id=_PROMOTED_HEAD_ID
    )

    assert structural is None
    assert bool(asks) is (failure == "derivation-raises")


def _selected_child_promotion(tmp_path: Path, slug: str, *, with_seed_member: bool):
    """Publish a review-seal-promotion of a stored child candidate; return (root dir, generation, child)."""
    root = _enroll_decision_settlement_root(tmp_path, slug)
    child_record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=root.record.version_id,
        content_identity="a" * 64,
        review_lineage_identity="b" * 64,
        brief_digest=root.record.brief_digest,
        artifact_digests=tuple(member.digest for member in root.record.artifact_members),
    )
    prepared_child = PreparedRoadmapVersion(record=child_record, content=root.content)
    root_dir = roadmap_dir(tmp_path, slug)
    version_dir = version_directory_path(tmp_path, slug, child_record.version_id)
    version_dir.mkdir(parents=True)
    for stored_member in stored_version_members(prepared_child):
        (version_dir / stored_member.member_name).write_bytes(stored_member.data)
    selector_path = accepted_head_path(tmp_path, slug)
    members = [
        GenerationMember(
            selector_path.relative_to(root_dir).as_posix(),
            selector_path.read_bytes(),
            render_accepted_head(
                AcceptedRoadmapHead(
                    schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                    roadmap_slug=slug,
                    version_id=child_record.version_id,
                )
            ),
        )
    ]
    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        if with_seed_member:
            write_seed_state(seed_state_path(root_dir), _seed_state())
            members.append(
                build_enrolled_promotion_seed_state_member(
                    plans_dir=tmp_path,
                    slug=slug,
                    promoted_plans=PlansArtifact(plans=(), ordering=(), assumptions=(), decisions=(), body="plans\n"),
                    writer_token=writer_token,
                )
            )
        generation = PendingGeneration(kind="review-seal-promotion", members=tuple(members))
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=writer_token)
    return root_dir, generation, child_record


@pytest.mark.parametrize("journal_members", ("selector-only", "selector-and-seed-member"))
def test_structural_promotion_recovery_demands_the_seed_member_through_the_real_predicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, journal_members: str
) -> None:
    """The existing missing-seed test patches the predicate itself, so it cannot show that recovery is
    wired to the stack answer. Here the predicate runs against a stubbed structural stack: the selector-only
    journal is refused and left in place, while the same promotion with its seed member is recognized.
    The stub records no root, so no pointer release is expected and the seed member is the only variable."""
    slug = "structural-stack-seal-pin"
    root_dir, generation, _child = _selected_child_promotion(
        tmp_path, slug, with_seed_member=journal_members == "selector-and-seed-member"
    )
    _stub_promoted_candidate_and_stack(
        monkeypatch, evidence=SimpleNamespace(root_version_id=None), stack_is_structural=True
    )
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        if journal_members == "selector-only":
            with pytest.raises(RoadmapPublicationRecoveryError):
                recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)
        else:
            recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    if journal_members == "selector-only":
        assert journal.exists()
        assert _snapshot_tree(root_dir) == before
    else:
        journal_relative_path = journal.relative_to(root_dir).as_posix()
        assert not journal.exists()
        assert _snapshot_tree(root_dir) == {
            path: data for path, data in before.items() if path != journal_relative_path
        }


def test_recovery_refuses_an_underivable_stack_even_when_the_top_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable lower hop must not let a journal without its seed member through as "not structural".
    The top loads, so only the derivation fails; an evidence file exists, so the legacy selector-only
    allowance declines and the predicate's `None` becomes a refusal that leaves the journal in place."""
    slug = "underivable-stack-seal-pin"
    root_dir, generation, child = _selected_child_promotion(tmp_path, slug, with_seed_member=False)
    roadmap_candidate_run.candidate_evidence_path(tmp_path, slug, child.version_id).write_bytes(b"evidence")
    _stub_promoted_candidate_and_stack(
        monkeypatch,
        evidence=SimpleNamespace(root_version_id=None),
        stack_is_structural=roadmap_candidate_run.CandidateProposalError("candidate stack hop is unreadable"),
    )
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as writer_token:
        with pytest.raises(RoadmapPublicationRecoveryError, match="non-version-owned"):
            recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=writer_token)

    assert journal.exists()
    assert _snapshot_tree(root_dir) == before


def test_completed_decision_settlement_journal_is_dropped_without_touching_members(tmp_path: Path) -> None:
    slug = "settlement-pin-demo"
    _enroll_decision_settlement_root(tmp_path, slug)
    _prepared, generation = _hand_built_settlement_generation(tmp_path, slug)

    with roadmap_writer_guard(tmp_path, slug) as token:
        publish_roadmap_generation(generation, plans_dir=tmp_path, slug=slug, writer_token=token)

    root_dir = roadmap_dir(tmp_path, slug)
    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    journal_rel = journal.relative_to(root_dir).as_posix()
    before = _snapshot_tree(root_dir)

    with roadmap_writer_guard(tmp_path, slug) as token:
        recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=token)

    assert not journal.exists()
    assert _snapshot_tree(root_dir) == {k: v for k, v in before.items() if k != journal_rel}


@pytest.mark.parametrize(
    "written_count", (2, 6), ids=("two-of-six-members", "all-six-members-head-unswapped")
)
def test_decision_settlement_journal_interrupted_before_the_selector_swap_is_refused_and_left_in_place(
    tmp_path: Path, written_count: int
) -> None:
    slug = "interrupted-settlement-demo"
    _enroll_decision_settlement_root(tmp_path, slug)
    _prepared, generation = _hand_built_settlement_generation(tmp_path, slug)
    root_dir = roadmap_dir(tmp_path, slug)

    for member in generation.members[:written_count]:
        path = root_dir / member.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.new_bytes)

    journal = pending_generation_path(root_dir)
    journal.write_bytes(render_pending_generation(generation))
    journal_bytes = journal.read_bytes()
    before = _snapshot_tree(root_dir)
    head_before = accepted_head_path(tmp_path, slug).read_bytes()

    with roadmap_writer_guard(tmp_path, slug) as token:
        with pytest.raises(RoadmapPublicationRecoveryError):
            recover_roadmap_publication(plans_dir=tmp_path, slug=slug, writer_token=token)

    assert journal.read_bytes() == journal_bytes
    assert _snapshot_tree(root_dir) == before
    assert accepted_head_path(tmp_path, slug).read_bytes() == head_before


def test_decision_settlement_recognition_requires_the_old_head_to_name_the_versions_predecessor(
    tmp_path: Path,
) -> None:
    slug = "sibling-settlement-demo"
    _enroll_decision_settlement_root(tmp_path, slug)
    _prepared, generation = _hand_built_settlement_generation(tmp_path, slug)
    root_dir = roadmap_dir(tmp_path, slug)

    for member in generation.members:
        path = root_dir / member.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.new_bytes)

    sibling_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION, roadmap_slug=slug, version_id="f" * 64
    )
    doctored_members = generation.members[:-1] + (
        GenerationMember(
            generation.members[-1].relative_path,
            render_accepted_head(sibling_head),
            generation.members[-1].new_bytes,
        ),
    )
    doctored = PendingGeneration(kind=generation.kind, members=doctored_members)

    assert not roadmap_revision_publish._is_completed_version_owned_generation(
        doctored,
        plans_dir=tmp_path,
        slug=slug,
        accepted=load_accepted_version(plans_dir=tmp_path, slug=slug),
    )


@pytest.mark.parametrize(
    "case",
    (
        "selector-not-last",
        "extra-candidate-evidence-member",
        "brief-member-missing",
        "version-member-has-old-bytes",
        "accepted-version-is-a-root",
    ),
)
def test_decision_settlement_recognition_refuses_a_malformed_member_list(tmp_path: Path, case: str) -> None:
    slug = "malformed-settlement-demo"
    _enroll_decision_settlement_root(tmp_path, slug)
    _prepared, generation = _hand_built_settlement_generation(tmp_path, slug)
    root_dir = roadmap_dir(tmp_path, slug)

    if case == "accepted-version-is-a-root":
        # The selector is never swapped, so the accepted version stays the
        # root and recognition must refuse on version_kind alone.
        accepted = load_accepted_version(plans_dir=tmp_path, slug=slug)
        assert not roadmap_revision_publish._is_completed_version_owned_generation(
            generation, plans_dir=tmp_path, slug=slug, accepted=accepted
        )
        return

    members = list(generation.members)
    if case == "selector-not-last":
        members = [members[-1], *members[:-1]]
    elif case == "extra-candidate-evidence-member":
        evidence_path = (
            version_directory_path(tmp_path, slug, _prepared.record.version_id) / "candidate-evidence.json"
        )
        members.append(GenerationMember(evidence_path.relative_to(root_dir).as_posix(), None, b"{}"))
    elif case == "brief-member-missing":
        members = [member for member in members if not member.relative_path.endswith("brief.md")]
    elif case == "version-member-has-old-bytes":
        members[0] = GenerationMember(members[0].relative_path, b"old", members[0].new_bytes)
    else:
        raise AssertionError(f"unhandled case {case!r}")
    doctored = PendingGeneration(kind=generation.kind, members=tuple(members))

    for member in generation.members:
        path = root_dir / member.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.new_bytes)

    assert not roadmap_revision_publish._is_completed_version_owned_generation(
        doctored,
        plans_dir=tmp_path,
        slug=slug,
        accepted=load_accepted_version(plans_dir=tmp_path, slug=slug),
    )
