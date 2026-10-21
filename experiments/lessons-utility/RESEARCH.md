# Research — libraries for maintaining a "lessons learned" store (2025–2026)

Survey backing the **lessons-utility** experiment. The lessons store is an
accumulated, append-only knowledge base injected into LLM prompts; the design
problem is *selective retrieval + volume control*, which is the same problem
agent-memory frameworks, vector stores, lexical search, and dedup pipelines all
attack from different angles. Sources at the bottom.

## TL;DR

At this repo's current scale (305 bullets, ~400 KB on disk, ~100 K tokens —
see `measure_lessons.py`), **vector search is overkill**. The real win is
*selecting the right N bullets* instead of recency-truncating to the newest
48 KB (which today drops 88.5% of the corpus blindly). The pragmatic path:

1. **Lexical retrieval** — SQLite **FTS5** (zero new dep) or **`bm25s`**
   (pure-Python, fast) to inject the top-K *relevant* bullets per task.
2. **Write-time dedup** — **`datasketch`** MinHash/LSH near-duplicate gate
   (complements the existing substring dedupe + the Claude equivalence primitive).
3. **Salience scoring** — `project-citations.jsonl` already records which
   lessons get cited; rank by recency + citation count and cap the injected
   budget at top-K. **This is the cheapest single improvement and needs no new
   dependency.**

Defer embeddings (**sqlite-vec** / **fastembed**) and scheduled LLM compaction
until lexical recall visibly misses paraphrased lessons or the store crosses
~1–2 K bullets. Don't adopt a full agent-memory framework for a CLI lessons
file — borrow their extraction / dedup / decay / temporal ideas instead.

## 1. Agent memory frameworks (borrow ideas, don't embed the runtime)

| Framework | What it is | Weight | Local/offline | License | Use when |
|---|---|---|---|---|---|
| **mem0** | Memory layer; hybrid vector+graph+KV; LLM-driven extraction, dedup/merge, update. Largest community (~48k★). | Heavy — needs LLM + vector backend | Self-host path, but extraction calls an LLM + store | Apache-2.0 (core) | You run an agent and want managed-ish memory; **overkill for a CLI** |
| **Letta (ex-MemGPT)** | OS-memory metaphor: core (in-context) / recall / archival tiers; self-edits memory. | Heavy — stateful server runtime | Fully OSS self-host | Apache-2.0 | Autonomous agent paging its own memory; **far too much runtime here** |
| **Zep / Graphiti** | Temporal knowledge graph; facts carry validity windows ("true when?"). Strong on temporal retrieval. | Heavy — managed, or self-host Graphiti + graph DB | Self-host via Graphiti | Zep managed / Graphiti Apache-2.0 | Lessons frequently *supersede* each other and you need time-aware truth |
| **Cognee** | ECL pipeline (`add`→`cognify`→`search`); KG + dedup + background "Memify" enrichment (prunes stale, weights hot facts). | Heavy — graph DB + vector + LLM | Positioned local-first; multi-component | OSS (permissive) | You genuinely want a KG over lessons and accept the infra |
| **LangMem** | LangChain long-term memory: summarization + semantic extraction into LangGraph. | Medium; couples to LangChain | Yes (your store/model) | OSS (LangChain) | You're **already** on LangChain/LangGraph |

**Verdict:** all five assume a long-running process + an LLM in the extraction
loop. For a single-binary CLI, adopt the *patterns* (extraction at write time,
dedup/merge, salience, decay, temporal validity) directly. The ideas worth
stealing: Cognee's **Memify** (periodic prune-stale + weight-hot) and Zep's
**temporal validity** (a lesson can be superseded, not just appended).

## 2. Lightweight vector / embedding retrieval (defer until ~1–2 K bullets)

All embeddable (in-process, no server) unless noted. At small scale the
differentiator is dependency weight, not recall.

