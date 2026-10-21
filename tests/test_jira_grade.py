"""Tests for the jira-grade detail contract authority.

Covers the five-section schema and its validator, the deterministic
plain-English gate, and the collision-safety of the jira-grade artifact
path against the run-grade lifecycle. The path assertions live here rather
than in ``tests/test_detail_artifacts.py`` — that file is the step-1
characterization suite and must stay unmodified — even though the path
function itself lives in ``plan_tool/detail_artifacts.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from plan_tool.detail import (
    _archive_orphan_details,
    derive_detail_path,
    find_unreferenced_detail_for_step,
)
from plan_tool.detail_artifacts import derive_jira_detail_path
from plan_tool.jira_grade import (
    _RUN_GRADE_H2_TOKENS,
    FINDING_DUPLICATE_SECTION,
    FINDING_EMPTY_SECTION,
    FINDING_FILLER_PHRASE,
    FINDING_LONG_SENTENCE,
    FINDING_MISSING_SECTION,
    FINDING_UNKNOWN_SECTION,
    FINDING_UNTERMINATED_FENCE,
    FINDING_WRONG_SCHEMA,
    GRADE_DEFAULT,
    GRADE_JIRA,
    GRADE_RUN,
    JIRA_GRADE_REQUIRED_H2S,
    JIRA_GRADE_REQUIRED_H2_TOKENS,
    JIRA_GRADE_VALUES,
    JiraGradeContractError,
    check_plain_english,
    fenced_spans,
    load_jira_grade_detail,
    parse_jira_grade_sections,
    validate_jira_grade_body,
)
from plan_tool.schema import Plan, Step

CONFORMING_BODY = """# Step 3 — Ship the widget

## Intent

Give the operator one place to see the widget.

## Change

Add a widget panel to the dashboard and route the existing feed into it.

## Constraints

The panel loads from the cached feed only. No new network call.

## Done when

- The dashboard shows the panel.
- The panel renders an empty state with no feed.

## Out of scope

Editing the feed. Mobile layout.
"""

RUN_GRADE_BODY = """# Step 3 — Ship the widget

## Summary

Ships the widget panel.

## Table of Contents

- Summary

## Why

The operator has nowhere to see the widget.

## Files (creates vs edits)

- `dashboard.py` — add the panel.

## Implementation

Render the panel from the cached feed.

## Tests

- `test_panel_renders` — the panel appears.

## Acceptance criteria

- The dashboard shows the panel.
"""


def _drop_section(body: str, display_name: str) -> str:
    """Remove one ``## <display_name>`` section from a conforming body."""
    out: list[str] = []
    dropping = False
    for line in body.splitlines():
        if line.startswith("## "):
            dropping = line == f"## {display_name}"
        if not dropping:
            out.append(line)
    return "\n".join(out) + "\n"


def _plan_with_steps(steps: list[Step]) -> Plan:
    return Plan(title="Demo", status="planning", priority="medium", steps=steps)


def _blocking_kinds(findings: list) -> list[str]:
    return [f.kind for f in findings if f.blocking]


class TestContract:
    """The declared authority: section names, tokens, and the grade axis."""

    def test_required_h2_names_and_order(self) -> None:
        assert JIRA_GRADE_REQUIRED_H2S == (
            "Intent",
            "Change",
            "Constraints",
            "Done when",
            "Out of scope",
        )
        assert JIRA_GRADE_REQUIRED_H2_TOKENS == (
            "intent",
            "change",
            "constraints",
            "done",
            "out",
        )

    def test_grade_axis_values(self) -> None:
        """The four later grade flags read their spelling from here."""
        assert (GRADE_RUN, GRADE_JIRA) == ("run", "jira")
        assert JIRA_GRADE_VALUES == ("run", "jira")

    def test_grade_default_is_a_named_constant(self) -> None:
        """Run-grade stays the default on every surface, stated once.

        Four commands grow a grade selector; each reads this rather than
        re-deciding, or inferring it from `JIRA_GRADE_VALUES` ordering.
        """
        assert GRADE_DEFAULT == GRADE_RUN
        assert GRADE_DEFAULT in JIRA_GRADE_VALUES


