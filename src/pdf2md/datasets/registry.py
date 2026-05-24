"""Registry of supported external ground-truth datasets (Additional Plan 1).

Each :class:`DatasetEntry` describes one dataset the user may install
via ``pdf2md datasets install <name>``. The registry is intentionally
small: the project ships exactly three slots for now — tlc3-examples,
latex-cookbook, and a placeholder for arxiv-curated.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class DatasetStatus(str, Enum):
    """Registry-level availability for a dataset entry."""

    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"


@dataclass(frozen=True)
class DatasetEntry:
    """One external dataset the user can opt into.

    Fields:
        id: canonical dataset id (used on the filesystem and CLI).
        aliases: friendly alternative names accepted by the CLI.
        source_type: only ``"latex"`` for now; reserved for future asset
            types (``"pdf"``, ``"html"``, ...).
        url: git clone URL. Empty string when ``status`` is ``not_available``.
        default_ref: git ref to check out (branch or commit) when the
            caller does not pass ``--ref``.
        licence: free-text licence note for downstream attribution.
        keep_paths: relative paths inside the cloned repository to keep.
            ``"."`` means "keep everything".
        exclude_paths: relative paths to remove after cloning, even when
            they would otherwise be kept.
        root_globs: glob patterns (relative to the dataset root) that
            identify candidate root .tex files. Used by manifest generation.
        root_files: explicit root file paths (overrides root_globs when set).
        recommended_engine: ``"lualatex" | "pdflatex" | "xelatex" | None``.
        description: short human-readable description.
        status: :class:`DatasetStatus`. ``not_available`` entries cannot be
            installed but are still listed by ``pdf2md datasets list``.
    """

    id: str
    aliases: tuple[str, ...] = ()
    source_type: str = "latex"
    url: str = ""
    default_ref: str = ""
    licence: str = ""
    keep_paths: tuple[str, ...] = (".",)
    exclude_paths: tuple[str, ...] = ()
    root_globs: tuple[str, ...] = ()
    root_files: tuple[str, ...] = ()
    recommended_engine: str | None = None
    description: str = ""
    status: DatasetStatus = DatasetStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Registry table
# ---------------------------------------------------------------------------


_REGISTRY: tuple[DatasetEntry, ...] = (
    DatasetEntry(
        id="tlc3-examples",
        aliases=("tlc3",),
        source_type="latex",
        url="https://github.com/FrankMittelbach/tlc3-examples.git",
        default_ref="main",
        licence="LPPL-1.3c (with README-noted exceptions)",
        keep_paths=("NORMAL", "SPECIAL", "SUPPORT", "README.md", "build.lua"),
        exclude_paths=("BOOK-PDFS",),
        root_globs=(
            "NORMAL/**/*.ltx",
            "NORMAL/**/*.ltx2",
            "SPECIAL/**/*.ltx",
            "SPECIAL/**/*.ltx2",
        ),
        description=(
            "Many small isolated examples from The LaTeX Companion 3rd "
            "edition — good for feature-level variety across document "
            "classes, floats, fonts, tables, math and bibliography."
        ),
    ),
    DatasetEntry(
        id="latex-cookbook",
        aliases=("cookbook",),
        source_type="latex",
        url="https://github.com/alexpovel/latex-cookbook.git",
        default_ref="main",
        licence="MIT",
        keep_paths=(".",),
        root_files=("cookbook.tex",),
        recommended_engine="lualatex",
        description=(
            "One realistic multi-file project with media, bibliography, "
            "glossaries, TikZ, tables, chemistry, code highlighting and "
            "LuaLaTeX tooling — good for end-to-end project compilation "
            "stress testing."
        ),
    ),
    DatasetEntry(
        id="arxiv-curated",
        aliases=("arxiv",),
        source_type="latex",
        url="",
        default_ref="",
        licence="varies per paper",
        description=(
            "Placeholder for a curated arXiv paper set. Not downloadable "
            "in Additional Plan 1; reserved for a future plan."
        ),
        status=DatasetStatus.NOT_AVAILABLE,
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_datasets() -> list[DatasetEntry]:
    """Return all registered datasets in canonical id order."""

    return sorted(_REGISTRY, key=lambda entry: entry.id)


def _all_names() -> Iterable[str]:
    for entry in _REGISTRY:
        yield entry.id
        yield from entry.aliases


def get_dataset(id_or_alias: str) -> DatasetEntry:
    """Look up a dataset by id or alias.

    Raises:
        ValueError: when the name is unknown. The error message lists all
            valid choices so the CLI surface is self-discoverable.
    """

    needle = (id_or_alias or "").strip()
    if not needle:
        raise ValueError(
            "Dataset name must not be empty. Valid choices: "
            + ", ".join(sorted(set(_all_names())))
        )
    for entry in _REGISTRY:
        if entry.id == needle or needle in entry.aliases:
            return entry
    raise ValueError(
        f"Unknown dataset {id_or_alias!r}. Valid choices: "
        + ", ".join(sorted(set(_all_names())))
    )


def resolve_alias(name: str) -> str:
    """Return the canonical dataset id for ``name``."""

    return get_dataset(name).id


__all__ = [
    "DatasetEntry",
    "DatasetStatus",
    "get_dataset",
    "list_datasets",
    "resolve_alias",
]