| Library | What it is | Weight | License | Use when |
|---|---|---|---|---|
| **sqlite-vec** | SQLite extension for vector search; single file, no server; stable v0.1.0. | **Very light** | Apache-2.0 / MIT | You already touch SQLite and want vectors with ~zero new infra |
| **LanceDB** | Disk-based embedded vector DB; built-in FTS (Tantivy) + SQL filter + rerank; versioning. | Medium | Apache-2.0 | You want **hybrid (vector+lexical) in one engine** and headroom to thousands+ |
| **ChromaDB** | In-process embedded vector DB; metadata filter; 2025 Rust rewrite (~4× faster). | Medium | Apache-2.0 | Easiest "just works" embedded store, deps acceptable |
| **FAISS** | Meta's ANN library; in-memory, fastest raw search; not a DB (no persistence/metadata). | Medium (native) | MIT | Raw ANN speed on a fixed in-memory index; **more than this needs** |
| **usearch** | Tiny single-header ANN engine + Python bindings. | **Very light** | Apache-2.0 | FAISS-like ANN with a much smaller dependency |
| **txtai** | All-in-one embeddings DB: dense+sparse+graph + LLM orchestration. | Medium-heavy | Apache-2.0 | One lib for semantic+lexical+graph in-process |

**Embedding models (only if you go vector):**
- **Local/offline:** `sentence-transformers` (standard; BGE-small/Stella, but
  PyTorch-heavy); **`fastembed`** (Qdrant, ONNX-based, **no PyTorch** — right
  for a CLI wanting local embeddings without a multi-GB install).
- **API (network, paid, not offline):** OpenAI `text-embedding-3-large`, Voyage
  `voyage-3-large`, Cohere Embed v3. Avoid for an offline-first CLI.
- **Caveat:** for hundreds of short bullets, model-load latency can dwarf the
  retrieval benefit. `fastembed` mitigates; lexical (§3) avoids it entirely.

## 3. Lexical / no-embedding retrieval (the right fit at this scale)

| Library | What it is | Weight | License | Use when |
|---|---|---|---|---|
| **SQLite FTS5** | Built-in full-text search, BM25-ranked via `bm25()`. Zero new dep if lessons live in SQLite. | **Zero** | Public domain | Smallest-footprint relevance filter — the default recommendation |
| **bm25s** | Pure-Python BM25 (NumPy/SciPy); sparse-matrix precompute, ~500× faster than rank-bm25, Lucene-class. | Light | MIT | In-memory BM25 without SQLite, fast as the store grows |
| **rank-bm25** | Classic pure-Python BM25; simple, slower. | Very light | Apache-2.0 | Quick prototype; prefer **bm25s** ongoing |
| **tantivy-py** | Rust Lucene-like FTS engine + Python bindings; persistent index. | Medium (native) | MIT | You outgrow FTS5/bm25s and want a real persistent FTS engine |
| **Whoosh** | Pure-Python search lib; largely dormant. | Light | BSD | Generally skip |

## 4. Dedup / clustering / compaction (attacks *volume* directly)

| Technique | What it is | Weight | License | Use when |
|---|---|---|---|---|
| **`datasketch` (MinHash+LSH)** | Probabilistic near-dup detection; Jaccard threshold over n-gram shingles. Sub-second at this scale. | Light (numpy) | MIT | **Write-time gate:** reject/merge a near-duplicate bullet. Highest-leverage volume control |
| **Exact-hash dedup** | Hash normalized text, drop exact repeats. | Zero | — | First-line cheap filter before MinHash (repo already does substring dedupe) |
| **Semantic dedup** | Embed + cosine threshold; catches paraphrases MinHash misses. | §2 weight | — | Once embeddings exist anyway |
| **Clustering (HDBSCAN/k-means)** | Group related lessons; summarize per cluster. | Medium | BSD | Theme-based compaction at hundreds+ |
| **Periodic LLM compaction** | Background job merges/rewrites/prunes stale lessons (Cognee Memify, LangMem summarization). Not in retrieval hot path. | LLM call | — | Scheduled maintenance to keep injected corpus small |
| **Decay / salience scoring** | Track recency + access/citation count; demote low-score entries from the injected set. | Trivial | — | Bound injected token budget at top-K. **`project-citations.jsonl` is a ready-made signal** |

