"""Emit JIRA-ready story titles and descriptions for a plan.

`plan-tool jira <plan-name>` runs a single claude call over the *whole*
plan and asks for a consolidated set of JIRA stories, each an **atomic
PR** — self-contained work that merges without breaking the build.
``--max-hours`` (default 8) is an advisory size target, not a hard cap.
Each story declares the plan step ids it covers via ``steps: [int, ...]``.
See JIRA_FORMAT.md for the sizing contract.

Output is paste-ready markdown by default; ``--format json`` returns a
structured array for tooling. Output is also written to disk alongside
the plan at ``<plan_dir>/plan-details/<plan_slug>/jira-stories.{md,json}``
so it becomes a checked-in artifact next to the per-step detail files.

Run-grade ``Step.detail`` grounds both artifacts in one paired export.

Claude does the natural-language work — synthesizing titles, writing
descriptions and acceptance criteria, and deciding how to chunk the plan
into stories. The deterministic pieces (prompt rendering, JSON
extraction, validation, markdown / JSON formatting, output paths) live
here.

Story ids come from claude as sequential ``S<N>`` (validated here), so
``depends_on`` references resolve within the same response.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from string import Template
from typing import AbstractSet, Callable, Optional

from plan_tool.backend import spawn_cwd_from_repo_root
from plan_tool.detail_artifacts import (
    DetailFormatError,
    derive_detail_path,
    require_supported_detail_format_version,
)
from plan_tool.jira_config import Epic
from plan_tool.jira_handoff import (
    DETAIL_STATE_MISSING as _HANDOFF_DETAIL_STATE_MISSING,
    DETAIL_STATE_PRESENT as _HANDOFF_DETAIL_STATE_PRESENT,
    FILE_EXCERPT_STATE_EXCERPT as _HANDOFF_FILE_EXCERPT_STATE_EXCERPT,
    FILE_EXCERPT_STATE_MISSING as _HANDOFF_FILE_EXCERPT_STATE_MISSING,
    FILE_EXCERPT_STATE_UNREADABLE as _HANDOFF_FILE_EXCERPT_STATE_UNREADABLE,
    CarriedStoryRecordRenderInput,
    CommittedStepRenderInput,
    CompanionRenderSettings as HandoffCompanionRenderSettings,
    CompanionProvenance,
    DetailRenderInput,
    FileExcerptRenderInput,
    GeneratedSourcePairIdentity as HandoffPairIdentity,
    HandoffRenderError,
    HandoffRenderInput,
    ParkedStepRenderInput,
    build_companion_provenance,
    read_json_provenance,
    read_markdown_provenance,
    read_markdown_story_provenance,
    render_handoff,
    render_handoff_body,
    strip_markdown_provenance,
    write_json_provenance,
    write_markdown_provenance,
)
from plan_tool.parser import parse_plan, parse_plan_text, split_plan_document
from plan_tool.prompt_excerpt import (
    ExcerptResult,
    build_prompt_excerpt,
    clip_text_to_byte_budget,
)
from plan_tool.renderer import prompts_dir
from plan_tool.scope_fence import _fenced_code_spans
from plan_tool.review import (
    _derive_file_path_symbols,
    _derive_symbols,
    _merge_candidate_symbols,
)
from plan_tool.schema import Plan, Step, StepScope, StepStatus
from plan_tool.shell import claude_invoke
from plan_tool.style import change_type_tag, warn


JiraInvoker = Callable[[str], str]  # returns captured stdout

_MAX_PROMPT_FILE_BYTES = 4096
_VALID_FORMATS = ("markdown", "json")

# Story-id format is always ``<EPIC_KEY>-S`` + digits (``AUTH-S1``,
# ``PAY-S12``). Plans must be assigned to an epic in
# ``jira-config.json``; the legacy bare ``S<N>`` shape is no longer
# accepted so two plans can't silently produce colliding ids.


def build_story_id_re(epic: Epic) -> re.Pattern[str]:
    """Build the strict ``^<EPIC_KEY>-S\\d+$`` regex for ``epic``.

    The exact prefix is enforced — partial matches like ``AUTHS1`` or
    bare ``S1`` get rejected so the response is internally consistent.
    """
    return re.compile(rf"^{re.escape(epic.key)}-S\d+$")


def story_id_prefix(epic: Epic) -> str:
    """The leading token of every story id under ``epic`` (``"<KEY>-S"``)."""
    return f"{epic.key}-S"


_STORY_ID_NUMBER_RE = re.compile(r"-S(\d+)\b")

# Which side of the JIRA handoff a story is on. Once a ticket exists,
# JIRA is canonical for everything about it, so this vocabulary carries
# no JIRA workflow states (no in-progress/in-review/done) — mirroring
# them here would go stale the moment someone moves the ticket.
# ``dropped`` is a fact about the *plan*, not the ticket: the plan no
# longer covers the story. See JIRA_FORMAT.md's "Status" section.
_EXPORT_STATE_DRAFT = "draft"
_EXPORT_STATE_CREATED = "created"
_EXPORT_STATE_DROPPED = "dropped"
_VALID_EXPORT_STATES = (
    _EXPORT_STATE_DRAFT,
    _EXPORT_STATE_CREATED,
    _EXPORT_STATE_DROPPED,
)

# Legacy ``status: todo|done`` read compat. ``done`` meant the work
# shipped and was accepted — so the ticket exists in JIRA, hence
# ``created``. The old code *also* wrote ``done`` when a story left the
# plan, so some migrated rows land on ``created`` that should be
# ``dropped``; JIRA_FORMAT.md tells operators how to spot them.
_LEGACY_STATUS_MAP = {
    "todo": _EXPORT_STATE_DRAFT,
    "done": _EXPORT_STATE_CREATED,
}


def _normalize_export_state(raw: object) -> str:
    """Map any stored/legacy state token onto the current vocabulary."""
    if isinstance(raw, str):
        if raw in _VALID_EXPORT_STATES:
            return raw
        mapped = _LEGACY_STATUS_MAP.get(raw)
        if mapped is not None:
            return mapped
    return _EXPORT_STATE_DRAFT


def _resolve_export_state(raw: object, jira_issue_key: str) -> str:
    """Normalize a state, promoting ``draft`` to ``created`` on a key.

    Recording the JIRA key directly is the whole handoff gesture — the
    operator writes only the key, and the next run derives the state from
    it, so the two can never disagree. A ``dropped`` story stays dropped.
    """
    state = _normalize_export_state(raw)
    if state == _EXPORT_STATE_DRAFT and jira_issue_key:
        return _EXPORT_STATE_CREATED
    return state

# Layer vocabulary. ``layer`` records where a story lands in the stack;
# ``_LAYER_UNSPECIFIED`` is the default sentinel meaning "not provided"
# (not an assignable choice — the parser validates against _VALID_LAYERS).
_LAYER_FRONTEND = "frontend"
_LAYER_BACKEND = "backend"
_LAYER_FULL_STACK = "full_stack"
_LAYER_INFRA = "infra"
_LAYER_UNSPECIFIED = "unspecified"
_VALID_LAYERS = (_LAYER_FRONTEND, _LAYER_BACKEND, _LAYER_FULL_STACK, _LAYER_INFRA)

# layer → short bracket tag for the story title. ``unspecified`` and any
# unknown value map to "" (no tag). Bare bracket, no surrounding spaces —
# the caller composes ``[<id>] [BE] <title>``.
_LAYER_TAGS = {
    _LAYER_FRONTEND: "[FE]",
    _LAYER_BACKEND: "[BE]",
    _LAYER_FULL_STACK: "[FE+BE]",
    _LAYER_INFRA: "[INFRA]",
}

# Width of the ``=`` rule separating story blocks in the markdown output.
_STORY_SEPARATOR = "=" * 64

# Matches the trailing ``[state: <s>]`` tag on a markdown block header
# line — or the legacy ``[status: …]`` it replaced. Used to read an
# existing ticket's state back and to rewrite it in place without
# disturbing the rest of the verbatim block.
_MD_STATE_TAG_RE = re.compile(r"\[(?:state|status): (?:draft|created|dropped|todo|done)\]")

# The hand-written JIRA key tag, e.g. ``[jira: PROJ-4412]``. Deliberately
# permissive — an operator types this, so anything but a bracket or a
# newline is accepted and stripped rather than silently dropped.
_MD_JIRA_KEY_TAG_RE = re.compile(r"\[jira: (?P<key>[^\]\n]+)\]")


# Acceptance-criteria phrasing patterns that almost always produce a
# brittle or unverifiable check. Flagged by :func:`lint_acceptance_criteria`,
# which is a **hard gate**: ``_raise_for_acceptance_criteria_lint`` blocks the
# export write on any finding, so the AC bullets must be repaired before the
# export is produced. The prompt documents the same anti-patterns; these
# patterns catch the most common shapes the prompt didn't dissuade.
#
# ``_VAGUE_AC_PATTERNS`` matches phrasing the reviewer can't actually
# run ("code is clean", "well-tested", lone "tests pass" / "no
# regressions" bullets). Anchored bare-bullet patterns (``^…$``) only
# fire when the *entire* bullet is the vague phrase, so a richer
# bullet like "a test fails if X drops Y" doesn't trip them.
_VAGUE_AC_PATTERNS = [
    re.compile(r"\bcode is (clean|good|correct)\b", re.IGNORECASE),
    re.compile(r"\bwell[- ]tested\b", re.IGNORECASE),
    re.compile(r"\btests are (good|clean|comprehensive|thorough)\b", re.IGNORECASE),
    re.compile(r"\b(it )?looks (good|correct|right|fine)\b", re.IGNORECASE),
    re.compile(r"\bworks (as expected|correctly|properly|fine)\b", re.IGNORECASE),
    re.compile(r"^(all )?tests?\s+pass\.?$", re.IGNORECASE),
    re.compile(r"^no regressions?\.?$", re.IGNORECASE),
    re.compile(r"^no errors?\.?$", re.IGNORECASE),
]

# ``_INTERNAL_HANDLE_PATTERNS`` matches AC bullets that pin to
# refactor-fragile internals: a specific test function name (``test_x
# passes`` / ``test_x()``), a Mocha/Jest ``it('…')`` block, a
# ``should_*`` test name, or a ``file.ext:NN`` line-number reference.
# Each is a contract handle the implementation can rename without
# changing behavior — the AC then "fails" while the code is fine.
_INTERNAL_HANDLE_PATTERNS = [
    re.compile(r"\btest_[A-Za-z][A-Za-z0-9_]*\s*(?:\(|passes?\b)", re.IGNORECASE),
    re.compile(r"\bit\(['\"]"),
    re.compile(r"\bshould_[A-Za-z][A-Za-z0-9_]*\b", re.IGNORECASE),
    re.compile(r"\b[\w./-]+\.[A-Za-z0-9]{1,5}:\d+\b"),
    re.compile(r"\blines?\s+\d+(?:\s*[-–]\s*\d+)?\b", re.IGNORECASE),
]

_GREP_OR_CALL_COUNT_PATTERNS = [
    re.compile(
        r"\b(?:git\s+)?grep\b.*\b(?:returns?|finds?|has|shows)\b.*"
        r"\b(?:exactly|only|zero|one|two|three|\d+|no matches?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:zero|one|two|three|\d+)\s+call[- ]sites?\b", re.IGNORECASE),
    re.compile(r"\bcall[- ]site\s+count\b", re.IGNORECASE),
    re.compile(r"\boccurs?\s+(?:exactly\s+)?\d+\s+times?\b", re.IGNORECASE),
    re.compile(r"\bzero\s+occurrences?\b", re.IGNORECASE),
]

_IMPORT_LIST_PATTERNS = [
    re.compile(r"\bfrom\s+[\w.]+\s+import\s+[\w*,\s]+", re.IGNORECASE),
    re.compile(r"\bimports?\s+[\w.]+(?:\s*,\s*[\w.]+)+", re.IGNORECASE),
    re.compile(r"\bimport\s+list\b", re.IGNORECASE),
]

_FILE_SIZE_CAP_PATTERNS = [
    re.compile(
        r"\b(?:under|below|fewer than|less than|<=|<|no more than|at most)\s*"
        r"\d+\s*(?:lines?|loc|kb|kib|bytes?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bfile[- ]size\s+cap\b", re.IGNORECASE),
]

_INFRA_LITERAL_PATTERNS = [
    re.compile(r"\barn:aws:[^\s`]+", re.IGNORECASE),
    re.compile(r"\bAWS::[A-Za-z0-9:]+"),
    re.compile(
        r"\b(?:lambda|s3|dynamodb|iam|eventbridge|cloudformation|api gateway|"
        r"cloudwatch|cognito|sns|sqs)\b.*\b(?:function|bucket|table|role|"
        r"policy|rule|stack|resource|queue|topic|user pool)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:cdk|terraform|cloudformation)\s+(?:stack|resource)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:amplify/backend|cdk\.json|buildspec\.ya?ml)\b", re.IGNORECASE),
]

_INFRA_CONTRACT_PATTERNS = [
    re.compile(
        r"\b(?:infra|infrastructure|deployment|deploy|cdk|terraform|cloudformation|"
        r"iam|lambda|s3|dynamodb|eventbridge|cloudwatch|cognito|sns|sqs|"
        r"api gateway)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:amplify/backend|buildspec\.ya?ml|\.tf\b|cdk\.json)\b",
        re.IGNORECASE,
    ),
]

_VERIFICATION_EVIDENCE_ONLY_PATTERNS = [
    re.compile(
        r"\b(?:evidence|screenshot|screen recording|recording|verification notes?|"
        r"artifact|report)\b.*\b(?:recorded|attached|captured|uploaded|saved)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmanual verification\b.*\b(?:complete|completed|recorded)\b",
        re.IGNORECASE,
    ),
]

# Minimum non-space characters at least one ``frontend_test_recommendation``
# bullet must carry to count as substantive. Below this the recommendation
# is a stub the author can't act on (``["test it"]``). Advisory floor —
# tune from the tests that pin the observable behavior, not this number.
_TEST_REC_MIN_SUBSTANTIVE_CHARS = 12

# Soft decomposition floor for a story's ``estimate_hours`` (half a working
# day). A story below this is *skeptically* flagged (advisory only, never a
# gate) — over-decomposition is discouraged, but atomicity still wins, so a
# genuinely-atomic sub-floor story that can't merge upward is legitimate.
# Tune from the tests that pin the behavior, not this number. See JIRA_FORMAT.md.
_STORY_SIZE_SOFT_FLOOR_HOURS = 4

# Documentation file suffixes — used to decide which missing-file
# warnings are worth surfacing. Missing source files are common and
# expected (claude regularly proposes creating them); missing doc files
# almost always indicate a typo or a stale plan-detail reference.
_DOC_FILE_SUFFIXES = (".md", ".mdx", ".rst", ".txt", ".adoc")


def _is_documentation_path(path: str) -> bool:
    """True if ``path`` looks like a documentation artifact.

    A path counts as documentation when it lives under a ``docs/``
    directory (anywhere in the tree) or carries a documentation
    suffix like ``.md``. Tightening this further would require
    introspecting plan structure; the current heuristic mirrors the
    convention already used across the repo's implementation plans.
    """
    p = path.lower()
    if p.endswith(_DOC_FILE_SUFFIXES):
        return True
    parts = p.replace("\\", "/").split("/")
    return "docs" in parts


def _normalize_story_references(
    stories: list["Story"], epic: Epic
) -> list["Story"]:
    """Post-process stories so cross-references and titles are JIRA-ready.

    Two cleanups, applied to ``title``, ``plain_summary``,
    ``description``, and each ``acceptance_criteria`` bullet:

    1. **Strip a leading ``[<EPIC>-S<N>] `` prefix from the title.**
       The renderer adds the prefix deterministically, so if claude
       included one (despite the prompt) we drop it to avoid
       double-prefixing.
    2. **Expand bare ``S<N>`` references to ``<EPIC>-S<N>``** when
       ``N`` matches a story emitted in this same response. Limiting
       the rewrite to known story numbers avoids false positives like
       ``S3`` (the AWS service) or ``S4`` (gear). References already
       prefixed (``<EPIC>-S<N>``) are left alone via a negative
       lookbehind on ``-`` and ``\\w``.

    ``files`` are intentionally left untouched — story-reference
    rewriting on file paths could corrupt legitimate names like
    ``S3-uploader.ts``.
    """
    if not stories:
        return stories
    valid_numbers: set[str] = set()
    for s in stories:
        m = _STORY_ID_NUMBER_RE.search(s.id)
        if m:
            valid_numbers.add(m.group(1))
    if not valid_numbers:
        return stories
    # Longest alternatives first so ``S10`` wins over ``S1`` when both
    # are present.
    alts = "|".join(sorted(valid_numbers, key=len, reverse=True))
    bare_ref_re = re.compile(rf"(?<![\w-])S({alts})\b")
    prefix = story_id_prefix(epic)
    title_prefix_re = re.compile(
        rf"^\s*\[{re.escape(epic.key)}-S\d+\]\s+"
    )

    def rewrite(text: str) -> str:
        return bare_ref_re.sub(lambda m: f"{prefix}{m.group(1)}", text)

    normalized: list[Story] = []
    for s in stories:
        new_title = title_prefix_re.sub("", s.title)
        new_title = rewrite(new_title)
        normalized.append(
            Story(
                id=s.id,
                title=new_title,
                description=rewrite(s.description),
                plain_summary=rewrite(s.plain_summary),
                acceptance_criteria=[rewrite(a) for a in s.acceptance_criteria],
                files=list(s.files),
                steps=list(s.steps),
                depends_on=list(s.depends_on),
                estimate_hours=s.estimate_hours,
                export_state=s.export_state,
                jira_issue_key=s.jira_issue_key,
                layer=s.layer,
                ui_impact=s.ui_impact,
                frontend_test_recommendation=list(s.frontend_test_recommendation),
            )
        )
    return normalized


def lint_acceptance_criteria(stories: list[Story]) -> list[str]:
    """Return human-readable findings for likely-brittle / weak AC.

    These findings are a hard gate for a paired Jira export before it writes,
    and are emitted by ``jira --lint`` for existing artifacts. Catches the
    patterns the prompt explicitly warns against:

    - Stories with **no** acceptance criteria at all.
    - Bullets matching vague-quality phrasing (``code is clean``,
      ``well-tested``, lone ``tests pass`` / ``no regressions`` lines).
    - Bullets matching brittle internal handles: a specific test
      function name (``test_foo passes``), a Mocha/Jest ``it('…')``
      block, a ``should_*`` test name, or a ``file:line`` reference.

    Each story produces at most one warning per failure category to
    avoid drowning the user when many bullets share the same problem.
    The returned strings are ``style.warn()`` bodies (no ``warning:``
    prefix) — the caller routes them through ``warn()`` for display when it
    wants one finding per line.
    """
    warnings: list[str] = []
    for story in stories:
        if not story.acceptance_criteria:
            warnings.append(
                f"story {story.id} has no acceptance criteria — "
                "the reviewer has nothing to check before merging or "
                "pasting into JIRA"
            )
            continue
        flagged_vague: Optional[str] = None
        flagged_handle: Optional[str] = None
        flagged_grep_or_call_count: Optional[str] = None
        flagged_import_list: Optional[str] = None
        flagged_file_size_cap: Optional[str] = None
        flagged_infra_literal: Optional[str] = None
        flagged_verification_evidence: Optional[str] = None
        story_is_infra_contract = _story_is_infra_contract(story)
        for ac in story.acceptance_criteria:
            stripped = ac.strip()
            if flagged_vague is None and any(
                p.search(stripped) for p in _VAGUE_AC_PATTERNS
            ):
                flagged_vague = stripped
            if flagged_handle is None and any(
                p.search(stripped) for p in _INTERNAL_HANDLE_PATTERNS
            ):
                flagged_handle = stripped
            if flagged_grep_or_call_count is None and any(
                p.search(stripped) for p in _GREP_OR_CALL_COUNT_PATTERNS
            ):
                flagged_grep_or_call_count = stripped
            if flagged_import_list is None and any(
                p.search(stripped) for p in _IMPORT_LIST_PATTERNS
            ):
                flagged_import_list = stripped
            if flagged_file_size_cap is None and any(
                p.search(stripped) for p in _FILE_SIZE_CAP_PATTERNS
            ):
                flagged_file_size_cap = stripped
            if (
                flagged_infra_literal is None
                and not story_is_infra_contract
                and any(p.search(stripped) for p in _INFRA_LITERAL_PATTERNS)
            ):
                flagged_infra_literal = stripped
            if flagged_verification_evidence is None and any(
                p.search(stripped) for p in _VERIFICATION_EVIDENCE_ONLY_PATTERNS
            ):
                flagged_verification_evidence = stripped
            if all(
                x is not None
                for x in (
                    flagged_vague,
                    flagged_handle,
                    flagged_grep_or_call_count,
                    flagged_import_list,
                    flagged_file_size_cap,
                    flagged_verification_evidence,
                )
            ) and (story_is_infra_contract or flagged_infra_literal is not None):
                break
        if flagged_vague is not None:
            warnings.append(
                f"story {story.id} acceptance criterion uses "
                f"vague phrasing the reviewer can't run: {flagged_vague!r} "
                "— rephrase as an observable check (boundary behavior, "
                "data invariant, or the specific regression a test pins)"
            )
        if flagged_handle is not None:
            warnings.append(
                f"story {story.id} acceptance criterion pins to "
                f"a refactor-fragile handle (specific test name or "
                f"file:line): {flagged_handle!r} — rephrase to assert the "
                "behavior the test guards, not the test's identifier"
            )
        if flagged_grep_or_call_count is not None:
            warnings.append(
                f"story {story.id} acceptance criterion uses a brittle "
                f"grep/call-count gate: {flagged_grep_or_call_count!r} — "
                "state the observable outcome or the regression the check "
                "guards instead of an exact count"
            )
        if flagged_import_list is not None:
            warnings.append(
                f"story {story.id} acceptance criterion pins an import list: "
                f"{flagged_import_list!r} — assert the public behavior or "
                "module boundary instead of exact imports"
            )
        if flagged_file_size_cap is not None:
            warnings.append(
                f"story {story.id} acceptance criterion uses a file-size cap: "
                f"{flagged_file_size_cap!r} — replace line/byte ceilings with "
                "the maintainability or behavior signal they approximate"
            )
        if flagged_infra_literal is not None:
            warnings.append(
                f"story {story.id} acceptance criterion contains an infra "
                f"literal outside an infra contract: {flagged_infra_literal!r} "
                "— keep resource names and deployment path literals in the "
                "description unless the story's contract is infrastructure"
            )
        if flagged_verification_evidence is not None:
            warnings.append(
                f"story {story.id} acceptance criterion records verification "
                f"evidence without asserting behavior: "
                f"{flagged_verification_evidence!r} — separate evidence "
                "capture from the done condition being verified"
            )
    return warnings


def lint_layer_metadata(stories: list[Story]) -> list[str]:
    """Advisory soft-lint findings for missing layer-derived metadata.

    Deterministic, Claude-free; advisory only (kept out of the export hard
    gate). See JIRA_FORMAT.md's lint section for the two checks and severity.
    """
    warnings: list[str] = []
    for story in stories:
        if (
            story.layer in (_LAYER_BACKEND, _LAYER_FULL_STACK)
            and story.ui_impact.strip() == ""
        ):
            warnings.append(
                f"story {story.id} is a {story.layer} story with no "
                "UI-impact note — record what the change means for the UI "
                "(answer `none` when the change is UI-invisible)"
            )
        if is_frontend_impacting(story) and not _test_rec_is_substantive(
            story.frontend_test_recommendation
        ):
            warnings.append(
                f"story {story.id} is frontend-impacting but its test "
                "recommendation is missing or too thin to act on — name the "
                "flow/component to cover and a test level"
            )
    return warnings


def lint_story_size(stories: list[Story]) -> list[str]:
    """Advisory soft-lint findings for stories below the decomposition floor.

    Deterministic, Claude-free; advisory only (never gates the export). One
    finding per story whose ``estimate_hours`` is a **positive** value below
    ``_STORY_SIZE_SOFT_FLOOR_HOURS`` — a skeptical nudge to consolidate
    over-decomposed work, subordinate to atomicity (a genuinely-atomic story
    that can't merge upward is a legitimate exception). A non-positive estimate
    is the "not provided" sentinel (``read_stories_for_lint`` coerces a
    missing/invalid ``estimate_hours`` to ``0``), not a real sub-floor ticket,
    so it is left alone here — flagging it would give misleading "0h,
    consolidate it" advice. See JIRA_FORMAT.md.
    """
    warnings: list[str] = []
    for story in stories:
        if 0 < story.estimate_hours < _STORY_SIZE_SOFT_FLOOR_HOURS:
            warnings.append(
                f"story {story.id} is estimated at {story.estimate_hours}h, "
                f"below the {_STORY_SIZE_SOFT_FLOOR_HOURS}h soft decomposition "
                "floor — consolidate it with an adjacent story unless it's "
                "genuinely atomic and can't be merged upward without breaking "
                "the build"
            )
    return warnings


def _test_rec_is_substantive(recommendation: list[str]) -> bool:
    """Whether ``recommendation`` carries at least one actionable bullet.

    A bullet counts once it clears ``_TEST_REC_MIN_SUBSTANTIVE_CHARS``
    non-space characters; an empty list, all-blank bullets, or a one-word
    stub like ``["test it"]`` all fail.
    """
    return any(
        len("".join(bullet.split())) >= _TEST_REC_MIN_SUBSTANTIVE_CHARS
        for bullet in recommendation
    )


def partition_lint_findings(
    stories: list[Story],
) -> tuple[list[str], list[str]]:
    """Split lint findings into ``(blocking, advisory)`` for report surfaces.

    Blocking = acceptance-criteria findings (these also gate the export write
    via :func:`_raise_for_acceptance_criteria_lint`); advisory = layer-metadata
    and story-size warnings (never block a write). The single source of the
    severity split so ``jira --lint`` and the export gate cannot drift — a new
    lint class picks a side here, not in the CLI handler.
    """
    advisory = lint_layer_metadata(stories) + lint_story_size(stories)
    return lint_acceptance_criteria(stories), advisory


def _raise_for_acceptance_criteria_lint(stories: list[Story]) -> None:
    """Raise before writing JIRA output when deterministic AC lint fails."""
    warnings = lint_acceptance_criteria(stories)
    if not warnings:
        return
    noun = "finding" if len(warnings) == 1 else "findings"
    bullets = "\n".join(f"- {body}" for body in warnings)
    raise JiraError(
        f"jira acceptance-criteria lint found {len(warnings)} {noun}; "
        f"fix the generated stories before writing:\n{bullets}"
    )


def _story_is_infra_contract(story: Story) -> bool:
    """Heuristic guard for infra literal AC warnings.

    Exact AWS/CDK names are acceptable when the story itself is an
    infrastructure contract. Otherwise they belong in description prose,
    where a rename doesn't make the pass/fail gate stale.
    """
    fields = [story.title, story.description, *story.files]
    return any(p.search(text) for text in fields for p in _INFRA_CONTRACT_PATTERNS)


class JiraError(Exception):
    """Raised when the jira export pipeline can't produce a valid result.

    Examples: claude returned unparseable output, an unknown format was
    requested, ``steps`` references a plan step that doesn't exist,
    ``depends_on`` references a story id that wasn't in the response, or
    a plan step is missing from every story's ``steps`` field.
    """


def _reject_unmatched_handoff_fence(*, plan_path: Path, body_text: str) -> None:
    """Keep paired publication from committing a truncated handoff."""
    if _fenced_code_spans(body_text).unmatched_opening is not None:
        raise JiraError(
            f"{plan_path}: unmatched opening code fence; add a matching "
            "closing fence before publishing the Jira export."
        )


@dataclass(frozen=True)
class Story:
    """One JIRA story produced for a plan.

    ``id`` is ``<EPIC_KEY>-S<N>`` (e.g. ``AUTH-S1``), claude-assigned and
    validated against ``build_story_id_re`` here — the bare ``S<N>`` shape
    is no longer accepted (see the module-level note on story ids).
    ``steps`` lists the plan step ids this story implements — multiple
    ids when the story consolidates steps, the same id appearing on
    multiple stories when a step was split.

    Every field is tool-written except ``jira_issue_key``, which an
    operator fills in after creating the ticket; it sorts last everywhere
    to keep that boundary visible.
    """

    id: str
    title: str
    description: str
    # Jargon-free, PM-facing one-liner rendered as the ``## In plain
    # English`` preamble at the top of each ticket. Additive: defaults
    # empty on legacy exports that predate it. See JIRA_FORMAT.md.
    plain_summary: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    steps: list[int] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    estimate_hours: int = 0
    export_state: str = _EXPORT_STATE_DRAFT
    layer: str = _LAYER_UNSPECIFIED
    ui_impact: str = ""
    frontend_test_recommendation: list[str] = field(default_factory=list)
    # Deliberately LAST, here and in every rendered surface: it is the one
    # field a person writes rather than the tool. Keep new tool-written
    # fields above it. See JIRA_FORMAT.md's story-schema table.
    jira_issue_key: str = ""


def layer_tag(layer: str) -> str:
    """Return the short bracket tag for ``layer`` (e.g. ``"[BE]"``).

    Empty string for ``unspecified`` and any unknown/empty value — an
    unknown layer never crashes or emits a stray tag. Bare bracket, no
    surrounding spaces; the caller owns placement and spacing.
    """
    return _LAYER_TAGS.get(layer, "")


def plan_tag_bracket(plan_tag: str) -> str:
    """Return the short bracket tag for ``plan_tag`` (e.g. ``"[DCL]"``).

    Empty string for a blank ``plan_tag``, mirroring :func:`layer_tag`. Bare
    bracket, no surrounding spaces. See JIRA_FORMAT.md's "Plan tag" section.
    """
    return f"[{plan_tag}]" if plan_tag else ""


_PLAN_TAG_ACRONYM_WORD_RE = re.compile(r"[A-Za-z0-9]+")
# Ceiling on a derived tag's length so a many-word slug (or the single-word
# fallback) still reads as "short" next to the id / layer brackets.
_PLAN_TAG_ACRONYM_MAX_LEN = 12


def derive_plan_tag_acronym(plan_slug: str) -> str:
    """Derive a short, uppercase acronym default suggestion from a plan slug.

    ``"decomposition-convergence-loop"`` -> ``"DCL"``; a single-word slug
    falls back to its own first ``_PLAN_TAG_ACRONYM_MAX_LEN`` chars
    (``"auth"`` -> ``"AUTH"``). See JIRA_FORMAT.md's "Plan tag" section.
    """
    words = _PLAN_TAG_ACRONYM_WORD_RE.findall(plan_slug)
    if not words:
        return ""
    if len(words) == 1:
        return words[0][:_PLAN_TAG_ACRONYM_MAX_LEN].upper()
    return "".join(w[0] for w in words).upper()[:_PLAN_TAG_ACRONYM_MAX_LEN]


def is_frontend_impacting(story: Story) -> bool:
    """Whether ``story`` surfaces frontend work.

    True for ``frontend``/``full_stack`` layers, and for ``backend`` when
    it carries a non-empty ``ui_impact`` other than the literal ``none``.
    Reads only ``layer`` and ``ui_impact``; never inspects files or prose.
    """
    if story.layer in (_LAYER_FRONTEND, _LAYER_FULL_STACK):
        return True
    if story.layer == _LAYER_BACKEND:
        return story.ui_impact.strip().lower() not in ("", "none")
    return False


def _read_layer_fields(item: dict) -> tuple[str, str, list[str]]:
    """Coerce the three additive story fields from a raw dict, additively.

    Shared by the JSON export parser (``parse_jira_response``) and the JSON
    lint reader (``_read_json_stories_for_lint``) so the two never drift.
    Every field defaults on missing/invalid — never rejects — since the
    fields are additive over legacy exports that omit them entirely.
    """
    raw_layer = item.get("layer")
    layer = raw_layer if raw_layer in _VALID_LAYERS else _LAYER_UNSPECIFIED
    raw_ui_impact = item.get("ui_impact")
    ui_impact = raw_ui_impact if isinstance(raw_ui_impact, str) else ""
    raw_ftr = item.get("frontend_test_recommendation")
    frontend_test_recommendation = (
        [x for x in raw_ftr if isinstance(x, str)]
        if isinstance(raw_ftr, list)
        else []
    )
    return layer, ui_impact, frontend_test_recommendation


def _optional_stripped_str(value: object) -> str:
    """Coerce a raw JSON value to a stripped string, ``""`` when absent/non-str.

    Shared by every JSON reader here (``parse_jira_response``,
    ``_read_json_stories_for_lint``, ``_read_json_tickets``) so the
    additive string fields — ``plain_summary``, ``jira_issue_key`` — are
    normalized identically in all of them.
    """
    return value.strip() if isinstance(value, str) else ""


def shell_jira_invoker(prompt: str) -> str:
    """Production invoker: run ``claude -p`` and capture stdout.

    Delegates to :func:`plan_tool.shell.claude_invoke`. Returns ``""``
    when the executable isn't on PATH (the parser treats that as a
    failure, so the caller raises a clean ``JiraError``).
    """
    _, stdout = claude_invoke(prompt)
    return stdout


def _render_epic_block(epic: Epic) -> str:
    """Render the prompt's per-epic context section.

    Names the epic and the real JIRA epic id (if known) so claude can
    include it in story descriptions when relevant. An epic is always
    required — plans without an assignment in ``jira-config.json`` are
    rejected upstream before reaching this helper.
    """
    parts = [
        "## Epic context",
        "",
        f"These stories belong to epic **{epic.key}** ({epic.name}).",
    ]
    if epic.description:
        parts.append("")
        parts.append(f"Epic description: {epic.description}")
    parts.append("")
    parts.append(
        f"Every story id MUST start with `{epic.key}-S` (e.g. "
        f"`{epic.key}-S1`, `{epic.key}-S2`). Story ids without this "
        "prefix will be rejected."
    )
    return "\n".join(parts)


def parse_jira_response(
    raw: str,
    plan_step_ids: list[int],
    *,
    epic: Epic,
    min_number: int = 1,
    required_steps: Optional[set[int]] = None,
    known_ids: Optional[set[str]] = None,
    allowed_existing_ids: Optional[set[str]] = None,
) -> Optional[list[Story]]:
    """Extract a list of ``Story`` objects from a claude response.

    Lenient extraction: finds the outermost ``[``…``]`` pair and parses
    it as JSON. Surrounding chatter and ```json code fences are
    tolerated.

    Contract enforcement (rejects on violation):

    - Each story's ``id`` must match ``^<EPIC_KEY>-S\\d+$`` and the
      integer suffix must be ``>= min_number`` unless the id is in
      ``allowed_existing_ids``. Ids must be unique
      within the response and must not collide with an already-created
      ticket id in ``known_ids``.
    - ``estimate_hours`` must be a positive integer — an advisory size
      signal with no upper cap (``--max-hours`` is a soft prompt target,
      not a reject gate). See JIRA_FORMAT.md.
    - ``steps`` must be a non-empty list of distinct ints, every id
      referencing a real plan step in ``plan_step_ids``.
    - ``depends_on`` entries must each match the same story-id shape AND
      reference an id that's elsewhere in the response or in
      ``known_ids`` (an already-created ticket the new story builds on).
    - Every plan step id in ``required_steps`` (default: all
      ``plan_step_ids``) must appear in at least one story's ``steps``
      field. Missing coverage is a hard reject — the tool's contract is
      "no selected plan step is silently dropped." Callers can select a
      subset when they need to validate only active work.

    ``min_number`` enforces global uniqueness across plans: the caller
    scans previously-written ``jira-stories`` files for the same epic
    and passes ``max_existing + 1`` so the new plan's ids can't collide
    with ones already in flight.

    ``known_ids`` carries the ids of already-created tickets (append
    mode): new ids may not reuse them, and ``depends_on`` may reference
    them.

    ``allowed_existing_ids`` carries already-created partial ticket ids
    that this response is explicitly refreshing. Those ids may be reused
    in the response and may be below ``min_number``; all other ids keep
    the normal collision and numbering guards.

    Returns ``None`` when nothing parseable was found or the contract
    above is violated.
    """
    text = raw.strip()
    if not text:
        return None
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        items = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list) or not items:
        return None

    story_id_re = build_story_id_re(epic)
    stories: list[Story] = []
    seen_ids: set[str] = set()
    plan_step_id_set = set(plan_step_ids)
    required = (
        required_steps if required_steps is not None else set(plan_step_ids)
    )
    known = known_ids or set()
    allowed_existing = allowed_existing_ids or set()
    covered_steps: set[int] = set()

    for item in items:
        if not isinstance(item, dict):
            return None

        story_id = item.get("id")
        if not isinstance(story_id, str) or not story_id_re.match(story_id):
            return None
        if story_id in seen_ids:
            return None
        if story_id in known and story_id not in allowed_existing:
            return None
        number_match = _STORY_ID_NUMBER_RE.search(story_id)
        if number_match is None:
            return None
        if (
            int(number_match.group(1)) < min_number
            and story_id not in allowed_existing
        ):
            return None
        seen_ids.add(story_id)

        title = item.get("title")
        description = item.get("description")
        if not isinstance(title, str) or not title.strip():
            return None
        if not isinstance(description, str):
            return None

        # Additive PM-facing preamble — default empty, never rejects.
        plain_summary = _optional_stripped_str(item.get("plain_summary"))

        acceptance = item.get("acceptance_criteria") or []
        if not isinstance(acceptance, list) or not all(
            isinstance(a, str) for a in acceptance
        ):
            return None

        files = item.get("files") or []
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            return None

        steps_field = item.get("steps")
        if not isinstance(steps_field, list) or not steps_field:
            return None
        if any(isinstance(s, bool) or not isinstance(s, int) for s in steps_field):
            return None
        if len(set(steps_field)) != len(steps_field):
            return None
        if any(s not in plan_step_id_set for s in steps_field):
            return None
        covered_steps.update(steps_field)

        depends_on = item.get("depends_on") or []
        if not isinstance(depends_on, list) or not all(
            isinstance(d, str) for d in depends_on
        ):
            return None
        if not all(story_id_re.match(d) for d in depends_on):
            return None

        raw_estimate = item.get("estimate_hours", 0)
        if isinstance(raw_estimate, bool) or not isinstance(raw_estimate, int):
            if isinstance(raw_estimate, float):
                raw_estimate = int(raw_estimate)
            else:
                return None
        if raw_estimate < 1:
            return None

        # New fields are additive: default on missing/invalid, never reject.
        layer, ui_impact, frontend_test_recommendation = _read_layer_fields(item)

        stories.append(
            Story(
                id=story_id,
                title=title.strip(),
                description=description,
                plain_summary=plain_summary,
                acceptance_criteria=list(acceptance),
                files=list(files),
                steps=list(steps_field),
                depends_on=list(depends_on),
                estimate_hours=raw_estimate,
                layer=layer,
                ui_impact=ui_impact,
                frontend_test_recommendation=frontend_test_recommendation,
            )
        )

    # Cross-story validation: every depends_on must point at a story id
    # that's in this response or at an already-created ticket the new
    # story builds on. Catches typos and dangling references that would
    # otherwise look fine to a markdown reader.
    resolvable_ids = seen_ids | known
    for s in stories:
        for d in s.depends_on:
            if d not in resolvable_ids:
                return None

    # Coverage check: every required plan step must be covered by at least
    # one story.
    if not required.issubset(covered_steps):
        return None

    return _normalize_story_references(stories, epic)


def _render_markdown_header(
    plan_title: str,
    story_count: int,
    total_estimate: int,
    *,
    epic: Epic,
    source_plan_path: Optional[str] = None,
) -> str:
    """Render the plan-level markdown header (no trailing blank line).

    Kept separate from the per-story blocks so a companion regeneration can
    recompute the count + total over the merged (frozen + new) set
    without re-rendering the carried historical blocks.

    ``source_plan_path`` (default ``None``, no line) is companion-only
    informational context. Embedded provenance remains the ownership proof.
    """
    noun = "story" if story_count == 1 else "stories"
    lines = [
        f"# JIRA stories — {plan_title}",
        "",
        f"_Epic: **{epic.key}** ({epic.name})_",
    ]
    if source_plan_path is not None:
        lines.append(f"_Source plan: `{source_plan_path}`_")
    lines.append("")
    lines.append(f"_{story_count} {noun} · total estimate: {total_estimate}h_")
    return "\n".join(lines)


def _render_story_block(
    story: Story,
    *,
    detail_map: dict[int, str],
    plan_tag: str = "",
    step_status_map: Optional[dict[int, str]] = None,
) -> str:
    """Render one self-contained story block (no trailing blank line).

    The block header line carries a ``[state: <s>]`` tag so a re-run can
    read each ticket's state back and rewrite it in place without
    re-synthesizing the concept, followed by ``[jira: <key>]`` once
    someone records the real key. The key tag comes last — after every
    tool-written token — and is omitted entirely while the key is blank.

    ``step_status_map`` (default ``None``) is companion-only: it labels
    each covered step's captured ``pending``/``current``/``done`` status
    in "## Plan details" and marks the block historical when every
    covered step is done. ``None`` renders exactly as before.
    """
    steps_label = ", ".join(str(s) for s in story.steps)
    lines: list[str] = []
    lines.append(_STORY_SEPARATOR)
    header = (
        f"{story.id} — Plan steps: {steps_label}   "
        f"(estimate: {story.estimate_hours}h)   [state: {story.export_state}]"
    )
    if story.jira_issue_key:
        header += f"   [jira: {story.jira_issue_key}]"
    lines.append(header)
    lines.append(_STORY_SEPARATOR)
    lines.append("")
    lines.append("## Title")
    # The leading ``[<id>] `` matches the format the actual JIRA
    # tickets carry, so a reviewer searching JIRA for a ticket can
    # locate the corresponding block in this file (and vice versa).
    # ``plan_tag_bracket`` / ``layer_tag`` are render-only decorations
    # between the id prefix and the title; each empty tag is dropped so a
    # blank ``plan_tag`` or ``unspecified`` layer stays ``[<id>] <title>``
    # with a single space (neither ever touches Story.title).
    title_parts = [
        f"[{story.id}]",
        plan_tag_bracket(plan_tag),
        layer_tag(story.layer),
        story.title,
    ]
    lines.append(" ".join(part for part in title_parts if part))
    lines.append("")
    # Plain-English preamble first, so a PM grasps the ticket before the
    # technical ``## Description``. Heading is the write/read contract for
    # ``_read_markdown_stories_for_lint`` — keep it verbatim.
    lines.append("## In plain English")
    lines.append(story.plain_summary.strip() or "_(no summary)_")
    lines.append("")
    lines.append("## Description")
    lines.append(story.description.strip() or "_(no description)_")
    lines.append("")
    lines.append("## Acceptance criteria")
    if story.acceptance_criteria:
        for ac in story.acceptance_criteria:
            lines.append(f"- {ac}")
    else:
        lines.append("_(none specified)_")
    lines.append("")
    lines.append("## Files in scope")
    if story.files:
        for f in story.files:
            lines.append(f"- `{f}`")
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("## Plan details")
    for s in story.steps:
        detail_path = detail_map.get(s)
        status_suffix = ""
        if step_status_map is not None and s in step_status_map:
            status = step_status_map[s]
            status_suffix = f" ({status})"
        if detail_path:
            lines.append(f"- Step {s}{status_suffix}: `{detail_path}`")
        else:
            lines.append(f"- Step {s}{status_suffix} _(no detail file)_")
    lines.append("")
    if _is_historical_story(story, step_status_map):
        lines.append("_(historical — every covered step is already done)_")
        lines.append("")
    lines.append("## Depends on")
    if story.depends_on:
        for d in story.depends_on:
            lines.append(f"- {d}")
    else:
        lines.append("_(none)_")
    lines.append("")
    # Heading strings are the write/read contract for
    # ``_read_markdown_stories_for_lint`` — keep them verbatim.
    lines.append("## Layer")
    lines.append(story.layer)
    lines.append("")
    lines.append("## UI impact")
    # ``_(none)_`` for an empty note; a literal ``none`` renders as the
    # plain word so the two stay distinct on this surface.
    lines.append(story.ui_impact or "_(none)_")
    # Render the section when the story is frontend-impacting (so an empty
    # rec still shows the ``_(none specified)_`` prompt) OR whenever a
    # recommendation is populated — otherwise a rec set on a
    # non-frontend-impacting story would be silently dropped on round-trip.
    if is_frontend_impacting(story) or story.frontend_test_recommendation:
        lines.append("")
        lines.append("## Testing recommendation")
        if story.frontend_test_recommendation:
            for rec in story.frontend_test_recommendation:
                lines.append(f"- {rec}")
        else:
            lines.append("_(none specified)_")
    return "\n".join(lines)


def _is_historical_story(
    story: Story, step_status_map: Optional[dict[int, str]]
) -> bool:
    """Whether every listed step has the captured ``done`` status."""
    if step_status_map is None:
        return False
    statuses = [step_status_map[s] for s in story.steps if s in step_status_map]
    return bool(statuses) and len(statuses) == len(story.steps) and all(
        status == StepStatus.DONE.value for status in statuses
    )


def _story_to_json_dict(
    story: Story,
    detail_map: dict[int, str],
    *,
    plan_tag: str = "",
    step_status_map: Optional[dict[int, str]] = None,
) -> dict[str, object]:
    """Build the JSON object for one story (mirrors the rendered shape).

    ``step_status_map`` (default ``None``, no extra keys) is
    companion-only: it adds ``step_status`` (each covered step's captured
    status) and ``historical`` (true when every covered step is done).
    """
    # ``[<id>] `` prefix (plus the optional plan tag) mirrors the rendered
    # JIRA ticket titles so downstream tooling that uses this JSON to
    # create or update tickets gets the canonical shape.
    title_parts = [f"[{story.id}]", plan_tag_bracket(plan_tag), story.title]
    result: dict[str, object] = {
        "id": story.id,
        "title": " ".join(part for part in title_parts if part),
        "plain_summary": story.plain_summary,
        "description": story.description,
        "acceptance_criteria": list(story.acceptance_criteria),
        "files": list(story.files),
        "steps": list(story.steps),
        "plan_detail_paths": [
            detail_map[step] for step in story.steps if step in detail_map
        ],
        "depends_on": list(story.depends_on),
        "estimate_hours": story.estimate_hours,
        "export_state": story.export_state,
        # Layer is its own structured key here, so the JSON ``title``
        # stays clean of the markdown-only layer tag.
        "layer": story.layer,
        "ui_impact": story.ui_impact,
        "frontend_test_recommendation": list(story.frontend_test_recommendation),
    }
    if step_status_map is not None:
        step_status = {
            str(s): step_status_map[s] for s in story.steps if s in step_status_map
        }
        result["step_status"] = step_status
        result["historical"] = _is_historical_story(story, step_status_map)
    # LAST on purpose — everything above the tool wrote, this one key a
    # person did. Add new tool-written keys above it, never below.
    result["jira_issue_key"] = story.jira_issue_key
    return result


def _render_json_payload(
    plan_title: str,
    story_dicts: list[dict[str, object]],
    *,
    epic: Epic,
    total_estimate: int,
    source_plan_path: Optional[str] = None,
) -> str:
    """Serialize the top-level JSON object from pre-built story dicts.

    Shared by :func:`_render_story_json`'s fresh and frozen-history-splice
    cases so a companion regeneration that carries forward dropped history
    produces byte-identical shape to a fresh export of the same set.

    ``source_plan_path`` (default ``None``, key omitted) is companion-only
    informational context — see :func:`_render_markdown_header`.
    """
    payload: dict[str, object] = {"plan_title": plan_title}
    if source_plan_path is not None:
        payload["source_plan_path"] = source_plan_path
    payload["epic"] = epic.to_dict()
    payload["total_estimate_hours"] = total_estimate
    payload["stories"] = story_dicts
    return json.dumps(payload, indent=2)


def scan_existing_story_numbers(
    plan_path: Path, epic: Epic
) -> set[int]:
    """Find every ``<EPIC_KEY>-S<N>`` already used in sibling jira outputs.

    Scans ``<plan_path.parent>/plan-details/*/jira-stories.{md,json}``
    *and* the archived copies under
    ``<plan_path.parent>/archive/plan-details/*/jira-stories.{md,json}``
    for occurrences of the active epic's id pattern and returns the set
    of integer suffixes seen. Archived plans keep their original ids, so
    they must stay in the uniqueness scan — otherwise archiving a plan
    would silently free its numbers for reuse and collide a future
    export with already-created tickets. The current plan's own
    conventional output paths are excluded so re-running ``jira`` on the
    same plan reuses the same number range instead of incrementing past
    it on each run.

    A best-effort scan: unreadable files and JSON parse errors are
    silently skipped (returning a partial result is safer than failing
    the whole export over an unrelated stray file). Both formats are
    scanned with a single regex against file text — robust to id
    placements in either the structured ``"id"`` field or markdown
    headers.
    """
    from plan_tool.create import ARCHIVE_DIRNAME

    scan_dirs = [
        plan_path.parent / "plan-details",
        plan_path.parent / ARCHIVE_DIRNAME / "plan-details",
    ]

    own_md = derive_jira_output_path(plan_path, None, format="markdown")
    own_json = derive_jira_output_path(plan_path, None, format="json")
    own_paths = {own_md.resolve(), own_json.resolve()}

    pattern = re.compile(rf"\b{re.escape(epic.key)}-S(\d+)\b")
    found: set[int] = set()
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for path in scan_dir.glob("*/jira-stories.*"):
            if path.suffix not in (".md", ".json"):
                continue
            try:
                if path.resolve() in own_paths:
                    continue
            except OSError:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in pattern.finditer(text):
                try:
                    found.add(int(match.group(1)))
                except ValueError:
                    continue
    return found


def compute_start_number(plan_path: Path, epic: Epic) -> int:
    """Return the next ``<EPIC_KEY>-S<N>`` integer safe for a new plan.

    ``max(existing) + 1`` when other plans under the same epic have
    already written stories; ``1`` for the first plan under this epic.
    Combined with :func:`parse_jira_response`'s ``min_number`` check,
    this enforces global uniqueness of story ids across every
    jira-stories file in the repo.
    """
    existing = scan_existing_story_numbers(plan_path, epic)
    if not existing:
        return 1
    return max(existing) + 1


# Header line of a markdown story block, e.g.
#   AUTH-S1 — Plan steps: 1, 2   (estimate: 4h)   [status: todo]
# The ``[status: …]`` tag is optional so legacy artifacts written before
# the status feature still parse (they default to ``todo``).
# ``state`` accepts the legacy ``[status: todo|done]`` spelling as well as
# the current ``[state: …]`` so an export written before the handoff model
# still parses; ``_normalize_export_state`` maps it forward. Both tags are
# optional, and ``[jira: …]`` trails them.
_MD_BLOCK_HEADER_RE = re.compile(
    r"(?m)^={64}\n"
    r"(?P<id>[A-Z][A-Z0-9]{1,9}-S(?P<num>\d+)) — Plan steps: "
    r"(?P<steps>[\d,\s]+?)\s+\(estimate: (?P<est>\d+)h\)"
    r"(?:\s+\[(?:state|status): (?P<state>draft|created|dropped|todo|done)\])?"
    r"(?:\s+\[jira: (?P<jira_key>[^\]\n]+)\])?"
    # Tolerate anything else trailing the header line. ``[jira: …]`` is
    # hand-typed, so a malformed one (``[jira: ]``, a stray note) must not
    # make the whole block unparseable — an unparsed record could otherwise
    # lose its Jira-key ownership evidence during regeneration.
    r"[^\n]*\n"
    r"={64}\n"
)


@dataclass(frozen=True)
class _FrozenTicket:
    """One already-created ticket read back from an existing export.

    Its ``id`` / concept are immutable — only ``export_state`` may move,
    to ``dropped`` on a re-run when the plan stops covering it. ``raw``
    holds the verbatim merge material (the markdown block string, or the
    JSON story dict) so the concept is re-emitted byte-for-byte rather
    than re-synthesized.
    """

    id: str
    number: int
    steps: list[int]
    estimate_hours: int
    export_state: str
    raw_markdown: Optional[str] = None
    raw_json: Optional[dict] = field(default=None)
    jira_issue_key: str = ""


@dataclass(frozen=True)
class _ExistingExport:
    """Parsed view of a jira-stories file that already exists on disk.

    Pair ownership stays on :class:`_ExistingStorySourceCapture`'s parsed
    provenance. This record contains only frozen story data.
    """

    format: str
    tickets: list[_FrozenTicket]

    @property
    def ids(self) -> set[str]:
        return {t.id for t in self.tickets}

    @property
    def numbers(self) -> set[int]:
        return {t.number for t in self.tickets}

    def covered_current_steps(self, current: set[int]) -> set[int]:
        """Plan steps (in ``current``) covered by some existing ticket."""
        covered: set[int] = set()
        for t in self.tickets:
            covered.update(s for s in t.steps if s in current)
        return covered


def _read_existing_export_text(
    text: str, *, format: str, epic: Epic
) -> Optional[_ExistingExport]:
    """Parse one already-captured story source for paired regeneration."""

    if format == "markdown":
        tickets = _read_markdown_tickets(text, epic)
    elif format == "json":
        tickets = _read_json_tickets(text, epic)
    else:
        return None

    if not tickets:
        return None
    return _ExistingExport(format=format, tickets=tickets)


def _read_markdown_tickets(text: str, epic: Epic) -> list[_FrozenTicket]:
    """Extract frozen tickets (with verbatim blocks) from markdown text."""
    text = strip_markdown_provenance(text)
    matches = [
        m
        for m in _MD_BLOCK_HEADER_RE.finditer(text)
        if m.group("id").startswith(story_id_prefix(epic))
    ]
    tickets: list[_FrozenTicket] = []
    for i, m in enumerate(matches):
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw_block = text[m.start() : block_end].rstrip("\n")
        try:
            steps = [int(p) for p in m.group("steps").split(",") if p.strip()]
        except ValueError:
            continue
        jira_key = (m.group("jira_key") or "").strip()
        tickets.append(
            _FrozenTicket(
                id=m.group("id"),
                number=int(m.group("num")),
                steps=steps,
                estimate_hours=int(m.group("est")),
                export_state=_resolve_export_state(m.group("state"), jira_key),
                raw_markdown=raw_block,
                jira_issue_key=jira_key,
            )
        )
    return tickets


def _read_json_tickets(text: str, epic: Epic) -> list[_FrozenTicket]:
    """Extract frozen tickets (with verbatim dicts) from JSON text."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    raw_stories = payload.get("stories")
    if not isinstance(raw_stories, list):
        return []
    prefix = story_id_prefix(epic)
    tickets: list[_FrozenTicket] = []
    for item in raw_stories:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        if not isinstance(sid, str) or not sid.startswith(prefix):
            continue
        num_match = _STORY_ID_NUMBER_RE.search(sid)
        if num_match is None:
            continue
        steps = item.get("steps")
        if not isinstance(steps, list) or not all(
            isinstance(s, int) and not isinstance(s, bool) for s in steps
        ):
            continue
        estimate = item.get("estimate_hours", 0)
        if isinstance(estimate, bool) or not isinstance(estimate, int):
            estimate = 0
        jira_key = _optional_stripped_str(item.get("jira_issue_key"))
        # ``status`` is the legacy key this replaced; read either.
        raw_state = item.get("export_state", item.get("status"))
        tickets.append(
            _FrozenTicket(
                id=sid,
                number=int(num_match.group(1)),
                steps=list(steps),
                estimate_hours=estimate,
                export_state=_resolve_export_state(raw_state, jira_key),
                raw_json=dict(item),
                jira_issue_key=jira_key,
            )
        )
    return tickets


def read_stories_for_lint(path: Path) -> list[Story]:
    """Read a markdown or JSON jira-stories artifact for AC linting.

    This parser is intentionally independent of epic assignment. Lint
    mode must be able to inspect an existing export for a plan that has
    not yet been assigned in ``jira-config.json`` and must not persist
    any config while doing so.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise JiraError(f"failed to read jira lint input {path}: {exc}") from exc
    if path.suffix == ".json":
        return _read_json_stories_for_lint(text)
    return _read_markdown_stories_for_lint(text)


def _read_json_stories_for_lint(text: str) -> list[Story]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JiraError(f"could not parse jira lint JSON input: {exc}") from exc
    if isinstance(payload, list):
        raw_stories = payload
    elif isinstance(payload, dict) and isinstance(payload.get("stories"), list):
        raw_stories = payload["stories"]
    else:
        raise JiraError(
            "jira lint JSON input must be a story array or object with stories"
        )

    stories: list[Story] = []
    for item in raw_stories:
        if not isinstance(item, dict):
            continue
        story_id = item.get("id")
        title = item.get("title")
        description = item.get("description")
        acceptance = item.get("acceptance_criteria") or []
        files = item.get("files") or []
        steps = item.get("steps") or []
        depends_on = item.get("depends_on") or []
        estimate = item.get("estimate_hours", 0)
        if not isinstance(story_id, str) or not story_id.strip():
            continue
        if not isinstance(title, str):
            title = ""
        if title.startswith(f"[{story_id}] "):
            title = title[len(story_id) + 3 :]
        if not isinstance(description, str):
            description = ""
        plain_summary = _optional_stripped_str(item.get("plain_summary"))
        if not isinstance(acceptance, list):
            acceptance = []
        if not isinstance(files, list):
            files = []
        if not isinstance(steps, list):
            steps = []
        if not isinstance(depends_on, list):
            depends_on = []
        if isinstance(estimate, bool) or not isinstance(estimate, int):
            estimate = 0
        jira_issue_key = _optional_stripped_str(item.get("jira_issue_key"))
        export_state = _resolve_export_state(
            item.get("export_state", item.get("status")), jira_issue_key
        )
        layer, ui_impact, frontend_test_recommendation = _read_layer_fields(item)
        stories.append(
            Story(
                id=story_id,
                title=title,
                description=description,
                plain_summary=plain_summary,
                acceptance_criteria=[a for a in acceptance if isinstance(a, str)],
                files=[f for f in files if isinstance(f, str)],
                steps=[
                    s
                    for s in steps
                    if isinstance(s, int) and not isinstance(s, bool)
                ],
                depends_on=[d for d in depends_on if isinstance(d, str)],
                estimate_hours=estimate,
                export_state=export_state,
                layer=layer,
                ui_impact=ui_impact,
                frontend_test_recommendation=frontend_test_recommendation,
                jira_issue_key=jira_issue_key,
            )
        )
    return stories


def _read_markdown_stories_for_lint(text: str) -> list[Story]:
    text = strip_markdown_provenance(text)
    matches = list(_MD_BLOCK_HEADER_RE.finditer(text))
    stories: list[Story] = []
    for i, match in enumerate(matches):
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[match.start() : block_end].rstrip("\n")
        story_id = match.group("id")
        try:
            steps = [int(p) for p in match.group("steps").split(",") if p.strip()]
        except ValueError:
            steps = []
        raw_layer = _markdown_section(block, "Layer").strip()
        layer = raw_layer if raw_layer in _VALID_LAYERS else _LAYER_UNSPECIFIED
        title = _markdown_section(block, "Title").strip()
        title_prefix = f"[{story_id}] "
        if title.startswith(title_prefix):
            title = title[len(title_prefix) :]
        # Undo the render-only layer tag so it never leaks into Story.title
        # (else re-render doubles it). Strip exactly what render would have
        # written for this layer — render always emits the tag and ``##
        # Layer`` together, so the canonical ``layer_tag(layer)`` is symmetric.
        # For an unspecified layer render writes no tag, so a directly edited
        # ``[BE] `` title prefix is left intact (never destroy authored text).
        tag = layer_tag(layer)
        if tag and title.startswith(f"{tag} "):
            title = title[len(tag) + 1 :]
        plain_summary = _markdown_section(block, "In plain English").strip()
        # ``_(no summary)_`` is the empty-preamble sentinel the renderer
        # writes; read it back as empty so it round-trips empty→empty.
        if plain_summary == "_(no summary)_":
            plain_summary = ""
        ui_impact = _markdown_section(block, "UI impact").strip()
        # ``_(none)_`` is the empty-note sentinel the renderer writes; read
        # it back as empty so ui_impact round-trips empty→empty (and
        # is_frontend_impacting doesn't flip).
        if ui_impact == "_(none)_":
            ui_impact = ""
        frontend_test_recommendation = _markdown_bullets(
            _markdown_section(block, "Testing recommendation")
        )
        jira_issue_key = (match.group("jira_key") or "").strip()
        stories.append(
            Story(
                id=story_id,
                title=title,
                description=_markdown_section(block, "Description").strip(),
                plain_summary=plain_summary,
                acceptance_criteria=_markdown_bullets(
                    _markdown_section(block, "Acceptance criteria")
                ),
                files=_markdown_code_bullets(
                    _markdown_section(block, "Files in scope")
                ),
                steps=steps,
                depends_on=_markdown_bullets(_markdown_section(block, "Depends on")),
                estimate_hours=int(match.group("est")),
                export_state=_resolve_export_state(
                    match.group("state"), jira_issue_key
                ),
                layer=layer,
                ui_impact=ui_impact,
                frontend_test_recommendation=frontend_test_recommendation,
                jira_issue_key=jira_issue_key,
            )
        )
    return stories


def _markdown_section(block: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)"
    )
    match = pattern.search(block)
    return match.group("body").strip() if match is not None else ""


def _markdown_bullets(section: str) -> list[str]:
    bullets: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def _markdown_code_bullets(section: str) -> list[str]:
    values: list[str] = []
    for bullet in _markdown_bullets(section):
        if bullet.startswith("`") and "`" in bullet[1:]:
            values.append(bullet[1 : bullet.find("`", 1)])
        elif bullet not in ("_(none)_",):
            values.append(bullet)
    return values


