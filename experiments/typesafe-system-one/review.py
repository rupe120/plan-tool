"""Interactive terminal reviewer for the typesafe-system-one blind label sheets.

One generic stepper over any of the three sheets ``label.py`` exports —
paginating the CSV's raw columns (t1) or the full finding + diff text from the
companion ``.todo.md`` (t2_audit / t2_residue) — instead of reading a wide CSV.

    python3 experiments/typesafe-system-one/review.py t1
    python3 experiments/typesafe-system-one/review.py t2_audit
    python3 experiments/typesafe-system-one/review.py t2_residue

Saves after every labeled item to ``labels/<task>.csv`` (same columns the
``.todo.csv`` has, so ``label.py import`` reads it unchanged) and resumes from
there next time. Stdlib only.
"""
import csv
import re
import shutil
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = HERE / "labels"

CSI_GREEN, CSI_RED, CSI_CYAN, CSI_BOLD, CSI_DIM, CSI_RESET = (
    "\x1b[32m", "\x1b[31m", "\x1b[36m", "\x1b[1m", "\x1b[2m", "\x1b[0m")
TTY = sys.stdout.isatty()


def color(s: str, c: str) -> str:
    return f"{c}{s}{CSI_RESET}" if TTY else s


def width() -> int:
    return min(shutil.get_terminal_size(fallback=(100, 24)).columns - 2, 100)


def wrap(text: str) -> str:
    """Wrap prose paragraph-by-paragraph, preserving blank lines between them."""
    w = width()
    return "\n\n".join(textwrap.fill(p, w) if p.strip() else "" for p in text.split("\n\n"))


def render_diff(diff: str) -> str:
    if diff.strip() == "(empty)":
        return color("(no prior edit)", CSI_DIM)
    lines = []
    for ln in diff.splitlines():
        if ln.startswith("+++") or ln.startswith("---"):
            lines.append(color(ln, CSI_BOLD))
        elif ln.startswith("+"):
            lines.append(color(ln, CSI_GREEN))
        elif ln.startswith("-"):
            lines.append(color(ln, CSI_RED))
        elif ln.startswith("@@"):
            lines.append(color(ln, CSI_CYAN))
        else:
            lines.append(ln)
    return "\n".join(lines)


# ---- per-task shape --------------------------------------------------------

@dataclass
class Task:
    todo_csv: str
    md: str | None
    options: tuple[str, ...]
    question: str
    columns: tuple[str, ...]  # written back out, same shape label.py's import expects


TASKS: dict[str, Task] = {
    "t1": Task(
        todo_csv="t1.todo.csv", md=None,
        options=("code-logic", "unit-test", "docs", "unknown"),
        question="Which domain does this finding's required fix belong to?",
        columns=("item_id", "split", "source", "title", "body", "suggested_action", "cited_step", "label", "note"),
    ),
    "t2_audit": Task(
        todo_csv="t2_audit.todo.csv", md="t2_audit.todo.md", options=("yes", "no"),
        question="Did the prior edit introduce the problem this finding describes?",
        columns=("n", "item_id", "title", "label", "note"),
    ),
    "t2_residue": Task(
        todo_csv="t2_residue.todo.csv", md="t2_residue.todo.md", options=("yes", "no"),
        question="Did the prior edit introduce the problem this finding describes?",
        columns=("n", "item_id", "title", "label", "note"),
    ),
}

MD_HEADER_RE = re.compile(r"^## \d+\. `([^`]+)`\s*$", re.MULTILINE)


def parse_md(path: Path) -> dict[str, dict]:
    """item_id -> {step, finding_source, finding_severity, finding_title, body, suggested_action, prior_edit}."""
    text = path.read_text()
    heads = list(MD_HEADER_RE.finditer(text))
    out = {}
    for h, nxt in zip(heads, heads[1:] + [None]):
        block = text[h.end():nxt.start() if nxt else len(text)]
        item_id = h.group(1)
        try:
            step = block.split("**Cited step:** ", 1)[1].split("\n\n**Finding (", 1)[0].strip()
            rest = block.split("**Finding (", 1)[1]
            head_meta, rest = rest.split("):** ", 1)
            source, severity = [x.strip() for x in head_meta.split(",", 1)]
            title, rest = rest.split("\n\n", 1)
            body, rest = rest.split("\n\n**Suggested action:** ", 1)
            action, rest = rest.split("\n\n**Prior edit:**\n\n````diff\n", 1)
            diff = rest.rsplit("\n````", 1)[0]
        except (IndexError, ValueError):
            out[item_id] = {"step": "(parse error)", "finding_source": "", "finding_severity": "",
                             "finding_title": "(see raw block below)", "body": block.strip(),
                             "suggested_action": "", "prior_edit": ""}
            continue
        out[item_id] = {"step": step, "finding_source": source, "finding_severity": severity,
                         "finding_title": title.strip(), "body": body.strip(),
                         "suggested_action": action.strip(), "prior_edit": diff}
    return out


# ---- load / save ------------------------------------------------------------

