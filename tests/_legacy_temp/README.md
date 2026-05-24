# Temporary Ashcroft/Mermin regression tests

These are temporary sample-specific regression tests.

They depend on `Ashcroft_Mermin_sub.pdf` and existing backend IR JSON artefacts.

- The Ashcroft sample pipeline contract uses `pdf2md.consensus.example.toml`.
- These tests run the real utility CLIs in order.
- They do not run backend extraction.
- The tests may create fresh artefacts under `tmp_path`.
- The generated `.current` folder is not the source of truth for tests unless explicitly requested.

They may be removed after the canonical pre-Docling contract becomes stable.