class TestValidator:
    """`validate_jira_grade_body`: the closed five-section schema."""

    def test_validate_accepts_minimal_conforming_body(self) -> None:
        assert validate_jira_grade_body(CONFORMING_BODY) == []

    def test_validate_accepts_heading_variants(self) -> None:
        """First-token matching: case-insensitive, trailing words allowed."""
        body = CONFORMING_BODY.replace("## Done when", "## done when").replace(
            "## Out of scope", "## Out of scope (v1)"
        )
        assert validate_jira_grade_body(body) == []

    @pytest.mark.parametrize("display_name", list(JIRA_GRADE_REQUIRED_H2S))
    def test_validate_flags_each_missing_section(self, display_name: str) -> None:
        findings = validate_jira_grade_body(
            _drop_section(CONFORMING_BODY, display_name)
        )
        missing = [f for f in findings if f.kind == FINDING_MISSING_SECTION]
        assert len(missing) == 1
        assert missing[0].blocking
        assert display_name in missing[0].message

    def test_validate_flags_empty_section_body(self) -> None:
        body = CONFORMING_BODY.replace(
            "The panel loads from the cached feed only. No new network call.", ""
        )
        findings = validate_jira_grade_body(body)
        assert _blocking_kinds(findings) == [FINDING_EMPTY_SECTION]
        assert "Constraints" in findings[0].message

    def test_validate_rejects_unknown_h2(self) -> None:
        body = CONFORMING_BODY + "\n## Implementation\n\nRender the panel.\n"
        findings = validate_jira_grade_body(body)
        assert _blocking_kinds(findings) == [FINDING_UNKNOWN_SECTION]
        assert "Implementation" in findings[0].message

    def test_validate_allows_h3_inside_a_section(self) -> None:
        body = CONFORMING_BODY.replace(
            "## Done when\n", "## Done when\n\n### Acceptance\n"
        )
        assert validate_jira_grade_body(body) == []

    def test_validate_flags_duplicate_section(self) -> None:
        body = CONFORMING_BODY + "\n## Intent\n\nSay it again.\n"
        assert _blocking_kinds(validate_jira_grade_body(body)) == [
            FINDING_DUPLICATE_SECTION
        ]

    def test_validate_ignores_headings_inside_fences(self) -> None:
        body = CONFORMING_BODY.replace(
            "Editing the feed. Mobile layout.",
            "Editing the feed.\n\n```md\n## Implementation\n```\n",
        )
        assert validate_jira_grade_body(body) == []

    def test_nested_shorter_fence_does_not_close_a_longer_opener(self) -> None:
        """A ```` (4-backtick) block containing an inner ``` (3-backtick)
        line must not close on that inner line — the real closer has to
        match the opener's character *and* be at least as long, or the
        inner line closes it early, the real closer reopens a new fence,
        and the next real heading gets swallowed as fence content."""
        body = CONFORMING_BODY.replace(
            "Add a widget panel to the dashboard and route the existing feed into it.",
            "````python\nexample:\n```\nnested\n```\nmore\n````\n",
        )
        assert validate_jira_grade_body(body) == []
        assert "constraints" in parse_jira_grade_sections(body)

    def test_validate_rejects_complete_run_grade_body(self) -> None:
        """A valid body from the *other* schema fails as one wrong-schema
        finding, not five missing-section lines."""
        findings = validate_jira_grade_body(RUN_GRADE_BODY)
        assert _blocking_kinds(findings) == [FINDING_WRONG_SCHEMA]
        assert "run-grade body at a jira-grade path" in findings[0].message

    def test_run_grade_token_copy_matches_detail(self) -> None:
        """The wrong-schema detector's run-grade token tuple is a copy — the
        leaf can't import ``detail``. Nothing but this test keeps the copy
        honest, and drift degrades silently: rename enough run-grade
        sections and a run-grade body stops clearing
        ``_WRONG_SCHEMA_MIN_RUN_H2S``, so it reports five missing-section
        lines instead of naming the mistake — the exact ambiguity step 3
        exists to close. A test may import both modules; the leaf may not.

        Order (not just membership) matters: jira.py imports this same
        tuple as its own run-grade-detail contract order, to report
        missing sections in that order without a fourth hand-maintained
        copy.
        """
        from plan_tool.detail import _REQUIRED_H2_TOKENS

        assert _RUN_GRADE_H2_TOKENS == _REQUIRED_H2_TOKENS

    def test_parse_sections_maps_tokens_to_bodies(self) -> None:
        sections = parse_jira_grade_sections(CONFORMING_BODY)
        assert set(sections) == set(JIRA_GRADE_REQUIRED_H2_TOKENS)
        assert sections["intent"] == (
            "Give the operator one place to see the widget."
        )


