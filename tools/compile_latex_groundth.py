#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, re, shutil, subprocess, sys, tempfile
from pathlib import Path
SCHEMA='compile_latex_groundth_v1_lualatex_latexml'

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--corpus-root',default='groundtruth/corpus/latex')
    p.add_argument('--doc')
    p.add_argument('--force',action='store_true')
    return p.parse_args()

def require_tool(name):
    if shutil.which(name): return
    print('HUMAN TASK'); print(f'- Missing required executable: {name}'); print('- This script does not install external dependencies.'); raise SystemExit(42)

def run_cmd(cmd,cwd): return subprocess.run(cmd,cwd=str(cwd),text=True,capture_output=True)
def ver(cmd):
    cp=subprocess.run(cmd,text=True,capture_output=True)
    return (cp.stdout+cp.stderr).strip() if cp.returncode==0 else ''

def discover(root,doc=None):
    root=Path(root)
    if doc:
        d=root/doc; t=d/f'{doc}.tex'
        if not t.exists(): raise SystemExit(f"Document '{doc}' not found at {t}")
        return [d]
    return [d for d in sorted(root.iterdir()) if d.is_dir() and (d/f'{d.name}.tex').exists()]

def metadata_ok(tex):
    txt=tex.read_text(encoding='utf-8',errors='ignore'); dm=txt.find('\\DocumentMetadata'); dc=txt.find('\\documentclass')
    return dm!=-1 and dc!=-1 and dm<dc

def build_hash(doc_dir,doc_id,biber):
    h=hashlib.sha256(); h.update(SCHEMA.encode()); h.update((doc_dir/f'{doc_id}.tex').read_bytes())
    for bib in sorted(doc_dir.rglob('*.bib')): h.update(bib.relative_to(doc_dir).as_posix().encode()); h.update(bib.read_bytes())
    assets=doc_dir/'assets'
    if assets.is_dir():
        for f in sorted(assets.rglob('*')):
            if f.is_file(): h.update(f.relative_to(doc_dir).as_posix().encode()); h.update(f.read_bytes())
    h.update(ver(['lualatex','--version']).encode()); h.update((ver(['latexml','--VERSION']) or ver(['latexml','--version'])).encode())
    if biber: h.update(ver(['biber','--version']).encode())
    return h.hexdigest()

def main():
    a=parse_args(); docs=discover(a.corpus_root,a.doc); require_tool('lualatex'); require_tool('latexml'); failed=[]
    for d in docs:
        doc=d.name; tex=d/f'{doc}.tex'; pdf=d/f'{doc}.pdf'; xml=d/f'{doc}.latexml.xml'; log=d/'build.log'
        biber_needed='\\addbibresource' in tex.read_text(encoding='utf-8',errors='ignore'); h=build_hash(d,doc,biber_needed)
        old=log.read_text(encoding='utf-8',errors='ignore') if log.exists() else ''
        if not a.force and f'build_hash: {h}' in old and pdf.exists() and xml.exists() and xml.stat().st_size>0:
            print(f'{doc}: skipped (hash match)'); continue
        warnings=[]; errors=[]
        if not metadata_ok(tex): warnings.append('\\DocumentMetadata not found before \\documentclass')
        with tempfile.TemporaryDirectory(prefix=f'{doc}_latex_') as t:
            tmp=Path(t); cmd=['lualatex','-interaction=nonstopmode','-halt-on-error','-file-line-error','-recorder','-synctex=1','-output-directory',str(tmp),f'{doc}.tex']
            logs=[]
            for _ in range(2):
                cp=run_cmd(cmd,d); logs.append(cp.stdout+cp.stderr)
                if cp.returncode!=0: errors.append('lualatex returned non-zero'); break
            if not errors and (tmp/f'{doc}.bcf').exists():
                require_tool('biber'); bp=run_cmd(['biber','--input-directory',str(tmp),'--output-directory',str(tmp),doc],d); logs.append(bp.stdout+bp.stderr)
                if bp.returncode!=0: errors.append('biber returned non-zero')
                else:
                    for _ in range(2):
                        cp=run_cmd(cmd,d); logs.append(cp.stdout+cp.stderr)
                        if cp.returncode!=0: errors.append('lualatex returned non-zero after biber'); break
            joined='\n'.join(logs)
            if re.search(r'^! ',joined,flags=re.M): errors.append('latex fatal line found')
            if 'Undefined control sequence' in joined: errors.append('undefined control sequence')
            if re.search(r'Citation[^\n]*undefined',joined,flags=re.I): errors.append('unresolved citations')
            if re.search(r'Reference[^\n]*undefined',joined,flags=re.I): errors.append('unresolved references')
            if not (tmp/f'{doc}.pdf').exists(): errors.append('final pdf missing')
            if (tmp/f'{doc}.pdf').exists(): shutil.copy2(tmp/f'{doc}.pdf',pdf)
            if (tmp/f'{doc}.synctex.gz').exists(): shutil.copy2(tmp/f'{doc}.synctex.gz',d/f'{doc}.synctex.gz')
        lcmd=['latexml',f'--destination={doc}.latexml.xml',f'--log={doc}.latexml.log',f'--documentid={doc}']
        if (d/'assets').is_dir(): lcmd.append('--path=assets')
        lcmd.append(f'{doc}.tex'); lp=run_cmd(lcmd,d); out=lp.stdout+lp.stderr
        if lp.returncode!=0: errors.append('latexml returned non-zero')
        if re.search(r'\b(Fatal|Error):',out): errors.append('latexml fatal/error output')
        if 'Warning:' in out: warnings.append('latexml warnings present')
        if not xml.exists() or xml.stat().st_size==0: errors.append('latexml xml missing or empty')
        with log.open('w',encoding='utf-8') as f:
            f.write(f'build_hash: {h}\n'); f.write(f'doc_id: {doc}\n')
            if warnings:
                f.write('warnings:\n'); [f.write(f'- {w}\n') for w in warnings]
            if errors:
                f.write('errors:\n'); [f.write(f'- {e}\n') for e in errors]
        print(f'{doc}: {"failed" if errors else "built"}')
        if errors: failed.append(doc)
    if failed:
        print('Failed documents: '+', '.join(failed),file=sys.stderr); return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
