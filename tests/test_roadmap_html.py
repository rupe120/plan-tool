"""Tests for the ``--view html`` artifact renderer.

Plain unit tests: the module touches no disk, drives no orchestrator, and has
no backend seam. Fixtures construct the row dataclasses directly rather than
parsing text, matching ``tests/test_roadmap_view.py``'s stated policy.
"""

from __future__ import annotations

import re
from dataclasses import replace
from html.parser import HTMLParser

import pytest

from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    AttributeDispositionRow,
    BusinessRuleRow,
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    ComponentRow,
    ComponentsArtifact,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DOMAIN_FILENAME,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    HostingRow,
    OrderingEntry,
    PLANS_FILENAME,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RejectedAlternative,
    RemovalRecord,
    StoreRow,
    WorkflowRow,
)
from plan_tool.roadmap_html import anchor_for, render_roadmap_html, review_path
from plan_tool.roadmap_view import (
    MODE_CURRENT,
    MODE_REVIEW,
    UnparseableArtifact,
    build_design_row_index,
    build_feedback_index,
    build_removal_index,
    resolve_id,
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def test_review_path_sits_beside_one_roadmaps_artifacts(tmp_path) -> None:
    assert review_path(tmp_path, "project") == (
        tmp_path / "roadmaps" / "project" / "review.html"
    )


def _domain(**overrides) -> DomainArtifact:
    values = {
        "entities": (
            EntityRow(
                id="ent-world",
                name="World",
                fields=(
                    FieldRow(name="name", type=FieldType.TEXT),
                    FieldRow(
                        name="owner", type=FieldType.REFERENCE, entity_id="ent-user"
                    ),
                ),
            ),
            EntityRow(
                id="ent-user",
                name="User",
                fields=(FieldRow(name="email", type=FieldType.TEXT),),
            ),
        ),
        "business_rules": (
            BusinessRuleRow(
                id="br-owner",
                statement="A world has one owner.",
                entity_ids=("ent-world", "ent-user"),
            ),
        ),
        "workflows": (
            WorkflowRow(
                id="wf-create", name="Create a world", entity_ids=("ent-world",)
            ),
        ),
        "decisions": (
            DecisionRow(
                id="dec-owner",
                chosen_option="One owner",
                rejected_alternatives=(
                    RejectedAlternative(option="Co-ownership", reason="Needs roles."),
                ),
                rationale="Sharing is read-only.",
                anchor="br-owner",
                status=DecisionStatus.SETTLED,
            ),
        ),
        "body": "Domain prose.",
    }
    values.update(overrides)
    return DomainArtifact(**values)


def _constraints(**overrides) -> ConstraintsArtifact:
    values = {
        "hosting": (HostingRow(id="host-compute", facet="compute", value="container"),),
        "dispositions": (
            AttributeDispositionRow(
                id="disp-durability",
                attribute="durability",
                disposition=ConstraintDisposition.PRIORITIZED,
            ),
        ),
        "constraints": (
            ConstraintRow(
                id="con-backup",
                statement="Snapshots restore for 30 days.",
                attribute="durability",
                anchor_ids=("ent-world",),
            ),
        ),
        "decisions": (),
        "body": "Constraints prose.",
    }
    values.update(overrides)
    return ConstraintsArtifact(**values)


def _components(**overrides) -> ComponentsArtifact:
    values = {
        "system_patterns": (
            PatternRow(
                id="pat-local", name="Local-first", statement="Writes land locally."
            ),
        ),
        "component_patterns": (),
        "stores": (StoreRow(id="store-world", category="relational", sharing="silo"),),
        "components": (
            ComponentRow(
                id="cmp-world",
                name="World store",
                entity_ids=("ent-world",),
                pattern_ids=("pat-local",),
                constraint_ids=("con-backup",),
                store_ids=("store-world",),
            ),
        ),
        "decisions": (),
        "body": "Components prose.",
    }
    values.update(overrides)
    return ComponentsArtifact(**values)


def _plans(**overrides) -> PlansArtifact:
    values = {
        "plans": (
            PlanRow(
                id="plan-store",
                title="World store",
                disposition=PlanDisposition.KEEP,
                component_ids=("cmp-world",),
                draft_seed_path="plan-seed-drafts/plan-store.md",
                sizing_rationale="One component.",
                intent="A world persists.",
                non_goals=("Any editor UI",),
            ),
        ),
        "ordering": (
            OrderingEntry(
                plan_id="plan-store", depends_on=(), assumption_targets=("asm-single",)
            ),
        ),
        "assumptions": (
            AssumptionRow(
                id="asm-single",
                statement="One device at a time.",
                consuming_plan_ids=("plan-store",),
            ),
        ),
        "decisions": (),
        "body": "Plans prose.",
    }
    values.update(overrides)
    return PlansArtifact(**values)


def _loaded(
    *,
    domain=None,
    constraints=None,
    components=None,
    plans=None,
    mode: str = MODE_CURRENT,
    absent: tuple = (),
    unparseable: tuple = (),
    slug: str = "my-roadmap",
):
    """A :class:`LoadedRoadmap` built the way ``load_roadmap`` builds one, so
    the indices under test are the real ones rather than hand-written maps."""
    from plan_tool.roadmap_view import LoadedRoadmap

    return LoadedRoadmap(
        slug=slug,
        mode=mode,
        directory_exists=True,
        domain=domain,
        constraints=constraints,
        components=components,
        plans=plans,
        absent=absent,
        unparseable=unparseable,
        design_row_index=build_design_row_index(
            domain=domain, constraints=constraints, components=components, plans=plans
        ),
        removal_index=build_removal_index(
            domain=domain, constraints=constraints, components=components, plans=plans
        )
        if mode == MODE_REVIEW
        else {},
        feedback_index=build_feedback_index(
            domain=domain, constraints=constraints, components=components, plans=plans
        )
        if mode == MODE_REVIEW
        else {},
        all_removal_index=build_removal_index(
            domain=domain, constraints=constraints, components=components, plans=plans
        ),
        all_feedback_index=build_feedback_index(
            domain=domain, constraints=constraints, components=components, plans=plans
        ),
    )


def _full(**kwargs):
    return _loaded(
        domain=_domain(),
        constraints=_constraints(),
        components=_components(),
        plans=_plans(),
        **kwargs,
    )


def _anchor_ids(html: str) -> list[str]:
    return re.findall(r' id="(row-[^"]+)"', html)


def _link_targets(html: str) -> list[str]:
    return re.findall(r'href="#(row-[^"]+)"', html)


# --------------------------------------------------------------------------
# Anchors and links
# --------------------------------------------------------------------------


class TestAnchorsAndLinks:
    def test_every_internal_link_lands_on_an_anchor_that_exists(self) -> None:
        html = render_roadmap_html(_full())
        assert set(_link_targets(html)) <= set(_anchor_ids(html))
        assert _link_targets(html), "fixture must exercise at least one link"

    def test_a_decision_anchored_to_a_stack_row_links_to_an_anchor_that_exists(self) -> None:
        """Stack ids are valid decision anchors, so the page must render the row a
        link lands on; a stack-less constraints artifact renders no stack block."""
        from plan_tool.roadmap_artifacts import DecisionRow, DecisionStatus, StackRow

        stack = (StackRow("stack-platform", "platform", open=True),)
        decision = DecisionRow(
            "dec-platform", "Defer the platform.", (), "Not yet chosen.",
            "stack-platform", DecisionStatus.PENDING,
        )
        constraints = _constraints(stack=stack, decisions=(decision,))
        html = render_roadmap_html(
            _loaded(domain=_domain(), constraints=constraints, components=_components(), plans=_plans())
        )

        assert any("stack-platform" in anchor for anchor in _anchor_ids(html))
        assert set(_link_targets(html)) <= set(_anchor_ids(html))
        assert "Stack" in html and "open — not decided" in html
        assert ">Stack<" not in render_roadmap_html(_full())

    def test_no_anchor_id_is_emitted_twice_even_when_two_rows_share_an_id(
        self,
    ) -> None:
        # Nothing enforces id uniqueness *across* artifacts, so a collision is
        # reachable; a duplicate fragment id would be invalid HTML and would
        # make the browser's jump target arbitrary.
        colliding = _components(
            stores=(StoreRow(id="ent-world", category="document", sharing="pool"),)
        )
        html = render_roadmap_html(
            _loaded(domain=_domain(), components=colliding)
        )
        anchors = _anchor_ids(html)
        assert len(anchors) == len(set(anchors))

    def test_anchor_for_separates_ids_a_lossy_slugifier_would_collide(self) -> None:
        # "a b" and "a-b" both slugify to "a-b" under the usual rule; the
        # encoding here must keep them apart or a link would jump to the
        # wrong row.
        assert anchor_for("a b") != anchor_for("a-b")
        assert anchor_for("x/y") != anchor_for("x.y")

    def test_anchor_for_emits_only_html_id_safe_characters(self) -> None:
        assert re.fullmatch(r"[A-Za-z0-9._-]+", anchor_for("id with spaces & \"quotes\""))


# --------------------------------------------------------------------------
# Unresolved references
# --------------------------------------------------------------------------


class TestUnresolvedReferences:
    def test_a_dangling_reference_reuses_resolve_ids_own_marker_text(self) -> None:
        # Pinned against ``resolve_id`` rather than a literal so this view and
        # the text views cannot drift into two wordings for one condition.
        loaded = _loaded(
            domain=_domain(
                business_rules=(
                    BusinessRuleRow(
                        id="br-x", statement="Rule.", entity_ids=("ent-missing",)
                    ),
                )
            )
        )
        expected = resolve_id("ent-missing", loaded.design_row_index).text
        html = render_roadmap_html(loaded)
        assert f'<span class="warn">{expected}</span>' in html

    def test_a_dangling_reference_is_not_rendered_as_a_link(self) -> None:
        loaded = _loaded(
            domain=_domain(
                business_rules=(
                    BusinessRuleRow(
                        id="br-x", statement="Rule.", entity_ids=("ent-missing",)
                    ),
                )
            )
        )
        assert anchor_for("ent-missing") not in "".join(
            _link_targets(render_roadmap_html(loaded))
        )

    def test_an_ambiguous_reference_renders_the_marker_and_lists_its_matches(
        self,
    ) -> None:
        # The candidates are the actionable half: "ambiguous" alone does not
        # tell a reader which two rows collided, so both labels must render,
        # exactly as ``render_traceability_walk`` renders its own matches.
        colliding = _components(
            stores=(StoreRow(id="ent-world", category="document", sharing="pool"),)
        )
        html = render_roadmap_html(
            _loaded(domain=_domain(), components=colliding)
        )
        assert "⚠ ambiguous: ent-world" in html
        assert "<li>World</li>" in html
        assert "<li>store: document, pool</li>" in html


# --------------------------------------------------------------------------
# Mode contract
# --------------------------------------------------------------------------


class TestModeContract:
    def _reviewed(self, mode: str) -> str:
        domain = _domain(
            feedback=(
                FeedbackRow(
                    id="fb-1",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="ent-world"
                    ),
                    request="Reconsider ownership.",
                    state=FeedbackState.OPEN,
                ),
            ),
            removals=(
                RemovalRecord(
                    removed_id="ent-culture",
                    rationale="Folded in.",
                    feedback_ids=("fb-1",),
                ),
            ),
        )
        return render_roadmap_html(_loaded(domain=domain, mode=mode))

    def test_review_channel_rows_render_only_under_review_mode(self) -> None:
        assert "Reconsider ownership." in self._reviewed(MODE_REVIEW)
        assert "ent-culture" in self._reviewed(MODE_REVIEW)

    def test_current_mode_hides_feedback_and_removals_entirely(self) -> None:
        current = self._reviewed(MODE_CURRENT)
        assert "Reconsider ownership." not in current
        assert "ent-culture" not in current
        assert "Feedback" not in current

    def test_the_header_names_the_mode_it_rendered(self) -> None:
        assert "mode: review" in self._reviewed(MODE_REVIEW)
        assert "mode: current" in self._reviewed(MODE_CURRENT)


