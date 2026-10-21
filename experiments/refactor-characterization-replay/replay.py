"""Phase 2: replay each historical refactor step's tests against pre-change source.

For every refactor step that changed >=1 test file: worktree at the step's
PARENT commit (detached), copy in that step's POST-change test files unmodified,
run only those files, and classify the outcome.

This executes the proposed characterization-pinning check retrospectively, and
answers the question its plan could not: how often would it actually fire?

Tests are copied UNMODIFIED. No import stripping, no edits to force a green --
that is the vacuous-check failure mode the whole exercise exists to detect.

Run ``classify.py`` first (it writes ``corpus.json``), then:
``uv run python experiments/refactor-characterization-replay/replay.py``
Writes ``results.json`` beside this file. Worktrees are created under a fresh
temp dir and removed in a ``finally``; the run asserts none leak.

See LESSONS.md for the finding and the two methodology traps.
"""
import json
import subprocess
import tempfile
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
# Sandboxes land outside the repo so a stray worktree can never be mistaken
# for tracked content; mkdtemp keeps concurrent runs from colliding.
SCRATCH = Path(tempfile.mkdtemp(prefix="characterization-replay-"))
CORPUS = HERE / "corpus.json"
OUT = HERE / "results.json"

# pytest exit codes: 0 all passed, 1 tests failed, 2 interrupted (collection
# error lands here), 5 no tests collected.
VERDICT = {
    0: "PASS (check stays silent)",
    1: "FAIL (tests red pre-change)",
    2: "UNCOLLECTABLE (import/collection error)",
    5: "NO-TESTS-COLLECTED",
}


def git(*args, cwd=REPO):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )


rows = json.load(CORPUS.open())
targets = [
    r for r in rows if r["change_type"] == "refactor" and r["n_test_files"]
]
print(f"replaying {len(targets)} refactor steps\n", flush=True)

git("worktree", "prune")
results = []

for i, r in enumerate(targets, 1):
    sha, slug, step = r["sha"], r["slug"], r["step"]
    wt = SCRATCH / f"replay-{sha[:8]}"
    label = f"[{i}/{len(targets)}] {slug[:34]:<34} s{step}"
    entry = {**r, "verdict": None, "rc": None, "note": ""}
    try:
        # Detached checkout of the PRE-change tree.
        rc, err = (lambda p: (p.returncode, p.stderr.strip()))(
            git("worktree", "add", "-q", "--detach", str(wt), f"{sha}^")
        )
        if rc != 0:
            entry["verdict"] = "SETUP-FAILED"
            entry["note"] = err[:200]
            print(f"{label}  SETUP-FAILED  {err[:60]}", flush=True)
            results.append(entry)
            continue

        # Copy the step's POST-change test files in, unmodified.
        copied = []
        for tf in r["test_files"]:
            blob = git("show", f"{sha}:{tf}")
            if blob.returncode != 0:
                continue  # deleted/renamed in that commit
            dest = wt / tf
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(blob.stdout)
            copied.append(tf)
        if not copied:
            entry["verdict"] = "NO-TEST-BLOBS"
            print(f"{label}  NO-TEST-BLOBS", flush=True)
            results.append(entry)
            continue
        entry["copied"] = copied

        # Run ONLY those files, against pre-change source.
        p = subprocess.run(
            ["uv", "run", "pytest", *copied, "-q", "--no-header", "-p", "no:randomly"],
            cwd=wt,
            capture_output=True,
            text=True,
            timeout=900,
        )
        entry["rc"] = p.returncode
        entry["verdict"] = VERDICT.get(p.returncode, f"OTHER-rc{p.returncode}")
        tail = [l for l in p.stdout.strip().split("\n") if l.strip()][-1:]
        entry["note"] = (tail[0] if tail else "")[:120]
        print(f"{label}  {entry['verdict']:<40} {entry['note'][:44]}", flush=True)
    except subprocess.TimeoutExpired:
        entry["verdict"] = "TIMEOUT"
        print(f"{label}  TIMEOUT", flush=True)
    except Exception as exc:  # noqa: BLE001 - measurement harness
        entry["verdict"] = "HARNESS-ERROR"
        entry["note"] = f"{type(exc).__name__}: {exc}"[:200]
        print(f"{label}  HARNESS-ERROR {exc}", flush=True)
    finally:
        git("worktree", "remove", "--force", str(wt))
        git("worktree", "prune")
        results.append(entry) if entry not in results else None

OUT.write_text(json.dumps(results, indent=1))

print("\n" + "=" * 74)
tally: dict = {}
for e in results:
    tally[e["verdict"]] = tally.get(e["verdict"], 0) + 1
for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
    print(f"  {k:<44} {v}")

concl = [e for e in results if e["rc"] in (0, 1, 2)]
fired = [e for e in concl if e["rc"] in (1, 2)]
print("=" * 74)
if concl:
    pct = 100.0 * len(fired) / len(concl)
    print(
        f"\nWOULD-FIRE RATE: {len(fired)}/{len(concl)} conclusive replays = {pct:.0f}%"
    )
print(f"\nleftover worktrees (must be none): {len(git('worktree','list').stdout.splitlines()) - 1}")
print(f"wrote {OUT}")
