#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description='Setup GLM backend environment')
 p.add_argument('--manager',choices=['conda','venv'],default='conda'); p.add_argument('--env-name',default='pdf2md-glm'); p.add_argument('--python',default='3.11')
 a=p.parse_args(); here=Path(__file__).resolve().parent
 if a.manager=='conda': cmd=['conda','env','create','-n',a.env_name,'-f',str(here/'environment.yml')]
 else:
  v=Path(a.env_name); subprocess.check_call([sys.executable,'-m','venv',str(v)]); cmd=[str(v/'bin'/'pip'),'install','-r',str(here/'requirements.txt')]
 print('Running:',' '.join(cmd)); subprocess.check_call(cmd); return 0
if __name__=='__main__': raise SystemExit(main())
