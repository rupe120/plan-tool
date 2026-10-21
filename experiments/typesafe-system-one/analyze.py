"""Metrics for the typesafe-system-one experiment. Stdlib only.

    python3 experiments/typesafe-system-one/analyze.py part1

Reads ``.tmp/typesafe-system-one/part1.results.jsonl`` (run_jev.py) and
writes ``part1.metrics.json`` beside this file. See DESIGN.md § "Part 1" for
each probe and gate G1.
"""
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slices import t2_items, t2_truth  # noqa: E402

HERE = Path(__file__).resolve().parent
TMP = HERE.parents[1] / ".tmp" / "typesafe-system-one"
QUESTIONS = json.loads((HERE / "questions.draft.json").read_text())
PRICE_PER_TOKEN = 0.042 / 1e6  # USD, input only (vendor `models` page)


def answer(resp: dict, qid: str) -> dict | None:
    return (resp.get("answers") or {}).get(qid)


def valid(a: dict | None, qid: str) -> bool:
    """Schema check against the requested type (C1)."""
    if not a:
        return False
    q = QUESTIONS[qid]
    if q["type"] == "noul":
        p = a.get("noul")
        return isinstance(p, (int, float)) and 0 <= p <= 1
    probs = a.get("probabilities") or {}
    if abs(sum(probs.values()) - 1) > 0.02:
        return False
    if q["type"] == "choice":
        return a.get("choice") in q["criteria"] and set(probs) <= set(q["criteria"])
    n = len(q["criteria"])
    return isinstance(a.get("score"), (int, float)) and all(0 <= int(k) < n for k in probs)


def argmax(a: dict, qid: str):
    t = QUESTIONS[qid]["type"]
    if t == "noul":
        return a["noul"] >= 0.5
    if t == "choice":
        return a["choice"]
    return max(a["probabilities"], key=lambda k: a["probabilities"][k])


