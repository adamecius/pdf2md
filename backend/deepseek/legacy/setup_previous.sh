#!/usr/bin/env bash
set -euo pipefail

ENVNAME="deepseek-ocr2"
ENVFLAVOR="conda"
WORKDIR="$HOME/models/deepseek-ocr2"
REPO_URL="https://github.com/deepseek-ai/DeepSeek-OCR-2.git"
REPO_DIR_NAME="DeepSeek-OCR-2"
VLLM_WHEEL_NAME="vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl"
VLLM_WHEEL_URL="https://github.com/vllm-project/vllm/releases/download/v0.8.5/vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl"
PYTHON_VERSION="3.12.9"
NUMPY_VERSION="2.2.6"
MAX_JOBS_DEFAULT="4"

usage() {
  cat <<EOF
Usage:
  ./setup_deepseek_ocr2.sh [options]

Options:
  --envname NAME        Environment name or venv path. Default: deepseek-ocr2
  --envflavor FLAVOR    conda or venv. Default: conda
  --workdir PATH        Working directory. Default: \$HOME/models/deepseek-ocr2
  --repo-url URL        DeepSeek-OCR-2 repository URL
  --vllm-wheel-url URL  vLLM wheel URL
  --help               Show this help

Examples:
  ./setup_deepseek_ocr2.sh --envname deepseek-ocr2 --envflavor conda
  ./setup_deepseek_ocr2.sh --envname ocr2-prod --envflavor conda
  ./setup_deepseek_ocr2.sh --envname .venv-deepseek-ocr2 --envflavor venv
EOF
}

log() {
  printf '\n[deepseek-ocr2-setup] %s\n' "$1"
}

fail() {
  printf '\n[deepseek-ocr2-setup] ERROR: %s\n' "$1" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --envname)
      ENVNAME="${2:-}"
      shift 2
      ;;
    --envflavor)
      ENVFLAVOR="${2:-}"
      shift 2
      ;;
    --workdir)
      WORKDIR="${2:-}"
      shift 2
      ;;
    --repo-url)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --vllm-wheel-url)
      VLLM_WHEEL_URL="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

if [ "$ENVFLAVOR" != "conda" ] && [ "$ENVFLAVOR" != "venv" ]; then
  fail "--envflavor must be either conda or venv"
fi

command -v git >/dev/null 2>&1 || fail "git is required"
command -v curl >/dev/null 2>&1 || fail "curl is required"

mkdir -p "$WORKDIR"
cd "$WORKDIR"

setup_conda_env() {
  command -v conda >/dev/null 2>&1 || fail "conda is required for --envflavor conda"

  local conda_base
  conda_base="$(conda info --base)"

  # This fixes shells where 'conda activate' fails with:
  # CondaError: Run 'conda init' before 'conda activate'
  # shellcheck disable=SC1090
  source "$conda_base/etc/profile.d/conda.sh"

  if ! conda env list | awk '{print $1}' | grep -qx "$ENVNAME"; then
    log "Creating Conda environment: $ENVNAME"
    conda create -n "$ENVNAME" "python=$PYTHON_VERSION" pip -y
  else
    log "Conda environment already exists: $ENVNAME"
  fi

  conda activate "$ENVNAME"

  log "Installing CUDA 11.8 toolkit inside the Conda environment"
  conda install -y -c nvidia/label/cuda-11.8.0 cuda-toolkit

  export CUDA_HOME="$CONDA_PREFIX"
  export PATH="$CUDA_HOME/bin:$PATH"
  export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

  mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"
  cat > "$CONDA_PREFIX/etc/conda/activate.d/cuda-11.8.sh" <<'EOF'
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
EOF

  log "Conda CUDA configuration"
  which nvcc || true
  nvcc -V || true
}

setup_venv_env() {
  command -v python3 >/dev/null 2>&1 || fail "python3 is required for --envflavor venv"

  if [ ! -d "$ENVNAME" ]; then
    log "Creating Python venv: $ENVNAME"
    python3 -m venv "$ENVNAME"
  else
    log "Python venv already exists: $ENVNAME"
  fi

  # shellcheck disable=SC1090
  source "$ENVNAME/bin/activate"

  if [ -n "${CUDA_HOME:-}" ]; then
    export PATH="$CUDA_HOME/bin:$PATH"
    export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
  elif [ -d "/usr/local/cuda-11.8" ]; then
    export CUDA_HOME="/usr/local/cuda-11.8"
    export PATH="$CUDA_HOME/bin:$PATH"
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
  fi

  command -v nvcc >/dev/null 2>&1 || fail "nvcc is required for venv mode. Use Conda mode or install CUDA 11.8 toolkit."

  log "venv CUDA configuration"
  which nvcc
  nvcc -V

  if nvcc -V | grep -q "release 11.5"; then
    fail "venv mode is using CUDA 11.5. Use --envflavor conda or point CUDA_HOME to CUDA 11.8."
  fi
}

