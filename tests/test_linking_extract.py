from pathlib import Path

from pdf2md.linking.extract import consensus_block_to_node_type, entity_support_for_block, extract_link_candidates, normalise_text
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import BlockKind, ConsensusIR
from pdf2md.models.linked import LinkedNodeType
from pdf2md.models.priors import CalibrationPriorDocument

FIX=Path('tests/data/linking_fixtures')

def load(name):
    base=FIX/name
    consensus=ConsensusIR.model_validate_json((base/'consensus_ir.json').read_text())
    entities={p.stem:EntityProposalDocument.model_validate_json(p.read_text()) for p in (base/'entities').glob('*.json')}
    priors={p.stem:CalibrationPriorDocument.model_validate_json(p.read_text()) for p in (base/'priors').glob('*.json')}
    return consensus, entities, priors


def test_normalise_text():
    assert normalise_text(' A\n B  ') == 'a b'


def test_consensus_block_kind_mapping_all_fixture_kinds():
    consensus,_,_=load('toc_footnotes_references')
    mapped={b.kind:consensus_block_to_node_type(b) for p in consensus.pages for b in p.blocks}
    assert mapped[BlockKind.HEADING] == LinkedNodeType.SECTION
    assert mapped[BlockKind.FORMULA] == LinkedNodeType.EQUATION
    assert mapped[BlockKind.BIBITEM] == LinkedNodeType.REFERENCE_ITEM


def test_entity_support_for_block_intersects_candidate_ids():
    consensus,entities,_=load('simple_document')
    support=entity_support_for_block(consensus_block=consensus.pages[0].blocks[0], entities_by_backend=entities)
    assert {e.entity_type for e in support} == {'section'}


def test_toc_entity_refines_paragraph_to_toc_entry():
    consensus,entities,priors=load('toc_footnotes_references')
    candidates=extract_link_candidates(consensus=consensus,entities_by_backend=entities,priors_by_backend=priors)
    toc=next(c for c in candidates if c.text.startswith('1 Introduction'))
    assert toc.node_type == LinkedNodeType.TOC_ENTRY


def test_reference_section_entity_refines_heading():
    consensus,entities,priors=load('toc_footnotes_references')
    cands=extract_link_candidates(consensus=consensus,entities_by_backend=entities,priors_by_backend=priors)
    assert next(c for c in cands if c.text=='References').node_type == LinkedNodeType.REFERENCE_SECTION


def test_one_candidate_per_consensus_block_and_preserves_order_backend_confidence():
    consensus,entities,priors=load('simple_document')
    cands=extract_link_candidates(consensus=consensus,entities_by_backend=entities,priors_by_backend=priors)
    assert len(cands) == sum(len(p.blocks) for p in consensus.pages)
    assert cands[0].page_no == 1 and cands[0].order == 0 and cands[0].source_backend == 'mineru'
    assert cands[0].confidence > 0.5
    assert cands[0].source_entity_ids


def test_mapping_for_all_plan_block_kinds():
    consensus, _, _ = load('toc_footnotes_references')
    sample = consensus.pages[0].blocks[0]
    expected = {
        BlockKind.HEADING: LinkedNodeType.SECTION,
        BlockKind.PARAGRAPH: LinkedNodeType.PARAGRAPH,
        BlockKind.FORMULA: LinkedNodeType.EQUATION,
        BlockKind.FIGURE: LinkedNodeType.FIGURE,
        BlockKind.TABLE: LinkedNodeType.TABLE,
        BlockKind.CAPTION: LinkedNodeType.CAPTION,
        BlockKind.LIST: LinkedNodeType.LIST,
        BlockKind.LIST_ITEM: LinkedNodeType.LIST_ITEM,
        BlockKind.FOOTNOTE: LinkedNodeType.FOOTNOTE,
        BlockKind.PAGE_NUMBER: LinkedNodeType.PAGE_NUMBER,
        BlockKind.HEADER: LinkedNodeType.HEADER,
        BlockKind.FOOTER: LinkedNodeType.FOOTER,
        BlockKind.REFERENCE: LinkedNodeType.REFERENCE_ITEM,
        BlockKind.BIBITEM: LinkedNodeType.REFERENCE_ITEM,
        BlockKind.CODE: LinkedNodeType.CODE,
        BlockKind.UNKNOWN: LinkedNodeType.UNKNOWN,
    }
    for kind, node_type in expected.items():
        assert consensus_block_to_node_type(sample.model_copy(update={"kind": kind})) == node_type


def test_normalise_text_none_is_empty():
    assert normalise_text(None) == ''


def test_extract_without_entities_keeps_base_type():
    consensus, _, priors = load('toc_footnotes_references')
    candidates = extract_link_candidates(consensus=consensus, entities_by_backend={}, priors_by_backend=priors)
    assert next(c for c in candidates if c.text.startswith('1 Introduction')).node_type == LinkedNodeType.PARAGRAPH


def test_extract_without_priors_uses_available_confidence():
    consensus, entities, _ = load('simple_document')
    candidates = extract_link_candidates(consensus=consensus, entities_by_backend=entities, priors_by_backend={})
    assert all(0.0 <= c.confidence <= 1.0 for c in candidates)


def test_extract_metadata_preserves_candidate_ids():
    consensus, entities, priors = load('simple_document')
    candidate = extract_link_candidates(consensus=consensus, entities_by_backend=entities, priors_by_backend=priors)[0]
    assert candidate.metadata['candidate_ids'] == consensus.pages[0].blocks[0].candidate_ids


def test_entity_support_sorted_by_confidence():
    consensus, entities, _ = load('simple_document')
    mineru = entities['mineru'].model_copy(deep=True)
    mineru.entities[0].confidence = 0.1
    support = entity_support_for_block(consensus_block=consensus.pages[0].blocks[0], entities_by_backend={'mineru': mineru, 'paddleocr': entities['paddleocr']})
    assert support[0].confidence >= support[-1].confidence


def test_entity_support_empty_when_no_candidate_overlap():
    consensus, entities, _ = load('simple_document')
    block = consensus.pages[0].blocks[0].model_copy(update={'candidate_ids': ['mineru:linkdoc:p1:b99']})
    assert entity_support_for_block(consensus_block=block, entities_by_backend=entities) == []


def test_reference_item_mapping_from_reference_kind():
    consensus, _, _ = load('simple_document')
    block = consensus.pages[0].blocks[0].model_copy(update={'kind': BlockKind.REFERENCE})
    assert consensus_block_to_node_type(block) == LinkedNodeType.REFERENCE_ITEM


def test_source_entity_ids_include_supporting_entity_ids():
    consensus, entities, priors = load('simple_document')
    candidate = extract_link_candidates(consensus=consensus, entities_by_backend=entities, priors_by_backend=priors)[0]
    assert candidate.source_entity_ids == ('ent:mineru:linkdoc:section:0',)


def test_unknown_kind_maps_to_unknown_node_type():
    consensus, _, _ = load('simple_document')
    block = consensus.pages[0].blocks[0].model_copy(update={'kind': BlockKind.UNKNOWN})
    assert consensus_block_to_node_type(block) == LinkedNodeType.UNKNOWN