def reconcile_existing_statuses(
    existing: _ExistingExport, current_plan_steps: set[int]
) -> tuple[list[_FrozenTicket], list[str]]:
    """Mark tickets ``dropped`` when the plan stops covering them.

    A ticket is dropped when *every* plan step it covered is gone from the
    current plan — the concept was removed outright, or merged into
    another step that survives under a different ticket. The ticket's id,
    title, description, and acceptance criteria are untouched; only the
    state tag changes, so a ticket already in JIRA still matches what
    someone reads there. Tickets that still cover at least one live step,
    and tickets already ``dropped``, pass through unchanged.

    ``dropped`` says nothing about what should happen to the JIRA ticket —
    cancel, repurpose, or leave alone is a call made in JIRA. The caller
    surfaces the ids so a person can make it.

    Returns the reconciled ticket list (with verbatim merge material
    updated to carry the new state) and the ids newly dropped.
    """
    reconciled: list[_FrozenTicket] = []
    newly_dropped: list[str] = []
    for t in existing.tickets:
        still_live = any(s in current_plan_steps for s in t.steps)
        if still_live or t.export_state == _EXPORT_STATE_DROPPED:
            reconciled.append(t)
            continue
        newly_dropped.append(t.id)
        raw_markdown = (
            _set_markdown_block_state(t.raw_markdown, _EXPORT_STATE_DROPPED)
            if t.raw_markdown is not None
            else None
        )
        raw_json: Optional[dict] = None
        if t.raw_json is not None:
            raw_json = dict(t.raw_json)
            raw_json.pop("status", None)
            raw_json["export_state"] = _EXPORT_STATE_DROPPED
        reconciled.append(
            _FrozenTicket(
                id=t.id,
                number=t.number,
                steps=t.steps,
                estimate_hours=t.estimate_hours,
                export_state=_EXPORT_STATE_DROPPED,
                raw_markdown=raw_markdown,
                raw_json=raw_json,
                jira_issue_key=t.jira_issue_key,
            )
        )
    return reconciled, newly_dropped