def scalar(a: dict, qid: str) -> float:
    """p(yes) for noul, top-option probability for choice, expected score for score."""
    t = QUESTIONS[qid]["type"]
    if t == "noul":
        return a["noul"]
    if t == "choice":
        return max(a["probabilities"].values())
    return a["score"]


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def part1() -> None:
    rows = [json.loads(line) for line in (TMP / "part1.results.jsonl").open()]
    m: dict = {"n_rows": len(rows)}

    # P1a schema validity over every (row, question).
    checks = [(r["ok"] and valid(answer(r["response"], q), q)) for r in rows for q in r["qids"]]
    errors = [r["error"] for r in rows if not r["ok"]]
    m["P1a"] = {"answers": len(checks), "valid": sum(checks), "valid_rate": sum(checks) / len(checks),
                "call_errors": len(errors), "error_samples": errors[:5]}

    def ok_ans(r, q):
        return answer(r["response"], q) if r["ok"] and valid(answer(r["response"], q), q) else None

    # P1b repeat stability.
    reps = defaultdict(list)
    for r in rows:
        if r["probe"] == "P1b" and (a := ok_ans(r, r["variant"])):
            reps[(r["item_id"], r["variant"])].append(a)
    p1b = {}
    for qid in ("domain", "self_seeded", "materiality"):
        groups = [v for (i, q), v in reps.items() if q == qid and len(v) >= 2]
        flips = [len({str(argmax(a, qid)) for a in g}) > 1 for g in groups]
        sds = [st.pstdev([scalar(a, qid) for a in g]) for g in groups]
        p1b[qid] = {"items": len(groups), "flip_rate": sum(flips) / len(groups),
                    "sd_mean": st.mean(sds), "sd_max": max(sds),
                    "identical_rate": sum(sd == 0 for sd in sds) / len(sds)}
    p1b["overall_flip_rate"] = st.mean(v["flip_rate"] for v in p1b.values())
    m["P1b"] = p1b

    # P1c batch vs singles.
    singles = {}
    lat_single, lat_batch, tok_single, tok_batch = defaultdict(float), {}, defaultdict(int), {}
    for r in rows:
        if not r["ok"]:
            continue
        if r["probe"] == "P1c-single" or (r["probe"] == "P1b" and r["rep"] == 0):
            q = r["variant"]
            singles[(r["item_id"], q)] = answer(r["response"], q)
            lat_single[r["item_id"]] += r["latency_ms"]
            tok_single[r["item_id"]] += r["response"]["usage"]["input_tokens"]
        elif r["probe"] == "P1c-batch":
            lat_batch[r["item_id"]] = r["latency_ms"]
            tok_batch[r["item_id"]] = r["response"]["usage"]["input_tokens"]
            for q in r["qids"]:
                singles.setdefault(("batch", r["item_id"], q), answer(r["response"], q))
    agree, dp = defaultdict(list), defaultdict(list)
    for (tag, item, q), ab in [(k, v) for k, v in singles.items() if k[0] == "batch"]:
        a1 = singles.get((item, q))
        if a1 and ab and valid(a1, q) and valid(ab, q):
            agree[q].append(argmax(a1, q) == argmax(ab, q))
            dp[q].append(abs(scalar(a1, q) - scalar(ab, q)))
    items_c = [i for i in lat_batch if i in lat_single]
    m["P1c"] = {
        "per_question": {q: {"agreement": sum(v) / len(v), "mean_abs_dp": st.mean(dp[q])} for q, v in agree.items()},
        "overall_agreement": sum(sum(v) for v in agree.values()) / sum(len(v) for v in agree.values()),
        "token_ratio_singles_over_batch": sum(tok_single[i] for i in items_c) / sum(tok_batch[i] for i in items_c),
        "latency_ratio_singles_over_batch": sum(lat_single[i] for i in items_c) / sum(lat_batch[i] for i in items_c),
        "items": len(items_c),
    }

    # P1d paraphrase: w0 (P1b rep 0) vs w1, w2.
    base = {(r["item_id"], r["variant"]): ok_ans(r, r["variant"]) for r in rows if r["probe"] == "P1b" and r["rep"] == 0}
    para = defaultdict(dict)
    for r in rows:
        if r["probe"] == "P1d":
            q, w = r["variant"].split(":")
            para[(r["item_id"], q)][w] = ok_ans(r, q)
    p1d = {}
    for qid in ("domain", "self_seeded", "materiality"):
        flips = []
        for (item, q), ws in para.items():
            if q != qid or not base.get((item, q)) or not all(ws.values()):
                continue
            labels = {str(argmax(base[(item, q)], q))} | {str(argmax(a, q)) for a in ws.values()}
            flips.append(len(labels) > 1)
        p1d[qid] = {"items": len(flips), "flip_rate": sum(flips) / len(flips)}
    m["P1d"] = p1d

    # P1e state size: finding / step (P1b rep 0) / plan.
    sized = defaultdict(dict)
    lat_size, tok_size = defaultdict(list), defaultdict(list)
    for r in rows:
        if r["probe"] == "P1e":
            q, size = r["variant"].split(":")
        elif r["probe"] == "P1b" and r["rep"] == 0:
            q, size = r["variant"], "step"
        else:
            continue
        if (a := ok_ans(r, q)):
            sized[(r["item_id"], q)][size] = a
            lat_size[size].append(r["latency_ms"])
            tok_size[size].append(r["response"]["usage"]["input_tokens"])
    p1e = {"latency_p50_ms": {s: pct(v, .5) for s, v in lat_size.items()},
           "input_tokens_mean": {s: st.mean(v) for s, v in tok_size.items()}}
    for qid in ("domain", "self_seeded", "materiality"):
        for other in ("finding", "plan"):
            pairs = [(d["step"], d[other]) for (i, q), d in sized.items() if q == qid and "step" in d and other in d]
            p1e[f"{qid}:step_vs_{other}"] = {
                "items": len(pairs),
                "argmax_shift_rate": sum(str(argmax(a, qid)) != str(argmax(b, qid)) for a, b in pairs) / len(pairs),
                "mean_abs_dp": st.mean(abs(scalar(a, qid) - scalar(b, qid)) for a, b in pairs)}
    m["P1e"] = p1e

    # P1f cost and latency over all calls.
    lat = [r["latency_ms"] for r in rows if r["ok"]]
    tok = [r["response"]["usage"]["input_tokens"] for r in rows if r["ok"]]
    single_rows = [r for r in rows if r["ok"] and len(r["qids"]) == 1]
    m["P1f"] = {"calls": len(lat), "latency_p50_ms": pct(lat, .5), "latency_p95_ms": pct(lat, .95),
                "latency_max_ms": max(lat), "input_tokens_total": sum(tok),
                "usd_total": sum(tok) * PRICE_PER_TOKEN,
                "usd_per_single_question_decision_mean":
                    st.mean(r["response"]["usage"]["input_tokens"] for r in single_rows) * PRICE_PER_TOKEN}

    m["G1"] = {"schema_100pct": m["P1a"]["valid_rate"] == 1.0,
               "flip_rate_le_5pct": p1b["overall_flip_rate"] <= 0.05,
               "per_question_flip_le_2pct": {q: p1b[q]["flip_rate"] <= 0.02 for q in ("domain", "self_seeded", "materiality")}}
    m["G1"]["pass"] = m["G1"]["schema_100pct"] and m["G1"]["flip_rate_le_5pct"]
    (HERE / "part1.metrics.json").write_text(json.dumps(m, indent=2) + "\n")
    print(json.dumps(m, indent=2))


