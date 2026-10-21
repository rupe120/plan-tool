"""Tests for plan_tool.drift_detection.

Pure in-memory + tmp_path file-system tests. No claude shell-out -- the
module is a small acquire/release primitive plus mtime drift
detection. Callers (cli.cmd_completeness, _iterate_reconcile_loop,
create_plan, generate_detail) own their own integration tests.
"""

from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pytest

from plan_tool import style
from plan_tool.drift_detection import (
    IterationLock,
    acquire_lock,
    emit_drift_halt_warning,
    emit_drift_warning,
    reconcile_drift_hint,
    release_lock,
)


# ---------- acquire_lock ----------

def test_acquire_records_metadata_on_lock_object(tmp_path: Path) -> None:
    """slug/command/pid/started_at live on the returned ``IterationLock``,
    not on disk."""
    lock = acquire_lock(
        tmp_path,
        slug="demo",
        command="completeness",
        watched_paths=[],
    )
    assert lock.slug == "demo"
    assert lock.command == "completeness"
    assert lock.pid == os.getpid()
    assert isinstance(lock.started_at, (int, float))


# ---------- compute_content_hash (#31 helper) ----------

def test_compute_content_hash_returns_sha256_hex(tmp_path: Path) -> None:
    """Round-trip: SHA-256 of known content matches the standard
    hashlib digest. Pin the algorithm so a future swap to a different
    hash (faster, e.g. blake2) becomes a deliberate change reviewed
    here rather than a silent behavior shift."""
    import hashlib
    from plan_tool.drift_detection import compute_content_hash

    f = tmp_path / "known.bin"
    payload = b"hello plan-tool 31"
    f.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert compute_content_hash(f) == expected