def _set_markdown_block_state(raw_block: str, state: str) -> str:
    """Return ``raw_block`` with its header ``[state: …]`` tag set.

    Edits only the state tag on the block's header line, leaving the rest
    of the verbatim concept intact — including any trailing
    ``[jira: …]``, which a person wrote and this must never disturb. A
    legacy ``[status: …]`` tag is replaced in place by the new spelling.
    When no tag is present at all, it is inserted after the
    ``(estimate: Nh)`` token, which keeps it ahead of ``[jira: …]``.
    """
    if _MD_STATE_TAG_RE.search(raw_block):
        return _MD_STATE_TAG_RE.sub(f"[state: {state}]", raw_block, count=1)
    return re.sub(
        r"(\(estimate: \d+h\))",
        rf"\1   [state: {state}]",
        raw_block,
        count=1,
    )


@dataclass(frozen=True)
class _StoryRenderInput:
    """Already-prepared stories ready to render into markdown or JSON.

    The single rendering boundary behind the paired export. The renderer turns
    this prepared shape
    into text: it never reads a file, invokes claude, decides which
    stories are current, or reconciles ticket state — those decisions are
    made by the caller before this is built.
    """

    plan_title: str
    epic: Epic
    new_stories: list[Story]
    frozen: list[_FrozenTicket] = field(default_factory=list)
    detail_map: dict[int, str] = field(default_factory=dict)
    plan_tag: str = ""
    # ``source_plan_path`` is informational; embedded provenance owns
    # same-plan proof. ``step_status_map`` labels each covered committed
    # step's captured status on ``new_stories`` only; frozen/dropped history
    # is re-emitted verbatim and never labeled.
    source_plan_path: Optional[str] = None
    step_status_map: Optional[dict[int, str]] = None


