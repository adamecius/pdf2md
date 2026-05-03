import json
import subprocess
import tempfile
from pathlib import Path


def _run_gen(out: Path, verbose: bool = False):
    cmd=["python","generate_latex_docling_groundtruth.py","--output-root",str(out),"--batch","b1"]
    if verbose: cmd.append("--verbose")
    subprocess.run(cmd,check=True)


def test_generator_outputs_and_contracts():
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)
        _run_gen(out, verbose=True)
        batch=out/"b1"
        docs=[d for d in batch.iterdir() if d.is_dir()]
        assert len(docs) >= 20
        assert "multipage_all_features_references_footnotes" in [d.name for d in docs]
        for d in docs:
            did=d.name
            gt=d/"groundtruth"/"source_groundtruth_ir.json"
            prov=d/"groundtruth"/"provenance_manifest.json"
            assert gt.exists() and prov.exists()
            g=json.loads(gt.read_text())
            p=json.loads(prov.read_text())
            for k in ["schema_name","schema_version","document_id","source_type","source_tex","expected_pdf","nodes","labels","references","features"]:
                assert k in g
            for k in ["schema_name","schema_version","document_id","batch","generated_at","source_tex","generated_files","feature_counts"]:
                assert k in p
            assert g["nodes"]
            for lbl,node_id in g["labels"].items():
                t=next((n for n in g["nodes"] if n["id"]==node_id),None)
                assert t
                if lbl.startswith("fig:"): assert t["type"]=="figure"
                if lbl.startswith("tab:"): assert t["type"]=="table"
                if lbl.startswith("eq:"): assert t["type"]=="equation"
                if lbl.startswith("sec:"): assert t["type"]=="section"
                if lbl.startswith("sub:"): assert t["type"]=="subsection"
            tex=(d/"input"/f"{did}.tex").read_text()
            for lbl in g["labels"]: assert f"\\label{{{lbl}}}" in tex
            for r in g["references"]:
                assert "reference_text" in r
                t=next((n for n in g["nodes"] if n["id"]==r["target_node_id"]),None)
                assert t and t["type"]!="reference"
            if did=="two_figures_cross_references":
                assert g["labels"]["fig:one"] != g["labels"]["fig:two"]
            if did=="complex_multi_reference_network":
                assert next(n for n in g["nodes"] if n["id"]==g["labels"]["sec:complex"])["type"]=="section"
                assert next(n for n in g["nodes"] if n["id"]==g["labels"]["sub:mesh"])["type"]=="subsection"
                assert next(n for n in g["nodes"] if n["id"]==g["labels"]["fig:box"])["type"]=="figure"
                assert next(n for n in g["nodes"] if n["id"]==g["labels"]["tab:s"])["type"]=="table"
                assert next(n for n in g["nodes"] if n["id"]==g["labels"]["eq:one"])["type"]=="equation"
            if 'multipage' in did:
                assert g['pages_expected_min'] >= 2
            if did=="multipage_all_features_references_footnotes":
                req={"section","subsection","figure","caption","table","equation","list","list_item","footnote","reference","bibliography_like"}
                node_types={n["type"] for n in g["nodes"]}
                assert req.issubset(node_types)
                assert sum(1 for n in g["nodes"] if n["type"]=="footnote") >= 2
                assert sum(1 for r in g["references"] if r["expected_resolved"]) >= 5
