#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description='GLM backend wrapper. API mode only.')
 p.add_argument('-i','--input',required=True); p.add_argument('-o','--output'); p.add_argument('--json-out'); p.add_argument('--out-dir')
 p.add_argument('--lang',default='en'); p.add_argument('--device',default='auto'); p.add_argument('--model-path'); p.add_argument('--allow-download',action='store_true')
 p.add_argument('--api',action='store_true',help='Required for GLM API mode')
 a=p.parse_args(); ip=Path(a.input).expanduser().resolve()
 if not ip.exists() or ip.suffix.lower()!='.pdf': print(f'error: Input must be an existing PDF file: {ip}',file=sys.stderr); return 1
 if not a.api: print('error: GLM wrapper is API-based. Re-run with --api and set GLM_API_KEY.',file=sys.stderr); return 1
 if not os.getenv('GLM_API_KEY'): print('error: Missing GLM_API_KEY. Looked in environment. Set it and retry. Local model mode is not implemented in this wrapper.',file=sys.stderr); return 1
 print('error: GLM API execution is intentionally not auto-run in smoke-safe wrapper yet. Credentials detected, but implement explicit call flow before use.',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
