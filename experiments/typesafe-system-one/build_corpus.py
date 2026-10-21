"""Build the typesafe-system-one item corpus from saved audit reports.

Unions the tracked completeness reports of this clone and the sibling
``plan-tool-2`` clone, deduplicated by (plan_slug, created_at, rec id), and
resolves each conceptual finding's cited step *as it stood at audit time*
(the last commit touching the plan before ``created_at``). See DESIGN.md
§ "Corpus sources" and § "Part 1".

Usage (project venv; reads ``plan_tool`` only for the B-code domain label):
    uv run python experiments/typesafe-system-one/build_corpus.py

Writes regenerable items under ``.tmp/typesafe-system-one/items/``:
    all.jsonl     every deduplicated conceptual finding with its state slices
    part1.jsonl   the 60-item Part 1 sample (seed PART1_SEED)
    t1.jsonl      the 150-item T1 labeling set, stratified by B-code label
"""
import json
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SIBLING = REPO.parent / "plan-tool-2"
OUT = REPO / ".tmp" / "typesafe-system-one" / "items"
REPORT_GLOB = "docs/implementation-plans/plan-details/*/reports/*.json"

PART1_SEED = 20260928
PART1_N = 60
T1_SEED = 20260929
T1_TARGETS = {"docs": 32, "unit-test": 3, "code-logic": 40, "unknown": 75}
T1_DEV = 50
DETAIL_CAP = 6000  # chars of a step's detail file sent as the step slice
PLAN_CAP = 100_000  # chars; ~25k tokens, under the 32k state limit

CONCEPTUAL = {"plan-correctness", "plan-completeness"}
STEP_RE = re.compile(r"\b[Ss]teps? (\d+)\b")
# Secret shapes; any hit drops the item (DESIGN.md § "Data handling").
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}"
    r"|xox[abposr]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY"
    r"|(?i:api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,})"
)

sys.path.insert(0, str(REPO))
from plan_tool.review import Recommendation, classify_finding_domain  # noqa: E402


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def load_reports() -> list[tuple[Path, dict]]:
    seen, out = set(), []
    for repo in (REPO, SIBLING):
        for f in sorted(repo.glob(REPORT_GLOB)):
            d = json.loads(f.read_text())
            key = (d.get("plan_slug"), d.get("created_at"))
            if key in seen:
                continue
            seen.add(key)
            out.append((repo, d))
    return out


def plan_rel(d: dict) -> str:
    p = d.get("plan_path") or ""
    if p:
        return p if p.endswith(".md") else p + ".md"
    return f"docs/implementation-plans/2-{d['plan_slug']}.md"


_plan_cache: dict = {}


def plan_at(repo: Path, rel: str, when: str) -> tuple[str, str]:
    """(commit, text) of ``rel`` at the last commit before ``when``."""
    key = (repo, rel, when)
    if key not in _plan_cache:
        sha = git(repo, "log", "-1", "--format=%H", f"--before={when}", "--", rel).strip()
        text = git(repo, "show", f"{sha}:{rel}") if sha else ""
        _plan_cache[key] = (sha, text)
    return _plan_cache[key]


