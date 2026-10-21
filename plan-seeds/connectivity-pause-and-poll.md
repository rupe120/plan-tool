# Connectivity-aware pause-and-poll for the transient recovery loop

## Outcome

A backend call whose failure is plausibly a **local** connectivity loss — a
fast `ClaudeFailureKind.TRANSIENT` network error, or a long-running call the
heartbeat silence-kills (`TerminationReason.SILENCE_TIMEOUT`, never a caller's
own `CONFIGURED_TIMEOUT`) — pauses and polls for connectivity's return, and
resubmits **only once a fresh probe confirms it is actually back**, never on a
blind fixed delay. Interruptible on a TTY; capped on a non-interactive run.
Connectivity that reads up throughout is unaffected: identical behavior to
today, for both the fast and the long-running case.

## Overview

`shell.claude_invoke` (batch) and `launcher.shell_invoker` (streaming, via
`run`) both drive `rate_limit_loop.run_with_rate_limit_recovery`, the one
shared recovery state machine (BACKLOG #101), and both spawn through the one
shared Popen supervisor, `backend_runner.run_streaming_once`. A real network
outage — WiFi drop, laptop sleep/wake, VPN reconnect, a train tunnel — shows up
in two different shapes today, and both under-serve it:

- **Fast:** a `TRANSIENT` classification — `backend._CLAUDE_TRANSIENT_PATTERN`
  matching `ECONNRESET`, `network error`, `timeout`, `connection reset`,
  `socket hang up`, bare `429`, or a provider 5xx — gets
  `DEFAULT_MAX_TRANSIENT_RETRIES=2` attempts at
  `DEFAULT_TRANSIENT_BASE_DELAY=2.0`s exponential backoff
  (`shell.py:156-157`), indistinguishable from an ordinary one-off provider
  blip, then `TERMINAL` within ~6 seconds.
- **Long-running:** a call already deep into real work (editing many files
  over several minutes) whose connection dies silently blocks on a dead read.
  `backend_runner.py`'s heartbeat notices no NDJSON activity and, past
  `_KILL_AFTER_SILENCE_S=900.0` seconds, sends SIGTERM/SIGKILL
  (`backend_runner.py:57`, `:704-745`), recording
  `TerminationReason.SILENCE_TIMEOUT` and classifying the outcome
  `ClaudeFailureKind.TIMEOUT` — deliberately terminal, never retried
  (`claude_errors.py:98-100`, `:576-580`).

Neither path asks "is the local machine actually reachable right now." This
seed adds that probe and two narrow recovery arms gated on it — one per shape
above — changing nothing about an ordinary blip with connectivity confirmed
up, a caller's own `CONFIGURED_TIMEOUT` ceiling, or `RATE_LIMIT`/`PLAN_QUOTA`,
which already own their own wait/switch/ask machinery.

## Architecture

### The probe: a new injected seam, not a new classification

Connectivity is a **runtime fact consulted after classification** (§ below
covers exactly which outcomes it applies to and why no closed vocabulary
gains a member), not something `classify()` itself learns to detect.

`rate_limit_loop.py` is a stdlib-only leaf with no first-party import
(`docs/how-to/pipeline/run.md` § "Rate-limit / transient recovery seam"); its default
probe must stay stdlib-only too (`socket.create_connection` against a small,
fixed, DNS-independent set of well-known IP:port pairs — a public anycast
resolver, not a hostname, so a broken local DNS server doesn't itself produce a
false "still reachable"). Each caller can override the seam exactly like it
already overrides `wait`/`sleep`/`retry_guard`; production callers use the
default.

**Deliberately not the backend's own API host.** Probing `api.anthropic.com` (or
the active backend's equivalent) would conflate "my network is down" with "the
provider is having an outage" — the latter is already `RATE_LIMIT`/`PLAN_QUOTA`/
ordinary `TRANSIENT`'s job. This probe answers one question only: is there a
route to the general internet at all.

### One connectivity signal covers both cases — the leaf stays ignorant of *why*

**Decision:** the stdlib-only leaf (`rate_limit_loop.py`) must receive exactly
one new, opaque, already-computed signal per attempt — call it a
poll-eligibility signal — and must never itself inspect `ClaudeFailureKind` or
`TerminationReason` to derive it; that computation belongs entirely to the
caller-side mapping layer that already owns `KIND_TO_CATEGORY`
(`claude_errors.py`), preserving the leaf's existing "no first-party import"
constraint. `classify()` itself stays pure pattern-matching, untouched. The
exact shape that signal takes on the wire — a new dataclass field, a separate
return value, or something else — is `detail`'s call, not this seed's; what
must not drift is the constraint above and the eligibility rule below.

**The eligibility rule (must not drift):** the signal is true only when a
fresh connectivity probe reads down **and** the outcome is either an ordinary
`TRANSIENT` classification, or a `TIMEOUT` classification whose termination
reason — read via the existing `get_last_termination_reason()`
(`backend_runner.py`) — was specifically `SILENCE_TIMEOUT`. `category` itself
is untouched: `TRANSIENT` still maps to `TRANSIENT`, and `TIMEOUT` still maps
to `TERMINAL` by the same absence from `KIND_TO_CATEGORY` as today. No new
`ClaudeFailureKind`, `AttemptCategory`, or `TerminationReason` member — each
would otherwise oblige the full per-value contract SEED_FORMAT.md requires
(definition, producer, precedence, consumers, exit path).

**Why `CONFIGURED_TIMEOUT` is permanently excluded.**
`get_last_termination_reason()` already distinguishes `SILENCE_TIMEOUT` (the
heartbeat's own silence-kill) from `CONFIGURED_TIMEOUT` (a caller's explicit
elapsed-time ceiling via `enforce_configured_timeout`/`PLAN_TOOL_CLAUDE_TIMEOUT`)
— both produce the identical `ClaudeFailureKind.TIMEOUT` and the identical
`BACKEND_TIMEOUT_SENTINEL` substring, so `classify()` cannot and does not tell
them apart; only the termination-reason accessor can, and the eligibility rule
must key on it, never on stderr text. A caller that set its own deliberate
wall-clock budget wanted a hard stop, not a connectivity-contingent extension
of it, regardless of what the network is doing. (`run`'s streaming call sites
never set `enforce_configured_timeout`, so for `launcher.shell_invoker` every
`TIMEOUT` is already necessarily a `SILENCE_TIMEOUT` — this exclusion matters
only for `shell.claude_invoke`'s batch lane.) No change to `backend_runner.py`
— it already exposes this accessor read-only; this seed only adds a reader.

**Why a genuinely wedged (non-network) long-running call stays exactly as
terminal as it is today.** If connectivity reads *up* at classification time,
a `SILENCE_TIMEOUT` outcome is not poll-eligible, exactly as it is today — it
falls through to plain `TERMINAL`, with no new retry eligibility. This seed
narrows, not reopens, the "retrying under the same budget nearly always
double-pays wall-clock for another empty kill" rationale (`claude_errors.py:
98-100`, `:576-580`): that reasoning holds fully whenever connectivity is up
(an unexplained wedge, or a caller's own budget expiry) and is deliberately
weakened only in the one case where the call has independent evidence — a
failed probe — that blind retrying was never going to help. **Ordering
requirement:** the termination reason for the attempt that just completed
must be read before any subsequent attempt starts on the same thread (which
would overwrite it) — satisfied by construction today, since classification
already happens synchronously right after each attempt, before the next one
is dispatched.

### The ordering fence: partial-mutation guard runs first, always

**Guarantee, must not drift:** a poll-eligible outcome never bypasses
`git_state.make_partial_mutation_retry_guard` — if anything this matters more
here than for a fast blip, since a long-running call killed after minutes of
real work is far more likely to have partially mutated the tree. The retry
guard is consulted whenever `run_with_rate_limit_recovery` predicts it might
re-invoke the call (`rate_limit_loop.py:163-188`); the fix must widen exactly
that prediction to also cover a poll-eligible outcome, so the guard still
runs — and can still `STOP` — before any poll begins. A poll-eligible
`TRANSIENT` outcome takes the poll path instead of the fixed 2s/4s backoff,
never both; the two are mutually exclusive for the same outcome.

### A caller must be able to opt out entirely — mirroring `recover_rate_limit`

**Decision:** a caller must be able to disable the poll behavior entirely,
independent of its ordinary transient budget — following the exact precedent
`recover_rate_limit: bool` already sets for the RATE_LIMIT category
(`rate_limit_loop.py:116`; wired from `policy.action` at `shell.py:777`), a
**separate, independent-of-budget** toggle, not a budget value doing double
duty as an opt-out signal. This toggle gates only whether a poll-eligible
outcome is actually polled — it does not change whether the outcome *is*
poll-eligible in the first place, which stays a caller-agnostic description of
"what happened," computed the same way regardless of who is asking. The exact
name and plumbing are `detail`'s call; the existence, independence from the
budget, and default (below) are not.

This is not a hypothetical: `roadmap_revision_run.py:shell_local_revision_invoker`
passes `wait_on_rate_limit=False` (→ `recover_rate_limit=False`) *and*
`max_transient_retries=1` specifically to make, in its own docstring's words,
"the one physical local-revision backend request **without recovery**"
(`roadmap_revision_run.py:66-74`). With `max_transient_retries=1`, its ordinary
budget is already exhausted before a first retry — so without this opt-out,
the poll-eligibility rule alone would newly make this explicitly no-recovery
caller retry (and poll, possibly for a long time) whenever connectivity is
down, contradicting the behavior its docstring already commits to.
`run_with_rate_limit_recovery` itself has only two direct call sites
(`launcher.py:679`, `shell.py:760`); `shell_local_revision_invoker` reaches it
two layers down, through `shell.claude_invoke` (`shell.py:504-536`, which
already declares and forwards `wait_on_rate_limit`/`max_transient_retries` by
name — there is no generic passthrough). The new opt-out must be threaded the
same way, as an explicit parameter on `claude_invoke`/`claude_invoke_outcome`
as well as on the leaf, defaulting to "recovery allowed" everywhere except
where `shell_local_revision_invoker` sets it alongside its existing
`recover_rate_limit=False`. No current caller of `launcher.shell_invoker`
needs the same opt-out, so extending that path is left to `detail` only if a
need appears.

### The poll arm, its two independent bounds, and the self-correcting budget

Once the retry guard clears (`RETRY`) on a poll-eligible outcome whose caller
has not opted out: call a new poll-wait seam — interruptible the same way
`wait_until_epoch` already is (`q`/Esc/Ctrl+C) — instead of the fixed
exponential-backoff sleep or a plain terminal return, and do **not** increment
the ordinary transient-attempt count. If connectivity is up (so the outcome
was never poll-eligible), behavior for both shapes is unchanged: an ordinary
`TRANSIENT` keeps today's fixed backoff, and a `SILENCE_TIMEOUT` `TIMEOUT`
stays `TERMINAL`.

**There is no retry-count bound on the poll itself** — polling is not a
sequence of discrete retries, it is one continuous (or periodically-checked)
wait for a single condition to flip, ended by exactly one of: connectivity
returns, the operator aborts (TTY only), or the non-interactive cap elapses.
Two *existing* bounds carry over unchanged and remain the only limits in this
design:

1. **The ordinary transient budget, `max_transient_retries`.** Unaffected by
   polling — since `transient_attempts` is never incremented while polling,
   an ordinary blip that recurs after connectivity returns still gets the full
   2-attempt allowance, not a partially consumed one.
2. **The non-interactive poll cap**, mirroring `MAX_RATE_LIMIT_WAIT_SECONDS`'s
   existing 86400s (24h) ceiling on the rate-limit wait. An interactive TTY
   session's poll is abortable via the same key-check UI `wait_until_epoch`
   already wires, with **no separate hard ceiling** beyond operator control. A
   no-TTY caller (`can_prompt()` false — the same check `ASK` already uses)
   gets the real ceiling instead: past it, the call surfaces `TERMINAL` with an
   actionable resume hint, rather than spinning forever with nothing watching
   to abort it.

This makes the design self-correcting against a false-positive probe (e.g. a
captive portal that lets a raw TCP connect through while the real backend stays
blocked): since polling never spends the transient budget, the very next
attempt — even if it transient-fails again immediately — still has the full
ordinary bounded-backoff allowance available, rather than the poll having
silently consumed it.

### Observability: one new open-string value, no schema change

`backend_recovery_wait.reason` is documented today (`DATA_CONTRACT.md:850`) as
`"rate_limit"` or `"transient"` — the loop's two existing sleep seams. This adds
a third value, `"connectivity"`, through the same `claude_errors.py` wrapper
pattern as `make_backend_recovery_wait_seam` / `make_backend_recovery_sleep_seam`
(mirror its shape rather than inventing a new one). `run_log.py`'s `reason`
field is already an open string (no schema migration), but `DATA_CONTRACT.md`'s
table is the durable documentation of the vocabulary and must gain the new row.

### Prior art for the injectable-real-network-default shape

`plan_tool/model_specs.py` already carries the precedent this seed follows: a
default that hits the network via stdlib, is fully injectable, and whose
failure is never fatal — with no autouse pytest guard the way there is for
spawning the real backend binary (`tests/conftest.py`'s autouse gate covers
backend *binaries*, not this kind of network touch). Follow the same
discipline here: every test overrides the probe/poll-wait seams exactly as
existing tests already override `wait`/`sleep`/`retry_guard`; none makes a real
socket call. No new autouse fixture.

## In scope

`plan_tool/rate_limit_loop.py` (the widened retry-candidate computation and the
new opt-out toggle), `plan_tool/claude_errors.py` (default probe + poll-wait +
the poll-eligibility computation, reading the existing
`get_last_termination_reason()`), `plan_tool/launcher.py` (wiring — unchanged
unless a caller needs a non-default override), `plan_tool/shell.py`
(`claude_invoke`/`claude_invoke_outcome` gain and forward the new opt-out
parameter, since `roadmap_revision_run.py` reaches the leaf only through
them), `roadmap_revision_run.py:shell_local_revision_invoker` (sets the new
opt-out toggle to disable connectivity recovery, alongside its existing
`wait_on_rate_limit=False`, preserving its documented no-recovery contract),
`docs/how-to/pipeline/run.md`, `DATA_CONTRACT.md`, `RUNBOOK.md`, `TESTING.md`, `tests/`.
**Not** `plan_tool/backend_runner.py` — it already exposes
`get_last_termination_reason()`/`TerminationReason` read-only; nothing there
needs to change.

### Scope contract

- **Binary observable, in one sentence:** a `socket.create_connection` attempt
  to a fixed IP:port pair succeeds or fails within a short timeout. Nothing
  about *why* it failed, no latency/quality judgment, no distinguishing "the
  provider is down" from "my network is down" beyond this one check.
- **Allowed behavior changes:** the new poll-instead-of-terminal path for a
  connectivity-confirmed-down `TRANSIENT` failure, and for a
  `SILENCE_TIMEOUT`-killed call with connectivity confirmed down; the third
  `backend_recovery_wait.reason` value. Nothing else user-visible — ordinary
  transient-blip behavior with connectivity up, a `CONFIGURED_TIMEOUT` kill, a
  genuinely wedged call with connectivity up, `RATE_LIMIT`, `PLAN_QUOTA`, and
  the partial-mutation guard's precedence are all unchanged.
- **Allowed reorganization:** none.
- **Verification:** § Testing below.
- **Stop / defer:** § Deferred, and anything the iteration loop surfaces
  outside this fence goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied as
  plan expansion.

## Out of scope

- BACKLOG #119 (snapshot-restore-then-retry) and #120 (retry-guard hardening).
  Those change *what happens when a retry is allowed*; this changes *how long
  the loop waits before giving up*. Independent, composing only through the
  shared `retry_guard` consult.
- Any CLI-surfaced configuration for the new poll's interval, cap, or probe
  targets — these stay code-level constants, matching how
  `max_transient_retries` and `_KILL_AFTER_SILENCE_S` are handled today.
- A network-quality, latency, or diagnostics feature of any kind — the probe
  is a bare reachability check, nothing more.
- Migrating or backfilling any historical run-log data.
- Any change to `backend_runner.py`, `_KILL_AFTER_SILENCE_S`,
  `_STALL_THRESHOLD_S`, or the kill ladder's terminate/grace/kill sequence
  itself — this seed only adds a reader of the `TerminationReason` it already
  produces.

## Risks

- **False-positive probe (captive portal / proxy)** — a raw TCP connect can
  succeed while the real backend stays unreachable. Mitigated by the
  self-correcting budget property in § Architecture: polling never spends
  `transient_attempts`, so a probe-cleared retry that immediately fails again
  still has the ordinary bounded-backoff allowance intact.
- **Unattended run with a permanently broken network** — mitigated by the
  non-interactive cap; past it the call surfaces `TERMINAL` with a resume hint
  rather than spinning forever with no operator watching.
- **Test suite opening real sockets** — mitigated by the injected-seam
  discipline (§ Architecture's prior-art note); every test stubs the probe.
- **A no-recovery caller silently gaining recovery** — `roadmap_revision_run.py:
  shell_local_revision_invoker` already opts out of all recovery
  (`wait_on_rate_limit=False` and `max_transient_retries=1`, per its own
  "without recovery" docstring). Without a separate, budget-independent
  opt-out (mirroring the existing `recover_rate_limit` boolean), the poll
  would fire regardless of budget and silently break that contract. Mitigated
  by requiring this caller to set the new opt-out explicitly — the same shape
  as its existing `recover_rate_limit=False` — rather than inferring opt-out
  from `max_transient_retries`'s value.
- **`SILENCE_TIMEOUT`/`CONFIGURED_TIMEOUT` misattribution** — both currently
  produce the identical `ClaudeFailureKind.TIMEOUT` and
  `BACKEND_TIMEOUT_SENTINEL` text, so getting this wrong would either make a
  caller's explicit elapsed-time ceiling connectivity-contingent (should never
  happen) or leave a genuine long-running-call outage unrecovered (the gap
  this seed exists to close). Mitigated by keying exclusively off
  `get_last_termination_reason()`'s enum value, never off stderr text, and by
  the ordering requirement in § Architecture (classify before the next
  attempt starts).
- **A long-running call is more likely to have partially mutated the tree
  than a fast blip** — not a new risk, but a sharper instance of one the
  partial-mutation guard already exists for. No new mitigation needed: the
  ordering fence means `retry_guard` still runs first and this is exactly the
  case it is designed to catch.

## Testing

- **Predicate, by mutation of each condition:** `TRANSIENT` + connectivity up +
  budget available → today's fixed backoff, unchanged; `TRANSIENT` +
  connectivity up + budget exhausted → `TERMINAL`, unchanged; `TRANSIENT` +
  connectivity down (any budget state) → poll path entered immediately, budget
  untouched.
- **`SILENCE_TIMEOUT` promotion, by mutation:** `SILENCE_TIMEOUT` + connectivity
  down → poll path entered; `SILENCE_TIMEOUT` + connectivity up → `TERMINAL`,
  unchanged from today; `CONFIGURED_TIMEOUT` + connectivity down → `TERMINAL`,
  never promoted, proving the exclusion is real and not accidental; a
  `SILENCE_TIMEOUT` result with the new opt-out set → `TERMINAL`, no poll.
- **Ordering fence:** a poll-eligible outcome (either shape) *and* an aborted
  turn that left uncommitted tracked/untracked edits still returns `TERMINAL`
  via the existing partial-mutation `retry_guard` — the poll is never reached.
- **Self-correcting budget:** after a poll-driven retry, an immediate second
  `TRANSIENT` failure with connectivity now reading up falls to the ordinary
  fixed-backoff arm with the full, unconsumed `transient_attempts` budget.
- **No retry-count bound on the poll itself:** the poll-wait seam loops purely
  on the probe result (and, on a TTY, the abort key-check), with no internal
  attempt counter to exhaust.
- **Non-interactive cap:** a no-TTY caller's poll surfaces `TERMINAL` with an
  actionable hint after the cap elapses, for both the `TRANSIENT` and the
  `SILENCE_TIMEOUT` shape; an interactive caller's poll is cancellable via the
  same key-check seam `wait_until_epoch` uses, with no cap applied.
- **Observability:** a connectivity-driven wait emits `backend_recovery_wait`
  with `reason="connectivity"` for both shapes; a plain transient sleep still
  emits `reason="transient"`.
- **Both callers:** `shell.claude_invoke` and `launcher.shell_invoker` both
  exercise the new arm identically (shared leaf).
- **No-recovery caller preserved:** `shell_local_revision_invoker`, with
  connectivity confirmed down, still returns `TERMINAL` on its first failure —
  no poll, no retry — proving the new opt-out actually suppresses the poll
  rather than only the ordinary budget doing so.
- **No real sockets:** every new/changed test stubs the connectivity probe;
  none exercises the real default implementation live.

## Acceptance criteria

- A `TRANSIENT` failure with connectivity confirmed down pauses and polls
  instead of counting against `max_transient_retries`, and retries only once a
  probe confirms connectivity is back — never on a blind fixed delay.
- A long-running call the heartbeat silence-kills
  (`TerminationReason.SILENCE_TIMEOUT`) with connectivity confirmed down gets
  the same poll-then-resubmit-only-once-restored treatment; the same call with
  connectivity confirmed up, or a `CONFIGURED_TIMEOUT` kill regardless of
  connectivity, stays exactly as terminal as it is today.
- A `TRANSIENT` failure with connectivity confirmed up is byte-for-byte
  unaffected — identical to today's behavior.
- The partial-mutation `retry_guard` still refuses any retry — connectivity-
  driven or not, either shape — when the aborted turn left a dirty tree.
- `roadmap_revision_run.py:shell_local_revision_invoker` still returns
  `TERMINAL` on its first transient failure with connectivity down, with no
  poll and no retry — its "without recovery" contract is unchanged.
- The poll itself has no retry-count limit; a non-interactive caller's poll is
  capped on wall-clock time and surfaces `TERMINAL` with a resume hint past the
  cap, while an interactive caller's poll is abortable with no separate cap.
- `ClaudeFailureKind`, `AttemptCategory`, and `TerminationReason` are all
  unchanged — zero new closed-vocabulary members.
- No change to `backend_runner.py`, and its existing test suite passes
  entirely unmodified.
- `DATA_CONTRACT.md`'s `backend_recovery_wait.reason` table documents the new
  `"connectivity"` value alongside the existing two.
- Every existing `rate_limit_loop` / `claude_errors` test still passes
  unchanged except where it exercises the widened predicate.
- `BACKLOG.md` #317 is updated to reflect this plan's authoring (per
  CLAUDE.md's backlog-derived-seed convention) once the plan ships.

## Deferred

- A CLI flag for poll interval, non-interactive cap, or probe targets, if real
  operator demand emerges.
- Probing the backend's own API host in addition to the generic connectivity
  check, if evidence shows the generic probe under- or over-fires in practice.
- Folding this loop's resilience improvements together with BACKLOG #119's
  snapshot-restore-then-retry into one combined recovery redesign, if a later
  reviewer finds the two easier to land together than the independence this
  seed assumes.
- Any change to `_KILL_AFTER_SILENCE_S`/`_STALL_THRESHOLD_S`'s values, or to
  the kill ladder's own terminate/grace/kill mechanics — this seed only reads
  the `TerminationReason` those mechanics already produce.

## References

- `BACKLOG.md` #101 — shared recovery-state-machine context for the retry
  route this seed extends.
- `docs/how-to/pipeline/run.md` — rate-limit and transient-recovery seam that defines the
  current recovery boundary.
- `plan_tool/rate_limit_loop.py` — retry-candidate computation named by the
  in-scope behavior.
