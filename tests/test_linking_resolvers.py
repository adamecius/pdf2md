from pathlib import Path

from pdf2md.linking.extract import extract_link_candidates
from pdf2md.linking.resolvers import *
from pdf2md.models.entities import EntityProposalDocument
from pdf2md.models.ir import ConsensusIR
from pdf2md.models.linked import LinkedNodeType, LinkedRelationType, LinkStatus
from pdf2md.models.priors import CalibrationPriorDocument

FIX=Path('tests/data/linking_fixtures')

def cands(name):
    base=FIX/name
    consensus=ConsensusIR.model_validate_json((base/'consensus_ir.json').read_text())
    ents={p.stem:EntityProposalDocument.model_validate_json(p.read_text()) for p in (base/'entities').glob('*.json')}
    priors={p.stem:CalibrationPriorDocument.model_validate_json(p.read_text()) for p in (base/'priors').glob('*.json')}
    return extract_link_candidates(consensus=consensus,entities_by_backend=ents,priors_by_backend=priors)

def has(result, rt):
    return [l for l in result.links if l.relation_type == rt]


def test_reading_order_follows_excludes_page_numbers():
    result=resolve_reading_order(cands('toc_footnotes_references'))
    assert has(result, LinkedRelationType.FOLLOWS)
    assert all('p1:b2' not in (l.source_candidate_id,l.target_candidate_id) for l in result.links)


def test_section_hierarchy_contains_body_blocks():
    result=resolve_section_hierarchy(cands('simple_document'))
    assert has(result, LinkedRelationType.CONTAINS)


def test_section_hierarchy_warns_missing_level():
    result=resolve_section_hierarchy(cands('simple_document'))
    assert any(w.startswith('section_level_missing') for w in result.warnings)


def test_toc_links_to_introduction():
    result=resolve_toc_links(cands('toc_footnotes_references'))
    assert len(has(result, LinkedRelationType.TOC_POINTS_TO)) == 1


def test_toc_missing_warns():
    items=cands('simple_document')
    toc=items[1].__class__(**{**items[1].__dict__, 'node_type': LinkedNodeType.TOC_ENTRY, 'text':'Missing .... 9'})
    result=resolve_toc_links([items[0], toc])
    assert any(w.startswith('toc_target_missing') for w in result.warnings)


def test_page_number_sequence_links_roman_and_arabic():
    result=resolve_page_number_sequence(cands('toc_footnotes_references'))
    assert has(result, LinkedRelationType.PAGE_NUMBER_SEQUENCE_NEXT)


def test_repeating_headers_and_footers():
    base=cands('simple_document')[0]
    h1=base.__class__(**{**base.__dict__, 'consensus_block_id':'con:doc:p1:b9','node_type':LinkedNodeType.HEADER,'text':'Journal','page_no':1})
    h2=base.__class__(**{**base.__dict__, 'consensus_block_id':'con:doc:p2:b9','node_type':LinkedNodeType.HEADER,'text':'Journal','page_no':2})
    f1=base.__class__(**{**base.__dict__, 'consensus_block_id':'con:doc:p1:b8','node_type':LinkedNodeType.FOOTER,'text':'Footer','page_no':1})
    f2=base.__class__(**{**base.__dict__, 'consensus_block_id':'con:doc:p2:b8','node_type':LinkedNodeType.FOOTER,'text':'Footer','page_no':2})
    result=resolve_repeating_headers_footers([h1,h2,f1,f2])
    assert has(result, LinkedRelationType.HEADER_REPEATS_AS)
    assert has(result, LinkedRelationType.FOOTER_REPEATS_AS)


def test_caption_links_nearest_figure():
    result=resolve_captions(cands('simple_document'))
    assert has(result, LinkedRelationType.CAPTION_OF)


def test_caption_missing_warns():
    items=[c for c in cands('simple_document') if c.node_type == LinkedNodeType.CAPTION]
    result=resolve_captions(items)
    assert any(w.startswith('caption_target_missing') for w in result.warnings)


def test_footnote_anchor_links_and_avoids_page_number():
    result=resolve_footnotes(cands('toc_footnotes_references'))
    links=has(result, LinkedRelationType.FOOTNOTE_ANCHOR_FOR)
    assert links and 'p2:b5' not in links[0].source_candidate_id


def test_footnote_missing_warns():
    fn=next(c for c in cands('toc_footnotes_references') if c.node_type == LinkedNodeType.FOOTNOTE)
    result=resolve_footnotes([fn])
    assert any(w.startswith('footnote_anchor_missing') for w in result.warnings)


def test_equation_sequence():
    assert has(resolve_equation_sequence(cands('toc_footnotes_references')), LinkedRelationType.EQUATION_SEQUENCE_NEXT)


def test_figure_table_sequence():
    items=cands('simple_document')
    fig=next(c for c in items if c.node_type==LinkedNodeType.FIGURE)
    fig2=fig.__class__(**{**fig.__dict__,'consensus_block_id':'con:doc:p2:b2','page_no':2})
    assert has(resolve_figure_table_sequence([fig, fig2]), LinkedRelationType.FIGURE_SEQUENCE_NEXT)


