"""CLI tests for the ``bench`` command — drive ``main(["bench", ...])``.

Split-proof: every test drives the CLI through ``main(argv)`` against a temp
repo (``conftest.CliRepo``) and inspects the on-disk records / stdout, never
patching a ``plan_tool.cli`` module global. The real-binary path is exercised
to prove the repo-root subprocess guard blocks it (no fake invoker is injected
through the CLI surface).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import plan_tool.cli as cli
from plan_tool import bench
from plan_tool.backend import CLAUDE_BACKEND, set_active_backend
from plan_tool.bench import BenchTrialRecord


@pytest.fixture(autouse=True)
def _restore_active_backend():
    """Reset the process-global active backend after each test.

    The bench engine mutates the active backend per trial; reset so a
    selection can't leak across tests.
    """
    yield
    set_active_backend(CLAUDE_BACKEND)


def _stub_corpus(root: Path, seeds: int = 1) -> Path:
    """Write a minimal proposal-only corpus and return its root."""
    proposal = root / "corpus" / "proposal"
    proposal.mkdir(parents=True, exist_ok=True)
    for i in range(seeds):
        (proposal / f"seed-stub{i}.md").write_text(
            f"# Stub seed {i}\n\n## Request\nAdd small feature {i}.\n",
            encoding="utf-8",
        )
    return root / "corpus"


def _records(repo_root: Path, stamp: str) -> list[dict]:
    path = repo_root / ".plan-tool" / "bench" / "runs" / stamp / "records.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _stub_cell_trials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI wiring tests independent of benchmark trial execution."""

    def fake_trial(family, cell, backend_name, trial, *, stamp, **_kwargs):
        return BenchTrialRecord(
            family=family.name,
            cell_id=cell.cell_id,
            backend=backend_name,
            trial=trial,
            stamp=stamp,
            wall_clock_ms=0,
            tokens_input=None,
            tokens_output=None,
            cache_creation_tokens=None,
            cache_read_tokens=None,
            cost_usd=None,
            failure_kind=None,
            retries=0,
            exit_or_verdict=0,
            raw_output="",
        )

    monkeypatch.setattr(bench, "_run_cell_trial", fake_trial)


def test_bench_run_creates_run_dir_and_records(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _stub_corpus(tmp_repo.root, seeds=1)
    _stub_cell_trials(monkeypatch)
    rc = cli.main(
        tmp_repo.argv(
            "bench", "run",
            "--families", "proposal",
            "--backends", "claude",
            "--trials", "1",
            "--stamp", "s1",
            "--corpus-root", str(corpus),
        )
    )
    assert rc == 0
    assert _records(tmp_repo.root, "s1")  # one record per cell trial


def test_bench_run_forwards_selection_flags(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _stub_corpus(tmp_repo.root, seeds=1)
    _stub_cell_trials(monkeypatch)
    rc = cli.main(
        tmp_repo.argv(
            "bench", "run",
            "--families", "proposal",
            "--backends", "claude",
            "--trials", "2",
            "--stamp", "s1",
            "--corpus-root", str(corpus),
        )
    )
    assert rc == 0
    records = _records(tmp_repo.root, "s1")
    assert {r["family"] for r in records} == {"proposal"}
    assert {r["backend"] for r in records} == {"claude"}
    assert {r["trial"] for r in records} == {1, 2}


def test_bench_run_resume_default_skips_completed(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _stub_corpus(tmp_repo.root, seeds=1)
    _stub_cell_trials(monkeypatch)
    argv = tmp_repo.argv(
        "bench", "run",
        "--families", "proposal",
        "--backends", "claude",
        "--trials", "1",
        "--stamp", "s1",
        "--corpus-root", str(corpus),
    )
    assert cli.main(argv) == 0
    first = len(_records(tmp_repo.root, "s1"))
    assert cli.main(argv) == 0
    second = len(_records(tmp_repo.root, "s1"))
    assert first == second  # resume added no new records


def _run_proposal_stub(
    tmp_repo, corpus: Path, monkeypatch: pytest.MonkeyPatch, stamp: str = "s1"
) -> None:
    """Drive a one-cell proposal matrix so a report has records to render."""
    _stub_cell_trials(monkeypatch)
    assert cli.main(
        tmp_repo.argv(
            "bench", "run",
            "--families", "proposal",
            "--backends", "claude",
            "--trials", "1",
            "--stamp", stamp,
            "--corpus-root", str(corpus),
        )
    ) == 0


def test_bench_report_markdown_default(
    tmp_repo, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _stub_corpus(tmp_repo.root, seeds=1)
    _run_proposal_stub(tmp_repo, corpus, monkeypatch)
    capsys.readouterr()  # drop run output
    rc = cli.main(
        tmp_repo.argv("bench", "report", "--stamp", "s1", "--corpus-root", str(corpus))
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "proposal" in out
    assert "claude" in out
    assert "quality" in out


def test_bench_report_json_format(
    tmp_repo, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _stub_corpus(tmp_repo.root, seeds=1)
    _run_proposal_stub(tmp_repo, corpus, monkeypatch)
    capsys.readouterr()
    rc = cli.main(
        tmp_repo.argv(
            "bench", "report", "--stamp", "s1",
            "--format", "json", "--corpus-root", str(corpus),
        )
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "cells" in payload
    assert "run_meta" in payload
    assert {c["family"] for c in payload["cells"]} == {"proposal"}


def test_bench_report_write_recommendations(
    tmp_repo, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _stub_corpus(tmp_repo.root, seeds=1)
    _run_proposal_stub(tmp_repo, corpus, monkeypatch)
    capsys.readouterr()
    rc = cli.main(
        tmp_repo.argv(
            "bench", "report", "--stamp", "s1",
            "--write-recommendations", "--corpus-root", str(corpus),
        )
    )
    assert rc == 0
    doc_path = tmp_repo.root / "docs" / "BACKEND_RECOMMENDATIONS.md"
    assert doc_path.is_file()
    text = doc_path.read_text(encoding="utf-8")
    assert "do not edit directly" in text
    assert "## proposal" in text  # one recommendation section per family
    assert str(doc_path) in capsys.readouterr().out


def test_bench_report_unknown_stamp_errors(
    tmp_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(tmp_repo.argv("bench", "report", "--stamp", "does-not-exist"))
    assert rc == 1
    assert "no bench run" in capsys.readouterr().err


def test_bench_in_help_and_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "80")
    help_text = cli.build_parser().format_help()
    assert "bench" in help_text
    assert callable(getattr(cli, "cmd_bench", None))


def test_bench_run_blocked_from_real_binary(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no fake invoker, the subprocess guard blocks a real backend spawn.

    ``shutil.which`` is forced to resolve so the production invoker reaches
    ``subprocess`` — where the repo-root guard intercepts it. The blocked
    attempt is recorded; no real backend runs.
    """
    monkeypatch.setattr(shutil, "which", lambda binary: f"/usr/bin/{binary}")
    # Reuse the real implementation corpus so run_step reaches the invoker.
    repo_corpus = Path(__file__).resolve().parents[2] / "benchmarks" / "corpus"
    rc = cli.main(
        tmp_repo.argv(
            "bench", "run",
            "--families", "implementation",
            "--backends", "claude",
            "--trials", "1",
            "--stamp", "s1",
            "--corpus-root", str(repo_corpus),
        )
    )
    assert rc == 0
    records = _records(tmp_repo.root, "s1")
    assert records
    # The guard fired (its hint mentions spawning the real CLI) — proof the
    # engine attempted the production path and a real call was blocked.
    assert any("spawn the real" in r["raw_output"] for r in records)
