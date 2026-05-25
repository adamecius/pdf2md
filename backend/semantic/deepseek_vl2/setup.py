#!/usr/bin/env python3
"""setup.py — Set up a DeepSeek-VL2 environment for the pdf2md semantic backend.

DeepSeek-VL2 is a Vision-Language Model that emits structured JSON from
page images. Stock `transformers` does NOT register the `deepseek_vl_v2`
architecture, so the model load fails unless the official
`deepseek-vl2` source package is installed; that package over-pins
`torch==2.0.1` + `transformers==4.38.2`. This installer applies those
exact pins via a constraints file (the proven-working combo) and a pip
`--index-url` for cu118 wheels — exactly the pattern used by
backend/deepseek/setup.py for the DeepSeek-OCR-2 backend.

  1. Preflight HW/SW checks (GPU, VRAM, CUDA driver, RAM, disk).
  2. Create a conda env (or use an existing venv) named pdf2md-deepseek-vl2.
  3. Install torch + torchvision + transformers from upstream-tested cu118.
  4. Write a constraints file pinning the working combo.
  5. Install requirements.txt against the constraints file.
  6. Install deepseek-vl2 from GitHub with `--no-deps`.
  7. Verify: `import deepseek_vl2.models.{DeepseekVLV2ForCausalLM,DeepseekVLV2Processor}`.

Environment name convention:  pdf2md-deepseek-vl2

Official references:
  https://github.com/deepseek-ai/DeepSeek-VL2
  https://huggingface.co/deepseek-ai/deepseek-vl2-small
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_ENV_NAME = "pdf2md-deepseek-vl2"
DEFAULT_PYTHON_VERSION = "3.11"

DEEPSEEK_VL2_REPO_URL = "https://github.com/deepseek-ai/DeepSeek-VL2.git"

# Upstream-tested combination (matches deepseek-vl2's pyproject pins).
TORCH_VERSION = "2.0.1"
TORCHVISION_VERSION = "0.15.2"
TORCH_CUDA_VARIANT = "cu118"
TORCH_INDEX_URL = f"https://download.pytorch.org/whl/{TORCH_CUDA_VARIANT}"
TRANSFORMERS_VERSION = "4.38.2"

# Inline constraints — applied to every pip install in this env so
# transitive deps cannot upgrade the working combo.
INLINE_CONSTRAINTS = [
    f"torch=={TORCH_VERSION}",
    f"torchvision=={TORCHVISION_VERSION}",
    f"transformers=={TRANSFORMERS_VERSION}",
]

PYTHON_MIN = (3, 10)
PYTHON_MAX = (3, 14)
MIN_VRAM_MB = 16_000
MIN_RAM_GB = 16
MIN_DISK_GB = 30   # cu118 wheels + model + cache + ~6 GB env


# ---------------------------------------------------------------------------
# Preflight checks (mirror paddleocr/mineru/deepseek style)
# ---------------------------------------------------------------------------
class CheckResult:
    def __init__(self, name: str, ok: bool, detail: str):
        self.name, self.ok, self.detail = name, ok, detail

    def __str__(self) -> str:
        return f"  {'✓' if self.ok else '✗'} {self.name}: {self.detail}"


def _run_quiet(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def check_os() -> CheckResult:
    s = platform.system()
    ok = s in ("Linux", "Darwin", "Windows")
    return CheckResult("OS", ok, f"{s} {platform.release()}")


def check_python_version() -> CheckResult:
    v = sys.version_info[:2]
    ok = PYTHON_MIN <= v <= PYTHON_MAX
    detail = (
        f"Python {v[0]}.{v[1]} "
        + ("(OK)" if ok else f"(need {PYTHON_MIN[0]}.{PYTHON_MIN[1]}–{PYTHON_MAX[0]}.{PYTHON_MAX[1]})")
    )
    return CheckResult("Python version", ok, detail)


def check_nvidia_gpu() -> CheckResult:
    if not shutil.which("nvidia-smi"):
        return CheckResult("NVIDIA GPU", False, "nvidia-smi not found")
    r = _run_quiet(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if r.returncode != 0:
        return CheckResult("NVIDIA GPU", False, f"nvidia-smi failed: {r.stderr.strip()}")
    lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
    if not lines:
        return CheckResult("NVIDIA GPU", False, "no GPUs reported")
    parts = lines[0].split(",")
    gpu_name = parts[0].strip()
    try:
        vram_mb = int(parts[1].strip())
    except (IndexError, ValueError):
        vram_mb = 0
    ok = vram_mb >= MIN_VRAM_MB
    detail = f"{gpu_name}, {vram_mb} MB VRAM" + ("" if ok else f" (need ≥{MIN_VRAM_MB} MB)")
    if len(lines) > 1:
        detail += f" (+{len(lines)-1} more GPU(s))"
    return CheckResult("NVIDIA GPU", ok, detail)


def check_cuda_driver() -> CheckResult:
    if not shutil.which("nvidia-smi"):
        return CheckResult("CUDA driver", False, "nvidia-smi not found")
    r = _run_quiet(["nvidia-smi"])
    if r.returncode != 0:
        return CheckResult("CUDA driver", False, "nvidia-smi failed")
    m = re.search(r"CUDA Version:\s+([\d.]+)", r.stdout)
    if not m:
        return CheckResult("CUDA driver", False, "could not parse CUDA version")
    ver = m.group(1)
    major = int(ver.split(".")[0])
    # cu118 wheels need driver ≥ 11.8 (forward-compatible for newer drivers).
    ok = major >= 11
    detail = f"CUDA driver {ver}" + ("" if ok else " (need ≥11.8)")
    return CheckResult("CUDA driver", ok, detail)


def check_ram() -> CheckResult:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    total_gb = int(line.split()[1]) / (1024**2)
                    break
            else:
                return CheckResult("RAM", True, "could not determine (skipping)")
    except FileNotFoundError:
        return CheckResult("RAM", True, "could not determine (skipping)")
    ok = total_gb >= MIN_RAM_GB
    detail = f"{total_gb:.0f} GB" + ("" if ok else f" (need ≥{MIN_RAM_GB} GB)")
    return CheckResult("RAM", ok, detail)


def check_disk(path: str = ".") -> CheckResult:
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024**3)
    ok = free_gb >= MIN_DISK_GB
    detail = f"{free_gb:.0f} GB free" + ("" if ok else f" (need ≥{MIN_DISK_GB} GB)")
    return CheckResult("Disk space", ok, detail)


def run_checks() -> tuple[list[CheckResult], bool]:
    """Run preflight checks. Returns (results, gpu_critical_ok)."""
    checks = [
        check_os(),
        check_python_version(),
        check_nvidia_gpu(),
        check_cuda_driver(),
        check_ram(),
        check_disk(),
    ]
    gpu_ok = all(c.ok for c in checks if c.name in ("NVIDIA GPU", "CUDA driver"))
    return checks, gpu_ok


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------
def _conda_envs_json() -> dict:
    if shutil.which("conda") is None:
        raise SystemExit("ERROR: conda not found on PATH.")
    r = _run_quiet(["conda", "env", "list", "--json"])
    if r.returncode != 0:
        raise SystemExit(f"ERROR: could not list Conda environments.\n{r.stdout}\n{r.stderr}")
    return json.loads(r.stdout)


def conda_env_prefix(env_name: str) -> Path | None:
    for env_path in _conda_envs_json().get("envs", []):
        path = Path(env_path)
        if path.name == env_name:
            return path
    return None


def conda_env_exists(env_name: str) -> bool:
    return conda_env_prefix(env_name) is not None


def env_python(manager: str, env_name: str) -> str:
    """Return the path to the env's python interpreter."""
    if manager == "conda":
        prefix = conda_env_prefix(env_name)
        if prefix is None:
            raise SystemExit(f"ERROR: conda env {env_name!r} not found.")
        # On Linux/macOS the layout is <prefix>/bin/python.
        return str(prefix / "bin" / "python")
    venv_dir = Path(env_name).expanduser().resolve()
    bindir = "Scripts" if platform.system() == "Windows" else "bin"
    return str(venv_dir / bindir / "python")


