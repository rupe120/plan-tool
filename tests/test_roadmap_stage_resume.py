from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from plan_tool import roadmap_stage_resume as rsr
from plan_tool.run_log import in_flight_path, run_dir

SLUG = "demo"
DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def _seed(root: Path, n: int = 3) -> Path:
    rsr.write_brief_digest(root, SLUG, DIGEST)
    for i in range(1, n + 1):
        rsr.write_stage(root, SLUG, i, f"stage {i} text\n")
    return rsr.resume_dir_path(root, SLUG)


class TestPathAndRoundTrip:
    def test_resume_dir_path_is_under_the_run_directory(self, tmp_path: Path) -> None:
        path = rsr.resume_dir_path(tmp_path, SLUG)
        assert path == run_dir(tmp_path, SLUG) / rsr.RESUME_DIRNAME
        assert not (tmp_path / ".plan-tool").exists()

    def test_resume_dir_name_does_not_collide_with_run_log_names(self, tmp_path: Path) -> None:
        assert not rsr.RESUME_DIRNAME.endswith(".jsonl")
        assert rsr.RESUME_DIRNAME != in_flight_path(tmp_path, SLUG).name

    def test_write_then_read_round_trips_digest_and_stages(self, tmp_path: Path) -> None:
        _seed(tmp_path)
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert held.brief_digest == DIGEST
        assert held.stages == ((1, "stage 1 text\n"), (2, "stage 2 text\n"), (3, "stage 3 text\n"))
        assert held.warnings == ()

    def test_first_write_creates_the_run_directory_and_a_read_of_a_missing_one_returns_none(
        self, tmp_path: Path
    ) -> None:
        assert not run_dir(tmp_path, SLUG).exists()
        assert rsr.read_held_stages(tmp_path, SLUG) is None
        assert not run_dir(tmp_path, SLUG).exists()
        rsr.write_brief_digest(tmp_path, SLUG, DIGEST)
        assert rsr.resume_dir_path(tmp_path, SLUG).is_dir()

    def test_rewriting_a_stage_replaces_only_that_file(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path, 2)
        before = (directory / "stage-1.md").read_bytes()
        rsr.write_stage(tmp_path, SLUG, 2, "new two\n")
        assert (directory / "stage-1.md").read_bytes() == before
        assert (directory / "stage-2.md").read_text() == "new two\n"

    def test_write_failure_keeps_the_previous_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        directory = _seed(tmp_path, 1)

        def boom(*_a: object, **_k: object) -> None:
            raise OSError("rename failed")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError):
            rsr.write_stage(tmp_path, SLUG, 1, "half\n")
        assert (directory / "stage-1.md").read_text() == "stage 1 text\n"
        assert not [p for p in directory.iterdir() if p.name.endswith(".tmp")]


class TestResumeWritesAreDurable:
    def test_digest_and_stage_writes_sync_to_disk_so_a_power_loss_keeps_paid_for_stages(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        synced: list[int] = []
        real_fsync = os.fsync
        monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd))[1])

        rsr.write_brief_digest(tmp_path, SLUG, DIGEST)
        after_digest = len(synced)
        rsr.write_stage(tmp_path, SLUG, 1, "stage 1 text\n")

        assert after_digest >= 1
        assert len(synced) > after_digest

    def test_a_first_write_creates_the_missing_resume_directory(self, tmp_path: Path) -> None:
        rsr.write_stage(tmp_path, SLUG, 1, "stage 1 text\n")

        assert (rsr.resume_dir_path(tmp_path, SLUG) / "stage-1.md").read_text() == "stage 1 text\n"


