# /// script
# requires-python = ">=3.12"
# dependencies = ["typesafe-sdk==0.7.2"]
# ///
"""Call TypeSafe System One (pinned jev-1.13.0) for the typesafe-system-one experiment.

Usage (from the repo root; needs TYPESAFE_API_KEY in the environment):
    uv run --script experiments/typesafe-system-one/run_jev.py part1

Reads items from ``.tmp/typesafe-system-one/items/`` (build_corpus.py) and
caches every raw response under ``.tmp/typesafe-system-one/cache/``, keyed by
sha256(model, state, questions, rep), so a re-run makes no new calls. Calls
are serial (DESIGN.md § "Serial calls"); SDK retries are disabled so recorded
latency is one attempt, and a 429 is retried here after its back-off.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

from typesafe_sdk import Choice, Noul, RetryPolicy, Score, TypeSafeClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slices import load_jsonl, prior_commits, prior_edit, state_for, t2_items, t2_state  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TMP = REPO / ".tmp" / "typesafe-system-one"
CACHE = TMP / "cache"
MODEL = "jev-1.13.0"
QUESTIONS = json.loads((HERE / "questions.draft.json").read_text())
REPEATS = 5
BASE_QS = ("domain", "self_seeded", "materiality")
T2_DECOMP = ("t2_adds_cited_text", "t2_names_edit_contract", "t2_false_before_edit")


def question(qid: str, wording: str = "w0"):
    q = QUESTIONS[qid]
    ins = q["wordings"][wording]
    if q["type"] == "choice":
        return Choice(instructions=ins, criteria=q["criteria"])
    if q["type"] == "noul":
        return Noul(instructions=ins, criteria=q["criteria"])
    return Score(instructions=ins, criteria=q["criteria"])


def qpayload(qs: dict) -> dict:
    return {k: v.model_dump(mode="json", exclude_none=True) for k, v in qs.items()}


# ---- calling + cache --------------------------------------------------------

class Caller:
    def __init__(self) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.client = TypeSafeClient(retry=RetryPolicy(max_retries=0), timeout=60)
        self.new = self.hit = 0

    def call(self, state: dict, qs: dict, rep: int = 0) -> dict:
        body = {"model": MODEL, "state": state, "questions": qpayload(qs), "rep": rep}
        key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        path = CACHE / f"{key}.json"
        if path.exists():
            self.hit += 1
            return json.loads(path.read_text())
        for attempt in range(6):
            t0 = time.perf_counter()
            try:
                r = self.client.system_one(state, qs, model=MODEL)
                rec = {"ok": True, "latency_ms": (time.perf_counter() - t0) * 1000,
                       "response": r.model_dump(mode="json"), "request_id": r.request_id}
                break
            except Exception as e:  # schema/transport failures are data for P1a
                status = getattr(e, "status_code", None)
                if status == 429 and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                rec = {"ok": False, "latency_ms": (time.perf_counter() - t0) * 1000,
                       "error": f"{type(e).__name__}: {e}"[:500], "status": status}
                break
        rec["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if rec["ok"] and rec["response"].get("model") != MODEL:
            sys.exit(f"model mismatch: got {rec['response'].get('model')!r}; run invalid")
        path.write_text(json.dumps({"key_body": {k: body[k] for k in ("model", "rep")}, **rec}))
        self.new += 1
        return rec


def record(out, probe: str, it: dict, variant: str, qids, rep: int, rec: dict) -> None:
    out.write(json.dumps({"probe": probe, "item_id": it["item_id"], "variant": variant,
                          "qids": list(qids), "rep": rep, **rec}) + "\n")


def part1() -> None:
    items = load_jsonl("part1.jsonl")
    prev = prior_commits(load_jsonl("all.jsonl"))
    caller = Caller()
    out_path = TMP / "part1.results.jsonl"
    total = len(items)
    t_start = time.time()
    with out_path.open("w") as out:
        for i, it in enumerate(items, 1):
            edit = prior_edit(it, prev[it["item_id"]])
            base = state_for(it, "step", edit)
            # P1b repeat stability (rep 0 doubles as the P1c single-call arm).
            for qid in BASE_QS:
                for rep in range(REPEATS):
                    record(out, "P1b", it, qid, [qid], rep, caller.call(base, {qid: question(qid)}, rep))
            # P1c batch vs singles over the 3 base + 3 T2 decomposition questions.
            for qid in T2_DECOMP:
                record(out, "P1c-single", it, qid, [qid], 0, caller.call(base, {qid: question(qid)}))
            batch_ids = BASE_QS + T2_DECOMP
            record(out, "P1c-batch", it, "batch", batch_ids, 0,
                   caller.call(base, {q: question(q) for q in batch_ids}))
            # P1d paraphrase (w0 is the P1b rep-0 call).
            for qid in BASE_QS:
                for w in ("w1", "w2"):
                    record(out, "P1d", it, f"{qid}:{w}", [qid], 0, caller.call(base, {qid: question(qid, w)}))
            # P1e state size (the "step" arm is the P1b rep-0 call).
            for size in ("finding", "plan"):
                st = state_for(it, size, edit)
                for qid in BASE_QS:
                    record(out, "P1e", it, f"{qid}:{size}", [qid], 0, caller.call(st, {qid: question(qid)}))
            out.flush()
            print(f"[{i}/{total}] {it['plan_slug']} new={caller.new} cached={caller.hit} "
                  f"edit_chars={len(edit)} elapsed={time.time() - t_start:.0f}s", flush=True)
    print(f"done: results={out_path} new_calls={caller.new} cache_hits={caller.hit}", flush=True)


def dev_t2() -> None:
    """Dev-split tuning inputs for T2: the 3 single-arm wordings and the 3
    decomposition questions, one question per call."""
    items = [it for it in t2_items() if it.get("split") == "dev"]
    caller = Caller()
    out_path = TMP / "t2.dev.results.jsonl"
    with out_path.open("w") as out:
        for i, it in enumerate(items, 1):
            st = t2_state(it)
            for w in ("w0", "w1", "w2"):
                record(out, "T2-dev", it, f"self_seeded:{w}", ["self_seeded"], 0,
                       caller.call(st, {"self_seeded": question("self_seeded", w)}))
            for qid in T2_DECOMP:
                record(out, "T2-dev", it, f"{qid}:w0", [qid], 0, caller.call(st, {qid: question(qid)}))
            out.flush()
            print(f"[{i}/{len(items)}] new={caller.new} cached={caller.hit}", flush=True)
    print(f"done: results={out_path} new_calls={caller.new} cache_hits={caller.hit}", flush=True)


if __name__ == "__main__":
    {"part1": part1, "dev-t2": dev_t2}[sys.argv[1]]()
