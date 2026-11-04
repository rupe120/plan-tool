"""JIRA command module — the ``jira`` integration verb.

Holds the ``jira`` export handler (``cmd_jira``), its epic-resolution
helpers (``_assign_epic_for_plan`` / ``_prompt_new_epic_inline`` /
``_resolve_epic_for_plan``), its sibling plan-tag-resolution helpers
(``_assign_plan_tag_for_plan`` / ``_resolve_plan_tag_for_plan`` /
``_dedupe_plan_tag`` — the short grouping tag rendered into every story
title), the ``jira config`` sub-action (``cmd_jira_config`` /
``_print_jira_config`` / ``_run_jira_config_wizard``) and the six-member
``_wizard_*`` family, plus a :func:`register` that contributes the
``jira`` subparser to the shared ``add_subparsers`` action (see
:mod:`plan_tool.cli.parser`).

``jira config`` is *not* a second registered subparser: it is dispatched
inside ``cmd_jira`` via ``args.name == "config"``, so :func:`register`
returns a single ``{"jira": cmd_jira}`` entry.

Named ``jira_cmd`` (not ``jira``) so ``from plan_tool.cli import jira``
can never shadow the domain module :mod:`plan_tool.jira`.

Like every per-intent command module, this imports only the cycle-free
leaves (:mod:`plan_tool.cli.context`) and the domain packages — never
:mod:`plan_tool.cli.app`. ``app`` re-imports these names back into its
own namespace so the package surface stays intact.

``cmd_jira`` reads its Jira exporter as a bare-name **module global**, so
tests that stub it must ``setattr`` it on *this* module
(``plan_tool.cli.jira_cmd``), not on ``app``'s re-imported alias.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from plan_tool.cli.context import _load_context, _resolve_cmd_repo_root
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.jira import (
    JiraPublicationResult,
    JiraError,
    derive_default_handoff_output_path,
    derive_jira_output_path,
    derive_plan_tag_acronym,
    export_jira,
    partition_lint_findings,
    plan_slug_from_path,
    read_stories_for_lint,
    render_jira_export,
    shell_jira_invoker,
)
from plan_tool.jira_config import (
    Epic,
    JiraConfig,
    JiraConfigError,
    default_config_path as default_jira_config_path,
    epic_key_collision_warnings,
    load_jira_config,
    plan_rel_path,
    validate_epic_key,
    validate_new_epic_key_distinct_from_jira_projects,
    validate_plan_tag,
    write_jira_config,
)
from plan_tool.locator import (
    ManifestError,
    PlanToolContext,
    build_plan_tool_context,
    resolve_plan_for_context,
)
from plan_tool.parser import parse_plan
from plan_tool.progress import NullReporter
from plan_tool.style import error, warn


def cmd_jira(args: argparse.Namespace) -> int:
    """Export plan steps as copy-paste-ready JIRA stories (integration).

    Intent: bridge plan-tool's step graph to a sprint-planning tool by
    making one claude call against the whole plan and emitting a
    consolidated set of stories, each an atomic PR (independently
    mergeable without breaking the build); ``--max-hours`` is an
    advisory size target, not a hard cap. Stories may *consolidate*
    small adjacent steps or *split* an oversize step into independently
    shippable slices; every plan step must appear in at least one
    story's ``steps:`` (parser-enforced).

    The legacy positional ``name`` is overloaded — ``jira config``
    dispatches to :func:`cmd_jira_config` (state management on
    ``jira-config.json``). Future integrations with other systems
    (e.g. Linear, Asana) should live as sibling subcommands rather
    than overloading this verb further; the ``config`` sub-action is
    grandfathered in for backwards compatibility.

    Writes to ``<plan-dir>/plan-details/<plan-slug>/jira-stories.{md,json}``
    by default. ``--no-write`` falls back to stdout-only.

    Every export pairs the story source with a generated Markdown developer
    handoff from one captured input snapshot — see
    :func:`plan_tool.jira.export_jira` and ``docs/cli/jira.md``.

    See ``docs/reference/contracts/process.md`` for final-output authority and handoff.
    """
    # ``--adopt-existing`` is export authority, never a config/lint option.
    # ``getattr`` keeps hand-built stage namespaces compatible.
    handoff_output = getattr(args, "handoff_output", None)
    adopt_existing = getattr(args, "adopt_existing", False)
    if (handoff_output is not None or adopt_existing) and args.name == "config":
        error("jira export options cannot be combined with `jira config`")
        return 2
    if (handoff_output is not None or adopt_existing) and args.lint:
        error("jira export options cannot be combined with --lint")
        return 2

    # Sub-action dispatch: ``jira config ...`` routes to ``cmd_jira_config``.
    # The default (no subaction) is the legacy export flow that requires
    # a plan name. ``name == "config"`` is the discriminator so we keep
    # backwards compatibility with ``plan-tool jira <plan-name>``.
    if args.name == "config":
        return cmd_jira_config(args)
    if args.lint:
        return cmd_jira_lint(args)
    if args.name is None:
        error(
            "jira requires a plan name (or use `jira config`)"
        )
        return 2

    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)

    output_path = Path(args.output).resolve() if args.output else None

    resolved = _resolve_export_epic_and_tag(ctx, path, args)
    if resolved is None:
        return 2
    epic, plan_tag = resolved
    return _cmd_jira_paired_export(
        args,
        ctx=ctx,
        path=path,
        story_output_path=output_path,
        handoff_output=handoff_output,
        epic=epic,
        plan_tag=plan_tag,
        adopt_existing=adopt_existing,
    )


def _resolve_export_epic_and_tag(
    ctx: PlanToolContext, path: Path, args: argparse.Namespace
) -> Optional[tuple[Epic, str]]:
    """Resolve (assigning/persisting as needed) the epic + jira tag for an export.

    Resolves the paired export's settings, prompting/persisting to
    ``jira-config.json`` on a
    TTY or auto-deriving off one. Returns ``None`` when resolution or
    assignment fails; the callee has already printed a diagnostic (mirrors
    :func:`_assign_epic_for_plan` / :func:`_assign_plan_tag_for_plan`'s own
    contract), so the caller just returns 2.
    """
    epic = _resolve_epic_for_plan(ctx.repo_root, path)
    if epic is None:
        try:
            epic = _assign_epic_for_plan(
                ctx.repo_root, path, requested_key=args.epic
            )
        except JiraConfigError as exc:
            error(str(exc))
            return None
        if epic is None:
            return None

    # Cosmetic (a grouping aid, not an id-uniqueness requirement), so unlike
    # epic assignment a missing tag never blocks the export: on a TTY the
    # operator confirms/edits a deterministic suggestion (or `-y`
    # auto-accepts it); off a TTY it's auto-derived and persisted silently.
    # See :func:`_assign_plan_tag_for_plan`.
    plan_tag = _resolve_plan_tag_for_plan(ctx.repo_root, path)
    if plan_tag is None:
        try:
            plan_tag = _assign_plan_tag_for_plan(
                ctx.repo_root,
                path,
                requested_tag=args.jira_tag,
                auto_accept=args.yes,
            )
        except JiraConfigError as exc:
            error(str(exc))
            return None
        # ``None`` here just means "nothing to derive" (e.g. a punctuation-only
        # slug) or an unassignable path — cosmetic, so fall back to no tag
        # rather than blocking the export the way a missing epic does.
        plan_tag = plan_tag or ""

    return epic, plan_tag


def _print_companion_artifacts(
    *, story_path: Path, story_output: str, handoff_path: Path, handoff_output: str
) -> None:
    """Print both labeled generated artifacts (no-write, and --stdout)."""
    print(f"--- story ({story_path}) ---")
    print(story_output)
    print(f"--- developer handoff ({handoff_path}) ---")
    print(handoff_output)


def _print_companion_followups(result: JiraPublicationResult) -> None:
    """Warn about the two things only a person can finish in JIRA.

    Companion analog of :func:`_print_jira_followups`: plan-tool never
    edits JIRA, so naming the story id and live key is the whole remedy.
    Both are advisory: neither changes the exit code.
    """
    for notice in result.changed_created_tickets:
        warn(
            f"story {notice.story_id} regenerated with a live JIRA key "
            f"({notice.jira_issue_key}) — update the ticket in JIRA to "
            "match."
        )
    for notice in result.created_to_dropped:
        warn(
            f"story {notice.story_id} (JIRA {notice.jira_issue_key}) no "
            "longer covers a committed plan step — cancel, close, or "
            "repurpose the ticket in JIRA."
        )


def _cmd_jira_paired_export(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    path: Path,
    story_output_path: Optional[Path],
    handoff_output: Optional[str],
    epic: Epic,
    plan_tag: str,
    adopt_existing: bool,
) -> int:
    """Render or publish the mandatory story/handoff export pair.

    The caller already resolves the export's epic and tag. This helper owns
    destination derivation and presentation while :mod:`plan_tool.jira`
    owns capture, validation, and paired publication.
    """
    resolved_story_path = (
        story_output_path
        if story_output_path is not None
        else derive_jira_output_path(path, None, format=args.format)
    ).resolve()
    resolved_handoff_path = (
        Path(handoff_output).resolve()
        if handoff_output
        else derive_default_handoff_output_path(resolved_story_path, path)
    )

    if args.no_write:
        try:
            rendered = render_jira_export(
                path,
                repo_root=ctx.repo_root,
                epic=epic,
                story_output_path=resolved_story_path,
                handoff_output_path=resolved_handoff_path,
                format=args.format,
                max_hours=args.max_hours,
                plan_tag=plan_tag,
                adopt_existing=adopt_existing,
                invoker=shell_jira_invoker,
            )
        except (JiraError, JiraConfigError) as exc:
            error(str(exc))
            return 2
        # --no-write: nothing landed on disk by design; stream both artifacts.
        # The handoff prints render_handoff_body's output alone — no title
        # heading, provenance stamp, or "Generated from" note, all of which
        # render_handoff adds on top for a real write. Provenance in
        # particular exists to prove ownership of a *written* file, and
        # nothing here is written.
        _print_companion_artifacts(
            story_path=resolved_story_path,
            story_output=rendered.story_export.output,
            handoff_path=resolved_handoff_path,
            handoff_output=rendered.handoff_body,
        )
        return 0

    try:
        result = export_jira(
            path,
            repo_root=ctx.repo_root,
            epic=epic,
            story_output_path=resolved_story_path,
            handoff_output_path=resolved_handoff_path,
            format=args.format,
            max_hours=args.max_hours,
            plan_tag=plan_tag,
            adopt_existing=adopt_existing,
        )
    except (JiraError, JiraConfigError) as exc:
        error(str(exc))
        return 2

    print(
        f"wrote story to {result.story_path} and developer handoff to "
        f"{result.handoff_path}"
    )
    _print_companion_followups(result)
    if args.stdout:
        _print_companion_artifacts(
            story_path=result.story_path,
            story_output=result.story_output,
            handoff_path=result.handoff_path,
            handoff_output=result.handoff_output,
        )
    return 0


def cmd_jira_lint(args: argparse.Namespace) -> int:
    """Lint an existing jira-stories artifact without invoking claude.

    ``--input`` checks a specific markdown/JSON export. Without
    ``--input``, ``name`` resolves to a plan and the conventional
    ``jira-stories`` artifact beside that plan is checked. This path
    deliberately does not resolve or assign epics; linting an existing
    artifact must not dirty ``jira-config.json``.
    """
    if args.input and args.name:
        error("jira --lint accepts either a plan name or --input, not both")
        return 2
    if not args.input and args.name is None:
        error("jira --lint requires a plan name or --input <path>")
        return 2

    try:
        if args.input:
            target = Path(args.input).resolve()
            if not target.is_file():
                error(f"jira lint input does not exist: {target}")
                return 2
            stories = read_stories_for_lint(target)
        else:
            ctx = _load_context(args)
            plan_path = resolve_plan_for_context(ctx, args.name)
            plan = parse_plan(plan_path)
            target = _resolve_jira_lint_artifact(
                plan_path, plan, preferred_format=args.format
            )
            if target is not None:
                stories = read_stories_for_lint(target)
            else:
                error(
                    "jira lint artifact does not exist for "
                    f"{plan_path}; run `plan-tool jira {args.name}` first "
                    "or pass --input <path>"
                )
                return 2
    except JiraError as exc:
        error(str(exc))
        return 2

    # Severity split (blocking vs advisory) is owned by jira.py so --lint and
    # the export write gate can't drift; the handler only reports the verdict.
    blocking, advisory_findings = partition_lint_findings(stories)
    for body in blocking + advisory_findings:
        warn(body)
    if blocking:
        noun = "finding" if len(blocking) == 1 else "findings"
        error(
            f"jira lint found {len(blocking)} acceptance-criteria {noun} "
            f"in {target}"
        )
        return 1
    noun = "story" if len(stories) == 1 else "stories"
    if advisory_findings:
        advisory = "warning" if len(advisory_findings) == 1 else "warnings"
        print(
            f"jira lint passed with {len(advisory_findings)} advisory "
            f"{advisory}: {len(stories)} {noun} checked in {target}"
        )
    else:
        print(f"jira lint passed: {len(stories)} {noun} checked in {target}")
    return 0


def _resolve_jira_lint_artifact(
    plan_path: Path, plan, *, preferred_format: str
) -> Optional[Path]:
    """Return the existing conventional jira artifact for ``plan_path``."""
    formats = ["markdown", "json"]
    if preferred_format == "json":
        formats = ["json", "markdown"]
    for fmt in formats:
        candidate = derive_jira_output_path(plan_path, plan, format=fmt)
        if candidate.is_file():
            return candidate
    return None


def _assign_epic_for_plan(
    repo_root: Path,
    plan_path: Path,
    *,
    requested_key: Optional[str] = None,
) -> Optional[Epic]:
    """Interactively (or via ``--epic <key>``) assign an epic to a plan.

    Returns the chosen :class:`Epic` and persists the assignment to
    ``jira-config.json`` so subsequent runs skip the prompt. Returns
    ``None`` when assignment can't proceed — prints a diagnostic to
    stderr in that case:

    - The repo has no epics defined yet AND stdin is not a TTY (tell
      the user to run ``plan-tool jira config`` to add one). On a TTY,
      the user is offered the inline "new epic" flow instead.
    - The plan path is outside ``repo_root`` (not assignable).
    - ``requested_key`` doesn't match any defined epic.
    - Non-TTY stdin and no ``--epic`` was passed (preserves
      script-friendly failure: don't hang waiting for input).
    - The interactive prompt was empty / cancelled.

    When the TTY user picks ``new`` (or accepts the offer on an empty
    config), the inline epic-creation prompt collects key / name /
    optional JIRA id / optional description, appends the new epic to
    the in-memory config, and continues with assignment. The combined
    config (new epic + assignment) is persisted in a single write so a
    Ctrl-C during the assignment write doesn't leave a half-saved
    epic without its assignment.

    Raises :class:`JiraConfigError` only when persisting the updated
    config fails or the existing file is malformed; the caller surfaces
    that to the user.
    """
    import builtins

    config = load_jira_config(repo_root)

    rel = plan_rel_path(plan_path, repo_root)
    if rel is None:
        error(
            f"plan {plan_path} is not under repo root {repo_root}; "
            "cannot record an assignment for it."
        )
        return None

    if not config.epics:
        # No epics yet. Headless callers still get the actionable
        # error (matches the original contract); TTY users are offered
        # the inline "create the first epic" flow so the very first
        # plan can bootstrap jira-config.json without a second command.
        if requested_key is not None:
            error(
                "no epics defined in jira-config.json — run "
                "`plan-tool jira config` to add one before assigning a plan."
            )
            return None
        if not sys.stdin.isatty():
            error(
                "no epics defined in jira-config.json — run "
                "`plan-tool jira config` to add one before assigning a plan."
            )
            return None
        print(
            f"plan `{rel}` is not yet assigned to an epic, and no epics "
            "are defined yet.",
            file=sys.stderr,
        )
        try:
            answer = builtins.input(
                "create a new epic now? [Y/n]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  cancelled — no epic assigned.", file=sys.stderr)
            return None
        if answer in ("n", "no"):
            print(
                "  cancelled — run `plan-tool jira config` to add an "
                "epic, then re-run.",
                file=sys.stderr,
            )
            return None
        new_epic = _prompt_new_epic_inline(config)
        if new_epic is None:
            return None
        config.epics.append(new_epic)
        chosen_key = new_epic.key
        config.plan_assignments[rel] = chosen_key
        write_jira_config(config, default_jira_config_path(repo_root))
        print(
            f"added epic {new_epic.key} ({new_epic.name}); "
            f"assigned {rel} → {chosen_key}",
            file=sys.stderr,
        )
        return new_epic

    available = ", ".join(e.key for e in config.epics)

    chosen_key: Optional[str] = None
    if requested_key is not None:
        chosen_key = requested_key.strip().upper()
        if config.epic_by_key(chosen_key) is None:
            error(
                f"--epic {requested_key!r} does not match any "
                f"defined epic (available: {available})."
            )
            return None
    else:
        if not sys.stdin.isatty():
            error(
                f"plan {rel} has no epic assigned and stdin is "
                "not a TTY. Re-run with `--epic <KEY>` (available: "
                f"{available}) or assign via `plan-tool jira config`."
            )
            return None
        print(
            f"plan `{rel}` is not yet assigned to an epic.",
            file=sys.stderr,
        )
        print("available epics:", file=sys.stderr)
        for epic in config.epics:
            label = f"  {epic.key} — {epic.name}"
            print(label, file=sys.stderr)
        try:
            raw = builtins.input(
                f"assign to which epic? ({available}, or `new` to add "
                "a new epic): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  cancelled — no epic assigned.", file=sys.stderr)
            return None
        if not raw:
            print("  no epic selected.", file=sys.stderr)
            return None
        if raw.lower() in ("n", "new"):
            new_epic = _prompt_new_epic_inline(config)
            if new_epic is None:
                return None
            config.epics.append(new_epic)
            chosen_key = new_epic.key
        else:
            chosen_key = raw.upper()
            if config.epic_by_key(chosen_key) is None:
                print(
                    f"  no epic with key {chosen_key!r} (available: "
                    f"{available}, or `new` to add a new epic).",
                    file=sys.stderr,
                )
                return None

    config.plan_assignments[rel] = chosen_key
    write_jira_config(config, default_jira_config_path(repo_root))
    chosen = config.epic_by_key(chosen_key)
    assert chosen is not None  # validated above
    print(f"assigned {rel} → {chosen.key}", file=sys.stderr)
    return chosen


def _prompt_new_epic_inline(config: JiraConfig) -> Optional[Epic]:
    """Interactively collect a new :class:`Epic` for inline creation.

    Used by :func:`_assign_epic_for_plan` so the user can add a new
    epic from within the assignment prompt without dropping out to
    ``plan-tool jira config``. Mirrors :func:`_wizard_add_epic`'s
    prompts (key / name / optional jira id / optional description)
    but returns the :class:`Epic` rather than mutating ``config`` — the
    caller appends and persists in one write so a Ctrl-C between the
    epic creation and the assignment can't leave a dangling epic.

    Returns ``None`` (and prints a stderr diagnostic) when the input
    is invalid, the key already exists, the name is empty, or the
    user cancels with Ctrl-C / EOF. All prompts and diagnostics flow
    through stderr so the surrounding ``jira`` command's stdout
    (success summary or formatted output) stays clean for piping.
    """
    import builtins

    try:
        key_raw = builtins.input(
            "  new epic key (uppercase, e.g. AUTH): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled — no epic added.", file=sys.stderr)
        return None
    key = key_raw.upper()
    if not key:
        print("  no key entered; cancelled.", file=sys.stderr)
        return None
    try:
        validate_epic_key(key)
    except JiraConfigError as exc:
        print(f"  {exc}", file=sys.stderr)
        return None
    if config.epic_by_key(key) is not None:
        print(
            f"  epic {key!r} already exists; pick it from the list "
            "instead.",
            file=sys.stderr,
        )
        return None
    try:
        name = builtins.input("  epic name (human-readable): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled — no epic added.", file=sys.stderr)
        return None
    if not name:
        print("  name is required; cancelled.", file=sys.stderr)
        return None
    try:
        jira_id_raw = builtins.input(
            "  real JIRA epic id (optional, e.g. PROJ-1234): "
        ).strip()
        description_raw = builtins.input(
            "  description (optional, free text): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled — no epic added.", file=sys.stderr)
        return None
    jira_id = jira_id_raw or None
    try:
        validate_new_epic_key_distinct_from_jira_projects(
            key, jira_id, other_epics=config.epics
        )
    except JiraConfigError as exc:
        print(f"  {exc}", file=sys.stderr)
        return None
    return Epic(
        key=key,
        name=name,
        jira_epic_id=jira_id,
        description=description_raw or None,
    )


def _resolve_epic_for_plan(
    repo_root: Path, plan_path: Path
) -> Optional[Epic]:
    """Look up the epic assigned to ``plan_path`` in ``jira-config.json``.

    Returns ``None`` when the config file is absent, when the plan path
    doesn't live under ``repo_root``, when the plan has no assignment
    entry, or when the entry references an epic key that no longer
    exists. Config-loader errors (malformed JSON, invalid shapes) bubble
    out as :class:`JiraConfigError` — the caller surfaces them so a
    broken config doesn't silently degrade to legacy behavior.
    """
    config = load_jira_config(repo_root)
    rel = plan_rel_path(plan_path, repo_root)
    if rel is None:
        return None
    return config.epic_for_plan(rel)


def _resolve_plan_tag_for_plan(
    repo_root: Path, plan_path: Path
) -> Optional[str]:
    """Look up the confirmed jira tag for ``plan_path`` in ``jira-config.json``.

    Returns ``None`` when the config file is absent, when the plan path
    doesn't live under ``repo_root``, or when the plan has no confirmed
    tag yet. Config-loader errors bubble out as :class:`JiraConfigError`
    (mirrors :func:`_resolve_epic_for_plan`).
    """
    config = load_jira_config(repo_root)
    rel = plan_rel_path(plan_path, repo_root)
    if rel is None:
        return None
    return config.tag_for_plan(rel)


def _dedupe_plan_tag(candidate: str, existing: set[str]) -> str:
    """Disambiguate ``candidate`` against ``existing`` tags with a numeric suffix.

    Two differently-named plans can derive the same acronym (e.g.
    "decomposition-convergence-loop" and "data-consistency-layer" both ->
    "DCL") — the grouping tag only helps if it's actually distinguishing,
    so a collision gets ``2``, ``3``, ... appended deterministically. An
    empty ``candidate`` (nothing to derive from) is returned unchanged —
    appending a suffix to nothing would just fabricate a misleading tag.
    """
    if not candidate or candidate not in existing:
        return candidate
    n = 2
    while f"{candidate}{n}" in existing:
        n += 1
    return f"{candidate}{n}"


def _assign_plan_tag_for_plan(
    repo_root: Path,
    plan_path: Path,
    *,
    requested_tag: Optional[str] = None,
    auto_accept: bool = False,
) -> Optional[str]:
    """Confirm (or auto-derive) and persist a short jira tag for ``plan_path``.

    Shaped after :func:`_assign_epic_for_plan`, but the tag is cosmetic
    (a grouping aid, not an id-uniqueness requirement), so — unlike epic
    assignment — a not-yet-confirmed tag never blocks the export: a
    non-TTY run (or a TTY run with ``auto_accept``/``-y``) silently
    accepts the deterministic default and persists it rather than
    erroring or prompting, and a cancelled TTY prompt (Ctrl-C/EOF) just
    skips tagging for this run rather than aborting the whole export —
    the caller treats every ``None`` return as "proceed with no tag."

    Resolution order: ``requested_tag`` (``--jira-tag``, confirmed as-is
    once validated) > interactive TTY confirm/edit of the suggested
    default > auto-accept the suggested default (non-TTY, or TTY +
    ``auto_accept``). The suggested default is
    :func:`~plan_tool.jira.derive_plan_tag_acronym` over the plan's
    filename slug, deduped against every tag already recorded in the
    config via :func:`_dedupe_plan_tag`.

    Returns ``None`` when the plan path isn't under ``repo_root``
    (unassignable, printed as an error), the TTY prompt is cancelled, or
    there's nothing to derive a tag from (e.g. a punctuation-only slug).
    Raises :class:`JiraConfigError` when persisting the updated config
    fails, the existing config file is malformed, or a tag fails
    :func:`~plan_tool.jira_config.validate_plan_tag` — whether from
    ``requested_tag`` or a non-default value typed at the TTY prompt.
    """
    import builtins

    config = load_jira_config(repo_root)
    rel = plan_rel_path(plan_path, repo_root)
    if rel is None:
        error(
            f"plan {plan_path} is not under repo root {repo_root}; "
            "cannot record a jira tag for it."
        )
        return None

    default_tag = _dedupe_plan_tag(
        derive_plan_tag_acronym(plan_slug_from_path(plan_path)),
        set(config.plan_tags.values()),
    )

    if requested_tag is not None:
        tag = requested_tag.strip()
        validate_plan_tag(tag)  # raises JiraConfigError on bad shape
    elif sys.stdin.isatty() and not auto_accept:
        try:
            raw = builtins.input(
                f"plan `{rel}` has no jira tag yet — confirm short tag "
                f"[{default_tag}]: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  cancelled — no jira tag assigned.", file=sys.stderr)
            return None
        tag = raw or default_tag
        if tag:
            validate_plan_tag(tag)  # raises JiraConfigError on bad shape
    else:
        tag = default_tag

    if not tag:
        # Nothing to derive (or the operator typed nothing over a blank
        # default) — cosmetic, so skip rather than block the export.
        return None

    config.plan_tags[rel] = tag
    write_jira_config(config, default_jira_config_path(repo_root))
    print(f"tagged {rel} → [{tag}]", file=sys.stderr)
    return tag


def cmd_jira_config(args: argparse.Namespace) -> int:
    """Manage ``jira-config.json`` (state management).

    Intent: provide an interactive wizard for the small persistent
    state JIRA export needs — epic definitions and plan→epic
    assignments — so :func:`cmd_jira` doesn't have to re-ask the
    same questions on every run. ``--show`` is a print-only mode for
    inspecting the current config.

    Conceptually a state-management subcommand (like
    :func:`cmd_checkpoint`), but reached via the ``jira config``
    sub-action for historical/UX reasons rather than a top-level
    verb. If future integrations need their own config, prefer
    sibling top-level verbs (``linear config``, etc.) over deeper
    overloading.
    """
    try:
        repo_root = _resolve_cmd_repo_root(args)
    except FileNotFoundError as exc:
        error(str(exc))
        return 2

    config_path = default_jira_config_path(repo_root)

    try:
        # Lenient on the epic-key/JIRA-project distinctness rule only:
        # this command (--show and the wizard) must always be able to
        # open a config that already violates it, since it's the one
        # place that can fix it. Every other rule (bad shape, duplicate
        # keys, ...) still hard-fails here as elsewhere.
        config = load_jira_config(
            repo_root, enforce_key_distinct_from_jira_project=False
        )
    except JiraConfigError as exc:
        error(str(exc))
        return 2

    if args.show:
        _print_jira_config(config, config_path, repo_root)
        return 0

    try:
        _run_jira_config_wizard(config, config_path, repo_root, yes=args.yes)
    except (KeyboardInterrupt, EOFError):
        print("\naborted (no changes saved)", file=sys.stderr)
        return 1
    except JiraConfigError as exc:
        error(str(exc))
        return 2
    return 0


def _print_jira_config(
    config: JiraConfig, config_path: Path, repo_root: Path
) -> None:
    """Pretty-print the current config to stdout."""
    if not config_path.is_file():
        print(f"no jira config at {config_path}")
        print("run `plan-tool jira config` to bootstrap one.")
        return
    print(f"jira config: {config_path}")
    print()
    warnings = epic_key_collision_warnings(config.epics)
    if warnings:
        print("WARNING: epic key / real JIRA project key collisions —")
        print("edit the offending epic below (`jira config` → edit epic):")
        for w in warnings:
            print(f"  {w}")
        print()
    print("Epics:")
    if not config.epics:
        print("  (none)")
    else:
        for e in config.epics:
            jira_id = f" → {e.jira_epic_id}" if e.jira_epic_id else ""
            print(f"  {e.key}  {e.name}{jira_id}")
            if e.description:
                print(f"    {e.description}")
    print()
    print("Plan assignments:")
    if not config.plan_assignments:
        print("  (none)")
    else:
        for plan, key in sorted(config.plan_assignments.items()):
            print(f"  {plan} → {key}")
    print()
    print("Plan tags:")
    if not config.plan_tags:
        print("  (none)")
    else:
        for plan, tag in sorted(config.plan_tags.items()):
            print(f"  {plan} → [{tag}]")


def _run_jira_config_wizard(
    config: JiraConfig,
    config_path: Path,
    repo_root: Path,
    *,
    yes: bool = False,
) -> None:
    """Interactive wizard for editing ``config`` in place.

    Loops on a top-level action menu (add / edit / remove epic, assign /
    unassign plan, show, save & quit, quit without saving). Persists to
    ``config_path`` only when the user picks save & quit, so an
    interrupted session never leaves a half-written file.
    """
    import builtins

    print(f"jira config wizard ({config_path})")
    print("Type `?` at any prompt for help, `q` to abort without saving.")
    print()

    while True:
        print("Actions:")
        print("  1) add epic")
        print("  2) edit epic")
        print("  3) remove epic")
        print("  4) assign plan to epic")
        print("  5) unassign plan")
        print("  6) show current config")
        print("  7) save and quit")
        print("  8) quit without saving")
        raw = builtins.input("Choose [1-8]: ").strip().lower()
        if raw in ("q", "8", "quit"):
            print("aborted (no changes saved)")
            return
        if raw == "1":
            _wizard_add_epic(config)
        elif raw == "2":
            _wizard_edit_epic(config)
        elif raw == "3":
            _wizard_remove_epic(config, yes=yes)
        elif raw == "4":
            _wizard_assign_plan(config, repo_root)
        elif raw == "5":
            _wizard_unassign_plan(config)
        elif raw == "6":
            _print_jira_config(config, config_path, repo_root)
        elif raw in ("7", "save"):
            write_jira_config(config, config_path)
            print(f"wrote {config_path}")
            return
        else:
            print(f"unknown choice {raw!r}; try 1-8.")
        print()


def _wizard_add_epic(config: JiraConfig) -> None:
    import builtins

    key = builtins.input("Epic key (uppercase, e.g. AUTH): ").strip().upper()
    try:
        validate_epic_key(key)
    except JiraConfigError as exc:
        print(f"  {exc}")
        return
    if config.epic_by_key(key) is not None:
        print(f"  epic {key!r} already exists; use 'edit epic' instead.")
        return
    name = builtins.input("Epic name (human-readable): ").strip()
    if not name:
        print("  name is required; skipping.")
        return
    jira_id = (
        builtins.input("Real JIRA epic id (optional, e.g. PROJ-1234): ")
        .strip()
        or None
    )
    try:
        validate_new_epic_key_distinct_from_jira_projects(
            key, jira_id, other_epics=config.epics
        )
    except JiraConfigError as exc:
        print(f"  {exc}")
        return
    description = (
        builtins.input("Description (optional, free text): ").strip() or None
    )
    config.epics.append(
        Epic(key=key, name=name, jira_epic_id=jira_id, description=description)
    )
    print(f"  added epic {key}.")


def _wizard_edit_epic(config: JiraConfig) -> None:
    import builtins

    if not config.epics:
        print("  no epics defined yet.")
        return
    key = (
        builtins.input(f"Key to edit ({', '.join(e.key for e in config.epics)}): ")
        .strip()
        .upper()
    )
    existing = config.epic_by_key(key)
    if existing is None:
        print(f"  no epic with key {key!r}.")
        return
    name = builtins.input(f"Name [{existing.name}]: ").strip() or existing.name
    jira_id_raw = builtins.input(
        f"Real JIRA epic id [{existing.jira_epic_id or '<none>'}] "
        "(- to clear): "
    ).strip()
    if jira_id_raw == "-":
        jira_id = None
    elif jira_id_raw == "":
        jira_id = existing.jira_epic_id
    else:
        jira_id = jira_id_raw
    try:
        validate_new_epic_key_distinct_from_jira_projects(
            key,
            jira_id,
            other_epics=[e for e in config.epics if e.key != key],
        )
    except JiraConfigError as exc:
        print(f"  {exc}")
        return
    desc_raw = builtins.input(
        f"Description [{existing.description or '<none>'}] (- to clear): "
    ).strip()
    if desc_raw == "-":
        description = None
    elif desc_raw == "":
        description = existing.description
    else:
        description = desc_raw
    config.epics = [
        Epic(
            key=key,
            name=name,
            jira_epic_id=jira_id,
            description=description,
        )
        if e.key == key
        else e
        for e in config.epics
    ]
    print(f"  updated epic {key}.")


def _wizard_remove_epic(config: JiraConfig, *, yes: bool = False) -> None:
    import builtins

    if not config.epics:
        print("  no epics defined yet.")
        return
    key = (
        builtins.input(f"Key to remove ({', '.join(e.key for e in config.epics)}): ")
        .strip()
        .upper()
    )
    if config.epic_by_key(key) is None:
        print(f"  no epic with key {key!r}.")
        return
    assigned = [p for p, k in config.plan_assignments.items() if k == key]
    if assigned:
        if yes:
            print(
                f"  {len(assigned)} plan(s) assigned to {key} will be "
                "unassigned (--yes)."
            )
        else:
            confirm = (
                builtins.input(
                    f"  {len(assigned)} plan(s) are assigned to {key} and will be "
                    "unassigned. Continue? [y/N]: "
                )
                .strip()
                .lower()
            )
            if confirm not in ("y", "yes"):
                print("  cancelled.")
                return
    config.epics = [e for e in config.epics if e.key != key]
    config.plan_assignments = {
        p: k for p, k in config.plan_assignments.items() if k != key
    }
    print(f"  removed epic {key}.")


def _wizard_assign_plan(config: JiraConfig, repo_root: Path) -> None:
    import builtins

    if not config.epics:
        print("  add an epic first.")
        return
    plan_input = builtins.input(
        "Plan name (matches `plan-tool list`, or repo-relative path): "
    ).strip()
    if not plan_input:
        print("  no plan specified.")
        return
    rel = _wizard_resolve_plan_rel(plan_input, repo_root)
    if rel is None:
        return
    key = (
        builtins.input(f"Epic key ({', '.join(e.key for e in config.epics)}): ")
        .strip()
        .upper()
    )
    if config.epic_by_key(key) is None:
        print(f"  no epic with key {key!r}.")
        return
    config.plan_assignments[rel] = key
    print(f"  assigned {rel} → {key}.")


def _wizard_unassign_plan(config: JiraConfig) -> None:
    import builtins

    if not config.plan_assignments:
        print("  no plan assignments to remove.")
        return
    print("  currently assigned:")
    for p, k in sorted(config.plan_assignments.items()):
        print(f"    {p} → {k}")
    rel = builtins.input("Plan path to unassign (repo-relative): ").strip()
    if rel not in config.plan_assignments:
        print(f"  no assignment for {rel!r}.")
        return
    del config.plan_assignments[rel]
    print(f"  unassigned {rel}.")


def _wizard_resolve_plan_rel(
    plan_input: str, repo_root: Path
) -> Optional[str]:
    """Resolve a user-supplied plan reference to a repo-relative posix path.

    Accepts either a slug (matches the manifest's registered plans via
    :func:`resolve_plan_for_context`) or a direct repo-relative path
    string. Returns ``None`` and prints a diagnostic when neither
    resolves — so the wizard can loop without exiting.
    """
    # Try the manifest first — slug, with/without priority prefix.
    try:
        ctx = build_plan_tool_context(repo_root_override=repo_root)
        path = resolve_plan_for_context(ctx, plan_input)
    except (FileNotFoundError, ManifestError):
        path = None
    if path is None:
        candidate = (repo_root / plan_input).resolve()
        if candidate.is_file():
            path = candidate
    if path is None:
        print(
            f"  could not resolve {plan_input!r} as a registered plan or "
            "as a path under the repo root."
        )
        return None
    rel = plan_rel_path(path, repo_root)
    if rel is None:
        print(f"  plan {path} is not inside repo root {repo_root}.")
        return None
    return rel


def register(subparsers) -> dict[str, Handler]:
    """Add the ``jira`` subparser and return its command→handler map.

    Returns a single ``{"jira": cmd_jira}`` entry — ``jira config`` is
    dispatched *inside* ``cmd_jira`` via ``args.name == "config"``, not a
    second registered subparser.

    ``-y/--yes`` comes from :func:`plan_tool.cli.parser.make_yes_parent`;
    argparse ``parents=`` copies actions by reference, so an identical
    parent yields byte-identical per-subcommand help.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    p_jira = sub.add_parser(
        "jira",
        help=(
            "emit copy-paste-ready JIRA story titles and descriptions; "
            "`jira config` opens the configuration wizard"
        ),
        parents=[yes_parent],
    )
    p_jira.add_argument(
        "name",
        nargs="?",
        default=None,
        help=(
            "plan name to export, or the literal `config` to manage "
            "jira-config.json (epics + plan assignments)"
        ),
    )
    p_jira.add_argument(
        "--show",
        action="store_true",
        help=(
            "only meaningful with `jira config` — print the current config "
            "and exit without opening the wizard"
        ),
    )
    p_jira.add_argument(
        "--lint",
        action="store_true",
        help=(
            "lint an existing jira-stories artifact without invoking claude "
            "or assigning an epic; pass a plan name or --input <path>"
        ),
    )
    p_jira.add_argument(
        "--input",
        default=None,
        help=(
            "with --lint, check this existing jira-stories markdown/json file "
            "instead of resolving a plan's conventional output"
        ),
    )
    p_jira.add_argument(
        "--max-hours",
        type=int,
        default=8,
        dest="max_hours",
        help=(
            "advisory per-story size target in hours (default: 8). A soft "
            "target, not a hard cap — stories are sized to be atomic PRs "
            "(independently mergeable without breaking the build), so a "
            "large-but-atomic story is kept whole rather than fragmented."
        ),
    )
    p_jira.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="output format (default: markdown, paste-ready into JIRA)",
    )
    p_jira.add_argument(
        "--output",
        default=None,
        help=(
            "explicit output file path. Default: "
            "<plan_dir>/plan-details/<plan_slug>/jira-stories.{md,json}"
        ),
    )
    p_jira.add_argument(
        "--no-write",
        action="store_true",
        dest="no_write",
        help=(
            "invoke the story generator but do not write either artifact; "
            "print the story and developer handoff instead"
        ),
    )
    p_jira.add_argument(
        "--stdout",
        action="store_true",
        help=(
            "also print the formatted output to stdout (default prints only "
            "a short summary line when writing succeeds)"
        ),
    )
    p_jira.add_argument(
        "--epic",
        default=None,
        help=(
            "epic key to assign this plan to when it isn't yet listed in "
            "`plan_assignments`. Useful for scripts: skips the interactive "
            "prompt that the TTY flow would otherwise show. Must match a "
            "defined epic key in `jira-config.json`."
        ),
    )
    p_jira.add_argument(
        "--jira-tag",
        default=None,
        dest="jira_tag",
        help=(
            "short grouping tag to confirm for this plan when it isn't yet "
            "listed in `plan_tags` (rendered into every story title so "
            "tickets from the same plan stay grouped). Useful for scripts: "
            "skips the interactive confirm prompt / -y auto-accept that the "
            "TTY flow would otherwise show. 1-24 chars, letters/digits/-/_ "
            "only."
        ),
    )
    p_jira.add_argument(
        "--handoff-output",
        default=None,
        dest="handoff_output",
        help=(
            "explicit developer-handoff output path. Default: <plan_dir>/jira-handoffs/"
            "<plan_slug>/<normalized-story-stem>.developer-handoff.md"
        ),
    )
    p_jira.add_argument(
        "--adopt-existing",
        action="store_true",
        help=(
            "allow this export to replace the selected readable legacy story "
            "source after validating every carried Jira key and story state; "
            "never adopts a handoff"
        ),
    )

    return {"jira": cmd_jira}