def _render_story_markdown(render_input: _StoryRenderInput) -> str:
    """Render ``render_input`` as the markdown jira-stories artifact.

    With no frozen tickets this is the fresh-export shape: a header
    followed by ``new_stories`` in their given (unsorted) order. With
    frozen tickets present (companion mode's retained dropped history),
    frozen blocks splice in verbatim and the combined set sorts by story
    number.
    """
    frozen = render_input.frozen
    new_stories = render_input.new_stories
    story_count = len(frozen) + len(new_stories)
    total_estimate = sum(t.estimate_hours for t in frozen) + sum(
        s.estimate_hours for s in new_stories
    )
    header = _render_markdown_header(
        render_input.plan_title,
        story_count,
        total_estimate,
        epic=render_input.epic,
        source_plan_path=render_input.source_plan_path,
    )
    new_blocks = [
        _render_story_block(
            s,
            detail_map=render_input.detail_map,
            plan_tag=render_input.plan_tag,
            step_status_map=render_input.step_status_map,
        )
        for s in new_stories
    ]
    if not frozen:
        return "\n\n".join([header, *new_blocks])
    frozen_pairs = [(t.number, t.raw_markdown or "") for t in frozen]
    new_pairs = [
        (_story_number(s.id), block) for s, block in zip(new_stories, new_blocks)
    ]
    parts = [header, *(block for _n, block in sorted(frozen_pairs + new_pairs))]
    return "\n\n".join(p.rstrip("\n") for p in parts)


