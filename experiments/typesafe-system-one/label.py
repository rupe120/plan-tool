"""Blind labeling export/import for typesafe-system-one. Stdlib only.

    python3 experiments/typesafe-system-one/label.py export t1
    python3 experiments/typesafe-system-one/label.py import t1
    python3 experiments/typesafe-system-one/label.py export t2   # noise audit + residue
    python3 experiments/typesafe-system-one/label.py import t2

Export writes ``labels/<set>.todo.csv`` with no model output, no B-code label,
and no mechanical label (DESIGN.md § "Integrity rules" 2). The owner fills the
``label`` column and saves the file as ``labels/<set>.csv``; import validates
it against the item set. T2 sheets carry a companion ``.todo.md`` with each
item's full finding and ``prior_edit`` diff for reading.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slices import prior_edit  # noqa: E402

HERE = Path(__file__).resolve().parent
ITEMS = HERE.parents[1] / ".tmp" / "typesafe-system-one" / "items"
LABELS = HERE / "labels"
T1_OPTIONS = ("code-logic", "unit-test", "docs", "unknown")
COLUMNS = ("item_id", "split", "source", "title", "body", "suggested_action", "cited_step", "label", "note")


def items(name: str) -> list[dict]:
    return [json.loads(line) for line in (ITEMS / f"{name}.jsonl").open()]


def export_t1() -> None:
    LABELS.mkdir(exist_ok=True)
    path = LABELS / "t1.todo.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for it in items("t1"):
            s = it.get("step") or {}
            w.writerow({"item_id": it["item_id"], "split": it["split"],
                        "source": it["finding"]["source"], "title": it["finding"]["title"],
                        "body": it["finding"]["body"], "suggested_action": it["finding"]["suggested_action"] or "",
                        "cited_step": f"{s.get('id')}: {s.get('title')}" if s else "",
                        "label": "", "note": ""})
    print(f"wrote {path}; fill `label` with one of {T1_OPTIONS}, save as labels/t1.csv")


def import_t1() -> None:
    want = {it["item_id"] for it in items("t1")}
    rows = list(csv.DictReader((LABELS / "t1.csv").open(newline="")))
    got = {r["item_id"]: r["label"].strip() for r in rows}
    bad = {k: v for k, v in got.items() if v not in T1_OPTIONS}
    missing, extra = want - set(got), set(got) - want
    if bad or missing or extra:
        sys.exit(f"invalid: bad={len(bad)} {list(bad.items())[:5]} missing={len(missing)} extra={len(extra)}")
    print(f"ok: {len(got)} labels {dict(Counter(got.values()))}")


T2_OPTIONS = ("yes", "no")
T2_SETS = {"t2_audit": ("t2", lambda it: it["noise_audit"]), "t2_residue": ("t2_residue", lambda it: True)}
T2_QUESTION = ("Did the prior edit introduce the problem this finding describes? "
               "`yes` = the problem exists only because of text the edit added or changed; "
               "`no` = the problem was already present before the edit, or the edit is unrelated.")


def export_t2() -> None:
    LABELS.mkdir(exist_ok=True)
    for name, (src, keep) in T2_SETS.items():
        rows = [it for it in items(src) if keep(it)]
        with (LABELS / f"{name}.todo.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=("n", "item_id", "title", "label", "note"))
            w.writeheader()
            for n, it in enumerate(rows, 1):
                w.writerow({"n": n, "item_id": it["item_id"], "title": it["finding"]["title"][:120],
                            "label": "", "note": ""})
        with (LABELS / f"{name}.todo.md").open("w") as f:
            f.write(f"# {name} — blind labeling\n\n**Question.** {T2_QUESTION}\n\n")
            for n, it in enumerate(rows, 1):
                s = it.get("step") or {}
                fd = it["finding"]
                f.write(f"## {n}. `{it['item_id']}`\n\n**Cited step:** {s.get('id')}: {s.get('title')}\n\n"
                        f"**Finding ({fd['source']}, {fd['severity']}):** {fd['title']}\n\n{fd['body']}\n\n"
                        f"**Suggested action:** {fd['suggested_action'] or '(none)'}\n\n"
                        f"**Prior edit:**\n\n````diff\n{prior_edit(it) or '(empty)'}\n````\n\n")
        print(f"wrote labels/{name}.todo.csv + .todo.md ({len(rows)} items); "
              f"fill `label` with yes/no, save as labels/{name}.csv")


def import_t2() -> None:
    for name, (src, keep) in T2_SETS.items():
        want = {it["item_id"] for it in items(src) if keep(it)}
        got = {r["item_id"]: r["label"].strip().lower() for r in csv.DictReader((LABELS / f"{name}.csv").open(newline=""))}
        bad = {k: v for k, v in got.items() if v not in T2_OPTIONS}
        if bad or want - set(got) or set(got) - want:
            sys.exit(f"{name} invalid: bad={len(bad)} missing={len(want - set(got))} extra={len(set(got) - want)}")
        print(f"{name} ok: {len(got)} labels {dict(Counter(got.values()))}")


if __name__ == "__main__":
    verb, task = sys.argv[1], sys.argv[2]
    {("export", "t1"): export_t1, ("import", "t1"): import_t1,
     ("export", "t2"): export_t2, ("import", "t2"): import_t2}[(verb, task)]()