def test_references_sequence_and_body_mentions():
    result=resolve_references(cands('toc_footnotes_references'))
    assert has(result, LinkedRelationType.REFERENCE_SEQUENCE_NEXT)
    assert has(result, LinkedRelationType.REFERENCES)


def test_references_missing_section_warning():
    items=[c for c in cands('toc_footnotes_references') if c.node_type == LinkedNodeType.REFERENCE_ITEM]
    result=resolve_references(items)
    assert 'reference_section_missing' in result.warnings


def test_run_all_resolvers_combines_links_and_warnings():
    result=run_all_resolvers(cands('toc_footnotes_references'))
    types={l.relation_type for l in result.links}
    assert LinkedRelationType.FOLLOWS in types
    assert LinkedRelationType.TOC_POINTS_TO in types
    assert isinstance(result.warnings, tuple)


def _copy_candidate(base, **updates):
    return base.__class__(**{**base.__dict__, **updates})


def test_page_number_conflict_does_not_link_arbitrary_adjacent_pages():
    base = cands('toc_footnotes_references')[0]
    p1 = _copy_candidate(base, consensus_block_id='con:doc:p1:b90', node_type=LinkedNodeType.PAGE_NUMBER, text='10', page_no=1, order=90)
    p2 = _copy_candidate(base, consensus_block_id='con:doc:p2:b90', node_type=LinkedNodeType.PAGE_NUMBER, text='99', page_no=2, order=90)
    result = resolve_page_number_sequence([p1, p2])
    assert not result.links
    assert result.warnings == ('page_number_sequence_gap:con:doc:p1:b90',)


def test_page_number_roman_to_arabic_switch_is_low_confidence():
    base = cands('toc_footnotes_references')[0]
    p1 = _copy_candidate(base, consensus_block_id='con:doc:p1:b90', node_type=LinkedNodeType.PAGE_NUMBER, text='iv', page_no=1, order=90)
    p2 = _copy_candidate(base, consensus_block_id='con:doc:p2:b90', node_type=LinkedNodeType.PAGE_NUMBER, text='1', page_no=2, order=90)
    result = resolve_page_number_sequence([p1, p2])
    assert result.links[0].status == LinkStatus.RESOLVED_LOW_CONFIDENCE


def test_equation_number_gap_warns_and_does_not_link():
    eqs = [c for c in cands('toc_footnotes_references') if c.node_type == LinkedNodeType.EQUATION]
    gapped = [_copy_candidate(eqs[0], text='x (1)'), _copy_candidate(eqs[1], text='y (3)')]
    result = resolve_equation_sequence(gapped)
    assert not result.links
    assert result.warnings == (f'equation_sequence_gap:{gapped[0].consensus_block_id}',)


def test_equation_metadata_numbers_link_when_consecutive():
    eqs = [c for c in cands('toc_footnotes_references') if c.node_type == LinkedNodeType.EQUATION]
    numbered = [_copy_candidate(eqs[0], text='x', metadata={'number': 4}), _copy_candidate(eqs[1], text='y', metadata={'number': 5})]
    assert has(resolve_equation_sequence(numbered), LinkedRelationType.EQUATION_SEQUENCE_NEXT)


def test_figure_sequence_gap_warns_and_does_not_link():
    base = cands('simple_document')[0]
    f1 = _copy_candidate(base, consensus_block_id='con:doc:p1:b2', node_type=LinkedNodeType.FIGURE, text='', page_no=1, order=2, metadata={'number': 1})
    f2 = _copy_candidate(base, consensus_block_id='con:doc:p2:b2', node_type=LinkedNodeType.FIGURE, text='', page_no=2, order=2, metadata={'number': 3})
    result = resolve_figure_table_sequence([f1, f2])
    assert not result.links
    assert result.warnings == ('figure_sequence_gap:con:doc:p1:b2',)


def test_table_sequence_metadata_numbers_link_when_consecutive():
    base = cands('simple_document')[0]
    t1 = _copy_candidate(base, consensus_block_id='con:doc:p1:b4', node_type=LinkedNodeType.TABLE, text='', page_no=1, order=4, metadata={'number': 1})
    t2 = _copy_candidate(base, consensus_block_id='con:doc:p2:b4', node_type=LinkedNodeType.TABLE, text='', page_no=2, order=4, metadata={'number': 2})
    assert has(resolve_figure_table_sequence([t1, t2]), LinkedRelationType.TABLE_SEQUENCE_NEXT)


def test_caption_adjacent_page_target_is_low_confidence():
    items = cands('simple_document')
    fig = next(c for c in items if c.node_type == LinkedNodeType.FIGURE)
    cap = next(c for c in items if c.node_type == LinkedNodeType.CAPTION)
    cap = _copy_candidate(cap, page_no=2, consensus_block_id='con:doc:p2:b3')
    result = resolve_captions([fig, cap])
    assert result.links[0].status == LinkStatus.RESOLVED_LOW_CONFIDENCE