class TestInterruptedWriteLeftoversAreNotWarnedAbout:
    def test_a_killed_write_temp_file_is_ignored_silently_and_left_in_place(
        self, tmp_path: Path
    ) -> None:
        directory = _seed(tmp_path, 2)
        (directory / ".stage-3.md.12345.tmp").write_text("partial")
        (directory / ".brief.digest.k3j2h1.tmp").write_text("partial")
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert [n for n, _ in held.stages] == [1, 2]
        assert held.warnings == ()
        assert (directory / ".stage-3.md.12345.tmp").exists()

    def test_any_other_unexpected_file_still_warns(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path, 1)
        for name in ("stray.txt", "stage-9.tmp", ".hidden"):
            (directory / name).write_text("x")
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert sum("unexpected file" in w for w in held.warnings) == 3


class TestDamageIsRegeneratedNeverRaisedOrDeletedByARead:
    def test_unreadable_stage_file_ends_the_held_run_with_a_warning(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path)
        (directory / "stage-2.md").write_bytes(b"\xff\xfe\x00bad")
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert [n for n, _ in held.stages] == [1]
        assert any(str(directory / "stage-2.md") in w for w in held.warnings)
        assert (directory / "stage-2.md").exists() and (directory / "stage-3.md").exists()

    def test_gap_in_stage_files_ends_the_held_run(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path, 3)
        (directory / "stage-2.md").unlink()
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert [n for n, _ in held.stages] == [1]
        assert any(str(directory / "stage-3.md") in w for w in held.warnings)

    def test_empty_stage_file_is_not_held(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path, 1)
        (directory / "stage-1.md").write_text("")
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert held.stages == ()
        assert any("stage-1.md" in w for w in held.warnings)

    def test_oddly_named_file_in_the_directory_is_ignored_with_a_warning(
        self, tmp_path: Path
    ) -> None:
        directory = _seed(tmp_path, 2)
        (directory / "stage-01.md").write_text("x")
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert [n for n, _ in held.stages] == [1, 2]
        assert len(held.warnings) == 1 and "stage-01.md" in held.warnings[0]

    def test_missing_digest_file_reads_as_none_digest_with_a_warning(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path, 2)
        (directory / rsr.DIGEST_FILENAME).unlink()
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert held.brief_digest is None
        assert len(held.stages) == 2
        assert any(rsr.DIGEST_FILENAME in w for w in held.warnings)

    @pytest.mark.parametrize("bad", ["A" * 64, "abc123", ""])
    def test_malformed_digest_reads_as_none_digest_with_a_warning(
        self, tmp_path: Path, bad: str
    ) -> None:
        directory = _seed(tmp_path, 1)
        (directory / rsr.DIGEST_FILENAME).write_text(bad)
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        assert held.brief_digest is None
        assert any(rsr.DIGEST_FILENAME in w for w in held.warnings)

    def test_a_read_never_deletes_or_rewrites_any_file(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path, 4)
        (directory / "stage-2.md").write_bytes(b"\xff\xfe")
        (directory / "stage-3.md").write_text("")
        (directory / "stray.txt").write_text("x")
        (directory / rsr.DIGEST_FILENAME).write_text("nope")
        before = _snapshot(directory)
        assert rsr.read_held_stages(tmp_path, SLUG) is not None
        assert _snapshot(directory) == before


class TestTheOneRefusal:
    def test_matching_digest_passes(self, tmp_path: Path) -> None:
        _seed(tmp_path, 1)
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        rsr.require_matching_brief_digest(held, DIGEST)

    def test_changed_brief_digest_refuses_naming_the_directory_and_the_remedy(
        self, tmp_path: Path
    ) -> None:
        directory = _seed(tmp_path, 2)
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None
        before = _snapshot(directory)
        with pytest.raises(rsr.RoadmapStageResumeBriefChanged) as info:
            rsr.require_matching_brief_digest(held, OTHER_DIGEST)
        message = str(info.value)
        assert str(directory) in message
        for remedy in ("Restore the original brief", "delete", "successor slug"):
            assert remedy in message
        assert _snapshot(directory) == before

    def test_unverifiable_digest_does_not_raise_the_changed_brief_error(
        self, tmp_path: Path
    ) -> None:
        directory = _seed(tmp_path, 1)
        (directory / rsr.DIGEST_FILENAME).unlink()
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None and held.brief_digest is None
        rsr.require_matching_brief_digest(held, OTHER_DIGEST)


