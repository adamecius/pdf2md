"""Document-level semantic linker package."""

from pdf2md.linking.builder import LinkerRunResult, LinkerSettings, build_linked_structure
from pdf2md.linking.extract import LinkCandidate, extract_link_candidates
from pdf2md.linking.graph_utils import (
    detect_cycles,
    linked_structure_to_graph,
    orphan_nodes,
    reading_order_sort,
    section_ancestors,
)
from pdf2md.linking.io import LinkerLoadResult, load_linker_inputs, write_linker_outputs
from pdf2md.linking.resolvers import ResolvedLink, ResolverResult, run_all_resolvers

__all__ = [
    "LinkCandidate",
    "LinkerLoadResult",
    "LinkerRunResult",
    "LinkerSettings",
    "ResolvedLink",
    "ResolverResult",
    "build_linked_structure",
    "detect_cycles",
    "extract_link_candidates",
    "linked_structure_to_graph",
    "load_linker_inputs",
    "orphan_nodes",
    "reading_order_sort",
    "run_all_resolvers",
    "section_ancestors",
    "write_linker_outputs",
]