def split_plan(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    try:
        return yaml.safe_load(fm) or {}, body
    except yaml.YAMLError:
        return {}, body


def detail_at(repo: Path, sha: str, slug: str, step_id: int) -> str:
    listing = git(repo, "ls-tree", "--name-only", sha, f"docs/implementation-plans/plan-details/{slug}/")
    for name in listing.split():
        if Path(name).name.startswith(f"{step_id:02d}-") and name.endswith(".md"):
            return git(repo, "show", f"{sha}:{name}")[:DETAIL_CAP]
    return ""


def build_item(repo: Path, d: dict, r: dict) -> dict | None:
    slug, when = d["plan_slug"], d["created_at"]
    sha, text = plan_at(repo, plan_rel(d), when)
    fm, body = split_plan(text)
    prose = f"{r['title']}\n{r['body']}"
    m = STEP_RE.search(prose)
    cited = r.get("step_id") or (int(m.group(1)) if m else None)
    step = None
    for s in fm.get("steps") or []:
        if s.get("id") == cited:
            step = {k: s.get(k) for k in ("id", "title", "intent", "files", "change_type")}
            step["detail"] = detail_at(repo, sha, slug, cited) if sha else ""
    rec = Recommendation(
        id=r["id"], source=r["source"], severity=r["severity"], step_id=r.get("step_id"),
        title=r["title"], body=r["body"], suggested_action=r.get("suggested_action"),
        file_path=r.get("file_path"),
    )
    item = {
        "item_id": f"{slug}|{when}|{r['id']}",
        "plan_slug": slug,
        "created_at": when,
        "stage": (d.get("qualified_result") or {}).get("stage"),
        "plan_commit": sha,
        "bcode_domain": classify_finding_domain(rec),
        "finding": {k: r.get(k) for k in ("source", "severity", "title", "body", "suggested_action")},
        "cited_step_id": cited,
        "step": step,
        "plan": {"intent": fm.get("intent"), "title": fm.get("title"), "text": text[:PLAN_CAP]} if text else None,
    }
    if SECRET_RE.search(json.dumps(item)):
        return None
    return item


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items, seen, dropped = [], set(), Counter()
    reports = load_reports()
    for repo, d in reports:
        for r in d.get("recommendations") or []:
            if r.get("source") not in CONCEPTUAL:
                continue
            key = (d["plan_slug"], d["created_at"], r["id"])
            if key in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(key)
            it = build_item(repo, d, r)
            if it is None:
                dropped["secret-scan"] += 1
                continue
            items.append(it)
    write(OUT / "all.jsonl", items)

    # Part 1: findings with a resolved step slice and plan text, one per title.
    eligible, titles = [], set()
    for it in items:
        if it["step"] and it["plan"] and it["finding"]["title"] not in titles:
            titles.add(it["finding"]["title"])
            eligible.append(it)
    part1 = random.Random(PART1_SEED).sample(eligible, PART1_N)
    write(OUT / "part1.jsonl", part1)

    # T1: medium conceptual findings, stratified by the B-code label.
    rng = random.Random(T1_SEED)
    medium = [it for it in items if it["finding"]["severity"] == "medium"]
    by = {k: [it for it in medium if it["bcode_domain"] == k] for k in T1_TARGETS}
    t1 = []
    for k, n in T1_TARGETS.items():
        pool = by[k]
        t1 += rng.sample(pool, min(n, len(pool)))
    short = sum(T1_TARGETS.values()) - len(t1)
    if short:  # refill a thin stratum from `unknown`, keeping the 150 total
        rest = [it for it in by["unknown"] if it not in t1]
        t1 += rng.sample(rest, short)
    rng.shuffle(t1)
    for i, it in enumerate(t1):
        it["split"] = "dev" if i < T1_DEV else "test"
    write(OUT / "t1.jsonl", t1)

    print(f"reports={len(reports)} conceptual_items={len(items)} dropped={dict(dropped)}")
    print(f"part1: eligible={len(eligible)} sampled={len(part1)}")
    print("medium strata available:", {k: len(v) for k, v in by.items()})
    print("t1 strata:", dict(Counter(it['bcode_domain'] for it in t1)), "splits:", dict(Counter(it['split'] for it in t1)))


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ---- T2: self-seeded findings, labeled by `git blame` (DESIGN.md § T2) ----

T2_SEED = 20260930
T2_DEV_FRACTION = 0.3
T2_AUDIT_N = 50
T2_RESIDUE_N = 50
QUOTE_RE = re.compile(r"`([^`\n]{15,})`|\"([^\"\n]{15,})\"|“([^”\n]{15,})”")


def quotes(prose: str) -> list[str]:
    qs = {next(g for g in m.groups() if g) for m in QUOTE_RE.finditer(prose)}
    return sorted(qs, key=len, reverse=True)


def locate(text: str, quote: str) -> tuple[int, int] | None:
    """(first, last) 1-based line span of ``quote`` in ``text``, whitespace-insensitive."""
    norm, lines, line = [], [], 1
    prev_ws = False
    for ch in text:
        if ch.isspace():
            if not prev_ws:
                norm.append(" ")
                lines.append(line)
            prev_ws = True
        else:
            norm.append(ch)
            lines.append(line)
            prev_ws = False
        if ch == "\n":
            line += 1
    q = " ".join(quote.split())
    i = "".join(norm).find(q)
    if i < 0:
        return None
    return lines[i], lines[i + len(q) - 1]


def blame_commits(repo: Path, sha: str, path: str, span: tuple[int, int]) -> list[str]:
    out = git(repo, "blame", "--porcelain", "-L", f"{span[0]},{span[1]}", sha, "--", path)
    return sorted({ln.split()[0] for ln in out.splitlines() if re.match(r"^[0-9a-f]{40} \d+ \d+", ln)})


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=repo).returncode == 0


