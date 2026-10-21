"""Tests for plan_tool.jira_config — epic + assignment config file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.jira_config import (
    Epic,
    JiraConfig,
    JiraConfigError,
    default_config_path,
    epic_key_collision_warnings,
    jira_project_key,
    jira_project_keys_in_use,
    load_jira_config,
    plan_rel_path,
    validate_epic_key,
    validate_epic_key_distinct_from_jira_projects,
    validate_new_epic_key_distinct_from_jira_projects,
    validate_plan_tag,
    write_jira_config,
)


class TestValidateEpicKey:
    @pytest.mark.parametrize(
        "key",
        ["AB", "AUTH", "PAY", "PLAT", "A1", "AB12CD", "AB1234567"],
    )
    def test_valid(self, key: str) -> None:
        validate_epic_key(key)  # should not raise

    @pytest.mark.parametrize(
        "key",
        [
            "",
            "A",  # too short
            "auth",  # lowercase
            "AUTH-X",  # dash not allowed
            "AUTH_X",  # underscore not allowed
            "AUTH X",  # space
            "1AUTH",  # leading digit
            "AUTHENTICATION",  # > 10 chars
            "AB ",  # trailing space
            " AB",
        ],
    )
    def test_invalid(self, key: str) -> None:
        with pytest.raises(JiraConfigError):
            validate_epic_key(key)


class TestJiraProjectKey:
    def test_parses_project_prefix(self) -> None:
        assert jira_project_key("PROJ-1234") == "PROJ"

    def test_lowercase_input_normalized_to_upper(self) -> None:
        assert jira_project_key("proj-1") == "PROJ"

    @pytest.mark.parametrize("value", ["not a jira id", "PROJ", "PROJ-", "-1234"])
    def test_unparseable_returns_none(self, value: str) -> None:
        assert jira_project_key(value) is None

    def test_non_ascii_digits_do_not_parse_as_a_real_id(self) -> None:
        # A look-alike using full-width digits is not a real JIRA id --
        # \d without re.ASCII would otherwise accept it.
        assert jira_project_key("PROJ-１２３４") is None

    @pytest.mark.parametrize("value", [None, ""])
    def test_unset_returns_none_without_raising(self, value) -> None:
        # jira_epic_id is Optional[str] on Epic everywhere else in this
        # module; a caller passing that value straight through must not
        # crash just because no id was ever set.
        assert jira_project_key(value) is None


class TestJiraProjectKeysInUse:
    def test_maps_each_epics_own_project_key(self) -> None:
        epics = [
            Epic(key="AUTH", name="Auth", jira_epic_id="PROJ-1"),
            Epic(key="PAY", name="Pay", jira_epic_id="MONEY-9"),
        ]
        assert jira_project_keys_in_use(epics) == {
            "PROJ": "PROJ-1",
            "MONEY": "MONEY-9",
        }

    def test_epics_without_a_parseable_jira_epic_id_are_skipped(self) -> None:
        epics = [
            Epic(key="AUTH", name="Auth"),
            Epic(key="PAY", name="Pay", jira_epic_id="not-a-jira-id"),
        ]
        assert jira_project_keys_in_use(epics) == {}

    def test_first_epic_wins_when_two_share_a_project(self) -> None:
        epics = [
            Epic(key="A", name="A", jira_epic_id="PROJ-1"),
            Epic(key="B", name="B", jira_epic_id="PROJ-2"),
        ]
        assert jira_project_keys_in_use(epics) == {"PROJ": "PROJ-1"}


class TestValidateEpicKeyDistinctFromJiraProjects:
    def test_collision_raises_regardless_of_key_or_source_case(self) -> None:
        for key, project_keys_in_use in [
            ("AUTH", {"AUTH": "AUTH-1234"}),
            ("auth", {"AUTH": "AUTH-1"}),  # lowercase candidate key
        ]:
            with pytest.raises(
                JiraConfigError, match="matches the real JIRA project key"
            ):
                validate_epic_key_distinct_from_jira_projects(
                    key, project_keys_in_use
                )

    def test_no_collision_passes(self) -> None:
        validate_epic_key_distinct_from_jira_projects("AUTH", {})  # no raise
        validate_epic_key_distinct_from_jira_projects(
            "AUTH", {"PROJ": "PROJ-1234"}
        )  # no raise


class TestValidateNewEpicKeyDistinctFromJiraProjects:
    def test_collision_with_own_jira_epic_id_raises(self) -> None:
        with pytest.raises(
            JiraConfigError, match="matches the real JIRA project key"
        ):
            validate_new_epic_key_distinct_from_jira_projects(
                "AUTH", "AUTH-1234", other_epics=[]
            )

    def test_collision_with_a_sibling_epics_jira_epic_id_raises(self) -> None:
        # The candidate's own jira_epic_id is unset — the collision comes
        # from a sibling epic already in the config, which a per-epic-only
        # check (comparing a candidate only against its own two fields)
        # cannot see.
        siblings = [Epic(key="PAY", name="Pay", jira_epic_id="AUTH-500")]
        with pytest.raises(
            JiraConfigError, match="matches the real JIRA project key"
        ):
            validate_new_epic_key_distinct_from_jira_projects(
                "AUTH", None, other_epics=siblings
            )

    def test_no_collision_passes(self) -> None:
        siblings = [Epic(key="PAY", name="Pay", jira_epic_id="MONEY-1")]
        validate_new_epic_key_distinct_from_jira_projects(
            "AUTH", "PROJ-1234", other_epics=siblings
        )  # no raise

    def test_candidates_own_jira_epic_id_colliding_with_a_sibling_key_raises(
        self,
    ) -> None:
        # The reverse direction: the candidate's key doesn't collide with
        # anything, but its own jira_epic_id's project key equals an
        # existing sibling's key — checking only "candidate key vs. project
        # keys in use" can't see this, since it never inspects sibling keys.
        siblings = [Epic(key="AUTH", name="Auth")]
        with pytest.raises(
            JiraConfigError, match="matches existing epic key 'AUTH'"
        ):
            validate_new_epic_key_distinct_from_jira_projects(
                "PAY", "AUTH-100", other_epics=siblings
            )

    def test_self_collision_message_not_misattributed_to_sibling(self) -> None:
        # A sibling shares the same real project AND the candidate's own
        # jira_epic_id independently collides with its own key. The
        # self-collision must be reported (not the sibling's jira_epic_id),
        # since that's the one the caller can actually act on by editing
        # the epic they're currently creating/editing.
        siblings = [Epic(key="PAY", name="Pay", jira_epic_id="AUTH-500")]
        with pytest.raises(JiraConfigError, match="jira_epic_id 'AUTH-999'"):
            validate_new_epic_key_distinct_from_jira_projects(
                "AUTH", "AUTH-999", other_epics=siblings
            )


class TestEpicKeyCollisionWarnings:
    def test_no_collisions_returns_empty(self) -> None:
        epics = [Epic(key="AUTH", name="Auth", jira_epic_id="PROJ-1")]
        assert epic_key_collision_warnings(epics) == []

    def test_returns_one_line_per_colliding_epic(self) -> None:
        epics = [
            Epic(key="AUTH", name="Auth", jira_epic_id="AUTH-1234"),
            Epic(key="PAY", name="Pay", jira_epic_id="MONEY-1"),
        ]
        warnings = epic_key_collision_warnings(epics)
        assert len(warnings) == 1
        assert "AUTH" in warnings[0]

    def test_never_raises_even_for_a_fully_broken_config(self) -> None:
        # This is the non-raising counterpart load_jira_config's strict
        # check uses -- a caller (jira config --show) displaying a
        # config it loaded leniently must never have this throw instead.
        epics = [Epic(key="AUTH", name="Auth", jira_epic_id="AUTH-1")]
        epic_key_collision_warnings(epics)  # no raise


class TestValidatePlanTag:
    @pytest.mark.parametrize(
        "tag",
        ["a", "DCL", "demo", "demo-tag", "demo_tag", "A1", "x" * 24],
    )
    def test_valid(self, tag: str) -> None:
        validate_plan_tag(tag)  # should not raise

    @pytest.mark.parametrize(
        "tag",
        [
            "",
            "-leading-dash",
            "_leading-underscore",
            "has a space",
            "has]bracket",
            "has\nnewline",
            "x" * 25,  # over the 24-char ceiling
        ],
    )
    def test_invalid(self, tag: str) -> None:
        with pytest.raises(JiraConfigError):
            validate_plan_tag(tag)


class TestLoadJiraConfig:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        config = load_jira_config(tmp_path)
        assert config.epics == []
        assert config.plan_assignments == {}
        assert config.plan_tags == {}

    def test_unparseable_jira_epic_id_never_blocks_load(
        self, tmp_path: Path
    ) -> None:
        # _JIRA_ISSUE_KEY_RE's leniency contract: a jira_epic_id that
        # doesn't parse as <KEY>-<NUMBER> has no project key to compare
        # against, so it must never itself fail the distinctness check.
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [
                        {
                            "key": "AUTH",
                            "name": "Auth",
                            "jira_epic_id": "not a jira id",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        config = load_jira_config(tmp_path)
        assert config.epics[0].jira_epic_id == "not a jira id"

    def test_round_trip_preserves_records(self, tmp_path: Path) -> None:
        config = JiraConfig(
            epics=[
                Epic(key="AUTH", name="Authentication", jira_epic_id="PROJ-1"),
                Epic(key="PAY", name="Payments", description="Stripe stuff"),
            ],
            plan_assignments={
                "docs/implementation-plans/1-foo.md": "AUTH",
                "docs/implementation-plans/2-bar.md": "PAY",
            },
            plan_tags={
                "docs/implementation-plans/1-foo.md": "FOO",
                "docs/implementation-plans/2-bar.md": "BAR",
            },
        )
        path = default_config_path(tmp_path)
        write_jira_config(config, path)
        loaded = load_jira_config(tmp_path)
        assert [e.key for e in loaded.epics] == ["AUTH", "PAY"]
        assert loaded.epics[0].jira_epic_id == "PROJ-1"
        assert loaded.epics[1].description == "Stripe stuff"
        assert (
            loaded.plan_assignments["docs/implementation-plans/1-foo.md"]
            == "AUTH"
        )
        assert loaded.plan_tags["docs/implementation-plans/1-foo.md"] == "FOO"
        assert loaded.plan_tags["docs/implementation-plans/2-bar.md"] == "BAR"

    def test_rejects_duplicate_epic_keys(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [
                        {"key": "AUTH", "name": "Auth1"},
                        {"key": "AUTH", "name": "Auth2"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(JiraConfigError, match="duplicate"):
            load_jira_config(tmp_path)

    def test_rejects_invalid_key_shape(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"epics": [{"key": "lower", "name": "x"}]}),
            encoding="utf-8",
        )
        with pytest.raises(JiraConfigError, match="invalid epic key"):
            load_jira_config(tmp_path)

    def test_rejects_epic_key_matching_jira_project(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [
                        {
                            "key": "AUTH",
                            "name": "Auth",
                            "jira_epic_id": "AUTH-1234",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(
            JiraConfigError, match="matches the real JIRA project key"
        ):
            load_jira_config(tmp_path)

    def test_rejects_epic_key_matching_a_sibling_epics_jira_project(
        self, tmp_path: Path
    ) -> None:
        # AUTH's own jira_epic_id is unset — the collision comes from PAY's
        # jira_epic_id, whose project key ("AUTH") matches AUTH's key. A
        # check scoped to only an epic's own two fields would miss this.
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [
                        {"key": "AUTH", "name": "Auth"},
                        {"key": "PAY", "name": "Pay", "jira_epic_id": "AUTH-500"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(
            JiraConfigError, match="matches the real JIRA project key"
        ):
            load_jira_config(tmp_path)

    def test_self_collision_not_misattributed_to_an_uninvolved_sibling(
        self, tmp_path: Path
    ) -> None:
        # PAY has no relationship to AUTH's project at all (different
        # project, "MONEY") — so when AUTH's own jira_epic_id
        # independently collides with AUTH's own key, the raised message
        # must cite AUTH's own id, never PAY's unrelated one.
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [
                        {"key": "PAY", "name": "Pay", "jira_epic_id": "MONEY-1"},
                        {
                            "key": "AUTH",
                            "name": "Auth",
                            "jira_epic_id": "AUTH-999",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(JiraConfigError, match="jira_epic_id 'AUTH-999'"):
            load_jira_config(tmp_path)

    def test_load_time_collision_names_the_repair_command(
        self, tmp_path: Path
    ) -> None:
        # A pre-existing config broken by this rule has no way to reach the
        # wizard that repairs it unless the load-time error names the
        # command; the validator's own message (reused by the interactive
        # new-epic path) says only "pick a different key", not how.
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [
                        {"key": "AUTH", "name": "Auth", "jira_epic_id": "AUTH-1234"}
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(
            JiraConfigError, match=r"Run `plan-tool jira config` to repair"
        ):
            load_jira_config(tmp_path)

    def test_enforce_flag_false_tolerates_an_existing_collision(
        self, tmp_path: Path
    ) -> None:
        # The escape hatch `jira config` uses to stay reachable even when
        # the persisted config already violates this rule.
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [
                        {
                            "key": "AUTH",
                            "name": "Auth",
                            "jira_epic_id": "AUTH-1234",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        config = load_jira_config(
            tmp_path, enforce_key_distinct_from_jira_project=False
        )
        assert [e.key for e in config.epics] == ["AUTH"]

    def test_rejects_assignment_to_unknown_key(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "epics": [{"key": "AUTH", "name": "Auth"}],
                    "plan_assignments": {"docs/foo.md": "PAY"},
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(JiraConfigError, match="unknown epic key"):
            load_jira_config(tmp_path)

    def test_rejects_invalid_plan_tag_value(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"plan_tags": {"docs/foo.md": "has a space"}}),
            encoding="utf-8",
        )
        with pytest.raises(JiraConfigError, match="invalid plan tag"):
            load_jira_config(tmp_path)

    def test_rejects_non_dict_plan_tags(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"plan_tags": []}), encoding="utf-8")
        with pytest.raises(JiraConfigError, match="plan_tags"):
            load_jira_config(tmp_path)

    def test_plan_tags_independent_of_plan_assignments(
        self, tmp_path: Path
    ) -> None:
        """A plan can carry a tag with no epic assignment (and vice versa) —
        the two maps don't validate against each other."""
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"plan_tags": {"docs/foo.md": "FOO"}}),
            encoding="utf-8",
        )
        config = load_jira_config(tmp_path)
        assert config.plan_tags == {"docs/foo.md": "FOO"}
        assert config.plan_assignments == {}

    def test_rejects_invalid_json(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("{not json}", encoding="utf-8")
        with pytest.raises(JiraConfigError, match="invalid JSON"):
            load_jira_config(tmp_path)

    def test_rejects_non_object_top_level(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(JiraConfigError, match="top-level"):
            load_jira_config(tmp_path)

    def test_empty_object_is_valid(self, tmp_path: Path) -> None:
        path = default_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("{}", encoding="utf-8")
        config = load_jira_config(tmp_path)
        assert config.epics == []


class TestJiraConfigLookups:
    def test_epic_by_key_case_insensitive(self) -> None:
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        assert config.epic_by_key("AUTH").name == "Auth"
        assert config.epic_by_key("auth").name == "Auth"
        assert config.epic_by_key("PAY") is None

    def test_epic_for_plan_resolves(self) -> None:
        config = JiraConfig(
            epics=[
                Epic(key="AUTH", name="Auth"),
                Epic(key="PAY", name="Pay"),
            ],
            plan_assignments={"docs/foo.md": "AUTH"},
        )
        epic = config.epic_for_plan("docs/foo.md")
        assert epic is not None
        assert epic.key == "AUTH"

    def test_epic_for_plan_returns_none_when_unassigned(self) -> None:
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        assert config.epic_for_plan("docs/foo.md") is None

    def test_tag_for_plan_resolves(self) -> None:
        config = JiraConfig(plan_tags={"docs/foo.md": "FOO"})
        assert config.tag_for_plan("docs/foo.md") == "FOO"

    def test_tag_for_plan_returns_none_when_untagged(self) -> None:
        config = JiraConfig()
        assert config.tag_for_plan("docs/foo.md") is None


class TestPlanRelPath:
    def test_returns_posix_relative(self, tmp_path: Path) -> None:
        plan = tmp_path / "docs" / "foo.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("x", encoding="utf-8")
        assert plan_rel_path(plan, tmp_path) == "docs/foo.md"

    def test_returns_none_when_outside_repo(self, tmp_path: Path) -> None:
        elsewhere = tmp_path.parent / "elsewhere.md"
        assert plan_rel_path(elsewhere, tmp_path) is None


class TestWriteJiraConfigShape:
    def test_always_emits_both_keys(self, tmp_path: Path) -> None:
        """Empty config still emits epics + plan_assignments + plan_tags so
        diffs stay stable when bouncing between blank and populated states."""
        path = tmp_path / "jc.json"
        write_jira_config(JiraConfig(), path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"epics": [], "plan_assignments": {}, "plan_tags": {}}

    def test_omits_optional_fields_when_none(self, tmp_path: Path) -> None:
        path = tmp_path / "jc.json"
        write_jira_config(
            JiraConfig(epics=[Epic(key="AUTH", name="Auth")]), path
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["epics"] == [{"key": "AUTH", "name": "Auth"}]
        assert "jira_epic_id" not in data["epics"][0]

    def test_plan_assignments_sorted(self, tmp_path: Path) -> None:
        path = tmp_path / "jc.json"
        write_jira_config(
            JiraConfig(
                epics=[Epic(key="AUTH", name="x")],
                plan_assignments={"z.md": "AUTH", "a.md": "AUTH"},
            ),
            path,
        )
        body = path.read_text(encoding="utf-8")
        # a.md appears before z.md in the serialized output.
        assert body.index("a.md") < body.index("z.md")

    def test_plan_tags_sorted(self, tmp_path: Path) -> None:
        path = tmp_path / "jc.json"
        write_jira_config(
            JiraConfig(plan_tags={"z.md": "ZTAG", "a.md": "ATAG"}), path
        )
        body = path.read_text(encoding="utf-8")
        assert body.index("a.md") < body.index("z.md")

    def test_write_has_no_partial_target_when_replace_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        path = tmp_path / "jc.json"
        path.write_text("old\n", encoding="utf-8")

        def boom(src, dst):  # noqa: ANN001
            raise OSError("replace failed")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError, match="replace failed"):
            write_jira_config(
                JiraConfig(epics=[Epic(key="AUTH", name="Auth")]), path
            )

        assert path.read_text(encoding="utf-8") == "old\n"
