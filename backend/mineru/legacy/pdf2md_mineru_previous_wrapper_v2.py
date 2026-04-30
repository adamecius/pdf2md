#!/usr/bin/env python3
from __future__ import annotations
import argparse, asyncio, sys
from pathlib import Path

def build_parser():
    p=argparse.ArgumentParser(description='Convert a PDF to Markdown using local MinerU backend.')
    p.add_argument('-i','--input',required=True)
    p.add_argument('-o','--output')
    p.add_argument('--json-out')
    p.add_argument('--out-dir')
    p.add_argument('--lang',default='en')
    p.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    p.add_argument('--model-path')
    p.add_argument('--allow-download',action='store_true')
    p.add_argument('--api',action='store_true',help='Explicitly use remote API mode.')
    p.add_argument('--backend',default='hybrid-auto-engine',choices=['hybrid-auto-engine','pipeline','vlm-auto-engine'])
    p.add_argument('--api-url',default=None)
    p.add_argument('--no-formula',action='store_true')
    p.add_argument('--no-table',action='store_true')
    return p

def _validate_pdf(path:str)->Path:
    p=Path(path).expanduser().resolve()
    if not p.exists() or p.suffix.lower()!='.pdf':
        raise ValueError(f'Input must be an existing PDF file: {p}')
    return p

async def _run(args,input_pdf:Path,out_md:Path):
    try:
        from mineru.cli import api_client as _api_client
    except ImportError:
        raise RuntimeError('Missing local dependency: mineru package not importable. Looked in active Python environment. Install with requirements/setup_env.py. API mode exists via --api with --api-url.')
    out_dir=Path(args.out_dir).expanduser().resolve() if args.out_dir else out_md.parent
    out_dir.mkdir(parents=True,exist_ok=True)
    if args.model_path:
        import os; os.environ['MINERU_MODEL_PATH']=args.model_path
    form_data=_api_client.build_parse_request_form_data(lang_list=[args.lang],backend=args.backend,parse_method='auto',formula_enable=not args.no_formula,table_enable=not args.no_table,return_md=True,response_format_zip=True,return_images=False,return_middle_json=bool(args.json_out),return_content_list=bool(args.json_out))
    upload_assets=[_api_client.UploadAsset(path=input_pdf,upload_name=input_pdf.name)]
    async with _api_client.get_http_client() as client:
        local=None
        try:
            if args.api:
                if not args.api_url: raise RuntimeError('API mode requires --api-url explicitly.')
                base=args.api_url
            else:
                local=_api_client.LocalAPIServer(); base=local.start(); await _api_client.wait_for_local_api_ready(client,local)
            sub=await _api_client.submit_parse_task(base_url=base,upload_assets=upload_assets,form_data=form_data)
            await _api_client.wait_for_task_result(client=client,submit_response=sub,task_label='1 file')
            z=await _api_client.download_result_zip(client=client,submit_response=sub)
            _api_client.safe_extract_zip(z,out_dir); z.unlink(missing_ok=True)
        finally:
            if local: local.stop()
    candidates=sorted(out_dir.rglob('*.md'))
    if not candidates: raise RuntimeError(f'MinerU completed but no markdown found under: {out_dir}')
    out_md.write_text(candidates[0].read_text(encoding='utf-8'),encoding='utf-8')

def main():
    args=build_parser().parse_args()
    try:
        input_pdf=_validate_pdf(args.input)
        out_md=Path(args.output).expanduser().resolve() if args.output else input_pdf.with_suffix('.md')
        asyncio.run(_run(args,input_pdf,out_md))
        print(str(out_md))
        return 0
    except Exception as e:
        print(f'error: {e}',file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