def env_pip_install(manager: str, env_name: str, args: list[str]) -> None:
    """Run `<env-python> -m pip install <args>` directly.

    We deliberately bypass `conda run -n` and call the env's python
    directly because `conda run` reports the *outer* sys.executable on
    some setups (observed on this dev host), which would install into
    the wrong env.
    """
    py = env_python(manager, env_name)
    cmd = [py, "-m", "pip", "install", *args]
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd)


def env_python_run(manager: str, env_name: str, code: str) -> None:
    py = env_python(manager, env_name)
    cmd = [py, "-c", code]
    print(f"+ {' '.join(cmd[:2])} <…>", flush=True)
    subprocess.check_call(cmd)


# ---------------------------------------------------------------------------
# Env creation
# ---------------------------------------------------------------------------
def create_conda_env(env_name: str, python_ver: str) -> Path:
    here = Path(__file__).resolve().parent
    yml = here / "environment.yml"
    prefix = conda_env_prefix(env_name)
    if prefix is not None:
        print(f"[conda] Environment already exists: {env_name}")
        return prefix
    print(f"[conda] Creating environment '{env_name}' from {yml.name} …")
    subprocess.check_call(["conda", "env", "create", "-n", env_name, "-f", str(yml)])
    prefix = conda_env_prefix(env_name)
    if prefix is None:
        raise SystemExit(f"ERROR: could not resolve conda prefix for {env_name} after creation.")
    return prefix


