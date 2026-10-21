"""Generate the per-subcommand CLI reference under ``docs/cli/``.

This is a **leaf** doc-generation module: it imports the assembled parser
via :func:`plan_tool.cli.build_parser` and walks argparse's introspection
surface to render one Markdown file per subcommand plus an index. The
argparse parser is the single source of truth — flags, defaults, choices,
and ``help=`` text are read straight from the live actions, so the
reference cannot drift from the actual CLI surface.

The reference set is *generated, not directly edited*. The companion test
(``tests/cli/test_cli_reference.py``) regenerates in memory and fails on
any diff against the committed files; re-baseline an intentional CLI
change with::

    python -m plan_tool.cli_reference --write

The existing ``docs/*.md`` files remain hand-written user guides; this
module owns only the mechanical command reference.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Reference docs land here, one ``<command>.md`` per subcommand plus an
# ``README.md`` index. Resolved relative to the repo root (this file lives
# at ``<root>/plan_tool/cli_reference.py``).
REFERENCE_DIR = Path(__file__).resolve().parent.parent / "docs" / "cli"


def _subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise AssertionError("build_parser() registered no subparsers action")


def _alias_map(
    action: argparse._SubParsersAction,
) -> dict[str, list[str]]:
    """Map each primary command name to its alias list (canonical excluded).

    argparse stores ``alias -> same parser object`` in ``choices``; the
    primary name is the one carried by the ``_choices_actions`` pseudo-
    actions. Aliases are every *other* choice key pointing at the same
    parser object.
    """
    primaries = [ca.dest for ca in action._choices_actions]
    by_parser: dict[int, list[str]] = defaultdict(list)
    for name, parser in action.choices.items():
        by_parser[id(parser)].append(name)
    aliases: dict[str, list[str]] = {}
    for primary in primaries:
        group = by_parser[id(action.choices[primary])]
        aliases[primary] = [n for n in group if n != primary]
    return aliases


def _format_default(action: argparse.Action) -> str:
    """Render an action's default as a short, deterministic cell value."""
    default = action.default
    if default is None or default is argparse.SUPPRESS:
        return "—"
    if isinstance(action, argparse.BooleanOptionalAction):
        return "on" if default else "off"
    if default is False:
        return "off"
    if default is True:
        return "on"
    if isinstance(default, (list, tuple)) and not default:
        return "—"
    return f"`{default}`"


def _format_invocation(action: argparse.Action) -> str:
    """Render the left-hand 'how you type it' cell for one action."""
    if not action.option_strings:
        # Positional: show the metavar (or dest) it binds.
        return f"`{action.metavar or action.dest}`"
    flags = ", ".join(f"`{opt}`" for opt in action.option_strings)
    if action.choices:
        choices = "|".join(str(c) for c in action.choices)
        return f"{flags} `{{{choices}}}`"
    if action.nargs == 0 or isinstance(
        action, argparse.BooleanOptionalAction
    ):
        return flags
    metavar = action.metavar or action.dest.upper()
    return f"{flags} `{metavar}`"


def _clean_help(action: argparse.Action) -> str:
    """One-line, table-safe help text for an action."""
    text = " ".join((action.help or "").split())
    return text.replace("|", "\\|")


def _render_parser_body(
    invocation: str, parser: argparse.ArgumentParser, level: int
) -> list[str]:
    """Render usage + arguments + options for one parser at heading ``level``.

    ``invocation`` is the full typed prefix (e.g. ``checkpoint list``).
    Nested subparsers recurse one heading level deeper, so a command's
    subactions render as subsections within the same file — keeping the
    one-file-per-top-level-command structure while covering every flag.
    """
    hN = "#" * level
    lines: list[str] = []

    usage = " ".join(parser.format_usage().split())
    usage = usage[len("usage: "):] if usage.startswith("usage: ") else usage
    lines += [f"{hN} Usage", "", "```", usage, "```", ""]
    # Apply-only is a distinct mode from stage runs; surface its shorter form
    # so operators do not have to parse the XOR out of the combined usage line.
    if invocation == "roadmap":
        lines += [
            "```",
            "plan-tool roadmap [-h] [-y] --apply slug",
            "```",
            "",
        ]

    positionals = [
        a
        for a in parser._actions
        if not a.option_strings and not isinstance(a, argparse._SubParsersAction)
    ]
    optionals = [
        a
        for a in parser._actions
        if a.option_strings and not isinstance(a, argparse._HelpAction)
    ]

    if positionals:
        lines += [
            f"{hN} Arguments",
            "",
            "| Argument | Description |",
            "| --- | --- |",
        ]
        for action in positionals:
            lines.append(
                f"| {_format_invocation(action)} | {_clean_help(action)} |"
            )
        lines.append("")

    if optionals:
        lines += [
            f"{hN} Options",
            "",
            "| Option | Default | Description |",
            "| --- | --- | --- |",
        ]
        for action in optionals:
            lines.append(
                f"| {_format_invocation(action)} | {_format_default(action)} "
                f"| {_clean_help(action)} |"
            )
        lines.append("")

    nested = [
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    ]
    for sub_action in nested:
        for pseudo in sub_action._choices_actions:
            sub_name = pseudo.dest
            sub_parser = sub_action.choices[sub_name]
            lines += [f"{hN} `plan-tool {invocation} {sub_name}`", ""]
            if pseudo.help:
                lines += [" ".join(pseudo.help.split()), ""]
            lines += _render_parser_body(
                f"{invocation} {sub_name}", sub_parser, level + 1
            )

    return lines