def _render_story_json(render_input: _StoryRenderInput) -> str:
    """Render ``render_input`` as the JSON jira-stories artifact.

    Mirrors :func:`_render_story_markdown`'s fresh/frozen split: with no
    frozen tickets the total is summed straight from ``new_stories``. With
    frozen tickets present, frozen dicts splice in verbatim, the combined
    set sorts by story number, and the total recomputes from the rendered
    dicts.
    """
    frozen = render_input.frozen
    new_stories = render_input.new_stories
    new_dicts = [
        _story_to_json_dict(
            s,
            render_input.detail_map,
            plan_tag=render_input.plan_tag,
            step_status_map=render_input.step_status_map,
        )
        for s in new_stories
    ]
    if not frozen:
        return _render_json_payload(
            render_input.plan_title,
            new_dicts,
            epic=render_input.epic,
            total_estimate=sum(s.estimate_hours for s in new_stories),
            source_plan_path=render_input.source_plan_path,
        )
    frozen_pairs = [
        (
            _story_number(str(t.raw_json.get("id", t.id)))
            if t.raw_json
            else t.number,
            dict(t.raw_json or {}),
        )
        for t in frozen
    ]
    new_pairs = [
        (_story_number(s.id), d) for s, d in zip(new_stories, new_dicts)
    ]
    all_dicts = [d for _n, d in sorted(frozen_pairs + new_pairs)]
    total = 0
    for d in all_dicts:
        est = d.get("estimate_hours", 0)
        if isinstance(est, int) and not isinstance(est, bool):
            total += est
    return _render_json_payload(
        render_input.plan_title,
        all_dicts,
        epic=render_input.epic,
        total_estimate=total,
        source_plan_path=render_input.source_plan_path,
    )


def _story_number(story_id: str) -> int:
    match = _STORY_ID_NUMBER_RE.search(story_id)
    return int(match.group(1)) if match is not None else 0


def derive_jira_output_path(
    plan_path: Path, plan: Optional[Plan], *, format: str
) -> Path:
    """Compute the conventional output path for a plan's jira stories.

    Format mirrors :func:`plan_tool.detail.derive_detail_path`::

        <plan_path.parent>/plan-details/<plan_slug>/jira-stories.<ext>

    ``plan_slug`` strips a leading ``<digit>-`` from ``plan_path.stem``
    (mirrors :class:`PlanEntry.slug` and ``detail._plan_slug``). ``ext``
    is ``md`` or ``json`` based on ``format``.

    The plan parameter is accepted for API symmetry with future helpers
    that might need plan-level context; today the function only uses
    ``plan_path`` and ``format``.
    """
    _ = plan  # accepted for API symmetry; unused today
    if format not in _VALID_FORMATS:
        raise JiraError(
            f"unknown format {format!r}; choose one of {_VALID_FORMATS}"
        )
    ext = "md" if format == "markdown" else "json"
    plan_slug = plan_slug_from_path(plan_path)
    return plan_path.parent / "plan-details" / plan_slug / f"jira-stories.{ext}"


def derive_default_handoff_output_path(
    story_output_path: Path, plan_path: Path
) -> Path:
    """Derive the conventional developer-handoff destination for a story path."""
    return (
        plan_path.parent
        / "jira-handoffs"
        / plan_slug_from_path(plan_path)
        / f"{story_output_path.stem}.developer-handoff.md"
    )


def plan_slug_from_path(plan_path: Path) -> str:
    """Strip a leading ``<digit>-`` from the plan filename's stem.

    Mirrors :class:`PlanEntry.slug` / ``detail._plan_slug`` so the
    conventional path stays consistent with how plans are named on disk.
    Public (not the private-by-convention ``_plan_slug`` it once was) so
    the CLI's plan-tag confirmation flow
    (``cli/jira_cmd.py:_assign_plan_tag_for_plan``) can derive its default
    suggestion from the same slug without reaching into a private name.
    """
    from plan_tool.locator import slug_from_filename

    result = slug_from_filename(plan_path)
    assert result is not None  # default_to_stem=True guarantees non-None
    return result


def _plan_identity_matches(stamped: str, current: str) -> bool:
    """Whether a stamped companion ``source_plan_path`` still identifies
    the same plan as ``current`` (both repo-relative posix paths).

    Ignores each side's leading ``<digit>-`` priority prefix, mirroring
    :func:`plan_slug_from_path`/:func:`derive_jira_output_path` — a
    plan's generated destinations are keyed off its slug alone, so
    renumbering it (its priority prefix changing) must not break
    recognition of its own prior companion output at that unchanged
    destination. Compares the parent directory verbatim (unlike the
    destination derivation) so a same-slug plan in a different directory
    is still correctly treated as a different plan.
    """
    if stamped == current:
        return True
    from plan_tool.locator import slug_from_filename

    stamped_path, current_path = PurePosixPath(stamped), PurePosixPath(current)
    return stamped_path.parent == current_path.parent and slug_from_filename(
        stamped_path.name
    ) == slug_from_filename(current_path.name)


def _plan_created_paths(plan: Plan) -> frozenset[str]:
    """The union of every step's ``creates`` — paths the plan declares it
    will bring into existence, so the missing-doc warning can skip them.
    """
    return frozenset(c for step in plan.steps for c in step.creates)


def _normalize_path(p: str) -> str:
    """Collapse a repo-root-relative path to a stable comparison key.

    Strips surrounding whitespace and normalizes ``./`` / duplicate
    separators so a story's ``files`` entry and a plan step's ``creates``
    entry compare equal when they name the same file.
    """
    return str(PurePosixPath(p.strip()))


def _emit_story_warnings(
    stories: list[Story],
    repo_root: Path,
    *,
    created_paths: AbstractSet[str] = frozenset(),
) -> None:
    """Print the soft missing-doc-file and acceptance-criteria warnings.

    Informational only (never rejects) — called from
    :func:`render_jira_export`, shared by the real-write and ``--no-write``
    paths so both surface the same guidance over the stories they emit.

    ``created_paths`` is the set of repo-root-relative paths the plan
    declares it will *create* (the union of every step's ``creates``).
    A documentation file a story is supposed to author won't exist on
    disk yet, so warning on it is a false positive — those paths are
    skipped.
    """
    # Soft-warn on documentation paths the story claims to touch but
    # that don't resolve under repo_root. We deliberately *don't* warn
    # on missing code/test files — claude routinely (and correctly)
    # proposes creating new source files as part of a story, so those
    # warnings are noise. Missing documentation files, on the other
    # hand, almost always indicate a typo or a stale reference to a
    # plan-detail doc that should already exist on disk — *unless* the
    # plan declares the doc under a step's `creates`, in which case the
    # story's whole job is to author it and its absence is expected.
    created_norm = {_normalize_path(c) for c in created_paths}
    for story in stories:
        for f in story.files:
            if not _is_documentation_path(f):
                continue
            if _normalize_path(f) in created_norm:
                continue
            if not (repo_root / f).exists():
                warn(
                    f"story {story.id} references file "
                    f"`{f}` that doesn't exist under repo root "
                    f"`{repo_root}`"
                )

    # Soft-warn on AC bullets that are vague ("code is clean") or
    # pinned to refactor-fragile internals ("test_foo passes",
    # "handler.ts:42"). The prompt teaches the same anti-patterns; this
    # is the safety net for the cases the prompt didn't dissuade.
    for body in lint_acceptance_criteria(stories):
        warn(body)

    # Soft-warn on missing layer-derived metadata: a backend/full_stack
    # story with no UI-impact note, or a frontend-impacting story with a
    # missing/thin test recommendation. Advisory only — deliberately not
    # in ``_raise_for_acceptance_criteria_lint`` so they never block a write.
    for body in lint_layer_metadata(stories):
        warn(body)

    # Soft-warn on stories below the decomposition floor (over-decomposition).
    # Advisory only — a skeptical nudge to consolidate, never a gate.
    for body in lint_story_size(stories):
        warn(body)


def _repo_relative_posix(path: Path, repo_root: Path) -> str:
    """Render ``path`` the way ``Step.detail`` is stored: repo-relative posix.

    Detail-map values flow verbatim into markdown links and JSON
    ``plan_detail_paths``, all of which assume that shape. A path outside
    ``repo_root`` (only reachable when a caller points the export at a
    plan elsewhere) keeps its absolute posix form rather than growing a
    ``../..`` chain no reader can follow.
    """
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# --------------------------------------------------------------------------
# Paired export-input capture
# --------------------------------------------------------------------------
#
# One immutable snapshot of every value that can change either the story
# export or the developer-handoff renders, captured once per invocation so
# both renderers read the same frozen
# inputs instead of re-reading live files at different points. Deliberately
# local to this module rather than a shared framework —
# ``roadmap_impact_snapshot.py`` captures a different stage-artifact
# contract and this does not generalize over it.
#
_DETAIL_STATE_PRESENT = "present"
_DETAIL_STATE_MISSING = "missing"

_STORY_SOURCE_ABSENT = "absent"
_STORY_SOURCE_PRESENT = "present"

# Bumped when the story prompt's or handoff rendering contract changes in a
# way that should invalidate a fingerprint taken over this snapshot.
_STORY_PROMPT_CONTRACT_REVISION = 1
_HANDOFF_FORMAT_CONTRACT_REVISION = 1

# Run-grade required sections; see DETAIL_FORMAT.md.
_RUN_GRADE_H2_TOKENS = (
    "summary", "table", "why", "files", "implementation", "tests", "acceptance",
)

_RUN_GRADE_DETAIL_H2_RE = re.compile(r"^##[ \t]+([A-Za-z]+)", re.MULTILINE)


def _run_grade_detail_missing_sections(text: str) -> list[str]:
    """Required run-grade H2 tokens absent from ``text``, in contract order.

    A read-only structural check: unlike
    ``detail.py:parse_detail_response``, it never synthesizes a stub for a
    missing section, so a companion snapshot only ever holds bytes that
    were actually validated.

    Excludes matches inside fenced code so a fenced example mentioning a
    required heading (e.g. a snippet demonstrating ``## Tests``) can't stand
    in for a real one and hide an actually-missing section.
    """
    fenced_spans = _fenced_code_spans(text).spans
    headings = {
        m.group(1).lower()
        for m in _RUN_GRADE_DETAIL_H2_RE.finditer(text)
        if not any(start <= m.start() < end for start, end in fenced_spans)
    }
    return [tok for tok in _RUN_GRADE_H2_TOKENS if tok not in headings]


@dataclass(frozen=True)
class _StepDetailInput:
    """One committed step's captured selected-detail render input.

    ``state`` is ``_DETAIL_STATE_PRESENT`` (validated body captured
    verbatim, ``path`` + ``text`` set) or ``_DETAIL_STATE_MISSING`` (no
    selected detail at all, or a declared pointer whose target isn't on
    disk — either way only legal on a ``done`` step, kept for a later
    historical fallback). A present-but-unreadable-or-structurally-invalid
    detail never reaches this state: capture rejects it outright,
    regardless of step status.
    """

    state: str
    path: Optional[str] = None
    text: Optional[str] = None


def _capture_run_grade_step_detail(step: Step, repo_root: Path) -> _StepDetailInput:
    """Capture valid run detail; an absent pointer or file counts as missing."""
    if step.detail is None:
        return _StepDetailInput(state=_DETAIL_STATE_MISSING)
    path = repo_root / step.detail
    rel = _repo_relative_posix(path, repo_root)
    if not path.is_file():
        return _StepDetailInput(state=_DETAIL_STATE_MISSING)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise JiraError(
            f"step {step.id} ({step.title}): selected detail `{rel}` could "
            f"not be read: {exc}"
        ) from exc
    try:
        require_supported_detail_format_version(text, path=path)
    except DetailFormatError as exc:
        raise JiraError(
            f"step {step.id} ({step.title}): selected detail `{rel}`: {exc}"
        ) from exc
    # Check before, not just inside, _run_grade_detail_missing_sections: an
    # unmatched opening fence makes _fenced_code_spans treat everything from
    # the opener to EOF as fenced, so a real heading after it is excluded and
    # reported as a confusing generic "missing section" instead of the clear
    # fence diagnostic every sibling guard in this module already gives.
    if _fenced_code_spans(text).unmatched_opening is not None:
        raise JiraError(
            f"step {step.id} ({step.title}): selected detail `{rel}` has an "
            "unmatched opening code fence; add a matching closing fence "
            "before exporting."
        )
    missing = _run_grade_detail_missing_sections(text)
    if missing:
        raise JiraError(
            f"step {step.id} ({step.title}): selected detail `{rel}` is "
            f"missing required section(s): {', '.join(missing)}"
        )
    return _StepDetailInput(state=_DETAIL_STATE_PRESENT, path=rel, text=text)


@dataclass(frozen=True)
class _FileExcerptCapture:
    """One declared file's captured render state for a committed step.

    Mirrors :func:`_render_captured_file_excerpts`'s three cases (excerpted,
    absent, unreadable) so the snapshot holds the exact rendered state
    instead of a live path a later read could see differently.
    """

    path: str
    state: str  # "excerpt" | "missing" | "unreadable"
    excerpt: Optional[ExcerptResult] = None
    error: Optional[str] = None


def _capture_step_file_excerpts(
    step: Step, repo_root: Path, *, max_file_bytes: int
) -> tuple[_FileExcerptCapture, ...]:
    """Capture the "Current file contents" render input for ``step``."""
    if not step.all_files:
        return ()
    captures: list[_FileExcerptCapture] = []
    step_candidate_symbols = _derive_symbols(step.title)
    for f in step.all_files:
        path = repo_root / f
        if not path.is_file():
            captures.append(_FileExcerptCapture(path=f, state="missing"))
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            captures.append(
                _FileExcerptCapture(path=f, state="unreadable", error=str(exc))
            )
            continue
        candidate_symbols = list(step_candidate_symbols)
        _merge_candidate_symbols(candidate_symbols, _derive_file_path_symbols(f))
        excerpt = build_prompt_excerpt(
            f, body, candidate_symbols, max_bytes=max_file_bytes
        )
        captures.append(_FileExcerptCapture(path=f, state="excerpt", excerpt=excerpt))
    return tuple(captures)


@dataclass(frozen=True)
class _CommittedStepInput:
    """One committed step's captured render input.

    Everything else about the step (title, status, status_note, intent) is
    read from the snapshot's own ``plan.step_by_id(id)`` — only the values
    this module resolves from disk (selected detail, file excerpts) are
    duplicated here.
    """

    id: int
    detail: _StepDetailInput
    file_excerpts: tuple[_FileExcerptCapture, ...]


