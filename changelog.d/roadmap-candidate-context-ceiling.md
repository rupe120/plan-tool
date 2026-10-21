### Changed

- A roadmap candidate proposal now admits a canonical context up to 384 KiB, up from 192 KiB, so a legitimate follow-up on a modest roadmap is no longer refused before a model call with `full canonical batch payload exceeds the fixed context ceiling`. Candidates already stored under the 64 KiB or 192 KiB ceiling keep that ceiling and their exact bytes.

### Fixed

- Re-running the proposal for a selector-era roadmap candidate stored under the 64 KiB ceiling no longer fails with `candidate capsule cannot be reproduced from its predecessor`. A stored capsule is now reproduced at the ceiling it was issued under, so a later ceiling change cannot break re-entry, review, or promotion of an existing candidate.
