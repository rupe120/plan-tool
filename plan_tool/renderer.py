"""Render prompt templates for plan-tool steps.

Templates are packaged under `plan_tool/prompts/` as plain markdown, so they
ship with the installed wheel. Placeholders use `${name}` syntax (stdlib
`string.Template`) so markdown curly braces pass through untouched.

Template variables (passed as a dict to `render`):
    plan_title, plan_status, plan_priority
    step_id, step_title, step_index, step_total, step_files, step_detail
    done_count, lessons_section, scope_fence_block
"""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Optional

from plan_tool.detail_artifacts import (
    DetailFormatError,
    require_supported_detail_format_version,
    resolve_detail_artifact,
)
from plan_tool.scope_fence import _fenced_code_spans, _strip_frontmatter, render_scope_fence
from plan_tool.schema import Plan, Step
from plan_tool.response_contract import (
    APPLY_BASIC_VERDICT_RESPONSE_CONTRACT,
    FINDINGS_RESPONSE_CONTRACT,
)


_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Lead-in for the scope-fence block, held here rather than in the templates so
# it disappears with the block. It has to name the *source*, not just claim
# authority: the fence's own headings sit at the same level as the template's
# ``## Files in scope`` / ``## What to do``. Pinned by test —
# it is the only prose the run lane mints for the fence.
_SCOPE_FENCE_LEAD_IN = (
    "**Scope fence (authoritative, from the plan).** These sections state "
    "what the whole plan is for, what this step is for, and what the plan "
    "will not build. They bind this step. Do not widen past them."
)

class DetailGradeError(Exception):
    """A detail artifact or plan fence cannot be rendered safely."""