def create_venv_env(env_name: str) -> Path:
    venv_dir = Path(env_name).expanduser().resolve()
    if not venv_dir.exists():
        print(f"[venv] Creating venv at {venv_dir} …")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        print(f"[venv] Venv already exists: {venv_dir}")
    return venv_dir


# ---------------------------------------------------------------------------
# Pip-install steps
# ---------------------------------------------------------------------------
def write_constraints_file(prefix: Path) -> Path:
    share = prefix / "share" / "deepseek-vl2"
    share.mkdir(parents=True, exist_ok=True)
    constraints = share / "constraints.txt"
    constraints.write_text("\n".join(INLINE_CONSTRAINTS) + "\n", encoding="utf-8")
    print(f"[constraints] wrote {constraints}")
    return constraints


def install_base_packaging(manager: str, env_name: str) -> None:
    print("[pip] Upgrading pip / setuptools / wheel …")
    env_pip_install(manager, env_name, ["--upgrade", "pip", "setuptools", "wheel"])


def install_torch(manager: str, env_name: str) -> None:
    print(f"[pip] Installing torch=={TORCH_VERSION} torchvision=={TORCHVISION_VERSION} ({TORCH_CUDA_VARIANT}) …")
    env_pip_install(
        manager, env_name,
        [
            f"torch=={TORCH_VERSION}",
            f"torchvision=={TORCHVISION_VERSION}",
            "--index-url", TORCH_INDEX_URL,
        ],
    )


def install_requirements(manager: str, env_name: str, constraints: Path) -> None:
    here = Path(__file__).resolve().parent
    req = here / "requirements.txt"
    if not req.exists():
        raise SystemExit(f"ERROR: {req} not found.")
    print(f"[pip] Installing {req.name} against {constraints.name} …")
    env_pip_install(
        manager, env_name,
        ["-r", str(req), "-c", str(constraints)],
    )


def install_transformers(manager: str, env_name: str, constraints: Path) -> None:
    """Pin transformers explicitly even though it's also in the constraints."""
    print(f"[pip] Installing transformers=={TRANSFORMERS_VERSION} …")
    env_pip_install(
        manager, env_name,
        [f"transformers=={TRANSFORMERS_VERSION}", "-c", str(constraints)],
    )


def install_deepseek_vl2(manager: str, env_name: str, constraints: Path) -> None:
    print(f"[pip] Installing deepseek-vl2 from {DEEPSEEK_VL2_REPO_URL} (--no-deps) …")
    env_pip_install(
        manager, env_name,
        ["--no-deps", f"deepseek-vl2 @ git+{DEEPSEEK_VL2_REPO_URL}", "-c", str(constraints)],
    )


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
def verify_install(manager: str, env_name: str) -> None:
    print("[verify] Importing torch + transformers + deepseek_vl2 …")
    code = (
        "import torch, transformers;\n"
        "print('torch', torch.__version__);\n"
        "print('cuda available:', torch.cuda.is_available());\n"
        "print('transformers', transformers.__version__);\n"
        "from deepseek_vl2.models import DeepseekVLV2ForCausalLM, DeepseekVLV2Processor;\n"
        "print('OK:', DeepseekVLV2ForCausalLM.__name__, DeepseekVLV2Processor.__name__)\n"
    )
    env_python_run(manager, env_name, code)


