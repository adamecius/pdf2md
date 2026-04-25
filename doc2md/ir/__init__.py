"""Public DocIR API."""

from doc2md.ir.ids import make_block_id, make_document_id, make_media_id, make_page_id
from doc2md.ir.normalise import normalise_text
from doc2md.ir.schema import BackendRun, BlockIR, DocumentIR, MediaRef, PageIR, Provenance
from doc2md.ir.serialise import from_dict, from_json, to_dict, to_json

__all__ = [
    "BackendRun",
    "BlockIR",
    "DocumentIR",
    "MediaRef",
    "PageIR",
    "Provenance",
    "from_dict",
    "from_json",
    "make_block_id",
    "make_document_id",
    "make_media_id",
    "make_page_id",
    "normalise_text",
    "to_dict",
    "to_json",
]
