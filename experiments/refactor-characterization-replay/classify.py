"""Phase 1: classify every historical green-step commit by ``change_type``.

Reads the plan file *as of that commit* and looks up the step's declared
change_type — the only trustworthy retrospective source, since a commit
subject does not carry the type. No worktrees, no test runs: this only sizes
the refactor corpus so we know whether the replay (``replay.py``) is worth
running.

Run: ``uv run python experiments/refactor-characterization-replay/classify.py``
Writes ``corpus.json`` beside this file — the input to ``replay.py``.

See LESSONS.md for the finding and the two methodology traps.
"""
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)
OUT = HERE / "corpus.json"

SUBJ_RE = re.compile(r"^plan\(([^)]+)\): step (\d+) green")
PLAN_PATH_RE = re.compile(r"^(?:docs/)?implementation-plans/[^/]+\.md$")


def git(*args: str) -> str:
    p = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True
    )
    return p.stdout if p.returncode == 0 else ""


def step_change_type(sha: str, plan_path: str, step_id: int):
    """change_type for step_id in plan_path as of sha, or None."""
    blob = git("show", f"{sha}:{plan_path}")
    if not blob:
        return None
    # Frontmatter only — split on the closing '---' at column 0.
    parts = blob.split("\n---\n", 1)
    fm = parts[0] if parts else blob
    # Walk '- id: N' blocks; take change_type before the next '- id:'.
    cur, found = None, None
    for line in fm.splitlines():
        m = re.match(r"^- id:\s*(\d+)\s*$", line)
        if m:
            cur = int(m.group(1))
            continue
        if cur == step_id:
            m2 = re.match(r"^\s+change_type:\s*([a-z-]+)\s*$", line)
            if m2:
                found = m2.group(1)
                break
    return found


rows = []
shas = git("log", "--all", "--format=%H", "--grep=step [0-9]* green").split()
for sha in shas:
    subject = git("log", "-1", "--format=%s", sha).strip()
    m = SUBJ_RE.match(subject)
    if not m:
        continue
    slug, step_id = m.group(1), int(m.group(2))
    files = [f for f in git("show", "--name-only", "--format=", sha).split() if f]
    # Plans live at implementation-plans/<n>-<slug>.md and, after the move,
    # docs/implementation-plans/<n>-<slug>.md. Match the file directly in that
    # directory only — plan-details/ subdirs hold per-step detail, not plans.
    plans = [f for f in files if PLAN_PATH_RE.match(f)]
    if not plans:
        continue
    ct = step_change_type(sha, plans[0], step_id)
    tests = [
        f
        for f in files
        if ("/test" in f or f.startswith("tests/"))
        and f.endswith(".py")
    ]
    rows.append(
        {
            "sha": sha,
            "slug": slug,
            "step": step_id,
            "change_type": ct,
            "plan": plans[0],
            "test_files": tests,
            "n_test_files": len(tests),
        }
    )

OUT.write_text(json.dumps(rows, indent=1))

counts: dict = {}
for r in rows:
    counts[r["change_type"]] = counts.get(r["change_type"], 0) + 1

print(f"green-step commits parsed: {len(rows)}")
print("\nby change_type:")
for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
    print(f"  {str(k):<12} {v}")

refac = [r for r in rows if r["change_type"] == "refactor"]
with_tests = [r for r in refac if r["n_test_files"]]
print(f"\nREFACTOR steps: {len(refac)}")
print(f"  ...of which changed >=1 test file: {len(with_tests)}  <- the replayable corpus")
if with_tests:
    print("\nreplayable sample:")
    for r in with_tests[:12]:
        print(f"  {r['sha'][:8]} {r['slug'][:38]:<38} s{r['step']:<3} {r['n_test_files']} test file(s)")
print(f"\nwrote {OUT}")
print("next: uv run python experiments/refactor-characterization-replay/replay.py")