def test_caption_ambiguous_target_warns():
    items = cands('simple_document')
    fig = next(c for c in items if c.node_type == LinkedNodeType.FIGURE)
    fig2 = _copy_candidate(fig, consensus_block_id='con:doc:p1:b4', order=4)
    cap = next(c for c in items if c.node_type == LinkedNodeType.CAPTION)
    cap = _copy_candidate(cap, order=3)
    result = resolve_captions([fig, fig2, cap])
    assert any(w.startswith('caption_target_ambiguous') for w in result.warnings)


def test_toc_ambiguous_target_warns():
    items = cands('toc_footnotes_references')
    toc = next(c for c in items if c.node_type == LinkedNodeType.TOC_ENTRY)
    target = next(c for c in items if c.text == '1 Introduction')
    duplicate = _copy_candidate(target, consensus_block_id='con:linktoc:p2:b99', order=99)
    result = resolve_toc_links([toc, target, duplicate])
    assert any(w.startswith('toc_target_ambiguous') for w in result.warnings)


def test_footnote_ambiguous_anchor_warns():
    items = cands('toc_footnotes_references')
    para = next(c for c in items if c.text.startswith('Paragraph'))
    para2 = _copy_candidate(para, consensus_block_id='con:linktoc:p2:b99', order=99)
    footnote = next(c for c in items if c.node_type == LinkedNodeType.FOOTNOTE)
    result = resolve_footnotes([para, para2, footnote])
    assert any(w.startswith('footnote_anchor_ambiguous') for w in result.warnings)


def test_author_year_reference_links_to_matching_item():
    base = cands('toc_footnotes_references')[0]
    para = _copy_candidate(base, consensus_block_id='con:doc:p1:b1', node_type=LinkedNodeType.PARAGRAPH, text='Prior work (Author, 2020) applies.', page_no=1, order=1)
    section = _copy_candidate(base, consensus_block_id='con:doc:p2:b1', node_type=LinkedNodeType.REFERENCE_SECTION, text='References', page_no=2, order=1)
    item = _copy_candidate(base, consensus_block_id='con:doc:p2:b2', node_type=LinkedNodeType.REFERENCE_ITEM, text='Author. Example paper. 2020.', page_no=2, order=2)
    assert has(resolve_references([para, section, item]), LinkedRelationType.REFERENCES)


def test_numeric_reference_ambiguous_target_warns():
    base = cands('toc_footnotes_references')[0]
    para = _copy_candidate(base, consensus_block_id='con:doc:p1:b1', node_type=LinkedNodeType.PARAGRAPH, text='See [1].', page_no=1, order=1)
    item1 = _copy_candidate(base, consensus_block_id='con:doc:p2:b2', node_type=LinkedNodeType.REFERENCE_ITEM, text='[1] First.', page_no=2, order=2)
    item2 = _copy_candidate(base, consensus_block_id='con:doc:p2:b3', node_type=LinkedNodeType.REFERENCE_ITEM, text='[1] Duplicate.', page_no=2, order=3)
    result = resolve_references([para, item1, item2])
    assert any(w.startswith('reference_target_ambiguous') for w in result.warnings)


def test_numeric_reference_missing_target_warns():
    base = cands('toc_footnotes_references')[0]
    para = _copy_candidate(base, consensus_block_id='con:doc:p1:b1', node_type=LinkedNodeType.PARAGRAPH, text='See [9].', page_no=1, order=1)
    item = _copy_candidate(base, consensus_block_id='con:doc:p2:b2', node_type=LinkedNodeType.REFERENCE_ITEM, text='[1] First.', page_no=2, order=2)
    result = resolve_references([para, item])
    assert any(w.startswith('reference_target_missing') for w in result.warnings)


def test_pure_page_number_footer_is_not_repeating_footer():
    base = cands('simple_document')[0]
    f1 = _copy_candidate(base, consensus_block_id='con:doc:p1:b8', node_type=LinkedNodeType.FOOTER, text='1', page_no=1)
    f2 = _copy_candidate(base, consensus_block_id='con:doc:p2:b8', node_type=LinkedNodeType.FOOTER, text='1', page_no=2)
    assert not resolve_repeating_headers_footers([f1, f2]).links


def test_numbered_section_hierarchy_creates_parent_of():
    base = cands('simple_document')[0]
    s1 = _copy_candidate(base, consensus_block_id='con:doc:p1:b1', node_type=LinkedNodeType.SECTION, text='1 Methods', order=1)
    s2 = _copy_candidate(base, consensus_block_id='con:doc:p1:b2', node_type=LinkedNodeType.SECTION, text='1.1 Data', order=2)
    assert has(resolve_section_hierarchy([s1, s2]), LinkedRelationType.PARENT_OF)


def test_run_all_resolvers_preserves_gap_warnings():
    eqs = [c for c in cands('toc_footnotes_references') if c.node_type == LinkedNodeType.EQUATION]
    gapped = [_copy_candidate(eqs[0], text='x (1)'), _copy_candidate(eqs[1], text='y (3)')]
    result = run_all_resolvers(gapped)
    assert any(w.startswith('equation_sequence_gap') for w in result.warnings)
