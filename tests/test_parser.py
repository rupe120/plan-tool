"""Tests for plan_tool.parser and plan_tool.schema."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError as ModelValidationError

from plan_tool import (
    ChangeType,
    Plan,
    ParseError,
    Priority,
    RiskProfile,
    PlanStatus,
    StepStatus,
    ValidationError,
    format_validation_errors,
    parse_plan,
    parse_plan_text,
    write_plan,
)
from plan_tool.parser import (
    UnsupportedPlanFormatVersionError,
    _require_supported_plan_format_version,
    parse_body_sections,
    render_plan_text,
    replace_body_sections,
    split_body_sections,
    split_plan_document,
    upgrade_plan_frontmatter_to_current,
)
from plan_tool.schema import PLAN_FORMAT_VERSION, SUPPORTED_PLAN_FORMAT_VERSIONS, Step

FIXTURES = Path(__file__).parent / "fixtures"
CONCEPT_A = "a" * 64
CONCEPT_B = "b" * 64


def _fixture(name: str) -> Path:
    return FIXTURES / name


def _concept_plan(concept_lines: str = "", second_step: str = "") -> str:
    return (
        "---\n"
        "title: Concept ownership\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        f"{concept_lines}"
        f"{second_step}"
        "---\n"
        "# Exact body\n\nKeep this prose.\n"
    )


def _depends_on_notes_plan(step_lines: str = "", second_step: str = "") -> str:
    return (
        "---\n"
        "title: Depends on notes\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        f"{step_lines}"
        f"{second_step or '  - id: 2\n    title: Second\n'}"
        "---\n"
        "# Exact body\n\nKeep this prose.\n"
    )


def _intent_plan(plan_intent: str = "", step_intent: str = "") -> str:
    """Plan text with optional ``intent:`` YAML lines spliced in.

    Both arguments are raw YAML (already indented for their container), so a
    case can exercise the scalar styles the schema must accept verbatim.
    """
    return (
        "---\n"
        "title: Intent Plan\n"
        f"{plan_intent}"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        f"{step_intent}"
        "---\n"
        "# Intent body\n\nKeep this prose.\n"
    )


def _risk_profile_plan(declaration: str = "") -> str:
    return (
        "---\n"
        "title: Risk profile plan\n"
        "status: planning\n"
        "priority: low\n"
        f"{declaration}"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "---\n"
        "# Risk profile body\n\nKeep this prose.\n"
    )


class TestDependsOnNotes:
    def test_depends_on_notes_absent_defaults_empty(self) -> None:
        assert parse_plan_text(_depends_on_notes_plan()).step_by_id(2).depends_on_notes == {}

    def test_depends_on_notes_parses_valid_mapping(self) -> None:
        step = (
            "  - id: 2\n"
            "    title: Second\n"
            "    depends_on: [1]\n"
            "    depends_on_notes:\n"
            "      1: consumes the schema type\n"
        )
        plan = parse_plan_text(_depends_on_notes_plan(second_step=step))
        assert plan.step_by_id(2).depends_on_notes == {1: "consumes the schema type"}

    def test_depends_on_notes_rejects_key_not_in_depends_on(self) -> None:
        step = (
            "  - id: 2\n"
            "    title: Second\n"
            "    depends_on: [1]\n"
            "    depends_on_notes:\n"
            "      2: orphan note\n"
        )
        with pytest.raises(ValidationError, match=r"step 2 depends_on_notes.*\b2\b"):
            parse_plan_text(_depends_on_notes_plan(second_step=step))

    def test_depends_on_notes_allows_partial_coverage(self) -> None:
        steps = (
            "  - id: 2\n"
            "    title: Second\n"
            "  - id: 3\n"
            "    title: Third\n"
            "    depends_on: [1, 2]\n"
            "    depends_on_notes:\n"
            "      1: only the first edge is noted\n"
        )
        plan = parse_plan_text(_depends_on_notes_plan(second_step=steps))
        assert plan.step_by_id(3).depends_on_notes == {1: "only the first edge is noted"}

    def test_depends_on_notes_accepts_empty_string_value(self) -> None:
        # Empty string parses (content is never graded), but authoring paths in
        # steps 3+ omit the key for silent edges — never write {id: ""}.
        step = (
            "  - id: 2\n"
            "    title: Second\n"
            "    depends_on: [1]\n"
            "    depends_on_notes:\n"
            '      1: ""\n'
        )
        plan = parse_plan_text(_depends_on_notes_plan(second_step=step))
        assert plan.step_by_id(2).depends_on_notes == {1: ""}

    def test_depends_on_notes_round_trips_through_write_plan(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        original = _depends_on_notes_plan(
            second_step=(
                "  - id: 2\n"
                "    title: Second\n"
                "    depends_on: [1]\n"
                "    depends_on_notes:\n"
                "      1: round-trip note\n"
            )
        )
        target.write_text(original, encoding="utf-8")
        write_plan(target, parse_plan(target))
        assert parse_plan(target).step_by_id(2).depends_on_notes == {1: "round-trip note"}
        rewritten_body = target.read_text(encoding="utf-8").split("---", 2)[2]
        assert rewritten_body == original.split("---", 2)[2]

    def test_empty_depends_on_notes_elided_on_write(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _depends_on_notes_plan(
                second_step=(
                    "  - id: 2\n"
                    "    title: Second\n"
                    "    depends_on: [1]\n"
                    "    depends_on_notes: {}\n"
                )
            ),
            encoding="utf-8",
        )
        write_plan(target, parse_plan(target))
        assert "depends_on_notes:" not in target.read_text(encoding="utf-8")

    def test_existing_well_formed_fixture_unchanged(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert all(step.depends_on_notes == {} for step in plan.steps)


class TestConceptOwnership:
    def test_concept_ids_absent_default_empty(self) -> None:
        assert parse_plan_text(_concept_plan()).step_by_id(1).concept_ids == []

    def test_step_concept_ids_parse(self) -> None:
        plan = parse_plan_text(
            _concept_plan(f"    concept_ids: [{CONCEPT_B}, {CONCEPT_A}]\n")
        )
        assert plan.step_by_id(1).concept_ids == [CONCEPT_B, CONCEPT_A]

    def test_step_concept_ids_reject_non_string_entry(self) -> None:
        with pytest.raises(ValidationError, match="concept_ids"):
            parse_plan_text(_concept_plan("    concept_ids: [42]\n"))

    @pytest.mark.parametrize("bad_id", ["", "   ", "abc", "A" * 64])
    def test_step_concept_ids_reject_malformed_or_empty_id(self, bad_id: str) -> None:
        with pytest.raises(ValidationError, match="concept_ids"):
            parse_plan_text(_concept_plan(f"    concept_ids: ['{bad_id}']\n"))

    def test_step_concept_ids_reject_duplicate(self) -> None:
        with pytest.raises(ValidationError, match="repeat"):
            parse_plan_text(
                _concept_plan(f"    concept_ids: [{CONCEPT_A}, {CONCEPT_A}]\n")
            )

    def test_concept_ids_may_be_owned_by_multiple_steps(self) -> None:
        second = (
            "  - id: 2\n"
            "    title: Second\n"
            f"    concept_ids: [{CONCEPT_A}]\n"
        )
        plan = parse_plan_text(
            _concept_plan(f"    concept_ids: [{CONCEPT_A}]\n", second)
        )
        assert [step.concept_ids for step in plan.steps] == [
            [CONCEPT_A],
            [CONCEPT_A],
        ]

    def test_concept_ids_round_trip(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        original = _concept_plan(f"    concept_ids: [{CONCEPT_B}, {CONCEPT_A}]\n")
        target.write_text(original, encoding="utf-8")
        plan = parse_plan(target)
        write_plan(target, plan)
        assert parse_plan(target).step_by_id(1).concept_ids == [
            CONCEPT_B,
            CONCEPT_A,
        ]
        rewritten_body = target.read_text(encoding="utf-8").split("---", 2)[2]
        assert rewritten_body == original.split("---", 2)[2]

    def test_empty_concept_ids_elided_on_write(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_concept_plan("    concept_ids: []\n"), encoding="utf-8")
        write_plan(target, parse_plan(target))
        assert "concept_ids:" not in target.read_text(encoding="utf-8")


class TestSplitBodySections:
    def test_simple_two_sections(self) -> None:
        body = "## A\n\nbody-a\n\n## B\n\nbody-b\n"
        sections = split_body_sections(body)
        assert sections == {"a": "body-a", "b": "body-b"}

    def test_trailing_punctuation_normalized(self) -> None:
        body = "## Risks:\n\ncolon\n\n## RISKS.\n\nperiod\n"
        sections = split_body_sections(body)
        assert sections == {"risks": "period"}

    def test_h1_terminates_section(self) -> None:
        body = "## A\n\nbody-a\n\n# Top\ncontent\n"
        sections = split_body_sections(body)
        assert sections["a"] == "body-a"

    def test_h3_remains_in_parent_body(self) -> None:
        body = "## A\n\nintro\n\n### Detail\n\nmore\n"
        sections = split_body_sections(body)
        assert sections == {"a": "intro\n\n### Detail\n\nmore"}

    def test_empty_body_returns_empty(self) -> None:
        assert split_body_sections("") == {}

    def test_duplicate_normalized_heading_uses_last(self) -> None:
        body = "## Risks:\n\nfirst\n\n## risks.\n\nsecond\n"
        sections = split_body_sections(body)
        assert sections == {"risks": "second"}

    def test_preserves_internal_markdown(self) -> None:
        section_body = (
            "First paragraph.\n\n"
            "- one\n"
            "- two\n\n"
            "### Detail\n\n"
            "`inline code` and **bold**"
        )
        body = f"## Implementation\n\n{section_body}\n\n"
        sections = split_body_sections(body)
        assert sections == {"implementation": section_body}

    def test_replacement_preserves_unowned_sections_and_inserts_missing(self) -> None:
        body = "# Plan\n\n## Custom\n\nExact.\n\n## Deferred\n\nOld\n"
        updated = replace_body_sections(
            body, {"deferred": "- Later", "out of scope": "- Never"}
        )
        assert "## Custom\n\nExact." in updated
        assert split_body_sections(updated)["deferred"] == "- Later"
        assert split_body_sections(updated)["out of scope"] == "- Never"

    def test_default_split_keeps_fenced_pseudo_heading_behavior(self) -> None:
        body = "## Real\n\nbefore\n\n```markdown\n## Example\ninside\n```\n\n## Later\n\nafter\n"

        assert split_body_sections(body) == {
            "real": "before\n\n```markdown",
            "example": "inside\n```",
            "later": "after",
        }

    def test_fence_safe_split_ignores_fenced_h1_and_h2_boundaries(self) -> None:
        body = (
            "## Real\n\nbefore\n\n```markdown\n# Example title\n"
            "## Example section\ninside\n```\n\n## Later\n\nafter\n"
        )

        assert split_body_sections(body, ignore_fenced_code=True) == {
            "real": "before\n\n```markdown\n# Example title\n## Example section\ninside\n```",
            "later": "after",
        }

    def test_fence_safe_split_strips_fenced_body_text_only_when_requested(self) -> None:
        body = "## Real\n\nbefore\n\n```\n## Example\ninside\n```\n\nafter\n"

        assert split_body_sections(body, ignore_fenced_code=True) == {
            "real": "before\n\n```\n## Example\ninside\n```\n\nafter"
        }
        assert split_body_sections(body, strip_fenced_code=True) == {
            "real": "before\n\n\nafter"
        }

    def test_fence_safe_parse_keeps_existing_duplicate_and_normalization_rules(self) -> None:
        body = (
            "## Risks:\n\nfirst\n\n```\n## RISKS.\nignored\n```\n\n"
            "## risks.\n\nlast\n"
        )

        sections = parse_body_sections(body, ignore_fenced_code=True)

        assert [(section.name, section.heading, section.order) for section in sections] == [
            ("risks", "Risks:", 0),
            ("risks", "risks.", 1),
        ]
        assert split_body_sections(body, ignore_fenced_code=True) == {"risks": "last"}

    def test_fence_safe_replacement_uses_only_real_h2_headings(self) -> None:
        body = (
            "## Deferred\n\nold\n\n```markdown\n## Deferred\n"
            "example\n```\n\n## Next\n\nkeep\n"
        )

        updated = replace_body_sections(
            body, {"deferred": "new"}, ignore_fenced_code=True
        )

        assert updated == "## Deferred\n\nnew\n## Next\n\nkeep\n"

    def test_fence_safe_replacement_preserves_unowned_fenced_content(self) -> None:
        fenced_unowned_section = (
            "## Notes\n\n```markdown\n## Deferred\nexample\n```\n\nkeep this\n"
        )
        body = "## Deferred\n\nold\n\n" + fenced_unowned_section

        updated = replace_body_sections(
            body, {"deferred": "new"}, ignore_fenced_code=True
        )

        assert updated == "## Deferred\n\nnew\n" + fenced_unowned_section

    def test_fence_safe_unmatched_opening_keeps_later_pseudo_heading_out_of_sections(
        self,
    ) -> None:
        body = "## Before\n\ntext\n\n```markdown\n## Later\nnot a section\n"

        assert split_body_sections(body, ignore_fenced_code=True) == {
            "before": "text\n\n```markdown\n## Later\nnot a section"
        }
        assert split_body_sections(body, strip_fenced_code=True) == {"before": "text"}


class TestWellFormed:
    def test_parses_without_error(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert isinstance(plan, Plan)

    def test_top_level_fields(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert plan.title == "Well-Formed Plan"
        assert plan.status == PlanStatus.IN_PROGRESS
        assert plan.priority == Priority.MEDIUM

    def test_step_count(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert len(plan.steps) == 3

    def test_step_defaults_applied(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        # Step 3 has no files/complexity/detail/status — should fall back to defaults.
        step3 = plan.step_by_id(3)
        assert step3.files == []
        assert step3.complexity is None
        assert step3.detail is None
        assert step3.status == StepStatus.PENDING
        assert step3.status_note is None
        assert step3.depends_on == [2]

    def test_current_step_lookup(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        current = plan.current_step()
        assert current is not None
        assert current.id == 2

    def test_next_runnable_when_current_active(self) -> None:
        # With a current step in-flight, next_runnable_step returns the next
        # PENDING step whose deps are done. Step 3 depends on 2 (current), so
        # no runnable pending step exists.
        plan = parse_plan(_fixture("well_formed.md"))
        assert plan.next_runnable_step() is None


class TestValidationErrors:
    def test_missing_required_field_is_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("missing_required.md"))
        assert "title" in str(exc_info.value).lower()

    def test_duplicate_ids_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("duplicate_ids.md"))
        assert "duplicate" in str(exc_info.value).lower()

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("unknown_field.md"))
        msg = str(exc_info.value).lower()
        assert "mystery_field" in msg or "extra" in msg

    def test_invalid_dependency_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("invalid_dep.md"))
        assert "99" in str(exc_info.value)

    def test_cycle_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("cycle.md"))
        assert "cycle" in str(exc_info.value).lower()

    def test_two_current_steps_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("two_current.md"))
        assert "current" in str(exc_info.value).lower()

    def test_self_dependency_rejected(self) -> None:
        text = (
            "---\n"
            "title: Self-Dep\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Loops on self\n"
            "    depends_on: [1]\n"
            "---\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(text)
        assert "itself" in str(exc_info.value).lower() or "cycle" in str(exc_info.value).lower()


class TestFormatValidationErrors:
    def test_carries_structured_errors(self) -> None:
        """The wrapper exposes pydantic's structured errors, not just str()."""
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("missing_required.md"))
        assert exc_info.value.errors  # non-empty list of error dicts

    def test_renders_field_colon_message(self) -> None:
        errs = [{"loc": ("steps",), "msg": "List should have at least 1 item"}]
        assert format_validation_errors(errs) == [
            "steps: List should have at least 1 item"
        ]

    def test_drops_value_error_prefix_for_model_validators(self) -> None:
        """Model-level validators have no field loc; the pydantic 'Value error,'
        prefix is stripped so the message reads naturally."""
        errs = [{"loc": (), "msg": "Value error, cycle detected among steps"}]
        assert format_validation_errors(errs) == ["cycle detected among steps"]

    def test_nested_loc_is_dotted(self) -> None:
        errs = [{"loc": ("steps", 0, "id"), "msg": "Input should be a valid integer"}]
        assert format_validation_errors(errs) == [
            "steps.0.id: Input should be a valid integer"
        ]

    def test_omits_pydantic_boilerplate(self) -> None:
        """No '[type=...]' annotation or docs URL leaks into the concise form."""
        with pytest.raises(ValidationError) as exc_info:
            parse_plan(_fixture("missing_required.md"))
        lines = format_validation_errors(exc_info.value.errors)
        joined = "\n".join(lines)
        assert "[type=" not in joined
        assert "errors.pydantic.dev" not in joined
        assert "validation error" not in joined.lower()

    def test_extra_plan_field_names_allowed_fields(self) -> None:
        """A forbidden plan-level field reports as unknown and lists what's valid,
        replacing pydantic's opaque 'Extra inputs are not permitted'."""
        errs = [{"type": "extra_forbidden", "loc": ("depends_on",), "msg": "x"}]
        (line,) = format_validation_errors(errs)
        assert line.startswith("depends_on: unknown plan-level field (allowed: ")
        assert "title" in line and "steps" in line
        # depends_on is a real *step* field, so point the author there.
        assert "depends_on belongs on a step" in line

    def test_extra_step_field_names_step_fields(self) -> None:
        """A forbidden step-level field lists the step schema, not the plan one."""
        errs = [
            {"type": "extra_forbidden", "loc": ("steps", 0, "complixity"), "msg": "x"}
        ]
        (line,) = format_validation_errors(errs)
        assert line.startswith("steps.0.complixity: unknown step field (allowed: ")
        assert "depends_on" in line and "complexity" in line
        # A pure typo isn't a real field anywhere, so no misplacement hint.
        assert "belongs on" not in line

    def test_extra_forbidden_renders_end_to_end(self) -> None:
        """The whole path (parse -> errors -> format) yields the clear message."""
        text = (
            "---\n"
            "title: T\n"
            "status: planning\n"
            "priority: high\n"
            "depends_on:\n"
            "- other-plan.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "---\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(text)
        lines = format_validation_errors(exc_info.value.errors)
        assert any("depends_on belongs on a step" in line for line in lines)


class TestParseErrors:
    def test_missing_frontmatter_is_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_plan(_fixture("no_frontmatter.md"))

    def test_unclosed_frontmatter_is_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_plan(_fixture("unclosed_frontmatter.md"))

    def test_empty_string_is_parse_error(self) -> None:
        with pytest.raises(ParseError):
            parse_plan_text("")

    def test_invalid_yaml_in_frontmatter_is_parse_error(self) -> None:
        text = "---\n: : :\ntitle: x\n---\nbody\n"
        with pytest.raises(ParseError):
            parse_plan_text(text)

    def test_non_mapping_frontmatter_is_parse_error(self) -> None:
        text = "---\n- just\n- a\n- list\n---\nbody\n"
        with pytest.raises(ParseError):
            parse_plan_text(text)


class TestRoundTrip:
    def test_body_preserved_byte_for_byte(self, tmp_path: Path) -> None:
        original = _fixture("well_formed.md").read_text(encoding="utf-8")
        target = tmp_path / "plan.md"
        target.write_text(original, encoding="utf-8")

        plan = parse_plan(target)
        write_plan(target, plan)

        new_text = target.read_text(encoding="utf-8")
        # Body (everything after the closing ---) must be identical.
        original_body = original.split("---", 2)[2]
        new_body = new_text.split("---", 2)[2]
        assert new_body == original_body

    def test_status_update_persists(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_fixture("well_formed.md").read_text(encoding="utf-8"), encoding="utf-8")

        plan = parse_plan(target)
        # Advance: step 2 done, step 3 becomes current.
        plan.step_by_id(2).status = StepStatus.DONE
        plan.step_by_id(3).status = StepStatus.CURRENT
        write_plan(target, plan)

        reloaded = parse_plan(target)
        assert reloaded.step_by_id(2).status == StepStatus.DONE
        assert reloaded.step_by_id(3).status == StepStatus.CURRENT
        assert reloaded.step_by_id(1).status == StepStatus.DONE
        # Exactly one current step, still valid.
        assert reloaded.current_step() is not None
        assert reloaded.current_step().id == 3

    def test_write_rejects_invalid_mutation(self, tmp_path: Path) -> None:
        """Pydantic doesn't re-run validators on field assignment. write_plan must."""
        target = tmp_path / "plan.md"
        target.write_text(_fixture("well_formed.md").read_text(encoding="utf-8"), encoding="utf-8")

        plan = parse_plan(target)
        # Introduce a two-current invariant violation via raw attribute assignment.
        plan.step_by_id(1).status = StepStatus.CURRENT  # step 2 is already current

        with pytest.raises(ValidationError) as exc_info:
            write_plan(target, plan)
        assert "current" in str(exc_info.value).lower()

    def test_default_values_elided_on_write(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_fixture("well_formed.md").read_text(encoding="utf-8"), encoding="utf-8")

        plan = parse_plan(target)
        write_plan(target, plan)

        rewritten = target.read_text(encoding="utf-8")
        # Step 3 in the fixture has no explicit status/files/complexity/detail;
        # they must not appear in the rewritten frontmatter either.
        step3_region = rewritten.split("id: 3", 1)[1].split("---", 1)[0]
        assert "status:" not in step3_region
        assert "files:" not in step3_region
        assert "complexity:" not in step3_region
        assert "detail:" not in step3_region


class TestConcurrentModificationGuard:
    """write_plan is compare-and-swap: it refuses to overwrite a plan whose
    on-disk frontmatter changed since it was parsed in-process, so a
    concurrent external edit isn't silently clobbered by a stale snapshot.
    """

    def _seed(self, tmp_path: Path) -> Path:
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("well_formed.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return target

    def test_clean_write_after_parse_succeeds(self, tmp_path: Path) -> None:
        target = self._seed(tmp_path)
        plan = parse_plan(target)
        plan.step_by_id(2).status = StepStatus.DONE
        plan.step_by_id(3).status = StepStatus.CURRENT
        write_plan(target, plan)  # no concurrent edit → passes
        assert parse_plan(target).step_by_id(2).status == StepStatus.DONE

    def test_concurrent_frontmatter_edit_is_refused(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import ConcurrentModificationError

        target = self._seed(tmp_path)
        plan = parse_plan(target)
        plan.step_by_id(2).status = StepStatus.DONE

        # Simulate an external editor changing the frontmatter mid-flight.
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "title: Third step", "title: Third step EDITED"
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConcurrentModificationError, match="changed on disk"):
            write_plan(target, plan)
        # The external edit is intact — not clobbered.
        assert "EDITED" in target.read_text(encoding="utf-8")

    def test_expect_unchanged_false_forces_the_write(
        self, tmp_path: Path
    ) -> None:
        target = self._seed(tmp_path)
        plan = parse_plan(target)
        plan.step_by_id(2).status = StepStatus.DONE
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "title: Third step", "title: Third step EDITED"
            ),
            encoding="utf-8",
        )
        # Explicit override: write regardless of the concurrent edit.
        write_plan(target, plan, expect_unchanged=False)
        assert parse_plan(target).step_by_id(2).status == StepStatus.DONE

    def test_body_only_edit_does_not_trip_guard(self, tmp_path: Path) -> None:
        """A concurrent body edit is preserved by write_plan and must not
        trip the frontmatter-scoped guard."""
        target = self._seed(tmp_path)
        plan = parse_plan(target)
        plan.step_by_id(2).status = StepStatus.DONE
        # Append to the prose body only (after the closing fence).
        target.write_text(
            target.read_text(encoding="utf-8") + "\nAdded body line.\n",
            encoding="utf-8",
        )
        write_plan(target, plan)  # body change is safe → no raise
        new_text = target.read_text(encoding="utf-8")
        assert "Added body line." in new_text
        assert parse_plan(target).step_by_id(2).status == StepStatus.DONE

    def test_unparsed_path_writes_through(self, tmp_path: Path) -> None:
        """A file never parsed in-process has no provenance, so write_plan
        can't (and shouldn't) check it — it writes through."""
        target = self._seed(tmp_path)
        # Build a Plan without parsing `target` (parse a copy elsewhere).
        other = tmp_path / "other.md"
        other.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        plan = parse_plan(other)
        plan.step_by_id(2).status = StepStatus.DONE
        write_plan(target, plan)  # no provenance for `target` → no raise
        assert parse_plan(target).step_by_id(2).status == StepStatus.DONE


