"""Characterization tests for the state-management command helpers.

Pins the small, pure helpers behind ``checkpoint`` / ``runs`` /
``lessons consolidate`` — argument validators, run-log readers, the
``runs profile`` call-sample aggregation, and the lessons-consolidate
summary/diff renderers — so the "split cli.py into an intent-grouped
package" refactor can relocate them without changing what they parse,
compute, or print. The ``cmd_*`` handlers are directly covered by the
legacy suite (``test_cli.py``); per ``tests/cli/COVERAGE_BASELINE.md`` the
helpers exercised here are the ``indirectly covered`` ones.

Split-proof conventions (see ``test_package_surface.py``): every symbol is
imported from ``plan_tool.cli`` and called directly on temp-file inputs or
plain data objects; no ``plan_tool.cli`` module global is
``monkeypatch.setattr``\\ed. Run-log fixtures are written as JSONL so the
readers exercise their real parse path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from plan_tool.cli import (
    _CallSample,
    _aggregate_run_for_diff,
    _group_samples,
    _is_run_evictable,
    _iter_call_samples,
    _iter_events,
    _load_events_with_skips,
    _parse_duration_arg,
    _parse_runs_target,
    _print_consolidate_summary,
    _recurrence_annotation,
    _render_lessons_unified_diff,
    _safe_under_root,
    _summarize_group,
    _summarize_run_log,
    _validate_checkpoint_arg,
)
from plan_tool.lessons import (
    EquivalenceFinding,
    EquivalenceFindings,
    EquivalenceKind,
    LessonEntry,
    LessonsFile,
)


def _write_jsonl(path: Path, events: list[Any]) -> Path:
    """Write ``events`` (dicts or raw strings) one per line as a JSONL file."""
    lines = [e if isinstance(e, str) else json.dumps(e) for e in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _sample(**over: Any) -> _CallSample:
    """Build a :class:`_CallSample` with sensible, overridable defaults."""
    base: dict[str, Any] = dict(
        plan_slug="plan",
        run_id="run-1",
        run_started_at="2026-01-01T00:00:00Z",
        step_id=1,
        attempt=1,
        phase="step-1",
        mode="run",
        duration_ms=100,
        rc=0,
        tokens_input=None,
        tokens_output=None,
        cache_creation_tokens=None,
        cache_read_tokens=None,
        cost_usd=None,
        incomplete=False,
    )
    base.update(over)
    return _CallSample(**base)


class TestValidateCheckpointArg:
    def test_valid_value_returns_none(self) -> None:
        assert _validate_checkpoint_arg("my-plan", kind="slug") is None

    @pytest.mark.parametrize(
        "value",
        ["", "a/b", "a\\b", "..", "a..b", ".hidden", "."],
    )
    def test_traversal_shapes_rejected(self, value: str) -> None:
        assert _validate_checkpoint_arg(value, kind="slug") is not None

    def test_error_message_names_the_kind(self) -> None:
        assert _validate_checkpoint_arg("", kind="name") == "name cannot be empty"


class TestSafeUnderRoot:
    def test_descendant_is_safe(self, tmp_path: Path) -> None:
        assert _safe_under_root(tmp_path / "a" / "b.json", tmp_path) is True

    def test_sibling_is_not_safe(self, tmp_path: Path) -> None:
        (tmp_path / "root").mkdir()
        (tmp_path / "other").mkdir()
        assert _safe_under_root(tmp_path / "other" / "x", tmp_path / "root") is False


class TestParseDurationArg:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("30d", 30 * 86400),
            ("48h", 48 * 3600),
            ("90m", 90 * 60),
            ("45s", 45),
            ("3600", 3600),
            ("0", 0),
        ],
    )
    def test_valid_durations(self, value: str, expected: int) -> None:
        assert _parse_duration_arg(value) == expected

    @pytest.mark.parametrize("value", ["", "abc", "-5", "-5d", "10x", "1.5h"])
    def test_garbage_returns_none(self, value: str) -> None:
        assert _parse_duration_arg(value) is None


class TestParseRunsTarget:
    def test_slug_and_run_id_split(self) -> None:
        assert _parse_runs_target("my-plan/run-9") == ("my-plan", "run-9", None)

    def test_trailing_jsonl_suffix_stripped(self) -> None:
        assert _parse_runs_target("my-plan/run-9.jsonl") == (
            "my-plan",
            "run-9",
            None,
        )

    def test_only_first_slash_splits(self) -> None:
        assert _parse_runs_target("my-plan/a/b") == ("my-plan", "a/b", None)

    def test_missing_slash_returns_error(self) -> None:
        slug, run_id, err = _parse_runs_target("no-slash")
        assert slug is None and run_id is None
        assert err is not None and "requires <slug>/<run_id>" in err


class TestIsRunEvictable:
    def test_none_cutoff_always_evictable(self, tmp_path: Path) -> None:
        # Full wipe: even a file with no run_start is evictable.
        path = _write_jsonl(tmp_path / "r.jsonl", [{"event": "other"}])
        assert _is_run_evictable(path, None) is True

    def test_old_run_start_exceeds_ttl(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [{"event": "run_start", "ts": "2000-01-01T00:00:00+00:00"}],
        )
        assert _is_run_evictable(path, cutoff_seconds=10) is True

    def test_recent_run_start_under_ttl(self, tmp_path: Path) -> None:
        now = datetime.now(timezone.utc).isoformat()
        path = _write_jsonl(
            tmp_path / "r.jsonl", [{"event": "run_start", "ts": now}]
        )
        assert _is_run_evictable(path, cutoff_seconds=3600) is False

    def test_no_run_start_under_ttl_not_evictable(self, tmp_path: Path) -> None:
        path = _write_jsonl(tmp_path / "r.jsonl", [{"event": "phase_start"}])
        assert _is_run_evictable(path, cutoff_seconds=10) is False

    def test_missing_file_under_ttl_not_evictable(self, tmp_path: Path) -> None:
        assert _is_run_evictable(tmp_path / "gone.jsonl", cutoff_seconds=10) is False


class TestIterEvents:
    def test_skips_blank_bad_json_and_non_dict_lines(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [
                {"event": "a"},
                "",
                "{not json",
                "[1, 2, 3]",  # valid JSON, but not a dict
                {"event": "b"},
            ],
        )
        events = list(_iter_events(path))
        assert [e["event"] for e in events] == ["a", "b"]

    def test_partial_trailing_line_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "r.jsonl"
        path.write_text(
            json.dumps({"event": "a"}) + '\n{"event": "b"', encoding="utf-8"
        )
        assert [e["event"] for e in _iter_events(path)] == ["a"]


class TestLoadEventsWithSkips:
    def test_counts_damaged_lines_but_not_blanks(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [
                {"event": "a"},
                "",  # blank — not a skip
                "{broken",  # skip
                "42",  # non-dict — skip
                {"event": "b"},
            ],
        )
        events, skipped = _load_events_with_skips(path)
        assert [e["event"] for e in events] == ["a", "b"]
        assert skipped == 2


class TestSummarizeRunLog:
    def test_full_log_pulls_headline_fields(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [
                {
                    "event": "run_start",
                    "command": "run",
                    "plan_slug": "my-plan",
                    "ts": "2026-01-01T00:00:00Z",
                },
                {
                    "event": "claude_call_end",
                    "tokens_input": 100,
                    "tokens_output": 40,
                },
                {"event": "run_end", "duration_ms": 1234},
            ],
        )
        summary = _summarize_run_log(path)
        assert summary["command"] == "run"
        assert summary["plan_slug"] == "my-plan"
        assert summary["started_at"] == "2026-01-01T00:00:00Z"
        assert summary["duration"] == "1234ms"
        assert summary["event_count"] == 3
        assert summary["tokens_total"] == 140
        assert summary["unreadable"] is False

    def test_no_run_end_is_in_flight(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl", [{"event": "run_start", "command": "run"}]
        )
        summary = _summarize_run_log(path)
        assert summary["duration"] == "in-flight"
        assert summary["tokens_total"] is None

    def test_unreadable_file_flagged(self, tmp_path: Path) -> None:
        summary = _summarize_run_log(tmp_path / "gone.jsonl")
        assert summary["unreadable"] is True


class TestAggregateRunForDiff:
    def test_per_phase_aggregation_and_schema(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [
                {"event": "run_start", "schema_version": 7},
                {"event": "phase_start", "phase": "step-1", "mode": "run"},
                {
                    "event": "claude_call_start",
                    "phase": "step-1",
                    "attempt": 1,
                },
                {
                    "event": "claude_call_end",
                    "phase": "step-1",
                    "attempt": 1,
                    "tokens_input": 100,
                    "tokens_output": 50,
                },
                {"event": "phase_end", "phase": "step-1", "duration_ms": 1500},
            ],
        )
        agg = _aggregate_run_for_diff(path)
        assert agg["__schema__"] == {"schema_version": 7}
        step = agg["step-1"]
        assert step["wall_ms"] == 1500
        assert step["claude_call_count"] == 1
        assert step["tokens_in"] == 100
        assert step["tokens_out"] == 50
        assert step["tokens_seen"] is True

    def test_open_phase_contributes_zero_wall(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [{"event": "phase_start", "phase": "open"}],
        )
        agg = _aggregate_run_for_diff(path)
        assert agg["open"]["wall_ms"] == 0

    def test_unmatched_phase_end_skipped(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [{"event": "phase_end", "phase": "ghost", "duration_ms": 9}],
        )
        agg = _aggregate_run_for_diff(path)
        assert "ghost" not in agg


class TestIterCallSamples:
    def test_pairs_start_and_end_carrying_step_and_mode(
        self, tmp_path: Path
    ) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [
                {"event": "run_start", "run_id": "abc", "ts": "2026-01-01T00:00:00Z"},
                {"event": "phase_start", "phase": "step-1", "mode": "run"},
                {
                    "event": "claude_call_start",
                    "phase": "step-1",
                    "attempt": 1,
                    "step_id": 3,
                },
                {
                    "event": "claude_call_end",
                    "phase": "step-1",
                    "attempt": 1,
                    "duration_ms": 800,
                    "rc": 0,
                    "tokens_input": 10,
                    "tokens_output": 5,
                    "cost_usd": 0.02,
                },
            ],
        )
        samples = _iter_call_samples(path, plan_slug="my-plan")
        assert len(samples) == 1
        s = samples[0]
        assert s.plan_slug == "my-plan"
        assert s.run_id == "abc"
        assert s.step_id == 3
        assert s.mode == "run"
        assert s.duration_ms == 800
        assert s.cost_usd == pytest.approx(0.02)
        assert s.incomplete is False

    def test_unmatched_start_is_incomplete(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [
                {"event": "phase_start", "phase": "step-1", "mode": "run"},
                {
                    "event": "claude_call_start",
                    "phase": "step-1",
                    "attempt": 1,
                    "step_id": 1,
                },
            ],
        )
        samples = _iter_call_samples(path, plan_slug="p")
        assert len(samples) == 1
        assert samples[0].incomplete is True
        assert samples[0].duration_ms is None

    def test_orphan_end_is_skipped(self, tmp_path: Path) -> None:
        path = _write_jsonl(
            tmp_path / "r.jsonl",
            [{"event": "claude_call_end", "phase": "step-1", "attempt": 1}],
        )
        assert _iter_call_samples(path, plan_slug="p") == []


class TestGroupSamples:
    def test_by_mode_buckets_with_question_fallback(self) -> None:
        groups = _group_samples(
            [_sample(mode="run"), _sample(mode=None)], by="mode"
        )
        assert set(groups) == {"run", "?"}

    def test_by_step_prefixes_with_slug(self) -> None:
        groups = _group_samples(
            [_sample(plan_slug="p", step_id=2), _sample(plan_slug="p", step_id=None)],
            by="step",
        )
        assert set(groups) == {"p#2", "p#?"}

    def test_by_run_uses_slug_and_run_id(self) -> None:
        groups = _group_samples(
            [_sample(plan_slug="p", run_id="r9")], by="run"
        )
        assert set(groups) == {"p/r9"}


class TestSummarizeGroup:
    def test_small_bucket_suppresses_quantiles_but_keeps_min_max(self) -> None:
        samples = [_sample(duration_ms=d) for d in (100, 200, 300)]
        summ = _summarize_group(samples, include_incomplete=False)
        assert summ["count"] == 3
        assert summ["p50_ms"] is None
        assert summ["p95_ms"] is None
        assert summ["mean_ms"] == pytest.approx(200.0)
        assert summ["total_ms"] == 600
        assert summ["min_ms"] == 100
        assert summ["max_ms"] == 300

    def test_large_bucket_emits_quantiles(self) -> None:
        samples = [_sample(duration_ms=d) for d in (100, 200, 300, 400, 500)]
        summ = _summarize_group(samples, include_incomplete=False)
        assert summ["p50_ms"] == pytest.approx(300.0)
        assert summ["p95_ms"] is not None and summ["p95_ms"] >= 400

    def test_fail_and_incomplete_counted(self) -> None:
        samples = [
            _sample(rc=0),
            _sample(rc=1),  # failed
            _sample(incomplete=True, rc=None, duration_ms=None),
        ]
        summ = _summarize_group(samples, include_incomplete=False)
        assert summ["count"] == 3
        assert summ["fail"] == 1
        assert summ["incomplete"] == 1

    def test_token_columns_none_when_never_recorded(self) -> None:
        summ = _summarize_group([_sample()], include_incomplete=False)
        assert summ["tokens_input"] is None
        assert summ["tokens_output"] is None

    def test_token_columns_sum_present_values(self) -> None:
        samples = [
            _sample(tokens_input=10, tokens_output=4),
            _sample(tokens_input=20, tokens_output=6),
        ]
        summ = _summarize_group(samples, include_incomplete=False)
        assert summ["tokens_input"] == 30
        assert summ["tokens_output"] == 10


class TestRecurrenceAnnotation:
    @pytest.mark.parametrize(
        "weight, expected",
        [(1.0, ""), (2.0, " recurrence=1"), (3.0, " recurrence=2")],
    )
    def test_annotation_text(self, weight: float, expected: str) -> None:
        assert _recurrence_annotation(weight) == expected


class TestRenderLessonsUnifiedDiff:
    def test_diff_names_repo_relative_paths(self, tmp_path: Path) -> None:
        path = tmp_path / "general.md"
        diff = _render_lessons_unified_diff(
            path, "old line\n", "new line\n", repo_root=tmp_path
        )
        assert "a/general.md" in diff
        assert "b/general.md" in diff
        assert "-old line" in diff
        assert "+new line" in diff


class TestPrintConsolidateSummary:
    @staticmethod
    def _per_file(tmp_path: Path):
        entries = [LessonEntry(rule="always lint"), LessonEntry(rule="run the linter")]
        findings = EquivalenceFindings(
            duplicates=(
                EquivalenceFinding(
                    kind=EquivalenceKind.DUPLICATE,
                    left_index=1,
                    right_index=2,
                    confidence=0.9,
                    rationale="same idea",
                ),
            ),
            conflicts=(
                EquivalenceFinding(
                    kind=EquivalenceKind.CONFLICT,
                    left_index=1,
                    right_index=2,
                    confidence=0.7,
                    rationale="contradicts",
                ),
            ),
        )
        f = LessonsFile(path=tmp_path / "general.md", kind="general")
        return [(f, entries, findings)]

    def test_header_and_bullets_without_recurrence(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _print_consolidate_summary(
            self._per_file(tmp_path), repo_root=tmp_path, recurrence=None
        )
        out = capsys.readouterr().out
        assert (
            "### general.md · kind=general · 2 entries · "
            "1 duplicates · 1 conflicts" in out
        )
        assert "DUP[0.90] #1 ↔ #2" in out
        assert "(will drop #2)" in out
        assert "CONFLICT[0.70] #1 ↔ #2" in out
        assert "(manual review required)" in out
        # No recurrence map → no recurrence= annotation.
        assert "recurrence=" not in out

    def test_recurrence_annotation_appended_when_counts_present(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The warning log records (candidate_lower, prior_lower); the duplicate
        # maps right_index→"run the linter", left_index→"always lint".
        recurrence = {("run the linter", "always lint"): 2}
        _print_consolidate_summary(
            self._per_file(tmp_path), repo_root=tmp_path, recurrence=recurrence
        )
        out = capsys.readouterr().out
        assert "recurrence=2" in out
