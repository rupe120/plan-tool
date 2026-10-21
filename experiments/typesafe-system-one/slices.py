"""State slices shared by run_jev.py, run_claude.py, and label.py. Stdlib only.

One definition of what each system (and each labeler) sees, so the model,
the baselines, and the owner judge identical state (DESIGN.md § Baselines).
"""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SIBLING = REPO.parent / "plan-tool-2"
ITEMS = REPO / ".tmp" / "typesafe-system-one" / "items"
DIFF_CAP = 8000


def load_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (ITEMS / name).open()]


def prior_commits(all_items: list[dict]) -> dict:
    """item_id -> plan commit of the previous report (with findings) of the same plan.

    Part 1 items carry no ``prev_commit``; T2 items do, from the full report
    sequence, and :func:`prior_edit` prefers it.
    """
    by_slug: dict = {}
    for it in all_items:
        by_slug.setdefault(it["plan_slug"], set()).add((it["created_at"], it["plan_commit"]))
    out = {}
    for it in all_items:
        earlier = sorted(x for x in by_slug[it["plan_slug"]] if x[0] < it["created_at"])
        out[it["item_id"]] = earlier[-1][1] if earlier else None
    return out


def prior_edit(it: dict, prev: str | None = None) -> str:
    """Plan + cited-step detail diff between the previous audit and this one."""
    prev = it.get("prev_commit") or prev
    cur = it["plan_commit"]
    if not prev or not cur or prev == cur:
        return ""
    slug, sid = it["plan_slug"], it["cited_step_id"]
    specs = [f":(glob)docs/implementation-plans/*{slug}.md"]
    if sid is not None:
        specs.append(f":(glob)docs/implementation-plans/plan-details/{slug}/{int(sid):02d}-*.md")
    for repo in (REPO, SIBLING):
        r = subprocess.run(["git", "diff", "--unified=2", prev, cur, "--", *specs],
                           cwd=repo, capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout[:DIFF_CAP]
    return ""


def state_for(it: dict, size: str, edit: str) -> dict:
    s = {"finding": it["finding"]}
    if size in ("step", "plan"):
        s["cited_step"] = it["step"]
        s["prior_edit"] = edit
    if size == "plan":
        s["plan"] = it["plan"]["text"]
    return s


# ---- per-task item sets, states, and truth (DESIGN.md § Part 2) -------------

def t1_items() -> list[dict]:
    return load_jsonl("t1.jsonl")


def t2_items() -> list[dict]:
    return load_jsonl("t2.jsonl") + load_jsonl("t2_residue.jsonl")


def t1_state(it: dict) -> dict:
    return {"finding": it["finding"], "cited_step": it["step"]}


def t2_state(it: dict) -> dict:
    return {"finding": it["finding"], "cited_step": it["step"], "prior_edit": prior_edit(it)}


def t2_truth(it: dict) -> bool | None:
    """Mechanical `git blame` label; None for residue items (owner-labeled)."""
    return (it.get("t2_mech") or {}).get("label")


def t3_items() -> list[dict]:
    return load_jsonl("t3.jsonl")


def t3_state(it: dict) -> dict:
    return {"step": it["step"], "detail": it["detail"]}
