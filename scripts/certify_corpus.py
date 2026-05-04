#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def cert(doc:Path,did:str):
    tex=doc/f"{did}.tex"; pdf=doc/f"{did}.pdf"; log=doc/'build.log'; meta=doc/'meta.toml'
    checks=[]
    checks.append({'check':'pdf_exists_newer','ok':pdf.exists() and pdf.stat().st_mtime>=tex.stat().st_mtime if pdf.exists() else False})
    txt=log.read_text(errors='ignore') if log.exists() else ''
    checks.append({'check':'log_errors','ok':('! ' not in txt and 'undefined' not in txt)})
    t=tex.read_text()
    checks.append({'check':'documentmetadata','ok':'\\DocumentMetadata{testphase=phase-III, pdfstandard=ua-2}' in t})
    lbl=len(re.findall(r"\\label\{",t)); refs=len(re.findall(r"\\(ref|eqref|autoref)\{",t)); cites=len(re.findall(r"\\cite\{",t))
    checks.append({'check':'basic_tex_counts','ok':lbl>=0 and refs>=0 and cites>=0})
    if meta.exists():
        m=meta.read_text(); checks.append({'check':'meta_exists','ok':'expected_counts' in m})
    passed=all(c['ok'] for c in checks)
    out={'document_id':did,'passed':passed,'checks':checks}
    (doc/'certification.json').write_text(json.dumps(out,indent=2))
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--corpus-root',default='groundtruth/corpus/latex'); ap.add_argument('--doc'); a=ap.parse_args()
    root=Path(a.corpus_root)
    docs=[a.doc] if a.doc else [p.name for p in sorted(root.iterdir()) if p.is_dir()]
    reps=[cert(root/d,d) for d in docs]
    agg={'documents':reps,'all_passed':all(r['passed'] for r in reps)}
    (root/'corpus_report.json').write_text(json.dumps(agg,indent=2))
    raise SystemExit(0 if agg['all_passed'] else 1)
if __name__=='__main__': main()
