"""SemanticBackend abstract base class.

The three Plan 005_0 backends (regex, GROBID, DeepSeek-VL2) are wrapped
by adapters that implement this interface. The ensemble runner takes a
list of :class:`SemanticBackend` instances and merges their outputs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pdf2md.models.cross_ref import CrossReferenceGraph


class SemanticBackend(ABC):
    """Abstract base for in-tree semantic backend adapters.

    Implementations wrap one of the standalone ``backend/semantic/<name>/``
    backends, convert its native output into a
    :class:`CrossReferenceGraph`, and report a stable backend name and
    version string.

    Implementations MUST NOT import heavy runtime dependencies (``torch``,
    ``transformers``, etc.) at module level from the main pdf2md env.
    The VLM adapter uses subprocess to bridge into its isolated env.
    """

    @abstractmethod
    def name(self) -> str:
        """Return the backend identifier (``"regex"``, ``"grobid"``, ``"vlm"``)."""

    @abstractmethod
    def version(self) -> str:
        """Return a stable version string for the backend implementation."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` iff the backend can run on the current host.

        Used by the ensemble runner and the CLI to skip backends whose
        runtime preconditions (Docker daemon, GPU + conda env) are not
        met, without raising.
        """

    @abstractmethod
    def extract(
        self,
        pdf_path: Path | None,
        text: str | None,
        output_dir: Path,
    ) -> CrossReferenceGraph:
        """Run the backend and return a :class:`CrossReferenceGraph`.

        Args:
            pdf_path: Path to the source PDF, or ``None`` when the backend
                operates on raw text (regex). Backends that require a PDF
                raise :class:`ValueError` when this is ``None``.
            text: Pre-extracted plain text, or ``None`` when the backend
                operates directly on the PDF (GROBID, VLM).
            output_dir: Directory where the backend may write transient
                artefacts (TEI XML, VLM responses). The
                :class:`CrossReferenceGraph` itself is returned to the
                caller and not written by the adapter.

        Returns:
            A populated :class:`CrossReferenceGraph` with the backend's
            name registered in ``backend_versions``.

        Raises:
            ValueError: If required inputs are missing for this backend.
            RuntimeError: If the backend errors out at runtime in a way
                that is NOT an environmental gating failure. Adapters MUST
                check :meth:`is_available` first and short-circuit via
                an empty graph rather than raising on environment misses.
        """