## Recommendation matrix

| Concern | Now (hundreds of bullets) | If it grows to thousands |
|---|---|---|
| **Storage** | Optionally migrate `.md`+`.jsonl` → **SQLite** (keep append semantics, gain indexing) | Same SQLite, or **LanceDB** if vector |
| **Retrieval** | **FTS5** (zero dep) or **bm25s**; inject top-K by score, not the newest 48 KB | Add **sqlite-vec**/**LanceDB** for semantic recall; **hybrid** BM25+vector + rerank |
| **Embeddings** | None — lexical is enough; the gap today is *selection*, not recall | Local **fastembed** or sentence-transformers (BGE-small); API only if already calling an LLM |
| **Dedup** | **datasketch** MinHash + exact-hash prefilter (on top of existing substring + Claude equivalence) | + semantic dedup once embeddings exist |
| **Volume control** | **Salience/decay** from recency + existing citation counts → top-K budget | + **periodic LLM compaction** (cluster→summarize→prune) |
| **Frameworks** | **Skip** mem0/Letta/Zep/Cognee/LangMem — server-shaped | Reconsider **Cognee** / **mem0** only if entity-graph/temporal reasoning is truly needed |

**One-paragraph recommendation.** The current cost/volume problem is a
*selection* problem, not a recall or storage problem: 88.5% of bullets are
dropped by blind recency truncation while the prompt still pays ~12 K tokens
for an arbitrary newest-48 KB slice. Wire the existing `project-citations.jsonl`
into a recency + citation-count salience score, add **FTS5/bm25s** top-K
relevance selection per task, and gate writes with a **datasketch** near-dup
check. That removes the problem at this scale with ~one lightweight dependency
(or zero, with FTS5). Defer embeddings and scheduled compaction until lexical
recall visibly misses paraphrased lessons or the store crosses ~1–2 K bullets.

## Sources

- Best AI Agent Memory Frameworks 2026 (Atlan) — https://atlan.com/know/best-ai-agent-memory-frameworks-2026/
- Letta — https://github.com/letta-ai/letta
- State of AI Agent Memory 2026 (mem0) — https://mem0.ai/blog/state-of-ai-agent-memory-2026
- Mem0 vs Zep vs Letta vs Cognee — https://mcp.directory/blog/mem0-vs-letta-vs-zep-vs-cognee-2026
- Agent Memory Frameworks Tested (Particula) — https://particula.tech/blog/agent-memory-frameworks-tested-mem0-zep-letta-cognee-2026
- Mem0 Open Source overview — https://docs.mem0.ai/open-source/overview
- Cognee / best OSS memory frameworks 2026 (XLR8) — https://tryxlr8.ai/blogs/best-open-source-ai-memory-frameworks-2026
- Survey of AI Agent Memory Frameworks (Graphlit) — https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks
- LanceDB vs ChromaDB — https://aicoolies.com/comparisons/lancedb-vs-chromadb
- Introducing sqlite-vec v0.1.0 — https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html
- Best Vector Databases 2026 (Firecrawl) — https://www.firecrawl.dev/blog/best-vector-databases
- BM25S paper (arXiv) — https://arxiv.org/pdf/2407.03618 ; site — https://bm25s.github.io/
- SQLite FTS5 docs — https://sqlite.org/fts5.html
- txtai — https://github.com/neuml/txtai
- Choosing Embedding Models 2025 (Ailog) — https://app.ailog.fr/en/blog/guides/choosing-embedding-models
- Near-dup detection with LSH + datasketch — https://yorko.github.io/2023/practical-near-dup-detection/
- MinHash LSH (Milvus) — https://milvus.io/blog/minhash-lsh-in-milvus-the-secret-weapon-for-fighting-duplicates-in-llm-training-data.md

_Library facts captured ~2026-06; verify maintenance status before adopting._