class TestDiscardAndDelete:
    def test_discard_stages_from_removes_that_stage_and_every_later_one(
        self, tmp_path: Path
    ) -> None:
        directory = _seed(tmp_path, 3)
        rsr.discard_stages_from(tmp_path, SLUG, 2)
        assert sorted(p.name for p in directory.iterdir()) == [rsr.DIGEST_FILENAME, "stage-1.md"]

    def test_discard_warns_and_continues_when_an_entry_cannot_be_removed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The module contract is warn, never raise: a stray stage-N entry that
        # is a directory must not abort preflight; the later write fails loudly.
        directory = _seed(tmp_path, 2)
        (directory / "stage-9.md").mkdir()
        (directory / "stage-3.md").write_text("later\n", encoding="utf-8")
        rsr.discard_stages_from(tmp_path, SLUG, 3)
        assert not (directory / "stage-3.md").exists()
        assert (directory / "stage-9.md").is_dir()
        assert "stage-9.md" in capsys.readouterr().err

    def test_delete_resume_removes_the_directory_and_reports_true(self, tmp_path: Path) -> None:
        directory = _seed(tmp_path)
        assert rsr.delete_resume(tmp_path, SLUG) is True
        assert not directory.exists()

    def test_delete_of_a_missing_directory_is_not_an_error(self, tmp_path: Path) -> None:
        assert rsr.delete_resume(tmp_path, SLUG) is False


class TestDeliberateNonChecks:
    def test_stage_text_is_stored_without_parsing(self, tmp_path: Path) -> None:
        garbage = "::: not yaml\n\t- [unclosed\n---\n\x01 weird"
        rsr.write_brief_digest(tmp_path, SLUG, DIGEST)
        rsr.write_stage(tmp_path, SLUG, 1, garbage)
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None and held.stages == ((1, garbage),)

    @pytest.mark.parametrize("count", [1, 9])
    def test_any_stage_count_is_accepted(self, tmp_path: Path, count: int) -> None:
        _seed(tmp_path, count)
        held = rsr.read_held_stages(tmp_path, SLUG)
        assert held is not None and len(held.stages) == count


class TestSlugSafety:
    @pytest.mark.parametrize("bad", ["..", "a/b", "a\\b", ""])
    def test_slug_with_traversal_or_separator_is_rejected(self, tmp_path: Path, bad: str) -> None:
        with pytest.raises(ValueError):
            rsr.resume_dir_path(tmp_path, bad)


class TestLeafDiscipline:
    def test_leaf_imports_no_roadmap_stage_run_module_at_import_time(self) -> None:
        pkg_dir = Path(__file__).resolve().parents[1] / "plan_tool"
        code = (
            "import sys, types\n"
            "pkg = types.ModuleType('plan_tool')\n"
            f"pkg.__path__ = [{str(pkg_dir)!r}]\n"
            "sys.modules['plan_tool'] = pkg\n"
            "import plan_tool.roadmap_stage_resume\n"
            "loaded = {m for m in sys.modules if m.startswith('plan_tool.roadmap')}\n"
            "allowed = {'plan_tool.roadmap_stage_resume', 'plan_tool.roadmap_artifacts'}\n"
            "assert loaded == allowed, loaded\n"
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr

    def test_leaf_source_has_no_first_party_import_beyond_the_three_allowed(self) -> None:
        src = Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_stage_resume.py"
        text = src.read_text()
        found = set(re.findall(r"(?m)^\s*(?:from|import)\s+(plan_tool[\w.]*)", text))
        assert found == {"plan_tool.fileio", "plan_tool.roadmap_artifacts", "plan_tool.run_log"}
        assert not re.search(r"input\(|isatty|sys\.exit", text)
