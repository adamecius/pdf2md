from __future__ import annotations
import subprocess, sys

CASES=[
 ('backend/mineru/pdf2md_mineru.py',['--help'],0),
 ('backend/deepseek/pdf2md_deepseek.py',['--help'],0),
 ('backend/paddleocr/pdf2md_paddleocr.py',['--help'],0),
 ('backend/glm/pdf2md_glm.py',['--help'],0),
 ('backend/mineru/setup_env.py',['--help'],0),
 ('backend/deepseek/setup_env.py',['--help'],0),
 ('backend/paddleocr/setup_env.py',['--help'],0),
 ('backend/glm/setup_env.py',['--help'],0),
 ('backend/deepseek/pdf2md_deepseek.py',['-i','missing.pdf'],1),
 ('backend/glm/pdf2md_glm.py',['-i','missing.pdf'],1),
]

def run(path,args):
 return subprocess.run([sys.executable,path,*args],capture_output=True,text=True)

def test_cli_smoke():
 for p,a,rc in CASES:
  r=run(p,a)
  assert r.returncode==rc, (p,a,r.stdout,r.stderr)