# --------------------------------------------------------------------------
# Missing artifacts
# --------------------------------------------------------------------------


class TestMissingArtifacts:
    def test_an_absent_artifact_says_so_in_its_own_section(self) -> None:
        html = render_roadmap_html(
            _loaded(domain=_domain(), absent=(CONSTRAINTS_FILENAME,))
        )
        assert "not present on disk" in html
        assert f"absent: {CONSTRAINTS_FILENAME}" in html

    def test_an_unparseable_artifact_reports_the_parse_reason(self) -> None:
        html = render_roadmap_html(
            _loaded(
                domain=_domain(),
                unparseable=(
                    UnparseableArtifact(
                        filename=PLANS_FILENAME, reason="missing 'plans' key"
                    ),
                ),
            )
        )
        assert "not parsed — missing &#x27;plans&#x27; key" in html

    def test_readable_count_reports_what_actually_parsed(self) -> None:
        html = render_roadmap_html(
            _loaded(
                domain=_domain(),
                absent=(CONSTRAINTS_FILENAME, COMPONENTS_FILENAME),
                unparseable=(
                    UnparseableArtifact(filename=PLANS_FILENAME, reason="broken"),
                ),
            )
        )
        assert "1/4 artifacts readable" in html

    def test_all_four_sections_render_even_with_nothing_on_disk(self) -> None:
        html = render_roadmap_html(_loaded())
        for anchor in ("domain", "constraints", "components", "plans"):
            assert f'<section id="{anchor}">' in html


# --------------------------------------------------------------------------
# Plan ordering
# --------------------------------------------------------------------------


