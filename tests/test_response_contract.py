import pytest

from plan_tool.response_contract import (
    JSON_ROOT_ARRAY,
    JSON_ROOT_OBJECT,
    JsonResponseContract,
    MarkdownSectionsContract,
    ResponseSection,
    VerdictContract,
    coerce_response_id,
)


class TestMarkdownSectionsContract:
    def test_parser_pattern_and_prompt_skeleton_share_declared_order(self) -> None:
        contract = MarkdownSectionsContract(
            sections=(
                ResponseSection("Correctness findings", "correctness"),
                ResponseSection("Completeness findings", "completeness"),
            )
        )

        assert contract.heading_pattern().findall(
            "## correctness FINDINGS\n\n_(none)_\n\n## Completeness findings"
        ) == ["correctness FINDINGS", "Completeness findings"]
        assert contract.render_empty_skeleton() == (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n_(none)_"
        )
        assert contract.render_prompt_block().index("Correctness findings") < (
            contract.render_prompt_block().index("Completeness findings")
        )

    def test_rejects_duplicate_headings(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            MarkdownSectionsContract(
                sections=(
                    ResponseSection("Findings", "a"),
                    ResponseSection("findings", "b"),
                )
            )

    def test_heading_pattern_tolerates_trailing_decoration(self) -> None:
        """A model that decorates the heading line (extra punctuation/prose
        after the section name) must still be recognized — this parser has
        no retry-on-miss path, so under-matching silently reads as "no
        block at all" rather than a slightly messy one."""
        contract = MarkdownSectionsContract(
            sections=(ResponseSection("Findings", "findings"),)
        )

        assert contract.heading_pattern().search("## Findings (none reported)")
        assert contract.heading_pattern().search("## Findings:")


class TestVerdictContract:
    def test_longer_token_precedes_its_prefix(self) -> None:
        contract = VerdictContract(
            heading="Verdict", tokens=("BLOCKED", "BLOCKED-STRUCTURAL")
        )

        assert contract.heading_pattern().search("## Verdict\n")
        assert contract.token_pattern().search("BLOCKED-STRUCTURAL").group(1) == (
            "BLOCKED-STRUCTURAL"
        )
        assert "<BLOCKED | BLOCKED-STRUCTURAL>" in contract.render_prompt_block()

    def test_render_prompt_block_closes_its_fence(self) -> None:
        contract = VerdictContract(heading="Verdict", tokens=("PASS", "FAIL"))
        block = contract.render_prompt_block()

        assert "```markdown\n" in block
        assert block.count("```") == 2, (
            "an unclosed fence swallows every instruction after it in the "
            "rendered prompt"
        )


class TestJsonResponseContract:
    def test_decodes_its_envelope_and_enforces_top_level_keys(self) -> None:
        contract = JsonResponseContract(
            root=JSON_ROOT_OBJECT,
            example={"items": []},
            required_keys=frozenset({"items"}),
            exact_keys=True,
        )

        assert contract.decode('preamble {"items": []} trailing') == {"items": []}
        assert contract.decode('{"items": [], "extra": true}') is None
        assert contract.decode('{"other": []}') is None
        assert '"items"' in contract.render_prompt_block()

    def test_array_root_rejects_an_object(self) -> None:
        contract = JsonResponseContract(root=JSON_ROOT_ARRAY, example=[])

        assert contract.decode("[1, 2]") == [1, 2]
        assert contract.decode("{}") is None

    def test_alternate_examples_share_one_response_shape(self) -> None:
        contract = JsonResponseContract(
            root=JSON_ROOT_OBJECT,
            example={"after_step_id": None},
            alternate_examples=({"after_step_id": 2},),
        )

        prompt = contract.render_prompt_block()
        assert '"after_step_id": null' in prompt
        assert '"after_step_id": 2' in prompt
        assert "Each example is valid; use the one that fits." in prompt

        with pytest.raises(ValueError, match="does not match"):
            JsonResponseContract(
                root=JSON_ROOT_OBJECT,
                example={"after_step_id": None},
                alternate_examples=([],),
            )

    def test_object_pairs_hook_reaches_json_loads_and_its_errors_are_swallowed(
        self,
    ) -> None:
        """A caller-supplied hook (e.g. duplicate-key rejection) must see
        every object json.loads parses, and a hook that raises is treated
        as a malformed reply rather than propagating."""
        contract = JsonResponseContract(root=JSON_ROOT_OBJECT, example={"a": 1})

        def reject_duplicates(pairs: list) -> dict:
            seen: dict = {}
            for key, value in pairs:
                if key in seen:
                    raise ValueError(f"duplicate key: {key}")
                seen[key] = value
            return seen

        assert contract.decode(
            '{"a": 1}', object_pairs_hook=reject_duplicates
        ) == {"a": 1}
        assert contract.decode(
            '{"a": 1, "a": 2}', object_pairs_hook=reject_duplicates
        ) is None


class TestResponseIdCoercion:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (5, 5),
            (-5, -5),
            (0, 0),
            ("5", 5),
            (" 5 ", 5),
            ("0", None),
            ("01", None),
            ("+5", None),
            ("--5", None),
            ("5.0", None),
            ("2_0", None),
            ("²", None),
            ("٢", None),
            (pytest.param("1" + "0" * 4999, None, id="oversized")),
            (True, None),
            (2.0, None),
            (None, None),
        ],
    )
    def test_coerces_only_the_shared_response_id_grammar(
        self, value: object, expected: int | None
    ) -> None:
        assert coerce_response_id(value) == expected
