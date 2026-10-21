"""Tests for plan_tool.change_collision.

Pure tmp_path file-system tests + injected input/isatty for the
interactive prompt. No claude shell-out -- this module operates on
pre_snapshot dicts produced by apply_finding, not on claude output.
The iteration entry points' wiring (cmd_completeness, create_plan,
generate_detail) is covered by sibling integration tests in
``test_cli.py`` / ``test_create.py`` / ``test_detail.py``.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from plan_tool import style
from plan_tool.change_collision import (
    CollisionSidecar,
    allocate_sidecar_path,
    collision_sidecar_path,
    emit_collision_summary,
    handle_drift_collision,
    prompt_user_to_merge,
    save_collision_sidecars,
)


# ---------- collision_sidecar_path ----------


def test_collision_sidecar_path_inserts_marker_before_extension(
    tmp_path: Path,
) -> None:
    """Standard case: file with extension gets the sidecar marker
    inserted before the extension."""
    original = tmp_path / "plans" / "2-foo-bar.md"
    sidecar = collision_sidecar_path(original)
    assert sidecar == tmp_path / "plans" / "2-foo-bar-change-collision.md"


def test_collision_sidecar_path_handles_no_extension(
    tmp_path: Path,
) -> None:
    """Files without an extension (Makefile, LICENSE, etc.) get the
    marker appended with no extension on the sidecar either."""
    original = tmp_path / "Makefile"
    sidecar = collision_sidecar_path(original)
    assert sidecar == tmp_path / "Makefile-change-collision"


def test_collision_sidecar_path_handles_double_extension(
    tmp_path: Path,
) -> None:
    """For files like ``foo.tar.gz``, ``Path.suffix`` returns ``.gz``
    and ``Path.stem`` returns ``foo.tar``. The sidecar lands next to
    the original with the marker before only the final extension --
    matches what most users expect from `<name>-change-collision.<ext>`."""
    original = tmp_path / "archive.tar.gz"
    sidecar = collision_sidecar_path(original)
    assert sidecar == tmp_path / "archive.tar-change-collision.gz"


def test_collision_sidecar_path_lives_next_to_original(
    tmp_path: Path,
) -> None:
    """The sidecar shares the original's parent directory regardless
    of how deeply nested the original is."""
    original = tmp_path / "a" / "b" / "c" / "deep.py"
    sidecar = collision_sidecar_path(original)
    assert sidecar.parent == original.parent
    assert sidecar.name == "deep-change-collision.py"


# ---------- save_collision_sidecars ----------


def test_save_sidecar_writes_post_apply_content_and_restores_original(
    tmp_path: Path,
) -> None:
    """The happy path: pre_snapshot has the pre-apply content, the
    file on disk has claude's post-apply content. save_collision_-
    sidecars writes the post-apply content to the sidecar and
    restores the original to pre-apply state."""
    plan = tmp_path / "plan.md"
    plan.write_text("CLAUDE'S NEW VERSION\n", encoding="utf-8")
    pre_snapshot = {plan: "ORIGINAL VERSION\n"}

    sidecars = save_collision_sidecars(pre_snapshot)

    # Original is restored.
    assert plan.read_text(encoding="utf-8") == "ORIGINAL VERSION\n"
    # Sidecar carries claude's edits.
    sidecar_path = collision_sidecar_path(plan)
    assert sidecar_path.read_text(encoding="utf-8") == (
        "CLAUDE'S NEW VERSION\n"
    )
    # Helper returned one record naming both paths.
    assert len(sidecars) == 1
    assert sidecars[0].original == plan
    assert sidecars[0].sidecar == sidecar_path
    assert sidecars[0].pre_content == "ORIGINAL VERSION\n"


def test_save_sidecar_skips_unchanged_files(tmp_path: Path) -> None:
    """When the post-apply content matches the pre-apply state for a
    given file in pre_snapshot, no sidecar is written and the
    original is left alone. apply_finding may snapshot files it
    never edits (e.g. plan + detail; only detail changed); we
    shouldn't emit noise sidecars for the unchanged half."""
    a = tmp_path / "unchanged.md"
    b = tmp_path / "changed.md"
    a.write_text("same\n", encoding="utf-8")
    b.write_text("claude-edit\n", encoding="utf-8")
    pre_snapshot = {a: "same\n", b: "original\n"}

    sidecars = save_collision_sidecars(pre_snapshot)

    # Only the changed file gets a sidecar.
    assert len(sidecars) == 1
    assert sidecars[0].original == b
    # Unchanged file's sidecar path was NOT written.
    assert not collision_sidecar_path(a).exists()
    # Unchanged original keeps its content.
    assert a.read_text(encoding="utf-8") == "same\n"
    # Changed file got restored.
    assert b.read_text(encoding="utf-8") == "original\n"
    # Changed file's sidecar carries claude's edit.
    assert collision_sidecar_path(b).read_text(encoding="utf-8") == (
        "claude-edit\n"
    )


