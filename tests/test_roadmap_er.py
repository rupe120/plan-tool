"""Tests for the ER-style entity diagram geometry.

Plain unit tests: the module touches no disk, has no backend seam, and takes
no roadmap types — every fixture builds :class:`DiagramEntity` values
directly, which is the whole point of the leaf being view-agnostic.

The assertions here are about *geometry that a browser will believe*: a box
wide enough for its own text, a canvas wide enough for its own boxes, an
arrow for every edge. There is no renderer in the test run, so a check that
merely re-derives the module's own arithmetic proves nothing — where a
constant is needed, it is an independent one (the real advance width of the
fonts in the stylesheet), not the module's estimate of it.
"""

from __future__ import annotations

import math
import re

import pytest

from plan_tool.roadmap_er import (
    DiagramEntity,
    DiagramField,
    ER_STYLE,
    _cells,
    _run,
    render_entity_diagram,
)

# The widest advance width in the monospace stack ``ER_STYLE`` names (Menlo
# and DejaVu Sans Mono, both .602em); Consolas and SF Mono are narrower. Held
# here rather than imported so a shrunk estimate in the module fails these
# tests instead of moving them with it.
_REAL_ADVANCE = 0.602
_PAD = 12  # ditto: the padding the module claims, asserted not reused


# --------------------------------------------------------------------------
# Fixtures and parsing
# --------------------------------------------------------------------------


def _entity(name: str, row_id: str, *fields: DiagramField, **kwargs) -> DiagramEntity:
    return DiagramEntity(
        title=name, subtitle=row_id, fields=tuple(fields), **kwargs
    )


def _ref(name: str, detail: str, target: int) -> DiagramField:
    return DiagramField(name=name, detail=detail, target=target)


def _pair() -> "list[DiagramEntity]":
    """Two entities, the first referencing the second."""
    return [
        _entity(
            "World",
            "ent-world",
            DiagramField(name="name", detail="text"),
            _ref("owner", "→ User", 1),
        ),
        _entity("User", "ent-user", DiagramField(name="email", detail="text")),
    ]


def _boxes(svg: str) -> "list[tuple[int, int, int, int]]":
    """``(x, y, width, height)`` for each drawn box, in emission order."""
    return [
        tuple(int(value) for value in match)
        for match in re.findall(
            r'<rect class="er-fill" x="(-?\d+)" y="(-?\d+)" '
            r'width="(\d+)" height="(\d+)"',
            svg,
        )
    ]


def _canvas(svg: str) -> "tuple[int, int]":
    match = re.search(r'<svg class="er-svg"[^>]*viewBox="0 0 (\d+) (\d+)"', svg)
    assert match is not None, "the diagram must declare a viewBox"
    return int(match.group(1)), int(match.group(2))


def _edges(svg: str) -> "list[str]":
    return re.findall(r'<path class="er-edge" d="([^"]+)"', svg)


def _arrows(svg: str) -> "list[str]":
    return re.findall(r'<polygon class="er-arrow" points="([^"]+)"', svg)


def _points(arrow: str) -> "list[tuple[int, int]]":
    return [
        (int(pair.split(",")[0]), int(pair.split(",")[1]))
        for pair in arrow.split(" ")
    ]


def _path_end(path: str) -> "tuple[int, int]":
    """The final coordinate pair of a cubic bezier ``M … C … x y``."""
    numbers = [int(value) for value in re.findall(r"-?\d+", path)]
    return numbers[-2], numbers[-1]


def _path_start(path: str) -> "tuple[int, int]":
    numbers = [int(value) for value in re.findall(r"-?\d+", path)]
    return numbers[0], numbers[1]