class TestUnterminatedFence:
    """An unclosed fence silences both gates, so both must name it."""

    UNCLOSED = CONFORMING_BODY.replace(
        "Mobile layout.", "Mobile layout.\n\n```python\nx = 1\n"
    )

    def test_validate_reports_the_fence_not_its_symptoms(self) -> None:
        # Without this, section scanning swallows every heading below the
        # fence and the body is reported as missing sections it actually has.
        findings = validate_jira_grade_body(self.UNCLOSED)
        assert [f.kind for f in findings] == [FINDING_UNTERMINATED_FENCE]
        assert findings[0].blocking

    def test_prose_gate_is_not_silently_disabled(self) -> None:
        # `_strip_fenced_blocks` drops everything after an unclosed fence, so
        # prose below it was measured by nothing at all — a defect that turned
        # the authoring gate off rather than failing it.
        body = self.UNCLOSED.replace(
            "## Out of scope", "## Out of scope\n\nWe do it in order to ship."
        )
        findings = check_plain_english(body)
        assert [f.kind for f in findings] == [FINDING_UNTERMINATED_FENCE]

    def test_closed_fence_is_unaffected(self) -> None:
        closed = self.UNCLOSED + "```\n"
        assert validate_jira_grade_body(closed) == []
        assert check_plain_english(closed) == []


class TestFencedSpans:
    """`fenced_spans` -- the general-purpose char-span primitive review.py's
    plan-audit citation-fencing protection is built on (round-5 finding:
    review.py's own regex reinvented this, with regressions, instead of
    reusing it)."""

    def test_basic_pair(self) -> None:
        text = "before\n```\ncode\n```\nafter\n"
        spans = fenced_spans(text)
        assert spans == [(7, 20)]
        assert text[spans[0][0] : spans[0][1]] == "```\ncode\n```\n"

    def test_unclosed_fence_spans_to_end_of_text(self) -> None:
        """An unclosed fence must span to EOF, not pair with an unrelated
        later fence elsewhere in the same text (the round-5 regression the
        old regex-based mechanism had: it paired an unclosed citation fence
        with a later, unrelated fence in the ### Fix suggestion)."""
        text = "before\n```\nnever closes\n"
        spans = fenced_spans(text)
        assert spans == [(7, len(text))]

    def test_tilde_fence_recognized(self) -> None:
        text = "before\n~~~\ncode\n~~~\nafter\n"
        assert fenced_spans(text) == [(7, 20)]

    def test_backtick_and_tilde_do_not_close_each_other(self) -> None:
        text = "before\n```\ncode\n~~~\nstill inside\n```\nafter\n"
        spans = fenced_spans(text)
        assert len(spans) == 1
        assert spans[0] == (7, len(text) - len("after\n"))

    def test_nested_shorter_run_does_not_close_a_longer_fence_early(self) -> None:
        """CommonMark's closing-length rule: a citation nesting a same-
        character run no longer than the opener's fence can't close it."""
        text = "before\n````\nouter\n```\ninner-fake-close\n````\nafter\n"
        spans = fenced_spans(text)
        assert len(spans) == 1
        assert text[spans[0][0] : spans[0][1]] == (
            "````\nouter\n```\ninner-fake-close\n````\n"
        )

    def test_crlf_line_endings_do_not_hide_the_fence(self) -> None:
        text = "before\r\n```\r\ncode\r\n```\r\nafter\r\n"
        spans = fenced_spans(text)
        assert len(spans) == 1
        assert text[spans[0][0] : spans[0][1]] == "```\r\ncode\r\n```\r\n"

    def test_indentation_beyond_three_spaces_still_recognized(self) -> None:
        """Deliberately more lenient than CommonMark's 3-space limit: this
        parses a model's own citation protocol, not rendered markdown, so a
        missed fence (false negative) is the unsafe direction."""
        text = "before\n      ```\n      code\n      ```\nafter\n"
        spans = fenced_spans(text)
        assert len(spans) == 1

    def test_no_fence_returns_empty(self) -> None:
        assert fenced_spans("just plain prose, no backticks at all\n") == []


