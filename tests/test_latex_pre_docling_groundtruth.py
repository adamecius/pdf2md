import json, subprocess, tempfile
from pathlib import Path


def test_pre_docling_generator_structure():
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)
        subprocess.run(["python","generate_latex_docling_groundtruth.py","--output-root",str(out),"--batch","b1"],check=True)
        subprocess.run(["python","latex_to_pre_docling_groundtruth.py","--root",str(out),"--batch","b1"],check=True)
        d=out/"b1"/"multipage_all_features_references_footnotes"/"groundtruth"/"semantic_document_groundtruth.json"
        sem=json.loads(d.read_text())
        types=[b['type'] for b in sem['body']]
        assert 'section' in types and 'subsection' in types and 'table' in types and 'figure' in types
        assert 'footnote' in types and 'list' in types and 'list_item' in types
        # source order
        assert types.index('section') < types.index('subsection') < types.index('figure')
        # labels resolve
        assert sem['labels']['sec:deep']
        assert any(r['target_label']=='eq:deep' for r in sem['references'])
        # repeated refs preserved
        assert sum(1 for r in sem['references'] if r['target_label']=='eq:deep') == 2
        # table cells emitted
        table=next(b for b in sem['body'] if b['type']=='table')
        assert table.get('table_rows')
        # nested lists preserved
        lists=[b for b in sem['body'] if b['type']=='list']
        assert len(lists) >= 2
        # footnote link
        assert any(rel['type']=='footnote_of' for rel in sem['relations'])
