"""ER-style geometry for the domain section of ``--view html``.

A stdlib-only leaf: :mod:`plan_tool.roadmap_html` resolves semantics and this
module lays out its boxes and edges. See ``ROADMAP_FORMAT.md`` for the view's
contract and deliberate carve-outs.
"""

from __future__ import annotations

import html
import unicodedata
from dataclasses import dataclass
from typing import Optional, Sequence

# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

# Font sizes, in px, matching the class rules in :data:`ER_STYLE`. Changing
# one without the other is what makes a box too small for its own text.
_FONT_TITLE = 13
_FONT_ID = 10
_FONT_FIELD = 12

# Monospace advance width in hundredths of an em. The stack in ER_STYLE tops
# out at .602em (Menlo, DejaVu Sans Mono); the rest are narrower, so this
# over-estimates slightly and a box is never too small for its text.
_ADVANCE = 62

_PAD = 12  # horizontal padding inside a box
_HEAD_H = 38  # header band: title baseline at 17, id baseline at 31
_FIELD_H = 19
_BODY_PAD = 8  # below the last field line
_COL_GAP = 96
_ROW_GAP = 28
_MARGIN = 18
_MIN_W = 148
_MID_GAP = 20  # least space between a field's name and its detail
_RADIUS = 7
_SELF_LOOP = 46  # how far a self-reference bulges past its own box
_SELF_DROP = 16  # vertical offset between a self-reference's two ends
_ARROW = 8
_ARROW_HALF = 4
_DOT_R = 3
_BEND_MIN = 30  # bezier control-point offset bounds
_BEND_MAX = 90

# Cell budgets per text run, past which a label is clipped and its full text
# moves to a hover ``<title>``.
_TITLE_CELLS = 30
_NAME_CELLS = 22
_DETAIL_CELLS = 26

_UNNAMED = "(unnamed)"
_NO_FIELDS = "(no fields)"
_ZWJ = "\u200d"
_WIDE_SYMBOLS = frozenset({"⚠"})


# --------------------------------------------------------------------------
# Input model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DiagramField:
    """One field line, already resolved by the caller."""

    name: str
    detail: str
    target: Optional[int] = None
    warn: bool = False
    note: Optional[str] = None


@dataclass(frozen=True)
class DiagramEntity:
    """One box and its optional table-row link."""

    title: str
    subtitle: str
    fields: tuple[DiagramField, ...] = ()
    href: Optional[str] = None
    warn: bool = False
    note: Optional[str] = None


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------


def _e(value: object) -> str:
    """Escape any value for SVG text or a quoted attribute."""
    return html.escape(str(value), quote=True)


def _cell_width(char: str) -> int:
    return (
        2
        if char in _WIDE_SYMBOLS
        or unicodedata.east_asian_width(char) in ("W", "F")
        else 1
    )


def _cells(text: str) -> int:
    """Monospace character cells, counting wide forms as two."""
    return sum(_cell_width(char) for char in text)


def _text_units(text: str) -> "tuple[str, ...]":
    """Text units that never split a ZWJ or combining sequence."""
    units: "list[str]" = []
    position = 0
    while position < len(text):
        start = position
        position += 1
        while position < len(text):
            char = text[position]
            if char == _ZWJ:
                position += 2 if position + 1 < len(text) else 1
            elif (
                unicodedata.category(char).startswith("M")
                or "\U0001f3fb" <= char <= "\U0001f3ff"
            ):
                position += 1
            else:
                break
        units.append(text[start:position])
    return tuple(units)


def _px(cells: int, size: int) -> int:
    """Integer-ceiling width of ``cells`` monospace cells at ``size`` px."""
    return (cells * size * _ADVANCE + 99) // 100


@dataclass(frozen=True)
class _Run:
    """One rendered text run and its optional hover note.

    ``cells`` is ``show``'s cell count, computed once by whoever builds this
    run — :func:`width` trusts it rather than re-scanning ``show`` on every
    call, since a box's width is queried once per title/subtitle/field line
    during layout.
    """

    show: str
    full: str
    cells: int
    note: Optional[str] = None

    @property
    def clipped(self) -> bool:
        return self.show != self.full

    def width(self, size: int) -> int:
        return _px(self.cells, size)