class TestLoad:
    """`load_jira_grade_detail`: the loud-failure form consumers wire."""

    def test_contract_error_raised_on_load(self, tmp_path: Path) -> None:
        good = tmp_path / "03-good.md"
        good.write_text(CONFORMING_BODY, encoding="utf-8")
        assert load_jira_grade_detail(good) == CONFORMING_BODY

        bad = tmp_path / "03-bad.md"
        bad.write_text(RUN_GRADE_BODY, encoding="utf-8")
        with pytest.raises(JiraGradeContractError) as excinfo:
            load_jira_grade_detail(bad)
        assert excinfo.value.path == bad
        assert [f.kind for f in excinfo.value.findings] == [FINDING_WRONG_SCHEMA]

    def test_missing_artifact_raises_contract_error(self, tmp_path: Path) -> None:
        with pytest.raises(JiraGradeContractError):
            load_jira_grade_detail(tmp_path / "nope.md")

    def test_non_utf8_artifact_raises_contract_error(self, tmp_path: Path) -> None:
        path = tmp_path / "03-non-utf8.md"
        path.write_bytes(b"\xff")

        with pytest.raises(JiraGradeContractError) as excinfo:
            load_jira_grade_detail(path)

        assert excinfo.value.path == path

    def test_load_ignores_prose_findings(self, tmp_path: Path) -> None:
        """Read-time consumption validates structure only — an operator's
        hand-edited artifact never fails export over prose taste."""
        body = CONFORMING_BODY.replace(
            "Give the operator one place to see the widget.",
            "It is worth noting that the operator needs one place.",
        )
        path = tmp_path / "03-wordy.md"
        path.write_text(body, encoding="utf-8")
        assert _blocking_kinds(check_plain_english(body))
        assert load_jira_grade_detail(path) == body


class TestPlainEnglishGate:
    """`check_plain_english`: deterministic, anchor-blind, report-only."""

    def test_prose_gate_clean_body_no_findings(self) -> None:
        assert check_plain_english(CONFORMING_BODY) == []

    def test_prose_gate_flags_filler_phrase(self) -> None:
        body = CONFORMING_BODY.replace(
            "Add a widget panel",
            "It should be noted that we add a widget panel",
        )
        findings = check_plain_english(body)
        assert _blocking_kinds(findings) == [FINDING_FILLER_PHRASE]
        assert "it should be noted" in findings[0].message

    def test_prose_gate_flags_filler_across_a_line_break(self) -> None:
        """Prose is routinely hard-wrapped; the denylist must not depend on
        where the author's line breaks land.

        The sentence checks already fold a block's lines into one string, so
        a raw-substring filler scan made the two halves of the same gate
        disagree about whether a newline is a space — and the wrapped form is
        the one an authoring model emits.
        """
        wrapped = CONFORMING_BODY.replace(
            "Add a widget panel", "In order\nto add a widget panel"
        )
        kinds = [f.kind for f in check_plain_english(wrapped)]
        assert FINDING_FILLER_PHRASE in kinds

    def test_prose_gate_reports_overlapping_filler_once(self) -> None:
        body = CONFORMING_BODY.replace(
            "Editing the feed.", "Skipped due to the fact that it is slow."
        )
        assert _blocking_kinds(check_plain_english(body)) == [
            FINDING_FILLER_PHRASE
        ]

    def test_prose_gate_flags_over_long_sentence(self) -> None:
        long_sentence = " ".join(["widget"] * 40) + "."
        body = CONFORMING_BODY.replace(
            "Give the operator one place to see the widget.", long_sentence
        )
        findings = check_plain_english(body)
        assert _blocking_kinds(findings) == [FINDING_LONG_SENTENCE]

    def test_prose_gate_exempts_code_anchors(self) -> None:
        """A sentence long only because of anchors passes, and a fenced
        block is never measured."""
        # Half path-shaped, half plain lowercase words inside backticks —
        # the latter only survive the cap because the whole span is stripped.
        anchors = " ".join(
            f"`plan_tool/mod_{n}.py:handler` `widget panel feed cache`"
            for n in range(20)
        )
        body = CONFORMING_BODY.replace(
            "Give the operator one place to see the widget.",
            f"Route the feed through {anchors}.",
        ).replace(
            "Editing the feed. Mobile layout.",
            "Editing the feed.\n\n```python\n"
            + " ".join(["token"] * 60)
            + "\n```\n",
        )
        assert check_plain_english(body) == []

    def test_prose_gate_never_rewrites(self) -> None:
        body = CONFORMING_BODY.replace("Add a", "In order to add a")
        before = body
        check_plain_english(body)
        assert body == before

    def test_prose_gate_shape_signals_are_advisory(self) -> None:
        """Clause stacking reports, but never blocks."""
        body = CONFORMING_BODY.replace(
            "The panel loads from the cached feed only.",
            "The panel loads, then caches, then renders, then settles, "
            "then idles.",
        )
        findings = check_plain_english(body)
        assert findings and not any(f.blocking for f in findings)