def _curve_bounds(path: str) -> "tuple[float, float, float, float]":
    """``(min x, max x, min y, max y)`` of one cubic bezier, by sampling.

    The curve, not its endpoints: a control point pushed sideways carries the
    drawn line well past both ends, which is exactly the case a bounds check
    over endpoints alone cannot see.
    """
    numbers = [int(value) for value in re.findall(r"-?\d+", path)]
    assert len(numbers) == 8, f"expected one cubic segment, got {path}"
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = (
        (numbers[0], numbers[1]),
        (numbers[2], numbers[3]),
        (numbers[4], numbers[5]),
        (numbers[6], numbers[7]),
    )
    xs, ys = [], []
    for step in range(101):
        t = step / 100
        u = 1 - t
        xs.append(u**3 * x0 + 3 * u**2 * t * x1 + 3 * u * t**2 * x2 + t**3 * x3)
        ys.append(u**3 * y0 + 3 * u**2 * t * y1 + 3 * u * t**2 * y2 + t**3 * y3)
    return min(xs), max(xs), min(ys), max(ys)


# --------------------------------------------------------------------------
# The empty case and determinism
# --------------------------------------------------------------------------


class TestDocumentGuarantees:
    def test_no_entities_renders_nothing_and_leaves_the_wording_to_the_caller(
        self,
    ) -> None:
        # The caller owns what a domain with no entities should *say*; an
        # empty <svg> with a viewBox of nothing would be a claim of its own.
        assert render_entity_diagram(()) == ""

    def test_render_is_deterministic_for_the_same_entities(self) -> None:
        assert render_entity_diagram(_pair()) == render_entity_diagram(_pair())

    def test_the_diagram_loads_nothing_and_runs_nothing(self) -> None:
        # Inline SVG in an HTML document is namespaced by the parser, so an
        # xmlns would put a URL on a page whose contract is that it has none.
        svg = render_entity_diagram(_pair())
        assert "http://" not in svg
        assert "https://" not in svg
        assert "xmlns" not in svg
        assert "<script" not in svg

    @pytest.mark.parametrize(
        "hostile",
        ('<script>alert(1)</script>', '" onload="alert(1)', "</svg><img src=x>"),
    )
    def test_entity_text_cannot_inject_markup(self, hostile: str) -> None:
        svg = render_entity_diagram(
            [
                _entity(
                    hostile,
                    hostile,
                    DiagramField(name=hostile, detail=hostile),
                    href=hostile,
                    note=hostile,
                )
            ]
        )
        assert hostile not in svg
        assert "<script" not in svg
        assert 'onload="alert(1)"' not in svg


class TestTextClipping:
    def test_warning_symbol_reserves_two_character_cells(self) -> None:
        # The font stack can render the warning as an emoji-width glyph, so a
        # one-cell estimate risks overflowing the calculated box width.
        assert _cells("⚠") == 2

    def test_clipping_keeps_a_zwj_sequence_whole(self) -> None:
        family = "👨\u200d👩\u200d👧\u200d👦"
        clipped = _run("x" * 17 + family, 22).show
        assert clipped == "x" * 17 + "…"
        assert "\u200d…" not in clipped

    def test_an_unclipped_runs_cell_count_matches_its_own_text(self) -> None:
        # ``_run`` caches this count rather than making ``_Run.width()``
        # rescan ``show`` on every call; checked against an independent
        # ``_cells`` call so a wrong cached value doesn't pass for want of a
        # second opinion.
        run = _run("populationnumber", 26)
        assert run.cells == _cells("populationnumber")

    def test_a_clipped_runs_cell_count_matches_its_own_shown_text(self) -> None:
        run = _run("x" * 30, 10)
        assert run.clipped
        assert run.cells == _cells(run.show)


# --------------------------------------------------------------------------
# Box geometry
# --------------------------------------------------------------------------


