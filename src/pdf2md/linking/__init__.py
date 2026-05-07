"""Document-level semantic linker package."""

from pdf2md.linking.builder import LinkerRunResult, LinkerSettings, build_linked_structure
from pdf2md.linking.extract import LinkCandidate, extract_link_candidates
from pdf2md.linking.io import LinkerLoadResult, load_linker_inputs, write_linker_outputs
from pdf2md.linking.resolvers import ResolverResult, ResolvedLink, run_all_resolvers

__all__ = [
    "LinkCandidate",
    "LinkerLoadResult",
    "LinkerRunResult",
    "LinkerSettings",
    "ResolverResult",
    "ResolvedLink",
    "build_linked_structure",
    "extract_link_candidates",
    "load_linker_inputs",
    "run_all_resolvers",
    "write_linker_outputs",
]