class TestJiraArtifactPaths:
    """`derive_jira_detail_path` vs. the run-grade lifecycle."""

    def test_derive_jira_detail_path_format(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "2-widget-rollout.md"
        step = Step(id=3, title="Ship the widget panel")
        plan = _plan_with_steps([step])
        assert derive_jira_detail_path(plan_path, plan, step) == (
            tmp_path
            / "plan-details"
            / "widget-rollout"
            / "jira"
            / "03-ship-widget-panel.md"
        )

    def test_jira_path_never_equals_run_grade_path(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "2-widget-rollout.md"
        steps = [
            Step(id=1, title="Extract the resolver"),
            Step(id=2, title="Wire the panel"),
            Step(id=12, title="Document the contract"),
        ]
        plan = _plan_with_steps(steps)
        for step in steps:
            run_grade = derive_detail_path(plan_path, plan, step)
            jira = derive_jira_detail_path(plan_path, plan, step)
            assert jira != run_grade
            assert jira.name == run_grade.name
            assert jira.parent == run_grade.parent / "jira"

    def test_orphan_sweep_leaves_jira_artifact(self, tmp_path: Path) -> None:
        """The run-grade orphan sweep globs `NN-*.md` non-recursively, so a
        re-authored run-grade file must not archive the jira artifact."""
        plan_path = tmp_path / "2-widget-rollout.md"
        step = Step(id=3, title="Ship the widget panel")
        plan = _plan_with_steps([step])
        run_grade = derive_detail_path(plan_path, plan, step)
        jira = derive_jira_detail_path(plan_path, plan, step)
        for path, content in ((run_grade, "# run"), (jira, CONFORMING_BODY)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        assert _archive_orphan_details(run_grade, step.id) == []
        assert jira.is_file()
        assert not (jira.parent / "archive").exists()

    def test_run_grade_adoption_ignores_jira_artifact(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-widget-rollout.md"
        step = Step(id=3, title="Ship the widget panel")
        plan = _plan_with_steps([step])
        jira = derive_jira_detail_path(plan_path, plan, step)
        jira.parent.mkdir(parents=True, exist_ok=True)
        jira.write_text(CONFORMING_BODY, encoding="utf-8")

        assert find_unreferenced_detail_for_step(plan_path, plan, step) is None


class TestLeafImportDiscipline:
    def test_jira_grade_is_stdlib_only_leaf(self) -> None:
        """Consumers import the contract at module load, so it must pull in
        no orchestrator. Registers a stub ``plan_tool`` package first — the
        real package ``__init__`` eagerly imports ``detail``/``review``,
        which would mask what the *leaf* pulls in."""
        pkg_dir = Path(__file__).resolve().parents[1] / "plan_tool"
        code = (
            "import sys, types\n"
            "pkg = types.ModuleType('plan_tool')\n"
            f"pkg.__path__ = [{str(pkg_dir)!r}]\n"
            "sys.modules['plan_tool'] = pkg\n"
            "import plan_tool.jira_grade\n"
            "leaked = [m for m in sys.modules if m.startswith('plan_tool.')"
            " and m != 'plan_tool.jira_grade']\n"
            "assert not leaked, leaked\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr
