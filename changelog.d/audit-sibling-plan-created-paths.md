### Changed

- The conceptual audit of a roadmap-derived plan is now shown the paths that the other plans in the same roadmap will create, so it no longer reports those as missing files. The audit is told, not filtered: `integrations/shared/DIRECTIVES.md` § T still has you check a finding of that kind against the sibling plans' `creates:`. The audit prompt states plainly when no sibling paths are listed or they could not be determined, and never claims the list is complete.
- The saved audit revision moves to version 4 and records a `sibling_paths_digest`. After upgrading, a saved audit of a roadmap plan that has sibling plans reads stale once, and re-auditing is enough; a plan without siblings is unchanged, and so is an older saved report of one.
