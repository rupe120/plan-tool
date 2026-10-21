# The AWS sample: what to copy, what to refuse

**Status (2026-09-08):** dated grounding. The refusals (regex-sniffed approvals, in-band UI tags, unversioned transcripts, socket-as-record, decorative authorization) remain evidence. The "copy the UX concept" recommendation belonged to the retired 2026-08-28 definition and is not a Integration decision; Integration's product definition is in `integration/docs/concepts/integration-mvp-domain-disposition.md`.

Read at `<platform-sample-root>`
(single commit, `0b5f65c`). It is a **workshop demo**, not a product
foundation. Its UX concept is worth copying almost wholesale; almost none of
its mechanics are.

## The decisive finding

**The sample is inception-only.** Every construction node is commented out in
`code/agentcore-runtime/icode-agent/orchestrator.py` (imports, the `agents`
dict, `NODE_NAMES`, and every construction edge), and
`tools/state.py` states it: `_CONSTRUCTION_STAGES: set[str] = set()  #
Construction stages are disabled for the inception-only workshop.` The graph
terminates at an `inception_complete` agent whose prompt tells the user to
"move on to the Construction phase using Kiro", and the UI's only exit is an
external `OpenIdeButton`.

**So the sample proves the half Integration wants for inception and explicitly punts
the half plan-tool already does.** Integration's thesis — the sample's inception UX
plus plan-tool's construction — is not a stretch; it fills the exact gap the
sample leaves open.

## The UX concept to adopt

Four routes only (`app/routes.tsx`); the workspace is `/project/:projectId`.
It is **not one chat** — it is a three-pane workspace:

| Pane | Width | Contents |
| --- | --- | --- |
| Left | 20% | `FileBrowser` (60%) over `ProgressPanel` (40%) |
| Center | 40% | `ChatPanel` — messages, approval pills, thinking indicator, input bar |
| Right | 40% | `DocumentViewer` — one closable tab per artifact, markdown/mermaid/image |

Mobile (<768px) collapses to three tabs: Chat / Files / Documents.

Worth copying: the pane split; documents appearing as tabs as they are
produced; a progress tree of phases → steps; approval presented inline in the
chat; a thinking indicator that names the current tool in human words
(a 27-entry `TOOL_LABELS` map, e.g. `generate_requirements` → "Generating
requirements…"); stage banners between stages.

## The mechanics to refuse, each with the reason

| Sample mechanic | Why it must not be copied |
| --- | --- |
| **Approvals are plain text sniffed by regex.** The frontend renders buttons when `/approve\s*&?\s*continue/i` and `/request\s*changes/i` both match; server-side `_is_approval` matches the literal `"2"`, so any reply containing the character 2 reads as approval. | Integration's `rule-explicit-approval` requires a recorded human approval. Use typed events with an approval id and a recorded decider — never string matching. |
| **Structured UI rides in-band tags** — `[PROGRESS_BANNER]…[/PROGRESS_BANNER]` parsed out of the token stream, with the model instructed to emit them. | Structured UI then depends on model formatting compliance. Emit typed events. |
| **No conversation persistence.** The transcript is React state; `connect()` does `setMessages([])`. Navigating away and back loses it. Resume rebuilds workflow position, never the transcript. | Integration's mob record *is* the product. A conversation must be a first-class durable record. |
| **No versioning anywhere.** The bucket is not versioned; every write is `put_object` in place. ADR-005: "accidental overwrites are permanent." | `rule-durable-artifacts` already requires inspect/version/export/trace. |
| **No database at all** — project metadata is `localStorage` keyed by `user.sub`; the project `description` and `type` are collected and never read again. ADR-009: "Projects are not synced across devices or browsers." | Any group workflow needs server-side state by definition. |
| **No multi-user, no tenancy isolation.** Six Cognito groups exist and are decorative (one read, to print a label). The Identity Pool role grants `s3:GetObject`/`ListBucket` on the whole bucket with no condition — any signed-in user can read every other user's artifacts. ADR-009: "No sharing or collaboration features possible without a backend." | **Mobs cannot be borrowed from the sample — it has no participant model at all.** This is Integration's net-new surface, and it is precisely what the sample says needs a backend. |
| **The browser socket is the only channel**, connecting directly to the AgentCore runtime (`wss://bedrock-agentcore.../runtimes/<arn>/ws`, token smuggled through the subprotocol array). The agent blocks on `await queue.get()` with no timeout; a dropped socket ends the run. | Integration's `rule-durable-work` already says tracked state, not the stream, is the record of truth. |
| **Reconnect corrupts state.** The retry drops `projectName`, so the reconnect lands on a different session id and writes artifacts under the UUID prefix while the file browser still lists the slug prefix. | Resume must rebind the same durable job, not start a differently-keyed one. |
| **State is markdown parsed by client-side regex**, and the round-trip is lossy: skipped stages are written as `[x]` and read back as **completed**. | Phase state is a typed record; render markdown, do not parse it. |
| Two inconsistent project identities (slug for artifacts, UUID for config); two projects named "Bookstore" collide on one S3 prefix. | One durable id, assigned server-side. |

## What the sample confirms about scope

It ships **10 agents + 5 integration hub nodes**, one model, one WebSocket, no
job queue, no database — and it is still only half a lifecycle. That is the
size of an inception-only proof done as a demo. It is a useful calibration for
how much Integration's own inception phase needs in order to be real, and a warning
about how much of it is load-bearing versus scaffolding.