def test_compute_content_hash_empty_file_has_empty_sha256(
    tmp_path: Path,
) -> None:
    """The canonical SHA-256 of an empty input is a well-known
    constant. Edge case worth pinning: a zero-byte step.files entry
    (rare but legal) shouldn't raise."""
    from plan_tool.drift_detection import compute_content_hash

    f = tmp_path / "empty.txt"
    f.write_bytes(b"")
    assert (
        compute_content_hash(f)
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_compute_content_hash_returns_none_on_missing_file(
    tmp_path: Path,
) -> None:
    """Missing files yield None rather than raising -- the calling
    code (acquire_lock, check_drift) treats None as "skip this
    path silently," matching the legacy mtime-snapshot behavior."""
    from plan_tool.drift_detection import compute_content_hash

    assert compute_content_hash(tmp_path / "does_not_exist.py") is None


def test_compute_content_hash_returns_none_on_directory(
    tmp_path: Path,
) -> None:
    """Passing a directory (caller bug or step.files entry that
    happens to resolve to a dir) yields None rather than raising
    -- ``open("rb")`` raises ``IsADirectoryError`` which is an
    ``OSError`` subclass."""
    from plan_tool.drift_detection import compute_content_hash

    assert compute_content_hash(tmp_path) is None


def test_compute_content_hash_handles_multi_chunk_file(
    tmp_path: Path,
) -> None:
    """Files larger than the 64 KB chunk size are read in chunks
    but produce the same digest as a single-shot hash. Pin the
    chunked-read correctness."""
    import hashlib
    from plan_tool.drift_detection import compute_content_hash

    # 200 KB ensures multiple 64 KB chunks. Use a non-uniform
    # payload so a bug that hashes only the first chunk would
    # produce a wrong digest.
    payload = (b"abcdefgh" * 8 * 1024 + b"_tail_block") * 3
    assert len(payload) > 64 * 1024
    f = tmp_path / "big.bin"
    f.write_bytes(payload)
    assert compute_content_hash(f) == hashlib.sha256(payload).hexdigest()


def test_acquire_snapshots_watched_file_content_hashes(
    tmp_path: Path,
) -> None:
    """Existing watched files have their content hash captured at
    acquire."""
    import hashlib
    f = tmp_path / "watched.py"
    f.write_text("x", encoding="utf-8")
    expected_hash = hashlib.sha256(b"x").hexdigest()
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    assert str(f) in lock.content_hash_snapshot
    assert lock.content_hash_snapshot[str(f)] == expected_hash


def test_acquire_skips_missing_watched_paths(tmp_path: Path) -> None:
    """Missing watched paths (e.g. step.files declaring not-yet-created
    files) are silently skipped, not an error."""
    f = tmp_path / "does_not_exist.py"
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    assert str(f) not in lock.content_hash_snapshot


# ---------- release_lock ----------

def test_release_returns_empty_when_no_drift(tmp_path: Path) -> None:
    f = tmp_path / "watched.py"
    f.write_text("x", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    assert release_lock(lock) == []


def test_release_flags_files_whose_content_changed(tmp_path: Path) -> None:
    """When a watched file's CONTENT changed during the hold, release
    flags it as drift. Caller surfaces this as the live-edit warning."""
    f = tmp_path / "watched.py"
    f.write_text("before", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    f.write_text("after", encoding="utf-8")
    drifted = release_lock(lock)
    assert drifted == [f]


def test_release_does_not_flag_mtime_advance_alone(
    tmp_path: Path,
) -> None:
    """#31: mtime advance with UNCHANGED content (some IDEs do this on
    every save; ``git checkout`` of unchanged content does this) must
    NOT trigger drift. The legacy mtime check would false-positive
    here; the content-hash check ignores it.

    This is the load-bearing test for the #31 false-positive
    elimination -- without it a regression to mtime-based comparison
    would silently restore the noise."""
    f = tmp_path / "watched.py"
    f.write_text("unchanged content", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    # Bump the mtime without touching the bytes.
    new_mtime = f.stat().st_mtime + 5
    os.utime(f, (new_mtime, new_mtime))
    # Confirm the mtime really did advance -- otherwise the test
    # passes vacuously.
    assert f.stat().st_mtime > lock.started_at - 1
    drifted = release_lock(lock)
    assert drifted == []


def test_release_ignores_files_deleted_mid_hold(tmp_path: Path) -> None:
    """A watched file that disappears during the hold is not flagged
    (the file no longer exists -- can't be "live-edited drift")."""
    f = tmp_path / "watched.py"
    f.write_text("x", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    f.unlink()
    drifted = release_lock(lock)
    assert drifted == []


# ---------- reconcile_drift_hint (step 4) ----------

def test_reconcile_drift_hint_plan_side() -> None:
    """The plan-authoring loops drift on plan/detail text -> the hint
    names ``detail --reconcile`` only, never ``run --reconcile``."""
    for loop_name in ("completeness", "detail (step 1)", "create"):
        hint = reconcile_drift_hint(loop_name)
        assert "plan-tool detail <name> --reconcile" in hint
        assert "plan-tool run <name> --reconcile" not in hint


def test_reconcile_drift_hint_reconcile_loop_is_plan_side() -> None:
    """The ``reconcile`` loop is the ``detail --reconcile`` audit itself,
    not a code-side loop -- its drift recovery is ``detail --reconcile``."""
    hint = reconcile_drift_hint("reconcile")
    assert "plan-tool detail <name> --reconcile" in hint
    assert "plan-tool run <name> --reconcile" not in hint


def test_reconcile_drift_hint_neutral_when_none() -> None:
    """``loop_name is None`` is the neutral halt-path default: name both
    commands as an operator menu."""
    hint = reconcile_drift_hint(None)
    assert "plan-tool detail <name> --reconcile" in hint
    assert "plan-tool run <name> --reconcile" in hint


# ---------- emit_drift_warning ----------

def test_emit_drift_warning_no_op_on_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    emit_drift_warning([], repo_root=tmp_path, loop_name="reconcile")
    assert capsys.readouterr().err == ""


def test_emit_drift_warning_renders_relative_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = [tmp_path / "src" / "foo.py", tmp_path / "src" / "bar.py"]
    emit_drift_warning(paths, repo_root=tmp_path, loop_name="reconcile")
    err = capsys.readouterr().err
    assert "WARNING: 2 watched file(s)" in err
    assert "reconcile iteration loop" in err
    assert "src/foo.py" in err  # rendered relative to repo_root
    assert "src/bar.py" in err
    # The reconcile hint is now the last line, so assert the truncation
    # marker is absent across the whole output instead of on the last line.
    assert "... and" not in err  # no "... and N more" line


def test_build_file_to_step_map_resolves_step_files(
    tmp_path: Path,
) -> None:
    """Each entry in every ``step.files`` resolves to the owning
    step's ``(id, title)``. Annotations like ``(new)`` are stripped
    before resolving, matching the in-scope-path convention."""
    from plan_tool.scope_guard import build_file_to_step_map
    from plan_tool.schema import Plan, Step

    plan = Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(
                id=1, title="alpha",
                files=["src/alpha.py", "src/alpha_helper.py (new)"],
            ),
            Step(id=2, title="beta", files=["src/beta.py"]),
        ],
    )
    mapping = build_file_to_step_map(plan, tmp_path)
    assert mapping[(tmp_path / "src/alpha.py").resolve()] == (1, "alpha")
    assert (
        mapping[(tmp_path / "src/alpha_helper.py").resolve()]
        == (1, "alpha")
    )
    assert mapping[(tmp_path / "src/beta.py").resolve()] == (2, "beta")


def test_build_file_to_step_map_first_step_wins_on_duplicates(
    tmp_path: Path,
) -> None:
    """When two steps declare the same file, the earlier step wins.
    Unusual but valid input -- the behavior is deterministic so
    drift attribution doesn't flap based on dict-iteration order."""
    from plan_tool.scope_guard import build_file_to_step_map
    from plan_tool.schema import Plan, Step

    plan = Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(id=1, title="alpha", files=["shared.py"]),
            Step(id=2, title="beta", files=["shared.py"]),
        ],
    )
    mapping = build_file_to_step_map(plan, tmp_path)
    assert mapping[(tmp_path / "shared.py").resolve()] == (1, "alpha")


def test_drift_check_excludes_plan_and_detail_files(tmp_path: Path) -> None:
    """The iteration loop's apply_finding step legitimately rewrites
    the plan + detail files every round. Drift detection must NOT
    flag those files -- otherwise every successful iteration emits a
    noisy false-positive warning naming the loop's own edits.

    Pin: ``compute_drift_watched_paths`` (used at every acquire_lock
    call site) excludes the plan markdown and detail files from the
    watched set, so apply_finding's edits to those don't fire the
    drift warning.
    """
    from plan_tool.scope_guard import (
        compute_drift_watched_paths,
        compute_in_scope_paths,
    )
    from plan_tool.schema import Plan, Step

    # Build a plan with one declared file + one detail file.
    plan = Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(
                id=1,
                title="Stub",
                files=["src/foo.py"],
                detail="docs/details/step-1.md",
            ),
        ],
    )
    plan_path = tmp_path / "docs" / "plans" / "demo.md"

    full = compute_in_scope_paths(plan, plan_path, tmp_path)
    drift = compute_drift_watched_paths(plan, plan_path, tmp_path)

    # Sanity: the full in-scope set includes plan + detail + step files.
    assert plan_path.resolve() in full
    assert (tmp_path / "docs/details/step-1.md").resolve() in full
    assert (tmp_path / "src/foo.py").resolve() in full

    # The drift-watch subset excludes plan + detail; only step.files
    # remain. apply_finding's edits to the plan/detail files won't
    # trip a false-positive warning at iteration release.
    assert plan_path.resolve() not in drift
    assert (tmp_path / "docs/details/step-1.md").resolve() not in drift
    assert (tmp_path / "src/foo.py").resolve() in drift


