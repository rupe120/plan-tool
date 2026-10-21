"""Tests for the distill first-pass: seed reorganization + multi-plan split.

Covers the pure parse/validate/render helpers, the
``propose_distilled_seed_from_claude`` round-trip (checkpoint, repair retry,
refusal), the ``create_plan`` threading (single-plan rebinds the seed and
subsumes body synthesis; multi-plan short-circuits to a split proposal), and
the CLI surface (split proposal saved + exit 0, distilled artifact archived).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

import pytest

from plan_tool import create as create_module
from plan_tool.create import (
    CreateError,
    DirectSplitAssessment,
    DistillOutcome,
    DroppedReference,
    FileBackedSourceRoute,
    SplitProposal,
    SplitProposalEntry,
    _parse_direct_split_assessment_json,
    _canonical_seed_covers_all,
    _clamp_line_range,
    _distill_seed_input_hash,
    _direct_assessment_input_hash,
    _parse_distill_json,
    _render_distilled_markdown,
    _render_numbered_source,
    _validate_distilled_sections,
    _validate_split_plans,
    assess_direct_source_split_from_claude,
    create_plan,
    extract_h2_sections,
    find_dropped_references,
    propose_distilled_seed_from_claude,
)

_SECTION_KEYS = [
    "Overview",
    "Problem statement",
    "Architecture",
    "Out of scope",
    "Risks",
    "Testing",
    "Acceptance criteria",
    "Deferred",
]


def _single_json(filled: Optional[list[str]] = None) -> str:
    filled = _SECTION_KEYS if filled is None else filled
    evidence_keys = [key for key in _SECTION_KEYS if key not in {
        "Overview", "Problem statement", "Architecture"
    }]
    return json.dumps(
        {
            "outcome": "single",
            "sections": {
                k: (
                    f"{k} body — see `src/app.py`."
                    if k in filled or k in {"Overview", "Problem statement", "Architecture"}
                    else None
                )
                for k in _SECTION_KEYS
            },
            "evidence_spans": {
                key: ([{"start_line": 1, "end_line": 1}] if key in filled else None)
                for key in evidence_keys
            },
        }
    )


def _split_json(entries: list[dict]) -> str:
    return json.dumps({"outcome": "split", "plans": entries})


_TWO_PLANS = [
    {
        "title": "OAuth login",
        "suggested_slug": "oauth-login",
        "rationale": "auth surface",
        "start_line": 1,
        "end_line": 3,
    },
    {
        "title": "Billing queue",
        "suggested_slug": "billing-queue",
        "rationale": "infra",
        "start_line": 4,
        "end_line": 6,
    },
]


def _router(
    distill_resp: str,
    *,
    steps: str = '[{"title": "Do it", "files": ["src/app.py"], "depends_on": []}]',
    refs: str = '[{"title": "D", "url": "https://e.com", "description": "d"}]',
    body: Optional[str] = None,
    counters: Optional[dict] = None,
) -> Callable[[str], str]:
    """Build a fake claude invoker that routes by prompt content."""
    body = body if body is not None else json.dumps({k: None for k in _SECTION_KEYS})

    def invoke(prompt: str) -> str:
        if "Distill a free-form seed" in prompt:
            if counters is not None:
                counters["distill"] = counters.get("distill", 0) + 1
            return distill_resp
        if "developer and API reference documentation" in prompt:
            return refs
        if "Synthesize plan body sections" in prompt:
            if counters is not None:
                counters["body"] = counters.get("body", 0) + 1
            return body
        if counters is not None:
            counters["steps"] = counters.get("steps", 0) + 1
        return steps

    return invoke


def _repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    (tmp_path / ".git").mkdir()
    out_dir = tmp_path / "plans"
    out_dir.mkdir()
    return tmp_path, out_dir, tmp_path / "m.json"


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


class TestDistillHelpers:
    def test_render_numbered_source(self) -> None:
        assert _render_numbered_source("a\nb\nc") == "1\ta\n2\tb\n3\tc"

    def test_direct_split_assessment_accepts_only_single_or_valid_shared_split(self) -> None:
        single, single_error = _parse_direct_split_assessment_json(
            '{"outcome":"single"}', total_lines=6
        )
        split, split_error = _parse_direct_split_assessment_json(
            _split_json(_TWO_PLANS), total_lines=6
        )
        replacement, replacement_error = _parse_direct_split_assessment_json(
            '{"outcome":"single","sections":{"Overview":"replacement"}}',
            total_lines=6,
        )
        malformed, malformed_error = _parse_direct_split_assessment_json(
            '{"outcome":"split","plans":[{}]}', total_lines=6
        )

        assert single is not None and single.is_single and single_error is None
        assert split is not None and split.is_split and split_error is None
        assert replacement is None and "replacement" in (replacement_error or "")
        assert malformed is None and "requires >= 2" in (malformed_error or "")

    @pytest.mark.parametrize(
        "start,end,total,expected",
        [
            (1, 3, 10, (1, 3)),
            (0, 99, 10, (1, 10)),  # clamped to [1, 10]
            (5, 2, 10, (None, None)),  # inverted
            ("x", 3, 10, (None, None)),  # non-int
            (True, 3, 10, (None, None)),  # bool is not a valid int here
            (1, 3, 0, (None, None)),  # empty seed
        ],
    )
    def test_clamp_line_range(self, start, end, total, expected) -> None:
        assert _clamp_line_range(start, end, total) == expected

    def test_validate_sections_missing_key(self) -> None:
        out, err = _validate_distilled_sections({"Overview": "x"})
        assert out is None and "missing canonical section keys" in err

    def test_validate_sections_extra_key(self) -> None:
        secs = {k: None for k in _SECTION_KEYS}
        secs["Steps"] = "nope"
        out, err = _validate_distilled_sections(secs)
        assert out is None and "not allowed" in err

    def test_validate_sections_rejects_empty_derived_section(self) -> None:
        secs = {k: None for k in _SECTION_KEYS}
        secs["Overview"] = "   "
        out, err = _validate_distilled_sections(secs)
        assert out is None and "derived section" in err

    def test_validate_split_requires_two(self) -> None:
        out, err = _validate_split_plans([_TWO_PLANS[0]], total_lines=10)
        assert out is None and ">= 2" in err

    def test_render_distilled_markdown_skips_null_and_orders(self) -> None:
        md = _render_distilled_markdown(
            {"Architecture": "arch", "Overview": "ov", "Risks": None}
        )
        # Canonical order: Overview before Architecture; Risks (null) omitted.
        assert md.index("## Overview") < md.index("## Architecture")
        assert "## Risks" not in md

    def test_render_distilled_markdown_empty(self) -> None:
        assert _render_distilled_markdown({k: None for k in _SECTION_KEYS}) == ""

    def test_input_hash_pivots_on_seed(self, tmp_path: Path) -> None:
        h1 = _distill_seed_input_hash("s", "seed a", tmp_path, tmp_path)
        h2 = _distill_seed_input_hash("s", "seed b", tmp_path, tmp_path)
        assert h1 != h2
        assert h1 == _distill_seed_input_hash("s", "seed a", tmp_path, tmp_path)


class TestParseDistillJson:
    @staticmethod
    def _source(total_lines: int) -> str:
        return "\n".join("source fact" for _ in range(total_lines))

    def test_single(self) -> None:
        out, err = _parse_distill_json(
            _single_json(["Overview"]),
            source_text=self._source(10),
            total_lines=10,
        )
        assert err is None and out.is_normalized
        assert "## Overview" in out.distilled

    def test_split_clamps_ranges(self) -> None:
        entries = [
            {**_TWO_PLANS[0], "end_line": 999},
            _TWO_PLANS[1],
        ]
        out, err = _parse_distill_json(
            _split_json(entries), source_text=self._source(6), total_lines=6
        )
        assert err is None and out.is_split
        assert out.split[0].end_line == 6  # clamped

    def test_single_entry_split_rejected(self) -> None:
        out, err = _parse_distill_json(
            _split_json([_TWO_PLANS[0]]),
            source_text=self._source(10),
            total_lines=10,
        )
        assert out is None and ">= 2" in err

    def test_missing_derived_section_rejected(self) -> None:
        response = json.loads(_single_json([]))
        response["sections"]["Overview"] = None
        out, err = _parse_distill_json(
            json.dumps(response), source_text=self._source(10), total_lines=10
        )
        assert out is None and "derived section" in err

    def test_bad_outcome(self) -> None:
        out, err = _parse_distill_json(
            '{"outcome": "maybe"}', source_text=self._source(10), total_lines=10
        )
        assert out is None and "single" in err

    @pytest.mark.parametrize(
        "response",
        [
            '{"outcome":"single","sections":{},"evidence_spans":{},"plans":[]}',
            '{"outcome":"split","plans":[],"evidence_spans":{}}',
        ],
    )
    def test_parser_rejects_mixed_model_outcome_shapes(self, response: str) -> None:
        outcome, error = _parse_distill_json(
            response, source_text=self._source(10), total_lines=10
        )

        assert outcome is None and error is not None

    def test_non_json(self) -> None:
        out, err = _parse_distill_json(
            "not json", source_text=self._source(10), total_lines=10
        )
        assert out is None and "JSON object" in err

    def test_parser_rejects_normalized_json_with_surrounding_model_prose(self) -> None:
        outcome, error = _parse_distill_json(
            f"Here is the result:\n{_single_json()}\nThanks!",
            source_text=self._source(10),
            total_lines=10,
        )

        assert outcome is None
        assert error == "response must be one JSON object with no surrounding prose"

    def test_normalized_preparation_materializes_evidence_from_cited_source_lines(
        self,
    ) -> None:
        source = "Goal.\nActual risk from source.\n"
        response = json.loads(_single_json())
        response["sections"]["Risks"] = "invented model risk"
        response["evidence_spans"]["Risks"] = [
            {"start_line": 2, "end_line": 2}
        ]

        outcome, error = _parse_distill_json(
            json.dumps(response), source_text=source, total_lines=2
        )

        assert error is None and outcome is not None
        assert outcome.sections is not None
        assert outcome.sections["Risks"] == "Actual risk from source."
        assert outcome.evidence_spans is not None
        assert outcome.evidence_spans["Risks"] == ((2, 2),)

    def test_normalized_preparation_preserves_optional_context_from_source(
        self,
    ) -> None:
        source = (
            "Source fact.\n\n"
            "## Input\n\n"
            "Read `seed-state.json` and its `status` field.\n\n"
            "## Scope guardrails\n\n"
            "Keep the source lifecycle unchanged.\n"
        )
        response = json.loads(_single_json())
        response["sections"]["Input"] = "model replacement input"
        response["sections"]["Scope guardrails"] = "model replacement guardrail"

        outcome, error = _parse_distill_json(
            json.dumps(response), source_text=source, total_lines=9
        )

        assert error is None and outcome is not None
        assert outcome.sections is not None
        assert outcome.sections["Input"] == "Read `seed-state.json` and its `status` field."
        assert outcome.sections["Scope guardrails"] == "Keep the source lifecycle unchanged."
        assert "model replacement" not in (outcome.distilled or "")

    @pytest.mark.parametrize("section", ["Input", "Scope guardrails"])
    def test_normalized_preparation_rejects_fabricated_optional_context(
        self, section: str
    ) -> None:
        response = json.loads(_single_json())
        response["sections"][section] = "model-only optional context"
        if section == "Input":
            response["evidence_spans"]["Input"] = None

        outcome, error = _parse_distill_json(
            json.dumps(response), source_text=self._source(10), total_lines=10
        )

        assert outcome is None
        if section == "Input":
            assert error == "evidence spans for 'Input' must be a non-empty list"
        else:
            assert error == f"optional section {section!r} was not supplied by the raw source"

    def test_normalized_preparation_materializes_prose_backed_input(self) -> None:
        source = "The plan reads `seed-state.json` and its `status` field.\n"
        response = json.loads(_single_json())
        response["sections"]["Input"] = "model summary of the seed state contract"
        response["evidence_spans"]["Input"] = [
            {"start_line": 1, "end_line": 1}
        ]

        outcome, error = _parse_distill_json(
            json.dumps(response), source_text=source, total_lines=1
        )

        assert error is None and outcome is not None
        assert outcome.sections is not None
        assert outcome.sections["Input"] == source.strip()
        assert outcome.evidence_spans is not None
        assert outcome.evidence_spans["Input"] == ((1, 1),)

    @pytest.mark.parametrize(
        "spans",
        [
            [{"start_line": 2, "end_line": 2}],
            [
                {"start_line": 2, "end_line": 3},
                {"start_line": 3, "end_line": 3},
            ],
        ],
    )
    def test_normalized_preparation_rejects_heading_only_or_overlapping_evidence(
        self, spans: list[dict[str, int]]
    ) -> None:
        response = json.loads(_single_json())
        response["evidence_spans"]["Testing"] = spans

        outcome, error = _parse_distill_json(
            json.dumps(response),
            source_text="Source fact.\n## Testing\nTest body.\n",
            total_lines=3,
        )

        assert outcome is None and error is not None


# --------------------------------------------------------------------------
# propose_distilled_seed_from_claude
# --------------------------------------------------------------------------


class TestProposeDistilledSeed:
    def test_single_outcome(self) -> None:
        outcome = propose_distilled_seed_from_claude(
            "raw seed", _router(_single_json(["Overview"]))
        )
        assert outcome.is_normalized and "## Overview" in outcome.distilled

    def test_split_outcome(self) -> None:
        outcome = propose_distilled_seed_from_claude(
            "l1\nl2\nl3\nl4\nl5\nl6", _router(_split_json(_TWO_PLANS))
        )
        assert outcome.is_split and len(outcome.split) == 2

    def test_repair_retry_recovers(self) -> None:
        calls = {"n": 0}

        def invoke(prompt: str) -> str:
            calls["n"] += 1
            return "garbage" if calls["n"] == 1 else _single_json(["Overview"])

        outcome = propose_distilled_seed_from_claude("seed", invoke)
        assert calls["n"] == 2 and outcome.is_normalized

    def test_refusal_on_double_failure(self) -> None:
        outcome = propose_distilled_seed_from_claude("seed", lambda _p: "garbage")
        assert outcome.is_refused and outcome.reason

    def test_checkpoint_save_then_hit(self, tmp_path: Path) -> None:
        repo, out_dir, _ = _repo(tmp_path)
        calls = {"n": 0}

        def invoke(prompt: str) -> str:
            calls["n"] += 1
            return _single_json(["Overview"])

        kwargs = dict(slug="demo", output_dir=out_dir, repo_root=repo)
        first = propose_distilled_seed_from_claude("seed", invoke, **kwargs)
        assert first.is_normalized and calls["n"] == 1
        # Second call with the same seed hits the checkpoint — no new invoke.
        second = propose_distilled_seed_from_claude("seed", invoke, **kwargs)
        assert second.is_normalized and calls["n"] == 1

    def test_route_checkpoint_key_changes_with_prompt_or_result_contract(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, _ = _repo(tmp_path)
        source = "seed"
        original = _distill_seed_input_hash("demo", source, out_dir, repo)
        changed_prompt = _distill_seed_input_hash(
            "demo", source, out_dir, repo, rendered_prompt="changed prompt"
        )
        monkeypatch.setattr(create_module, "_DISTILL_RESULT_CONTRACT_REVISION", "next")
        changed_contract = _distill_seed_input_hash("demo", source, out_dir, repo)

        assert original != changed_prompt
        assert original != changed_contract

    def test_direct_assessment_checkpoint_cannot_satisfy_preparation(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.checkpoint import Checkpoint, checkpoint_path, save_checkpoint

        repo, out_dir, _ = _repo(tmp_path)
        source = "seed"
        direct_prompt = create_module._render_direct_split_assessment_prompt(source)
        direct_hash = _direct_assessment_input_hash(
            "demo", source, direct_prompt, out_dir, repo
        )
        direct_path = checkpoint_path(repo, "demo", "create-direct-assessment")
        preparation_path = checkpoint_path(repo, "demo", "create-distill-seed")
        save_checkpoint(
            direct_path,
            Checkpoint(
                input_hash=direct_hash,
                payload='{"outcome":"single"}',
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        calls = 0

        def invoke(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            return _single_json()

        outcome = propose_distilled_seed_from_claude(
            source, invoke, slug="demo", output_dir=out_dir, repo_root=repo
        )

        assert outcome.is_normalized and calls == 1
        assert direct_path.is_file() and preparation_path.is_file()

    def test_invalid_cached_preparation_response_is_discarded_and_repaired_once(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.checkpoint import Checkpoint, checkpoint_path, save_checkpoint

        repo, out_dir, _ = _repo(tmp_path)
        source = "seed"
        slug = "demo"
        input_hash = _distill_seed_input_hash(slug, source, out_dir, repo)
        cache_path = checkpoint_path(repo, slug, "create-distill-seed")
        save_checkpoint(
            cache_path,
            Checkpoint(
                input_hash=input_hash,
                payload="not valid JSON",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        calls = 0

        def invoke(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            return _single_json()

        outcome = propose_distilled_seed_from_claude(
            source, invoke, slug=slug, output_dir=out_dir, repo_root=repo
        )

        assert calls == 1
        assert outcome.is_normalized

    def test_invalid_cached_direct_assessment_is_discarded_and_refused(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.checkpoint import Checkpoint, checkpoint_path, save_checkpoint

        repo, out_dir, _ = _repo(tmp_path)
        source_text = _direct_file_seed()
        source = repo / "seed.md"
        source.write_text(source_text, encoding="utf-8")
        prompt = create_module._render_direct_split_assessment_prompt(source_text)
        input_hash = _direct_assessment_input_hash(
            "demo", source_text, prompt, out_dir, repo
        )
        cache_path = checkpoint_path(repo, "demo", "create-direct-assessment")
        save_checkpoint(
            cache_path,
            Checkpoint(
                input_hash=input_hash,
                payload="not valid JSON",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )

        result = create_plan(
            "demo",
            repo_root=repo,
            output_dir_override=out_dir,
            from_description=source_text,
            from_existing_path=source,
            yes=True,
            claude_invoker=lambda _prompt: (_ for _ in ()).throw(
                AssertionError("invalid direct cache must not invoke a repair")
            ),
        )

        assert result.file_backed_route is FileBackedSourceRoute.REFUSED
        assert result.plan_path is None
        assert not cache_path.exists()

    def test_direct_assessment_cache_rejects_invalid_payload_without_repair(
        self, tmp_path: Path
    ) -> None:
        """Keep the low-level direct contract fail-closed for standalone callers."""
        repo, out_dir, _ = _repo(tmp_path)
        calls = 0

        def invoke(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            return "not valid JSON"

        with pytest.raises(CreateError, match="no plan was written"):
            assess_direct_source_split_from_claude(
                "seed",
                invoke,
                slug="demo",
                output_dir=out_dir,
                repo_root=repo,
            )
        assert calls == 1


# --------------------------------------------------------------------------
# create_plan threading
# --------------------------------------------------------------------------

_SEED = (
    "Add a feature in `src/app.py`.\n\n# Messy\n\n" * 4
    + "\n## References\n\n- [App API](https://example.test/app-api)\n"
)


def _direct_file_seed() -> str:
    return "\n".join(
        f"## {section}\n\n{section} source text.\n" for section in _SECTION_KEYS
    ) + "\n## References\n\n- [App API](https://example.test/app-api)\n"


class TestFindDroppedReferences:
    def test_flags_runbook_and_section_absent_from_acceptance(self) -> None:
        # The exact failure shape that motivated the check: Risks points at
        # a runbook in "Section 7" that no acceptance criterion produces.
        md = (
            "## Risks\n\nThe runbook in Section 7 sequences the cutover.\n\n"
            "## Acceptance criteria\n\nDoc exists with seven H2s.\n"
        )
        refs = find_dropped_references(md)
        assert {r.keyword for r in refs} == {"runbook", "section"}
        assert all(r.section == "risks" for r in refs)
        assert any(r.anchor == "Section 7" for r in refs)

    def test_corroborated_reference_not_flagged(self) -> None:
        # Acceptance criteria mentions both the runbook and Section 7, so the
        # reference is pinned and must not be flagged.
        md = (
            "## Risks\n\nThe operator cutover runbook sequences the copy.\n\n"
            "## Acceptance criteria\n\nThe runbook is authored in Section 7.\n"
        )
        assert find_dropped_references(md) == []

    def test_one_finding_per_distinct_artifact(self) -> None:
        md = (
            "## Risks\n\nThe runbook matters.\n\n"
            "## Testing\n\nRun the runbook again.\n\n"
            "## Acceptance criteria\n\nNothing relevant.\n"
        )
        assert [r.keyword for r in find_dropped_references(md)] == ["runbook"]

    def test_captures_leading_phrase_for_matrix(self) -> None:
        md = (
            "## Architecture\n\nSee the per-vendor evaluation matrix.\n\n"
            "## Acceptance criteria\n\nNo mention here.\n"
        )
        refs = find_dropped_references(md)
        assert len(refs) == 1
        assert refs[0].keyword == "matrix"
        assert "evaluation matrix" in refs[0].anchor

    def test_no_artifacts_means_no_flags(self) -> None:
        md = (
            "## Overview\n\nA simple plan touching `src/app.py`.\n\n"
            "## Acceptance criteria\n\nIt works.\n"
        )
        assert find_dropped_references(md) == []

    def test_returns_dropped_reference_instances(self) -> None:
        md = "## Risks\n\nthe runbook.\n\n## Acceptance criteria\n\nx.\n"
        refs = find_dropped_references(md)
        assert refs and isinstance(refs[0], DroppedReference)


class TestCreatePlanDistillThreading:
    def test_dropped_reference_warns_and_records(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, out_dir, manifest = _repo(tmp_path)
        source = _SEED + "\nOrdering: the runbook in Section 7 sequences this.\n"
        sections = {k: f"{k} body." for k in _SECTION_KEYS}
        sections["Risks"] = "Ordering: the runbook in Section 7 sequences this."
        response = json.loads(_single_json())
        response["sections"] = sections
        source_line = len(source.splitlines())
        response["evidence_spans"]["Risks"] = [
            {"start_line": source_line, "end_line": source_line}
        ]
        distill_resp = json.dumps(response)
        res = create_plan(
            "feat",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=source,
            yes=True,
            resume=False,
            distill=True,
            claude_invoker=_router(distill_resp),
        )
        assert res.plan_path is not None and res.plan_path.is_file()
        assert {r.keyword for r in res.dropped_references} == {"runbook", "section"}
        err = capsys.readouterr().err
        assert "may have dropped" in err
        assert "runbook" in err and "Section 7" in err

    def test_no_dropped_reference_no_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, out_dir, manifest = _repo(tmp_path)
        res = create_plan(
            "feat",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_SEED,
            yes=True,
            resume=False,
            distill=True,
            claude_invoker=_router(_single_json()),
        )
        assert res.dropped_references == []
        assert "may have dropped" not in capsys.readouterr().err

    def test_single_subsumes_body_synthesis(self, tmp_path: Path) -> None:
        repo, out_dir, manifest = _repo(tmp_path)
        counters: dict = {}
        res = create_plan(
            "feat",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_SEED,
            yes=True,
            resume=False,
            distill=True,
            claude_invoker=_router(_single_json(), counters=counters),
        )
        assert res.plan_path is not None and res.plan_path.is_file()
        # Distill covered all 8 sections, so body synthesis was skipped.
        assert counters.get("body", 0) == 0
        body = res.plan_path.read_text(encoding="utf-8")
        assert "Overview body — see" in body and "_(TODO)_" not in body
        # The distilled artifact is returned for the CLI to archive.
        assert res.distilled_seed is not None
        assert res.split_proposal is None

    def test_split_short_circuits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, out_dir, manifest = _repo(tmp_path)
        counters: dict = {}
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("a split proposal must not resolve risk")
            ),
        )
        monkeypatch.setattr(
            create_module,
            "append_to_manifest",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("a split proposal must not publish")
            ),
        )
        res = create_plan(
            "big",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="l1\nl2\nl3\nl4\nl5\nl6",
            yes=True,
            resume=False,
            distill=True,
            claude_invoker=_router(_split_json(_TWO_PLANS), counters=counters),
        )
        assert res.split_proposal is not None
        assert [e.suggested_slug for e in res.split_proposal.entries] == [
            "oauth-login",
            "billing-queue",
        ]
        assert res.plan_path is None
        assert res.file_backed_route is None
        # Short-circuited before steps/references/body.
        assert counters.get("steps", 0) == 0 and counters.get("body", 0) == 0
        assert list(out_dir.glob("*.md")) == []
        assert not manifest.exists()

    def test_inline_small_canonical_seed_retains_distill_flag_compatibility(
        self, tmp_path: Path
    ) -> None:
        repo, out_dir, manifest = _repo(tmp_path)
        canonical = "\n".join(f"## {k}\n\n{k} text.\n" for k in _SECTION_KEYS)
        counters: dict = {}
        create_plan(
            "canon",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=canonical,
            seed_body=canonical,
            yes=True,
            resume=False,
            distill=True,
            claude_invoker=_router(_single_json(), counters=counters),
        )
        # Already-canonical + small => distill skipped entirely.
        assert counters.get("distill", 0) == 0
        # Sanity: this seed really does cover all canonical sections.
        assert _canonical_seed_covers_all(extract_h2_sections(canonical))

    def test_distill_false_skips_pass(self, tmp_path: Path) -> None:
        repo, out_dir, manifest = _repo(tmp_path)
        counters: dict = {}
        create_plan(
            "nd",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_SEED,
            yes=True,
            resume=False,
            distill=False,
            claude_invoker=_router(
                _single_json(), body=_single_body_all(), counters=counters
            ),
        )
        assert counters.get("distill", 0) == 0

    def test_file_backed_no_distill_uses_selected_route(self, tmp_path: Path) -> None:
        routes: list[FileBackedSourceRoute | None] = []
        distill_calls: list[int] = []
        for distill in (False, True):
            case_root = tmp_path / str(distill).lower()
            case_root.mkdir()
            repo, out_dir, manifest = _repo(case_root)
            source = repo / "seed.md"
            source.write_text(_SEED, encoding="utf-8")
            counters: dict = {}
            result = create_plan(
                "file-route",
                repo_root=repo,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description=source.read_text(encoding="utf-8"),
                from_existing_path=source,
                yes=True,
                resume=False,
                distill=distill,
                claude_invoker=_router(_single_json(), counters=counters),
            )
            routes.append(result.file_backed_route)
            distill_calls.append(counters.get("distill", 0))

        assert routes == [FileBackedSourceRoute.NORMALIZED] * 2
        assert distill_calls == [1, 1]

    def test_inline_no_distill_keeps_legacy_distill_bypass(self, tmp_path: Path) -> None:
        repo, out_dir, manifest = _repo(tmp_path)
        counters: dict = {}

        result = create_plan(
            "inline-no-distill",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_SEED,
            yes=True,
            resume=False,
            distill=False,
            claude_invoker=_router(
                _single_json(), body=_single_body_all(), counters=counters
            ),
        )

        assert counters.get("distill", 0) == 0
        assert result.file_backed_route is None

    def test_file_backed_result_distinguishes_published_split_and_refused_routes(
        self, tmp_path: Path
    ) -> None:
        def file_result(case: str, response: str):
            from plan_tool.run_log import RunLogWriter

            case_root = tmp_path / case
            case_root.mkdir()
            repo, out_dir, manifest = _repo(case_root)
            source = repo / "seed.md"
            source.write_text(_SEED, encoding="utf-8")
            logger = RunLogWriter.start(
                repo_root=repo,
                slug=case,
                command="create",
                argv=["plan-tool", "create", case],
            )
            result = create_plan(
                case,
                repo_root=repo,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description=source.read_text(encoding="utf-8"),
                from_existing_path=source,
                yes=True,
                resume=False,
                distill=False,
                claude_invoker=_router(response),
                run_logger=logger,
            )
            logger.run_end(outcome="ok", rc=0)
            route_events = [
                json.loads(line)
                for log_path in (repo / ".plan-tool" / "runs" / case).glob("*.jsonl")
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if '"file_backed_route"' in line
            ]
            assert len(route_events) == 1
            return result, route_events[0]

        published, published_event = file_result("published", _single_json())
        split, split_event = file_result("split", _split_json(_TWO_PLANS))
        refused, refused_event = file_result("refused", "not preparation JSON")

        assert published.file_backed_route is FileBackedSourceRoute.NORMALIZED
        assert published.plan_path is not None
        assert split.file_backed_route is FileBackedSourceRoute.SPLIT
        assert split.plan_path is None and split.split_proposal is not None
        assert refused.file_backed_route is FileBackedSourceRoute.REFUSED
        assert refused.plan_path is None and refused.refusal_reason
        assert [event["route"] for event in (published_event, split_event, refused_event)] == [
            "normalized",
            "split",
            "refused",
        ]
        assert "refusal_reason" not in published_event
        assert "refusal_reason" not in split_event
        assert refused_event["refusal_reason"] == refused.refusal_reason

    def test_file_backed_library_routes_never_archive_or_write_normalized_siblings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        direct_root = tmp_path / "direct"
        direct_root.mkdir()
        direct_repo, direct_out, direct_manifest = _repo(direct_root)
        direct_source = direct_repo / "direct.md"
        direct_text = _direct_file_seed()
        direct_source.write_text(direct_text, encoding="utf-8")
        direct_sibling = direct_repo / "direct.distilled.md"
        direct_sibling.write_text("recoverable direct sibling\n", encoding="utf-8")
        monkeypatch.setattr(
            create_module,
            "assess_direct_source_split_from_claude",
            lambda *_args, **_kwargs: DirectSplitAssessment(),
        )
        direct = create_plan(
            "direct-source",
            repo_root=direct_repo,
            output_dir_override=direct_out,
            manifest_path=direct_manifest,
            from_description=direct_text,
            from_existing_path=direct_source,
            yes=True,
            resume=False,
            claude_invoker=_router(_single_json()),
        )

        normalized_root = tmp_path / "normalized"
        normalized_root.mkdir()
        normalized_repo, normalized_out, normalized_manifest = _repo(normalized_root)
        normalized_source = normalized_repo / "normalized.md"
        normalized_source.write_text(_SEED, encoding="utf-8")
        normalized_sibling = normalized_repo / "normalized.distilled.md"
        normalized_sibling.write_text(
            "recoverable normalized sibling\n", encoding="utf-8"
        )
        normalized = create_plan(
            "normalized-source",
            repo_root=normalized_repo,
            output_dir_override=normalized_out,
            manifest_path=normalized_manifest,
            from_description=normalized_source.read_text(encoding="utf-8"),
            from_existing_path=normalized_source,
            yes=True,
            resume=False,
            distill=False,
            claude_invoker=_router(_single_json()),
        )

        assert direct.file_backed_route is FileBackedSourceRoute.DIRECT
        assert normalized.file_backed_route is FileBackedSourceRoute.NORMALIZED
        assert direct_source.read_text(encoding="utf-8") == direct_text
        assert normalized_source.read_text(encoding="utf-8") == _SEED
        assert direct_sibling.read_text(encoding="utf-8") == "recoverable direct sibling\n"
        assert (
            normalized_sibling.read_text(encoding="utf-8")
            == "recoverable normalized sibling\n"
        )

    def test_direct_success_discards_route_and_stale_preparation_checkpoints(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.checkpoint import Checkpoint, checkpoint_path, save_checkpoint

        repo, out_dir, manifest = _repo(tmp_path)
        source = repo / "direct.md"
        source_text = _direct_file_seed()
        source.write_text(source_text, encoding="utf-8")
        stale_preparation = checkpoint_path(repo, "direct", "create-distill-seed")
        save_checkpoint(
            stale_preparation,
            Checkpoint(
                input_hash="stale",
                payload="stale preparation",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        base_invoke = _router(_single_json())

        def invoke(prompt: str) -> str:
            if prompt.startswith("Assess whether this file-backed"):
                return '{"outcome":"single"}'
            return base_invoke(prompt)

        result = create_plan(
            "direct",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=source_text,
            from_existing_path=source,
            yes=True,
            claude_invoker=invoke,
        )

        assert result.file_backed_route is FileBackedSourceRoute.DIRECT
        assert source.is_file()
        assert not stale_preparation.exists()
        assert not checkpoint_path(repo, "direct", "create-direct-assessment").exists()
        assert not (source.parent / "direct.distilled.md").exists()

    def test_normalized_iteration_incomplete_retains_route_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.checkpoint import checkpoint_path

        repo, out_dir, manifest = _repo(tmp_path)
        source = repo / "normalized.md"
        source.write_text(_SEED, encoding="utf-8")
        monkeypatch.setattr(
            create_module,
            "_converge_create_plan",
            lambda *_args, **_kwargs: "iteration stage failed",
        )

        result = create_plan(
            "normalized",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_SEED,
            from_existing_path=source,
            yes=True,
            claude_invoker=_router(_single_json()),
        )

        assert result.file_backed_route is FileBackedSourceRoute.NORMALIZED
        assert result.iteration_stage_failure == "iteration stage failed"
        assert result.plan_path is not None and result.plan_path.is_file()
        assert source.is_file()
        assert checkpoint_path(repo, "normalized", "create-distill-seed").is_file()

    def test_split_retains_versioned_result_without_plan_or_manifest(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.checkpoint import checkpoint_path

        repo, out_dir, manifest = _repo(tmp_path)
        source = repo / "split.md"
        source.write_text(_SEED, encoding="utf-8")

        result = create_plan(
            "split",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_SEED,
            from_existing_path=source,
            yes=True,
            resume=False,
            claude_invoker=_router(_split_json(_TWO_PLANS)),
        )

        assert result.file_backed_route is FileBackedSourceRoute.SPLIT
        assert result.plan_path is None and result.split_proposal is not None
        assert source.is_file()
        assert checkpoint_path(repo, "split", "create-distill-seed").is_file()
        assert list(out_dir.glob("*.md")) == []
        assert not manifest.exists()

    def test_refused_route_discards_its_checkpoint_and_keeps_unrelated_state(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.checkpoint import Checkpoint, checkpoint_path, save_checkpoint

        repo, out_dir, manifest = _repo(tmp_path)
        source = repo / "refused.md"
        source.write_text(_SEED, encoding="utf-8")
        preparation = checkpoint_path(repo, "refused", "create-distill-seed")
        save_checkpoint(
            preparation,
            Checkpoint(
                input_hash=_distill_seed_input_hash("refused", _SEED, out_dir, repo),
                payload="not preparation JSON",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        unrelated = checkpoint_path(repo, "refused", "create-initial-steps")
        save_checkpoint(
            unrelated,
            Checkpoint(
                input_hash="unrelated",
                payload="keep this checkpoint",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )

        result = create_plan(
            "refused",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_SEED,
            from_existing_path=source,
            yes=True,
            claude_invoker=_router("still not preparation JSON"),
        )

        assert result.file_backed_route is FileBackedSourceRoute.REFUSED
        assert result.plan_path is None
        assert source.is_file()
        assert not preparation.exists()
        assert unrelated.is_file()
        assert list(out_dir.glob("*.md")) == []
        assert not manifest.exists()


def _single_body_all() -> str:
    return json.dumps({k: f"{k} text" for k in _SECTION_KEYS})


# --------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------


def _patch_fake_claude(monkeypatch, router: Callable[[str], str]) -> None:
    from plan_tool import backend_runner
    from plan_tool import shell as shell_module
    from subprocess_doubles import _FakeProc, claude_result_ndjson

    monkeypatch.setattr(shell_module.shutil, "which", lambda _n: "/usr/bin/claude")

    real_popen = backend_runner.subprocess.Popen

    def fake_popen(argv, **kwargs):
        if argv and argv[0] == "git":
            return real_popen(argv, **kwargs)
        # claude batch is stream-json now (BACKLOG #74), so wrap the router's
        # assistant text in a terminal `result` envelope the way real claude
        # does; claude_invoke's collapse rule unwraps it back to the text +
        # usage.
        envelope = claude_result_ndjson(
            router(argv[-1]),
            usage={
                "input_tokens": 1,
                "output_tokens": 1,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        )
        return _FakeProc(envelope.splitlines(keepends=True), [], 0)

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)


class TestCmdCreateDistillCli:
    def test_split_proposal_saved_and_exit_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import cli as cli_module

        repo, out_dir, manifest = _repo(tmp_path)
        seed = repo / "notes.md"
        seed.write_text(
            "l1\nl2\nl3\nl4\nl5\nl6\n\n"
            "## References\n\n- [App API](https://example.test/app-api)\n",
            encoding="utf-8",
        )
        _patch_fake_claude(monkeypatch, _router(_split_json(_TWO_PLANS)))
        monkeypatch.chdir(repo)

        rc = cli_module.main([
            "--manifest", str(manifest), "create", "big",
            "--from-existing", str(seed), "--output-dir", str(out_dir),
            "--no-iterate", "-y",
        ])
        assert rc == 0  # split proposal is a success, not an error
        proposal = out_dir / "big-split-proposal.md"
        assert proposal.is_file()
        text = proposal.read_text(encoding="utf-8")
        assert "oauth-login" in text and "billing-queue" in text
        assert "sed -n" in text  # carve command rendered for valid ranges
        # No plan written; seed left in place for the user to carve.
        assert list(out_dir.glob("*-big.md")) == []
        assert seed.is_file()

    def test_single_archives_distilled_artifact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import cli as cli_module

        repo, out_dir, manifest = _repo(tmp_path)
        seed = repo / "notes.md"
        seed.write_text(_SEED, encoding="utf-8")
        _patch_fake_claude(monkeypatch, _router(_single_json()))
        monkeypatch.chdir(repo)

        rc = cli_module.main([
            "--manifest", str(manifest), "create", "feat",
            "--from-existing", str(seed), "--output-dir", str(out_dir),
            "--no-iterate", "-y",
        ])
        assert rc == 0
        # Plan written, seed + distilled artifact archived (superseded rule).
        assert len(list(out_dir.glob("*-feat.md"))) == 1
        archive = seed.parent / "archive"
        archived = {p.name for p in archive.glob("*.md")}
        assert "notes.replaced.md" in archived
        assert "notes.distilled.replaced.md" in archived

    def test_registered_finalization_error_leaves_distilled_seed_unarchived(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Do not treat a registered but incomplete create as a successful conversion."""
        from plan_tool import cli as cli_module

        repo, out_dir, manifest = _repo(tmp_path)
        seed = repo / "notes.md"
        seed.write_text(_SEED, encoding="utf-8")
        _patch_fake_claude(monkeypatch, _router(_single_json()))
        monkeypatch.setattr(
            create_module,
            "_finalize_create_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("registered tail stopped")
            ),
        )
        monkeypatch.chdir(repo)

        rc = cli_module.main([
            "--manifest", str(manifest), "create", "feat",
            "--from-existing", str(seed), "--output-dir", str(out_dir),
            "--no-iterate", "-y",
        ])

        assert rc == 1
        assert seed.is_file()
        assert not (seed.parent / "archive").exists()
        assert "plans/2-feat.md" in json.loads(manifest.read_text(encoding="utf-8"))["plans"]
        assert "registered but finalization is incomplete" in capsys.readouterr().err