@dataclass(frozen=True)
class _ParkedStepHistory:
    """A deferred/``wont_do`` step's non-actionable historical record.

    Deliberately narrow: a parked step contributes only these four fields
    to companion input — no detail, excerpt, or dependency data is ever
    selected or validated for it.
    """

    id: int
    title: str
    scope: StepScope
    status_note: Optional[str]


@dataclass(frozen=True)
class _CompanionExportSettings:
    """Resolved, non-file-derived export settings captured once per run."""

    epic: Epic
    plan_tag: str
    format: str
    max_hours: int
    start_number: int
    story_prompt_contract_revision: int
    handoff_format_contract_revision: int


@dataclass(frozen=True)
class _ExistingStorySourceCapture:
    """The existing story-export file's captured state, if any.

    ``state`` is ``_STORY_SOURCE_ABSENT`` (no file at the story
    destination — a legitimate fresh-export case) or
    ``_STORY_SOURCE_PRESENT`` (a readable source, possibly with zero
    recognized tickets). Unreadable sources always refuse capture.
    """

    state: str
    existing: Optional["_ExistingExport"]
    provenance: Optional[CompanionProvenance] = None


def _capture_existing_story_source(
    path: Path, *, format: str, epic: Epic, adopt_existing: bool
) -> _ExistingStorySourceCapture:
    """Capture the existing story source at ``path``, or its absence.

    A readable but invalid JSON source is adoptable only with explicit
    ``--adopt-existing`` authority; otherwise it cannot be established.
    """
    if not path.is_file():
        return _ExistingStorySourceCapture(state=_STORY_SOURCE_ABSENT, existing=None)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise JiraError(
            f"companion capture cannot establish the existing story source "
            f"at {path}: {exc}"
        ) from exc
    if format == "json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            if adopt_existing:
                return _ExistingStorySourceCapture(
                    state=_STORY_SOURCE_PRESENT, existing=None
                )
            raise JiraError(
                f"companion capture cannot establish the existing story "
                f"source at {path}: invalid JSON ({exc})"
            ) from exc
    provenance = (
        read_json_provenance(text)
        if format == "json"
        else read_markdown_story_provenance(text)
    )
    existing = _read_existing_export_text(text, format=format, epic=epic)
    return _ExistingStorySourceCapture(
        state=_STORY_SOURCE_PRESENT, existing=existing, provenance=provenance
    )


@dataclass(frozen=True)
class _TargetContentProof:
    """A generated target's raw existence + SHA-256 digest at capture time.

    Ownership-validation evidence only — a later step compares this proof
    immediately before replacing the target to detect a human edit outside
    parsed ticket fields. Never a render input: it says nothing about what
    either artifact should say.
    """

    path: str
    exists: bool
    sha256: Optional[str]


_CONTENT_PROOF_CHUNK_BYTES = 1 << 16


def _capture_target_content_proof(path: Path, repo_root: Path) -> _TargetContentProof:
    rel = _repo_relative_posix(path, repo_root)
    if not path.is_file():
        return _TargetContentProof(path=rel, exists=False, sha256=None)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(_CONTENT_PROOF_CHUNK_BYTES), b""):
                digest.update(chunk)
    except OSError as exc:
        raise JiraError(
            f"could not read {path} to establish its content-state proof: {exc}"
        ) from exc
    return _TargetContentProof(path=rel, exists=True, sha256=digest.hexdigest())


def _all_detail_artifact_paths(
    plan_path: Path, plan: Plan, repo_root: Path
) -> frozenset[str]:
    """Canonical and declared detail paths for every step, including absent files."""
    paths: set[str] = set()
    for step in plan.steps:
        paths.add(
            _repo_relative_posix(derive_detail_path(plan_path, plan, step), repo_root)
        )
        if step.detail is not None:
            paths.add(_repo_relative_posix(repo_root / step.detail, repo_root))
    return frozenset(paths)


@dataclass(frozen=True)
class _TargetPreflightCapture:
    """Ownership-validation evidence for both generated targets.

    Ownership evidence only; it is never part of generated content.
    """

    story_target: _TargetContentProof
    handoff_target: _TargetContentProof


def _capture_target_preflight(
    plan_path: Path,
    plan: Plan,
    repo_root: Path,
    *,
    story_target: Path,
    handoff_target: Path,
) -> _TargetPreflightCapture:
    """Resolve both targets and reject a detail-artifact collision.

    Runs before any per-step detail/excerpt capture so a bad destination
    fails fast — mirroring "before any companion model invocation or
    handoff/story render" even though this function itself never renders
    or invokes anything.
    """
    detail_paths = _all_detail_artifact_paths(plan_path, plan, repo_root)
    for label, target in (("story", story_target), ("handoff", handoff_target)):
        rel = _repo_relative_posix(target, repo_root)
        if rel in detail_paths:
            raise JiraError(
                f"companion {label} target `{rel}` collides with a run-grade "
                "detail artifact path — choose a different "
                "destination"
            )
    return _TargetPreflightCapture(
        story_target=_capture_target_content_proof(story_target, repo_root),
        handoff_target=_capture_target_content_proof(handoff_target, repo_root),
    )


@dataclass(frozen=True)
class CompanionExportInput:
    """One immutable snapshot of every value that can change either the
    Jira story export or the developer handoff for one paired invocation.

    Captured once, up front, so both renderers consume the same frozen
    inputs instead of re-reading live files at different points — a file
    changed after capture can never change what either artifact says. See
    :func:`capture_companion_export_input`.
    """

    plan_path: Path
    plan: Plan
    frontmatter_text: str
    body_text: str
    committed_steps: tuple[_CommittedStepInput, ...]
    parked_step_history: tuple[_ParkedStepHistory, ...]
    settings: _CompanionExportSettings
    # A recognizable same-plan generated target may be replaced only when
    # its provenance binds it to this exact pair — a changed destination
    # or format is a distinct pair by construction (plain dataclass
    # equality). Shared with jira_handoff.HandoffRenderInput so both
    # capture and render carry one identity type, not a translated copy.
    pair_identity: HandoffPairIdentity
    existing_story_source: _ExistingStorySourceCapture
    # Explicit operator authority to migrate one readable, unproven legacy
    # story source. It never applies to the handoff target.
    adopt_existing: bool
    # Ownership-validation evidence, not a render input.
    target_preflight: _TargetPreflightCapture


def capture_companion_export_input(
    plan_path: Path,
    *,
    repo_root: Path,
    epic: Epic,
    story_output_path: Path,
    handoff_output_path: Path,
    format: str = "markdown",
    max_hours: int = 8,
    plan_tag: str = "",
    adopt_existing: bool = False,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
) -> CompanionExportInput:
    """Capture one immutable companion-mode export-input snapshot.

    Reads the plan file exactly once — frontmatter, body, and the
    validated model all come from that single read — and then captures
    every value the story or handoff render can consume. Raises
    ``JiraError`` before any of that rendering could begin when: a
    committed non-done step has no structurally valid selected detail; a
    committed step's present detail is structurally invalid (even when the
    step is done); a generated target collides with a detail artifact from
    run-grade detail; or an existing story source at ``story_output_path``
    cannot be established. Parked (``deferred``/``wont_do``) steps are
    never selected, validated, or excerpted — only their
    id/title/scope/status_note survive, in
    :attr:`CompanionExportInput.parked_step_history`.

    ``story_output_path`` / ``handoff_output_path`` are the caller's
    already-resolved final destinations. This function normalizes and
    records them but never derives a default for either. The CLI owns the
    conventional handoff path and flag precedence.
    """
    if format not in _VALID_FORMATS:
        raise JiraError(
            f"unknown format {format!r}; choose one of {_VALID_FORMATS}"
        )


    text = plan_path.read_text(encoding="utf-8")
    document = split_plan_document(text)
    plan = parse_plan_text(text)

    target_preflight = _capture_target_preflight(
        plan_path,
        plan,
        repo_root,
        story_target=story_output_path,
        handoff_target=handoff_output_path,
    )

    committed_inputs: list[_CommittedStepInput] = []
    problems: list[str] = []
    for step in plan.committed_steps:
        try:
            detail = _capture_run_grade_step_detail(step, repo_root)
        except JiraError as exc:
            problems.append(str(exc))
            continue
        if detail.state == _DETAIL_STATE_MISSING and step.status != StepStatus.DONE:
            problems.append(
                f"step {step.id} ({step.title}): companion capture requires "
                "a structurally valid selected detail for every committed "
                "step that is not done"
            )
            continue
        excerpts = _capture_step_file_excerpts(
            step, repo_root, max_file_bytes=max_file_bytes
        )
        committed_inputs.append(
            _CommittedStepInput(id=step.id, detail=detail, file_excerpts=excerpts)
        )

    if problems:
        noun = "step" if len(problems) == 1 else "steps"
        raise JiraError(
            f"companion capture could not ground {len(problems)} committed {noun}:\n"
            + "\n".join(f"- {problem}" for problem in problems)
        )

    parked_history = tuple(
        _ParkedStepHistory(
            id=step.id,
            title=step.title,
            scope=step.scope,
            status_note=step.status_note,
        )
        for step in plan.steps
        if step.scope is not StepScope.COMMITTED
    )

    settings = _CompanionExportSettings(
        epic=epic,
        plan_tag=plan_tag,
        format=format,
        max_hours=max_hours,
        start_number=compute_start_number(plan_path, epic),
        story_prompt_contract_revision=_STORY_PROMPT_CONTRACT_REVISION,
        handoff_format_contract_revision=_HANDOFF_FORMAT_CONTRACT_REVISION,
    )
    pair_identity = HandoffPairIdentity(
        story_path=_repo_relative_posix(story_output_path, repo_root),
        handoff_path=_repo_relative_posix(handoff_output_path, repo_root),
        format=settings.format,
    )
    existing_story_source = _capture_existing_story_source(
        story_output_path,
        format=settings.format,
        epic=epic,
        adopt_existing=adopt_existing,
    )

    return CompanionExportInput(
        plan_path=plan_path,
        plan=plan,
        frontmatter_text=document.frontmatter_yaml,
        body_text=document.body,
        committed_steps=tuple(committed_inputs),
        parked_step_history=parked_history,
        settings=settings,
        pair_identity=pair_identity,
        existing_story_source=existing_story_source,
        adopt_existing=adopt_existing,
        target_preflight=target_preflight,
    )


def _render_captured_file_excerpts(
    excerpts: tuple[_FileExcerptCapture, ...],
) -> str:
    """Build the prompt's "Current file contents" block from captured state.

    Renders each excerpt's captured "excerpt" / "missing" / "unreadable"
    case (``excerpts`` was captured once, up front, instead of a live
    read) so a file changed after capture can never change the prompt.
    """
    if not excerpts:
        return "_no files declared_"
    out: list[str] = []
    for fc in excerpts:
        if fc.state == "missing":
            out.append(f"#### `{fc.path}` _(not on disk)_\n")
            continue
        if fc.state == "unreadable":
            out.append(f"#### `{fc.path}` _(unreadable: {fc.error})_\n")
            continue
        excerpt = fc.excerpt
        assert excerpt is not None  # state == "excerpt" always carries one
        metadata = (
            f"_excerpt_kind: {excerpt.excerpt_kind}; "
            f"fallback_reason: {excerpt.fallback_reason or 'none'}; "
            f"truncated: {str(excerpt.truncated).lower()}_"
        )
        out.append(f"#### `{fc.path}`\n\n{metadata}\n\n```\n{excerpt.text}\n```\n")
    return "\n".join(out)


def _render_captured_steps_block(
    capture: "CompanionExportInput", *, max_file_bytes: int
) -> str:
    """Build the prompt's per-step context block from ``capture`` alone.

    Every value comes from the captured snapshot rather than a live read,
    scoped to the committed-only companion case: there is no
    ``covered_by`` annotation, since companion mode always regenerates
    the complete committed set rather than tracking what an earlier
    partial run already covered.
    """
    out: list[str] = []
    for ci in capture.committed_steps:
        step = capture.plan.step_by_id(ci.id)
        complexity = step.complexity.value if step.complexity else "unknown"
        out.append(f"### Step {step.id}: {step.title}{change_type_tag(step.change_type)}")
        out.append("")
        out.append(f"- complexity: {complexity}")
        if step.depends_on:
            deps = ", ".join(str(d) for d in step.depends_on)
            out.append(f"- depends on: {deps}")
        out.append("")
        out.append("**Files in scope:**")
        if step.files or step.creates:
            for f in step.files:
                out.append(f"- `{f}`")
            for f in step.creates:
                out.append(f"- `{f}` (new)")
        else:
            out.append("(no files declared)")
        out.append("")
        out.append("**Step detail:**")
        out.append("")
        if ci.detail.state == _DETAIL_STATE_MISSING:
            out.append("_(no detail file)_")
        else:
            text = ci.detail.text or ""
            snippet, _truncated = clip_text_to_byte_budget(
                text, max_bytes=max_file_bytes
            )
            out.append(f"_from `{ci.detail.path}`:_\n\n{snippet}")
        out.append("")
        out.append("**Current file contents:**")
        out.append("")
        out.append(_render_captured_file_excerpts(ci.file_excerpts))
        out.append("")
    return "\n".join(out)


def render_companion_export_prompt(
    capture: "CompanionExportInput", *, max_file_bytes: int = _MAX_PROMPT_FILE_BYTES
) -> str:
    """Render the companion-only export prompt from ``capture`` alone.

    Every step's title, files, detail body, and file excerpts come from
    the immutable snapshot rather than a live read, so a file changed
    after capture can never change what gets sent to the model. Companion
    mode always regenerates the complete committed set in a single pass —
    there is no "already-created tickets" block, and coverage is scoped
    to committed steps only — a deferred or ``wont_do`` step never
    reaches the model.
    """
    template_path = prompts_dir() / "jira.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    plan = capture.plan
    settings = capture.settings
    steps_block = _render_captured_steps_block(capture, max_file_bytes=max_file_bytes)
    prefix = story_id_prefix(settings.epic)
    start_number = settings.start_number
    prompt = template.safe_substitute(
        plan_title=plan.title,
        plan_status=plan.status.value,
        plan_priority=plan.priority.value,
        steps_block=steps_block,
        max_hours=str(settings.max_hours),
        epic_block=_render_epic_block(settings.epic),
        existing_tickets_block="",
        coverage_scope="every committed plan step",
        story_id_prefix=prefix,
        story_id_example=f"{prefix}{start_number}",
        story_id_example_2=f"{prefix}{start_number + 1}",
        story_id_example_dep=f"{prefix}{start_number + 2}",
        start_number=str(start_number),
    )
    return prompt


@dataclass(frozen=True)
class CompanionCreatedTicketNotice:
    """One created ticket a companion regeneration needs a human to act on.

    ``changed_created_tickets`` (content changed under an unchanged key)
    and ``created_to_dropped`` (the ticket's coverage left the committed
    set entirely) both carry this shape — see
    :class:`CompanionStoryExport`.
    """

    story_id: str
    jira_issue_key: str


@dataclass(frozen=True)
class CompanionStoryExport:
    """Result of regenerating companion-mode stories from one snapshot.

    ``output`` is the rendered story-source text (markdown or JSON per
    ``capture.settings.format``); ``stories`` is the current regenerated
    set with state/key already attached. Neither is written anywhere.
    """

    output: str
    stories: list[Story]
    dropped_history: list[_FrozenTicket]
    changed_created_tickets: list[CompanionCreatedTicketNotice]
    created_to_dropped: list[CompanionCreatedTicketNotice]


def _story_from_frozen_ticket(ticket: _FrozenTicket) -> Optional[Story]:
    """Reconstruct a comparable ``Story`` from a frozen ticket's raw content.

    Reuses the existing lint readers rather than re-deriving field
    extraction a third time — see :func:`_read_json_stories_for_lint` and
    :func:`_read_markdown_stories_for_lint`.
    """
    if ticket.raw_json is not None:
        stories = _read_json_stories_for_lint(
            json.dumps({"stories": [ticket.raw_json]})
        )
    elif ticket.raw_markdown is not None:
        stories = _read_markdown_stories_for_lint(ticket.raw_markdown)
    else:
        return None
    return stories[0] if stories else None


