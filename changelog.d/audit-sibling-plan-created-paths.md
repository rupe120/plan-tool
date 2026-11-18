### Changed

- The conceptual audit of a roadmap-derived plan is now shown the paths that the other plans in the same roadmap will create, so it stops reporting those as missing files. Its findings are not filtered, so a finding of that kind is still worth checking against the sibling plans' `creates:`.
- The saved audit revision moves to version 4 and records a `sibling_paths_digest`. After upgrading, a saved audit of a roadmap plan that has sibling plans reads stale once, and re-auditing is enough; a plan without siblings is unchanged, and so is an older saved report of one.
