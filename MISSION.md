# Mission & grounding principles

## Mission

Turn a rough idea into a plan a developer can actually build from, keep it honest
as the code moves underneath it, and carry it to execution or export.

The hard part of using an LLM for real engineering work isn't generating text;
it's *trusting* it. So `plan-tool` wraps non-deterministic generation in
deterministic scaffolding — the output is **verifiable, scoped, and grounded in
the repository as it is right now**, not as it was when the plan was written.

The tool shapes an idea into an ordered, scoped plan (`create → detail → audit`),
helps find the real edges of the work, re-grounds the plan as code drifts, and
drives it to local execution (`run`) or Jira export (`jira`).

One fact underpins all of it: **the frontmatter is the machine contract; the
prose is for the human.** Everything below follows from that.

## Grounding principles

The rules the codebase obeys. When a design decision is ambiguous, resolve it
toward the principle.

Each principle carries a stable **kebab-slug id** in an HTML comment
(`<!-- principle-id: … -->`) — a position- and title-independent handle that
`CAPABILITIES.md` cites and the capability honesty check resolves. The slug is
assigned once and never changed on reorder or reword. When principles **merge**,
the absorbed slug is **retired**, not reused; a reference still citing a retired
slug is surfaced (the check's no-valid-principle finding), never silently
remapped.

### 1. Converge on the more-correct plan; mutate only when allowed
<!-- principle-id: converge-on-correct-plan -->

*The audit→apply walk runs until it converges — or surfaces a directional change instead.*

The loop is gates → `apply_finding` → re-audit until findings stabilize and stop
shrinking. Detection is unconditional; only auto-mutation is gated (opt-in +
confirmation). When the loop *won't* converge — the same region re-flagged pass
after pass — re-decompose; don't keep patching.

*"More-correct" means downstream impact, not plan-internal completeness.* The
findings that matter are the **seams** — inter-step contracts that break at a
jira ticket boundary — not prose an executor fills in for free. The stop signal
should track that impact, grounded in observed `reconcile-code` drift, not the
auditor's self-report. Today the loop keys on `severity`; re-keying it onto the
already-collected `impact` axis is the arc in BACKLOG #152–#154.

**Why:** Convergence is what separates "it generated something" from "the plan is
right." The user decides; the tool never rewrites structure silently.

### 2. Deterministically driven non-determinism
<!-- principle-id: deterministic-non-determinism -->

*The LLM is the engine; deterministic code is the chassis — it decides when to spend the model and how its output is verified.*

Every call goes through a controlled seam (`invoker=`) into a machine-validated
structure, bounded by gates. So: **validate, don't trust** (nothing counts until
it's re-parsed and passes a gate), and **let code find the patterns** (write the
check instead of asking the model where one can).

**Durable version changes carry an explicit transition contract.** Before a new
persisted schema, identity, or protocol version becomes the default, its plan
defines how existing projects reach it: compatible reading and rewrite, a
bounded migration with recovery, or a user-approved retirement after every
known consumer and live record has moved or been deliberately archived. The
contract names the observable behavior for legacy data, fails closed rather
than guessing, and has fixtures proving both the upgrade and its refusal
boundary. A new writer version alone is never an upgrade path.

**Why:** Same inputs, same control flow. What `grep` and a hash can decide
shouldn't cost an LLM round-trip.

### 3. Keep the plan true to live code
<!-- principle-id: keep-the-plan-true-to-code -->

*A plan is only as good as its fit to the repo right now — re-ground it rather than follow a stale one.*

Drift detection, reconcile, and the annotate→seed bridge re-fit the plan against
the live tree.

**Why:** Code moves underneath every plan. The value is in the one that stays
true.

### 4. Survive interruption
<!-- principle-id: survive-interruption -->

*State is checkpointed and every stage resumable — work continues, it doesn't restart.*

**Why:** A multi-step plan is expensive to regenerate. A tool that loses it to
one failure can't be trusted with real work.

### 5. Write for the human — once, and sharp
<!-- principle-id: write-for-the-human -->

*Docs and output serve the person who has to trust the system, not the parser.*

Explain the *why* and the sharp edges, tie each to its mechanism, push depth into
reference docs.

**Why:** A doc that only restates the code has failed its job. The terse version
gets read; the exhaustive one gets skimmed.