def smoke_test(manager: str, env_name: str, image: Path) -> None:
    if not image.exists():
        raise SystemExit(f"ERROR: smoke image not found: {image}")
    here = Path(__file__).resolve().parent
    out_dir = Path("/tmp/vlm_smoke")
    print(f"[smoke] Running smoke_test.py against {image}")
    py = env_python(manager, env_name)
    subprocess.check_call([
        py, str(here / "smoke_test.py"),
        "--image", str(image),
        "--out-dir", str(out_dir),
    ])
    print(f"[smoke] Result written to {out_dir}/vlm_smoke_result.json")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Set up a pdf2md-deepseek-vl2 environment for the semantic VLM backend.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Default: conda env named 'pdf2md-deepseek-vl2'
  %(prog)s

  # Only run preflight checks
  %(prog)s --check-only

  # Skip env-create if you already have the env
  %(prog)s --skip-env-create

  # Also run the model-loading smoke test
  %(prog)s --smoke-image /tmp/sample_page.png
""",
    )
    p.add_argument("--manager", choices=["conda", "venv"], default="conda")
    p.add_argument("--env-name", default=DEFAULT_ENV_NAME, metavar="NAME")
    p.add_argument("--python", default=DEFAULT_PYTHON_VERSION, metavar="VER")
    p.add_argument("--skip-env-create", action="store_true")
    p.add_argument("--skip-checks", action="store_true")
    p.add_argument("--skip-verify", action="store_true")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--smoke-image", type=Path, default=None,
                   help="Optional PNG/JPEG to run through the smoke test after install.")
    return p


def main() -> int:
    args = build_parser().parse_args()

    # -- Preflight --
    if not args.skip_checks:
        print("=" * 60)
        print("  pdf2md-deepseek-vl2 — Preflight Checks")
        print("=" * 60)
        checks, gpu_ok = run_checks()
        for c in checks:
            print(c)
        print()
        if not gpu_ok:
            print(
                "ERROR: DeepSeek-VL2 needs an NVIDIA GPU with ≥16 GB VRAM and CUDA driver ≥11.8.\n"
                "       Use --skip-checks to bypass (e.g. CPU-only experiments) or run on a GPU host.",
            )
            return 1
        if args.check_only:
            print("All checks passed. Use without --check-only to install.")
            return 0

    # -- Env create --
    if args.manager == "conda":
        if not shutil.which("conda"):
            print("ERROR: conda not found on PATH. Use --manager venv or install conda.", file=sys.stderr)
            return 1
        if args.skip_env_create:
            prefix = conda_env_prefix(args.env_name)
            if prefix is None:
                print(f"ERROR: --skip-env-create set, but conda env {args.env_name!r} does not exist.")
                return 1
        else:
            prefix = create_conda_env(args.env_name, args.python)
    else:
        prefix = create_venv_env(args.env_name)

    print(f"[env] prefix: {prefix}")

    # -- pip steps --
    install_base_packaging(args.manager, args.env_name)
    install_torch(args.manager, args.env_name)
    constraints = write_constraints_file(prefix)
    install_requirements(args.manager, args.env_name, constraints)
    install_transformers(args.manager, args.env_name, constraints)
    install_deepseek_vl2(args.manager, args.env_name, constraints)

    # -- Verify --
    if not args.skip_verify:
        verify_install(args.manager, args.env_name)

    if args.smoke_image is not None:
        smoke_test(args.manager, args.env_name, args.smoke_image)

    # -- Summary --
    print()
    print("─" * 60)
    print(f"  pdf2md-deepseek-vl2 install complete.")
    print()
    if args.manager == "conda":
        print(f"    conda activate {args.env_name}")
    else:
        print(f"    source {prefix}/bin/activate")
    print()
    print("  Run the smoke test (will download ~5.6 GB model on first call):")
    print()
    print(f"    python backend/semantic/deepseek_vl2/smoke_test.py \\")
    print(f"        --image <page>.png --out-dir /tmp/vlm_smoke")
    print("─" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
