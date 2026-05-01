#!/usr/bin/env python3
"""setup.py — Set up a PaddleOCR environment (GPU build, local-first).

Checks that the machine meets GPU requirements, detects the system CUDA
version, creates a conda or venv environment, and installs PaddlePaddle
(GPU) + PaddleOCR with the correct CUDA variant.

Environment name convention:  pdf2md-paddleocr  (matches the project's
pdf2md-<backend> standard).

Official installation reference:
  https://github.com/PaddlePaddle/PaddleOCR
  https://www.paddlepaddle.org.cn/documentation/docs/en/install/index_en.html
  https://paddlepaddle.github.io/PaddleOCR/main/en/quick_start.html
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
DEFAULT_ENV_NAME = "pdf2md-paddleocr"
PYTHON_MIN = (3, 9)       # 3.9+ required for paddleocr[all]
PYTHON_MAX = (3, 14)
MIN_VRAM_MB = 2_000       # PaddleOCR works on light GPUs; 2 GB minimum
MIN_RAM_GB = 8
MIN_DISK_GB = 10

# PaddlePaddle GPU version → CUDA index URLs
# (ordered newest first — we pick the best match for the system)
PADDLE_VERSION = "3.3.0"
PADDLE_CUDA_MAP = {
    "13.0": f"paddlepaddle-gpu=={PADDLE_VERSION} -i https://www.paddlepaddle.org.cn/packages/stable/cu130/",
    "12.9": f"paddlepaddle-gpu=={PADDLE_VERSION} -i https://www.paddlepaddle.org.cn/packages/stable/cu129/",
    "12.6": f"paddlepaddle-gpu=={PADDLE_VERSION} -i https://www.paddlepaddle.org.cn/packages/stable/cu126/",
    "11.8": f"paddlepaddle-gpu=={PADDLE_VERSION} -i https://www.paddlepaddle.org.cn/packages/stable/cu118/",
}

# PaddleOCR extras to install
PADDLEOCR_INSTALL = '"paddleocr[all]@git+https://github.com/PaddlePaddle/PaddleOCR.git"'


# ---------------------------------------------------------------------------
# System checks
# ---------------------------------------------------------------------------
class CheckResult:
    def __init__(self, name: str, ok: bool, detail: str):
        self.name, self.ok, self.detail = name, ok, detail

    def __str__(self) -> str:
        return f"  {'✓' if self.ok else '✗'} {self.name}: {self.detail}"


def _run_quiet(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


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


def detect_cuda_version() -> tuple[CheckResult, str | None]:
    """Detect CUDA driver version and return the best PaddlePaddle match."""
    if not shutil.which("nvidia-smi"):
        return CheckResult("CUDA driver", False, "nvidia-smi not found"), None
    r = _run_quiet(["nvidia-smi"])
    if r.returncode != 0:
        return CheckResult("CUDA driver", False, "nvidia-smi failed"), None
    m = re.search(r"CUDA Version:\s+([\d.]+)", r.stdout)
    if not m:
        return CheckResult("CUDA driver", False, "could not parse CUDA version"), None

    driver_ver = m.group(1)
    major_minor = tuple(int(x) for x in driver_ver.split(".")[:2])

    # Find best matching PaddlePaddle CUDA variant
    # Driver must be >= the toolkit version
    best_match = None
    for cuda_key in PADDLE_CUDA_MAP:
        key_tuple = tuple(int(x) for x in cuda_key.split("."))
        if major_minor >= key_tuple:
            best_match = cuda_key
            break  # map is ordered newest first

    if best_match is None:
        return (
            CheckResult("CUDA driver", False, f"CUDA {driver_ver} — too old, need ≥11.8"),
            None,
        )

    detail = f"CUDA driver {driver_ver} → will use PaddlePaddle cu{best_match.replace('.', '')}"
    return CheckResult("CUDA driver", True, detail), best_match


def check_ram() -> CheckResult:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
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


def check_os() -> CheckResult:
    s = platform.system()
    ok = s in ("Linux", "Darwin", "Windows")
    return CheckResult("OS", ok, f"{s} {platform.release()}")


def run_checks() -> tuple[list[CheckResult], bool, str | None]:
    """Run all preflight checks.  Returns (results, gpu_ok, cuda_key)."""
    os_chk = check_os()
    py_chk = check_python_version()
    gpu_chk = check_nvidia_gpu()
    cuda_chk, cuda_key = detect_cuda_version()
    ram_chk = check_ram()
    disk_chk = check_disk()

    checks = [os_chk, py_chk, gpu_chk, cuda_chk, ram_chk, disk_chk]
    gpu_ok = gpu_chk.ok and cuda_chk.ok
    return checks, gpu_ok, cuda_key


# ---------------------------------------------------------------------------
# Environment creation
# ---------------------------------------------------------------------------
def _run_in_env(
    manager: str, env_name: str, args: list[str], **kw
) -> subprocess.CompletedProcess:
    """Run a command inside the target environment."""
    if manager == "conda":
        cmd = ["conda", "run", "-n", env_name, *args]
    else:
        venv = Path(env_name)
        bindir = "Scripts" if platform.system() == "Windows" else "bin"
        exe = str(venv / bindir / args[0])
        cmd = [exe, *args[1:]]
    print(f"+ {' '.join(cmd)}", flush=True)
    return subprocess.check_call(cmd, **kw)


def create_env(manager: str, env_name: str, python_ver: str) -> None:
    """Create conda or venv environment."""
    if manager == "conda":
        print(f"\n[conda] Creating environment '{env_name}' with Python {python_ver} …")
        subprocess.check_call([
            "conda", "create", "-n", env_name,
            f"python={python_ver}", "-y",
        ])
    else:
        venv_dir = Path(env_name)
        print(f"\n[venv] Creating virtual environment at '{venv_dir}' …")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])


def install_packages(
    manager: str,
    env_name: str,
    cuda_key: str,
    install_from_git: bool,
) -> None:
    """Install PaddlePaddle GPU + PaddleOCR."""
    # Upgrade pip
    print(f"\n[{manager}] Upgrading pip …")
    _run_in_env(manager, env_name, ["pip", "install", "--upgrade", "pip"])

    # PaddlePaddle GPU
    paddle_spec = PADDLE_CUDA_MAP[cuda_key]
    parts = paddle_spec.split(" -i ")
    paddle_pkg = parts[0]
    paddle_index = parts[1] if len(parts) > 1 else None

    print(f"\n[{manager}] Installing {paddle_pkg} (CUDA {cuda_key}) …")
    pip_args = ["pip", "install", paddle_pkg]
    if paddle_index:
        pip_args.extend(["-i", paddle_index])
    _run_in_env(manager, env_name, pip_args)

    # PaddleOCR
    if install_from_git:
        print(f"\n[{manager}] Installing paddleocr[all] from GitHub (latest) …")
        _run_in_env(manager, env_name, [
            "pip", "install",
            "paddleocr[all]@git+https://github.com/PaddlePaddle/PaddleOCR.git",
        ])
    else:
        print(f"\n[{manager}] Installing paddleocr[all] from PyPI …")
        _run_in_env(manager, env_name, [
            "pip", "install", "-U", "paddleocr[all]",
        ])


def verify_install(manager: str, env_name: str) -> None:
    """Quick smoke test."""
    print(f"\n[{manager}] Verifying installation …")
    code = (
        "import paddle; "
        "print('PaddlePaddle:', paddle.__version__); "
        "print('CUDA available:', paddle.is_compiled_with_cuda()); "
        "import paddleocr; "
        "print('PaddleOCR: OK')"
    )
    _run_in_env(manager, env_name, ["python", "-c", code])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Set up a PaddleOCR GPU environment for PDF → Markdown conversion.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Default: conda env named 'pdf2md-paddleocr'
  %(prog)s

  # Use venv instead of conda
  %(prog)s --manager venv

  # Force a specific CUDA variant
  %(prog)s --cuda 12.6

  # Install from GitHub HEAD instead of PyPI
  %(prog)s --from-git

  # Dry run: only show check results
  %(prog)s --check-only
""",
    )
    p.add_argument(
        "--manager", choices=["conda", "venv"], default="conda",
        help="Environment manager (default: conda).",
    )
    p.add_argument(
        "--env-name", default=DEFAULT_ENV_NAME, metavar="NAME",
        help="Environment name (default: %(default)s).",
    )
    p.add_argument(
        "--python", default="3.11", metavar="VER",
        help="Python version (default: %(default)s). "
             "PaddleOCR[all] requires ≥3.9.",
    )
    p.add_argument(
        "--cuda", default=None, choices=list(PADDLE_CUDA_MAP.keys()), metavar="VER",
        help="Force a specific CUDA variant for PaddlePaddle "
             f"(choices: {', '.join(PADDLE_CUDA_MAP.keys())}). "
             "Default: auto-detected from nvidia-smi.",
    )
    p.add_argument(
        "--from-git", action="store_true",
        help="Install PaddleOCR from GitHub HEAD instead of PyPI "
             "(gets the very latest code).",
    )
    p.add_argument(
        "--skip-checks", action="store_true",
        help="Skip preflight hardware/software checks.",
    )
    p.add_argument(
        "--check-only", action="store_true",
        help="Only run checks, do not create the environment.",
    )
    p.add_argument(
        "--no-verify", action="store_true",
        help="Skip post-install verification.",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    args = build_parser().parse_args()
    cuda_key = args.cuda

    # -- Preflight checks --
    if not args.skip_checks:
        print("=" * 60)
        print("  PaddleOCR GPU Environment — Preflight Checks")
        print("=" * 60)
        checks, gpu_ok, detected_cuda = run_checks()
        for c in checks:
            print(c)
        print()

        if cuda_key is None:
            cuda_key = detected_cuda

        if not gpu_ok:
            print(
                "ERROR: This setup targets GPU-accelerated PaddleOCR.\n"
                "       Your machine does not meet the GPU requirements:\n"
                "         • NVIDIA GPU with ≥2 GB VRAM\n"
                "         • CUDA driver ≥11.8\n\n"
                "       We only support the GPU build in this script.\n"
                "       For CPU-only usage, install manually:\n\n"
                "         pip install paddlepaddle\n"
                "         pip install paddleocr[all]",
            )
            return 1

        non_gpu_fails = [c for c in checks if not c.ok and c.name not in ("NVIDIA GPU", "CUDA driver")]
        if non_gpu_fails:
            print("WARNING: Some non-GPU checks failed:")
            for c in non_gpu_fails:
                print(f"  → {c.name}: {c.detail}")
            print()
            ans = input("Continue anyway? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                return 1

        if args.check_only:
            print("All checks passed. Run without --check-only to install.")
            return 0
    else:
        if cuda_key is None:
            # Must detect even when skipping checks
            _, _, cuda_key = run_checks()
            if cuda_key is None:
                print("ERROR: Could not detect CUDA version. Use --cuda to specify.", file=sys.stderr)
                return 1

    # -- Check manager availability --
    if args.manager == "conda" and not shutil.which("conda"):
        print(
            "ERROR: conda not found. Install Miniforge/Miniconda first, "
            "or use --manager venv.",
            file=sys.stderr,
        )
        return 1

    # -- Check if environment already exists --
    if args.manager == "conda":
        r = _run_quiet(["conda", "env", "list", "--json"])
        if r.returncode == 0:
            envs = json.loads(r.stdout).get("envs", [])
            if any(Path(e).name == args.env_name for e in envs):
                print(f"ERROR: Conda environment '{args.env_name}' already exists.")
                print(f"       Remove it first:  conda env remove -n {args.env_name} -y")
                return 1
    else:
        if Path(args.env_name).exists():
            print(f"ERROR: Directory '{args.env_name}' already exists.")
            return 1

    # -- Create environment --
    print("=" * 60)
    print(f"  Creating PaddleOCR GPU environment: {args.env_name}")
    print(f"  Manager: {args.manager}  |  Python: {args.python}")
    print(f"  PaddlePaddle: {PADDLE_VERSION}  |  CUDA: {cuda_key}")
    print(f"  PaddleOCR:  {'GitHub HEAD' if args.from_git else 'PyPI (latest)'}")
    print("=" * 60)

    try:
        create_env(args.manager, args.env_name, args.python)
        install_packages(args.manager, args.env_name, cuda_key, args.from_git)
        if not args.no_verify:
            verify_install(args.manager, args.env_name)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Installation step failed (exit code {e.returncode}).", file=sys.stderr)
        print("       Check the output above for details.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return 130

    # -- Post-install summary --
    if args.manager == "conda":
        activate = f"conda activate {args.env_name}"
    else:
        activate = f"source {args.env_name}/bin/activate"

    print()
    print("─" * 60)
    print(f"  ✅ Done. Activate with:\n     {activate}")
    print()
    print("  Quick reference:")
    print()
    print("    # PP-OCRv5 text recognition")
    print("    paddleocr pp_ocrv5 -i document.pdf")
    print()
    print("    # PP-StructureV3 document parsing → Markdown")
    print("    paddleocr pp_structurev3 -i document.pdf")
    print()
    print("    # PaddleOCR-VL (vision-language model)")
    print("    paddleocr paddleocr_vl -i document.pdf")
    print("─" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
