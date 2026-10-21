"""Claude baselines (B-haiku / B-sonnet) for typesafe-system-one. Stdlib only.

    python3 experiments/typesafe-system-one/run_claude.py <task> <model> [--repeats-subset]

Each call is an isolated ``claude -p`` (no tools, no settings, no MCP, no
session, run from outside the repo so no CLAUDE.md loads) given the same state
and question wording Jev receives, asking for ``{"answer", "probability"}``.
Cost is read from the CLI's ``total_cost_usd``, never a price table, and a
cumulative ledger stops the run at the owner's cap (DESIGN.md § Budget).
Test-split calls require ``questions.frozen.json`` (Integrity rule 1).
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slices import t1_items, t1_state, t2_items, t2_state, t3_items, t3_state  # noqa: E402

HERE = Path(__file__).resolve().parent
TMP = HERE.parents[1] / ".tmp" / "typesafe-system-one"
CACHE = TMP / "claude-cache"
LEDGER = TMP / "claude-spend.json"
CAP_USD = 25.0  # owner decision, 2026-09-28
MODELS = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-5"}
FROZEN = HERE / "questions.frozen.json"
SUBSET_N = 30
SUBSET_REPEATS = 3
SYSTEM = ("You are a precise classifier. Judge only the JSON state you are given. "
          "Reply with one JSON object and nothing else.")
TASKS = {"t1": ("domain", t1_items, t1_state), "t2": ("self_seeded", t2_items, t2_state),
         "t3": ("t3_preserves_interface", t3_items, t3_state)}


def render(q: dict, state: dict) -> str:
    wording = q["wordings"]["w0"]
    if q["type"] == "choice":
        opts = "\n".join(f"- `{k}`: {v}" for k, v in q["criteria"].items())
        fmt = ('{"answer": "<one option name>", "probability": <your probability, 0 to 1, '
               'that this answer is correct>}')
    else:
        opts = f"- yes: {q['criteria']['true']}\n- no: {q['criteria']['false']}"
        fmt = '{"answer": "yes" | "no", "probability": <your probability, 0 to 1, that the answer is yes>}'
    return (f"Question: {wording}\n\nOptions:\n{opts}\n\nState (JSON):\n```json\n"
            f"{json.dumps(state, indent=1)}\n```\n\nReply with exactly one JSON object: {fmt}")


def parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else None
        return d if isinstance(d, dict) and "answer" in d and isinstance(d.get("probability"), (int, float)) else None
    except json.JSONDecodeError:
        return None


def spent() -> float:
    return json.loads(LEDGER.read_text())["usd"] if LEDGER.exists() else 0.0


def call(model: str, prompt: str, rep: int, cwd: str) -> dict:
    key = hashlib.sha256(json.dumps([model, SYSTEM, prompt, rep]).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    if spent() >= CAP_USD:
        sys.exit(f"spend cap reached: ${spent():.2f} >= ${CAP_USD}")
    r = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--tools", "",
         "--system-prompt", SYSTEM, "--setting-sources", "", "--strict-mcp-config",
         "--no-session-persistence", "--exclude-dynamic-system-prompt-sections"],
        cwd=cwd, capture_output=True, text=True, timeout=600)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        d = {"is_error": True, "result": r.stdout[-500:] + r.stderr[-500:]}
    rec = {"model": model, "rep": rep, "cost_usd": d.get("total_cost_usd") or 0.0,
           "duration_ms": d.get("duration_ms"), "is_error": d.get("is_error", True),
           "raw": d.get("result"), "parsed": parse(d.get("result") or "")}
    LEDGER.write_text(json.dumps({"usd": spent() + rec["cost_usd"]}))
    path.write_text(json.dumps(rec))
    return rec


def main() -> None:
    task, alias = sys.argv[1], sys.argv[2]
    subset = "--repeats-subset" in sys.argv
    if not FROZEN.exists():
        sys.exit("questions.frozen.json missing: baselines run on test splits only after the freeze")
    qid, items_fn, state_fn = TASKS[task]
    q = json.loads(FROZEN.read_text())[qid]
    items = [it for it in items_fn() if it.get("split") == "test"]
    reps = range(SUBSET_REPEATS) if subset else range(1)
    if subset:
        items = items[:SUBSET_N]
    CACHE.mkdir(parents=True, exist_ok=True)
    out_path = TMP / f"{task}.{alias}{'.repeats' if subset else ''}.results.jsonl"
    with tempfile.TemporaryDirectory(prefix="tss1-claude-") as cwd, out_path.open("w") as out:
        for i, it in enumerate(items, 1):
            prompt = render(q, state_fn(it))
            for rep in reps:
                rec = call(MODELS[alias], prompt, rep, cwd)
                out.write(json.dumps({"item_id": it["item_id"], **rec}) + "\n")
            out.flush()
            print(f"[{i}/{len(items)}] {alias} spent=${spent():.2f}", flush=True)
    print(f"done: {out_path} cumulative_spend=${spent():.2f}", flush=True)


if __name__ == "__main__":
    main()
