#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys, json
from pathlib import Path

def parser():
  p=argparse.ArgumentParser(description='Convert PDF to Markdown via PaddleOCR (local).')
  p.add_argument('-i','--input',required=True); p.add_argument('-o','--output'); p.add_argument('--json-out'); p.add_argument('--out-dir')
  p.add_argument('--lang',default='en'); p.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
  p.add_argument('--model-path'); p.add_argument('--allow-download',action='store_true'); p.add_argument('--api',action='store_true')
  return p

def main():
  a=parser().parse_args(); ip=Path(a.input).expanduser().resolve()
  if not ip.exists() or ip.suffix.lower()!='.pdf': print(f'error: Input must be an existing PDF file: {ip}',file=sys.stderr); return 1
  if a.api: print('error: API mode is not implemented for PaddleOCR wrapper. Use local PaddleOCR installation.',file=sys.stderr); return 1
  try:
    import fitz
    from PIL import Image
    from paddleocr import PaddleOCR
  except Exception as e:
    print(f'error: Missing local dependency for PaddleOCR flow: {e}. Looked in active Python environment. Install requirements.',file=sys.stderr); return 1
  out_md=Path(a.output).expanduser().resolve() if a.output else ip.with_suffix('.md')
  out_dir=Path(a.out_dir).expanduser().resolve() if a.out_dir else out_md.parent
  out_dir.mkdir(parents=True,exist_ok=True)
  ocr=PaddleOCR(use_angle_cls=True,lang=a.lang,use_gpu=(a.device=='cuda'))
  doc=fitz.open(ip); lines=[]
  for i,p in enumerate(doc,1):
    pix=p.get_pixmap(alpha=False); img=Image.frombytes('RGB',[pix.width,pix.height],pix.samples); tmp=out_dir/f'{ip.stem}_p{i:04d}.png'; img.save(tmp)
    res=ocr.ocr(str(tmp),cls=True); lines.append(f'\n\n<!-- page {i} -->')
    for blk in res or []:
      for item in blk or []:
        if len(item)>=2 and isinstance(item[1],tuple): lines.append(item[1][0])
  out_md.write_text('\n'.join(lines).strip()+"\n",encoding='utf-8')
  if a.json_out: Path(a.json_out).write_text(json.dumps({'backend':'paddleocr','input':str(ip),'pages':len(doc)}),encoding='utf-8')
  print(str(out_md)); return 0
if __name__=='__main__': raise SystemExit(main())
