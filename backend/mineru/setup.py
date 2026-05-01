#!/usr/bin/env python3
"""setup.py — Set up a MinerU environment (GPU build, local-first).

Checks that the machine meets MinerU's GPU requirements, creates a
conda or venv environment, and installs MinerU with vLLM acceleration.

Environment name convention:  pdf2md-mineru  (matches the project's
pdf2md-<backend> standard).

Official installation reference:
  https://opendatalab.github.io/MinerU/quick_start/
  https://opendatalab.github.io/MinerU/quick_start/extension_modules/
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
DEFAULT_ENV_NAME = "pdf2md-mineru"
PYTHON_MIN = (3, 10)
PYTHON_MAX = (3, 13)
MIN_VRAM_MB = 8_000          # 8 GB (Volta+, official requirement)
MIN_RAM_GB = 16
MIN_DISK_GB = 20
MINERU_EXTRAS_GPU = "core,vllm"   # GPU build: core + vLLM acceleration
MINERU_EXTRAS_ALL = "all"         # fallback / simple install


# ---------------------------------------------------------------------------
# System checks
# ---------------------------------------------------------------------------
class CheckResult:
    """Container for a single preflight check."""

    def __init__(self, name: str, ok: bool, detail: str):
        self.name = name
        self.ok = ok
        self.detail = detail

    def __str__(self) -> str:
        tag = "  ✓" if self.ok else "  ✗"
        return f"{tag} {self.name}: {self.detail}"


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
    """Check for NVIDIA GPU via nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return CheckResult("NVIDIA GPU", False, "nvidia-smi not found")
    r = _run_quiet(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if r.returncode != 0:
        return CheckResult("NVIDIA GPU", False, f"nvidia-smi failed: {r.stderr.strip()}")
    lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
    if not lines:
        return CheckResult("NVIDIA GPU", False, "no GPUs reported")
    # Parse first GPU
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


def check_cuda_version() -> CheckResult:
    """Check CUDA driver version from nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return CheckResult("CUDA driver", False, "nvidia-smi not found")
    r = _run_quiet(["nvidia-smi"])
    if r.returncode != 0:
        return CheckResult("CUDA driver", False, "nvidia-smi failed")
    # Parse "CUDA Version: 12.x"
    m = re.search(r"CUDA Version:\s+([\d.]+)", r.stdout)
    if not m:
        return CheckResult("CUDA driver", False, "could not parse CUDA version")
    ver = m.group(1)
    major = int(ver.split(".")[0])
    ok = major >= 11
    detail = f"CUDA {ver}" + ("" if ok else " (need ≥11)")
    return CheckResult("CUDA driver", ok, detail)


def check_ram() -> CheckResult:
    """Check total system RAM."""
    try:
        import psutil
        total_gb = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        # Fallback: /proc/meminfo on Linux
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
    """Check free disk space."""
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024**3)
    ok = free_gb >= MIN_DISK_GB
    detail = f"{free_gb:.0f} GB free" + ("" if ok else f" (need ≥{MIN_DISK_GB} GB)")
    return CheckResult("Disk space", ok, detail)


def check_os() -> CheckResult:
    """Basic OS check."""
    s = platform.system()
    ok = s in ("Linux", "Darwin", "Windows")
    detail = f"{s} {platform.release()}"
    if s == "Darwin":
        try:
            mac_ver = tuple(int(x) for x in platform.mac_ver()[0].split(".")[:2])
            if mac_ver < (14, 0):
                return CheckResult("OS", False, f"macOS {platform.mac_ver()[0]} (need ≥14.0)")
        except Exception:
            pass
    return CheckResult("OS", ok, detail)


def run_checks() -> tuple[list[CheckResult], bool]:
    """Run all preflight checks. Returns (results, all_gpu_ok)."""
    checks = [
        check_os(),
        check_python_version(),
        check_nvidia_gpu(),
        check_cuda_version(),
        check_ram(),
        check_disk(),
    ]
    # GPU-critical checks: GPU + CUDA
    gpu_ok = all(c.ok for c in checks if c.name in ("NVIDIA GPU", "CUDA driver"))
    return checks, gpu_ok


# ---------------------------------------------------------------------------
# Environment creation
# ---------------------------------------------------------------------------
def create_conda_env(
    env_name: str,
    python_ver: str,
    *,
    model_source: str = "huggingface",
    model_type: str = "all",
    skip_model_download: bool = False,
) -> None:
    """Create a conda environment and install MinerU."""
    print(f"\n[conda] Creating environment '{env_name}' with Python {python_ver} …")
    subprocess.check_call([
        "conda", "create", "-n", env_name,
        f"python={python_ver}", "-y",
    ])

    conda_run = ["conda", "run", "-n", env_name]

    # Upgrade pip, install uv
    print("[conda] Installing pip + uv …")
    subprocess.check_call(conda_run + ["pip", "install", "--upgrade", "pip"])
    subprocess.check_call(conda_run + ["pip", "install", "uv"])

    # Install MinerU with GPU extras
    print(f"[conda] Installing mineru[{MINERU_EXTRAS_GPU}] …")
    subprocess.check_call(
        conda_run + ["uv", "pip", "install", "-U", f"mineru[{MINERU_EXTRAS_GPU}]"]
    )

    # Download models using CLI flags to skip interactive prompts
    # (click.prompt in mineru-models-download hangs under conda run)
    if not skip_model_download:
        print(f"[conda] Downloading MinerU models from {model_source} (this may take a while) …")
        subprocess.check_call(
            conda_run + [
                "mineru-models-download",
                "-s", model_source,
                "-m", model_type,
            ]
        )
    else:
        print("[conda] Skipping model download (--skip-model-download).")

    print(f"\n✅ Done. Activate with:\n   conda activate {env_name}")


def create_venv_env(
    env_name: str,
    python_exe: str,
    *,
    model_source: str = "huggingface",
    model_type: str = "all",
    skip_model_download: bool = False,
) -> None:
    """Create a venv environment and install MinerU."""
    venv_dir = Path(env_name)
    print(f"\n[venv] Creating virtual environment at '{venv_dir}' …")
    subprocess.check_call([python_exe, "-m", "venv", str(venv_dir)])

    if platform.system() == "Windows":
        pip = str(venv_dir / "Scripts" / "pip")
        py = str(venv_dir / "Scripts" / "python")
    else:
        pip = str(venv_dir / "bin" / "pip")
        py = str(venv_dir / "bin" / "python")

    # Upgrade pip, install uv
    print("[venv] Installing pip + uv …")
    subprocess.check_call([pip, "install", "--upgrade", "pip"])
    subprocess.check_call([pip, "install", "uv"])

    uv = str(venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / "uv")

    # Install MinerU with GPU extras
    print(f"[venv] Installing mineru[{MINERU_EXTRAS_GPU}] …")
    subprocess.check_call([uv, "pip", "install", "-U", f"mineru[{MINERU_EXTRAS_GPU}]"])

    # Locate mineru-models-download binary
    mineru_dl = str(
        venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / "mineru-models-download"
    )
    # Download models using CLI flags to skip interactive prompts
    if not skip_model_download:
        print(f"[venv] Downloading MinerU models from {model_source} (this may take a while) …")
        subprocess.check_call([mineru_dl, "-s", model_source, "-m", model_type])
    else:
        print("[venv] Skipping model download (--skip-model-download).")

    activate = (
        str(venv_dir / "Scripts" / "activate")
        if platform.system() == "Windows"
        else f"source {venv_dir}/bin/activate"
    )
    print(f"\n✅ Done. Activate with:\n   {activate}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Set up a MinerU GPU environment for PDF → Markdown conversion.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Default: conda env named 'pdf2md-mineru'
  %(prog)s

  # Use venv instead of conda
  %(prog)s --manager venv

  # Custom environment name
  %(prog)s --env-name my-mineru-env

  # Skip GPU check (e.g. you know your GPU is fine)
  %(prog)s --skip-checks

  # Dry run: only show check results, don't install
  %(prog)s --check-only
""",
    )
    p.add_argument(
        "--manager", choices=["conda", "venv"], default="conda",
        help="Environment manager to use (default: conda).",
    )
    p.add_argument(
        "--env-name", default=DEFAULT_ENV_NAME, metavar="NAME",
        help="Name for the environment (default: %(default)s).",
    )
    p.add_argument(
        "--python", default="3.11", metavar="VER",
        help="Python version to install in the env (default: %(default)s). "
             "MinerU supports 3.10–3.13.",
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
        "--skip-model-download", action="store_true",
        help="Skip the mineru-models-download step after installation.",
    )
    p.add_argument(
        "--model-source", choices=["huggingface", "modelscope"], default="huggingface",
        help="Model download source (default: huggingface, as recommended "
             "by the official repo).  Use modelscope if HuggingFace is "
             "inaccessible from your network.",
    )
    p.add_argument(
        "--model-type", choices=["pipeline", "vlm", "all"], default="all",
        help="Which model set to download (default: all). "
             "'vlm' = VLM backend only (faster, needs 8 GB+ VRAM), "
             "'pipeline' = CPU pipeline backend only, "
             "'all' = both.",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    args = build_parser().parse_args()

    # -- Preflight checks --
    if not args.skip_checks:
        print("=" * 60)
        print("  MinerU GPU Environment — Preflight Checks")
        print("=" * 60)
        checks, gpu_ok = run_checks()
        for c in checks:
            print(c)
        print()

        all_ok = all(c.ok for c in checks)

        if not gpu_ok:
            print(
                "ERROR: This setup targets GPU-accelerated MinerU (VLM + vLLM).\n"
                "       Your machine does not meet the GPU requirements:\n"
                "         • NVIDIA GPU with Volta architecture or later\n"
                "         • ≥8 GB VRAM\n"
                "         • CUDA driver ≥11\n\n"
                "       We only support the GPU build in this setup script.\n"
                "       If you only have a CPU, you can still install MinerU\n"
                "       manually with the pipeline backend:\n\n"
                "         pip install \"mineru[core]\"\n"
                "         mineru -p input.pdf -o output/ -b pipeline\n\n"
                "       Or connect to a remote GPU server:\n\n"
                "         pip install mineru\n"
                "         mineru -p input.pdf -o output/ -b vlm-http-client \\\n"
                "               -u http://<gpu-server>:30000",
            )
            return 1

        if not all_ok:
            failed = [c for c in checks if not c.ok]
            print("WARNING: Some non-GPU checks failed:")
            for c in failed:
                print(f"  → {c.name}: {c.detail}")
            print()
            ans = input("Continue anyway? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                return 1

        if args.check_only:
            print("All checks passed. Use without --check-only to install.")
            return 0

    # -- Check manager availability --
    if args.manager == "conda" and not shutil.which("conda"):
        print(
            "ERROR: conda not found in PATH.\n"
            "       Install Miniforge/Miniconda first, or use --manager venv.",
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
    print(f"  Creating MinerU GPU environment: {args.env_name}")
    print(f"  Manager: {args.manager}  |  Python: {args.python}")
    print(f"  Install: mineru[{MINERU_EXTRAS_GPU}]")
    print(f"  Models:  {args.model_source} ({args.model_type})" + (" (skipped)" if args.skip_model_download else ""))
    print("=" * 60)

    try:
        kw = dict(
            model_source=args.model_source,
            model_type=args.model_type,
            skip_model_download=args.skip_model_download,
        )
        if args.manager == "conda":
            create_conda_env(args.env_name, args.python, **kw)
        else:
            create_venv_env(args.env_name, sys.executable, **kw)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Installation step failed (exit code {e.returncode}).", file=sys.stderr)
        print("       Check the output above for details.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return 130

    # -- Post-install summary --
    print()
    print("─" * 60)
    print("  Quick reference after activating the environment:")
    print()
    print("    # GPU-accelerated parsing (default: vlm-auto-engine)")
    print("    mineru -p document.pdf -o output/")
    print()
    print("    # CPU-only pipeline backend")
    print("    mineru -p document.pdf -o output/ -b pipeline")
    print()
    print("    # Start API server")
    print("    mineru-api --host 0.0.0.0 --port 8000")
    print("─" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())