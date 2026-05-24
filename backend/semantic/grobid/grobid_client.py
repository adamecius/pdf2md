"""Thin HTTP client for a locally-running GROBID service.

Plan 005 keeps this module dependency-light: it uses ``requests`` (already
present in the main ``pdf2md`` conda env, transitively via docling). No
external ``grobid-client-python`` package is required.

The client targets GROBID 0.8.x. The default port is 8070 (the GROBID
default). Override with ``--host`` / ``--port`` on the smoke-test CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests


GROBID_DEFAULT_HOST = "localhost"
GROBID_DEFAULT_PORT = 8070
GROBID_DEFAULT_TIMEOUT_S = 120


class GrobidUnavailableError(RuntimeError):
    """Raised when the GROBID service is not reachable.

    The smoke test reports this as ``env_not_ready`` rather than a
    repository defect (per agent.md test taxonomy: environment failure
    vs real failure).
    """


@dataclass(frozen=True)
class GrobidEndpoint:
    """A GROBID service endpoint.

    Attributes:
        host: Hostname or IP.
        port: TCP port.
        timeout_s: Per-request timeout, in seconds.
    """

    host: str = GROBID_DEFAULT_HOST
    port: int = GROBID_DEFAULT_PORT
    timeout_s: int = GROBID_DEFAULT_TIMEOUT_S

    @property
    def base_url(self) -> str:
        """Return ``http://host:port`` with no trailing slash."""
        return f"http://{self.host}:{self.port}"


def is_alive(endpoint: GrobidEndpoint) -> bool:
    """Return ``True`` iff GROBID answers ``/api/isalive`` with HTTP 200."""
    try:
        resp = requests.get(f"{endpoint.base_url}/api/isalive", timeout=5)
    except requests.RequestException:
        return False
    return resp.status_code == 200 and resp.text.strip().lower() == "true"


def process_fulltext_document(pdf_path: Path, endpoint: GrobidEndpoint) -> str:
    """POST a PDF to ``/api/processFulltextDocument`` and return TEI XML.

    Args:
        pdf_path: Path to a readable PDF file on disk.
        endpoint: GROBID service endpoint.

    Returns:
        The raw TEI XML body of the GROBID response (a string).

    Raises:
        GrobidUnavailableError: If the service is not reachable or the
            request fails with a transport / timeout error.
        RuntimeError: If GROBID returns a non-200 status code.
        FileNotFoundError: If ``pdf_path`` does not exist.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    url = f"{endpoint.base_url}/api/processFulltextDocument"
    try:
        with pdf_path.open("rb") as fh:
            resp = requests.post(
                url,
                files={"input": (pdf_path.name, fh, "application/pdf")},
                data={
                    "consolidateHeader": "0",
                    "consolidateCitations": "0",
                    "includeRawCitations": "1",
                    "segmentSentences": "0",
                },
                timeout=endpoint.timeout_s,
            )
    except requests.RequestException as exc:
        raise GrobidUnavailableError(
            f"GROBID at {endpoint.base_url} did not respond: {exc}"
        ) from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"GROBID returned HTTP {resp.status_code} for {pdf_path}: "
            f"{resp.text[:200]}"
        )
    return resp.text
