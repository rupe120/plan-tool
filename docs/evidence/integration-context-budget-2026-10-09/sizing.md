# Sizing the 384 KiB roadmap candidate context ceiling

*Part of the Integration context-budget evidence bundle. Start at the [evidence index](../README.md).*

**Sanitized example, 2026-10-20.** Project identifiers in this bundle use generic
integration names. The byte/token measurements and artifact/receipt hashes below
refer to the original input. `provenance.json` identifies the original measured
payload separately from the sanitized structural example; this copy does not
provide exact-byte replay of that measurement.

**Purpose.** Records how the 384 KiB ceiling was chosen and what the Claude Code and Codex harnesses
cost, measured 2026-10-09. The ceiling shipped in PR #58; this page is the provenance for its value, so a
later change to the value can start from the numbers instead of re-deriving them. The text below moved
verbatim from the BACKLOG #469 entry when that entry was removed on merge.

**How to read it.** Every figure is one run on the owner's interactive configuration (own skills, MCP
servers and instruction files), so a stock install would be lower. The Codex window comes from
`codex debug models` at client 0.162.0; re-run it before relying on the numbers for a newer client.
The measurements gate nothing.

- **Sizing the new ceiling (384 KiB):** the rendered prompt grows with the
  payload: the two measured points (175,269 → 311,815 and 211,712 → 360,960
  bytes in `measurements.json`) fit about 76 KB plus 0.34 × payload of templates
  and receipt, so 384 KiB (393,216) gives a prompt of about 605 KB. Windows:
  Claude reports 1,000,000 (`claude-sonnet-5-5` usage output). Codex does not:
  `codex debug models` (refreshed 2026-10-09, client 0.162.0) lists
  `gpt-6.1-sol` at 272,000 default, 872,000 maximum and 95% effective (about
  258K), with `supports_experimental_context` false, so 272K is the working
  window; the owner's earlier 1,000,000-token figure is not what the Codex
  catalog reports. Measured on Codex 2026-10-09: the real 211,712-byte Integration
  payload costs 51,307 input tokens (70,471 with it, 19,164 bare), 4.13 bytes
  per token. A 605 KB prompt is therefore about 147K tokens, and with 19K–42K of
  harness about 166K–189K: 64–73% of the effective window. A 512 KiB ceiling
  (about 780 KB, 189K tokens, 209K–231K with harness) also fits, at 81–90%, but
  leaves little for output, a retry's appended correction and the review pair,
  which is why the ceiling is 384 KiB. One payload and one run; a differently
  shaped payload may tokenize differently, and the repo's
  `prompt_budget.BYTES_PER_TOKEN` (3.5) is more conservative than this
  measurement. The prompt travels as one argv element: on macOS a 1,000,000-byte
  argument spawned (`ARG_MAX` 1,048,576, measured 2026-10-09), leaving about
  400 KB of headroom at 384 KiB; Linux's per-argument limit is unverified here.
  256 KiB leaves only 50,432 bytes of headroom over the measured context (81%
  used). The window does not set the ceiling alone: cost, latency and
  long-context quality matter too.
- **Harness baseline (measured 2026-10-09):** one trivial prompt per backend,
  stdin closed, `--ephemeral`, on the owner's interactive configuration.
  Claude Code (`claude-sonnet-5-5`): about 37,600 input tokens from an empty
  directory and 76,100 from this repo (+38,500, dominated by the 106 KB project
  `CLAUDE.md`). Codex 0.162.0 (`gpt-6.1-sol`): 19,172 with project docs
  disabled (`-c project_doc_max_bytes=0`), 26,519 by default, and 43,174 with
  the cap raised to 400,000 (all three on the 106,151-byte `CLAUDE.md`; the
  41,662 figure below was taken on the evidence-split branch's 98,637-byte file,
  which accounts for the 1.5K difference). Codex's default therefore reads about 7.3K of the
  file's roughly 24K tokens, about the first 32 KiB; `AGENTS.md` is a symlink
  to `CLAUDE.md`, so Codex sessions see roughly the first third of the rules.
  Raised to 128 KiB on the owner's machine 2026-10-09 (`project_doc_max_bytes`
  in `~/.codex/config.toml`): a Codex session here then starts at 41,662 tokens.
  For the ceiling choice, harness overhead matters only against Codex's 272K
  window, which is why 384 KiB and not larger.
  One run each, with the owner's own skills, MCP servers, and instruction
  files included; a stock install would be lower. Plan-tool's own subprocess
  calls were not measured.