def test_emit_drift_warning_truncates_long_lists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = [tmp_path / f"f{i}.py" for i in range(15)]
    emit_drift_warning(
        paths, repo_root=tmp_path, loop_name="create", max_listed=5,
    )
    err = capsys.readouterr().err
    assert "15 watched file(s)" in err
    # First 5 listed inline, remainder summarized.
    assert "and 10 more" in err


def test_emit_drift_warning_appends_detail_reconcile_hint_for_reconcile_loop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ``reconcile`` loop is plan-side -> the trailer points at
    ``detail --reconcile``, never ``run --reconcile``."""
    emit_drift_warning(
        [tmp_path / "foo.py"], repo_root=tmp_path, loop_name="reconcile",
    )
    err = capsys.readouterr().err
    assert "plan-tool detail <name> --reconcile" in err
    assert "plan-tool run <name> --reconcile" not in err


def test_emit_drift_warning_appends_detail_reconcile_hint_for_authoring_loop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Plan-authoring loops recover via ``detail --reconcile``."""
    for loop_name in ("completeness", "create"):
        emit_drift_warning(
            [tmp_path / "foo.py"], repo_root=tmp_path, loop_name=loop_name,
        )
        err = capsys.readouterr().err
        assert "plan-tool detail <name> --reconcile" in err