def _run(text: str, budget: int, *, note: Optional[str] = None) -> _Run:
    """Clip ``text`` to ``budget`` cells, keeping the original for the tooltip."""
    total = _cells(text)
    if total <= budget:
        return _Run(show=text, full=text, cells=total, note=note)
    kept: "list[str]" = []
    used = 0
    for unit in _text_units(text):
        width = _cells(unit)
        if used + width > budget - 1:
            break
        kept.append(unit)
        used += width
    show = "".join(kept) + "…"
    return _Run(show=show, full=text, cells=used + _cells("…"), note=note)


# --------------------------------------------------------------------------
# Boxes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Line:
    """A rendered field row: name on the left, detail right-aligned."""

    name: _Run
    detail: _Run
    warn: bool
    linked: bool


@dataclass
class _Box:
    entity: DiagramEntity
    title: _Run
    subtitle: _Run
    lines: tuple[_Line, ...]
    w: int = 0
    h: int = 0
    x: int = 0
    y: int = 0

    @property
    def right(self) -> int:
        return self.x + self.w

    def field_y(self, index: int) -> int:
        """The vertical centre of one field's row — where its edge leaves."""
        return self.y + _HEAD_H + index * _FIELD_H + _FIELD_H // 2


def _lines(entity: DiagramEntity) -> "tuple[_Line, ...]":
    """One ``_Line`` per field, or the explicit empty marker.

    An entity with no fields renders ``(no fields)`` rather than an empty box:
    a blank body reads as "not recorded" exactly as easily as "recorded as
    none", and the uniform geometry is a side benefit, not the reason.
    """
    if not entity.fields:
        return (
            _Line(
                name=_run(_NO_FIELDS, _NAME_CELLS),
                detail=_Run(show="", full="", cells=0),
                warn=False,
                linked=False,
            ),
        )
    return tuple(
        _Line(
            name=_run(field.name, _NAME_CELLS),
            detail=_run(field.detail, _DETAIL_CELLS, note=field.note),
            warn=field.warn,
            linked=field.target is not None,
        )
        for field in entity.fields
    )


def _box(entity: DiagramEntity) -> _Box:
    lines = _lines(entity)
    title = _run(entity.title or _UNNAMED, _TITLE_CELLS)
    subtitle = _run(entity.subtitle, _TITLE_CELLS)
    body = max(
        (
            line.name.width(_FONT_FIELD)
            + (_MID_GAP + line.detail.width(_FONT_FIELD) if line.detail.show else 0)
            for line in lines
        ),
        default=0,
    )
    width = max(
        _MIN_W,
        2 * _PAD
        + max(title.width(_FONT_TITLE), subtitle.width(_FONT_ID), body),
    )
    return _Box(
        entity=entity,
        title=title,
        subtitle=subtitle,
        lines=lines,
        w=width,
        h=_HEAD_H + len(lines) * _FIELD_H + _BODY_PAD,
    )


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------


def _edges(entities: Sequence[DiagramEntity]) -> "tuple[tuple[int, int, int], ...]":
    """``(source, field index, target)`` for every field the caller resolved
    to a drawn entity. Out-of-range targets are dropped rather than trusted."""
    return tuple(
        (source, index, field.target)
        for source, entity in enumerate(entities)
        for index, field in enumerate(entity.fields)
        if field.target is not None and 0 <= field.target < len(entities)
    )


def _forward_only(
    count: int, pairs: "Sequence[tuple[int, int]]"
) -> "list[tuple[int, int]]":
    """Drop DFS back edges before layering, preserving input order.

    Kept edges go right and dropped edges go left, so :func:`_routes` needs
    only those two directions.
    """
    adjacent: "dict[int, list[tuple[int, int]]]" = {node: [] for node in range(count)}
    for index, (source, target) in enumerate(pairs):
        adjacent[source].append((target, index))
    # 0 unvisited, 1 on the current path, 2 finished.
    state = [0] * count
    back: "set[int]" = set()
    for root in range(count):
        if state[root]:
            continue
        state[root] = 1
        stack = [(root, iter(adjacent[root]))]
        while stack:
            node, walker = stack[-1]
            descended = False
            for target, index in walker:
                if state[target] == 1:
                    back.add(index)
                elif state[target] == 0:
                    state[target] = 1
                    stack.append((target, iter(adjacent[target])))
                    descended = True
                    break
            if not descended:
                state[node] = 2
                stack.pop()
    return [pair for index, pair in enumerate(pairs) if index not in back]


