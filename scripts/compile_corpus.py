#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, re
from pathlib import Path

def h(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def input_hash(doc:Path,did:str)->str:
    parts=[h(doc/f"{did}.tex")]
    bib=doc/f"{did}.bib"
    if bib.exists(): parts.append(h(bib))
    for p in sorted((doc/'assets').rglob('*')) if (doc/'assets').exists() else []:
        if p.is_file(): parts.append(h(p))
    return hashlib.sha256(''.join(parts).encode()).hexdigest()

def parse_errors(log:str):
    out=[]
    for i,l in enumerate(log.splitlines(),1):
        if l.startswith('! ') or 'Reference ' in l and 'undefined' in l or 'Citation ' in l and 'undefined' in l: out.append((i,l))
    return out

def compile_doc(doc:Path,did:str,force=False):
    tex=doc/f"{did}.tex"; logp=doc/'build.log'; ih=input_hash(doc,did)
    if logp.exists() and not force:
        first=logp.read_text(errors='ignore').splitlines()[:1]
        if first and first[0].strip()==f"# input_hash={ih}": return True,'skipped'
    cmds=[["lualatex","-interaction=nonstopmode",f"-output-directory={doc}",str(tex)],["lualatex","-interaction=nonstopmode",f"-output-directory={doc}",str(tex)]]
    if (doc/f"{did}.bib").exists() and re.search(r"\\cite\{",tex.read_text()): cmds.insert(1,["biber",did])
    full=[f"# input_hash={ih}"]
    ok=True
    for c in cmds:
        p=subprocess.run(c,capture_output=True,text=True,cwd=doc)
        full.append(f"$ {' '.join(c)}\n{p.stdout}\n{p.stderr}")
        if p.returncode!=0: ok=False
    log='\n'.join(full); logp.write_text(log)
    errs=parse_errors(log)
    return ok and not errs, errs

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--corpus-root',default='groundtruth/corpus/latex'); ap.add_argument('--doc'); ap.add_argument('--force',action='store_true'); a=ap.parse_args()
    root=Path(a.corpus_root)
    docs=[a.doc] if a.doc else [p.name for p in sorted(root.iterdir()) if p.is_dir()]
    bad=[]
    for did in docs:
        ok,res=compile_doc(root/did,did,a.force)
        if not ok: bad.append((did,res))
    if bad:
        for did,res in bad: print(did,res)
        raise SystemExit(1)
if __name__=='__main__': main()
