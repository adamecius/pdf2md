# Plan 005_2 — GROBID conda-env migration (drop Docker)

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

Plan 005_0 documented the GROBID install as:

```bash
docker pull grobid/grobid:0.8.1
docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.1
```

The human reviewer (2026-05-24) rejected this:

> *"why docker? I did not wanted docker, I wanted to follow all the
> other style which was based in .venv"*

Every other backend in this project (`paddleocr`, `mineru`, `deepseek`,
`glm-ocr`, `deepseek-vl2`) installs into a dedicated
`pdf2md-<backend>` conda env created from `backend/<name>/env.yaml`.
GROBID being Docker is the lone outlier and creates real
friction — on dev hosts where the user is not in the `docker` group,
the documented install path is impossible to follow.

## 2. Goal

Replace the Docker-based GROBID install with a conda-env install that
matches the rest of the project:

```bash
conda env create -f backend/semantic/grobid/env.yaml
conda activate pdf2md-grobid
backend/semantic/grobid/start_grobid.sh   # starts the Java service in background
```

The smoke test, HTTP client, and TEI parser stay unchanged — GROBID
still exposes `processFulltextDocument` on `http://localhost:8070` —
only the startup mechanism changes.

## 3. Implementation sketch

### 3.1 `backend/semantic/grobid/env.yaml`

```yaml
name: pdf2md-grobid
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11       # for the start script's tarball download helper
  - openjdk=17        # GROBID requires Java 17
  - wget              # for downloading the release tarball
  - unzip             # for unpacking it
```

No PyPI packages — the GROBID service itself is downloaded as a
binary tarball from the upstream GitHub release.

### 3.2 `backend/semantic/grobid/start_grobid.sh`

```bash
#!/usr/bin/env bash
# Downloads GROBID 0.8.1 on first run, then starts the Java service.
set -euo pipefail

GROBID_VERSION="${GROBID_VERSION:-0.8.1}"
ENV_HOME="${CONDA_PREFIX:?activate pdf2md-grobid first}"
GROBID_HOME="${ENV_HOME}/share/grobid-${GROBID_VERSION}"

if [[ ! -d "${GROBID_HOME}" ]]; then
    cd "${ENV_HOME}/share"
    wget "https://github.com/kermitt2/grobid/archive/refs/tags/${GROBID_VERSION}.zip"
    unzip "${GROBID_VERSION}.zip"
    cd "grobid-${GROBID_VERSION}"
    ./gradlew clean install --no-daemon
fi

cd "${GROBID_HOME}"
./gradlew run --no-daemon
```

Notes:
- First run takes 10-20 minutes (Gradle build pulls every dep tree).
- Subsequent runs start in ~30 s once Gradle's cache is warm.
- Tarball lives inside the conda env's `share/` so removing the env
  removes everything.

### 3.3 README rewrite

Replace the Docker section with:

```bash
conda env create -f backend/semantic/grobid/env.yaml
conda activate pdf2md-grobid
backend/semantic/grobid/start_grobid.sh &
# Wait ~30 s for warm-up (longer on first install).
curl -s http://localhost:8070/api/isalive    # → "true"

# Smoke test (in the main pdf2md env — only stdlib + requests needed):
conda run -n pdf2md python backend/semantic/grobid/smoke_test.py \
    --pdf tests/data/<sample_article>.pdf \
    --out-dir /tmp/grobid_smoke
```

Keep the existing `grobid_client.py` and `tei_parser.py` unchanged —
they speak HTTP and don't care how the service is started.

### 3.4 No code changes in `src/pdf2md/semantic/`

The Plan 006_0 `GrobidSemanticBackend` adapter is already
HTTP-only and gates on `client.is_alive(endpoint)`. The startup
mechanism is transparent to the adapter.

## 4. Alternatives considered (and rejected)

### Pure Python bibliography parsing (refextract, anystyle, CERMINE)

| Tool        | Language | Notes                                                       |
|-------------|----------|-------------------------------------------------------------|
| refextract  | Python   | Only extracts references, not figure/table markers          |
| anystyle    | Ruby     | Cross-language toolchain — worse than Java for this project |
| CERMINE     | Java     | Same Java requirement as GROBID, less accurate              |

None match GROBID's coverage of figure/table/equation refs.

### Keep Docker as an OPT-IN secondary path

Tempting (Docker is faster on Linux servers where the daemon is
already running), but it adds two install paths to maintain. The
user wants one path; conda env is the right choice.

## 5. Acceptance criteria (when activated)

- [ ] `backend/semantic/grobid/env.yaml` ships and creates the env.
- [ ] `backend/semantic/grobid/start_grobid.sh` ships and is executable.
- [ ] First-run flow (clone + Gradle install + start) reaches
      `curl localhost:8070/api/isalive → "true"`.
- [ ] Existing `backend/semantic/grobid/smoke_test.py` passes
      against the locally-started service (same H1 acceptance as
      Plan 005_0, just with a different startup path).
- [ ] Plan 006_0's `GrobidSemanticBackend.is_available()` returns
      `True` and `extract()` returns a non-empty graph on a real PDF.
- [ ] README updated: no Docker commands; install steps mirror other
      backends' READMEs.

## 6. Out of scope

- Bundling a pre-built GROBID JAR into the repo (license-fine but
  bloats `git clone`).
- Multi-instance / GPU-accelerated GROBID. The default Java service
  on CPU is good enough.
- DeepSeek-VL2 rework. (See Plan 005_1.)

## 7. Promotion

This plan stays in `plans/` (not yet promoted) until the human
reviewer signs off on the approach. The note in the existing
`backend/semantic/grobid/README.md` flags the Docker install as
**inconsistent with project style** so users discover the planned
migration at the right time.