def render_command(
    name: str, parser: argparse.ArgumentParser, aliases: list[str]
) -> str:
    """Render the reference Markdown for a single top-level subcommand."""
    lines: list[str] = [f"# `plan-tool {name}`", ""]
    if aliases:
        alias_str = ", ".join(f"`{a}`" for a in aliases)
        lines += [f"**Aliases:** {alias_str}", ""]
    if parser.description:
        lines += [" ".join(parser.description.split()), ""]

    lines += _render_parser_body(name, parser, level=2)
    return "\n".join(lines).rstrip() + "\n"


def render_index(commands: list[tuple[str, str]]) -> str:
    """Render the ``README.md`` index linking every command reference.

    ``commands`` is a list of ``(name, summary)`` in display order.
    """
    lines = [
        "# plan-tool CLI reference",
        "",
        "Per-subcommand reference, generated from the argparse parser by",
        "`python -m plan_tool.cli_reference --write`. Do not edit directly — the",
        "files here are regenerated and drift-checked in CI. For narrative",
        "walkthroughs see the user guides in `docs/` (e.g. `RUNBOOK.md`).",
        "",
        "| Command | Summary |",
        "| --- | --- |",
    ]
    for name, summary in commands:
        summary = " ".join(summary.split()).replace("|", "\\|")
        lines.append(f"| [`{name}`]({name}.md) | {summary} |")
    return "\n".join(lines).rstrip() + "\n"


@contextmanager
def _plain_text_help() -> "Iterator[None]":
    """Force argparse to render uncolored help/usage for the duration.

    Python 3.14 colorizes argparse output whenever ``_colorize.can_colorize()``
    says so, and that honors ambient ``FORCE_COLOR`` / ``PYTHON_COLORS``
    **without requiring a TTY**. Generated reference docs must be identical no
    matter whose shell ran the generator, so color is pinned here rather than
    inherited — otherwise ``--write`` from a `FORCE_COLOR` shell commits ANSI
    escapes into ``docs/cli/*.md`` and the drift guard then fails for everyone.

    Setting ``NO_COLOR`` is what actually works, and the reason is not obvious:
    ``add_subparsers`` builds each subparser's ``prog`` string *through a
    formatter* at construction time, so a colored parent bakes escapes into
    every child's prog. Flipping ``parser.color`` afterwards leaves those
    already embedded — the environment has to be set **before the parser is
    built**, which is why this wraps ``build_parser`` too.
    """
    saved = os.environ.get("NO_COLOR")
    os.environ["NO_COLOR"] = "1"
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("NO_COLOR", None)
        else:
            os.environ["NO_COLOR"] = saved


def render_reference() -> dict[str, str]:
    """Render the whole reference set as ``{relative_filename: markdown}``."""
    # Imported here (not at module top) so this leaf doesn't sit on the
    # ``cli`` import path at import time.
    import plan_tool.cli as cli

    files: dict[str, str] = {}
    index_rows: list[tuple[str, str]] = []
    # The whole build+render runs under the pin: construction bakes prog
    # strings, and each ``format_usage`` re-checks color at call time.
    with _plain_text_help():
        parser = cli.build_parser()
        action = _subparsers_action(parser)
        aliases = _alias_map(action)
        for pseudo in action._choices_actions:
            name = pseudo.dest
            subparser = action.choices[name]
            files[f"{name}.md"] = render_command(name, subparser, aliases[name])
            index_rows.append((name, pseudo.help or ""))
    files["README.md"] = render_index(index_rows)
    return files


def write_reference(dest: Path = REFERENCE_DIR) -> list[Path]:
    """Write the reference set to ``dest``; return the paths written."""
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, content in render_reference().items():
        path = dest / filename
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m plan_tool.cli_reference",
        description="Generate the per-subcommand CLI reference under docs/cli/.",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="write the reference files to docs/cli/ (default: print to stdout).",
    )
    args = ap.parse_args(argv)
    if args.write:
        for path in write_reference():
            print(path)
    else:
        for filename, content in render_reference().items():
            print(f"===== {filename} =====")
            print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