# ---------- emit_drift_halt_warning (task #30 / #33) ----------

def test_emit_drift_halt_warning_no_op_on_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Empty drift list → no output (mirrors emit_drift_warning)."""
    emit_drift_halt_warning(
        [], phase="before", finding_id="x", repo_root=tmp_path
    )
    assert capsys.readouterr().err == ""


def test_emit_drift_halt_warning_before_phase_says_no_tokens_spent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``phase=before`` wording tells the operator no tokens were spent."""
    f = tmp_path / "watched.py"
    emit_drift_halt_warning(
        [f], phase="before", finding_id="finding-A",
        repo_root=tmp_path,
    )
    err = capsys.readouterr().err
    assert "BEFORE applying finding finding-A" in err
    assert "without spending claude tokens" in err
    assert "No edits made this round" in err
    assert "watched.py" in err
    assert "--allow-drift" not in err
    assert "--reconcile" in err


def test_emit_drift_warning_with_file_to_step_includes_attribution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``file_to_step`` enriches each drifted-path line with the
    owning step's id and title -- operators don't need to consult the
    plan to know which step a flagged file belongs to."""
    foo = tmp_path / "src" / "foo.py"
    foo.parent.mkdir(parents=True, exist_ok=True)
    foo.write_text("x = 1\n", encoding="utf-8")
    file_to_step = {foo.resolve(): (1, "implement core logic")}

    emit_drift_warning(
        [foo], repo_root=tmp_path, loop_name="completeness",
        file_to_step=file_to_step,
    )
    err = capsys.readouterr().err
    assert "src/foo.py (step 1: implement core logic)" in err


def test_emit_drift_warning_without_file_to_step_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Legacy behavior: passing ``file_to_step=None`` (or omitting it)
    emits bare relative paths -- back-compat with callers that don't
    have a plan handy."""
    foo = tmp_path / "src" / "foo.py"
    foo.parent.mkdir(parents=True, exist_ok=True)
    foo.write_text("x = 1\n", encoding="utf-8")

    emit_drift_warning(
        [foo], repo_root=tmp_path, loop_name="completeness",
    )
    err = capsys.readouterr().err
    assert "src/foo.py" in err
    assert "(step" not in err


def test_emit_drift_halt_warning_with_file_to_step_includes_attribution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The halt-warning variant also honors ``file_to_step``."""
    foo = tmp_path / "src" / "foo.py"
    foo.parent.mkdir(parents=True, exist_ok=True)
    foo.write_text("x = 1\n", encoding="utf-8")
    file_to_step = {foo.resolve(): (2, "wire up renderer")}

    emit_drift_halt_warning(
        [foo],
        phase="during",
        finding_id="finding-Z",
        repo_root=tmp_path,
        file_to_step=file_to_step,
    )
    err = capsys.readouterr().err
    assert "src/foo.py (step 2: wire up renderer)" in err


def test_emit_drift_halt_warning_falls_back_to_bare_path_when_unmapped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A drifted file that isn't in the file_to_step map (e.g. an
    edit that scope_guard surfaced from outside any step.files) gets
    a bare path, not a confusing ``(step ?: ?)``."""
    foo = tmp_path / "untracked.py"
    foo.write_text("x = 1\n", encoding="utf-8")
    file_to_step = {tmp_path / "other.py": (1, "other step")}

    emit_drift_halt_warning(
        [foo],
        phase="before",
        finding_id="finding-A",
        repo_root=tmp_path,
        file_to_step=file_to_step,
    )
    err = capsys.readouterr().err
    assert "untracked.py" in err
    # No spurious step annotation since untracked.py isn't in the map.
    assert "untracked.py (step" not in err


