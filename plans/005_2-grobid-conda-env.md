# Plan 005_2 — GROBID install rework (drop Docker, match extraction-backend pattern)

## Status: draft
## Date: 2026-05-24
## Depends on: Plan 005_0 (archived as M20)

Allowed status values:
draft
active
agent_in_progress
agent_complete
human_verification_required
human_verified
finished
blocked
superseded

Branch name (when activated):
plan-005-2-grobid-conda-env

---

## 1. Problem statement

Plan 005_0 shipped GROBID as a Docker container:

```bash
docker pull grobid/grobid:0.8.1
docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.1
```

The reviewer rejected this (2026-05-24):
*"why docker? I did not wanted docker, I wanted to follow all the
other style which was based in .venv"*.

The project already has a mature install style under
`backend/<extraction>/` — every OCR backend (paddleocr, mineru,
deepseek, glm) ships a **five-file install kit**:

```text
backend/<name>/
├── environment.yml          # minimal conda spec
├── requirements.txt         # pip deps
├── setup_env.py             # thin wrapper around `conda env create -f environment.yml`
├── setup.py                 # main installer — HW preflight, conda+venv,
│                            #   upstream-repo clone/download, post-install verify
├── delete_env.py            # companion teardown
└── …                        # backend-specific runner + README
```

GROBID's current install path under `backend/semantic/grobid/`
contains **none** of these files; it has only `grobid_client.py`,
`tei_parser.py`, `smoke_test.py`, and a Docker-centred `README.md`.
That's the inconsistency this plan eliminates.

## 2. Goal

Make GROBID install in the exact same shape as the four extraction
backends. After this plan:

```bash
# Standard pdf2md install — identical shape to backend/paddleocr/setup.py:
python backend/semantic/grobid/setup.py

# Or step-by-step:
python backend/semantic/grobid/setup_env.py --manager conda
python backend/semantic/grobid/setup.py --skip-env-create
```

The smoke test (`backend/semantic/grobid/smoke_test.py`) and the
in-tree adapter (`src/pdf2md/semantic/grobid_adapter.py` — Plan 006_0)
do not change — they continue to speak HTTP to `localhost:8070`.

## 3. File layout (5-file kit)

```text
backend/semantic/grobid/
├── environment.yml          # NEW — minimal: python + openjdk=17 + wget + unzip
├── requirements.txt         # NEW — empty body + a top comment ("Java service, no pip deps")
├── setup_env.py             # NEW — bootstrap, identical shape to backend/deepseek/setup_env.py
├── setup.py                 # NEW — main installer (see §4)
├── delete_env.py            # NEW — companion teardown, copied + adapted from backend/deepseek/
├── grobid_client.py         # UNCHANGED
├── tei_parser.py            # UNCHANGED
├── smoke_test.py            # UNCHANGED — already exits 3 on env_not_ready
└── README.md                # REWRITE — point at setup.py; drop Docker section
```

## 4. `setup.py` design (mirrors the extraction-backend installer)

Single Python file, ~250–350 LOC, structured like
[backend/paddleocr/setup.py](../backend/paddleocr/setup.py) and
[backend/mineru/setup.py](../backend/mineru/setup.py):

1. **Constants** (top of file)
   ```python
   DEFAULT_ENV_NAME = "pdf2md-grobid"
   GROBID_VERSION   = "0.8.1"
   GROBID_TARBALL_URL = (
       f"https://github.com/kermitt2/grobid/archive/refs/tags/"
       f"{GROBID_VERSION}.zip"
   )
   GROBID_PORT      = 8070
   PYTHON_VERSION   = "3.11"
   MIN_RAM_GB       = 4
   MIN_DISK_GB      = 4
   JAVA_MAJOR_MIN   = 17
   ```

2. **Preflight `check_*()` functions**, returning `CheckResult` like
   the extraction backends:
   - `check_os()` — same Linux/Darwin/Windows gate.
   - `check_python_version()` — ≥3.10 for `setup.py` itself.
   - `check_java_available()` — looks for `openjdk=17` in the active
     conda env *or* a system `java -version` ≥17 in venv mode. Will
     pass after the env-create step in conda mode.
   - `check_ram()`, `check_disk()`, `check_port_8070_free()`.

3. **Env creation**
   - `create_conda_env(env_name, python_ver)` — calls
     `conda env create -n pdf2md-grobid -f environment.yml`.
   - `create_venv_env(env_name, python_exe)` — creates the venv,
     then verifies system `java` is on PATH and `java -version`
     reports ≥17. If not, hard-fail with a clear message (we don't
     install JDK 17 into a venv).

4. **GROBID download + first-time build**
   - `download_grobid_tarball(prefix)` — `urllib.request.urlretrieve`
     of `GROBID_TARBALL_URL` into `${CONDA_PREFIX}/share/`. Unzips to
     `${CONDA_PREFIX}/share/grobid-0.8.1/`.
   - `grobid_first_build(prefix)` — runs
     `./gradlew clean install --no-daemon` inside the unpacked tree.
     This is the slow step (10–20 min first time, ~3 GB peak in
     Gradle cache).
   - Both steps skip cleanly when `${CONDA_PREFIX}/share/grobid-0.8.1/`
     already exists (idempotent).

5. **Install launcher script**
   - Writes `${CONDA_PREFIX}/bin/start_grobid` (no `.sh` suffix — the
     extraction backends place their entry points the same way under
     `${CONDA_PREFIX}/bin/`). Marks it `chmod +x`.
   - Script body:
     ```bash
     #!/usr/bin/env bash
     set -euo pipefail
     GROBID_HOME="${CONDA_PREFIX}/share/grobid-0.8.1"
     cd "${GROBID_HOME}"
     exec ./gradlew run --no-daemon "$@"
     ```
   - Also writes `${CONDA_PREFIX}/bin/stop_grobid` that runs
     `pkill -f 'org.grobid.service.main'` (best-effort, no error if
     not running).

