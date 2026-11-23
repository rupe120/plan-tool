### Fixed

- Mutating commands preserve existing repository lock markers. If a crash leaves a marker behind, stop every writer for the checkout and inspect the interrupted work before removing the marker at the reported path.
