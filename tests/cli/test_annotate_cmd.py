"""Unit/helper tests for the ``annotate`` command module.

Split-proof at the handler grain: every test drives ``cmd_annotate``
**directly** with an ``argparse.Namespace`` and an explicit ``invoker=``
stub (a recording closure returning canned classification JSON), so no
``plan_tool.cli`` module global is patched and the autouse backend gate
never fires. The real ``classify_plan_implementation`` + renderers run —
only the one Claude call is stubbed. ``main([...])`` end-to-end coverage
lives in ``tests/test_cli.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from plan_tool import annotate as annotate_module
from plan_tool.cli import annotate_cmd
from plan_tool.cli.annotate_cmd import cmd_annotate
from plan_tool.cli.parser import assemble
from plan_tool.create import ArchiveResult


# --- canned classification -------------------------------------------------

# A PARTIAL whose remaining_work and code_refs are distinct recognizable
# strings, so the carryover/done-context split is checkable end to end.
_PARTIAL_REMAINING = "finish wiring the resolver into dispatch"
_PARTIAL_CODE_REF = "resolver.py:resolve"


def _canned_sections() -> list[dict]:
    return [
        {
            "heading": "Goal A",
            "status": "IMPLEMENTED",
            "evidence": "already present",
            "code_refs": ["a.py:foo"],
        },
        {
            "heading": "Feature B",
            "status": "PARTIAL",
            "evidence": "half done",
            "code_refs": [_PARTIAL_CODE_REF],
            "remaining": _PARTIAL_REMAINING,
        },
        {
            "heading": "Feature C",
            "status": "NOT-IMPLEMENTED",
            "evidence": "no trace in code",
        },
    ]


def _recording_stub(sections: list[dict] | None = None):
    """A canned-JSON invoker that records each prompt it receives."""
    payload = json.dumps(_canned_sections() if sections is None else sections)
    calls: list[str] = []

    def stub(prompt: str) -> str:
        calls.append(prompt)
        return payload

    stub.calls = calls  # type: ignore[attr-defined]
    return stub


_SOURCE_TEXT = (
    "# My Plan\n\n"
    "## Goal A\n\nDo the A thing in `src/a.py`.\n\n"
    "## Feature B\n\nDo the B thing in `src/b.py`.\n\n"
    "## Feature C\n\nDo the C thing in `src/c.py`.\n"
)


def _write_source(tmp_path: Path, name: str = "plan.md") -> Path:
    (tmp_path / "src").mkdir(exist_ok=True)
    for code_name in ("a.py", "b.py", "c.py"):
        (tmp_path / "src" / code_name).write_text("# grounded\n", encoding="utf-8")
    path = tmp_path / name
    path.write_text(_SOURCE_TEXT, encoding="utf-8")
    return path


def _ns(plan_file: Path, **overrides) -> argparse.Namespace:
    """Build a cmd_annotate Namespace; ``repo_root`` defaults to the source dir."""
    base = dict(
        plans_dir=None,
        manifest=None,
        repo_root=plan_file.parent,
        plan_file=plan_file,
        plan_files=None,
        output_dir=None,
        report_dir=None,
        seed_dir=None,
        report=None,
        seed=None,
        archive=False,
        iterate=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _build_parser():
    return assemble("desc", (annotate_cmd,))[0]


def _find_subparser(parser, name: str):
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and name in choices:
            return choices[name]
    return None


# --- parse surface ---------------------------------------------------------


def test_annotate_subparser_registered() -> None:
    assert _find_subparser(_build_parser(), "annotate") is not None


def test_annotate_parses_paths_and_flags() -> None:
    sub = _find_subparser(_build_parser(), "annotate")
    ns = sub.parse_args(
        [
            "plan.md",
            "more/*.md",
            "--output-dir",
            "o",
            "--report-dir",
            "reports",
            "--seed-dir",
            "seeds",
            "--report",
            "r.md",
            "--seed",
            "s.md",
            "--archive",
            "--iterate",
        ]
    )
    assert ns.plan_files == [Path("plan.md"), Path("more/*.md")]
    assert ns.output_dir == Path("o")
    assert ns.report_dir == Path("reports")
    assert ns.seed_dir == Path("seeds")
    assert ns.report == Path("r.md")
    assert ns.seed == Path("s.md")
    assert ns.archive is True
    assert ns.iterate is True


def test_iterate_defaults_off() -> None:
    sub = _find_subparser(_build_parser(), "annotate")
    assert sub.parse_args(["plan.md"]).iterate is False
    assert sub.parse_args(["plan.md", "--no-iterate"]).iterate is False


def test_iterate_is_rejected_before_annotation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_source(tmp_path)
    invoker = _recording_stub()
    rc = cmd_annotate(_ns(src, iterate=True), invoker=invoker)
    assert rc == 2
    assert invoker.calls == []
    assert not (tmp_path / "plan.annotated.md").exists()
    assert not (tmp_path / "plan.seed.md").exists()
    assert "--iterate is not supported for annotate" in capsys.readouterr().err


def test_archive_defaults_off() -> None:
    sub = _find_subparser(_build_parser(), "annotate")
    assert sub.parse_args(["plan.md"]).archive is False


# --- handler behavior ------------------------------------------------------


def test_writes_report_and_seed(tmp_path: Path) -> None:
    src = _write_source(tmp_path)
    rc = cmd_annotate(_ns(src), invoker=_recording_stub())
    assert rc == 0
    assert (tmp_path / "plan.annotated.md").is_file()
    assert (tmp_path / "plan.seed.md").is_file()


def test_unmatched_opening_fence_skips_classifier_outputs_and_archive(
    tmp_path: Path,
) -> None:
    src = _write_source(tmp_path)
    original = src.read_text(encoding="utf-8") + "\n```\n"
    src.write_text(original, encoding="utf-8")
    invoker = _recording_stub()

    rc = cmd_annotate(_ns(src, archive=True), invoker=invoker)

    assert rc == 1
    assert invoker.calls == []
    assert src.read_text(encoding="utf-8") == original
    assert not (tmp_path / "plan.annotated.md").exists()
    assert not (tmp_path / "plan.seed.md").exists()
    assert not (tmp_path / "archive").exists()


def test_report_is_additive(tmp_path: Path) -> None:
    src = _write_source(tmp_path)
    cmd_annotate(_ns(src), invoker=_recording_stub())
    report = (tmp_path / "plan.annotated.md").read_text(encoding="utf-8")
    for line in _SOURCE_TEXT.splitlines():
        assert line in report


def test_seed_lists_carryover_headings(tmp_path: Path) -> None:
    src = _write_source(tmp_path)
    cmd_annotate(_ns(src), invoker=_recording_stub())
    seed = (tmp_path / "plan.seed.md").read_text(encoding="utf-8")
    carryover, _, done = seed.partition(
        "## Already implemented (done-context — do not re-plan)"
    )
    # NOT-IMPLEMENTED heading + the PARTIAL's remaining_work carry forward.
    assert "Feature C" in carryover
    assert _PARTIAL_REMAINING in carryover
    # The PARTIAL's already-implemented refs live only in done-context.
    assert _PARTIAL_CODE_REF not in carryover
    assert _PARTIAL_CODE_REF in done


def test_output_dir_redirects_both_artifacts(tmp_path: Path) -> None:
    src = _write_source(tmp_path)
    out = tmp_path / "out"
    rc = cmd_annotate(_ns(src, output_dir=out), invoker=_recording_stub())
    assert rc == 0
    assert (out / "plan.annotated.md").is_file()
    assert (out / "plan.seed.md").is_file()


def test_report_and_seed_path_overrides_used_verbatim(tmp_path: Path) -> None:
    src = _write_source(tmp_path)
    report = tmp_path / "custom" / "r.md"
    seed = tmp_path / "other" / "s.md"
    rc = cmd_annotate(
        _ns(src, report=report, seed=seed), invoker=_recording_stub()
    )
    assert rc == 0
    assert report.is_file()
    assert seed.is_file()


def test_report_and_seed_dirs_split_batch_outputs(tmp_path: Path) -> None:
    first = _write_source(tmp_path, name="a.md")
    second = _write_source(tmp_path, name="b.md")
    report_dir = tmp_path / "reports"
    seed_dir = tmp_path / "seeds"

    rc = cmd_annotate(
        _ns(
            first,
            plan_files=[first, second],
            report_dir=report_dir,
            seed_dir=seed_dir,
        ),
        invoker=_recording_stub(),
    )

    assert rc == 0
    assert (report_dir / "a.annotated.md").is_file()
    assert (report_dir / "b.annotated.md").is_file()
    assert (seed_dir / "a.seed.md").is_file()
    assert (seed_dir / "b.seed.md").is_file()


def test_batch_continues_past_per_file_failure_and_summarizes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _write_source(tmp_path, name="a.md")
    second = _write_source(tmp_path, name="b.md")
    missing = tmp_path / "missing.md"
    invoker = _recording_stub()

    rc = cmd_annotate(
        _ns(first, plan_files=[first, missing, second]), invoker=invoker
    )

    assert rc == 1
    assert len(invoker.calls) == 2
    assert (tmp_path / "a.annotated.md").is_file()
    assert not (tmp_path / "missing.annotated.md").exists()
    assert (tmp_path / "b.annotated.md").is_file()
    captured = capsys.readouterr()
    assert "annotate batch summary" in captured.out
    assert "a.md" in captured.out
    assert "missing.md" in captured.out
    assert "b.md" in captured.out
    assert "FAIL" in captured.out
    assert "1/3" in captured.out
    assert "3/3 (0 skipped)" in captured.out


def _write_unsupported_format_version_source(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        "---\n"
        "title: Newer plan\n"
        "status: planning\n"
        "priority: low\n"
        "format_version: 999\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )
    return path


def test_batch_continues_past_an_unsupported_plan_format_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _write_source(tmp_path, name="a.md")
    bad = _write_unsupported_format_version_source(tmp_path, "b.md")
    third = _write_source(tmp_path, name="c.md")
    invoker = _recording_stub()

    rc = cmd_annotate(
        _ns(first, plan_files=[first, bad, third]), invoker=invoker
    )

    assert rc == 1
    assert len(invoker.calls) == 2
    assert (tmp_path / "a.annotated.md").is_file()
    assert (tmp_path / "a.seed.md").is_file()
    assert not (tmp_path / "b.annotated.md").exists()
    assert not (tmp_path / "b.seed.md").exists()
    assert (tmp_path / "c.annotated.md").is_file()
    assert (tmp_path / "c.seed.md").is_file()
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "b.md" in captured.out


def _write_unsupported_detail_marker_source(tmp_path: Path, name: str) -> Path:
    from plan_tool.detail_artifacts import render_detail_format_version_marker

    (tmp_path / f"{name}.detail.md").write_text(
        f"# Step\n{render_detail_format_version_marker(999)}\n\nfine.\n",
        encoding="utf-8",
    )
    path = tmp_path / name
    path.write_text(
        "---\n"
        "title: Plan\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        f"    detail: {name}.detail.md\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )
    return path


def test_batch_continues_past_one_sources_unsupported_detail_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _write_source(tmp_path, name="a.md")
    bad = _write_unsupported_detail_marker_source(tmp_path, "b.md")
    third = _write_source(tmp_path, name="c.md")
    invoker = _recording_stub()

    rc = cmd_annotate(
        _ns(first, plan_files=[first, bad, third]), invoker=invoker
    )

    assert rc == 1
    assert len(invoker.calls) == 2
    assert (tmp_path / "a.annotated.md").is_file()
    assert (tmp_path / "a.seed.md").is_file()
    assert not (tmp_path / "b.annotated.md").exists()
    assert not (tmp_path / "b.seed.md").exists()
    assert (tmp_path / "c.annotated.md").is_file()
    assert (tmp_path / "c.seed.md").is_file()
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "b.md" in captured.out


def test_batch_expands_globs_in_sorted_order(tmp_path: Path) -> None:
    first = _write_source(tmp_path, name="b.md")
    _write_source(tmp_path, name="a.md")
    invoker = _recording_stub()

    rc = cmd_annotate(
        _ns(first, plan_files=[tmp_path / "*.md"]), invoker=invoker
    )

    assert rc == 0
    assert len(invoker.calls) == 2
    assert (tmp_path / "a.annotated.md").is_file()
    assert (tmp_path / "b.annotated.md").is_file()


def test_batch_expands_directory_and_excludes_generated_or_archived_inputs(
    tmp_path: Path,
) -> None:
    active = _write_source(tmp_path, name="a.md")
    archive = tmp_path / "archive"
    archive.mkdir()
    archived = _write_source(archive, name="b.md")
    details = tmp_path / "plan-details" / "demo"
    details.mkdir(parents=True)
    detail = _write_source(details, name="01-step.md")
    generated_report = tmp_path / "a.annotated.md"
    generated_report.write_text("# report\n", encoding="utf-8")
    generated_seed = tmp_path / "a.seed.md"
    generated_seed.write_text("# seed\n", encoding="utf-8")
    invoker = _recording_stub()

    rc = cmd_annotate(_ns(active, plan_files=[tmp_path]), invoker=invoker)

    assert rc == 0
    assert len(invoker.calls) == 1
    assert (tmp_path / "a.annotated.md").is_file()
    assert not (archive / "b.annotated.md").exists()
    assert not (details / "01-step.annotated.md").exists()
    assert archived.is_file()
    assert detail.is_file()


def test_zero_match_glob_returns_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_source(tmp_path)
    invoker = _recording_stub()

    rc = cmd_annotate(
        _ns(src, plan_files=[tmp_path / "missing-*.md"]), invoker=invoker
    )

    assert rc == 2
    assert invoker.calls == []
    assert "no plans matched" in capsys.readouterr().err


def test_batch_rejects_duplicate_derived_output_paths(tmp_path: Path) -> None:
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    first = _write_source(first_dir, name="plan.md")
    second = _write_source(second_dir, name="plan.md")
    out = tmp_path / "out"
    invoker = _recording_stub()

    rc = cmd_annotate(
        _ns(first, plan_files=[first, second], output_dir=out), invoker=invoker
    )

    assert rc == 2
    assert invoker.calls == []
    assert not (out / "plan.annotated.md").exists()


def test_batch_rejects_explicit_single_file_artifact_paths(tmp_path: Path) -> None:
    first = _write_source(tmp_path, name="a.md")
    second = _write_source(tmp_path, name="b.md")
    invoker = _recording_stub()

    rc = cmd_annotate(
        _ns(first, plan_files=[first, second], report=tmp_path / "one.md"),
        invoker=invoker,
    )

    assert rc == 2
    assert invoker.calls == []
    assert not (tmp_path / "one.md").exists()


def test_archive_moves_original_with_report_notice(tmp_path: Path) -> None:
    src = _write_source(tmp_path, name="2-old-plan.md")
    bundle = tmp_path / "plan-details" / "old-plan"
    bundle.mkdir(parents=True)
    (bundle / "1-step.md").write_text("# step detail\n", encoding="utf-8")

    rc = cmd_annotate(_ns(src, archive=True), invoker=_recording_stub())
    assert rc == 0
    assert not src.exists()  # original moved
    archived = tmp_path / "archive" / "2-old-plan.replaced.md"
    assert archived.is_file()
    notice = archived.read_text(encoding="utf-8")
    assert "2-old-plan.annotated.md" in notice  # notice points at the report
    # The sibling plan-details bundle is co-archived.
    assert (tmp_path / "archive" / "plan-details" / "old-plan" / "1-step.md").is_file()
    assert not bundle.exists()


def test_archive_collision_uses_numbered_replacement(tmp_path: Path) -> None:
    src = _write_source(tmp_path, name="2-old-plan.md")
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (archive_dir / "2-old-plan.replaced.md").write_text(
        "preexisting", encoding="utf-8"
    )

    rc = cmd_annotate(_ns(src, archive=True), invoker=_recording_stub())

    assert rc == 0
    archived = archive_dir / "2-old-plan.replaced.1.md"
    assert archived.is_file()
    assert not src.exists()
    assert "2-old-plan.annotated.md" in archived.read_text(encoding="utf-8")


def test_no_archive_leaves_original(tmp_path: Path) -> None:
    src = _write_source(tmp_path)
    cmd_annotate(_ns(src), invoker=_recording_stub())
    assert src.is_file()  # untouched


def test_archive_registered_source_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_source(tmp_path, name="3-registered.md")
    manifest = tmp_path / ".plan-tool" / "plans.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"plans": [src.name]}), encoding="utf-8"
    )
    rc = cmd_annotate(
        _ns(src, repo_root=tmp_path, archive=True), invoker=_recording_stub()
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "plans.json" in err
    assert not src.exists()  # archive still proceeds


def test_archive_failure_marks_annotation_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = _write_source(tmp_path)

    def fake_archive_existing_source(*args, **kwargs) -> ArchiveResult:
        result = ArchiveResult()
        result.skipped.append("could not archive source")
        return result

    monkeypatch.setattr(
        annotate_cmd, "archive_existing_source", fake_archive_existing_source
    )

    rc = cmd_annotate(_ns(src, archive=True), invoker=_recording_stub())

    assert rc == 1
    assert src.is_file()
    assert (tmp_path / "plan.annotated.md").is_file()
    assert "could not archive source" in capsys.readouterr().err


def test_archive_unregistered_source_no_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_source(tmp_path, name="4-loose.md")
    (tmp_path / ".plan-tool").mkdir()
    cmd_annotate(
        _ns(src, repo_root=tmp_path, archive=True), invoker=_recording_stub()
    )
    assert "plans.json" not in capsys.readouterr().err


def test_all_implemented_emits_no_forward_work_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_source(tmp_path)
    all_done = [
        {"heading": h, "status": "IMPLEMENTED", "evidence": "done",
         "code_refs": ["x.py:1"]}
        for h in ("Goal A", "Feature B", "Feature C")
    ]
    rc = cmd_annotate(_ns(src), invoker=_recording_stub(all_done))
    assert rc == 0
    assert (tmp_path / "plan.annotated.md").is_file()
    assert (tmp_path / "plan.seed.md").is_file()
    out = capsys.readouterr().out
    assert "no remaining work" in out
    assert "plan.annotated.md" in out


def test_non_terminal_omits_no_forward_work_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_source(tmp_path)
    cmd_annotate(_ns(src), invoker=_recording_stub())  # has a NOT-IMPLEMENTED
    assert "no remaining work" not in capsys.readouterr().out


def test_console_summary_includes_grounding_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _write_source(tmp_path)
    rc = cmd_annotate(_ns(src), invoker=_recording_stub())
    assert rc == 0
    out = capsys.readouterr().out
    assert "grounded_files=3" in out
    assert "candidate_text_files=3" in out
    assert "skipped_or_unreadable=0" in out


def test_low_grounding_report_and_seed_surface_review_required_work(
    tmp_path: Path,
) -> None:
    src = tmp_path / "plan.md"
    src.write_text(_SOURCE_TEXT, encoding="utf-8")
    rc = cmd_annotate(_ns(src), invoker=_recording_stub())
    assert rc == 0
    report = (tmp_path / "plan.annotated.md").read_text(encoding="utf-8")
    seed = (tmp_path / "plan.seed.md").read_text(encoding="utf-8")
    assert "**Low grounding (0 files)**" in report
    assert "Goal A" in seed
    assert "[NEEDS-REVIEW]" in seed
    assert "[PARTIAL — review-required remaining]" in seed


def test_unparseable_response_returns_1(tmp_path: Path) -> None:
    src = _write_source(tmp_path)
    rc = cmd_annotate(_ns(src), invoker=lambda prompt: "")
    assert rc == 1
    assert not (tmp_path / "plan.annotated.md").exists()


def test_missing_source_returns_1(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    rc = cmd_annotate(_ns(missing), invoker=_recording_stub())
    assert rc == 1
    assert not (tmp_path / "nope.annotated.md").exists()


def test_real_invoker_is_default_seam() -> None:
    assert (
        annotate_cmd.shell_annotate_invoker
        is annotate_module.shell_annotate_invoker
    )