def test_save_sidecar_handles_file_created_by_apply(
    tmp_path: Path,
) -> None:
    """When apply_finding created a new file (pre_snapshot value is
    None) and that file exists now, the sidecar captures the new
    content and the original is deleted (matching the snapshot's
    delete-on-restore semantics for missing pre-state files)."""
    new_file = tmp_path / "new.md"
    new_file.write_text("claude-created\n", encoding="utf-8")
    pre_snapshot = {new_file: None}

    sidecars = save_collision_sidecars(pre_snapshot)

    assert len(sidecars) == 1
    # Original (which didn't exist pre-apply) is gone again.
    assert not new_file.exists()
    # Sidecar carries the claude-created content.
    assert collision_sidecar_path(new_file).read_text(
        encoding="utf-8"
    ) == "claude-created\n"


def test_save_sidecar_handles_file_deleted_by_apply(
    tmp_path: Path,
) -> None:
    """When apply_finding deleted a file (pre_snapshot value is
    non-None content, current file missing), restore puts the
    pre-apply content back. No sidecar is written because there's
    no post-apply content to save AND no record is appended to
    the returned list -- otherwise the caller's summary would
    render a useless ``<orig> ⇄ <orig>`` row (Bug 5 from the
    session-4 review)."""
    deleted = tmp_path / "deleted.md"
    pre_snapshot = {deleted: "original\n"}
    # File is missing -- claude deleted it.

    sidecars = save_collision_sidecars(pre_snapshot)

    # Original is restored.
    assert deleted.read_text(encoding="utf-8") == "original\n"
    # No sidecar (nothing to save).
    assert not collision_sidecar_path(deleted).exists()
    # NO record returned -- the delete-only case is silently
    # restored, not surfaced as a merge candidate.
    assert sidecars == []


def test_collision_sidecar_path_n_2_inserts_counter(
    tmp_path: Path,
) -> None:
    """``n=2`` (and higher) inserts a numeric suffix on the marker
    so consecutive drift collisions on the same original don't
    silently overwrite a prior unmerged sidecar (Bug 2)."""
    original = tmp_path / "plan.md"
    assert collision_sidecar_path(original, n=1) == (
        tmp_path / "plan-change-collision.md"
    )
    assert collision_sidecar_path(original, n=2) == (
        tmp_path / "plan-change-collision-2.md"
    )
    assert collision_sidecar_path(original, n=7) == (
        tmp_path / "plan-change-collision-7.md"
    )


def test_allocate_sidecar_picks_smallest_unused_n(
    tmp_path: Path,
) -> None:
    """``allocate_sidecar_path`` returns the smallest-N variant that
    doesn't exist on disk. Pre-populating slots 1 and 2 forces it
    to return slot 3."""
    original = tmp_path / "plan.md"
    collision_sidecar_path(original, n=1).write_text("a", encoding="utf-8")
    collision_sidecar_path(original, n=2).write_text("b", encoding="utf-8")

    allocated = allocate_sidecar_path(original)
    assert allocated == collision_sidecar_path(original, n=3)
    assert not allocated.exists()  # caller will write to it


def test_allocate_sidecar_raises_when_exhausted(
    tmp_path: Path,
) -> None:
    """When every slot up to ``max_n`` is occupied, allocator
    raises RuntimeError rather than silently overwriting -- forces
    the operator to inspect / clean up before re-running."""
    original = tmp_path / "plan.md"
    for n in range(1, 4):
        collision_sidecar_path(original, n=n).write_text(
            "x", encoding="utf-8"
        )
    with pytest.raises(RuntimeError, match="exhausted at n=3"):
        allocate_sidecar_path(original, max_n=3)