def mechanical_label(repo: Path, item: dict, prev: str, cur: str) -> dict:
    """Blame the finding's longest verbatim quote at round N's plan commit."""
    slug, sid = item["plan_slug"], item["cited_step_id"]
    files = git(repo, "log", "-1", "--format=", "--name-only", cur, "--",
                f":(glob)docs/implementation-plans/*{slug}.md").split()[:1]
    details = git(repo, "ls-tree", "--name-only", cur, f"docs/implementation-plans/plan-details/{slug}/").split()
    details = [d for d in details if d.endswith(".md")]
    cited = [d for d in details if sid is not None and Path(d).name.startswith(f"{int(sid):02d}-")]
    files += cited + [d for d in details if d not in cited]
    texts = {f: git(repo, "show", f"{cur}:{f}") for f in files if f}
    prose = f"{item['finding']['title']}\n{item['finding']['body']}"
    for q in quotes(prose):
        for f, text in texts.items():
            span = locate(text, q) if text else None
            if not span:
                continue
            commits = blame_commits(repo, cur, f, span)
            fresh = [c for c in commits if not is_ancestor(repo, c, prev)]
            return {"label": bool(fresh), "quote": q, "file": f, "span": span,
                    "blamed": commits, "fresh": fresh}
    return {"label": None}