class TestPlanOrdering:
    def _two_plans(self, ordering) -> PlansArtifact:
        second = PlanRow(
            id="plan-editor",
            title="Editor",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/plan-editor.md",
            sizing_rationale="One surface.",
            intent="Editing works.",
            non_goals=("Map rendering",),
        )
        base = _plans()
        return PlansArtifact(
            plans=base.plans + (second,),
            ordering=ordering,
            assumptions=base.assumptions,
            decisions=base.decisions,
            body=base.body,
        )

    def test_plans_render_in_ordering_sequence_not_source_order(self) -> None:
        artifact = self._two_plans(
            (
                OrderingEntry(plan_id="plan-editor"),
                OrderingEntry(plan_id="plan-store"),
            )
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert html.index("Editor") < html.index("World store")

    def test_a_plan_the_ordering_never_names_renders_marked_not_dropped(self) -> None:
        artifact = self._two_plans((OrderingEntry(plan_id="plan-store"),))
        html = render_roadmap_html(_loaded(plans=artifact))
        assert "⚠ not in ordering" in html
        assert "Editor" in html

    def test_a_repeated_ordering_entry_renders_a_marker_not_a_second_card(
        self,
    ) -> None:
        artifact = self._two_plans(
            (
                OrderingEntry(plan_id="plan-store"),
                OrderingEntry(plan_id="plan-store"),
            )
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        # Labelled by the plan it names, not by the bare id — the wording
        # ``render_traceability_walk`` uses for the same malformation.
        assert "⚠ duplicate ordering entry: World store" in html
        assert html.count('<h4><code>plan-store</code>') == 1

    def test_an_ordering_entry_naming_no_plan_reuses_the_dangling_marker(self) -> None:
        artifact = self._two_plans(
            (
                OrderingEntry(plan_id="plan-store"),
                OrderingEntry(plan_id="plan-ghost"),
                OrderingEntry(plan_id="plan-editor"),
            )
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert "⚠ undefined: plan-ghost" in html


# --------------------------------------------------------------------------
# Document-level guarantees
# --------------------------------------------------------------------------


class TestDocumentGuarantees:
    def test_render_is_deterministic_for_the_same_artifacts(self) -> None:
        # No timestamp, host, or path is embedded, so the file diffs cleanly
        # across re-renders of an unchanged roadmap.
        assert render_roadmap_html(_full()) == render_roadmap_html(_full())

    def test_the_page_loads_nothing_over_the_network(self) -> None:
        html = render_roadmap_html(_full())
        assert "http://" not in html
        assert "https://" not in html
        assert "<script" not in html
        assert "<link" not in html

    @pytest.mark.parametrize(
        "hostile",
        ('<script>alert(1)</script>', '" onload="alert(1)', "<img src=x onerror=1>"),
    )
    def test_artifact_text_cannot_inject_markup(self, hostile: str) -> None:
        html = render_roadmap_html(
            _loaded(
                domain=_domain(
                    workflows=(
                        WorkflowRow(id="wf-x", name=hostile, entity_ids=()),
                    )
                )
            )
        )
        assert hostile not in html
        assert "<script>alert(1)</script>" not in html

    def test_a_row_id_carrying_a_quote_cannot_break_out_of_its_attribute(self) -> None:
        html = render_roadmap_html(
            _loaded(
                domain=_domain(
                    workflows=(
                        WorkflowRow(id='wf" onmouseover="x', name="W", entity_ids=()),
                    )
                )
            )
        )
        assert 'onmouseover="x"' not in html

    def test_the_document_is_a_complete_standalone_page(self) -> None:
        html = render_roadmap_html(_full())
        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")
        assert "<style>" in html


# --------------------------------------------------------------------------
# Coverage of the row collections
# --------------------------------------------------------------------------


class TestRowCoverage:
    @pytest.mark.parametrize(
        "needle",
        (
            "ent-world",
            "br-owner",
            "wf-create",
            "dec-owner",
            "host-compute",
            "disp-durability",
            "con-backup",
            "pat-local",
            "store-world",
            "cmp-world",
            "plan-store",
            "asm-single",
        ),
    )
    def test_every_collection_the_four_artifacts_carry_reaches_the_page(
        self, needle: str
    ) -> None:
        # The gap this view exists to close: the text views each render a
        # slice, and dispositions / hosting / stores / pattern statements
        # appear in none of them.
        assert needle in render_roadmap_html(_full())

    def test_a_non_reference_field_renders_its_logical_type(self) -> None:
        # Assert the key, not the word: the inlined stylesheet contains
        # `text-transform`, so a bare `"text" in html` passes with field-type
        # rendering deleted outright.
        html = render_roadmap_html(_loaded(domain=_domain()))
        assert "<b>name</b>" in html
        assert '<span class="type">text</span>' in html

    def test_a_reference_field_links_to_the_entity_it_points_at(self) -> None:
        html = render_roadmap_html(_loaded(domain=_domain()))
        assert f'href="#{anchor_for("ent-user")}"' in html

    def test_an_empty_collection_is_written_out_rather_than_left_blank(self) -> None:
        # Deliberate: a blank block reads as "not recorded" exactly as easily
        # as "recorded as none", which is the ambiguity this marker removes.
        html = render_roadmap_html(_loaded(domain=_domain(workflows=())))
        block = html.split("Workflows")[1].split("</details>")[0]
        assert '<p class="none">(none)</p>' in block

    def test_an_empty_reference_list_is_written_out_rather_than_left_blank(
        self,
    ) -> None:
        html = render_roadmap_html(
            _loaded(
                domain=_domain(
                    workflows=(WorkflowRow(id="wf-x", name="Ø", entity_ids=()),)
                )
            )
        )
        row = html.split("<code>wf-x</code>")[1].split("</tr>")[0]
        assert '<span class="none">(none)</span>' in row

    def test_a_decision_renders_its_status_rationale_and_rejected_options(
        self,
    ) -> None:
        html = render_roadmap_html(_loaded(domain=_domain()))
        # `.badge.settled` is a stylesheet rule, so the bare word proves
        # nothing about the rendered decision row.
        assert '<span class="badge settled">settled</span>' in html
        assert "Sharing is read-only." in html
        assert "Co-ownership" in html
        assert "Needs roles." in html

    def test_inherited_decision_without_rationale_does_not_render_python_none(self) -> None:
        domain = _domain()
        inherited = replace(
            domain.decisions[0], source="answer-owner", rationale=None, rejected_alternatives=()
        )
        html = render_roadmap_html(_loaded(domain=replace(domain, decisions=(inherited,))))

        assert "<th>source</th>" in html
        assert "<td>answer-owner</td>" in html
        assert "<td>(none)</td>" in html
        assert "<td>None</td>" not in html


# --------------------------------------------------------------------------
# The entity diagram
# --------------------------------------------------------------------------


def _diagram(html: str) -> str:
    """The domain section's ``<svg>``, or ``""`` when it drew none."""
    if "<svg" not in html:
        return ""
    return html[html.index("<svg") : html.index("</svg>") + 6]


class TestEntityDiagram:
    """The picture and the table under it are two renderings of one set of
    rows. Every test here is about them agreeing — on what resolves, on what
    a link points at, and on which of the two owns the anchor."""

    def test_the_diagram_comes_before_the_rows_it_draws(self) -> None:
        html = render_roadmap_html(_loaded(domain=_domain()))
        assert html.index("Entity diagram") < html.index("<summary>Entities")

    def test_a_resolved_reference_becomes_a_drawn_edge(self) -> None:
        svg = _diagram(render_roadmap_html(_loaded(domain=_domain())))
        assert svg.count('class="er-edge"') == 1

    def test_a_box_links_to_the_table_row_for_the_same_entity(self) -> None:
        svg = _diagram(render_roadmap_html(_loaded(domain=_domain())))
        assert f'href="#{anchor_for("ent-world")}"' in svg

    def test_the_diagram_links_to_an_anchor_without_claiming_it(self) -> None:
        # The table row owns the fragment id. A box that emitted its own
        # would either duplicate the id or steal it, and every existing
        # cross-reference to the entity would land on the picture instead of
        # the row it has always landed on.
        html = render_roadmap_html(_loaded(domain=_domain()))
        anchor = anchor_for("ent-world")
        assert html.count(f'id="{anchor}"') == 1
        assert f'<td id="{anchor}"' in html

    def test_an_unresolved_reference_reuses_resolve_ids_own_marker_text(self) -> None:
        # Pinned against ``resolve_id`` rather than a literal, exactly as the
        # table's own marker is: the two renderings of one field must not
        # drift into two wordings for one condition.
        loaded = _loaded(
            domain=_domain(
                entities=(
                    EntityRow(
                        id="ent-world",
                        name="World",
                        fields=(
                            FieldRow(
                                name="owner",
                                type=FieldType.REFERENCE,
                                entity_id="ent-missing",
                            ),
                        ),
                    ),
                )
            )
        )
        expected = resolve_id("ent-missing", loaded.design_row_index).text
        svg = _diagram(render_roadmap_html(loaded))
        assert expected in svg
        assert "er-edge" not in svg

    def test_a_reference_field_with_no_entity_id_has_one_marker_in_both_views(
        self,
    ) -> None:
        # The gate requires an ``entity_id`` on every reference field, but
        # the view layer runs no gates. The table and diagram share this
        # resolution so a malformed field cannot acquire two diagnoses.
        html = render_roadmap_html(
            _loaded(
                domain=_domain(
                    entities=(
                        EntityRow(
                            id="ent-world",
                            name="World",
                            fields=(
                                FieldRow(name="owner", type=FieldType.REFERENCE),
                            ),
                        ),
                    )
                )
            )
        )
        assert html.count("⚠ missing entity_id: owner") == 2
        assert "er-edge" not in _diagram(html)

    def test_entity_collisions_are_resolved_once_per_render(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.roadmap_html as roadmap_html_module

        calls = []
        original = roadmap_html_module.resolve_id

        def spy(row_id, index):
            calls.append(row_id)
            return original(row_id, index)

        monkeypatch.setattr(roadmap_html_module, "resolve_id", spy)
        render_roadmap_html(
            _loaded(
                domain=_domain(
                    entities=(EntityRow(id="ent-world", name="World", fields=()),),
                    business_rules=(),
                    workflows=(),
                    decisions=(),
                )
            )
        )
        assert calls.count("ent-world") == 1

    def test_entity_references_to_a_non_entity_warn_without_linking(self) -> None:
        # All four entity-typed reference shapes share the same kind-aware
        # resolution, including the field's table and diagram renderings.
        components = ComponentsArtifact(
            system_patterns=(),
            component_patterns=(),
            stores=(StoreRow(id="store-world", category="document", sharing="pool"),),
            components=(
                ComponentRow(
                    id="component-world",
                    name="World component",
                    entity_ids=("store-world",),
                    pattern_ids=(),
                ),
            ),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(
            _loaded(
                domain=_domain(
                    entities=(
                        EntityRow(
                            id="ent-world",
                            name="World",
                            fields=(
                                FieldRow(
                                    name="home",
                                    type=FieldType.REFERENCE,
                                    entity_id="store-world",
                                ),
                            ),
                        ),
                    ),
                    business_rules=(
                        BusinessRuleRow(
                            id="rule-world",
                            statement="World is stored.",
                            entity_ids=("store-world",),
                        ),
                    ),
                    workflows=(
                        WorkflowRow(
                            id="workflow-world",
                            name="Store world",
                            entity_ids=("store-world",),
                        ),
                    ),
                    decisions=(),
                ),
                components=components,
            )
        )
        svg = _diagram(html)
        warning = "⚠ wrong kind: store-world is a store, not entity"
        assert html.count(warning) == 5
        assert warning in svg
        assert f'<a class="ref" href="#{anchor_for("store-world")}">' not in html
        assert "er-edge" not in svg

    def test_an_ambiguous_reference_lists_matches_in_the_diagram_hover(self) -> None:
        components = ComponentsArtifact(
            system_patterns=(),
            component_patterns=(),
            stores=(StoreRow(id="target", category="document", sharing="pool"),),
            components=(),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(
            _loaded(
                domain=_domain(
                    entities=(
                        EntityRow(
                            id="source",
                            name="Source",
                            fields=(
                                FieldRow(
                                    name="target",
                                    type=FieldType.REFERENCE,
                                    entity_id="target",
                                ),
                            ),
                        ),
                        EntityRow(id="target", name="Candidate", fields=()),
                    ),
                    business_rules=(),
                    workflows=(),
                    decisions=(),
                ),
                components=components,
            )
        )
        svg = _diagram(html)
        assert "⚠ ambiguous: target" in svg
        assert "<title>Matches: Candidate; store: document, pool</title>" in svg

    def test_reference_fields_are_resolved_once_for_both_renderings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.roadmap_html as roadmap_html_module

        calls = []
        original = roadmap_html_module.resolve_id_of_kind

        def spy(row_id, loaded, *, kind):
            calls.append(row_id)
            return original(row_id, loaded, kind=kind)

        monkeypatch.setattr(roadmap_html_module, "resolve_id_of_kind", spy)
        render_roadmap_html(
            _loaded(
                domain=_domain(
                    entities=(
                        EntityRow(
                            id="ent-world",
                            name="World",
                            fields=(
                                FieldRow(
                                    name="home",
                                    type=FieldType.REFERENCE,
                                    entity_id="store-world",
                                ),
                            ),
                        ),
                    ),
                    business_rules=(),
                    workflows=(),
                    decisions=(),
                ),
                components=ComponentsArtifact(
                    system_patterns=(),
                    component_patterns=(),
                    stores=(
                        StoreRow(
                            id="store-world", category="document", sharing="pool"
                        ),
                    ),
                    components=(),
                    decisions=(),
                    body="",
                ),
            )
        )
        # The shared field bundle resolves once; a second table/diagram pass
        # would call the kind-aware resolver twice.
        assert calls.count("store-world") == 1

    def test_an_entity_whose_id_names_another_row_is_marked_and_not_linked(
        self,
    ) -> None:
        # The same refusal ``_ref`` makes for an ambiguous id: linking one of
        # two rows that share it would pick a winner the page cannot pick.
        colliding = _components(
            stores=(StoreRow(id="ent-world", category="document", sharing="pool"),)
        )
        svg = _diagram(
            render_roadmap_html(_loaded(domain=_domain(), components=colliding))
        )
        assert "er-warn-box" in svg
        assert f'href="#{anchor_for("ent-world")}"' not in svg

    def test_a_colliding_entitys_box_hover_lists_its_competing_matches(
        self,
    ) -> None:
        # The table's id cell lists every competing row for the same
        # collision (``_marker``'s <ul>); the diagram's box previously
        # showed only "ambiguous", with no way to see what it collides
        # with from the picture alone.
        colliding = _components(
            stores=(StoreRow(id="ent-world", category="document", sharing="pool"),)
        )
        svg = _diagram(
            render_roadmap_html(_loaded(domain=_domain(), components=colliding))
        )
        assert "Matches: World; store: document, pool" in svg

    def test_a_domain_with_no_entities_says_so_and_draws_nothing(self) -> None:
        html = render_roadmap_html(_loaded(domain=_domain(entities=())))
        block = html.split("Entity diagram")[1].split("</details>")[0]
        assert '<p class="none">(none)</p>' in block
        assert "<svg" not in html

    def test_the_caption_states_that_cardinality_is_not_drawn(self) -> None:
        # An ER diagram is read by convention, and this one breaks one of them
        # on purpose. Left to be inferred from the absence of crow's feet, a
        # reader takes "no mark" for "exactly one".
        html = render_roadmap_html(_loaded(domain=_domain()))
        caption = html.split('<p class="caption">')[1].split("</p>")[0]
        assert "Cardinality" in caption

    def test_the_diagrams_own_stylesheet_ships_with_the_page(self) -> None:
        # The page loads nothing, so a class with no rule in the inlined
        # stylesheet renders as an unfilled, unstroked shape — invisible
        # rather than merely unstyled.
        html = render_roadmap_html(_loaded(domain=_domain()))
        style = html.split("<style>")[1].split("</style>")[0]
        for rule in (".er-box", ".er-edge", ".er-arrow", ".er-title"):
            assert rule in style

    def test_the_diagram_renders_under_both_modes(self) -> None:
        # Entities are design content, not review-channel content: the mode
        # contract governs feedback and removals, and hiding the picture with
        # them would hide rows ``current`` mode is meant to show.
        for mode in (MODE_CURRENT, MODE_REVIEW):
            assert _diagram(render_roadmap_html(_loaded(domain=_domain(), mode=mode)))


# --------------------------------------------------------------------------
# The three carve-outs
# --------------------------------------------------------------------------


class TestDeliberateCarveOuts:
    """The module's docstring names three things this view deliberately does
    not do. Each is asserted, not merely stated: without these, widening the
    view to swallow another projection would stay green."""

    def test_prose_bodies_render_verbatim_with_no_markdown_interpreted(self) -> None:
        # A half-parser would mangle a table or fenced block written for a
        # markdown reader; escaped-verbatim cannot.
        body = "# Heading\n\n| a | b |\n| --- | --- |\n\n- bullet\n"
        html = render_roadmap_html(_loaded(domain=_domain(body=body)))
        assert "<h1>Heading</h1>" not in html
        assert "<li>bullet</li>" not in html
        assert "# Heading" in html
        assert "| a | b |" in html

    def test_no_reverse_citation_index_is_rendered(self) -> None:
        # ``--view index`` owns that projection; a second renderer for the
        # same derived fact is what would drift.
        html = render_roadmap_html(_full())
        assert "cited by" not in html.lower()
        assert "nothing cites this" not in html

    def test_no_draft_seed_lifecycle_state_is_rendered(self) -> None:
        # ``--view seeds`` owns freshness. The plan's own ``draft_seed_path``
        # is artifact content and does render, as written.
        html = render_roadmap_html(_full())
        assert "plan-seed-drafts/plan-store.md" in html
        for state in ("stale", "digest-mismatched", "materialize"):
            assert state not in html


# --------------------------------------------------------------------------
# Well-formedness under adversarial input
# --------------------------------------------------------------------------


_VOID_ELEMENTS = frozenset({"meta", "br", "hr", "img", "input", "link"})


# HTML5's "in body" insertion mode implicitly closes an open <p> when one
# of these starts — Python's html.parser does not implement that rule, so a
# tag-balance check alone treats `<p><ul>...</ul></p>` as well-formed even
# though a browser silently splits it into `<p></p><ul>...</ul><p></p>`.
# This is exactly the shape that escaped round 1: `_marker`'s span+ul output
# nested inside `_plans_block`'s `<p class="warn">` wrapper.
_P_AUTO_CLOSING_CHILDREN = frozenset(
    {
        "address", "article", "aside", "blockquote", "details", "div",
        "dl", "fieldset", "figure", "footer", "form", "h1", "h2", "h3",
        "h4", "h5", "h6", "header", "hr", "main", "nav", "ol", "p",
        "pre", "section", "table", "ul",
    }
)


class _StructureCheck(HTMLParser):
    """Collects tag-balance errors, every ``id`` the document emits, and any
    block-level element a browser would auto-close a ``<p>`` for.

    Escaping is asserted elsewhere by substring; this parses the result
    instead, which is what catches a value that escapes its *attribute* and
    changes the document's shape rather than merely showing up as text.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.ids: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag in _P_AUTO_CLOSING_CHILDREN and "p" in self.stack:
            self.errors.append(
                f"<{tag}> opened while a <p> was still open — a browser "
                "auto-closes the <p> here, so the intended nesting never "
                "renders as written"
            )
        if tag not in _VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_endtag(self, tag) -> None:
        if tag in _VOID_ELEMENTS:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"mismatched </{tag}> with open {self.stack[-3:]}")
            while self.stack and self.stack.pop() != tag:
                pass
            return
        self.stack.pop()


_HOSTILE = '</table><script>x</script>" id="pwn'


def _hostile_domain() -> DomainArtifact:
    return DomainArtifact(
        entities=(
            EntityRow(
                id=_HOSTILE,
                name=_HOSTILE,
                fields=(
                    FieldRow(
                        name=_HOSTILE, type=FieldType.REFERENCE, entity_id=_HOSTILE
                    ),
                ),
            ),
        ),
        business_rules=(
            BusinessRuleRow(
                id=_HOSTILE + "2", statement=_HOSTILE, entity_ids=(_HOSTILE,)
            ),
        ),
        workflows=(),
        decisions=(
            DecisionRow(
                id=_HOSTILE + "3",
                chosen_option=_HOSTILE,
                rejected_alternatives=(
                    RejectedAlternative(option=_HOSTILE, reason=_HOSTILE),
                ),
                rationale=_HOSTILE,
                anchor=_HOSTILE,
                status=DecisionStatus.PENDING,
            ),
        ),
        body=_HOSTILE,
        feedback=(
            FeedbackRow(
                id=_HOSTILE,
                target=FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id=_HOSTILE),
                request=_HOSTILE,
                state=FeedbackState.OPEN,
            ),
        ),
        removals=(
            RemovalRecord(
                removed_id=_HOSTILE, rationale=_HOSTILE, feedback_ids=(_HOSTILE,)
            ),
        ),
    )


def _colliding_hostile_domain() -> DomainArtifact:
    """Two rows sharing one id, both labelled with hostile text, and a
    reference to that id.

    This is the only shape that reaches two otherwise-unexercised paths at
    once: the ambiguity marker's ``title`` attribute (the one attribute
    carrying artifact prose rather than an ``anchor_for``-encoded id, so the
    only place a stray quote can break out) and the duplicate-anchor guard.
    Without it both checks below pass for want of an input.
    """
    return DomainArtifact(
        entities=(EntityRow(id="dup-1", name=_HOSTILE, fields=()),),
        business_rules=(
            BusinessRuleRow(id="br-1", statement="Cites both.", entity_ids=("dup-1",)),
        ),
        workflows=(WorkflowRow(id="dup-1", name=_HOSTILE, entity_ids=()),),
        decisions=(),
        body="",
    )


def _ambiguous_plan_ordering_domain_plans() -> PlansArtifact:
    """Two plan rows sharing one id, with an ordering entry for it — the
    scenario that produced `_marker`'s span+ul output nested inside a
    `<p class="warn-box">` in round 1. `TestWellFormedness` only ever
    exercised the *domain* artifact's ambiguity; this exercises the same
    shape in `_plans_block`, which the well-formedness sweep otherwise never
    reaches."""

    def plan(title: str) -> PlanRow:
        return PlanRow(
            id="plan-dup",
            title=title,
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path=f"plan-seed-drafts/{title}.md",
            sizing_rationale="One component.",
            intent="Ships something.",
            non_goals=("Nothing else",),
        )

    return PlansArtifact(
        plans=(plan("Alpha"), plan("Beta")),
        ordering=(OrderingEntry(plan_id="plan-dup"),),
        assumptions=(),
        decisions=(),
        body="",
    )


_EMPTY_ARTIFACTS = {
    "domain": DomainArtifact(
        entities=(), business_rules=(), workflows=(), decisions=(), body=""
    ),
    "constraints": ConstraintsArtifact(
        dispositions=(), constraints=(), decisions=(), body="", hosting=()
    ),
    "components": ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        components=(),
        decisions=(),
        body="",
        stores=(),
    ),
    "plans": PlansArtifact(
        plans=(), ordering=(), assumptions=(), decisions=(), body=""
    ),
}


def _cases():
    return {
        "fully populated": _full(mode=MODE_REVIEW),
        "every collection empty": _loaded(mode=MODE_REVIEW, **_EMPTY_ARTIFACTS),
        "nothing on disk": _loaded(mode=MODE_REVIEW),
        "hostile text in every field": _loaded(
            domain=_hostile_domain(), mode=MODE_REVIEW
        ),
        "colliding ids with hostile labels": _loaded(
            domain=_colliding_hostile_domain(), mode=MODE_REVIEW
        ),
        "ambiguous plan id referenced by ordering": _loaded(
            plans=_ambiguous_plan_ordering_domain_plans(), mode=MODE_REVIEW
        ),
        "unicode ids and blank names": _loaded(
            domain=DomainArtifact(
                entities=(EntityRow(id="日本", name="", fields=()),),
                business_rules=(),
                workflows=(),
                decisions=(),
                body="   ",
            )
        ),
    }


@pytest.mark.parametrize("case", sorted(_cases()))
class TestWellFormedness:
    def test_tags_stay_balanced(self, case: str) -> None:
        check = _StructureCheck()
        check.feed(render_roadmap_html(_cases()[case]))
        check.close()
        assert check.errors == []
        assert check.stack == []

    def test_no_fragment_id_is_emitted_twice(self, case: str) -> None:
        check = _StructureCheck()
        check.feed(render_roadmap_html(_cases()[case]))
        check.close()
        assert len(check.ids) == len(set(check.ids))

    def test_no_artifact_value_can_open_a_tag_of_its_own(self, case: str) -> None:
        # The attribute-escape case: a value that merely *shows up* as text is
        # harmless; one that closes its attribute and starts an element
        # changes the document's shape, which only a parse detects.
        html = render_roadmap_html(_cases()[case])
        assert "<script" not in html
        assert "pwn" not in re.findall(r'id="([^"]*)"', html)


# --------------------------------------------------------------------------
# Regressions
# --------------------------------------------------------------------------


class TestResolutionReuse:
    """Every unresolved reference is rendered from the resolution the view
    layer already computed. Re-deriving one is how this module previously
    reported a supported state as a malformation."""

    def test_feedback_targeting_a_removed_row_renders_the_removal_not_undefined(
        self,
    ) -> None:
        # `resolve_feedback_target` is the one resolver that consults removals;
        # `resolve_id` never does. Asking the latter for a removed target
        # reports "⚠ undefined" for a state the walk and ledger both render as
        # the removal it names.
        domain = _domain(
            feedback=(
                FeedbackRow(
                    id="fb-1",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="ent-gone"
                    ),
                    request="Confirm nothing still cites it.",
                    state=FeedbackState.OPEN,
                ),
            ),
            removals=(
                RemovalRecord(
                    removed_id="ent-gone",
                    rationale="Folded into World.",
                    feedback_ids=("fb-1",),
                ),
            ),
        )
        html = render_roadmap_html(_loaded(domain=domain, mode=MODE_REVIEW))
        row = html.split("<code>fb-1</code>")[1].split("</tr>")[0]
        assert "removed: ent-gone — Folded into World." in row
        assert "undefined" not in row

    def test_a_live_design_row_target_still_links(self) -> None:
        domain = _domain(
            feedback=(
                FeedbackRow(
                    id="fb-2",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="ent-world"
                    ),
                    request="Reconsider.",
                    state=FeedbackState.OPEN,
                ),
            )
        )
        html = render_roadmap_html(_loaded(domain=domain, mode=MODE_REVIEW))
        row = html.split("<code>fb-2</code>")[1].split("</tr>")[0]
        assert f'href="#{anchor_for("ent-world")}"' in row


class TestAmbiguousPlansKeepTheirContent:
    def test_two_plan_rows_sharing_an_id_both_render_full_cards(self) -> None:
        # Round 4: rendering only a warning-box line silently dropped both
        # colliding plans' actual content — title, intent, non-goals,
        # sizing rationale — leaving the block header's count claiming rows
        # the page never showed. Both cards now render in full, each
        # carrying the same ambiguity marker every other reference to the
        # id already shows.
        def plan(title: str) -> PlanRow:
            return PlanRow(
                id="plan-dup",
                title=title,
                disposition=PlanDisposition.KEEP,
                component_ids=(),
                draft_seed_path=f"plan-seed-drafts/{title}.md",
                sizing_rationale=f"rationale-{title}",
                intent=f"intent-{title}",
                non_goals=("Nothing else",),
            )

        artifact = PlansArtifact(
            plans=(plan("Alpha"), plan("Beta")),
            ordering=(OrderingEntry(plan_id="plan-dup"),),
            assumptions=(),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert html.count('<h4><code>plan-dup</code>') == 2
        assert "rationale-Alpha" in html and "rationale-Beta" in html
        assert "intent-Alpha" in html and "intent-Beta" in html
        assert "⚠ ambiguous: plan-dup" in html
        assert "<li>Alpha</li>" in html
        assert "<li>Beta</li>" in html

    def test_an_unordered_ambiguous_plan_also_renders_both_in_full(self) -> None:
        def plan(title: str) -> PlanRow:
            return PlanRow(
                id="plan-dup",
                title=title,
                disposition=PlanDisposition.KEEP,
                component_ids=(),
                draft_seed_path="plan-seed-drafts/x.md",
                sizing_rationale=f"rationale-{title}",
                intent=f"intent-{title}",
                non_goals=("None",),
            )

        artifact = PlansArtifact(
            plans=(plan("Alpha"), plan("Beta")),
            ordering=(),
            assumptions=(),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert html.count('<h4><code>plan-dup</code>') == 2
        assert "rationale-Alpha" in html and "rationale-Beta" in html
        assert html.count("⚠ not in ordering") == 2
        assert "⚠ ambiguous: plan-dup" in html
        assert "<li>Alpha</li>" in html
        assert "<li>Beta</li>" in html


class TestAnchorInjectivity:
    @pytest.mark.parametrize(
        "left, right",
        (
            ("\xab" + "cd", "ꯍ"),  # variable-width escapes ran together
            ("a b", "a-b"),
            ("x/y", "x.y"),
            ("«" + "0000", "\U000ab000" + "0"),
        ),
    )
    def test_distinct_ids_never_share_an_anchor(self, left: str, right: str) -> None:
        # Hex digits are themselves anchor-safe, so an escape with no fixed
        # width has no boundary: '\xab'+'cd' and 'ꯍ' both encoded to
        # `.abcd`, silently pointing every link for one row at the other.
        assert left != right
        assert anchor_for(left) != anchor_for(right)

    def test_every_escape_is_the_same_width(self) -> None:
        assert anchor_for("\xab") == "row-.0000ab"
        assert anchor_for("ꯍ") == "row-.00abcd"
        assert anchor_for("\U0010FFFF") == "row-.10ffff"


class TestNavCanActuallyStick:
    """The jump bar is the point of collapsing four artifacts onto one page,
    and `position:sticky` is inert unless the element can move within its
    containing block."""

    def test_nav_is_not_nested_inside_the_header(self) -> None:
        # A sticky element cannot escape its parent's box. As the header's
        # last child — with the header's content ending at the nav's own
        # bottom edge — it scrolls away with the header and the bar is
        # reachable only at the very top of the page.
        html = render_roadmap_html(_full())
        header = re.search(r"<header>.*?</header>", html, re.S)
        assert header is not None
        assert "<nav>" not in header.group()
        assert "</header>\n<nav>" in html

    def test_the_reserved_scroll_offset_covers_every_anchor_target(self) -> None:
        # `scroll-margin-top` keeps a jump from landing underneath the bar.
        # Row anchors sit on `td.rowid`, so omitting it there lands half the
        # links inconsistently with the sections and cards.
        html = render_roadmap_html(_full())
        style = html.split("<style>")[1].split("</style>")[0]
        for selector in ("section", ".card", "td.rowid"):
            rule = next(
                (r for r in style.split("}") if r.strip().startswith(selector + "{")),
                None,
            )
            assert rule is not None, f"no rule for {selector}"
            assert "scroll-margin-top" in rule, f"{selector} reserves no offset"


class TestMarkerOnlyWarnsWhenActionable:
    """`_marker` renders the warning treatment only for the two statuses
    that are actually a problem — `resolve_id`/`resolve_feedback_target`
    return several others, and each is an ordinary, resolved reference."""

    def test_an_artifact_scoped_feedback_target_renders_plainly(self) -> None:
        # `row.target.row_id` is None for an artifact-scoped row, so the
        # target cell has nothing to link — but "the whole artifact" is a
        # legitimate, resolved state (`RESOLUTION_ARTIFACT_SCOPE`), not a
        # broken reference. Styling it as a warning draws a reviewer's eye
        # to a row that has no problem.
        domain = _domain(
            feedback=(
                FeedbackRow(
                    id="fb-art",
                    target=FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT),
                    request="Review the whole domain.",
                    state=FeedbackState.OPEN,
                ),
            )
        )
        html = render_roadmap_html(_loaded(domain=domain, mode=MODE_REVIEW))
        row = html.split("<code>fb-art</code>")[1].split("</tr>")[0]
        assert "the whole artifact" in row
        assert 'class="warn"' not in row
        assert 'class="warn-box"' not in row

    def test_a_removal_resolved_target_renders_without_warning_styling(
        self,
    ) -> None:
        # Round-1 fixed the wrong *text* (it said "undefined"); round 2
        # covers the styling: a removal-resolved target is informational,
        # matching the plain rendering the text views give it, not a
        # flagged problem.
        domain = _domain(
            feedback=(
                FeedbackRow(
                    id="fb-1",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="ent-gone"
                    ),
                    request="Confirm nothing still cites it.",
                    state=FeedbackState.OPEN,
                ),
            ),
            removals=(
                RemovalRecord(
                    removed_id="ent-gone", rationale="Folded in.", feedback_ids=()
                ),
            ),
        )
        html = render_roadmap_html(_loaded(domain=domain, mode=MODE_REVIEW))
        row = html.split("<code>fb-1</code>")[1].split("</tr>")[0]
        assert "removed: ent-gone" in row
        assert 'class="warn"' not in row


class TestOrderingEntryWrongKind:
    def test_an_ordering_entry_naming_a_non_plan_row_says_so(self) -> None:
        # Before this fix, `resolve_id` searched the whole design-row index
        # and returned RESOLVED for any matching row of any kind, so an
        # ordering entry that (mis)names an assumption id rendered that
        # assumption's plain label in the warning box with nothing saying a
        # non-plan row had been named.
        plan = PlanRow(
            id="plan-x",
            title="X",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/x.md",
            sizing_rationale="One.",
            intent="Ships.",
            non_goals=("None",),
        )
        assumption = AssumptionRow(
            id="asm-1", statement="Single device.", consuming_plan_ids=()
        )
        artifact = PlansArtifact(
            plans=(plan,),
            ordering=(
                OrderingEntry(plan_id="asm-1"),
                OrderingEntry(plan_id="plan-x"),
            ),
            assumptions=(assumption,),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert "⚠ ordering entry does not name a plan: Single device." in html

    def test_a_genuinely_dangling_ordering_entry_still_gets_the_dangling_marker(
        self,
    ) -> None:
        plan = PlanRow(
            id="plan-x",
            title="X",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/x.md",
            sizing_rationale="One.",
            intent="Ships.",
            non_goals=("None",),
        )
        artifact = PlansArtifact(
            plans=(plan,),
            ordering=(
                OrderingEntry(plan_id="plan-ghost"),
                OrderingEntry(plan_id="plan-x"),
            ),
            assumptions=(),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert "⚠ undefined: plan-ghost" in html
        assert "does not name a plan" not in html


class TestCrossArtifactIdCollision:
    """Nothing enforces row-id uniqueness *across* artifacts. A plan id that
    collides with a row in another artifact must be flagged on the card
    itself, not only at the id's other occurrences — otherwise the page
    contradicts itself about the same id."""

    def test_a_plan_id_colliding_with_an_entity_id_is_flagged_on_the_card(
        self,
    ) -> None:
        domain = _domain(
            entities=(EntityRow(id="x-1", name="Widget", fields=()),)
        )
        plan = PlanRow(
            id="x-1",
            title="Ship widget",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/x.md",
            sizing_rationale="One.",
            intent="Ships.",
            non_goals=("None",),
        )
        artifact = PlansArtifact(
            plans=(plan,),
            ordering=(OrderingEntry(plan_id="x-1"),),
            assumptions=(),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(domain=domain, plans=artifact))
        card = html.split('<h4><code>x-1</code>')[1].split("</article>")[0]
        assert "⚠ ambiguous: x-1" in card
        assert "<li>Widget</li>" in card
        assert "<li>Ship widget</li>" in card

    def test_a_plan_id_colliding_with_a_non_plan_row_when_unordered(
        self,
    ) -> None:
        domain = _domain(
            entities=(EntityRow(id="x-1", name="Widget", fields=()),)
        )
        plan = PlanRow(
            id="x-1",
            title="Ship widget",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/x.md",
            sizing_rationale="One.",
            intent="Ships.",
            non_goals=("None",),
        )
        artifact = PlansArtifact(
            plans=(plan,), ordering=(), assumptions=(), decisions=(), body=""
        )
        html = render_roadmap_html(_loaded(domain=domain, plans=artifact))
        assert "⚠ ambiguous: x-1" in html
        assert "⚠ not in ordering" in html

    def test_a_uniquely_owned_plan_id_is_not_flagged(self) -> None:
        # No false positive: an ordinary, uncontested plan id renders no
        # collision warning at all.
        html = render_roadmap_html(_full())
        card = html.split('<h4><code>plan-store</code>')[1].split("</article>")[0]
        assert "warn" not in card


class TestReferenceFieldMissingEntityId:
    def test_a_reference_field_with_no_entity_id_says_so(self) -> None:
        # The gate requires entity_id on a reference field; --view runs no
        # gates, so a hand-edited artifact can violate it. Before this fix
        # the type badge rendered with nothing after it — indistinguishable
        # from an ordinary, complete field.
        domain = _domain(
            entities=(
                EntityRow(
                    id="ent-1",
                    name="A",
                    fields=(
                        FieldRow(
                            name="owner", type=FieldType.REFERENCE, entity_id=None
                        ),
                    ),
                ),
            )
        )
        html = render_roadmap_html(_loaded(domain=domain))
        assert "⚠ missing entity_id: owner" in html

    def test_a_complete_reference_field_is_unaffected(self) -> None:
        html = render_roadmap_html(_full())
        assert "missing entity_id" not in html


class TestReadableCountDerivesFromSections:
    def test_the_denominator_tracks_section_count_not_a_hardcoded_four(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # With the real four-artifact ``_SECTIONS``, a hardcoded ``4`` and a
        # derived ``len(_SECTIONS)`` render identical text, so that case
        # alone cannot tell "coincidentally equal" from "actually derived".
        # Monkeypatching a shorter table is the only way to distinguish
        # them.
        import re as _re

        import plan_tool.roadmap_html as roadmap_html

        monkeypatch.setattr(
            roadmap_html, "_SECTIONS", roadmap_html._SECTIONS[:2]
        )
        html = render_roadmap_html(_loaded())
        match = _re.search(r"(\d+)/(\d+) artifacts readable", html)
        assert match is not None
        assert match.group(2) == "2"


class TestIdCollisionAppliesToEveryRowKind:
    """Round 4: round 3's fix wired the cross-artifact collision check only
    into plan cards. Every id-bearing row renders through the same
    `_row_id_cell` primitive, which is where the check now lives — a
    collision must show up regardless of which row kind defines the id."""

    @pytest.mark.parametrize(
        "build",
        (
            lambda: _loaded(
                domain=_domain(
                    entities=(EntityRow(id="shared-1", name="Widget", fields=()),)
                ),
                constraints=ConstraintsArtifact(
                    hosting=(),
                    dispositions=(),
                    constraints=(
                        ConstraintRow(
                            id="shared-1",
                            statement="Must be fast.",
                            attribute="latency",
                            anchor_ids=(),
                        ),
                    ),
                    decisions=(),
                    body="",
                ),
            ),
            lambda: _loaded(
                domain=_domain(
                    workflows=(WorkflowRow(id="shared-2", name="Flow", entity_ids=()),)
                ),
                components=ComponentsArtifact(
                    system_patterns=(
                        PatternRow(id="shared-2", name="Pat", statement="s"),
                    ),
                    component_patterns=(),
                    stores=(),
                    components=(),
                    decisions=(),
                    body="",
                ),
            ),
        ),
    )
    def test_a_collision_between_two_non_plan_rows_is_flagged_on_both(
        self, build
    ) -> None:
        html = render_roadmap_html(build())
        assert html.count("⚠ ambiguous:") >= 1
        # The collision marker sits inside the row's own id cell, not only
        # at other references to it.
        collision_count = html.count('class="warn-box"><div class="warn">⚠ ambiguous')
        assert collision_count >= 1

    def test_an_uncontested_id_gets_no_collision_marker(self) -> None:
        html = render_roadmap_html(_full())
        assert "⚠ ambiguous" not in html


class TestFeedbackAndRemovalCellsDoNotShareTheDesignRowNamespace:
    """`_plain_id_cell` deliberately does not run `_id_collision`: feedback
    ids and a removal's ``removed_id`` are not part of ``design_row_index``,
    and checking them against it would be comparing unrelated id spaces."""

    def test_a_feedback_id_matching_a_design_row_id_is_not_flagged(self) -> None:
        # `fb-1` as a *feedback* id has nothing to do with `fb-1` as a
        # (contrived) entity id in a different namespace; the feedback cell
        # must not claim collision, and must not steal the entity's anchor.
        domain = _domain(
            entities=(EntityRow(id="fb-1", name="Not actually feedback", fields=()),),
            feedback=(
                FeedbackRow(
                    id="fb-1",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="ent-world"
                    ),
                    request="Check something.",
                    state=FeedbackState.OPEN,
                ),
            ),
        )
        html = render_roadmap_html(_loaded(domain=domain, mode=MODE_REVIEW))
        assert "⚠ ambiguous: fb-1" not in html
        # The entity still gets its own anchor; the feedback row's id cell
        # never registered one under the same string.
        assert html.count('id="row-fb-1"') == 1


class TestFeedbackTargetResolvedOnce:
    def _resolve_calls(self, monkeypatch: pytest.MonkeyPatch, mode: str) -> int:
        # The redundant second/third resolve only happens on the *resolved*
        # path (the explicit check, then again inside `_ref`) — a dangling
        # id short-circuits to `_marker` before ever reaching `_ref`, so the
        # target must actually resolve for this test to exercise anything.
        import plan_tool.roadmap_html as roadmap_html_module

        calls = []
        original = roadmap_html_module.resolve_id

        def spy(row_id, index):
            calls.append(row_id)
            return original(row_id, index)

        monkeypatch.setattr(roadmap_html_module, "resolve_id", spy)

        domain = DomainArtifact(
            entities=(EntityRow(id="ent-live", name="Live", fields=()),),
            business_rules=(),
            workflows=(),
            decisions=(),
            body="",
            feedback=(
                FeedbackRow(
                    id="fb-1",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="ent-live"
                    ),
                    request="check",
                    state=FeedbackState.OPEN,
                ),
            ),
        )
        render_roadmap_html(_loaded(domain=domain, mode=mode))
        return calls.count("ent-live")

    def test_resolving_a_live_target_calls_resolve_id_at_most_once_per_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Measured as the *review-minus-current* delta, not a page-wide
        # total: everything else that resolves this id — the entity's own id
        # cell, the entity diagram's box — renders identically in both modes
        # and cancels, while the feedback block renders only under review.
        # A total would pin the whole page's resolver count and would have to
        # be re-tuned by any renderer that legitimately resolves an id,
        # which says nothing about the property named here: that
        # `_feedback_block` does not also ask `_ref` to resolve the target it
        # already resolved itself.
        review = self._resolve_calls(monkeypatch, MODE_REVIEW)
        current = self._resolve_calls(monkeypatch, MODE_CURRENT)
        assert current == 1
        assert review - current == 1



class TestRepeatedMalformedOrderingEntry:
    def test_a_repeated_dangling_entry_keeps_its_own_diagnostic(self) -> None:
        # Before this fix, the second occurrence of the same malformed id
        # collapsed into a generic "duplicate ordering entry" with no
        # mention that the id is also undefined — the more actionable fact.
        plan = PlanRow(
            id="plan-x",
            title="X",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/x.md",
            sizing_rationale="One.",
            intent="Ships.",
            non_goals=("None",),
        )
        artifact = PlansArtifact(
            plans=(plan,),
            ordering=(
                OrderingEntry(plan_id="plan-ghost"),
                OrderingEntry(plan_id="plan-ghost"),
                OrderingEntry(plan_id="plan-x"),
            ),
            assumptions=(),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert "⚠ undefined: plan-ghost" in html
        assert "repeated, ⚠ undefined: plan-ghost" in html
        # The genuinely generic case (a repeat of an id that DOES resolve
        # to a real plan) is unaffected by this branch.
        assert "⚠ duplicate ordering entry:" not in html

    def test_a_repeated_wrong_kind_entry_keeps_its_own_diagnostic(self) -> None:
        plan = PlanRow(
            id="plan-x",
            title="X",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/x.md",
            sizing_rationale="One.",
            intent="Ships.",
            non_goals=("None",),
        )
        assumption = AssumptionRow(
            id="asm-1", statement="Single device.", consuming_plan_ids=()
        )
        artifact = PlansArtifact(
            plans=(plan,),
            ordering=(
                OrderingEntry(plan_id="asm-1"),
                OrderingEntry(plan_id="asm-1"),
                OrderingEntry(plan_id="plan-x"),
            ),
            assumptions=(assumption,),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert "⚠ ordering entry does not name a plan: Single device." in html
        assert (
            "⚠ ordering entry does not name a plan (repeated): Single device."
            in html
        )

    def test_a_genuine_repeat_of_a_resolvable_plan_is_unaffected(self) -> None:
        plan = PlanRow(
            id="plan-x",
            title="X",
            disposition=PlanDisposition.KEEP,
            component_ids=(),
            draft_seed_path="plan-seed-drafts/x.md",
            sizing_rationale="One.",
            intent="Ships.",
            non_goals=("None",),
        )
        artifact = PlansArtifact(
            plans=(plan,),
            ordering=(
                OrderingEntry(plan_id="plan-x"),
                OrderingEntry(plan_id="plan-x"),
            ),
            assumptions=(),
            decisions=(),
            body="",
        )
        html = render_roadmap_html(_loaded(plans=artifact))
        assert "⚠ duplicate ordering entry: X" in html


class TestCollisionBoxIsNotForcedNowrap:
    def test_nowrap_scopes_to_the_id_text_not_the_whole_cell(self) -> None:
        # Round 4 moved the collision warning into the same <td> the id's
        # <code> lives in. `td.rowid{white-space:nowrap}` would then force
        # the collision box's prose and match list to stay on one unbroken
        # line too, relying entirely on the outer .scroll container's
        # horizontal scrollbar to stay readable.
        html = render_roadmap_html(_full())
        style = html.split("<style>")[1].split("</style>")[0]
        assert "td.rowid{white-space:nowrap}" not in style
        assert "td.rowid>code{white-space:nowrap}" in style


class TestPrintStylesheet:
    """Pin the concrete print-media rules for a page meant to be printed."""

    def _style(self) -> str:
        html = render_roadmap_html(_full())
        return html.split("<style>")[1].split("</style>")[0]

    def test_print_media_block_exists(self) -> None:
        assert "@media print{" in self._style()

    def test_print_forces_light_regardless_of_viewer_theme(self) -> None:
        # A dark background prints as a solid ink block unless the viewer
        # opts in to background graphics, and looks wrong either way.
        print_block = self._style().split("@media print{")[1]
        assert "--bg:#fff" in print_block

    def test_print_hides_the_jump_nav(self) -> None:
        # The jump nav and its sticky positioning have no reason to exist
        # once there is no cursor to click them.
        print_block = self._style().split("@media print{")[1]
        assert "nav{display:none}" in print_block

    def test_table_headers_repeat_on_every_printed_page(self) -> None:
        # The standard, well-supported mechanism for keeping a table's
        # column headers visible after the table spans a page break —
        # without it, page 2 of a long table shows unlabeled columns.
        print_block = self._style().split("@media print{")[1]
        assert "thead{display:table-header-group}" in print_block

    def test_rows_and_cards_avoid_splitting_across_a_page_break(self) -> None:
        print_block = self._style().split("@media print{")[1]
        assert "tr,.card,.warn-box,table.kv{break-inside:avoid}" in print_block

    def test_each_later_artifact_starts_its_own_page_the_first_follows_the_header(
        self,
    ) -> None:
        # The first section follows the page header directly — a uniform
        # break-before:page on every section would leave a blank leading
        # page before any content.
        print_block = self._style().split("@media print{")[1]
        assert "section{margin-top:0;break-before:page}" in print_block
        assert "section:first-of-type{break-before:avoid}" in print_block

    def test_scroll_containers_do_not_clip_content_when_printed(self) -> None:
        # `.scroll{overflow-x:auto}` is a screen affordance; on paper there
        # is no scrollbar, so content past the container edge would simply
        # be cut off unless overflow is allowed to be visible.
        print_block = self._style().split("@media print{")[1]
        assert ".scroll{overflow:visible}" in print_block

    def test_a_manually_collapsed_section_still_prints_in_full(self) -> None:
        # This is a generated snapshot, not an interactive page — nothing
        # about "what a viewer had collapsed before printing" is meaningful
        # information to preserve.
        print_block = self._style().split("@media print{")[1]
        assert "details>*:not(summary){display:block!important}" in print_block

    def test_print_keeps_reference_links_in_their_semantic_blue(self) -> None:
        # The four artifact accents identify sections. Reference links keep
        # the separately meaningful blue used on screen.
        style = self._style()
        print_block = self._style().split("@media print{")[1]
        assert "a.ref{color:var(--accent);text-decoration:none}" in style
        assert "--accent:#2f5d8c" in print_block
        assert "a.ref{text-decoration:underline}" in print_block


class TestArtifactAccentSystem:
    """Artifact accents keep the high-level navigation, headings, and each
    section's ``.artifact-content`` card distinct.

    The details blocks select their own concept accents; see
    :class:`TestConceptAccentSystem`.
    """

    def _style(self) -> str:
        html = render_roadmap_html(_full())
        return html.split("<style>")[1].split("</style>")[0]

    @pytest.mark.parametrize(
        "section", ("domain", "constraints", "components", "plans")
    )
    def test_every_section_and_its_nav_pill_scope_an_accent(
        self, section: str
    ) -> None:
        style = self._style()
        assert f"#{section}{{--acc:var(--acc-{section});" in style
        assert (
            f"#{section}{{--acc:var(--acc-{section});--acc-bg:var(--acc-{section}-bg);"
            f"--artifact-acc:var(--acc-{section})}}"
        ) in style
        assert f'nav a[href="#{section}"]{{--acc:var(--acc-{section})}}' in style

    def test_the_four_accents_are_pairwise_distinct_in_every_theme(self) -> None:
        import re

        style = self._style()
        light = style.split("@media (prefers-color-scheme:dark){", 1)[0]
        dark = style.split("@media (prefers-color-scheme:dark){:root{", 1)[1].split(
            "}}\n*{", 1
        )[0]
        print_theme = style.split("@media print{\n  :root{", 1)[1].split(
            "}\n  body{", 1
        )[0]
        for theme in (light, dark, print_theme):
            colors = dict(
                re.findall(r"--acc-(\w+):(#[0-9a-f]{6});--acc-\w+-bg", theme)
            )
            assert len(colors) == 4
            assert len(set(colors.values())) == 4

    def test_every_section_has_a_light_dark_and_print_accent_palette(self) -> None:
        import plan_tool.roadmap_html as roadmap_html_module

        style = self._style()
        for section in roadmap_html_module._SECTIONS:
            for suffix in ("", "-bg"):
                assert style.count(f"--acc-{section.anchor}{suffix}:") == 3

    def test_heading_and_concept_blocks_and_table_headers_reference_the_active_accent(
        self,
    ) -> None:
        style = self._style()
        assert "border-left:.3rem solid var(--acc,var(--line))" in style  # h2
        assert (
            ".artifact-content{border:1px solid var(--line);"
            "border-left:.3rem solid var(--artifact-acc,var(--line));"
            "\nborder-radius:8px;padding:.1rem .85rem .85rem;background:var(--card)}"
            in style
        )  # artifact container
        assert (
            "details{border:1px solid var(--line);border-left:.25rem solid var(--acc,var(--line));"
            "\nborder-radius:8px;margin:.6rem 0"
            in style
        )  # details
        assert "background:var(--acc-bg,transparent);" in style  # thead th

    def test_a_rendered_entity_row_carries_its_sections_accent_scope(self) -> None:
        # Not just CSS text — confirms the id the CSS selector keys off is
        # actually the id the entity section renders under.
        html = render_roadmap_html(_full())
        assert '<section id="domain">' in html

    def test_the_scoping_selectors_are_generated_from_sections_not_hand_typed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # _Section's own docstring claims "adding a fifth artifact is one
        # row" — a hand-typed fourth copy of these selectors would violate
        # that the moment a fifth artifact family existed. Monkeypatching a
        # renamed anchor is the only way to prove the CSS actually tracks
        # _SECTIONS rather than merely agreeing with it by coincidence.
        import plan_tool.roadmap_html as roadmap_html_module

        renamed = roadmap_html_module._SECTIONS[0].__class__(
            "notdomain",
            roadmap_html_module._SECTIONS[0].title,
            roadmap_html_module._SECTIONS[0].filename,
            roadmap_html_module._SECTIONS[0].attribute,
            roadmap_html_module._SECTIONS[0].render,
        )
        monkeypatch.setattr(
            roadmap_html_module,
            "_SECTIONS",
            (renamed,) + roadmap_html_module._SECTIONS[1:],
        )
        generated = roadmap_html_module._accent_scope_rules()
        assert "#notdomain{--acc:var(--acc-notdomain);" in generated
        assert "#domain{" not in generated


class TestConceptAccentSystem:
    """Concept blocks are visibly distinct within their artifact section."""

    # Every group also carries the section's own "decision"/"feedback"/
    # "removal"/"prose" blocks (rendered by ``_common_tail`` in every
    # section under review mode) plus the enclosing section's own
    # ``--acc-<name>`` chrome accent, since both are visible alongside the
    # section-specific concepts and must stay distinct from them too.
    _SEPARATED_CONCEPTS = (
        ("domain", ("entity", "rule", "workflow", "decision", "feedback", "removal", "prose")),
        (
            "constraints",
            ("hosting", "disposition", "constraint", "decision", "feedback", "removal", "prose"),
        ),
        (
            "components",
            (
                "system-pattern",
                "component-pattern",
                "store",
                "component",
                "decision",
                "feedback",
                "removal",
                "prose",
            ),
        ),
        ("plans", ("plan", "assumption", "decision", "feedback", "removal", "prose")),
    )

    def _style(self) -> str:
        html = render_roadmap_html(_full())
        return html.split("<style>")[1].split("</style>")[0]

    def test_concept_blocks_are_nested_in_an_artifact_container(self) -> None:
        html = render_roadmap_html(_full())
        for section in ("domain", "constraints", "components", "plans"):
            body = html.split(f'<section id="{section}">', 1)[1].split(
                "</section>", 1
            )[0]
            assert '<div class="artifact-content"><details ' in body

    def test_every_rendered_block_names_its_concept(self) -> None:
        html = render_roadmap_html(_full(mode=MODE_REVIEW))
        for title, accent in (
            ("Entity diagram", "entity"),
            ("Entities", "entity"),
            ("Business rules", "rule"),
            ("Workflows", "workflow"),
            ("Hosting", "hosting"),
            ("Quality-attribute dispositions", "disposition"),
            ("Constraints", "constraint"),
            ("System patterns", "system-pattern"),
            ("Component patterns", "component-pattern"),
            ("Stores", "store"),
            ("Components", "component"),
            ("Plans", "plan"),
            ("Assumptions", "assumption"),
            ("Decisions", "decision"),
            ("Feedback", "feedback"),
            ("Removals", "removal"),
            ("Prose", "prose"),
        ):
            assert (
                f'<details open class="concept concept-{accent}"><summary>{title}'
                in html
            )

    def test_every_concept_has_a_light_dark_and_print_palette(self) -> None:
        import plan_tool.roadmap_html as roadmap_html_module

        style = self._style()
        for accent in roadmap_html_module._CONCEPT_ACCENTS:
            assert (
                f"details.concept-{accent}{{--acc:var(--concept-{accent});"
                f"--acc-bg:var(--concept-{accent}-bg)}}"
            ) in style
            for suffix in ("", "-bg"):
                assert style.count(f"--concept-{accent}{suffix}:") == 3

    def test_concepts_within_each_artifact_have_distinct_accents_in_every_theme(
        self,
    ) -> None:
        style = self._style()
        themes = (
            style.split("@media (prefers-color-scheme:dark){", 1)[0],
            style.split("@media (prefers-color-scheme:dark){:root{", 1)[1].split(
                "}}\n*{", 1
            )[0],
            style.split("@media print{\n  :root{", 1)[1].split("}\n  body{", 1)[0],
        )
        for theme in themes:
            colors = dict(
                re.findall(
                    r"--concept-([a-z-]+):(#[0-9a-f]{6});--concept-\1-bg", theme
                )
            )
            section_colors = dict(
                re.findall(r"--acc-(\w+):(#[0-9a-f]{6});--acc-\w+-bg", theme)
            )
            for section, concepts in self._SEPARATED_CONCEPTS:
                values = [colors[accent] for accent in concepts]
                values.append(section_colors[section])
                assert len(set(values)) == len(values)