class TestBoxesFitTheirText:
    """The module measures no text — it estimates from monospace character
    cells. These pin that the estimate is large enough for the fonts the
    stylesheet actually asks for, which is the only way the carve-out is
    safe."""

    def _needs(self, text: str, size: int) -> float:
        return 2 * _PAD + len(text) * size * _REAL_ADVANCE

    def test_a_box_is_wide_enough_for_its_own_title(self) -> None:
        title = "Settlement register entry"
        svg = render_entity_diagram([_entity(title, "ent-x")])
        assert _boxes(svg)[0][2] >= self._needs(title, 13)

    def test_a_box_is_wide_enough_for_its_own_id(self) -> None:
        row_id = "ent-settlement-register"
        svg = render_entity_diagram([_entity("S", row_id)])
        assert _boxes(svg)[0][2] >= self._needs(row_id, 10)

    def test_a_box_is_wide_enough_for_a_field_name_beside_its_detail(self) -> None:
        svg = render_entity_diagram(
            [
                _entity(
                    "S",
                    "ent-s",
                    DiagramField(name="population", detail="number"),
                )
            ]
        )
        # Both runs sit on one line with a gap between them, so the box must
        # hold the pair, not the wider of the two.
        assert _boxes(svg)[0][2] >= self._needs("populationnumber", 12)

    def test_a_double_width_script_widens_the_box_it_sits_in(self) -> None:
        # A CJK glyph occupies two monospace cells; counting it as one sizes
        # every box to half the room its own text needs.
        # Long enough that both clear the minimum box width, or the two would
        # tie there and the test would pass with the cell count deleted.
        narrow = render_entity_diagram([_entity("a" * 20, "ent-x")])
        wide = render_entity_diagram([_entity("世" * 20, "ent-x")])
        assert _boxes(wide)[0][2] > _boxes(narrow)[0][2]

    def test_a_box_grows_with_the_number_of_fields_it_holds(self) -> None:
        one = render_entity_diagram(
            [_entity("S", "ent-s", DiagramField(name="a", detail="text"))]
        )
        three = render_entity_diagram(
            [
                _entity(
                    "S",
                    "ent-s",
                    DiagramField(name="a", detail="text"),
                    DiagramField(name="b", detail="text"),
                    DiagramField(name="c", detail="text"),
                )
            ]
        )
        assert _boxes(three)[0][3] > _boxes(one)[0][3]

    def test_an_entity_with_no_fields_says_so_rather_than_rendering_blank(
        self,
    ) -> None:
        # A blank body reads as "not recorded" exactly as easily as
        # "recorded as none" — the same reason the tables write out (none).
        svg = render_entity_diagram([_entity("Rumor", "ent-rumor")])
        assert "(no fields)" in svg

    def test_an_entity_with_no_name_is_marked_rather_than_left_empty(self) -> None:
        svg = render_entity_diagram([_entity("", "ent-x")])
        assert "(unnamed)" in svg

    def test_a_label_past_its_budget_is_clipped_and_keeps_its_full_text(
        self,
    ) -> None:
        full = "an_extremely_long_field_name_nobody_should_write"
        svg = render_entity_diagram(
            [_entity("S", "ent-s", DiagramField(name=full, detail="text"))]
        )
        assert "…" in svg
        # Clipping without the tooltip would lose the text outright — the
        # table below carries it, but the picture must not silently drop it.
        assert f"<title>{full}</title>" in svg

    def test_a_label_within_its_budget_gets_no_redundant_tooltip(self) -> None:
        svg = render_entity_diagram(
            [_entity("S", "ent-s", DiagramField(name="short", detail="text"))]
        )
        assert "<title>short</title>" not in svg


