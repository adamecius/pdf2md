from pathlib import Path

import networkx as nx

from pdf2md.linking.builder import LinkerSettings, build_linked_structure
from pdf2md.linking.io import load_linker_inputs
from pdf2md.models.linked import LinkedNodeType, LinkedRelationType, LinkedStructure, LinkStatus

FIX=Path('tests/data/linking_fixtures')

def build(name, entities=True, priors=True):
    base=FIX/name
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json', consensus_report_path=base/'consensus_report.json', entities_root=base/'entities' if entities else None, priors_root=base/'priors' if priors else None)
    result=build_linked_structure(consensus=loaded.consensus,entities_by_backend=loaded.entities_by_backend,priors_by_backend=loaded.priors_by_backend,consensus_report=loaded.consensus_report,source_consensus_ir=str(base/'consensus_ir.json'),source_consensus_report=str(base/'consensus_report.json'),source_entity_documents=loaded.source_entity_documents,source_prior_documents=loaded.source_prior_documents,settings=LinkerSettings())
    return result, loaded


def rel_types(linked):
    return {r.relation_type for r in linked.relations}


def test_simple_document_builds_valid_linked_structure():
    result,_=build('simple_document')
    assert isinstance(result.linked, LinkedStructure)
    assert result.linked.document_id == 'linkdoc'


def test_document_node_is_created():
    result,_=build('simple_document')
    assert result.linked.nodes[0].node_type == LinkedNodeType.DOCUMENT


def test_every_consensus_block_becomes_node():
    result,loaded=build('simple_document')
    assert len(result.linked.nodes) == 1 + sum(len(p.blocks) for p in loaded.consensus.pages)


def test_all_nodes_derive_from_document_or_consensus():
    result,_=build('simple_document')
    derived=[r for r in result.linked.relations if r.relation_type == LinkedRelationType.DERIVED_FROM_CONSENSUS]
    assert len(derived) == len(result.linked.nodes)-1


def test_expected_simple_relations_present():
    result,_=build('simple_document')
    types=rel_types(result.linked)
    assert LinkedRelationType.FOLLOWS in types
    assert LinkedRelationType.CONTAINS in types
    assert LinkedRelationType.CAPTION_OF in types


def test_expected_toc_footnote_reference_relations_present():
    result,_=build('toc_footnotes_references')
    types=rel_types(result.linked)
    assert LinkedRelationType.TOC_POINTS_TO in types
    assert LinkedRelationType.FOOTNOTE_ANCHOR_FOR in types
    assert LinkedRelationType.REFERENCES in types
    assert LinkedRelationType.EQUATION_SEQUENCE_NEXT in types
    assert LinkedRelationType.REFERENCE_SEQUENCE_NEXT in types


def test_unresolved_ambiguity_creates_linked_conflict_and_warning():
    result,_=build('unresolved_ambiguity')
    assert result.linked.conflicts
    assert any(c.status == LinkStatus.UNRESOLVED for c in result.linked.conflicts)
    assert 'unresolved_semantic_ambiguity' in result.linked.warnings


def test_source_consensus_conflict_is_preserved():
    result,_=build('unresolved_ambiguity')
    assert result.linked.conflicts[0].source_conflict_id == 'conf:linkamb:0'


def test_missing_entities_and_priors_warn_but_build():
    result,loaded=build('simple_document',entities=False,priors=False)
    assert result.linked.nodes
    assert 'entities_root_missing' in loaded.warnings
    assert 'priors_root_missing' in loaded.warnings


def test_pydantic_round_trip():
    result,_=build('toc_footnotes_references')
    assert LinkedStructure.model_validate_json(result.linked.model_dump_json()).document_id == result.linked.document_id


def test_report_counts_match_structure():
    result,_=build('simple_document')
    assert result.report['node_count'] == len(result.linked.nodes)
    assert result.report['relation_count'] == len(result.linked.relations)
    assert result.report['conflict_count'] == len(result.linked.conflicts)


def test_resolver_warnings_are_exposed_with_linked_node_ids():
    result,_=build('simple_document')
    assert any(w.startswith('section_level_missing:node:') for w in result.linked.warnings)
    assert not any(w.startswith('section_level_missing:con:') for w in result.linked.warnings)


def test_equation_gap_warning_becomes_conflict():
    base=FIX/'toc_footnotes_references'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json', consensus_report_path=base/'consensus_report.json', entities_root=base/'entities', priors_root=base/'priors')
    loaded.consensus.pages[1].blocks[4].text = 'a^2+b^2=c^2 (4)'
    result=build_linked_structure(consensus=loaded.consensus,entities_by_backend=loaded.entities_by_backend,priors_by_backend=loaded.priors_by_backend,consensus_report=loaded.consensus_report)
    assert any(c.conflict_type == 'equation_sequence_gap' for c in result.linked.conflicts)


def test_source_document_paths_are_preserved():
    result,_=build('simple_document')
    assert result.linked.source_consensus_ir.endswith('consensus_ir.json')
    assert result.linked.source_consensus_report.endswith('consensus_report.json')
    assert result.linked.source_entity_documents
    assert result.linked.source_prior_documents


def test_low_confidence_threshold_marks_nodes_low_confidence():
    base=FIX/'simple_document'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json', consensus_report_path=base/'consensus_report.json', entities_root=base/'entities', priors_root=base/'priors')
    result=build_linked_structure(consensus=loaded.consensus,entities_by_backend=loaded.entities_by_backend,priors_by_backend=loaded.priors_by_backend,settings=LinkerSettings(low_confidence_threshold=0.99))
    assert any(node.status == LinkStatus.RESOLVED_LOW_CONFIDENCE for node in result.linked.nodes[1:])


def test_report_unresolved_contains_resolver_conflicts():
    base=FIX/'toc_footnotes_references'
    loaded=load_linker_inputs(consensus_ir_path=base/'consensus_ir.json', consensus_report_path=base/'consensus_report.json', entities_root=base/'entities', priors_root=base/'priors')
    loaded.consensus.pages[1].blocks[4].text = 'a^2+b^2=c^2 (4)'
    result=build_linked_structure(consensus=loaded.consensus,entities_by_backend=loaded.entities_by_backend,priors_by_backend=loaded.priors_by_backend,consensus_report=loaded.consensus_report)
    assert any(item['conflict_type'] == 'equation_sequence_gap' for item in result.report['unresolved'])


def test_run_result_exposes_networkx_graph():
    result,_=build('toc_footnotes_references')
    graph=result.graph
    assert isinstance(graph, nx.MultiDiGraph)
    assert graph.number_of_nodes() == len(result.linked.nodes)
    assert graph.number_of_edges() == len(result.linked.relations)


def test_graph_node_ids_match_linked_nodes():
    result,_=build('simple_document')
    assert set(result.graph.nodes) == {node.id for node in result.linked.nodes}


def test_graph_edges_carry_relation_attributes():
    result,_=build('simple_document')
    for _src,_dst,data in result.graph.edges(data=True):
        assert 'relation_type' in data
        assert 'confidence' in data
        assert 'status' in data