def _reject_unmatched_plan_fence(plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    if _fenced_code_spans(_strip_frontmatter(text)).unmatched_opening is not None:
        raise DetailGradeError(
            f"{plan_path}: unmatched opening code fence; add a matching closing fence "
            "before rendering this run prompt."
        )


def prompts_dir() -> Path:
    """Return the directory where prompt templates live."""
    return _PROMPTS_DIR


def render_prompt(
    plan: Plan,
    step: Step,
    *,
    repo_root: Path,
    mode: str = "run",
    extra_vars: Optional[dict[str, str]] = None,
    collect_blocks: Optional[list[tuple[str, int]]] = None,
    plan_path: Optional[Path] = None,
) -> str:
    """Render the prompt for a single step execution.

    Loads `prompts/<mode>.md`, substitutes plan + step variables, returns the
    rendered string. Raises FileNotFoundError if the template doesn't exist.

    ``extra_vars`` (when provided) merges into the substitution map AFTER
    the standard variables, so callers can override or supplement the
    template inputs without editing the renderer. The deep-verify
    pipeline uses this to inject ``acceptance_bullet`` into the
    ``reconcile-deep`` prompt.

    ``collect_blocks`` (when a list is passed) receives ``(name, bytes)`` pairs
    for the dominant content blocks, measured from the strings this render
    already built — so the prompt-budget advisory sizes its breakdown without a
    second file read. Purely additive: ``None`` leaves behavior unchanged.
    """
    if plan_path is not None and mode == "run":
        _reject_unmatched_plan_fence(plan_path)

    template_path = _PROMPTS_DIR / f"{mode}.md"
    if not template_path.is_file():
        raise FileNotFoundError(
            f"no prompt template for mode '{mode}' at {template_path}"
        )

    template = Template(template_path.read_text(encoding="utf-8"))

    variables = _build_variables(
        plan,
        step,
        repo_root=repo_root,
        collect_blocks=collect_blocks,
        plan_path=plan_path,
    )
    if extra_vars:
        variables.update(extra_vars)
    return template.safe_substitute(variables)


def _build_variables(
    plan: Plan,
    step: Step,
    *,
    repo_root: Path,
    collect_blocks: Optional[list[tuple[str, int]]] = None,
    plan_path: Optional[Path] = None,
) -> dict[str, str]:
    done_count = plan.done_count
    try:
        step_index = [s.id for s in plan.steps].index(step.id) + 1
    except ValueError:
        step_index = 0
    step_total = len(plan.steps)

    if step.files or step.creates:
        file_lines = [f"- `{f}`" for f in step.files]
        file_lines += [f"- `{f}` (new — created by this step)" for f in step.creates]
        step_files = "\n".join(file_lines)
    else:
        step_files = "(no files declared for this step)"

    step_detail = _load_detail(
        step, repo_root=repo_root, plan=plan, plan_path=plan_path
    )

    lessons_section = _load_lessons_section(plan, repo_root=repo_root)
    # Per-step, never cached on the plan: the fence carries this step's own
    # ``intent``, so one block reused across steps would put step 1's intent
    # in every step's prompt.
    scope_fence_block = _scope_fence_section(plan, step, plan_path=plan_path)

    if collect_blocks is not None:
        # Reuse the just-built strings — no second detail/lessons/fence read.
        collect_blocks.append(("step detail", len(step_detail.encode("utf-8"))))
        collect_blocks.append(("lessons", len(lessons_section.encode("utf-8"))))
        collect_blocks.append(
            ("scope fence", len(scope_fence_block.encode("utf-8")))
        )

    return {
        "plan_title": plan.title,
        "plan_status": plan.status.value,
        "plan_priority": plan.priority.value,
        "step_id": str(step.id),
        "step_title": step.title,
        "step_index": str(step_index),
        "step_total": str(step_total),
        "step_files": step_files,
        "step_detail": step_detail,
        "done_count": str(done_count),
        "lessons_section": lessons_section,
        "scope_fence_block": scope_fence_block,
        "findings_response_format_block": (
            FINDINGS_RESPONSE_CONTRACT.render_prompt_block(
                response_label="response"
            )
        ),
        "verdict_response_format_block": (
            APPLY_BASIC_VERDICT_RESPONSE_CONTRACT.render_prompt_block()
        ),
    }


def _display_path(path: Path, repo_root: Path) -> str:
    """``path`` relative to the repo root when it sits inside it, else as-is."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _load_detail(
    step: Step,
    *,
    repo_root: Path,
    plan: Optional[Plan] = None,
    plan_path: Optional[Path] = None,
) -> str:
    """The run-grade detail body for ``step``, or prose explaining its absence.

    Pointer first, canonical second — the same rule the quality checks and
    :func:`plan_tool.review.render_review_prompt` follow, so the executor
    reads the body the audit judged. A **set** pointer stays authoritative and
    never falls back, which keeps ``check_detail_coverage``'s
    ``missing_on_disk`` diagnostic meaningful. ``plan_path=None`` means no
    canonical resolution is possible, which is the pointer-only behavior.
    """
    if step.detail:
        detail_path = repo_root / step.detail
        if not detail_path.is_file():
            return (
                f"_Detail file declared at `{step.detail}` but not found on "
                f"disk. Proceed using the step title and files list._"
            )
        text = detail_path.read_text(encoding="utf-8")
        try:
            require_supported_detail_format_version(text, path=detail_path)
        except DetailFormatError as exc:
            raise DetailGradeError(f"step {step.id} ({step.title}): {exc}") from exc
        return text

    if plan is not None and plan_path is not None:
        resolution = resolve_detail_artifact(plan_path, plan, step, repo_root)
        if resolution.on_disk:
            text = resolution.path.read_text(encoding="utf-8")
            try:
                require_supported_detail_format_version(text, path=resolution.path)
            except DetailFormatError as exc:
                raise DetailGradeError(
                    f"step {step.id} ({step.title}): {exc}"
                ) from exc
            return text

    return (
        "_No detail file for this step. Use the step title and files list "
        "above as the scope._"
    )


def _scope_fence_section(
    plan: Plan, step: Step, *, plan_path: Optional[Path]
) -> str:
    """The plan's scope fence wrapped for the prompt, or ``""``.

    Same shape as :func:`_load_lessons_section` — heading prose in Python,
    leading and trailing newline on the value — because the two run templates
    spend an existing blank line on the slot. An empty fence therefore renders
    the blank line back and the prompt stays byte-identical to a fence-free
    render, by construction rather than by coincidence.

    ``plan_path=None`` renders nothing: the guardrail half can't be read
    without a path, and every ``render_prompt`` caller that omits one renders
    a template with no ``${scope_fence_block}`` slot.

    Unwraps the two ``Optional[str]`` intents here — the leaf takes plain
    strings so it can stay stdlib-only.
    """
    if plan_path is None:
        return ""
    fence = render_scope_fence(
        plan_path,
        plan_intent=plan.intent or "",
        step_intent=step.intent or "",
    )
    if not fence:
        return ""
    return f"\n{_SCOPE_FENCE_LEAD_IN}\n\n{fence}\n"


def _load_lessons_section(plan: Plan, *, repo_root: Path) -> str:
    if plan.lessons is None:
        return ""
    lessons_path = repo_root / plan.lessons
    if not lessons_path.is_file():
        return ""
    body = lessons_path.read_text(encoding="utf-8").strip()
    if not body:
        return ""
    return f"\n## Lessons from earlier steps\n\n{body}\n"
