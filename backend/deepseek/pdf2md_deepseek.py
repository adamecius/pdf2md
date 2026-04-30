#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, sys, json
from pathlib import Path

def parser():
    p=argparse.ArgumentParser(description='Convert PDF to Markdown with DeepSeek OCR (local first).')
    p.add_argument('-i','--input',required=True); p.add_argument('-o','--output'); p.add_argument('--json-out'); p.add_argument('--out-dir')
    p.add_argument('--lang',default='en'); p.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    p.add_argument('--model-path'); p.add_argument('--allow-download',action='store_true'); p.add_argument('--api',action='store_true')
    return p

def main():
    a=parser().parse_args(); ip=Path(a.input).expanduser().resolve()
    if not ip.exists() or ip.suffix.lower()!='.pdf': print(f'error: Input must be an existing PDF file: {ip}',file=sys.stderr); return 1
    model_path=a.model_path or os.getenv('PDF2MD_DEEPSEEK_MODEL')
    if a.api: print('error: API mode exists only if separately implemented; this wrapper requires explicit local model path.',file=sys.stderr); return 1
    if not model_path:
        print('error: Missing local model. Looked at --model-path and PDF2MD_DEEPSEEK_MODEL. Provide one. Downloads are disabled by default; use --allow-download only if you add model download flow. API mode can be added via --api.',file=sys.stderr); return 1
    mp=Path(model_path).expanduser().resolve()
    if not mp.exists(): print(f'error: Local model missing: {mp}. Looked at {mp}. Provide --model-path or PDF2MD_DEEPSEEK_MODEL.',file=sys.stderr); return 1
    try:
        from pdf_to_md_json import run
    except Exception as e:
        print(f'error: Failed to import local deepseek backend dependency: {e}',file=sys.stderr); return 1
    out_md=Path(a.output).expanduser().resolve() if a.output else ip.with_suffix('.md')
    out_dir=Path(a.out_dir).expanduser().resolve() if a.out_dir else out_md.parent
    dev='cpu' if a.device=='auto' else a.device
    try:
        md,_=run(ip,out_dir,str(mp),dev,local_only=not a.allow_download)
        out_md.write_text(md.read_text(encoding='utf-8'),encoding='utf-8')
        if a.json_out: Path(a.json_out).write_text(json.dumps({'backend':'deepseek','input':str(ip),'model_path':str(mp)}),encoding='utf-8')
        print(str(out_md)); return 0
    except Exception as e:
        print(f'error: {e}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
