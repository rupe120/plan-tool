### Fixed

- A roadmap candidate batch whose rows share narrative paragraphs no longer exceeds the context ceiling because each shared paragraph was repeated once per row. The batch now carries each shared paragraph once, so batches that were refused with `full canonical batch payload exceeds the fixed context ceiling` only because of that repetition can be proposed again. Candidates already stored keep their original context and verify unchanged.
