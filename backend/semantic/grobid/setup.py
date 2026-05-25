#!/usr/bin/env python3
"""setup.py — Set up a GROBID environment for the pdf2md semantic backend.

GROBID is a Java service. This installer mirrors the install pattern
used by the OCR extraction backends (paddleocr, mineru, deepseek, glm):

  1. Preflight HW/SW checks (RAM, disk, Java, port).
  2. Create a conda env (or use an existing venv) named pdf2md-grobid.
  3. Download GROBID source from GitHub into ${CONDA_PREFIX}/share/.
  4. Run `./gradlew clean install --no-daemon` (slow on first run).
  5. Write `${CONDA_PREFIX}/bin/{start_grobid,stop_grobid}` launchers.
  6. Verify the service starts and answers /api/isalive.

No Docker. Replaces the Docker install documented in Plan 005_0.

Environment name convention:  pdf2md-grobid

Official references:
  https://github.com/kermitt2/grobid
  https://grobid.readthedocs.io/
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_ENV_NAME = "pdf2md-grobid"
DEFAULT_PYTHON_VERSION = "3.11"
DEFAULT_GROBID_VERSION = "0.8.1"
GROBID_PORT = 8070

PYTHON_MIN = (3, 10)
PYTHON_MAX = (3, 14)
JAVA_MAJOR_MIN = 17
MIN_RAM_GB = 4
MIN_DISK_GB = 4
WARMUP_TIMEOUT_S = 180          # GROBID warm-up after `gradle run`
WARMUP_POLL_INTERVAL_S = 5


def _grobid_tarball_url(version: str) -> str:
    return f"https://github.com/kermitt2/grobid/archive/refs/tags/{version}.zip"


# ---------------------------------------------------------------------------
# Preflight checks (mirrors paddleocr/mineru/deepseek style)
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


def check_port_free(port: int = GROBID_PORT) -> CheckResult:
    """Best-effort check that nothing is listening on the GROBID port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        result = s.connect_ex(("127.0.0.1", port))
    finally:
        s.close()
    if result == 0:
        return CheckResult(
            f"Port {port}",
            False,
            f"port {port} already in use (set --port to a free port or stop the other process)",
        )
    return CheckResult(f"Port {port}", True, "free")


def check_java(env_check: bool = False) -> CheckResult:
    """Check that `java` is on PATH and reports ≥{JAVA_MAJOR_MIN}.

    Skipped during preflight when env_check=False — the conda env does
    not exist yet so we cannot run its java. The env-create step
    installs openjdk=17, so this check effectively runs after env
    creation only in venv mode.
    """
    if not env_check:
        return CheckResult(
            f"Java ≥{JAVA_MAJOR_MIN}",
            True,
            "deferred (will be installed by conda) or checked from PATH in venv mode",
        )
    java = shutil.which("java")
    if java is None:
        return CheckResult(f"Java ≥{JAVA_MAJOR_MIN}", False, "java not found on PATH")
    r = _run_quiet([java, "-version"])
    # `java -version` writes to stderr.
    text = (r.stderr or "") + (r.stdout or "")
    # Example: 'openjdk version "17.0.10" 2024-01-16'
    for token in text.split():
        token = token.strip('"')
        if token and token[0].isdigit():
            try:
                major = int(token.split(".")[0])
            except ValueError:
                continue
            ok = major >= JAVA_MAJOR_MIN
            return CheckResult(
                f"Java ≥{JAVA_MAJOR_MIN}",
                ok,
                f"Java {major} ({java})" + ("" if ok else f" — need ≥{JAVA_MAJOR_MIN}"),
            )
    return CheckResult(f"Java ≥{JAVA_MAJOR_MIN}", False, f"could not parse java -version output: {text!r}")


def run_checks(env_check: bool = False) -> tuple[list[CheckResult], bool]:
    """Run all preflight checks.  Returns (results, all_critical_ok)."""
    checks = [
        check_os(),
        check_python_version(),
        check_ram(),
        check_disk(),
        check_port_free(),
        check_java(env_check=env_check),
    ]
    # The Java check is critical only when env_check=True (venv mode);
    # otherwise it always passes (deferred).
    critical_ok = all(c.ok for c in checks if c.name != f"Java ≥{JAVA_MAJOR_MIN}" or env_check)
    return checks, critical_ok


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


def conda_run(env_name: str, args: list[str], **kw) -> None:
    cmd = ["conda", "run", "-n", env_name, *args]
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd, **kw)


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
# GROBID download + first-time Gradle build
# ---------------------------------------------------------------------------
def grobid_share_dir(prefix: Path) -> Path:
    return prefix / "share"


def grobid_home(prefix: Path, version: str) -> Path:
    return grobid_share_dir(prefix) / f"grobid-{version}"