def test_save_sidecar_allocates_numbered_slot_on_second_drift(
    tmp_path: Path,
) -> None:
    """When ``<stem>-change-collision<ext>`` already exists (e.g.
    from a prior unmerged collision), the next save lands at
    ``<stem>-change-collision-2<ext>`` instead of overwriting
    (Bug 2 from session-4 review)."""
    plan = tmp_path / "plan.md"
    plan.write_text("second-claude-edit\n", encoding="utf-8")
    # Simulate a prior unmerged sidecar still on disk.
    collision_sidecar_path(plan, n=1).write_text(
        "first-claude-edit\n", encoding="utf-8"
    )
    pre_snapshot = {plan: "original\n"}

    sidecars = save_collision_sidecars(pre_snapshot)

    # First slot still contains the prior unmerged content -- NOT
    # overwritten.
    assert collision_sidecar_path(plan, n=1).read_text(
        encoding="utf-8"
    ) == "first-claude-edit\n"
    # Second slot got the new claude edit.
    assert collision_sidecar_path(plan, n=2).read_text(
        encoding="utf-8"
    ) == "second-claude-edit\n"
    # Original restored.
    assert plan.read_text(encoding="utf-8") == "original\n"
    # Record points at the numbered slot.
    assert len(sidecars) == 1
    assert sidecars[0].sidecar == collision_sidecar_path(plan, n=2)


def test_save_sidecar_continues_on_write_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """If writing the sidecar fails (simulated via permission
    revocation on the parent), the helper logs the failure and
    LEAVES claude's edits in place on the original. Token
    preservation (Lesson 2) > tree cleanliness on the failure path:
    losing both the sidecar AND the work would be worse than the
    legacy keep-on-disk behavior."""
    plan = tmp_path / "plan.md"
    plan.write_text("claude-edit\n", encoding="utf-8")
    pre_snapshot = {plan: "original\n"}

    # Make the parent unwritable so sidecar.write_text fails.
    import os
    os.chmod(tmp_path, 0o555)
    try:
        sidecars = save_collision_sidecars(pre_snapshot)
    finally:
        os.chmod(tmp_path, 0o755)

    # No sidecar in the list (write failed → skipped).
    assert sidecars == []
    # Original NOT restored -- claude's edits stay.
    assert plan.read_text(encoding="utf-8") == "claude-edit\n"
    # Stderr names the failure.
    err = capsys.readouterr().err
    assert "collision-sidecar write failed" in err