class TestCanvas:
    def test_the_canvas_holds_every_box_it_draws(self) -> None:
        svg = render_entity_diagram(_pair())
        width, height = _canvas(svg)
        for x, y, box_w, box_h in _boxes(svg):
            assert x + box_w <= width
            assert y + box_h <= height

    @pytest.mark.parametrize(
        "shape", ("self-reference", "forward", "backward", "mutual")
    )
    def test_the_canvas_holds_every_curve_it_draws(self, shape: str) -> None:
        # Checked against the *curve*, not its endpoints: a self-reference
        # leaves and re-enters the same right edge, so the drawn line reaches
        # well past every box while both of its ends sit on one. A canvas
        # sized from the boxes alone clips it.
        entities = {
            "self-reference": [
                _entity("Region", "ent-region", _ref("parent", "→ Region", 0))
            ],
            "forward": _pair(),
            "backward": [
                _entity("A", "a", _ref("b", "→ B", 1)),
                _entity("B", "b"),
                _entity("C", "c", _ref("a", "→ A", 0)),
            ],
            "mutual": [
                _entity("A", "a", _ref("b", "→ B", 1)),
                _entity("B", "b", _ref("a", "→ A", 0)),
            ],
        }[shape]
        svg = render_entity_diagram(entities)
        width, height = _canvas(svg)
        assert _edges(svg), "the fixture must draw at least one curve"
        for path in _edges(svg):
            low_x, high_x, low_y, high_y = _curve_bounds(path)
            assert 0 <= low_x and high_x <= width
            assert 0 <= low_y and high_y <= height

    def test_every_box_starts_inside_the_canvas(self) -> None:
        svg = render_entity_diagram(_pair())
        assert all(x > 0 and y > 0 for x, y, _w, _h in _boxes(svg))


# --------------------------------------------------------------------------
# Columns
# --------------------------------------------------------------------------


def _column_xs(svg: str) -> "list[int]":
    return sorted({x for x, _y, _w, _h in _boxes(svg)})


class TestColumns:
    def test_an_entity_sits_right_of_everything_that_references_it(self) -> None:
        svg = render_entity_diagram(_pair())
        (world_x, _, world_w, _), (user_x, _, _, _) = _boxes(svg)
        assert world_x + world_w < user_x

    def test_a_reference_chain_gets_one_column_per_link(self) -> None:
        chain = [
            _entity("A", "a", _ref("b", "→ B", 1)),
            _entity("B", "b", _ref("c", "→ C", 2)),
            _entity("C", "c"),
        ]
        assert len(_column_xs(render_entity_diagram(chain))) == 3

    def test_boxes_in_one_column_share_a_width(self) -> None:
        # Uniform column width is what makes the arrows between two columns
        # run parallel instead of fanning off ragged right edges.
        svg = render_entity_diagram(
            [
                _entity("Short", "a"),
                _entity("A considerably longer entity name", "b"),
            ]
        )
        widths = {width for _x, _y, width, _h in _boxes(svg)}
        assert len(widths) == 1

    def test_entities_keep_their_given_order_inside_a_column(self) -> None:
        # Deliberately no crossing-reduction pass: a reader looking for the
        # third entity in the table finds it above the fourth.
        svg = render_entity_diagram(
            [_entity("A", "a"), _entity("B", "b"), _entity("C", "c")]
        )
        ys = [y for _x, y, _w, _h in _boxes(svg)]
        assert ys == sorted(ys)

    def test_a_two_entity_cycle_terminates_in_two_columns(self) -> None:
        # Layering a graph with a cycle never settles on its own; the back
        # edge is dropped for layering only, and the cycle still draws.
        cycle = [
            _entity("A", "a", _ref("b", "→ B", 1)),
            _entity("B", "b", _ref("a", "→ A", 0)),
        ]
        svg = render_entity_diagram(cycle)
        assert len(_column_xs(svg)) == 2
        assert len(_edges(svg)) == 2

    def test_a_small_cycle_does_not_widen_a_large_diagram(self) -> None:
        # A bounded relaxation would let one three-entity cycle push every
        # unrelated entity rightwards, one column per pass.
        cycle_and_bystanders = [
            _entity("A", "a", _ref("b", "→ B", 1)),
            _entity("B", "b", _ref("c", "→ C", 2)),
            _entity("C", "c", _ref("a", "→ A", 0)),
        ] + [_entity(f"X{n}", f"x{n}") for n in range(8)]
        assert len(_column_xs(render_entity_diagram(cycle_and_bystanders))) == 3


# --------------------------------------------------------------------------
# Edges
# --------------------------------------------------------------------------