def download_grobid_tarball(prefix: Path, version: str, force: bool = False) -> Path:
    share = grobid_share_dir(prefix)
    share.mkdir(parents=True, exist_ok=True)
    zip_path = share / f"grobid-{version}.zip"
    if zip_path.exists() and not force:
        print(f"[grobid] Tarball already cached: {zip_path}")
        return zip_path
    url = _grobid_tarball_url(version)
    print(f"[grobid] Downloading {url} → {zip_path}")
    try:
        urllib.request.urlretrieve(url, str(zip_path))
    except Exception as exc:
        raise SystemExit(f"ERROR: could not download GROBID {version}: {exc}")
    return zip_path


def unzip_grobid(prefix: Path, zip_path: Path, version: str) -> Path:
    target = grobid_home(prefix, version)
    if target.exists():
        print(f"[grobid] Already unpacked: {target}")
        return target
    share = grobid_share_dir(prefix)
    unzip = shutil.which("unzip") or str(prefix / "bin" / "unzip")
    if not Path(unzip).exists():
        raise SystemExit("ERROR: `unzip` not found on PATH (install via conda env or system).")
    print(f"[grobid] Unpacking {zip_path} → {share}")
    subprocess.check_call([unzip, "-q", str(zip_path), "-d", str(share)])
    if not target.exists():
        # Some tarballs unpack to grobid-<sha> instead of grobid-<version>; find it.
        candidates = sorted(share.glob("grobid-*"))
        if not candidates:
            raise SystemExit("ERROR: GROBID source tree not found after unzip.")
        # Rename the unique candidate to the canonical name.
        candidates[-1].rename(target)
    return target


def gradle_install(target: Path, env_name: str, manager: str) -> None:
    """Run `./gradlew clean install --no-daemon` inside the GROBID tree."""
    gradlew = target / "gradlew"
    if not gradlew.exists():
        raise SystemExit(f"ERROR: gradlew not found at {gradlew}.")
    # Make sure gradlew is executable (zip preserves perms on Linux but it's cheap to ensure).
    gradlew.chmod(gradlew.stat().st_mode | 0o111)
    print(f"[grobid] Building (this can take 10–20 min on first run): {target}")
    if manager == "conda":
        conda_run(env_name, ["bash", "-lc", f"cd {target} && ./gradlew clean install --no-daemon"])
    else:
        subprocess.check_call(["./gradlew", "clean", "install", "--no-daemon"], cwd=str(target))


# ---------------------------------------------------------------------------
# Launcher scripts
# ---------------------------------------------------------------------------
START_GROBID_TEMPLATE = """\
#!/usr/bin/env bash
# Auto-generated by backend/semantic/grobid/setup.py.
# Starts the GROBID Java service (Gradle Application plugin).
#
# JAVA_HOME is set explicitly to the conda env's OpenJDK 17 so that
# Gradle does not pick up a stale system-wide JAVA_HOME (commonly
# /usr/lib/jvm/java-8-openjdk-amd64 on Ubuntu, which lacks tools.jar
# and breaks the build).
set -euo pipefail
GROBID_HOME="${GROBID_HOME:-__GROBID_HOME__}"
JAVA_BIN="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/java"
if [[ -x "${JAVA_BIN}" ]]; then
    export JAVA_HOME="$(dirname "$(readlink -f "${JAVA_BIN}")")/.."
fi
cd "${GROBID_HOME}"
exec ./gradlew run --no-daemon "$@"
"""

STOP_GROBID_TEMPLATE = """\
#!/usr/bin/env bash
# Auto-generated by backend/semantic/grobid/setup.py.
# Best-effort stop of any locally running GROBID Java process.
set -uo pipefail
PIDS=$(pgrep -f 'org.grobid.service.main' || true)
if [[ -z "${PIDS}" ]]; then
    echo "No running GROBID process found."
    exit 0
fi
echo "Stopping GROBID PIDs: ${PIDS}"
kill ${PIDS}
"""


def write_launcher_scripts(prefix: Path, grobid_home_path: Path) -> tuple[Path, Path]:
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    start = bin_dir / "start_grobid"
    stop = bin_dir / "stop_grobid"
    start.write_text(
        START_GROBID_TEMPLATE.replace("__GROBID_HOME__", str(grobid_home_path)),
        encoding="utf-8",
    )
    stop.write_text(STOP_GROBID_TEMPLATE, encoding="utf-8")
    start.chmod(0o755)
    stop.chmod(0o755)
    print(f"[grobid] Wrote launcher: {start}")
    print(f"[grobid] Wrote launcher: {stop}")
    return start, stop


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
def poll_isalive(port: int, timeout_s: int, interval_s: int) -> bool:
    import urllib.error
    deadline = time.monotonic() + timeout_s
    url = f"http://localhost:{port}/api/isalive"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                body = resp.read().decode("utf-8", errors="replace").strip().lower()
                if resp.status == 200 and body == "true":
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(interval_s)
    return False