def build_t2() -> None:
    by_slug: dict = {}
    for repo, d in load_reports():
        if d.get("kind") == "completeness":
            by_slug.setdefault(d["plan_slug"], []).append((repo, d))
    rows, pairs, secret_drops = [], 0, 0
    for slug, reps in by_slug.items():
        reps.sort(key=lambda rd: rd[1]["created_at"])
        commits = [plan_at(repo, plan_rel(d), d["created_at"])[0] for repo, d in reps]
        for (rp, dp), (rc, dc), cp, cc in zip(reps, reps[1:], commits, commits[1:]):
            if not cp or not cc or cp == cc:
                continue
            pairs += 1
            old = [r for r in dp.get("recommendations") or [] if r.get("source") in CONCEPTUAL]
            old_ids, old_titles = {r["id"] for r in old}, {r["title"][:60] for r in old}
            for r in dc.get("recommendations") or []:
                if r.get("source") not in CONCEPTUAL or r["id"] in old_ids or r["title"][:60] in old_titles:
                    continue
                it = build_item(rc, dc, r)
                if it is None:
                    secret_drops += 1
                    continue
                it["prev_commit"] = cp
                it["round"] = f"{slug}|{dc['created_at']}"
                it["t2_mech"] = mechanical_label(rc, it, cp, cc)
                it.pop("plan", None)  # T2 state never carries the whole plan
                rows.append(it)
    rng = random.Random(T2_SEED)
    labeled = [r for r in rows if r["t2_mech"]["label"] is not None]
    residue = [r for r in rows if r["t2_mech"]["label"] is None]
    rng.shuffle(labeled)
    n_dev = round(len(labeled) * T2_DEV_FRACTION)
    for i, r in enumerate(labeled):
        r["split"] = "dev" if i < n_dev else "test"
    audit_ids = {r["item_id"] for r in rng.sample(labeled, min(T2_AUDIT_N, len(labeled)))}
    residue_sample = rng.sample(residue, min(T2_RESIDUE_N, len(residue)))
    for r in residue_sample:
        r["split"] = "test"
    for r in labeled:
        r["noise_audit"] = r["item_id"] in audit_ids
    write(OUT / "t2.jsonl", labeled)
    write(OUT / "t2_residue.jsonl", residue_sample)
    pos = sum(r["t2_mech"]["label"] for r in labeled)
    rounds = Counter(r["round"] for r in labeled)
    print(f"edited pairs={pairs} new findings={len(rows)} secret_drops={secret_drops}")
    print(f"mechanically labeled={len(labeled)} (positive={pos}) residue={len(residue)} residue_sampled={len(residue_sample)}")
    print(f"splits={dict(Counter(r['split'] for r in labeled))} rounds_with_ge4={sum(v >= 4 for v in rounds.values())}")


# ---- T3: refactor preserves the test-visible interface (DESIGN.md § T3) ----

T3_REPLAY = REPO / ".tmp" / "typesafe-system-one" / "t3.replay.results.json"
T3_SECTIONS = ("Files (creates vs edits)", "Implementation", "Tests")
T3_SECTION_CAP = 5000


def sections(md: str, names: tuple[str, ...]) -> dict:
    out, cur = {}, None
    for line in md.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip() if line[3:].strip() in names else None
            if cur:
                out[cur] = []
            continue
        if cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip()[:T3_SECTION_CAP] for k, v in out.items()}


def build_t3() -> None:
    """Replay verdicts: rc 0 = tests pass pre-change (positive); rc 1/2 = negative."""
    rows, skipped = [], Counter()
    for e in json.loads(T3_REPLAY.read_text()):
        if e["rc"] not in (0, 1, 2):
            skipped["inconclusive"] += 1
            continue
        parent = f"{e['sha']}^"
        listing = git(REPO, "ls-tree", "-r", "--name-only", parent)
        detail = next((p for p in listing.split()
                       if f"/plan-details/{e['slug']}/" in p and Path(p).name.startswith(f"{e['step']:02d}-")
                       and p.endswith(".md") and "/reports/" not in p), None)
        secs = sections(git(REPO, "show", f"{parent}:{detail}"), T3_SECTIONS) if detail else {}
        if not secs.get("Tests"):
            skipped["no-detail-tests"] += 1
            continue
        plan_fm, _ = split_plan(git(REPO, "show", f"{parent}:{e['plan']}"))
        step = next((s for s in plan_fm.get("steps") or [] if s.get("id") == e["step"]), {})
        it = {"item_id": f"{e['slug']}|{e['step']}|{e['sha'][:12]}", "split": "test",
              "step": {k: step.get(k) for k in ("id", "title", "intent", "change_type")},
              "detail": secs, "truth": e["rc"] == 0, "replay_verdict": e["verdict"]}
        if SECRET_RE.search(json.dumps(it)):
            skipped["secret-scan"] += 1
            continue
        rows.append(it)
    write(OUT / "t3.jsonl", rows)
    print(f"t3 items={len(rows)} positives={sum(r['truth'] for r in rows)} skipped={dict(skipped)}")


if __name__ == "__main__":
    {"all": main, "t2": build_t2, "t3": build_t3}[sys.argv[1] if len(sys.argv) > 1 else "all"]()
