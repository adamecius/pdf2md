import json, tempfile
from pathlib import Path
from generate_latex_docling_groundtruth import main as gen_main
import sys

def test_generator_outputs_and_contracts():
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)
        argv=sys.argv
        sys.argv=["gen","--output-root",str(out),"--batch","b1"]
        try:
            gen_main()
        finally:
            sys.argv=argv
        batch=out/"b1"
        docs=[d for d in batch.iterdir() if d.is_dir()]
        assert len(docs) >= 20
        for d in docs:
            did=d.name
            gt=d/"groundtruth"/"source_groundtruth_ir.json"
            assert gt.exists()
            g=json.loads(gt.read_text())
            assert g["nodes"]
            for r in g["references"]:
                t=next((n for n in g["nodes"] if n["id"]==r["target_node_id"]),None)
                assert t and t["type"]!="reference"
            tex=(d/"input"/f"{did}.tex").read_text()
            for lbl in g["labels"]:
                assert f"\\label{{{lbl}}}" in tex
            node_types={n['type'] for n in g['nodes']}
            assert (g['features']['figures']>0) == ('figure' in node_types)
            if 'multipage' in did:
                assert g['pages_expected_min'] >= 2
