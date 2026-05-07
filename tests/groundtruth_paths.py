"""Helpers for locating canonical LaTeX ground-truth corpus fixtures."""

from __future__ import annotations

import re
from pathlib import Path

LATEX_CORPUS_ROOT = Path("groundtruth/corpus/latex")


def _doc_id_from_corpus_dir(path: Path) -> str:
    name = path.name
    match = re.search(r"__input__(?:__)?(?P<doc>.+)$", name)
    if match:
        return match.group("doc")
    return name


def corpus_doc_dirs(batch: str | None = None) -> list[Path]:
    if not LATEX_CORPUS_ROOT.exists():
        return []
    dirs = [path for path in LATEX_CORPUS_ROOT.iterdir() if path.is_dir()]
    if batch is not None:
        dirs = [path for path in dirs if f"__{batch}__" in path.name]
    return sorted(dirs, key=lambda path: path.name)


def corpus_doc_ids(batch: str | None = None) -> list[str]:
    ids = {_doc_id_from_corpus_dir(path) for path in corpus_doc_dirs(batch)}
    return sorted(ids)


def corpus_doc_dir(doc_id: str, batch: str | None = None) -> Path:
    candidates = [path for path in corpus_doc_dirs(batch) if _doc_id_from_corpus_dir(path) == doc_id]
    if not candidates and batch is None:
        candidates = [path for path in corpus_doc_dirs(None) if _doc_id_from_corpus_dir(path) == doc_id]
    if not candidates:
        raise FileNotFoundError(f"No canonical LaTeX ground-truth corpus fixture for {doc_id!r}")
    # Prefer the explicitly generated batch_001 fixture over older/pr60 variants when both exist.
    return sorted(candidates, key=lambda path: ("__batch_001__" not in path.name, path.name))[0]


def corpus_tex_path(doc_id: str, batch: str | None = None) -> Path:
    doc_dir = corpus_doc_dir(doc_id, batch)
    exact = doc_dir / f"{doc_dir.name}.tex"
    if exact.exists():
        return exact
    matches = sorted(doc_dir.glob("*.tex"))
    if not matches:
        raise FileNotFoundError(f"No .tex file in canonical corpus fixture {doc_dir}")
    return matches[0]