def _columns(
    count: int, edges: "Sequence[tuple[int, int, int]]"
) -> "tuple[list[list[int]], list[int]]":
    """Entity indices grouped into columns, left to right.

    An entity sits one column right of every entity that references it, so an
    arrow reads left to right and the entities nothing points at end up on the
    left edge. Within a column the artifact's own order is kept: a reader
    looking for the third entity in the table finds it above the fourth, and
    no crossing-reduction heuristic gets to move it.

    Layered by a single Kahn's-algorithm pass rather than relaxing every edge
    up to ``count`` times: :func:`_forward_only` already guarantees ``pairs``
    is acyclic, so processing each node only after every edge into it has
    been seen computes the same longest-path-from-a-root layer in one O(V+E)
    sweep instead of O(V·E).
    """
    pairs = _forward_only(
        count,
        [(source, target) for source, _, target in edges if source != target],
    )
    adjacent: "list[list[int]]" = [[] for _ in range(count)]
    in_degree = [0] * count
    for source, target in pairs:
        adjacent[source].append(target)
        in_degree[target] += 1
    layer = [0] * count
    ready = [node for node in range(count) if in_degree[node] == 0]
    head = 0
    while head < len(ready):
        node = ready[head]
        head += 1
        for target in adjacent[node]:
            layer[target] = max(layer[target], layer[node] + 1)
            in_degree[target] -= 1
            if in_degree[target] == 0:
                ready.append(target)
    grouped: "dict[int, list[int]]" = {}
    for index, value in enumerate(layer):
        grouped.setdefault(value, []).append(index)
    return [grouped[key] for key in sorted(grouped)], layer


def _place(boxes: "list[_Box]", columns: "list[list[int]]") -> None:
    """Assign every box its position, and every column one shared width.

    Uniform width per column is what lets an outgoing edge leave every box in
    a column at the same x, so the arrows between two columns run parallel
    instead of fanning off ragged right edges.
    """
    widths = [max(boxes[index].w for index in column) for column in columns]
    heights = [
        sum(boxes[index].h for index in column) + _ROW_GAP * (len(column) - 1)
        for column in columns
    ]
    tallest = max(heights)
    x = _MARGIN
    for position, column in enumerate(columns):
        y = _MARGIN + (tallest - heights[position]) // 2
        for index in column:
            boxes[index].w = widths[position]
            boxes[index].x = x
            boxes[index].y = y
            y += boxes[index].h + _ROW_GAP
        x += widths[position] + _COL_GAP


# --------------------------------------------------------------------------
# Edges
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Route:
    """One drawn reference: its curve, its arrowhead, and how far right it
    reaches — the last so the canvas is wide enough for a bulging loop."""

    path: str
    arrow: str
    dot: str
    reach: int
    label: str