# ---- scoring primitives ----------------------------------------------------

def auroc(scores: list[float], truth: list[bool]) -> float:
    """Mann-Whitney AUROC; ties count half."""
    pos = [s for s, t in zip(scores, truth) if t]
    neg = [s for s, t in zip(scores, truth) if not t]
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def brier(p: list[float], truth: list[bool]) -> float:
    return st.mean((pi - ti) ** 2 for pi, ti in zip(p, truth))


def ece(p: list[float], truth: list[bool], bins: int = 10) -> float:
    total, err = len(p), 0.0
    for b in range(bins):
        idx = [i for i, pi in enumerate(p) if b / bins <= pi < (b + 1) / bins or (b == bins - 1 and pi == 1)]
        if idx:
            err += len(idx) / total * abs(st.mean(p[i] for i in idx) - st.mean(truth[i] for i in idx))
    return err


def fit_logistic(xs: list[list[float]], ys: list[bool], l2: float = 0.1, steps: int = 5000) -> list[float]:
    """Weights [bias, w1..wk] by full-batch gradient descent on logit(p) features."""
    feats = [[1.0] + [math.log(max(min(v, 1 - 1e-6), 1e-6) / (1 - max(min(v, 1 - 1e-6), 1e-6))) for v in x] for x in xs]
    w = [0.0] * len(feats[0])
    for _ in range(steps):
        grad = [0.0] * len(w)
        for f, y in zip(feats, ys):
            z = sum(wi * fi for wi, fi in zip(w, f))
            e = 1 / (1 + math.exp(-z)) - y
            for j, fj in enumerate(f):
                grad[j] += e * fj
        w = [wi - 0.05 * (g / len(feats) + (l2 * wi if j else 0)) for j, (wi, g) in enumerate(zip(w, grad))]
    return w


def apply_logistic(w: list[float], x: list[float]) -> float:
    f = [1.0] + [math.log(max(min(v, 1 - 1e-6), 1e-6) / (1 - max(min(v, 1 - 1e-6), 1e-6))) for v in x]
    return 1 / (1 + math.exp(-sum(wi * fi for wi, fi in zip(w, f))))


T2_DECOMP = ("t2_adds_cited_text", "t2_names_edit_contract", "t2_false_before_edit")


def dev_t2() -> None:
    truth = {it["item_id"]: t2_truth(it) for it in t2_items() if it.get("split") == "dev"}
    p = defaultdict(dict)
    for r in (json.loads(line) for line in (TMP / "t2.dev.results.jsonl").open()):
        if r["ok"]:
            p[r["item_id"]][r["variant"]] = answer(r["response"], r["qids"][0])["noul"]
    ids = sorted(truth)
    y = [truth[i] for i in ids]
    m = {"n": len(ids), "positives": sum(y)}
    for w in ("w0", "w1", "w2"):
        s = [p[i][f"self_seeded:{w}"] for i in ids]
        m[f"single:{w}"] = {"auroc": auroc(s, y), "brier": brier(s, y), "ece": ece(s, y)}
    for q in T2_DECOMP:
        m[f"atom:{q}"] = {"auroc": auroc([p[i][f"{q}:w0"] for i in ids], y)}
    xs = [[p[i][f"{q}:w0"] for q in T2_DECOMP] for i in ids]
    # Leave-one-out estimate of the decomposed arm, so the dev figure is not
    # scored on the data its weights were fit to.
    loo = [apply_logistic(fit_logistic(xs[:k] + xs[k + 1:], y[:k] + y[k + 1:]), xs[k]) for k in range(len(ids))]
    w = fit_logistic(xs, y)
    m["decomposed"] = {"weights": w, "loo_auroc": auroc(loo, y), "loo_brier": brier(loo, y), "loo_ece": ece(loo, y)}
    (HERE / "t2.dev.metrics.json").write_text(json.dumps(m, indent=2) + "\n")
    print(json.dumps(m, indent=2))


if __name__ == "__main__":
    {"part1": part1, "dev-t2": dev_t2}[sys.argv[1]]()