clone_repo() {
  if [ ! -d "$WORKDIR/$REPO_DIR_NAME/.git" ]; then
    log "Cloning DeepSeek-OCR-2 repository"
    git clone "$REPO_URL" "$REPO_DIR_NAME"
  else
    log "Repository already exists. Updating with git pull --ff-only"
    git -C "$WORKDIR/$REPO_DIR_NAME" pull --ff-only || true
  fi

  cd "$WORKDIR/$REPO_DIR_NAME"
}

download_vllm_wheel() {
  if [ ! -f "$WORKDIR/$VLLM_WHEEL_NAME" ]; then
    log "Downloading vLLM wheel"
    curl -fL -o "$WORKDIR/$VLLM_WHEEL_NAME" "$VLLM_WHEEL_URL"
  else
    log "vLLM wheel already exists: $WORKDIR/$VLLM_WHEEL_NAME"
  fi
}

install_python_packages() {
  log "Upgrading base Python packaging tools"
  python -m pip install --upgrade pip setuptools wheel packaging ninja

  log "Installing PyTorch CUDA 11.8 wheels"
  python -m pip install \
    torch==2.6.0 \
    torchvision==0.21.0 \
    torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu118

  log "Installing vLLM 0.8.5 CUDA 11.8 wheel"
  python -m pip install "$WORKDIR/$VLLM_WHEEL_NAME"

  log "Installing DeepSeek-OCR-2 requirements with NumPy pinned"
  local constraints_file
  constraints_file="$WORKDIR/deepseek-ocr2-constraints.txt"

  cat > "$constraints_file" <<EOF
numpy==$NUMPY_VERSION
EOF

  python -m pip install -r requirements.txt -c "$constraints_file"

  # Enforce this after requirements as well, because the upstream requirements file leaves numpy unpinned.
  python -m pip install "numpy==$NUMPY_VERSION"

  log "Installing flash-attn 2.7.3"
  export MAX_JOBS="${MAX_JOBS:-$MAX_JOBS_DEFAULT}"
  python -m pip install flash-attn==2.7.3 --no-build-isolation --no-cache-dir
}

verify_install() {
  log "Verifying installation"

  which nvcc || true
  nvcc -V || true

  python - <<'PY'
import os
import torch
import numpy
import transformers
import tokenizers

print("CUDA_HOME:", os.environ.get("CUDA_HOME"))
print("torch:", torch.__version__)
print("torch cuda:", torch.version.cuda)
print("cuda available:", torch.cuda.is_available())
print("numpy:", numpy.__version__)
print("transformers:", transformers.__version__)
print("tokenizers:", tokenizers.__version__)

try:
    import vllm
    print("vllm:", vllm.__version__)
except Exception as exc:
    print("vllm import failed:", repr(exc))

try:
    import flash_attn
    print("flash-attn:", flash_attn.__version__)
except Exception as exc:
    print("flash-attn import failed:", repr(exc))
    raise
PY

  log "pip check output follows. The vLLM Transformers and Tokenizers conflict is expected for the official shared environment."
  python -m pip check || true
}

log "Environment flavour: $ENVFLAVOR"
log "Environment name: $ENVNAME"
log "Working directory: $WORKDIR"

if [ "$ENVFLAVOR" = "conda" ]; then
  setup_conda_env
else
  setup_venv_env
fi

clone_repo
download_vllm_wheel
install_python_packages
verify_install

cat <<EOF

[deepseek-ocr2-setup] Done.

Repository:
  $WORKDIR/$REPO_DIR_NAME

To activate later with Conda:
  source ~/miniconda3/etc/profile.d/conda.sh
  conda activate $ENVNAME

To run vLLM image OCR:
  cd $WORKDIR/$REPO_DIR_NAME/DeepSeek-OCR2-master/DeepSeek-OCR2-vllm
  edit config.py
  python run_dpsk_ocr2_image.py

To run Transformers OCR:
  cd $WORKDIR/$REPO_DIR_NAME/DeepSeek-OCR2-master/DeepSeek-OCR2-hf
  python run_dpsk_ocr2.py

EOF
