#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description='Setup backend environment')
 p.add_argument('--manager',choices=['conda','venv'],default='conda')
 p.add_argument('--env-name')
 p.add_argument('--python',default='3.11')
 a=p.parse_args(); here=Path(__file__).resolve().parent
 req=here/'requirements.txt'; yml=here/'environment.yml'
 env=a.env_name
 if not env:
  env='pdf2md-'+here.name
 if a.manager=='conda':
  cmd=['conda','env','create','-n',env,'-f',str(yml)]
 else:
  v=Path(env); subprocess.check_call([sys.executable,'-m','venv',str(v)]); pip=v/'bin'/'pip'; cmd=[str(pip),'install','-r',str(req)]
 print('Running:',' '.join(cmd)); subprocess.check_call(cmd); return 0
if __name__=='__main__': raise SystemExit(main())