def _bend(distance: int) -> int:
    return max(_BEND_MIN, min(_BEND_MAX, distance // 2))


def _dot(x: int, y: int) -> str:
    """The mark on the field a reference leaves from, so a curve's origin is
    as findable as its arrowhead."""
    return f'<circle class="er-dot" cx="{x}" cy="{y}" r="{_DOT_R}"/>'


def _arrow(x: int, y: int, *, pointing_right: bool) -> str:
    """A filled triangle whose tip sits on the target's border.

    Drawn as an explicit polygon rather than an SVG ``<marker>``: a marker
    inherits neither the referencing path's stroke nor the page's theme
    without ``context-stroke``, and the entry direction here is always
    horizontal, so the triangle is exact.
    """
    tail = x - _ARROW if pointing_right else x + _ARROW
    return (
        f'<polygon class="er-arrow" points="{x},{y} '
        f"{tail},{y - _ARROW_HALF} {tail},{y + _ARROW_HALF}\"/>"
    )


def _routes(
    boxes: "list[_Box]",
    edges: "Sequence[tuple[int, int, int]]",
    column_of: "list[int]",
) -> "list[_Route]":
    """Every edge as a curve, with the endpoints on one target spread apart.

    Incoming edges are distributed down the side of the box they land on
    rather than converging on one point, so two references to the same entity
    stay tellable apart.
    """
    sides: "dict[tuple[int, int], list[int]]" = {}
    forward: "dict[int, bool]" = {}
    for position, (source, _index, target) in enumerate(edges):
        if source == target:
            continue
        points_right = column_of[target] > column_of[source]
        forward[position] = points_right
        side = 1 if points_right else -1
        sides.setdefault((target, side), []).append(position)
    slot = {
        position: (order, len(members))
        for members in sides.values()
        for order, position in enumerate(members)
    }

    routes: "list[_Route]" = []
    for position, (source, index, target) in enumerate(edges):
        start = boxes[source]
        end = boxes[target]
        label = f"{start.title.full} → {end.title.full}"
        start_y = start.field_y(index)
        if source == target:
            # Clamp the return below the last field; tests pin the padding invariant.
            end_y = min(start_y + _SELF_DROP, start.y + start.h - 2)
            edge_x = start.right
            routes.append(
                _Route(
                    path=(
                        f"M{edge_x} {start_y}C{edge_x + _SELF_LOOP} {start_y} "
                        f"{edge_x + _SELF_LOOP} {end_y} {edge_x} {end_y}"
                    ),
                    arrow=_arrow(edge_x, end_y, pointing_right=False),
                    dot=_dot(edge_x, start_y),
                    reach=edge_x + _SELF_LOOP,
                    label=label,
                )
            )
            continue

        order, total = slot[position]
        # The header is an opaque rect drawn over the edges. Spread arrivals
        # through the body only, so no arrowhead is hidden behind that band.
        body_top = end.y + _HEAD_H + _ARROW_HALF
        body_height = end.h - _HEAD_H - 2 * _ARROW_HALF
        end_y = body_top + body_height * (order + 1) // (total + 1)
        # Forward-only layering leaves each non-self edge left or right; see
        # ``test_no_drawn_reference_connects_two_boxes_in_one_column``.
        if forward[position]:
            start_x, end_x = start.right, end.x
            bend = _bend(end_x - start_x)
            controls = (start_x + bend, start_y, end_x - bend, end_y)
            pointing_right = True
            reach = max(start_x, end_x)
        else:
            start_x, end_x = start.x, end.right
            bend = _bend(start_x - end_x)
            controls = (start_x - bend, start_y, end_x + bend, end_y)
            pointing_right = False
            reach = max(start.right, end.right)
        routes.append(
            _Route(
                path=(
                    f"M{start_x} {start_y}C{controls[0]} {controls[1]} "
                    f"{controls[2]} {controls[3]} {end_x} {end_y}"
                ),
                arrow=_arrow(end_x, end_y, pointing_right=pointing_right),
                dot=_dot(start_x, start_y),
                reach=reach,
                label=label,
            )
        )
    return routes


# --------------------------------------------------------------------------
# Emission
# --------------------------------------------------------------------------


def _top_rounded(x: int, y: int, width: int, height: int, radius: int) -> str:
    """A rectangle rounded on its top two corners only — the header band,
    which must not poke past the box outline it sits inside."""
    return (
        f"M{x} {y + radius}A{radius} {radius} 0 0 1 {x + radius} {y}"
        f"H{x + width - radius}A{radius} {radius} 0 0 1 {x + width} {y + radius}"
        f"V{y + height}H{x}Z"
    )


def _text(
    x: int,
    y: int,
    run: _Run,
    css_class: str,
    *,
    anchor_end: bool = False,
) -> str:
    if not run.show:
        return ""
    anchor = ' text-anchor="end"' if anchor_end else ""
    tooltip_text = run.full if run.clipped else ""
    if run.note:
        tooltip_text = f"{tooltip_text} — {run.note}" if tooltip_text else run.note
    tooltip = f"<title>{_e(tooltip_text)}</title>" if tooltip_text else ""
    return (
        f'<text class="{css_class}" x="{x}" y="{y}"{anchor}>'
        f"{tooltip}{_e(run.show)}</text>"
    )


def _render_box(box: _Box) -> str:
    entity = box.entity
    x, y, width = box.x, box.y, box.w
    tooltip = f"{box.title.full} · {box.subtitle.full}"
    if entity.note:
        tooltip = f"{tooltip} — {entity.note}"
    outline = "er-box er-warn-box" if entity.warn else "er-box"
    parts = [
        f"<title>{_e(tooltip)}</title>",
        f'<rect class="er-fill" x="{x}" y="{y}" width="{width}" '
        f'height="{box.h}" rx="{_RADIUS}"/>',
        f'<path class="er-head" d="{_top_rounded(x, y, width, _HEAD_H, _RADIUS)}"/>',
        f'<line class="er-rule" x1="{x}" y1="{y + _HEAD_H}" '
        f'x2="{x + width}" y2="{y + _HEAD_H}"/>',
        f'<rect class="{outline}" x="{x}" y="{y}" width="{width}" '
        f'height="{box.h}" rx="{_RADIUS}"/>',
        _text(
            x + _PAD,
            y + 17,
            box.title,
            "er-title er-dim" if not entity.title else "er-title",
        ),
        _text(
            x + _PAD,
            y + 31,
            box.subtitle,
            "er-id er-warn" if entity.warn else "er-id",
        ),
    ]
    for index, line in enumerate(box.lines):
        baseline = y + _HEAD_H + index * _FIELD_H + 13
        parts.append(_text(x + _PAD, baseline, line.name, "er-name"))
        detail_class = "er-detail"
        if line.warn:
            detail_class = "er-detail er-warn"
        elif line.linked:
            detail_class = "er-detail er-link"
        parts.append(
            _text(
                x + width - _PAD,
                baseline,
                line.detail,
                detail_class,
                anchor_end=True,
            )
        )
    body = "".join(parts)
    if entity.href is None:
        return f'<g class="er-node">{body}</g>'
    return f'<a class="er-node" href="{_e(entity.href)}">{body}</a>'


def render_entity_diagram(entities: Sequence[DiagramEntity]) -> str:
    """One inline ``<svg>`` for ``entities``, or ``""`` when there are none.

    The caller owns the empty case: this module has no opinion on what a
    domain with no entities should say.
    """
    if not entities:
        return ""
    boxes = [_box(entity) for entity in entities]
    edges = _edges(entities)
    columns, column_of = _columns(len(boxes), edges)
    _place(boxes, columns)
    routes = _routes(boxes, edges, column_of)

    width = (
        max([box.right for box in boxes] + [route.reach for route in routes]) + _MARGIN
    )
    height = max(box.y + box.h for box in boxes) + _MARGIN
    # Edges first, so a curve passing a box runs behind it rather than over
    # its text.
    drawn = "".join(
        f'\n<g class="er-link-group"><title>{_e(route.label)}</title>'
        f'<path class="er-edge" d="{route.path}"/>{route.dot}{route.arrow}</g>'
        for route in routes
    )
    drawn += "".join(f"\n{_render_box(box)}" for box in boxes)
    caption = (
        f"Entity relationship diagram — {len(entities)} "
        f"{'entity' if len(entities) == 1 else 'entities'}, "
        f"{len(routes)} {'reference' if len(routes) == 1 else 'references'}"
    )
    return (
        f'<svg class="er-svg" role="img" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f"<title>{_e(caption)}</title>{drawn}\n</svg>"
    )


# --------------------------------------------------------------------------
# Style
# --------------------------------------------------------------------------

_MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# Every colour is a page variable with a literal fallback, so the diagram
# themes with whatever accent scopes it (``--acc``/``--acc-bg`` come from the
# enclosing ``details.concept-entity`` block, not the artifact family) and
# still renders legibly on its own. The font sizes below are the same numbers
# the geometry constants use — see this module's "no text measurement"
# carve-out.
ER_STYLE = f"""
.er{{margin:.1rem 0 .4rem}}
.er svg{{display:block}}
.er-fill{{fill:var(--card,#fff)}}
.er-head{{fill:var(--acc-bg,#f1f0ec)}}
.er-box{{fill:none;stroke:var(--line,#e2e1dc);stroke-width:1}}
.er-box.er-warn-box{{stroke:var(--warn,#a4531b);stroke-dasharray:5 3}}
.er-rule{{stroke:var(--line,#e2e1dc);stroke-width:1}}
.er-title{{fill:var(--fg,#1c1c1a);font:700 {_FONT_TITLE}px/1 {_MONO}}}
.er-title.er-dim{{fill:var(--muted,#6b6b66)}}
.er-id{{fill:var(--acc,var(--muted,#6b6b66));font:400 {_FONT_ID}px/1 {_MONO}}}
.er-name{{fill:var(--fg,#1c1c1a);font:400 {_FONT_FIELD}px/1 {_MONO}}}
.er-detail{{fill:var(--muted,#6b6b66);font:400 {_FONT_FIELD}px/1 {_MONO}}}
.er-detail.er-link{{fill:var(--acc,var(--accent,#2f5d8c))}}
.er-detail.er-warn,.er-id.er-warn{{fill:var(--warn,#a4531b);font-weight:700}}
.er-edge{{fill:none;stroke:var(--acc,var(--accent,#2f5d8c));stroke-width:1.4;opacity:.7}}
.er-arrow,.er-dot{{fill:var(--acc,var(--accent,#2f5d8c));opacity:.85}}
.er a.er-node{{cursor:pointer}}
.er a.er-node:hover .er-box{{stroke:var(--acc,var(--accent,#2f5d8c));stroke-width:2}}
@media print{{.er{{break-inside:avoid}}.er svg{{max-width:100%;height:auto}}}}
"""