def test_emit_drift_halt_warning_during_phase_says_edits_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``phase=during`` wording tells the operator the apply's edits
    were KEPT (token preservation > strict spec integrity)."""
    f = tmp_path / "watched.py"
    emit_drift_halt_warning(
        [f], phase="during", finding_id="finding-B",
        repo_root=tmp_path,
    )
    err = capsys.readouterr().err
    assert "DURING apply of finding finding-B" in err
    assert "KEPT" in err
    assert "git diff" in err
    assert "Halting subsequent applies" in err


def test_emit_drift_halt_warning_no_longer_mentions_allow_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The halt warning points operators at the re-reconcile fix, not at
    the ``--allow-drift`` opt-out -- for any phase."""
    for phase in ("before", "during"):
        emit_drift_halt_warning(
            [tmp_path / "watched.py"], phase=phase, finding_id="F",
            repo_root=tmp_path,
        )
        err = capsys.readouterr().err
        assert "--allow-drift" not in err


def test_emit_drift_halt_warning_neutral_hint_when_loop_name_omitted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With ``loop_name`` omitted the halt path emits the neutral menu
    naming both ``detail --reconcile`` and ``run --reconcile``."""
    emit_drift_halt_warning(
        [tmp_path / "watched.py"], phase="before", finding_id="F",
        repo_root=tmp_path,
    )
    err = capsys.readouterr().err
    assert "plan-tool detail <name> --reconcile" in err
    assert "plan-tool run <name> --reconcile" in err


def test_emit_drift_halt_warning_reconcile_loop_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``loop_name="reconcile"`` -> the plan-side ``detail --reconcile``
    pointer, never ``run --reconcile``."""
    emit_drift_halt_warning(
        [tmp_path / "watched.py"], phase="during", finding_id="F",
        repo_root=tmp_path, loop_name="reconcile",
    )
    err = capsys.readouterr().err
    assert "plan-tool detail <name> --reconcile" in err
    assert "plan-tool run <name> --reconcile" not in err