class TestEdges:
    def test_only_a_field_the_caller_resolved_becomes_an_edge(self) -> None:
        # Resolution is the html layer's job; an unresolved field renders as
        # a line of text in its box and draws nothing.
        entities = [
            _entity(
                "A",
                "a",
                DiagramField(name="ghost", detail="⚠ undefined: b", warn=True),
            )
        ]
        assert _edges(render_entity_diagram(entities)) == []

    def test_a_target_outside_the_drawn_set_is_dropped_rather_than_trusted(
        self,
    ) -> None:
        entities = [_entity("A", "a", _ref("b", "→ B", 7))]
        assert _edges(render_entity_diagram(entities)) == []

    def test_every_edge_gets_exactly_one_arrowhead(self) -> None:
        svg = render_entity_diagram(_pair())
        assert len(_arrows(svg)) == len(_edges(svg)) == 1

    def test_an_arrowhead_sits_on_the_end_of_the_curve_it_terminates(self) -> None:
        svg = render_entity_diagram(_pair())
        assert _points(_arrows(svg)[0])[0] == _path_end(_edges(svg)[0])

    @pytest.mark.parametrize("shape", ("forward", "backward", "self-reference"))
    def test_every_curve_arrives_horizontally_at_its_arrowhead(
        self, shape: str
    ) -> None:
        # The arrowhead is an axis-aligned triangle rather than an SVG marker
        # (a marker inherits neither the path's stroke nor the page's theme
        # without ``context-stroke``). That trade is only sound while the
        # curve's tangent where it lands is horizontal and non-zero: a
        # diagonal arrival, or control points collapsed onto the endpoint,
        # leaves a horizontal arrow on a slanted line.
        entities = {
            "forward": _pair(),
            "backward": [
                _entity("A", "a", _ref("b", "→ B", 1)),
                _entity("B", "b"),
                _entity("C", "c", _ref("a", "→ A", 0)),
            ],
            "self-reference": [
                _entity("Region", "ent-region", _ref("parent", "→ Region", 0))
            ],
        }[shape]
        svg = render_entity_diagram(entities)
        assert _edges(svg), "the fixture must draw at least one curve"
        for path in _edges(svg):
            numbers = [int(value) for value in re.findall(r"-?\d+", path)]
            control_x, control_y = numbers[4], numbers[5]
            end_x, end_y = numbers[6], numbers[7]
            assert control_y == end_y, "the tangent at the arrowhead is not level"
            assert control_x != end_x, "the tangent at the arrowhead has no length"

    def test_the_diagram_draws_one_terminator_shape_and_no_cardinality(
        self,
    ) -> None:
        # The carve-out, asserted rather than stated: the artifact records no
        # cardinality, so every edge ends the same way. A crow's foot, a
        # zero-or-one ring, or a `1..*` label would each introduce a second
        # kind of terminator, and this is what would catch it.
        svg = render_entity_diagram(
            [
                _entity("A", "a", _ref("b", "→ B", 1), _ref("c", "→ C", 2)),
                _entity("B", "b", _ref("a", "→ A", 0)),
                _entity("C", "c", _ref("c", "→ C", 2)),
            ]
        )
        shapes = {
            tuple(
                (x - _points(arrow)[0][0], y - _points(arrow)[0][1])
                for x, y in _points(arrow)
            )
            for arrow in _arrows(svg)
        }
        # Two: entering from the left, and entering from the right.
        assert len(shapes) <= 2
        assert all(
            len(shape) == 3 for shape in shapes
        ), "every terminator is the same three-point triangle"

    def test_two_references_to_one_entity_land_at_different_points(self) -> None:
        # Converging on a single point makes two distinct references read as
        # one thicker line.
        svg = render_entity_diagram(
            [
                _entity("A", "a", _ref("t", "→ T", 2)),
                _entity("B", "b", _ref("t", "→ T", 2)),
                _entity("T", "t"),
            ]
        )
        ends = [_path_end(path) for path in _edges(svg)]
        assert len(set(ends)) == 2

    def test_incoming_arrowheads_land_below_the_target_header(self) -> None:
        # Edges are drawn before opaque box headers. An arrowhead ending in
        # the header vanishes under the later fill rather than reaching its
        # target, so even a one-field target needs its arrivals in the body.
        svg = render_entity_diagram(
            [
                _entity("A", "a", _ref("t", "→ T", 2)),
                _entity("B", "b", _ref("t", "→ T", 2)),
                _entity("T", "t"),
            ]
        )
        target_y = _boxes(svg)[2][1]
        assert all(
            end_y >= target_y + 38
            for _end_x, end_y in map(_path_end, _edges(svg))
        )

    def test_a_self_reference_draws_a_loop_rather_than_a_zero_length_line(
        self,
    ) -> None:
        svg = render_entity_diagram(
            [_entity("Region", "ent-region", _ref("parent", "→ Region", 0))]
        )
        path = _edges(svg)[0]
        assert _path_start(path) != _path_end(path)

    def test_a_self_reference_stays_inside_its_own_box_vertically(self) -> None:
        # The loop re-enters the box it left; an endpoint below the box would
        # be an arrow pointing at empty canvas.
        svg = render_entity_diagram(
            [
                _entity(
                    "Region",
                    "ent-region",
                    DiagramField(name="name", detail="text"),
                    _ref("parent", "→ Region", 0),
                )
            ]
        )
        _x, y, _w, height = _boxes(svg)[0]
        for point in (_path_start(_edges(svg)[0]), _path_end(_edges(svg)[0])):
            assert y <= point[1] <= y + height

    @pytest.mark.parametrize(
        "targets",
        (
            ((1,), (0,)),  # two entities referencing each other
            ((1,), (2,), (0,)),  # a three-entity cycle
            ((1, 2), (2,), (0, 1)),  # a cycle with a chord both ways
            ((1,), (0, 2), (1,)),  # two overlapping two-cycles
        ),
    )
    def test_no_drawn_reference_connects_two_boxes_in_one_column(
        self, targets
    ) -> None:
        """The invariant ``_routes`` is allowed to have only two routes for.

        A kept edge puts its target one column right; a dropped one is a back
        edge, whose target is a DFS ancestor reached over kept edges and so
        sits strictly left. Neither can land in the source's own column — and
        if a later layering change makes one able to, this is what says so,
        rather than the edge quietly rendering through the box beside it.
        """
        entities = [
            _entity(
                f"E{index}",
                f"e{index}",
                *(_ref(f"f{n}", f"→ E{t}", t) for n, t in enumerate(row)),
            )
            for index, row in enumerate(targets)
        ]
        svg = render_entity_diagram(entities)
        # Every endpoint lands on a column's left or right face, and columns
        # share no face — they are a full gap apart — so a face x names the
        # column an endpoint belongs to. None of these fixtures references
        # itself, the one edge legitimately allowed both ends in one column.
        face_column = {}
        for column, x in enumerate(sorted({x for x, _y, _w, _h in _boxes(svg)})):
            width = next(w for bx, _y, w, _h in _boxes(svg) if bx == x)
            face_column[x] = column
            face_column[x + width] = column
        assert _edges(svg), "the fixture must draw at least one curve"
        for path in _edges(svg):
            start_x, _start_y = _path_start(path)
            end_x, _end_y = _path_end(path)
            assert start_x in face_column and end_x in face_column
            assert face_column[start_x] != face_column[end_x]

    def test_a_backward_reference_is_drawn_as_well_as_a_forward_one(self) -> None:
        entities = [
            _entity("A", "a", _ref("b", "→ B", 1)),
            _entity("B", "b"),
            _entity("C", "c", _ref("a", "→ A", 0)),
        ]
        assert len(_edges(render_entity_diagram(entities))) == 2

    def test_edges_are_emitted_before_the_boxes_they_connect(self) -> None:
        # A curve passing a box must run behind it; emitted after, it would
        # cross the box's own field text.
        svg = render_entity_diagram(_pair())
        assert svg.index('class="er-edge"') < svg.index('class="er-fill"')


