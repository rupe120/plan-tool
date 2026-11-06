# Evidence

*Measured and generated supporting material. Start with the task routes in the
[repository README](../../README.md).*

These records support decisions; they do not replace the operating contracts.

- [Benchmark design](benchmark-design.md)
- [Backend recommendations](backend-recommendations.md)
- [Roadmap layering measurement](roadmap-layering-measurement.md)
- [Roadmap run measurements](roadmap-run-measurements.md)
- [Authored-artifact structure versioning](authored-artifact-structure-versioning.md) — the design and delivery record of the completed format-version plan; follow-ups are `BACKLOG.md` #362–#365
- [Integration context budget, 2026-10-09](integration-context-budget-2026-10-09/) — the historical refusal and measurements with a separately hashed sanitized payload example behind the shipped 384 KiB candidate context ceiling (PR #58) and the model-aware prompt-budget warning (PR #60 and its review follow-up) and `BACKLOG.md` #471; [sizing](integration-context-budget-2026-10-09/sizing.md) records how the ceiling was chosen
- [CLAUDE.md measured incidents](claude-md-measured-incidents.md) — the multi-paragraph dated measurements behind `CLAUDE.md`'s rules, moved verbatim so that file keeps each rule and a short verdict

## Generic integration references

**Naming.** "Integration" in this repository names an external application that consumes `plan-tool`. Paths and commits cited for it, such as `<integration-consumer-root>`, belong to that application's own repository and are not in this one. Entries that mention it are kept as dated provenance.

Integration examples use generic project, client and service names, fixture
names and source paths. Assessment, labor-data and advice services remain
distinct examples; generic application namespaces replace client identifiers.
The 2026-10-20 naming cleanup also normalizes project names in saved report text.
Recorded dates, byte/token measurements, commit IDs, artifact digests and run
identities remain historical observations, not newly measured results for the
renamed examples. The context-budget bundle explicitly separates original input
identity from its sanitized payload; consult its provenance before attempting
exact-byte replay.