def _companion_story_content_signature(story: Story) -> tuple:
    """The comparable-content projection of ``story`` for change detection.

    Excludes ``id``, ``steps``, ``depends_on``, ``export_state``, and
    ``jira_issue_key`` — the id and dependency references are minted fresh
    on every companion regeneration regardless of content, and state/key
    are the ownership data being carried forward, not content.
    """
    return (
        story.title,
        story.plain_summary,
        story.description,
        tuple(story.acceptance_criteria),
        tuple(story.files),
        story.estimate_hours,
        story.layer,
        story.ui_impact,
        tuple(story.frontend_test_recommendation),
    )


def _companion_story_content_changed(ticket: _FrozenTicket, updated: Story) -> bool:
    """Whether ``updated``'s content differs from ``ticket``'s captured source.

    An unreconstructable prior record (neither ``raw_json`` nor
    ``raw_markdown`` set) is treated as changed — there is nothing to
    prove it *didn't* change, and understating a needed manual JIRA update
    is the unsafe direction.
    """
    old = _story_from_frozen_ticket(ticket)
    if old is None:
        return True
    return _companion_story_content_signature(
        old
    ) != _companion_story_content_signature(updated)


@dataclass(frozen=True)
class _ExistingCompanionTicketValidation:
    """Result of validating the existing story source alone (steps 1-5 of
    :func:`regenerate_companion_stories`), independent of any model
    response — see :func:`_validate_existing_companion_tickets`."""

    committed_ids: set[int]
    current_plan_identity: str
    tickets: list[_FrozenTicket]
    matchable_by_canon: dict[tuple[int, ...], list[_FrozenTicket]]
    dropped_history: list[_FrozenTicket]
    created_to_dropped: list[CompanionCreatedTicketNotice]


def _validate_existing_companion_tickets(
    capture: "CompanionExportInput", *, repo_root: Path
) -> _ExistingCompanionTicketValidation:
    """Run :func:`regenerate_companion_stories`'s structural checks on the
    existing story source alone — steps 1-5, none of which consult a model
    response. Shared by the real regeneration and the companion
    unwritten preview, so a preview never validates less than a real write
    would.

    Raises ``JiraError`` when: an existing record's covered-step set is
    empty or repeats an id; a non-dropped ``created`` record has no
    ``jira_issue_key``; a keyed record's source cannot prove it belongs to
    this plan (legacy or foreign export); a nonempty key appears on more
    than one existing record; a record mixes committed and parked/removed
    step coverage; a dropped record still names a committed step; or more
    than one existing record shares one canonical covered-step set.
    """
    committed_ids = {ci.id for ci in capture.committed_steps}
    existing = capture.existing_story_source.existing
    tickets: list[_FrozenTicket] = list(existing.tickets) if existing is not None else []

    # 1. Structural well-formedness, independent of coverage or matching.
    for t in tickets:
        if not t.steps:
            raise JiraError(
                f"companion regeneration: existing ticket {t.id} has an "
                "empty covered-step set"
            )
        if len(set(t.steps)) != len(t.steps):
            raise JiraError(
                f"companion regeneration: existing ticket {t.id} repeats a "
                "covered-step id"
            )
        if t.export_state == _EXPORT_STATE_CREATED and not t.jira_issue_key:
            raise JiraError(
                f"companion regeneration: existing ticket {t.id} is "
                "`created` without a jira_issue_key — record the key or "
                "mark the ticket dropped before regenerating"
            )

    # 2. A nonempty key occurs in only one *non-dropped* existing record —
    #    a dropped record's key needs no uniqueness proof since it never
    #    donates a key to a regenerated story (see step 4).
    current_plan_identity = _repo_relative_posix(capture.plan_path, repo_root)
    existing_provenance = capture.existing_story_source.provenance
    existing_plan_identity = (
        existing_provenance.source_plan_path
        if existing_provenance is not None
        else None
    )
    has_same_pair_proof = (
        existing_provenance is not None
        and existing_provenance.pair_identity == capture.pair_identity
    )
    seen_keys: dict[str, str] = {}
    for t in tickets:
        if not t.jira_issue_key or t.export_state == _EXPORT_STATE_DROPPED:
            continue
        prior_id = seen_keys.get(t.jira_issue_key)
        if prior_id is not None:
            raise JiraError(
                f"companion regeneration: jira key {t.jira_issue_key!r} "
                f"appears on both {prior_id} and {t.id} — a key must "
                "belong to exactly one existing record"
            )
        seen_keys[t.jira_issue_key] = t.id

    # 3. Reconcile against committed-only coverage — a record with zero
    #    remaining live coverage becomes dropped.
    if existing is not None:
        reconciled, newly_dropped_ids = reconcile_existing_statuses(
            existing, committed_ids
        )
    else:
        reconciled, newly_dropped_ids = [], []
    newly_dropped = set(newly_dropped_ids)
    originals_by_id = {t.id: t for t in tickets}

    dropped_history: list[_FrozenTicket] = []
    matchable: list[_FrozenTicket] = []
    created_to_dropped: list[CompanionCreatedTicketNotice] = []
    for t in reconciled:
        committed_part = set(t.steps) & committed_ids
        other_part = set(t.steps) - committed_ids
        if committed_part and other_part:
            raise JiraError(
                f"companion regeneration: existing ticket {t.id} mixes "
                "committed and parked/removed step coverage — split it by "
                "hand before regenerating"
            )
        if t.export_state == _EXPORT_STATE_DROPPED:
            if committed_part:
                raise JiraError(
                    f"companion regeneration: dropped existing ticket "
                    f"{t.id} still names committed step(s) "
                    f"{sorted(committed_part)}"
                )
            dropped_history.append(t)
            if t.id in newly_dropped:
                original = originals_by_id[t.id]
                if original.jira_issue_key:
                    created_to_dropped.append(
                        CompanionCreatedTicketNotice(
                            story_id=t.id, jira_issue_key=original.jira_issue_key
                        )
                    )
            continue
        # Non-dropped and fully committed: eligible for key matching.
        matchable.append(t)

    # 4. Same-plan proof for every matchable keyed record — checked only
    #    here, never for dropped/historical records, since only a
    #    matchable record can donate a key to a regenerated story. Never
    #    inferred from a matching title, output path, epic prefix, or
    #    story id alone.
    for t in matchable:
        has_same_plan_proof = (
            existing_plan_identity is not None
            and has_same_pair_proof
            and _plan_identity_matches(existing_plan_identity, current_plan_identity)
        )
        is_foreign_provenance = (
            existing_plan_identity is not None and not has_same_plan_proof
        )
        if t.jira_issue_key and (
            is_foreign_provenance
            or (not capture.adopt_existing and not has_same_plan_proof)
        ):
            raise JiraError(
                f"companion regeneration: existing ticket {t.id} carries "
                f"jira key {t.jira_issue_key!r} but its source cannot "
                "prove it belongs to this plan and generated-source pair "
                "(a legacy pre-companion export or a foreign source) — the "
                "key cannot be carried forward; use --adopt-existing only "
                "to migrate the selected legacy story source"
            )

    # 5. Canonical-set uniqueness among existing matchable records.
    matchable_by_canon: dict[tuple[int, ...], list[_FrozenTicket]] = {}
    for t in matchable:
        canon = tuple(sorted(t.steps))
        matchable_by_canon.setdefault(canon, []).append(t)
    for canon, group in matchable_by_canon.items():
        if len(group) > 1:
            raise JiraError(
                "companion regeneration: more than one existing source "
                f"record covers step set {list(canon)} "
                f"({', '.join(t.id for t in group)})"
            )

    return _ExistingCompanionTicketValidation(
        committed_ids=committed_ids,
        current_plan_identity=current_plan_identity,
        tickets=tickets,
        matchable_by_canon=matchable_by_canon,
        dropped_history=dropped_history,
        created_to_dropped=created_to_dropped,
    )


def regenerate_companion_stories(
    capture: "CompanionExportInput",
    raw_response: str,
    *,
    repo_root: Path,
) -> CompanionStoryExport:
    """Regenerate the companion-mode story source from one captured snapshot.

    Pure and file-free: every input is ``capture`` (step 1's immutable
    snapshot) and ``raw_response`` (the model's already-obtained reply).
    Renders through :func:`_render_story_markdown` /
    :func:`_render_story_json` and returns text plus lifecycle metadata;
    it never writes, stages, or replaces a file.

    Raises ``JiraError`` before producing a result for any reason
    :func:`_validate_existing_companion_tickets` does (steps 1-5), or when
    a keyed record's set has no regenerated match, or the model response
    is unparseable or reuses a retained historical story id (steps 6+).
    """
    plan = capture.plan
    settings = capture.settings
    epic = settings.epic
    validation = _validate_existing_companion_tickets(capture, repo_root=repo_root)
    committed_ids = validation.committed_ids
    current_plan_identity = validation.current_plan_identity
    tickets = validation.tickets
    matchable_by_canon = validation.matchable_by_canon
    dropped_history = validation.dropped_history
    created_to_dropped = validation.created_to_dropped

    # 6. Parse the model response against the committed-only step universe.
    #
    # ``known_ids`` covers every existing id, dropped included, so a *new*
    # story can never collide with retained history (dropped_history's ids
    # stay reserved and non-reusable). ``allowed_existing_ids`` is the
    # strictly narrower ``matchable`` subset -- non-dropped, fully
    # committed records step 3 above already proved eligible to donate a
    # key -- since only those are expected to be *refreshed* under the
    # same id every regeneration (compute_start_number's docstring:
    # re-running on the same plan reuses the same number range rather than
    # incrementing past it). Omitting allowed_existing_ids entirely made
    # every regeneration collide with the plan's own matchable ids;
    # widening it to all of known_ids would have let a new story silently
    # reuse a *dropped* id instead.
    reserved_ids = {t.id for t in tickets}
    matchable_ids = {t.id for group in matchable_by_canon.values() for t in group}
    new_stories = parse_jira_response(
        raw_response,
        sorted(committed_ids),
        epic=epic,
        min_number=settings.start_number,
        required_steps=committed_ids,
        known_ids=reserved_ids,
        allowed_existing_ids=matchable_ids,
    )
    if new_stories is None:
        raise JiraError(
            "companion regeneration: could not parse the model response "
            "(unparseable JSON, missing fields, invalid step references, "
            "an uncovered committed step, or a story id colliding with a "
            "retained historical id)"
        )
    _raise_for_acceptance_criteria_lint(new_stories)

    # 7. Canonical-set uniqueness among regenerated stories.
    new_by_canon: dict[tuple[int, ...], list[Story]] = {}
    for s in new_stories:
        canon = tuple(sorted(s.steps))
        new_by_canon.setdefault(canon, []).append(s)
    for canon, group in new_by_canon.items():
        if len(group) > 1:
            raise JiraError(
                "companion regeneration: more than one regenerated story "
                f"covers step set {list(canon)} "
                f"({', '.join(s.id for s in group)})"
            )

    # 8. Every keyed matchable record must find exactly one regenerated
    #    match — a changed covered-step set never silently drops the key.
    for canon, group in matchable_by_canon.items():
        ticket = group[0]
        if ticket.jira_issue_key and canon not in new_by_canon:
            raise JiraError(
                f"companion regeneration: existing keyed ticket {ticket.id} "
                f"(jira: {ticket.jira_issue_key}) covered step set "
                f"{list(canon)}, which no regenerated story covers — "
                "resolve the mismatch through a session-directed edit before "
                "regenerating"
            )

    # 9. Attach state/key on a match and detect a changed created ticket.
    changed_created_tickets: list[CompanionCreatedTicketNotice] = []
    final_stories: list[Story] = []
    for s in new_stories:
        canon = tuple(sorted(s.steps))
        candidates = matchable_by_canon.get(canon, [])
        ticket = candidates[0] if candidates and candidates[0].jira_issue_key else None
        if ticket is None:
            final_stories.append(s)
            continue
        updated = replace(
            s, export_state=ticket.export_state, jira_issue_key=ticket.jira_issue_key
        )
        final_stories.append(updated)
        if ticket.export_state == _EXPORT_STATE_CREATED and (
            _companion_story_content_changed(ticket, updated)
        ):
            changed_created_tickets.append(
                CompanionCreatedTicketNotice(
                    story_id=updated.id, jira_issue_key=ticket.jira_issue_key
                )
            )

    # 10. Render through step 2's boundary, carrying provenance and status.
    detail_map = {
        ci.id: ci.detail.path
        for ci in capture.committed_steps
        if ci.detail.path is not None
    }
    step_status_map = {
        ci.id: plan.step_by_id(ci.id).status.value for ci in capture.committed_steps
    }
    render_input = _StoryRenderInput(
        plan_title=plan.title,
        epic=epic,
        new_stories=final_stories,
        frozen=list(dropped_history),
        detail_map=detail_map,
        plan_tag=settings.plan_tag,
        source_plan_path=current_plan_identity,
        step_status_map=step_status_map,
    )
    output = (
        _render_story_json(render_input)
        if settings.format == "json"
        else _render_story_markdown(render_input)
    )

    return CompanionStoryExport(
        output=output,
        stories=final_stories,
        dropped_history=dropped_history,
        changed_created_tickets=changed_created_tickets,
        created_to_dropped=created_to_dropped,
    )


# --------------------------------------------------------------------------
# Paired Jira publication
# --------------------------------------------------------------------------
#
# Captures, renders, stamps, and publishes the story and handoff as one pair.

def _paths_collide(a: Path, b: Path) -> bool:
    """True if two resolved paths name the same file, including on a
    case-insensitive filesystem (default macOS/Windows) where a case
    variant would otherwise silently bypass an exact-string comparison."""
    return a == b or str(a).casefold() == str(b).casefold()


def _is_within(path: Path, root: Path) -> bool:
    for candidate, base in (
        (path, root),
        (Path(str(path).casefold()), Path(str(root).casefold())),
    ):
        try:
            candidate.relative_to(base)
            return True
        except ValueError:
            continue
    return False


def _require_target_recognized_or_absent(
    path: Path,
    *,
    label: str,
    format: str,
    capture: CompanionExportInput,
    current_plan_identity: str,
    allow_legacy_adoption: bool = False,
) -> bool:
    """Return whether ``path`` is an adopted legacy story source.

    Reads and parses ``path`` live — there is nothing captured ahead of
    time to compare against here, this *is* the ownership check — via the
    format-appropriate reader from :mod:`plan_tool.jira_handoff`. Never
    guesses ownership from a filename or heading: an absent, unrecognized,
    foreign-plan, or alternate-pair target is the exact set this function
    distinguishes.
    """
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise JiraError(
            f"companion {label} target `{path}` exists but could not be "
            f"read to confirm ownership: {exc}"
        ) from exc
    markdown_reader = (
        read_markdown_story_provenance if label == "story" else read_markdown_provenance
    )
    provenance = read_json_provenance(text) if format == "json" else markdown_reader(text)
    alternate_provenance = (
        markdown_reader(text)
        if format == "json"
        else read_json_provenance(text)
    )
    if provenance is None:
        if alternate_provenance is not None:
            raise JiraError(
                f"companion {label} target `{path}` is a generated source "
                "with a different format or pair identity — choose a distinct "
                "destination"
            )
        if allow_legacy_adoption:
            return True
        raise JiraError(
            f"companion {label} target `{path}` already exists and is not "
            "a recognized companion-generated source — refusing to "
            "overwrite a human-owned or unrelated file; use --adopt-existing "
            "only to migrate the selected legacy story source"
        )
    same_pair = (
        provenance.pair_identity.story_path == capture.pair_identity.story_path
        and provenance.pair_identity.handoff_path == capture.pair_identity.handoff_path
        and provenance.pair_identity.format == capture.pair_identity.format
    )
    if (
        not _plan_identity_matches(provenance.source_plan_path, current_plan_identity)
        or not same_pair
    ):
        raise JiraError(
            f"companion {label} target `{path}` is bound by its provenance "
            "to a different plan or generated-source pair — refusing to "
            "take it over"
        )
    # A partial two-file publication intentionally regenerates the stale
    # pair on the next run, so a predecessor fingerprint is not a gate.
    return False