def test_save_sidecar_logs_orphan_on_keyboard_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When KeyboardInterrupt fires AFTER the sidecar is written but
    BEFORE the original is restored, the helper logs a recovery note
    naming both files before re-raising (Bug 7 from session-4 review).
    Without the note, the operator wouldn't know there's an orphan
    sidecar to merge or clean up."""
    plan = tmp_path / "plan.md"
    plan.write_text("claude\n", encoding="utf-8")
    pre_snapshot = {plan: "orig\n"}

    # Force KeyboardInterrupt at the restore step by monkey-patching
    # ``Path.write_text`` after the sidecar write has succeeded.
    real_write_text = Path.write_text
    state = {"writes": 0}

    def patched_write_text(self, *a, **kw):
        state["writes"] += 1
        if state["writes"] == 1:
            # First write = sidecar; let it succeed.
            return real_write_text(self, *a, **kw)
        # Second write = restore; simulate SIGINT mid-restore.
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "write_text", patched_write_text)
    try:
        with pytest.raises(KeyboardInterrupt):
            save_collision_sidecars(pre_snapshot)
    finally:
        monkeypatch.setattr(Path, "write_text", real_write_text)

    err = capsys.readouterr().err
    # Recovery note names both files so the operator can locate the
    # orphan and decide whether to merge or delete.
    assert "caught SIGINT mid-collision-save" in err
    assert "plan-change-collision.md" in err
    assert "plan.md" in err


# ---------- emit_collision_summary ----------


def test_emit_summary_no_op_on_empty(tmp_path: Path) -> None:
    """No-op when there are no sidecars -- caller can pass an empty
    list unconditionally."""
    buf = io.StringIO()
    emit_collision_summary([], repo_root=tmp_path, file=buf)
    assert buf.getvalue() == ""


def test_emit_summary_lists_pairs_and_merge_commands(
    tmp_path: Path,
) -> None:
    """Each sidecar gets a bullet showing the original and sidecar
    paths (repo-relative), plus example merge-tool invocations
    using the first sidecar."""
    plan = tmp_path / "plan.md"
    detail = tmp_path / "plan-details" / "step-1.md"
    sidecars = [
        CollisionSidecar(
            original=plan,
            sidecar=collision_sidecar_path(plan),
            pre_content="orig\n",
        ),
        CollisionSidecar(
            original=detail,
            sidecar=collision_sidecar_path(detail),
            pre_content="orig\n",
        ),
    ]
    buf = io.StringIO()
    emit_collision_summary(sidecars, repo_root=tmp_path, file=buf)
    out = buf.getvalue()

    # Header names the number of sidecars + the recovery intent.
    assert "drift collision" in out
    assert "2 sidecar file(s)" in out
    # Bug 4 fix: header explicitly disambiguates "plan/detail only"
    # so the operator doesn't think the sidecar carries their
    # source-file edits too.
    assert "plan/detail" in out
    assert "source-file edits" in out
    # Both pairs surface.
    assert "plan.md" in out
    assert "plan-change-collision.md" in out
    assert "step-1.md" in out
    assert "step-1-change-collision.md" in out
    # Example merge commands cite the FIRST pair.
    assert "code --diff plan.md plan-change-collision.md" in out
    assert "vimdiff plan.md plan-change-collision.md" in out
    assert "meld plan.md plan-change-collision.md" in out


# ---------- prompt_user_to_merge ----------


def test_prompt_returns_false_when_yes_flag_set(tmp_path: Path) -> None:
    """``yes=True`` skips the prompt entirely and signals 'no merge'
    so headless callers fall through to legacy halt."""
    sidecars = [
        CollisionSidecar(
            original=tmp_path / "p.md",
            sidecar=tmp_path / "p-change-collision.md",
            pre_content="x",
        )
    ]
    buf = io.StringIO()
    result = prompt_user_to_merge(
        sidecars,
        yes=True,
        input_fn=lambda _: "should not be called",
        isatty_fn=lambda: True,
        file=buf,
    )
    assert result is False
    assert "skipping merge pause" in buf.getvalue()


def test_prompt_returns_false_when_non_tty(tmp_path: Path) -> None:
    """Non-TTY skips the prompt for the same reason -- nothing to
    block on, and no human to merge."""
    sidecars = [
        CollisionSidecar(
            original=tmp_path / "p.md",
            sidecar=tmp_path / "p-change-collision.md",
            pre_content="x",
        )
    ]
    buf = io.StringIO()
    result = prompt_user_to_merge(
        sidecars,
        yes=False,
        input_fn=lambda _: "",
        isatty_fn=lambda: False,
        file=buf,
    )
    assert result is False


def test_prompt_returns_true_when_user_presses_enter(
    tmp_path: Path,
) -> None:
    """Empty response (Enter) signals 'merge done; continue'. The
    caller breaks out of the per-finding loop so the outer
    while-loop recollects findings against the merged state."""
    sidecars = [
        CollisionSidecar(
            original=tmp_path / "p.md",
            sidecar=tmp_path / "p-change-collision.md",
            pre_content="x",
        )
    ]
    buf = io.StringIO()
    result = prompt_user_to_merge(
        sidecars,
        yes=False,
        input_fn=lambda _: "",
        isatty_fn=lambda: True,
        file=buf,
    )
    assert result is True
    assert "merge acknowledged" in buf.getvalue()


def test_prompt_returns_false_on_abort_keywords(
    tmp_path: Path,
) -> None:
    """Typing 'n', 'no', 'a', 'abort', 'q', or 'quit' signals
    'halt iteration'. Anything else (including 'yes', 'continue',
    'go', or just Enter) signals 'continue'."""
    sidecars = [
        CollisionSidecar(
            original=tmp_path / "p.md",
            sidecar=tmp_path / "p-change-collision.md",
            pre_content="x",
        )
    ]

    for word in ("n", "no", "abort", "a", "q", "quit"):
        buf = io.StringIO()
        result = prompt_user_to_merge(
            sidecars,
            yes=False,
            input_fn=lambda _, w=word: w,
            isatty_fn=lambda: True,
            file=buf,
        )
        assert result is False, f"expected {word!r} to abort"
        assert "halting iteration" in buf.getvalue()


def test_prompt_returns_false_on_eof(tmp_path: Path) -> None:
    """Ctrl-D (EOFError from input) → halt. Matches the explicit
    abort-keyword behavior so the caller's halt path is the same
    whether the user typed 'q' or pressed Ctrl-D."""
    sidecars = [
        CollisionSidecar(
            original=tmp_path / "p.md",
            sidecar=tmp_path / "p-change-collision.md",
            pre_content="x",
        )
    ]

    def _eof(_):
        raise EOFError

    buf = io.StringIO()
    result = prompt_user_to_merge(
        sidecars,
        yes=False,
        input_fn=_eof,
        isatty_fn=lambda: True,
        file=buf,
    )
    assert result is False
    assert "aborted via EOF" in buf.getvalue()


# ---------- handle_drift_collision (end-to-end helper) ----------


def test_handle_drift_collision_full_flow(tmp_path: Path) -> None:
    """End-to-end: write sidecars + emit summary + prompt for merge.
    Returns True when the user merges + continues."""
    plan = tmp_path / "plan.md"
    plan.write_text("claude\n", encoding="utf-8")
    pre_snapshot = {plan: "orig\n"}
    buf = io.StringIO()

    result = handle_drift_collision(
        pre_snapshot,
        repo_root=tmp_path,
        yes=False,
        input_fn=lambda _: "",
        isatty_fn=lambda: True,
        file=buf,
    )

    assert result is True
    # Sidecar written, original restored.
    assert collision_sidecar_path(plan).read_text(
        encoding="utf-8"
    ) == "claude\n"
    assert plan.read_text(encoding="utf-8") == "orig\n"
    # Summary emitted before the prompt -- the user sees the file
    # list and merge commands first.
    out = buf.getvalue()
    assert "drift collision" in out
    assert "merge acknowledged" in out
    assert out.index("drift collision") < out.index("merge acknowledged")


def test_handle_drift_collision_returns_false_when_no_changes(
    tmp_path: Path,
) -> None:
    """When apply_finding wrote nothing (every file in pre_snapshot
    matches its pre-apply content -- e.g. a NOT-APPLICABLE verdict
    that didn't touch disk), handle_drift_collision returns False
    without prompting. Caller proceeds with legacy halt."""
    plan = tmp_path / "plan.md"
    plan.write_text("same\n", encoding="utf-8")
    pre_snapshot = {plan: "same\n"}
    buf = io.StringIO()

    called_input = {"n": 0}

    def _input(_):
        called_input["n"] += 1
        return ""

    result = handle_drift_collision(
        pre_snapshot,
        repo_root=tmp_path,
        yes=False,
        input_fn=_input,
        isatty_fn=lambda: True,
        file=buf,
    )

    assert result is False
    assert called_input["n"] == 0  # never prompted


def test_handle_drift_collision_headless_halts_after_summary(
    tmp_path: Path,
) -> None:
    """Headless callers (yes=True) still get the sidecar summary --
    they can investigate later via the sidecar files -- but the
    prompt is skipped and the helper returns False so the caller
    falls through to legacy halt."""
    plan = tmp_path / "plan.md"
    plan.write_text("claude\n", encoding="utf-8")
    pre_snapshot = {plan: "orig\n"}
    buf = io.StringIO()

    result = handle_drift_collision(
        pre_snapshot,
        repo_root=tmp_path,
        yes=True,
        input_fn=lambda _: pytest.fail("should not prompt"),
        isatty_fn=lambda: True,
        file=buf,
    )

    assert result is False
    out = buf.getvalue()
    # Summary emitted so the operator sees the sidecar.
    assert "drift collision" in out
    # Prompt-skipped message emitted so the operator knows why.
    assert "skipping merge pause" in out
    # Sidecar physically exists; original restored.
    assert collision_sidecar_path(plan).exists()
    assert plan.read_text(encoding="utf-8") == "orig\n"


class TestChangeCollisionStyleOutput:
    """change_collision.py's ``plan-tool:`` diagnostics route through
    ``style.tool()``. Plain mode stays byte-identical to the legacy
    ``print(f"plan-tool: ...")`` strings; under ``PLAN_TOOL_FORCE_COLOR``
    only the ``plan-tool:`` tag carries ANSI, and the subordinate
    continuation lines (pair bullets, the example-command block) stay raw.
    """

    def _sidecar(self, tmp_path: Path) -> CollisionSidecar:
        original = tmp_path / "plans" / "2-foo.md"
        sidecar = tmp_path / "plans" / "2-foo-change-collision.md"
        return CollisionSidecar(
            original=original, sidecar=sidecar, pre_content="orig\n",
        )

    def test_summary_header_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        emit_collision_summary(
            [self._sidecar(tmp_path)], repo_root=tmp_path, file=buf,
        )
        first_line = buf.getvalue().splitlines()[0] + "\n"
        assert first_line == (
            "plan-tool: drift collision -- saved claude's plan/detail "
            "edits to 1 sidecar file(s). Originals "
            "restored to pre-apply state. NOTE: your source-file edits "
            "(the changes on watched ``step.files`` that triggered "
            "this drift) are untouched on disk -- the sidecar(s) below "
            "only carry claude's plan/detail proposals. Merge the "
            "sidecars manually:\n"
        )

    def test_summary_continuation_lines_have_no_prefix(
        self, tmp_path: Path
    ) -> None:
        buf = io.StringIO()
        emit_collision_summary(
            [self._sidecar(tmp_path)], repo_root=tmp_path, file=buf,
        )
        lines = buf.getvalue().splitlines()
        # Skip the header (line 0); every continuation line is raw.
        for line in lines[1:]:
            assert "plan-tool:" not in line
        joined = "\n".join(lines)
        assert "⇄" in joined
        assert "Example merge commands (pick any tool):" in joined
        assert "code --diff" in joined
        assert "vimdiff" in joined
        assert "meld" in joined

    def test_prompt_headless_skip_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        result = prompt_user_to_merge(
            [self._sidecar(tmp_path)],
            input_fn=lambda _: pytest.fail("should not prompt"),
            isatty_fn=lambda: False,
            file=buf,
        )
        assert result is False
        assert buf.getvalue() == (
            "plan-tool: skipping merge pause (non-interactive); "
            "halting iteration. Re-run after merging the sidecar "
            "file(s) above.\n"
        )

    def test_prompt_eof_abort_plain(self, tmp_path: Path) -> None:
        def _raise_eof(_: str) -> str:
            raise EOFError

        buf = io.StringIO()
        result = prompt_user_to_merge(
            [self._sidecar(tmp_path)],
            input_fn=_raise_eof,
            isatty_fn=lambda: True,
            file=buf,
        )
        assert result is False
        assert "plan-tool: merge prompt aborted via EOF;" in buf.getvalue()

    def test_prompt_declined_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        result = prompt_user_to_merge(
            [self._sidecar(tmp_path)],
            input_fn=lambda _: "n",
            isatty_fn=lambda: True,
            file=buf,
        )
        assert result is False
        assert "plan-tool: merge prompt declined;" in buf.getvalue()

    def test_prompt_acknowledged_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        result = prompt_user_to_merge(
            [self._sidecar(tmp_path)],
            input_fn=lambda _: "",
            isatty_fn=lambda: True,
            file=buf,
        )
        assert result is True
        assert buf.getvalue() == (
            "plan-tool: merge acknowledged; continuing iteration with "
            "the merged state.\n"
        )

    def test_save_write_failed_plain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = tmp_path / "cli.py"
        original.write_text("new\n", encoding="utf-8")

        def _raising_write_text(self: Path, *a: object, **k: object) -> int:
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", _raising_write_text)
        buf = io.StringIO()
        sidecars = save_collision_sidecars({original: "old\n"}, file=buf)
        assert sidecars == []
        sidecar = collision_sidecar_path(original)
        assert (
            f"plan-tool: collision-sidecar write failed for {sidecar}:"
            in buf.getvalue()
        )

    def test_summary_header_color_prefix_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        buf = io.StringIO()
        emit_collision_summary(
            [self._sidecar(tmp_path)], repo_root=tmp_path, file=buf,
        )
        out = buf.getvalue()
        assert out.startswith(style.DIM + "plan-tool:" + style.RESET + " ")
        assert "drift collision -- saved claude's plan/detail" in out
