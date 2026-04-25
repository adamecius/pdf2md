# Project Consistency Audit (Updated 2026-04-25)

This document records the convention decisions requested in review and the resulting repo updates.

## Applied convention choices

1. Use US spelling for new canonical DocIR helper modules:
   - `doc2md/ir/normalize.py`
   - `doc2md/ir/serialize.py`
2. Keep backward compatibility wrappers for prior UK spellings:
   - `doc2md/ir/normalise.py`
   - `doc2md/ir/serialise.py`
3. Use underscore naming for layout backend identifiers in CLI-facing defaults/examples:
   - `doclayout_yolo`
4. Keep `.venv` as the default contributor environment, with conda as optional.

## Verification summary

- CLI help reflects underscore layout naming.
- Tests pass after updating DocIR helper imports to canonical US spellings.
- AGENTS environment guidance is aligned with README (`.venv` default).