def load_rows(task: Task) -> list[dict]:
    rows = list(csv.DictReader((LABELS / task.todo_csv).open(newline="")))
    if task.md:
        parsed = parse_md(LABELS / task.md)
        for r in rows:
            r.update(parsed.get(r["item_id"], {}))
    out_path = LABELS / f"{task.todo_csv.replace('.todo', '')}"
    if out_path.exists():
        existing = {r["item_id"]: r for r in csv.DictReader(out_path.open(newline=""))}
        for r in rows:
            e = existing.get(r["item_id"])
            if e:
                r["label"], r["note"] = e.get("label", ""), e.get("note", "")
    return rows


def save_rows(task: Task, rows: list[dict]) -> Path:
    out_path = LABELS / f"{task.todo_csv.replace('.todo', '')}"
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=task.columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return out_path


# ---- rendering --------------------------------------------------------------

def render(task_name: str, task: Task, rows: list[dict], idx: int) -> None:
    if TTY:
        print("\x1b[2J\x1b[H", end="")
    r = rows[idx]
    labeled = sum(1 for x in rows if x["label"])
    print(color(f"{task_name}  —  item {idx + 1}/{len(rows)}  ({labeled} labeled)", CSI_BOLD))
    print(color(r["item_id"], CSI_DIM))
    print()
    if task.md:
        print(color(f"Cited step: {r['step']}", CSI_BOLD))
        print()
        print(color(f"Finding ({r['finding_source']}, {r['finding_severity']}): {r['finding_title']}", CSI_BOLD))
        print(wrap(r["body"]))
        print()
        print(color("Suggested action:", CSI_BOLD))
        print(wrap(r["suggested_action"] or "(none)"))
        print()
        print(color("Prior edit:", CSI_BOLD))
        print(render_diff(r["prior_edit"]))
    else:
        print(color(f"Source: {r['source']}   Split: {r['split']}", CSI_DIM))
        print(color(f"Cited step: {r['cited_step']}", CSI_BOLD))
        print()
        print(color("Title:", CSI_BOLD))
        print(wrap(r["title"]))
        print()
        print(color("Body:", CSI_BOLD))
        print(wrap(r["body"]))
        print()
        print(color("Suggested action:", CSI_BOLD))
        print(wrap(r["suggested_action"] or "(none)"))
    print()
    if r["label"]:
        print(color(f"Current label: {r['label']}", CSI_CYAN) + (f"   note: {r['note']}" if r.get("note") else ""))
    print()
    print(task.question)
    opts = "  ".join(f"[{i + 1}] {o}" for i, o in enumerate(task.options))
    print(opts)
    print(color("(s)kip  (b)ack  (n)ote  (j)ump  (q)uit  (h)elp", CSI_DIM))


HELP = """
Commands:
  1-9        pick an option by number
  <word>     type an option name directly (e.g. "docs", "yes")
  s          skip this item, move to the next
  b          go back one item
  n          add or edit a note on this item
  j          jump to an item number
  q          save and quit
  h / ?      this help
Labeling an item autosaves immediately and advances to the next item.
"""


def prompt(task: Task) -> str:
    return input("> ").strip()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in TASKS:
        sys.exit(f"usage: python3 {Path(__file__).name} <{'|'.join(TASKS)}>")
    name = sys.argv[1]
    task = TASKS[name]
    rows = load_rows(task)
    idx = next((i for i, r in enumerate(rows) if not r["label"]), 0)

    while True:
        render(name, task, rows, idx)
        cmd = prompt(task)
        low = cmd.lower()
        if low in ("q", "quit"):
            break
        if low in ("h", "?", "help"):
            print(HELP)
            input(color("(press Enter to continue)", CSI_DIM))
            continue
        if low in ("s", "skip", ""):
            idx = min(idx + 1, len(rows) - 1)
            continue
        if low in ("b", "back"):
            idx = max(idx - 1, 0)
            continue
        if low in ("j", "jump"):
            n = input(f"jump to item # (1-{len(rows)}): ").strip()
            if n.isdigit() and 1 <= int(n) <= len(rows):
                idx = int(n) - 1
            continue
        if low in ("n", "note"):
            rows[idx]["note"] = input("note: ").strip()
            save_rows(task, rows)
            continue
        choice = None
        if cmd.isdigit() and 1 <= int(cmd) <= len(task.options):
            choice = task.options[int(cmd) - 1]
        elif low in task.options:
            choice = low
        if choice is None:
            print(color(f"unrecognized: {cmd!r} — press h for help", CSI_RED))
            input()
            continue
        rows[idx]["label"] = choice
        save_rows(task, rows)
        nxt = next((i for i in range(idx + 1, len(rows)) if not rows[i]["label"]), None)
        idx = nxt if nxt is not None else min(idx + 1, len(rows) - 1)

    out_path = save_rows(task, rows)
    labeled = sum(1 for r in rows if r["label"])
    print(f"\nsaved {out_path}  ({labeled}/{len(rows)} labeled)")
    print(dict(Counter(r["label"] for r in rows if r["label"])))
    if labeled < len(rows):
        print(f"{len(rows) - labeled} item(s) still unlabeled — re-run to resume.")


if __name__ == "__main__":
    main()