6. **Verify**
   - Background-start GROBID:
     `Popen(['start_grobid'], stdout=PIPE, stderr=PIPE, start_new_session=True)`.
   - Poll `http://localhost:8070/api/isalive` every 5 s for up to 90 s.
     Pass on `200 + "true"`; fail otherwise.
   - Stop the background GROBID via `stop_grobid` to leave the host
     clean. `--keep-running` flag skips this if the user wants to
     hand off to a long-lived service.

7. **CLI flags**
   - `--manager {conda,venv}` (default `conda`).
   - `--env-name NAME` (default `pdf2md-grobid`).
   - `--python VER` (default `3.11`).
   - `--grobid-version VER` (default `0.8.1`).
   - `--skip-env-create` (skip §3 conda env create — assume env
     already exists).
   - `--skip-build` (skip §4.2 Gradle build — assume install layout
     already cached).
   - `--skip-checks` (skip §2 preflight).
   - `--skip-verify` (skip §6).
   - `--keep-running` (don't stop GROBID after verify).
   - `--check-only` (run §2 and exit 0).

## 5. `environment.yml`

```yaml
name: pdf2md-grobid
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - openjdk=17
  - wget
  - unzip
  - pip
```

No PyPI pkgs — GROBID is a Java service.

## 6. `requirements.txt`

```text
# Java service, no pip deps needed here.
# The HTTP client used by smoke_test.py + the Plan 006 adapter is
# `requests`, which is already present in the main `pdf2md` env via
# docling (not installed in pdf2md-grobid).
```

## 7. `setup_env.py` (thin wrapper)

Identical shape to
[backend/deepseek/setup_env.py](../backend/deepseek/setup_env.py):

```python
#!/usr/bin/env python3
"""Setup pdf2md-grobid environment (thin wrapper around environment.yml)."""
import argparse, subprocess, sys
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manager', choices=['conda', 'venv'], default='conda')
    p.add_argument('--env-name')
    p.add_argument('--python', default='3.11')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    yml  = here / 'environment.yml'
    env  = args.env_name or 'pdf2md-' + here.name
    if args.manager == 'conda':
        cmd = ['conda', 'env', 'create', '-n', env, '-f', str(yml)]
    else:
        v = Path(env)
        subprocess.check_call([sys.executable, '-m', 'venv', str(v)])
        # venv mode skips JDK install — requires system java ≥17.
        cmd = None
    if cmd:
        subprocess.check_call(cmd)

if __name__ == '__main__':
    raise SystemExit(main())
```

## 8. `delete_env.py`

Copy `backend/deepseek/delete_env.py` and swap the constant
`ENV_NAME = "pdf2md-deepseek"` → `"pdf2md-grobid"`. Same external
behaviour: removes the conda env or the local venv directory.

## 9. README rewrite

```markdown
# GROBID semantic backend

…(unchanged intro about what GROBID is)…

## Install

```bash
# One-shot install (creates pdf2md-grobid conda env, downloads + builds
# GROBID 0.8.1, writes start_grobid + stop_grobid launchers, verifies):
python backend/semantic/grobid/setup.py

# OR step-by-step:
python backend/semantic/grobid/setup_env.py --manager conda
python backend/semantic/grobid/setup.py --skip-env-create
```

After install, start the service:

```bash
conda activate pdf2md-grobid
start_grobid &     # ~30 s warm-up
curl -s http://localhost:8070/api/isalive   # → "true"
```

…(smoke test section, output shape, library use — unchanged)…
```

Remove the entire **Install (Docker)** section. The Docker quickstart
is not a supported install path going forward.

## 10. Acceptance criteria

- [ ] `python backend/semantic/grobid/setup.py --check-only` runs
      preflight without modifying anything and exits 0 on a Linux
      host with conda + curl + ≥4 GB RAM + ≥4 GB free disk.
- [ ] `python backend/semantic/grobid/setup.py` end-to-end:
      (a) creates `pdf2md-grobid` conda env;
      (b) downloads + unpacks GROBID 0.8.1;
      (c) `gradle install --no-daemon` exits 0;
      (d) writes `${CONDA_PREFIX}/bin/{start,stop}_grobid` (executable);
      (e) starts GROBID, polls `/api/isalive` → `"true"`, stops cleanly;
      (f) `pkill grobid` after.
- [ ] `conda run -n pdf2md python backend/semantic/grobid/smoke_test.py
      --pdf <some>.pdf --out-dir /tmp/grobid_smoke` succeeds when
      GROBID is running (matches Plan 005_0 H1).
- [ ] `python backend/semantic/grobid/delete_env.py` cleanly removes
      the conda env (and the GROBID tarball with it — it lives inside
      the env's `share/`).
- [ ] `pytest tests/test_semantic_*.py -q` still green: 20 passed.
- [ ] No Docker commands appear anywhere in `backend/semantic/grobid/`.

## 11. Out of scope

- DeepSeek-VL2 rework. (See Plan 005_1.)
- Multi-instance or GPU-accelerated GROBID.
- Bundling a pre-built GROBID JAR into the repo (license-fine but
  bloats `git clone`; download-on-install is the chosen tradeoff).
- The Plan 006_0 `GrobidSemanticBackend` adapter — it stays unchanged
  because the HTTP contract is unchanged.

## 12. Promotion

Promote to `current_plan.md` only after the human reviewer signs off
on this revised design.