class TestStatusNote:
    def test_status_note_parsed_when_present(self) -> None:
        plan = parse_plan(_fixture("with_status_note.md"))
        step1 = plan.step_by_id(1)
        step2 = plan.step_by_id(2)
        assert step1.status_note == "Skipped DB migration — already applied in a prior plan."
        assert step2.status_note == "Waiting on credentials from ops."

    def test_status_note_defaults_to_none(self) -> None:
        plan = parse_plan(_fixture("with_status_note.md"))
        # Step 3 omits status_note — should be None.
        assert plan.step_by_id(3).status_note is None

    def test_status_note_persists_on_round_trip(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("with_status_note.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        plan = parse_plan(target)
        plan.step_by_id(3).status_note = "Added after the fact."
        write_plan(target, plan)

        reloaded = parse_plan(target)
        assert reloaded.step_by_id(1).status_note == (
            "Skipped DB migration — already applied in a prior plan."
        )
        assert reloaded.step_by_id(2).status_note == "Waiting on credentials from ops."
        assert reloaded.step_by_id(3).status_note == "Added after the fact."

    def test_status_note_literal_block_preserves_newlines(self) -> None:
        text = (
            "---\n"
            "title: Multi-line Note\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    status: current\n"
            "    status_note: |\n"
            "      a multi-line note\n"
            "      across two lines\n"
            "---\n"
        )
        plan = parse_plan_text(text)
        assert plan.step_by_id(1).status_note == (
            "a multi-line note\nacross two lines\n"
        )

    @pytest.mark.parametrize("bad_value", ["42", "[a, b]", "{a: 1}"])
    def test_status_note_rejects_non_string_types(self, bad_value: str) -> None:
        text = (
            "---\n"
            "title: Bad Note\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            f"    status_note: {bad_value}\n"
            "---\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(text)
        assert "status_note" in str(exc_info.value)

    def test_status_note_omitted_when_unset_on_write(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("well_formed.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        plan = parse_plan(target)
        # No step has status_note set — write_plan must not introduce the field.
        write_plan(target, plan)

        rewritten = target.read_text(encoding="utf-8")
        assert "status_note:" not in rewritten

    def test_regression_guard_original_failure_shape_now_parses(self) -> None:
        # Exact shape that poisoned 5-chat-and-notification-data-access-hardening.md
        # in walk 20260512-192616-reconcile: step with status: current plus a
        # multi-line status_note: | block. Before this plan landed, parse_plan
        # raised ValidationError("Extra inputs are not permitted") on status_note.
        text = (
            "---\n"
            "title: Reproducer\n"
            "status: planning\n"
            "priority: high\n"
            "steps:\n"
            "  - id: 4\n"
            "    title: Document the rule\n"
            "    files:\n"
            "      - docs/architecture.md\n"
            "    status: current\n"
            "    status_note: |\n"
            "      Implementation not yet applied. Absent edits:\n"
            "      (1) top-level section between two anchors;\n"
            "      (2) two declared cross-reference bullet edits.\n"
            "---\n"
        )
        plan = parse_plan_text(text)
        assert plan.step_by_id(4).status == StepStatus.CURRENT
        assert plan.step_by_id(4).status_note is not None
        assert "Absent edits" in plan.step_by_id(4).status_note


class TestIntent:
    """``Plan.intent`` / ``Step.intent``: an optional one-line why, typed only.

    The schema checks the type and nothing else — empty, whitespace-only,
    placeholder, long, and multi-line values all parse. Judging presence is
    ``review.py``'s advisory job, so these cases pin what must *not* raise
    just as hard as what must.
    """

    def test_plan_and_step_intent_default_to_none(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert plan.intent is None
        assert all(step.intent is None for step in plan.steps)

    def test_plan_intent_parses_when_present(self) -> None:
        plan = parse_plan_text(_intent_plan(plan_intent="intent: Carry the why\n"))
        assert plan.intent == "Carry the why"

    def test_step_intent_parses_when_present(self) -> None:
        plan = parse_plan_text(_intent_plan(step_intent="    intent: Mint the field\n"))
        assert plan.step_by_id(1).intent == "Mint the field"

    def test_intent_round_trips_through_write_plan(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _intent_plan(
                plan_intent="intent: Carry the why\n",
                step_intent="    intent: Mint the field\n",
            ),
            encoding="utf-8",
        )

        write_plan(target, parse_plan(target))

        reloaded = parse_plan(target)
        assert reloaded.intent == "Carry the why"
        assert reloaded.step_by_id(1).intent == "Mint the field"
        assert "# Intent body\n\nKeep this prose.\n" in target.read_text(
            encoding="utf-8"
        )

    def test_absent_intent_not_introduced_on_write(self, tmp_path: Path) -> None:
        """The no-migration guard: an unset intent never reaches the file."""
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("well_formed.md").read_text(encoding="utf-8"), encoding="utf-8"
        )

        write_plan(target, parse_plan(target))

        assert "intent:" not in target.read_text(encoding="utf-8")

    @pytest.mark.parametrize("bad_value", ["42", "[a, b]", "{a: 1}"])
    def test_plan_intent_rejects_non_string_types(self, bad_value: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(_intent_plan(plan_intent=f"intent: {bad_value}\n"))
        assert "intent" in str(exc_info.value)

    @pytest.mark.parametrize("bad_value", ["42", "[a, b]", "{a: 1}"])
    def test_step_intent_rejects_non_string_types(self, bad_value: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(_intent_plan(step_intent=f"    intent: {bad_value}\n"))
        assert "intent" in str(exc_info.value)

    def test_empty_intent_is_preserved_not_collapsed(self, tmp_path: Path) -> None:
        """``''`` is not ``None``: only ``None`` is elided on rewrite."""
        target = tmp_path / "plan.md"
        target.write_text(
            _intent_plan(plan_intent="intent: ''\n", step_intent="    intent: ''\n"),
            encoding="utf-8",
        )

        plan = parse_plan(target)
        assert plan.intent == "" and plan.step_by_id(1).intent == ""

        write_plan(target, plan)

        reloaded = parse_plan(target)
        assert reloaded.intent == "" and reloaded.step_by_id(1).intent == ""

    def test_whitespace_only_intent_is_accepted_untrimmed(self) -> None:
        """A blank intent is review.py's advisory finding, not a parse error."""
        plan = parse_plan_text(
            _intent_plan(plan_intent="intent: '   '\n", step_intent="    intent: '  '\n")
        )
        assert plan.intent == "   "
        assert plan.step_by_id(1).intent == "  "

    def test_placeholder_intent_is_accepted(self) -> None:
        """A placeholder is review.py's advisory finding, not a parse error."""
        plan = parse_plan_text(
            _intent_plan(plan_intent="intent: TODO\n", step_intent="    intent: TODO\n")
        )
        assert plan.intent == "TODO"
        assert plan.step_by_id(1).intent == "TODO"

    def test_long_intent_is_accepted(self) -> None:
        """No cap exists anywhere — not in this step, not in any other."""
        long_intent = "why " * 125  # ~500 characters
        plan = parse_plan_text(
            _intent_plan(
                plan_intent=f"intent: '{long_intent}'\n",
                step_intent=f"    intent: '{long_intent}'\n",
            )
        )
        assert plan.intent == long_intent
        assert plan.step_by_id(1).intent == long_intent

    def test_multi_line_intent_keeps_its_newlines(self) -> None:
        """A ``|`` literal block arrives unjoined and untrimmed.

        (A plain multi-line scalar would be folded to one line by YAML itself,
        so a literal block is the only way a newline reaches the field.)
        """
        plan = parse_plan_text(
            _intent_plan(
                plan_intent="intent: |\n  plan why\n  second line\n",
                step_intent="    intent: |\n      step why\n      second line\n",
            )
        )
        assert plan.intent == "plan why\nsecond line\n"
        assert plan.step_by_id(1).intent == "step why\nsecond line\n"

    def test_unknown_field_message_lists_intent_for_both_containers(self) -> None:
        """Cheap proof the field landed on both models: the allowed-field list
        in ``_explain_extra_field`` is derived from ``model_fields``."""
        (plan_line,) = format_validation_errors(
            [{"type": "extra_forbidden", "loc": ("nope",), "msg": "x"}]
        )
        (step_line,) = format_validation_errors(
            [{"type": "extra_forbidden", "loc": ("steps", 0, "nope"), "msg": "x"}]
        )
        assert "unknown plan-level field" in plan_line and "intent" in plan_line
        assert "unknown step field" in step_line and "intent" in step_line


class TestRiskProfile:
    def test_legacy_omission_uses_effective_standard_without_declaration(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_risk_profile_plan(), encoding="utf-8")

        plan = parse_plan(target)

        assert plan.risk_profile is None
        assert plan.risk_profile_rationale is None
        assert plan.effective_risk_profile is RiskProfile.STANDARD

        write_plan(target, plan)

        frontmatter = target.read_text(encoding="utf-8").split("---", 2)[1]
        assert "risk_profile:" not in frontmatter
        assert "risk_profile_rationale:" not in frontmatter

    @pytest.mark.parametrize("tier", ["low", "standard", "high"])
    def test_declaration_accepts_each_closed_tier(self, tier: str) -> None:
        plan = parse_plan_text(
            _risk_profile_plan(
                f"risk_profile: {tier}\n"
                "risk_profile_rationale: Bounded and reviewable work.\n"
            )
        )

        assert plan.risk_profile is RiskProfile(tier)
        assert plan.risk_profile_rationale == "Bounded and reviewable work."
        assert plan.effective_risk_profile is RiskProfile(tier)

    def test_risk_profile_rejects_unknown_tier(self) -> None:
        with pytest.raises(ValidationError, match="risk_profile"):
            parse_plan_text(
                _risk_profile_plan(
                    "risk_profile: urgent\n"
                    "risk_profile_rationale: Bounded work.\n"
                )
            )

    @pytest.mark.parametrize(
        "declaration",
        [
            "risk_profile: low\n",
            "risk_profile_rationale: Bounded work.\n",
        ],
    )
    def test_risk_profile_requires_tier_and_rationale_together(
        self, declaration: str
    ) -> None:
        with pytest.raises(ValidationError, match="risk_profile"):
            parse_plan_text(_risk_profile_plan(declaration))

    @pytest.mark.parametrize(
        "declaration",
        [
            "risk_profile: null\nrisk_profile_rationale: Bounded work.\n",
            "risk_profile: low\nrisk_profile_rationale: null\n",
            "risk_profile: null\nrisk_profile_rationale: null\n",
        ],
    )
    def test_risk_profile_rejects_every_explicit_null_shape(
        self, declaration: str
    ) -> None:
        with pytest.raises(ValidationError, match="explicitly null"):
            parse_plan_text(_risk_profile_plan(declaration))

    @pytest.mark.parametrize(
        "rationale",
        [
            "risk_profile_rationale: ''\n",
            "risk_profile_rationale: '   '\n",
            "risk_profile_rationale: |\n  first line\n  second line\n",
        ],
    )
    def test_risk_profile_rationale_rejects_blank_or_multiline_text(
        self, rationale: str
    ) -> None:
        with pytest.raises(ValidationError, match="risk_profile_rationale"):
            parse_plan_text(_risk_profile_plan(f"risk_profile: low\n{rationale}"))

    def test_explicit_risk_profile_renders_and_reloads(self) -> None:
        plan = parse_plan_text(
            _risk_profile_plan(
                "risk_profile: high\n"
                "risk_profile_rationale: Changes a public execution boundary.\n"
            )
        )

        rendered = render_plan_text(plan, "# Rendered body\n")

        assert "risk_profile: high" in rendered
        assert "risk_profile_rationale: Changes a public execution boundary." in rendered
        reloaded = parse_plan_text(rendered)
        assert reloaded.risk_profile is RiskProfile.HIGH
        assert reloaded.risk_profile_rationale == "Changes a public execution boundary."

    def test_explicit_risk_profile_round_trips_through_write_plan(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _risk_profile_plan(
                "risk_profile: standard\n"
                "risk_profile_rationale: Bounded parser contract.\n"
            ),
            encoding="utf-8",
        )

        write_plan(target, parse_plan(target))

        reloaded = parse_plan(target)
        assert reloaded.risk_profile is RiskProfile.STANDARD
        assert reloaded.risk_profile_rationale == "Bounded parser contract."
        frontmatter = target.read_text(encoding="utf-8").split("---", 2)[1]
        assert "risk_profile: standard" in frontmatter
        assert "risk_profile_rationale: Bounded parser contract." in frontmatter

    def test_risk_profile_is_exported_from_plan_tool(self) -> None:
        from plan_tool.schema import RiskProfile as SchemaRiskProfile

        assert RiskProfile is SchemaRiskProfile


def _source_seed_plan(source_seed: str = "") -> str:
    return (
        "---\n"
        "title: Source Seed Plan\n"
        f"{source_seed}"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "---\n"
        "# Source seed body\n\nKeep this prose.\n"
    )


class TestSourceSeed:
    """``Plan.source_seed`` (BACKLOG #162) — a plain optional path string.

    The schema checks the type only; ``create`` decides when to write it and
    ``review.py`` decides how to resolve it. These pin round-trip parity with
    the field's ``registered_by``/``intent`` siblings.
    """

    def test_source_seed_defaults_to_none(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert plan.source_seed is None

    def test_source_seed_parses_when_present(self) -> None:
        plan = parse_plan_text(
            _source_seed_plan(source_seed="source_seed: plan-seeds/example.md\n")
        )
        assert plan.source_seed == "plan-seeds/example.md"

    def test_source_seed_round_trips_through_write_plan(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _source_seed_plan(source_seed="source_seed: plan-seeds/example.md\n"),
            encoding="utf-8",
        )

        write_plan(target, parse_plan(target))

        reloaded = parse_plan(target)
        assert reloaded.source_seed == "plan-seeds/example.md"

    def test_absent_source_seed_not_introduced_on_write(self, tmp_path: Path) -> None:
        """The no-migration guard: an unset source_seed never reaches the file."""
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("well_formed.md").read_text(encoding="utf-8"), encoding="utf-8"
        )

        write_plan(target, parse_plan(target))

        assert "source_seed:" not in target.read_text(encoding="utf-8")

    @pytest.mark.parametrize("bad_value", ["42", "[a, b]", "{a: 1}"])
    def test_source_seed_rejects_non_string_types(self, bad_value: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(_source_seed_plan(source_seed=f"source_seed: {bad_value}\n"))
        assert "source_seed" in str(exc_info.value)


class TestNextRunnable:
    def test_returns_first_pending_with_deps_met(self) -> None:
        text = (
            "---\n"
            "title: Next Runnable\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: Two\n"
            "    depends_on: [1]\n"
            "  - id: 3\n"
            "    title: Three\n"
            "    depends_on: [2]\n"
            "---\n"
        )
        plan = parse_plan_text(text)
        nxt = plan.next_runnable_step()
        assert nxt is not None
        assert nxt.id == 2

    def test_returns_none_when_all_done(self) -> None:
        text = (
            "---\n"
            "title: All Done\n"
            "status: completed\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    status: done\n"
            "---\n"
        )
        plan = parse_plan_text(text)
        assert plan.next_runnable_step() is None


_THREE_TYPED_STEPS = (
    "---\n"
    "title: Typed Steps\n"
    "status: planning\n"
    "priority: low\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: Tidy internals\n"
    "    change_type: refactor\n"
    "  - id: 2\n"
    "    title: Add the widget\n"
    "    change_type: feature\n"
    "  - id: 3\n"
    "    title: Wire the deploy\n"
    "    change_type: non-code\n"
    "---\n"
)


class TestChangeType:
    def test_step_change_type_absent_by_default(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert all(s.change_type is None for s in plan.steps)

    def test_step_change_type_parses_all_three_values(self) -> None:
        plan = parse_plan_text(_THREE_TYPED_STEPS)
        assert plan.step_by_id(1).change_type is ChangeType.REFACTOR
        assert plan.step_by_id(2).change_type is ChangeType.FEATURE
        assert plan.step_by_id(3).change_type is ChangeType.NON_CODE

    def test_step_change_type_invalid_value_rejected(self) -> None:
        text = (
            "---\n"
            "title: Bad Type\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    change_type: chore\n"
            "---\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(text)
        msg = str(exc_info.value).lower()
        assert "change_type" in msg or "refactor" in msg

    def test_change_type_round_trips_through_write_plan(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_THREE_TYPED_STEPS, encoding="utf-8")

        write_plan(target, parse_plan(target))

        reloaded = parse_plan(target)
        assert reloaded.step_by_id(1).change_type is ChangeType.REFACTOR
        assert reloaded.step_by_id(2).change_type is ChangeType.FEATURE
        assert reloaded.step_by_id(3).change_type is ChangeType.NON_CODE

    def test_change_type_none_elided_on_write(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("well_formed.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        write_plan(target, parse_plan(target))

        rewritten = target.read_text(encoding="utf-8")
        frontmatter = rewritten.split("---", 2)[1]
        assert "change_type:" not in frontmatter


_GATED_STEP = (
    "---\n"
    "title: Gated Step\n"
    "status: planning\n"
    "priority: low\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: Land the parser\n"
    "    gate:\n"
    "      - uv run pytest -q\n"
    "      - grep -q foo bar.py\n"
    "---\n"
)


class TestGate:
    def test_gate_absent_defaults_to_empty_list(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert all(s.gate == [] for s in plan.steps)

    def test_gate_parses_list_of_commands(self) -> None:
        plan = parse_plan_text(_GATED_STEP)
        assert plan.step_by_id(1).gate == ["uv run pytest -q", "grep -q foo bar.py"]

    def test_gate_round_trips_through_write_plan(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_GATED_STEP, encoding="utf-8")

        write_plan(target, parse_plan(target))

        reloaded = parse_plan(target)
        assert reloaded.step_by_id(1).gate == [
            "uv run pytest -q",
            "grep -q foo bar.py",
        ]

    def test_gate_empty_elided_on_write(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("well_formed.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        write_plan(target, parse_plan(target))

        rewritten = target.read_text(encoding="utf-8")
        frontmatter = rewritten.split("---", 2)[1]
        assert "gate:" not in frontmatter

    def test_gate_rejects_empty_string_entry(self) -> None:
        text = (
            "---\n"
            "title: Empty Gate\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            '    gate: [""]\n'
            "---\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(text)
        assert "gate" in str(exc_info.value)

    def test_gate_rejects_whitespace_only_entry(self) -> None:
        text = (
            "---\n"
            "title: Whitespace Gate\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            '    gate: ["   "]\n'
            "---\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(text)
        assert "gate" in str(exc_info.value)

    def test_gate_rejects_non_string_entry(self) -> None:
        text = (
            "---\n"
            "title: Non-string Gate\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    gate: [42]\n"
            "---\n"
        )
        with pytest.raises(ValidationError):
            parse_plan_text(text)

    def test_gate_rejects_scalar_not_list(self) -> None:
        text = (
            "---\n"
            "title: Scalar Gate\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    gate: uv run pytest\n"
            "---\n"
        )
        with pytest.raises(ValidationError):
            parse_plan_text(text)


_FEATURE_PLAN = (
    "---\n"
    "title: Feature Plan\n"
    "status: planning\n"
    "priority: low\n"
    "features:\n"
    "  - id: merge-transform\n"
    "    title: Merge transform pipeline\n"
    "  - id: suppression-flag\n"
    "    title: Suppression flag handling\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: Build the merge transform\n"
    "    features:\n"
    "      - merge-transform\n"
    "      - suppression-flag\n"
    "  - id: 2\n"
    "    title: Wire it in\n"
    "---\n"
)


class TestFeatures:
    def test_features_absent_default_empty(self) -> None:
        plan = parse_plan(_fixture("well_formed.md"))
        assert plan.features == []
        assert all(s.features == [] for s in plan.steps)

    def test_feature_registry_parses(self) -> None:
        plan = parse_plan_text(_FEATURE_PLAN)
        assert [(f.id, f.title) for f in plan.features] == [
            ("merge-transform", "Merge transform pipeline"),
            ("suppression-flag", "Suppression flag handling"),
        ]

    def test_step_features_tag_parses(self) -> None:
        plan = parse_plan_text(_FEATURE_PLAN)
        assert plan.step_by_id(1).features == [
            "merge-transform",
            "suppression-flag",
        ]
        assert plan.step_by_id(2).features == []

    def test_feature_block_round_trips(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_FEATURE_PLAN, encoding="utf-8")

        write_plan(target, parse_plan(target))

        reloaded = parse_plan(target)
        assert [(f.id, f.title) for f in reloaded.features] == [
            ("merge-transform", "Merge transform pipeline"),
            ("suppression-flag", "Suppression flag handling"),
        ]
        assert reloaded.step_by_id(1).features == [
            "merge-transform",
            "suppression-flag",
        ]

    def test_features_empty_elided_on_write(self, tmp_path: Path) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _fixture("well_formed.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        write_plan(target, parse_plan(target))

        rewritten = target.read_text(encoding="utf-8")
        frontmatter = rewritten.split("---", 2)[1]
        assert "features:" not in frontmatter

    def test_unknown_feature_key_rejected(self) -> None:
        text = (
            "---\n"
            "title: Bad Feature\n"
            "status: planning\n"
            "priority: low\n"
            "features:\n"
            "  - id: merge-transform\n"
            "    title: Merge\n"
            "    steps: [1]\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "---\n"
        )
        with pytest.raises(ValidationError):
            parse_plan_text(text)

    def test_feature_missing_title_rejected(self) -> None:
        text = (
            "---\n"
            "title: No Title\n"
            "status: planning\n"
            "priority: low\n"
            "features:\n"
            "  - id: merge-transform\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "---\n"
        )
        with pytest.raises(ValidationError):
            parse_plan_text(text)

    def test_step_features_rejects_non_string_entry(self) -> None:
        text = (
            "---\n"
            "title: Bad Tag\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    features: [42]\n"
            "---\n"
        )
        with pytest.raises(ValidationError):
            parse_plan_text(text)

    def test_malformed_feature_refs_still_parse(self) -> None:
        # Duplicate id, non-kebab id, and a step.features id with no matching
        # registry entry — all semantically wrong, none parse-fatal. Pins that
        # step 1 added no validator; run/jira/detail stay inert.
        text = (
            "---\n"
            "title: Malformed Refs\n"
            "status: planning\n"
            "priority: low\n"
            "features:\n"
            "  - id: merge-transform\n"
            "    title: Merge one\n"
            "  - id: merge-transform\n"
            "    title: Merge dup\n"
            "  - id: Merge_Transform\n"
            "    title: Non kebab\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    features:\n"
            "      - does-not-exist\n"
            "---\n"
        )
        plan = parse_plan_text(text)
        assert isinstance(plan, Plan)
        assert plan.step_by_id(1).features == ["does-not-exist"]

    def test_feature_imported_from_schema(self) -> None:
        from plan_tool.schema import Feature

        assert Feature(id="x", title="Y").id == "x"


def _format_version_plan(declaration: str = "", extra: str = "") -> str:
    return (
        "---\n"
        "title: Format version plan\n"
        f"{declaration}"
        "status: planning\n"
        "priority: low\n"
        f"{extra}"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "---\n"
        "# Format version body\n\nKeep this prose.\n"
    )


class TestFormatVersion:
    def test_absent_format_version_parses_as_legacy_one_and_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Absence must mean legacy version 1 even once the current/supported
        window has advanced — proves the absence branch hardcodes the
        literal 1 rather than reading the current-version constant."""
        import plan_tool.parser as parser_module
        import plan_tool.schema as schema_module

        monkeypatch.setattr(schema_module, "PLAN_FORMAT_VERSION", 2)
        monkeypatch.setattr(
            parser_module, "SUPPORTED_PLAN_FORMAT_VERSIONS", frozenset({1, 2})
        )

        plan = parse_plan_text(_format_version_plan())

        assert plan.format_version == 1

    def test_declared_current_version_parses_identically(self) -> None:
        plan = parse_plan_text(_format_version_plan("format_version: 1\n"))

        assert plan.format_version == 1

    def test_declared_unsupported_version_is_refused_by_name(self) -> None:
        with pytest.raises(UnsupportedPlanFormatVersionError) as exc_info:
            parse_plan_text(_format_version_plan("format_version: 999\n"))

        message = str(exc_info.value)
        assert "999" in message
        assert str(sorted(SUPPORTED_PLAN_FORMAT_VERSIONS)) in message

    def test_unsupported_format_version_error_is_a_validation_error_subtype(
        self,
    ) -> None:
        """Every existing ``except ValidationError`` site must keep catching
        this without changes, so the subclass relationship is pinned
        directly rather than left to be an accident of implementation."""
        with pytest.raises(ValidationError):
            parse_plan_text(_format_version_plan("format_version: 999\n"))

    def test_gate_fires_before_unknown_field_rejection(self) -> None:
        """An unsupported version must be reported for the version, not the
        unrelated key — regression test for checking format_version inside
        Plan.model_validate instead of on the raw mapping first."""
        with pytest.raises(UnsupportedPlanFormatVersionError):
            parse_plan_text(
                _format_version_plan(
                    "format_version: 999\n", extra="some_unknown_field: x\n"
                )
            )

    @pytest.mark.parametrize(
        "declaration",
        [
            'format_version: "1"\n',
            "format_version: true\n",
            "format_version: 1.5\n",
            "format_version: null\n",
        ],
    )
    def test_non_integer_declared_values_fail_closed(self, declaration: str) -> None:
        with pytest.raises(UnsupportedPlanFormatVersionError):
            parse_plan_text(_format_version_plan(declaration))

    def test_overlong_format_version_is_a_parse_error_not_a_raw_value_error(
        self,
    ) -> None:
        with pytest.raises(ParseError, match="invalid YAML in frontmatter"):
            parse_plan_text(_format_version_plan(f"format_version: {'9' * 5000}\n"))

    def test_format_version_default_is_a_supported_version(self) -> None:
        assert PLAN_FORMAT_VERSION in SUPPORTED_PLAN_FORMAT_VERSIONS

    def test_absent_format_version_round_trips_through_write_plan(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "plan.md"
        original = _format_version_plan()
        target.write_text(original, encoding="utf-8")
        assert "format_version:" not in original

        plan = parse_plan(target)
        write_plan(target, plan)

        rewritten = target.read_text(encoding="utf-8")
        assert f"format_version: {PLAN_FORMAT_VERSION}" in rewritten
        reloaded = parse_plan(target)
        assert reloaded.format_version == PLAN_FORMAT_VERSION

    def test_raw_absent_plan_refuses_serialization_after_a_future_current_version_bump(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A ``Plan`` field default must never silently relabel raw absence
        as a future current version. The parser's explicit legacy-1
        injection pins the effective version at 1 regardless of a later
        current-version bump, so both serializers must keep refusing to
        stamp it as current until the plan takes its explicit raw upgrade."""
        import plan_tool.parser as parser_module
        import plan_tool.schema as schema_module

        monkeypatch.setattr(schema_module, "PLAN_FORMAT_VERSION", 2)
        monkeypatch.setattr(parser_module, "PLAN_FORMAT_VERSION", 2)
        monkeypatch.setattr(
            parser_module, "SUPPORTED_PLAN_FORMAT_VERSIONS", frozenset({1, 2})
        )

        plan = parse_plan_text(_format_version_plan())
        assert plan.format_version == 1

        with pytest.raises(ValidationError) as render_exc:
            render_plan_text(plan, "# Format version body\n")
        message = str(render_exc.value)
        assert "1" in message
        assert "2" in message

        target = tmp_path / "plan.md"
        target.write_text(_format_version_plan(), encoding="utf-8")
        plan_on_disk = parse_plan(target)
        with pytest.raises(ValidationError):
            write_plan(target, plan_on_disk)

    def test_declared_current_format_version_round_trips_through_write_plan(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "plan.md"
        target.write_text(
            _format_version_plan("format_version: 1\n"), encoding="utf-8"
        )

        plan = parse_plan(target)
        write_plan(target, plan)

        rewritten = target.read_text(encoding="utf-8")
        assert f"format_version: {PLAN_FORMAT_VERSION}" in rewritten
        reloaded = parse_plan(target)
        assert reloaded.format_version == PLAN_FORMAT_VERSION

    def test_write_plan_stamps_the_current_declaration_in_rendered_text(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "plan.md"
        target.write_text(_format_version_plan(), encoding="utf-8")

        write_plan(target, parse_plan(target))

        frontmatter = target.read_text(encoding="utf-8").split("---", 2)[1]
        assert f"format_version: {PLAN_FORMAT_VERSION}" in frontmatter

    def test_render_plan_text_stamps_the_current_declaration(self) -> None:
        plan = parse_plan_text(_format_version_plan())

        rendered = render_plan_text(plan, "# Format version body\n")

        assert f"format_version: {PLAN_FORMAT_VERSION}" in rendered
        reloaded = parse_plan_text(rendered)
        assert reloaded.format_version == PLAN_FORMAT_VERSION

    def test_write_plan_refuses_a_hand_mutated_ineligible_format_version(
        self, tmp_path: Path
    ) -> None:
        """Mirrors ``test_write_rejects_invalid_mutation``'s technique for a
        different field: pydantic does not re-run validators on a raw
        post-construction attribute assignment, so ``write_plan`` must
        catch an ineligible ``format_version`` itself."""
        target = tmp_path / "plan.md"
        target.write_text(_format_version_plan(), encoding="utf-8")

        plan = parse_plan(target)
        plan.format_version = 0

        with pytest.raises(ValidationError) as exc_info:
            write_plan(target, plan)
        message = str(exc_info.value)
        assert "0" in message
        assert str(PLAN_FORMAT_VERSION) in message

    def test_write_plan_refusal_leaves_the_file_on_disk_untouched(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "plan.md"
        original = _format_version_plan()
        target.write_text(original, encoding="utf-8")

        plan = parse_plan(target)
        plan.format_version = 0

        with pytest.raises(ValidationError):
            write_plan(target, plan)

        assert target.read_text(encoding="utf-8") == original

    def test_render_plan_text_refuses_a_hand_mutated_ineligible_format_version(
        self,
    ) -> None:
        plan = parse_plan_text(_format_version_plan())
        plan.format_version = 0

        with pytest.raises(ValidationError) as exc_info:
            render_plan_text(plan, "# Format version body\n")
        message = str(exc_info.value)
        assert "0" in message
        assert str(PLAN_FORMAT_VERSION) in message

    def test_stamped_plan_is_rejected_by_a_pre_declaration_strict_fixture(
        self, tmp_path: Path
    ) -> None:
        """Proves the one-way bootstrap rather than asserting and hoping: a
        plan-tool build that predates ``format_version`` has no such field
        on its ``Plan`` model, so in strict (``extra="forbid"``) mode it
        rejects a plan this build wrote for carrying an unrecognized key."""
        import yaml
        from pydantic import BaseModel, ConfigDict
        from pydantic import ValidationError as PydanticValidationError

        class _PreDeclarationPlan(BaseModel):
            model_config = ConfigDict(extra="forbid")

            title: str
            status: str
            priority: str
            steps: list[dict]

        target = tmp_path / "plan.md"
        target.write_text(_format_version_plan(), encoding="utf-8")
        write_plan(target, parse_plan(target))

        frontmatter_yaml = target.read_text(encoding="utf-8").split("---", 2)[1]
        raw = yaml.safe_load(frontmatter_yaml)

        with pytest.raises(PydanticValidationError) as exc_info:
            _PreDeclarationPlan.model_validate(raw)
        assert "format_version" in str(exc_info.value)


def _raw_plan_mapping(declaration: str = "") -> dict[str, Any]:
    """Return unparsed plan frontmatter in the requested declared state."""
    doc = split_plan_document(_format_version_plan(declaration))
    raw = yaml.safe_load(doc.frontmatter_yaml)
    assert isinstance(raw, dict)
    return raw


class TestUpgradePlanFrontmatterToCurrent:
    def test_absent_declaration_upgrades_to_the_current_version(self) -> None:
        raw = _raw_plan_mapping()
        assert "format_version" not in raw

        upgraded = upgrade_plan_frontmatter_to_current(raw)

        assert upgraded["format_version"] == PLAN_FORMAT_VERSION

    def test_upgrade_reads_the_raw_state_not_a_readers_defaulted_version(
        self,
    ) -> None:
        """An absent declaration must remain an observable transition."""
        raw = _raw_plan_mapping()

        upgraded = upgrade_plan_frontmatter_to_current(raw)

        assert upgraded != raw
        assert upgraded["format_version"] == PLAN_FORMAT_VERSION

    def test_upgrade_preserves_every_other_frontmatter_key_unchanged(
        self,
    ) -> None:
        raw = _raw_plan_mapping()

        upgraded = upgrade_plan_frontmatter_to_current(raw)

        for key, value in raw.items():
            assert upgraded[key] == value

    def test_upgrade_does_not_mutate_the_caller_mapping(self) -> None:
        raw = _raw_plan_mapping()

        upgrade_plan_frontmatter_to_current(raw)

        assert "format_version" not in raw

    def test_current_declaration_upgrades_to_an_equal_mapping(self) -> None:
        raw = _raw_plan_mapping("format_version: 1\n")

        upgraded = upgrade_plan_frontmatter_to_current(raw)

        assert upgraded == raw

    def test_upgrade_refuses_an_unsupported_declared_version_by_name(
        self,
    ) -> None:
        raw = _raw_plan_mapping("format_version: 999\n")

        with pytest.raises(UnsupportedPlanFormatVersionError) as exc_info:
            upgrade_plan_frontmatter_to_current(raw)

        message = str(exc_info.value)
        assert "999" in message
        assert str(sorted(SUPPORTED_PLAN_FORMAT_VERSIONS)) in message

    @pytest.mark.parametrize(
        "declaration",
        [
            'format_version: "1"\n',
            "format_version: true\n",
            "format_version: 1.5\n",
            "format_version: null\n",
        ],
    )
    def test_upgrade_refuses_a_malformed_declaration_rather_than_treating_it_as_absent(
        self, declaration: str
    ) -> None:
        raw = _raw_plan_mapping(declaration)

        with pytest.raises(UnsupportedPlanFormatVersionError):
            upgrade_plan_frontmatter_to_current(raw)

    @pytest.mark.parametrize(
        "declaration",
        [
            "",
            "format_version: 999\n",
            'format_version: "1"\n',
            "format_version: true\n",
            "format_version: 1.5\n",
            "format_version: null\n",
        ],
    )
    def test_upgrade_refuses_exactly_what_the_reader_gate_refuses(
        self, declaration: str
    ) -> None:
        """Pins the single-decision invariant: the reader gate and the
        upgrader must never disagree about which declared values are
        acceptable, because the upgrader calls the same gate rather than
        re-deriving its own accepted-state set."""
        gate_raised = False
        try:
            _require_supported_plan_format_version(_raw_plan_mapping(declaration))
        except UnsupportedPlanFormatVersionError:
            gate_raised = True

        upgrade_raised = False
        try:
            upgrade_plan_frontmatter_to_current(_raw_plan_mapping(declaration))
        except UnsupportedPlanFormatVersionError:
            upgrade_raised = True

        assert gate_raised == upgrade_raised

    def test_upgraded_mapping_still_validates_as_a_plan(self) -> None:
        raw = _raw_plan_mapping()

        upgraded = upgrade_plan_frontmatter_to_current(raw)

        Plan.model_validate(upgraded)  # raises nothing

    def test_every_plan_state_has_a_declared_upgrade_path_to_current(
        self,
    ) -> None:
        for state in (None, *sorted(SUPPORTED_PLAN_FORMAT_VERSIONS)):
            declaration = "" if state is None else f"format_version: {state}\n"
            raw = _raw_plan_mapping(declaration)

            upgraded = upgrade_plan_frontmatter_to_current(raw)

            assert upgraded["format_version"] == PLAN_FORMAT_VERSION, state

    def test_adding_a_supported_plan_version_without_a_path_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new supported value needs a coded upgrade route."""
        import plan_tool.parser as parser_module

        monkeypatch.setattr(
            parser_module, "SUPPORTED_PLAN_FORMAT_VERSIONS", frozenset({1, 2})
        )
        raw = _raw_plan_mapping("format_version: 2\n")

        with pytest.raises(NotImplementedError):
            upgrade_plan_frontmatter_to_current(raw)


class TestStepDescriptionAlias:
    @staticmethod
    def plan_data(step):
        return dict(title="Plan", status="planning", priority="medium", steps=[step])

    @classmethod
    def plan_text(cls, step, **extra):
        return "---\n" + yaml.safe_dump(cls.plan_data(step) | extra) + "---\n# Body\n"

    @classmethod
    def validate_step(cls, entry, data):
        if entry == "constructor":
            return Step(**data)
        if entry == "model":
            return Step.model_validate(data)
        if entry == "plan":
            return Plan.model_validate(cls.plan_data(data)).steps[0]
        return parse_plan_text(cls.plan_text(data)).steps[0]

    @pytest.mark.parametrize("entry", ["constructor", "model", "plan", "parser"])
    @pytest.mark.parametrize("key", ["description", "title"])
    def test_step_accepts_either_text_key_through_shared_validation(self, entry, key):
        assert self.validate_step(entry, {"id": 1, key: "Exact text"}).title == "Exact text"

    @pytest.mark.parametrize("entry", ["constructor", "model", "plan", "parser"])
    @pytest.mark.parametrize("keys", [("description", "title"), ("title", "description")])
    def test_equal_dual_keys_are_accepted_in_either_key_order(self, entry, keys):
        data = {"id": 1, **dict.fromkeys(keys, "Same")}
        assert self.validate_step(entry, data).title == "Same"

    @pytest.mark.parametrize("entry", ["model", "parser"])
    @pytest.mark.parametrize("other", ["Different", "same", "Same "])
    def test_conflicting_dual_keys_name_both_keys_in_error(self, entry, other):
        with pytest.raises((ModelValidationError, ValidationError), match="description and title conflict; supply only one key"):
            self.validate_step(entry, dict(id=1, description="Same", title=other))

    @pytest.mark.parametrize("entry", ["constructor", "model", "plan", "parser"])
    @pytest.mark.parametrize("invalid", [None, 42, True, [], {}])
    @pytest.mark.parametrize("key", ["description", "title"])
    @pytest.mark.parametrize("peer", ["absent", "valid", "invalid"])
    def test_invalid_alias_is_not_hidden_by_valid_peer(self, entry, invalid, key, peer):
        data = {"id": 1, key: invalid}
        if peer != "absent":
            data["title" if key == "description" else "description"] = "Valid" if peer == "valid" else invalid
        with pytest.raises((ModelValidationError, ValidationError)):
            self.validate_step(entry, data)

    @pytest.mark.parametrize("entry", ["constructor", "model", "plan", "parser"])
    def test_missing_both_text_keys_remains_invalid(self, entry):
        with pytest.raises((ModelValidationError, ValidationError), match="title"):
            self.validate_step(entry, {"id": 1})

    @pytest.mark.parametrize("key", ["description", "title"])
    @pytest.mark.parametrize("value", ["", "  ", "世界 🌍", "First\nSecond\n"])
    @pytest.mark.parametrize("entry", ["constructor", "model", "plan", "parser"])
    def test_step_text_is_preserved_without_new_content_restrictions(self, entry, key, value):
        assert self.validate_step(entry, {"id": 1, key: value}).title == value

    @pytest.mark.parametrize("other", ["same", "Same ", " Same", "Same\n"])
    def test_dual_key_equality_does_not_trim_or_fold_text(self, other):
        with pytest.raises(ModelValidationError, match="conflict"):
            Step(id=1, title="Same", description=other)

    @pytest.mark.parametrize("extra", [{}, {"title": "Same"}, {"title": "Other"}, {"title": []}, {"unknown": []}])
    def test_alias_validation_does_not_mutate_input_mapping(self, extra):
        data = dict(id=1, description="Same", **extra)
        original = deepcopy(data)
        try:
            Step.model_validate(data)
        except ModelValidationError:
            pass
        assert data == original

    def test_step_dump_keeps_internal_title_contract(self):
        plan = Plan.model_validate(self.plan_data(dict(id=1, description="Exact")) | dict(
            risk_profile="standard", risk_profile_rationale="Round-trip fixture"
        ))
        for dumped in (plan.steps[0].model_dump(), plan.model_dump()["steps"][0]):
            assert dumped["title"] == "Exact"
            assert "description" not in dumped
            assert Step.model_validate(dumped).title == "Exact"
        assert Plan.model_validate(plan.model_dump()).steps[0].title == "Exact"

    def test_step_alias_does_not_allow_unrelated_unknown_fields(self):
        with pytest.raises(ModelValidationError, match="unknown"):
            Step(id=1, description="Text", unknown=True)

    def test_step_alias_does_not_change_plan_or_feature_titles(self):
        data = self.plan_data(dict(id=1, description="Step"))
        data["features"] = [dict(id="feature", title="Feature")]
        plan = Plan.model_validate(data)
        assert plan.title == "Plan"
        assert plan.features[0].title == "Feature"
        for target in (data, data["features"][0]):
            title = target.pop("title")
            target["description"] = title
            with pytest.raises(ModelValidationError, match="title"):
                Plan.model_validate(data)
            target["title"] = target.pop("description")

    @pytest.mark.parametrize("version", [None, PLAN_FORMAT_VERSION, 999])
    def test_step_alias_accepts_absent_and_current_format_version(self, version):
        text = self.plan_text(dict(id=1, description="Text"), **({} if version is None else dict(format_version=version)))
        if version == 999:
            with pytest.raises(UnsupportedPlanFormatVersionError):
                parse_plan_text(text)
        else:
            assert parse_plan_text(text).steps[0].title == "Text"

    def test_reading_description_plan_preserves_source_bytes(self, tmp_path):
        path = tmp_path / "description.md"
        original = self.plan_text(dict(id=1, description="Exact\ntext")).replace("\n", "\r\n").encode()
        path.write_bytes(original)
        assert parse_plan(path).steps[0].title == "Exact\ntext"
        assert path.read_bytes() == original