def _companion_target_preflight(
    capture: CompanionExportInput,
    *,
    story_output_path: Path,
    handoff_output_path: Path,
    repo_root: Path,
) -> None:
    """Reject an unsafe companion target before model invocation or either
    renderer runs.

    Complements the detail-artifact collision check
    ``capture_companion_export_input`` already enforced (raised before this
    function is ever reached) with the checks that need the *other* target
    for context (story/handoff collision), the plan's parent directory
    (bundle/authoring-lane placement), or a live read of a pre-existing
    target's provenance (same-plan complete-pair ownership). Paths are
    resolved before comparison so a spelling variant can't bypass a check.
    """
    story_resolved = story_output_path.resolve()
    handoff_resolved = handoff_output_path.resolve()
    plan_resolved = capture.plan_path.resolve()
    plan_details_root = (capture.plan_path.parent / "plan-details").resolve()

    if _paths_collide(story_resolved, handoff_resolved):
        raise JiraError(
            "companion target preflight: story and handoff destinations "
            f"both resolve to `{story_resolved}` — they must be distinct"
        )

    for label, resolved in (("story", story_resolved), ("handoff", handoff_resolved)):
        if _paths_collide(resolved, plan_resolved):
            raise JiraError(
                f"companion {label} target `{resolved}` collides with the "
                "plan source file — choose a different destination"
            )
        if _is_within(resolved, plan_details_root):
            if label == "handoff":
                raise JiraError(
                    f"companion handoff target `{resolved}` may not be "
                    "published inside any plan's detail bundle "
                    f"(`{plan_details_root}`) — choose a destination "
                    "outside it"
                )
    current_plan_identity = _repo_relative_posix(capture.plan_path, repo_root)
    story_is_legacy = _require_target_recognized_or_absent(
        story_output_path,
        label="story",
        format=capture.settings.format,
        capture=capture,
        current_plan_identity=current_plan_identity,
        allow_legacy_adoption=capture.adopt_existing,
    )
    _require_target_recognized_or_absent(
        handoff_output_path,
        label="handoff",
        format="markdown",
        capture=capture,
        current_plan_identity=current_plan_identity,
    )
    if capture.adopt_existing and not story_is_legacy:
        raise JiraError(
            "--adopt-existing requires the selected readable legacy story "
            "source; omit it for a fresh or already paired export"
        )


# --- Handoff render-input translation ---------------------------------------
#
# CompanionExportInput's captured shapes (jira.py-private) mirror
# jira_handoff's render-input shapes field-for-field by design (step 4's
# "no reverse import" boundary), but they're distinct dataclasses — this
# translates one to the other without either module importing the other's
# internals.


def _handoff_detail_render_input(detail: _StepDetailInput) -> DetailRenderInput:
    if detail.state == _DETAIL_STATE_PRESENT:
        return DetailRenderInput(
            state=_HANDOFF_DETAIL_STATE_PRESENT, path=detail.path, text=detail.text
        )
    return DetailRenderInput(state=_HANDOFF_DETAIL_STATE_MISSING)


def _handoff_file_excerpt_render_input(
    fc: _FileExcerptCapture,
) -> FileExcerptRenderInput:
    if fc.state == "excerpt":
        excerpt = fc.excerpt
        assert excerpt is not None  # state == "excerpt" always carries one
        return FileExcerptRenderInput(
            path=fc.path,
            state=_HANDOFF_FILE_EXCERPT_STATE_EXCERPT,
            excerpt_text=excerpt.text,
            excerpt_kind=excerpt.excerpt_kind,
            fallback_reason=excerpt.fallback_reason,
            truncated=excerpt.truncated,
        )
    if fc.state == "missing":
        return FileExcerptRenderInput(
            path=fc.path, state=_HANDOFF_FILE_EXCERPT_STATE_MISSING
        )
    return FileExcerptRenderInput(
        path=fc.path, state=_HANDOFF_FILE_EXCERPT_STATE_UNREADABLE, error=fc.error
    )


def _handoff_committed_step_render_input(
    ci: _CommittedStepInput,
) -> CommittedStepRenderInput:
    return CommittedStepRenderInput(
        id=ci.id,
        detail=_handoff_detail_render_input(ci.detail),
        file_excerpts=tuple(
            _handoff_file_excerpt_render_input(fc) for fc in ci.file_excerpts
        ),
    )


def _handoff_parked_step_render_input(p: _ParkedStepHistory) -> ParkedStepRenderInput:
    return ParkedStepRenderInput(
        id=p.id, title=p.title, scope=p.scope.value, status_note=p.status_note
    )


def _build_handoff_render_input(
    capture: CompanionExportInput, *, repo_root: Path
) -> HandoffRenderInput:
    return HandoffRenderInput(
        plan=capture.plan,
        body_text=capture.body_text,
        grade="run",
        source_plan_path=_repo_relative_posix(capture.plan_path, repo_root),
        committed_steps=tuple(
            _handoff_committed_step_render_input(ci) for ci in capture.committed_steps
        ),
        parked_step_history=tuple(
            _handoff_parked_step_render_input(p) for p in capture.parked_step_history
        ),
        pair_identity=capture.pair_identity,
        companion_settings=HandoffCompanionRenderSettings(
            epic_key=capture.settings.epic.key,
            epic_name=capture.settings.epic.name,
            epic_jira_id=capture.settings.epic.jira_epic_id,
            epic_description=capture.settings.epic.description,
            plan_tag=capture.settings.plan_tag,
            max_hours=capture.settings.max_hours,
            start_number=capture.settings.start_number,
            story_prompt_contract_revision=(
                capture.settings.story_prompt_contract_revision
            ),
            handoff_format_contract_revision=(
                capture.settings.handoff_format_contract_revision
            ),
        ),
    )


def _carried_story_record_render_input(
    ticket: _FrozenTicket,
) -> CarriedStoryRecordRenderInput:
    if ticket.raw_markdown is not None:
        rendered = ticket.raw_markdown
    elif ticket.raw_json is not None:
        rendered = json.dumps(ticket.raw_json, sort_keys=True)
    else:
        rendered = ""
    return CarriedStoryRecordRenderInput(
        id=ticket.id,
        steps=tuple(ticket.steps),
        export_state=ticket.export_state,
        jira_issue_key=ticket.jira_issue_key,
        rendered_content=rendered,
    )


def _decorate_story_with_provenance(
    output: str, provenance: CompanionProvenance, *, format: str
) -> str:
    """Embed ``provenance`` onto an already-rendered paired story source.

    The story renderer (:func:`_render_story_markdown` /
    :func:`_render_story_json`) has no concept of companion provenance, so
    this decorates its output afterward instead of teaching it a
    paired-publication branch. Markdown appends one HTML-comment block after
    the generated story source; JSON merges in the one top-level
    provenance key.
    """
    if format == "json":
        payload = json.loads(output)
        payload.update(write_json_provenance(provenance))
        return json.dumps(payload, indent=2)
    block = write_markdown_provenance(provenance)
    return output.rstrip("\n") + "\n\n" + block + "\n"


# --- Staged two-target publication ------------------------------------------


@dataclass(frozen=True)
class _StagedCompanionOutput:
    label: str
    final_path: Path
    tmp_path: Path


def _stage_companion_output(
    label: str, path: Path, text: str
) -> _StagedCompanionOutput:
    # Deliberately not fileio.atomic_write_text: that combines the
    # temp-file write and os.replace in one call, with no seam to write
    # BOTH targets' temp files and re-confirm BOTH are still unchanged
    # before EITHER commits — the two-phase stage/replace split
    # _publish_companion_pair's paired-publication guarantee requires.
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JiraError(
            f"could not stage companion {label} output at {path}: {exc}"
        ) from exc
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.companion.tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise JiraError(
            f"could not stage companion {label} output at {path}: {exc}"
        ) from exc
    return _StagedCompanionOutput(label=label, final_path=path, tmp_path=tmp_path)


def _cleanup_staged_outputs(staged: list[_StagedCompanionOutput]) -> None:
    for s in staged:
        try:
            s.tmp_path.unlink()
        except OSError:
            pass


def _confirm_target_unchanged(
    path: Path, *, captured: _TargetContentProof, repo_root: Path, label: str
) -> None:
    """Re-derive ``path``'s content-state proof and compare to ``captured``.

    Catches any edit since ``capture_companion_export_input`` — including
    one outside parsed ticket/provenance fields, which re-parsing alone
    would miss — by comparing raw existence/digest rather than meaning.
    """
    fresh = _capture_target_content_proof(path, repo_root)
    if fresh.exists != captured.exists or fresh.sha256 != captured.sha256:
        raise JiraError(
            f"companion publication aborted: {label} target `{path}` "
            "changed after capture — rerun companion export to "
            "regenerate both sources from current inputs"
        )


def _replace_staged_output(staged: _StagedCompanionOutput) -> None:
    try:
        os.replace(staged.tmp_path, staged.final_path)
    except OSError as exc:
        raise JiraError(
            f"failed to publish companion {staged.label} output to "
            f"{staged.final_path}: {exc}"
        ) from exc


def _publish_companion_pair(
    *,
    story_path: Path,
    story_text: str,
    handoff_path: Path,
    handoff_text: str,
    capture: CompanionExportInput,
    repo_root: Path,
) -> None:
    """Stage both outputs, confirm both targets are unchanged, then replace.

    Both temporary files are written before either target's ownership is
    reconfirmed, and both confirmations run before either replacement
    begins — a target that changed since capture aborts every replacement
    not yet started. Never claims atomic two-file publication: once a
    replacement begins it either lands or raises, and staged files are
    always cleaned up regardless of outcome.
    """
    staged: list[_StagedCompanionOutput] = []
    try:
        staged.append(_stage_companion_output("story", story_path, story_text))
        staged.append(_stage_companion_output("handoff", handoff_path, handoff_text))

        _confirm_target_unchanged(
            story_path,
            captured=capture.target_preflight.story_target,
            repo_root=repo_root,
            label="story",
        )
        _confirm_target_unchanged(
            handoff_path,
            captured=capture.target_preflight.handoff_target,
            repo_root=repo_root,
            label="handoff",
        )

        for index, s in enumerate(staged):
            try:
                _replace_staged_output(s)
            except JiraError as exc:
                if index:
                    published = ", ".join(previous.label for previous in staged[:index])
                    raise JiraError(
                        f"{exc}; companion {published} output may already be "
                        "updated while its sibling remains stale — rerun companion "
                        "export to regenerate both sources from current inputs"
                    ) from exc
                raise
    finally:
        _cleanup_staged_outputs(staged)


# --- Orchestration -----------------------------------------------------------


@dataclass(frozen=True)
class JiraRenderResult:
    """The validated, unwritten paired Jira artifacts from one snapshot."""

    capture: CompanionExportInput
    story_export: CompanionStoryExport
    handoff_render_input: HandoffRenderInput
    handoff_body: str


@spawn_cwd_from_repo_root
def render_jira_export(
    plan_path: Path,
    *,
    repo_root: Path,
    epic: Epic,
    story_output_path: Path,
    handoff_output_path: Path,
    format: str = "markdown",
    max_hours: int = 8,
    plan_tag: str = "",
    adopt_existing: bool = False,
    invoker: JiraInvoker = shell_jira_invoker,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
) -> JiraRenderResult:
    """Capture, validate, invoke once, and render an unwritten paired export.

    The publication path and ``jira --no-write`` share this sequence so each
    validates the same handoff contract and keeps an injectable backend boundary.
    """
    capture = capture_companion_export_input(
        plan_path,
        repo_root=repo_root,
        epic=epic,
        story_output_path=story_output_path,
        handoff_output_path=handoff_output_path,
        format=format,
        max_hours=max_hours,
        plan_tag=plan_tag,
        adopt_existing=adopt_existing,
        max_file_bytes=max_file_bytes,
    )
    _companion_target_preflight(
        capture,
        story_output_path=story_output_path,
        handoff_output_path=handoff_output_path,
        repo_root=repo_root,
    )
    handoff_render_input = _build_handoff_render_input(capture, repo_root=repo_root)
    try:
        handoff_body = render_handoff_body(handoff_render_input)
    except HandoffRenderError as exc:
        raise JiraError(f"companion handoff cannot be rendered: {exc}") from exc
    # Here, not only in export_jira: this docstring's "the publication path
    # and `jira --no-write` share this sequence" promise means `--no-write`
    # (which calls this function directly and never reaches export_jira's
    # own copy of this check) must validate the same handoff contract too,
    # or it silently prints a fence-truncated handoff instead of rejecting it.
    _reject_unmatched_handoff_fence(
        plan_path=capture.plan_path, body_text=handoff_render_input.body_text
    )
    prompt = render_companion_export_prompt(capture, max_file_bytes=max_file_bytes)
    raw_response = invoker(prompt)
    story_export = regenerate_companion_stories(
        capture, raw_response, repo_root=repo_root
    )
    # Emitted here, not in export_jira, so `jira --no-write` sees the same
    # advisory warnings a real write would -- the docstring above's "each
    # validates the same handoff contract" guarantee applies to warnings
    # too, not just hard validation.
    _emit_story_warnings(
        story_export.stories,
        repo_root,
        created_paths=_plan_created_paths(capture.plan),
    )
    return JiraRenderResult(
        capture=capture,
        story_export=story_export,
        handoff_render_input=handoff_render_input,
        handoff_body=handoff_body,
    )


@dataclass(frozen=True)
class JiraPublicationResult:
    """Outcome of one successful paired ``export_jira`` run.

    ``stories``, ``dropped_history``, ``changed_created_tickets``, and
    ``created_to_dropped`` are step 3's regeneration metadata, passed
    through unchanged — see :class:`CompanionStoryExport`.
    """

    story_path: Path
    handoff_path: Path
    story_output: str
    handoff_output: str
    stories: list[Story]
    dropped_history: list[_FrozenTicket]
    changed_created_tickets: list[CompanionCreatedTicketNotice]
    created_to_dropped: list[CompanionCreatedTicketNotice]


@spawn_cwd_from_repo_root
def export_jira(
    plan_path: Path,
    *,
    repo_root: Path,
    epic: Epic,
    story_output_path: Path,
    handoff_output_path: Path,
    format: str = "markdown",
    max_hours: int = 8,
    plan_tag: str = "",
    adopt_existing: bool = False,
    invoker: JiraInvoker = shell_jira_invoker,
    max_file_bytes: int = _MAX_PROMPT_FILE_BYTES,
) -> JiraPublicationResult:
    """Capture, preflight, invoke once, render, and publish both sources
    from one snapshot.

    Raises ``JiraError`` before any
    write when capture fails (see :func:`capture_companion_export_input`),
    when target preflight rejects a destination (see
    :func:`_companion_target_preflight`), when the model response cannot be
    parsed or key ownership cannot be proven (see
    :func:`regenerate_companion_stories`), or when a target changed since
    capture or a final replacement fails (see
    :func:`_publish_companion_pair`). The CLI owns flags, destination
    derivation, and operator-facing output; this function captures, invokes,
    and publishes.
    """
    rendered = render_jira_export(
        plan_path,
        repo_root=repo_root,
        epic=epic,
        story_output_path=story_output_path,
        handoff_output_path=handoff_output_path,
        format=format,
        max_hours=max_hours,
        plan_tag=plan_tag,
        adopt_existing=adopt_existing,
        invoker=invoker,
        max_file_bytes=max_file_bytes,
    )
    capture = rendered.capture
    story_export = rendered.story_export
    handoff_render_input = rendered.handoff_render_input
    existing = capture.existing_story_source.existing
    existing_records = tuple(
        _carried_story_record_render_input(t)
        for t in (existing.tickets if existing is not None else [])
    )
    provenance = build_companion_provenance(
        handoff_render_input,
        existing_story_records=existing_records,
    )
    try:
        handoff_text = render_handoff(
            handoff_render_input, provenance, body=rendered.handoff_body
        )
    except HandoffRenderError as exc:
        raise JiraError(f"companion handoff cannot be rendered: {exc}") from exc
    story_text = _decorate_story_with_provenance(
        story_export.output, provenance, format=capture.settings.format
    )

    # Already validated inside render_jira_export (above), against the same
    # capture.plan_path / handoff_render_input.body_text — no need to repeat.
    _publish_companion_pair(
        story_path=story_output_path,
        story_text=story_text,
        handoff_path=handoff_output_path,
        handoff_text=handoff_text,
        capture=capture,
        repo_root=repo_root,
    )

    return JiraPublicationResult(
        story_path=story_output_path,
        handoff_path=handoff_output_path,
        story_output=story_text,
        handoff_output=handoff_text,
        stories=story_export.stories,
        dropped_history=story_export.dropped_history,
        changed_created_tickets=story_export.changed_created_tickets,
        created_to_dropped=story_export.created_to_dropped,
    )
