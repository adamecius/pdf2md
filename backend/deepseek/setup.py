#!/usr/bin/env python3
"""Install DeepSeek-OCR-2 with the corrected CUDA 11.8 environment."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

DEFAULT_ENVNAME = "pdf2md-deepseek"
DEFAULT_ENVFLAVOR = "conda"
DEFAULT_WORKDIR = "~/models/deepseek-ocr2"
DEFAULT_REPO_URL = "https://github.com/deepseek-ai/DeepSeek-OCR-2.git"
DEFAULT_REPO_DIR_NAME = "DeepSeek-OCR-2"
DEFAULT_VLLM_WHEEL_NAME = "vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl"
DEFAULT_VLLM_WHEEL_URL = "https://github.com/vllm-project/vllm/releases/download/v0.8.5/vllm-0.8.5+cu118-cp38-abi3-manylinux1_x86_64.whl"
PYTHON_VERSION = "3.12.9"
NUMPY_VERSION = "2.2.6"

INLINE_REQUIREMENTS = [
    "transformers==4.46.3",
    "tokenizers==0.20.3",
    "PyMuPDF",
    "img2pdf",
    "einops",
    "easydict",
    "addict",
    "Pillow",
    f"numpy=={NUMPY_VERSION}",
]

def log(message: str) -> None:
    print(f"\n[deepseek-ocr2-install] {message}", flush=True)

def fail(message: str) -> None:
    raise SystemExit(f"\n[deepseek-ocr2-install] ERROR: {message}")

def run_command(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command, output=completed.stdout)
    return completed

def require_executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        fail(f"Required executable not found on PATH: {name}")
    return path

def conda_envs_json() -> dict:
    require_executable("conda")
    completed = subprocess.run(["conda", "env", "list", "--json"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if completed.returncode != 0:
        print(completed.stdout)
        fail("Could not list Conda environments.")
    return json.loads(completed.stdout)

def conda_env_prefix(envname: str) -> Path | None:
    for env_path in conda_envs_json().get('envs', []):
        path = Path(env_path)
        if path.name == envname:
            return path
    return None

def conda_env_exists(envname: str) -> bool:
    return conda_env_prefix(envname) is not None

def conda_run(envname: str, args: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["conda", "run", "-n", envname, *args], cwd=cwd, env=env, check=check)

def create_conda_env(envname: str, python_version: str) -> Path:
    require_executable("conda")
    if not conda_env_exists(envname):
        log(f"Creating Conda environment: {envname}")
        run_command(["conda", "create", "-n", envname, f"python={python_version}", "pip", "-y"])
    else:
        log(f"Conda environment already exists: {envname}")
    prefix = conda_env_prefix(envname)
    if prefix is None:
        fail(f"Could not resolve Conda prefix for environment: {envname}")
    return prefix

def install_conda_cuda_toolkit(envname: str) -> None:
    log("Installing NVIDIA CUDA 11.8 toolkit inside the Conda environment")
    run_command(["conda", "install", "-n", envname, "-y", "-c", "nvidia/label/cuda-11.8.0", "cuda-toolkit"])

def write_conda_activation_cuda(prefix: Path) -> None:
    activate_dir = prefix / "etc" / "conda" / "activate.d"
    activate_dir.mkdir(parents=True, exist_ok=True)
    activation_file = activate_dir / "cuda-11.8.sh"
    activation_file.write_text(
        'export CUDA_HOME="$CONDA_PREFIX"\n'
        'export PATH="$CUDA_HOME/bin:$PATH"\n'
        'export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"\n',
        encoding="utf-8",
    )
    log(f"Wrote Conda CUDA activation file: {activation_file}")

def env_with_cuda_home(prefix: Path) -> dict[str, str]:
    env = os.environ.copy()
    env['CUDA_HOME'] = str(prefix)
    env['CONDA_PREFIX'] = str(prefix)
    env['PATH'] = f"{prefix / 'bin'}:{env.get('PATH', '')}"
    env['LD_LIBRARY_PATH'] = f"{prefix / 'lib'}:{prefix / 'lib64'}:{env.get('LD_LIBRARY_PATH', '')}"
    return env

def create_venv(envname: str) -> Path:
    env_path = Path(envname).expanduser().resolve()
    if not env_path.exists():
        log(f"Creating venv: {env_path}")
        run_command([sys.executable, '-m', 'venv', str(env_path)])
    else:
        log(f"venv already exists: {env_path}")
    if not (env_path / 'bin' / 'python').exists():
        fail(f"Could not find venv python at: {env_path / 'bin' / 'python'}")
    return env_path

def find_system_cuda_home() -> Path | None:
    cuda_home = os.environ.get('CUDA_HOME')
    if cuda_home and (Path(cuda_home) / 'bin' / 'nvcc').exists():
        return Path(cuda_home)
    if Path('/usr/local/cuda-11.8/bin/nvcc').exists():
        return Path('/usr/local/cuda-11.8')
    nvcc = shutil.which('nvcc')
    if nvcc:
        return Path(nvcc).resolve().parent.parent
    return None

def parse_nvcc_version(text: str) -> tuple[int, int] | None:
    match = re.search(r'release\s+(\d+)\.(\d+)', text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))

def validate_nvcc(cuda_home: Path) -> None:
    nvcc = cuda_home / 'bin' / 'nvcc'
    if not nvcc.exists():
        fail(f'nvcc not found under CUDA_HOME: {cuda_home}')
    completed = run_command([str(nvcc), '-V'])
    version = parse_nvcc_version(completed.stdout)
    if version is None:
        fail('Could not parse nvcc version.')
    if version < (11, 7):
        fail(f"nvcc is CUDA {version[0]}.{version[1]}, but flash-attn requires CUDA 11.7+. Use Conda mode.")

def clone_repo(repo_url: str, workdir: Path, repo_dir_name: str, update: bool) -> Path:
    require_executable('git')
    workdir.mkdir(parents=True, exist_ok=True)
    repo_dir = workdir / repo_dir_name
    if not (repo_dir / '.git').exists():
        log(f"Cloning DeepSeek-OCR-2 repository into: {repo_dir}")
        run_command(['git', 'clone', repo_url, str(repo_dir)])
    elif update:
        log("Updating DeepSeek-OCR-2 repository with git pull --ff-only")
        run_command(['git', '-C', str(repo_dir), 'pull', '--ff-only'])
    else:
        log(f"Repository already exists: {repo_dir}")
    return repo_dir

def download_file(url: str, target: Path, force: bool = False) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        log(f"File already exists: {target}")
        return target
    log(f"Downloading: {url}")
    print(f"+ download {url} -> {target}", flush=True)
    try:
        with urllib.request.urlopen(url) as response, target.open('wb') as out:
            shutil.copyfileobj(response, out)
    except Exception as exc:
        fail(f'Could not download {url}\n{exc}')
    return target

def pip_install_conda(envname: str, args: list[str], env: dict[str, str]) -> None:
    conda_run(envname, ['python', '-m', 'pip', 'install', *args], env=env)

def pip_install_python(python_exe: str, args: list[str], env: dict[str, str]) -> None:
    run_command([python_exe, '-m', 'pip', 'install', *args], env=env)

def pip_install(envflavor: str, envname: str, python_exe: str | None, args: list[str], env: dict[str, str]) -> None:
    if envflavor == 'conda':
        pip_install_conda(envname, args, env)
    else:
        assert python_exe is not None
        pip_install_python(python_exe, args, env)

def install_base_packaging(envflavor: str, envname: str, python_exe: str | None, env: dict[str, str]) -> None:
    log('Upgrading pip/setuptools/wheel/packaging/ninja')
    pip_install(envflavor, envname, python_exe, ['--upgrade', 'pip', 'setuptools', 'wheel', 'packaging', 'ninja'], env)

def install_torch(envflavor: str, envname: str, python_exe: str | None, env: dict[str, str]) -> None:
    log('Installing PyTorch CUDA 11.8 wheels')
    pip_install(envflavor, envname, python_exe, ['torch==2.6.0', 'torchvision==0.21.0', 'torchaudio==2.6.0', '--index-url', 'https://download.pytorch.org/whl/cu118'], env)

def write_constraints(workdir: Path) -> Path:
    constraints = workdir / 'deepseek-ocr2-constraints.txt'
    constraints.write_text(f'numpy=={NUMPY_VERSION}\n', encoding='utf-8')
    return constraints

def write_inline_requirements(workdir: Path) -> Path:
    req = workdir / 'requirements-deepseek-ocr2-pinned.txt'
    req.write_text('\n'.join(INLINE_REQUIREMENTS) + '\n', encoding='utf-8')
    return req

def install_requirements(envflavor: str, envname: str, python_exe: str | None, repo_dir: Path | None, workdir: Path, env: dict[str, str]) -> None:
    log('Installing DeepSeek-OCR-2 requirements with NumPy pinned')
    constraints = write_constraints(workdir)
    if repo_dir is not None and (repo_dir / 'requirements.txt').exists():
        args = ['-r', str(repo_dir / 'requirements.txt'), '-c', str(constraints)]
    else:
        args = ['-r', str(write_inline_requirements(workdir))]
    pip_install(envflavor, envname, python_exe, args, env)
    pip_install(envflavor, envname, python_exe, [f'numpy=={NUMPY_VERSION}'], env)

def install_flash_attn(envflavor: str, envname: str, python_exe: str | None, env: dict[str, str], max_jobs: int) -> None:
    log('Installing flash-attn 2.7.3')
    install_env = env.copy()
    install_env['MAX_JOBS'] = str(max_jobs)
    pip_install(envflavor, envname, python_exe, ['flash-attn==2.7.3', '--no-build-isolation', '--no-cache-dir'], install_env)

def run_python_code(envflavor: str, envname: str, python_exe: str | None, code: str, env: dict[str, str]) -> None:
    if envflavor == 'conda':
        conda_run(envname, ['python', '-c', code], env=env)
    else:
        assert python_exe is not None
        run_command([python_exe, '-c', code], env=env)

def verify_install(envflavor: str, envname: str, python_exe: str | None, env: dict[str, str], skip_flash_attn: bool) -> None:
    log('Verifying installation')
    code = f'''
import os
import torch
import numpy
import transformers
import tokenizers
print('CUDA_HOME:', os.environ.get('CUDA_HOME'))
print('torch:', torch.__version__)
print('torch cuda:', torch.version.cuda)
print('cuda available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu:', torch.cuda.get_device_name(0))
print('numpy:', numpy.__version__)
print('transformers:', transformers.__version__)
print('tokenizers:', tokenizers.__version__)
import vllm
print('vllm:', getattr(vllm, '__version__', 'unknown'))
if {str(not skip_flash_attn)}:
    import flash_attn
    print('flash-attn:', getattr(flash_attn, '__version__', 'unknown'))
'''
    run_python_code(envflavor, envname, python_exe, code, env)
    log('pip check output follows. The vLLM transformers/tokenizers conflict is expected.')
    if envflavor == 'conda':
        conda_run(envname, ['python', '-m', 'pip', 'check'], env=env, check=False)
    else:
        assert python_exe is not None
        run_command([python_exe, '-m', 'pip', 'check'], env=env, check=False)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Install DeepSeek-OCR-2 corrected CUDA 11.8 environment')
    parser.add_argument('--envname', default=DEFAULT_ENVNAME, help='Conda env name or venv path')
    parser.add_argument('--envflavor', choices=['conda', 'venv'], default=DEFAULT_ENVFLAVOR)
    parser.add_argument('--workdir', default=DEFAULT_WORKDIR)
    parser.add_argument('--repo-url', default=DEFAULT_REPO_URL)
    parser.add_argument('--repo-dir-name', default=DEFAULT_REPO_DIR_NAME)
    parser.add_argument('--python', default=PYTHON_VERSION, help='Python version for Conda env')
    parser.add_argument('--update-repo', action='store_true')
    parser.add_argument('--no-clone-repo', action='store_true')
    parser.add_argument('--vllm-wheel-url', default=DEFAULT_VLLM_WHEEL_URL)
    parser.add_argument('--vllm-wheel', default=None, help='Existing local vLLM wheel path')
    parser.add_argument('--force-download', action='store_true')
    parser.add_argument('--skip-conda-cuda', action='store_true', help='Conda mode only: do not install cuda-toolkit')
    parser.add_argument('--skip-flash-attn', action='store_true')
    parser.add_argument('--max-jobs', type=int, default=4)
    parser.add_argument('--no-verify', action='store_true')
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    workdir = Path(args.workdir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    log(f'Environment flavour: {args.envflavor}')
    log(f'Environment name/path: {args.envname}')
    log(f'Working directory: {workdir}')
    repo_dir: Path | None = None
    python_exe: str | None = None
    if args.envflavor == 'conda':
        prefix = create_conda_env(args.envname, args.python)
        if not args.skip_conda_cuda:
            install_conda_cuda_toolkit(args.envname)
        write_conda_activation_cuda(prefix)
        env = env_with_cuda_home(prefix)
        log('Checking Conda CUDA compiler')
        conda_run(args.envname, ['bash', '-lc', 'which nvcc && nvcc -V'], env=env)
    else:
        env_path = create_venv(args.envname)
        python_exe = str(env_path / 'bin' / 'python')
        cuda_home = find_system_cuda_home()
        if cuda_home is None:
            fail('venv mode requires a valid system CUDA toolkit. Use Conda mode for automatic CUDA 11.8 toolkit installation.')
        validate_nvcc(cuda_home)
        env = os.environ.copy()
        env['CUDA_HOME'] = str(cuda_home)
        env['PATH'] = f"{cuda_home / 'bin'}:{env_path / 'bin'}:{env.get('PATH', '')}"
        env['LD_LIBRARY_PATH'] = f"{cuda_home / 'lib'}:{cuda_home / 'lib64'}:{env.get('LD_LIBRARY_PATH', '')}"
    if not args.no_clone_repo:
        repo_dir = clone_repo(args.repo_url, workdir, args.repo_dir_name, args.update_repo)
    else:
        log('Skipping repository clone as requested')
    install_base_packaging(args.envflavor, args.envname, python_exe, env)
    install_torch(args.envflavor, args.envname, python_exe, env)
    if args.vllm_wheel:
        wheel_path = Path(args.vllm_wheel).expanduser().resolve()
        if not wheel_path.exists():
            fail(f'Provided vLLM wheel does not exist: {wheel_path}')
    else:
        wheel_path = workdir / DEFAULT_VLLM_WHEEL_NAME
        download_file(args.vllm_wheel_url, wheel_path, force=args.force_download)
    log('Installing vLLM 0.8.5 CUDA 11.8 wheel')
    pip_install(args.envflavor, args.envname, python_exe, [str(wheel_path)], env)
    install_requirements(args.envflavor, args.envname, python_exe, repo_dir, workdir, env)
    if not args.skip_flash_attn:
        install_flash_attn(args.envflavor, args.envname, python_exe, env, max_jobs=args.max_jobs)
    else:
        log('Skipping flash-attn installation as requested')
    if not args.no_verify:
        verify_install(args.envflavor, args.envname, python_exe, env, skip_flash_attn=args.skip_flash_attn)
    log('Installation complete')
    if args.envflavor == 'conda':
        print('\nTo activate:\n\n  source ~/miniconda3/etc/profile.d/conda.sh\n  conda activate ' + args.envname)
    else:
        print('\nTo activate:\n\n  source ' + str(Path(args.envname).expanduser().resolve() / 'bin' / 'activate'))
    print('\nRepository:\n\n  ' + (str(repo_dir) if repo_dir is not None else '(not cloned)'))

if __name__ == '__main__':
    main()