# --------------------------------------------------------------------------
# Linking
# --------------------------------------------------------------------------


class TestLinking:
    def test_a_box_with_an_href_is_a_link(self) -> None:
        svg = render_entity_diagram([_entity("A", "a", href="#row-a")])
        assert '<a class="er-node" href="#row-a">' in svg

    def test_a_box_without_an_href_is_a_plain_group_and_not_a_dead_link(
        self,
    ) -> None:
        # ``None`` is how the caller says "this id names more than one row",
        # the same refusal the page's text references make.
        svg = render_entity_diagram([_entity("A", "a")])
        assert "<a " not in svg
        assert '<g class="er-node">' in svg

    def test_a_marked_box_carries_the_reason_in_its_hover_title(self) -> None:
        svg = render_entity_diagram(
            [_entity("A", "a", warn=True, note="⚠ ambiguous: a")]
        )
        assert "⚠ ambiguous: a" in svg
        assert "er-warn-box" in svg


# --------------------------------------------------------------------------
# Stylesheet
# --------------------------------------------------------------------------


class TestStyle:
    @pytest.mark.parametrize(
        "css_class",
        (
            "er-fill",
            "er-head",
            "er-box",
            "er-rule",
            "er-title",
            "er-id",
            "er-name",
            "er-detail",
            "er-edge",
            "er-arrow",
            "er-dot",
        ),
    )
    def test_every_class_the_diagram_emits_is_styled(self, css_class: str) -> None:
        # An SVG element with no fill/stroke rule renders black-on-black in
        # the dark theme — invisible, not merely unstyled.
        svg = render_entity_diagram(
            [
                _entity("A", "a", _ref("b", "→ B", 1)),
                _entity("B", "b"),
            ]
        )
        assert css_class in svg
        assert f".{css_class}" in ER_STYLE

    @pytest.mark.parametrize(
        "modifier", ("er-warn", "er-dim", "er-warn-box", "er-link")
    )
    def test_every_modifier_class_is_styled(self, modifier: str) -> None:
        assert f".{modifier}" in ER_STYLE

    def test_every_colour_falls_back_when_the_page_defines_no_variable(self) -> None:
        # The module is a leaf: it must render legibly on its own, not only
        # inside the page whose variables it prefers.
        for reference in re.findall(r"var\((--[a-z-]+)([^)]*)\)", ER_STYLE):
            assert reference[1].strip().startswith(","), (
                f"{reference[0]} has no fallback"
            )

    def test_the_font_sizes_in_the_stylesheet_match_the_geometry(self) -> None:
        # The whole no-measurement carve-out rests on these being one number,
        # not two: a 15px rule under a 12px estimate overflows every box.
        sizes = sorted(int(size) for size in re.findall(r"(\d+)px/1", ER_STYLE))
        assert sizes == [10, 12, 12, 13]

    def test_the_diagram_is_scaled_down_rather_than_clipped_when_printed(
        self,
    ) -> None:
        # On screen a wide diagram scrolls inside its container; a printed
        # page has no scrollbar, so it must fit instead.
        printed = ER_STYLE.split("@media print")[1]
        assert "max-width:100%" in printed
        assert "height:auto" in printed


def test_the_advance_estimate_is_not_narrower_than_the_fonts_it_assumes() -> None:
    """The one number the whole layout trusts, checked against reality.

    Every box width comes from ``cells × size × advance``. Menlo and DejaVu
    Sans Mono — both named in :data:`ER_STYLE` — advance .602em, so an
    estimate below that produces boxes their own text overflows, on the
    default macOS and Linux stacks respectively.
    """
    long_label = "x" * 20
    svg = render_entity_diagram([_entity(long_label, "ent-x")])
    width = _boxes(svg)[0][2]
    assert width >= 2 * _PAD + math.ceil(len(long_label) * 13 * _REAL_ADVANCE)