def test_emit_drift_halt_warning_plan_side_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A named plan-authoring loop yields the ``detail --reconcile``
    pointer."""
    emit_drift_halt_warning(
        [tmp_path / "watched.py"], phase="before", finding_id="F",
        repo_root=tmp_path, loop_name="completeness",
    )
    err = capsys.readouterr().err
    assert "plan-tool detail <name> --reconcile" in err


# ---------- refresh_snapshot (Bug 1 from session-4 review) ----------


def test_refresh_snapshot_picks_up_current_content_hashes(
    tmp_path: Path,
) -> None:
    """``refresh_snapshot`` rehashes the watched files against their
    CURRENT on-disk content. After refresh, ``check_drift`` compares
    against the new baseline rather than the original acquire-time
    state -- this is what makes the change-collision merge-continue
    path workable (without it, the next pre-apply drift check would
    halt on the same drift that triggered the collision).

    Pins the fix for the load-bearing bug surfaced in the session-4
    review: ``content_hash_snapshot`` was previously only assigned
    at acquire time, so merge-continue dead-ended on the next
    iteration."""
    from plan_tool.drift_detection import (
        check_drift,
        refresh_snapshot,
    )

    f = tmp_path / "watched.py"
    f.write_text("v1\n", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )

    # Drift the file -- this is what the user did before applying.
    f.write_text("v2-user-edit\n", encoding="utf-8")
    assert check_drift(lock) == [f]

    # User merged. Refresh the snapshot to the merged state.
    refresh_snapshot(lock)

    # Now check_drift sees no drift (the v2 content is the new
    # baseline).
    assert check_drift(lock) == []

    # And a subsequent edit DOES re-trigger drift, proving the
    # snapshot is live (not frozen at refresh time).
    f.write_text("v3\n", encoding="utf-8")
    assert check_drift(lock) == [f]


def test_refresh_snapshot_drops_files_missing_at_refresh_time(
    tmp_path: Path,
) -> None:
    """A file that existed at acquire time but is missing at refresh
    time is dropped from the snapshot -- subsequent check_drift no
    longer flags it. Mirrors acquire-time skip-None semantics."""
    from plan_tool.drift_detection import (
        check_drift,
        refresh_snapshot,
    )

    f = tmp_path / "watched.py"
    f.write_text("v1\n", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    assert str(f) in lock.content_hash_snapshot

    f.unlink()
    refresh_snapshot(lock)

    assert str(f) not in lock.content_hash_snapshot
    # And check_drift is silent on the deleted file.
    assert check_drift(lock) == []


# ---------- release_lock idempotency ----------


def test_release_lock_idempotent_second_call_returns_empty(
    tmp_path: Path,
) -> None:
    """A second release_lock returns [] even when the first detected
    drift, so a SIGINT handler that fires after explicit cleanup
    doesn't double-emit the live-edit drift warning."""
    f = tmp_path / "watched.py"
    f.write_text("before", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    f.write_text("after", encoding="utf-8")

    first = release_lock(lock)
    assert first == [f]
    assert lock.released is True

    # Second call: would re-flag the same drift naively, but the
    # ``released`` sentinel short-circuits.
    second = release_lock(lock)
    assert second == []


def test_release_lock_idempotent_against_drift_after_release(
    tmp_path: Path,
) -> None:
    """After release, a subsequent file edit shouldn't cause the
    second release to report drift -- the lock is conceptually gone."""
    f = tmp_path / "watched.py"
    f.write_text("before", encoding="utf-8")
    lock = acquire_lock(
        tmp_path, slug="x", command="run", watched_paths=[f],
    )
    release_lock(lock)

    # File edit AFTER release shouldn't be flagged.
    f.write_text("post-release edit", encoding="utf-8")
    assert release_lock(lock) == []


def test_iteration_session_leaves_sigint_handler_untouched(
    tmp_path: Path,
) -> None:
    """An enabled session yields a non-``None`` lock, writes no lockfile,
    and leaves the process SIGINT handler unchanged across enter, body,
    and exit -- the session installs nothing. A ``RuntimeError`` escaping
    the body still propagates, and the drift warning still fires in the
    ``finally``.
    """
    import signal as signal_module
    from plan_tool.drift_detection import iteration_session

    outer = signal_module.signal(
        signal_module.SIGINT, signal_module.default_int_handler,
    )
    try:
        f = tmp_path / "watched.py"
        f.write_text("phase1", encoding="utf-8")

        with pytest.raises(RuntimeError, match="boom"):
            with iteration_session(
                tmp_path,
                enabled=True,
                slug="iter1",
                command="completeness",
                loop_name="completeness",
                watched_paths=[f],
            ) as lock:
                assert lock is not None
                # The session installs no SIGINT handler.
                assert (
                    signal_module.getsignal(signal_module.SIGINT)
                    is signal_module.default_int_handler
                )
                raise RuntimeError("boom")

        # The SIGINT handler is the outer one -- the session never
        # touched it.
        assert (
            signal_module.getsignal(signal_module.SIGINT)
            is signal_module.default_int_handler
        )
    finally:
        signal_module.signal(signal_module.SIGINT, outer)


def test_iteration_session_disabled_yields_none_and_takes_no_lock(
    tmp_path: Path,
) -> None:
    """``enabled=False`` is the lock-free path: yields ``None``, writes
    no lockfile, and leaves the SIGINT handler untouched."""
    import signal as signal_module
    from plan_tool.drift_detection import iteration_session

    before = signal_module.getsignal(signal_module.SIGINT)
    with iteration_session(
        tmp_path,
        enabled=False,
        slug="p",
        command="create",
        loop_name="create",
        watched_paths=[],
    ) as lock:
        assert lock is None
        assert signal_module.getsignal(signal_module.SIGINT) is before


class TestIterationLockStyleOutput:
    """drift_detection.py's ``plan-tool:`` diagnostics route through
    ``style.tool()``. Plain mode stays byte-identical (including the
    uppercase ``WARNING:`` sub-tag); under ``PLAN_TOOL_FORCE_COLOR`` only
    the ``plan-tool:`` tag carries ANSI. The ``Drifted files:`` label and
    ``  - `` bullets stay raw.
    """

    def test_drift_warning_head_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        emit_drift_warning(
            [Path("a.py")],
            repo_root=tmp_path,
            loop_name="reconcile",
            file=buf,
        )
        first_line = buf.getvalue().splitlines()[0] + "\n"
        assert first_line == (
            "plan-tool: WARNING: 1 watched file(s) "
            "changed during the reconcile iteration loop. Findings "
            "against these files may reflect in-flight edits rather "
            "than pre-existing drift -- review the loop's output "
            "skeptically before treating it as canonical:\n"
        )

    def test_drift_warning_bullets_have_no_prefix(
        self, tmp_path: Path
    ) -> None:
        buf = io.StringIO()
        emit_drift_warning(
            [Path("a.py")],
            repo_root=tmp_path,
            loop_name="reconcile",
            file=buf,
        )
        bullet = buf.getvalue().splitlines()[1]
        assert bullet == "  - a.py"
        assert "plan-tool:" not in bullet

    def test_drift_halt_before_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        emit_drift_halt_warning(
            [Path("a.py")],
            phase="before",
            finding_id="F1",
            repo_root=tmp_path,
            file=buf,
        )
        first_line = buf.getvalue().splitlines()[0] + "\n"
        assert first_line == (
            "plan-tool: WARNING: drift detected on 1 "
            "watched file(s) BEFORE applying finding F1. "
            "Halting iteration loop without spending claude tokens "
            "on a likely-spurious apply. No edits made this round.\n"
        )

    def test_drift_halt_during_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        emit_drift_halt_warning(
            [Path("a.py")],
            phase="during",
            finding_id="F1",
            repo_root=tmp_path,
            file=buf,
        )
        first_line = buf.getvalue().splitlines()[0] + "\n"
        assert first_line == (
            "plan-tool: WARNING: drift detected on 1 "
            "watched file(s) DURING apply of finding F1. "
            "That apply's edits to plan/detail were KEPT (claude "
            "tokens already spent; the edits may still be useful) "
            "-- review them via `git diff` before relying on the "
            "output. Halting subsequent applies to prevent "
            "compounding the issue.\n"
        )

    def test_drift_halt_trailer_and_label(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        emit_drift_halt_warning(
            [Path("a.py")],
            phase="during",
            finding_id="F1",
            repo_root=tmp_path,
            file=buf,
        )
        out = buf.getvalue()
        # The label is raw (no prefix).
        assert "\nDrifted files:\n" in out
        # The trailer is a prefixed head: with loop_name omitted the
        # neutral both-commands re-reconcile hint fires.
        assert (
            "plan-tool: Re-reconcile against current code before relying "
            "on the output: `plan-tool detail <name> --reconcile` for "
            "plan-side drift, `plan-tool run <name> --reconcile` for "
            "code-side drift.\n"
        ) in out

    def test_drift_warning_head_color_prefix_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        buf = io.StringIO()
        emit_drift_warning(
            [Path("a.py")],
            repo_root=tmp_path,
            loop_name="reconcile",
            file=buf,
        )
        out = buf.getvalue()
        assert out.startswith(style.DIM + "plan-tool:" + style.RESET + " ")
        # The uppercase WARNING: sub-tag in the body carries no escapes.
        assert (
            style.DIM + "plan-tool:" + style.RESET + " WARNING: 1 watched"
        ) in out


# ---------------------------------------------------------------------------
# Seam invariant: every convergence-loop entry point goes through
# ``iteration_session``, never an open-coded acquire/drift-check.
# ---------------------------------------------------------------------------


class TestIterationSessionIsTheOnlyEntryShape:
    """The four convergence loops must acquire the drift session only via
    ``with iteration_session(...)``.

    ``iteration_session``'s ``finally`` is what runs the end-of-hold drift
    check on *any* exit — including a non-``KeyboardInterrupt`` exception
    escaping the loop body. Open-coding the acquire/drift-check without a
    ``try/finally`` would skip that check on a crashed loop (BUG_BACKLOG:
    "Iteration entry points leak on non-KI exception"; LESSONS_LEARNED
    Lesson 17). Routing through the context manager closes that gap; this
    test fails if a regression stops an entry point from going through
    ``iteration_session``.
    """

    _ENTRY_POINT_MODULES = (
        "plan_tool/create.py",
        "plan_tool/detail.py",
        "plan_tool/cli/completeness_phases.py",
        "plan_tool/cli/reconcile.py",
    )

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def test_entry_points_use_iteration_session(self) -> None:
        root = self._repo_root()
        for rel in self._ENTRY_POINT_MODULES:
            src = (root / rel).read_text(encoding="utf-8")
            assert "iteration_session(" in src, (
                f"{rel} no longer goes through iteration_session — the "
                f"drift-session lifecycle may have been re-open-coded"
            )