def verify_install(
    start_script: Path,
    stop_script: Path,
    port: int = GROBID_PORT,
    timeout_s: int = WARMUP_TIMEOUT_S,
    interval_s: int = WARMUP_POLL_INTERVAL_S,
    keep_running: bool = False,
) -> None:
    """Background-start GROBID, poll /api/isalive, stop unless --keep-running."""
    print(f"[verify] Starting GROBID via {start_script}")
    log_path = start_script.parent.parent / "var" / "grobid-startup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_fh:
        proc = subprocess.Popen(
            [str(start_script)],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print(f"[verify] PID {proc.pid}; log: {log_path}")
    try:
        ok = poll_isalive(port, timeout_s, interval_s)
        if ok:
            print(f"[verify] /api/isalive → true on port {port}")
        else:
            raise SystemExit(
                f"ERROR: GROBID did not answer /api/isalive within {timeout_s}s. "
                f"Check the startup log: {log_path}",
            )
    finally:
        if not keep_running:
            print(f"[verify] Stopping GROBID via {stop_script}")
            subprocess.run([str(stop_script)], check=False)
            # Best-effort wait for the process group to exit.
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
        else:
            print(
                f"[verify] Leaving GROBID running on port {port}. "
                f"Stop it later with: {stop_script}",
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Set up a pdf2md-grobid environment for semantic backend use.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Default: conda env named 'pdf2md-grobid', GROBID 0.8.1
  %(prog)s

  # Only run preflight checks
  %(prog)s --check-only

  # Skip env-create if you already have the env
  %(prog)s --skip-env-create

  # Skip the Gradle build (assumes ${CONDA_PREFIX}/share/grobid-<v> is ready)
  %(prog)s --skip-build

  # Leave GROBID running after verify so you can use it immediately
  %(prog)s --keep-running
""",
    )
    p.add_argument("--manager", choices=["conda", "venv"], default="conda")
    p.add_argument("--env-name", default=DEFAULT_ENV_NAME, metavar="NAME")
    p.add_argument("--python", default=DEFAULT_PYTHON_VERSION, metavar="VER")
    p.add_argument("--grobid-version", default=DEFAULT_GROBID_VERSION, metavar="VER")
    p.add_argument("--port", type=int, default=GROBID_PORT)
    p.add_argument("--skip-env-create", action="store_true")
    p.add_argument("--skip-build", action="store_true")
    p.add_argument("--skip-checks", action="store_true")
    p.add_argument("--skip-verify", action="store_true")
    p.add_argument("--keep-running", action="store_true")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--force-redownload", action="store_true")
    return p


def main() -> int:
    args = build_parser().parse_args()
    env_check = args.manager == "venv"   # in venv mode, Java must be on PATH already

    # -- Preflight --
    if not args.skip_checks:
        print("=" * 60)
        print("  pdf2md-grobid — Preflight Checks")
        print("=" * 60)
        checks, critical_ok = run_checks(env_check=env_check)
        for c in checks:
            print(c)
        print()
        if not critical_ok:
            print("ERROR: preflight checks failed. Fix the issues above or use --skip-checks.")
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

    # In venv mode (no openjdk installed by conda), confirm Java is on PATH.
    if args.manager == "venv":
        java_check = check_java(env_check=True)
        print(java_check)
        if not java_check.ok:
            print(
                "ERROR: venv mode requires Java ≥17 on PATH. Either install OpenJDK 17 "
                "system-wide or use --manager conda for an all-in-one install.",
            )
            return 1

    # -- Download + Gradle build --
    if not args.skip_build:
        zip_path = download_grobid_tarball(prefix, args.grobid_version, force=args.force_redownload)
        target = unzip_grobid(prefix, zip_path, args.grobid_version)
        gradle_install(target, args.env_name, args.manager)
    else:
        target = grobid_home(prefix, args.grobid_version)
        if not target.exists():
            print(
                f"ERROR: --skip-build set, but {target} does not exist. "
                "Run without --skip-build at least once."
            )
            return 1

    # -- Launchers --
    start_script, stop_script = write_launcher_scripts(prefix, target)

    # -- Verify --
    if not args.skip_verify:
        verify_install(
            start_script, stop_script,
            port=args.port,
            keep_running=args.keep_running,
        )

    # -- Summary --
    print()
    print("─" * 60)
    print("  pdf2md-grobid install complete.")
    print()
    print(f"    GROBID_HOME : {target}")
    print(f"    Start       : {start_script}")
    print(f"    Stop        : {stop_script}")
    print()
    print("  Activate the env and start GROBID:")
    print()
    if args.manager == "conda":
        print(f"    conda activate {args.env_name}")
    else:
        print(f"    source {prefix}/bin/activate")
    print(f"    start_grobid &")
    print(f"    curl -s http://localhost:{args.port}/api/isalive   # → 'true'")
    print()
    print("  Then run the smoke test from the main pdf2md env:")
    print()
    print("    conda run -n pdf2md python backend/semantic/grobid/smoke_test.py \\")
    print("        --pdf <sample>.pdf --out-dir /tmp/grobid_smoke")
    print("─" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
