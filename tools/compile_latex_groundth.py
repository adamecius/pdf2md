#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = "compile_latex_groundth_v1_lualatex_latexml"
MIN_LUATEX_VERSION = (1, 17, 0)
MIN_LATEXML_VERSION: tuple[int, int, int] | None = None
REQUIRED_KPSE_PACKAGES = ["article.cls"]

# TeX Live installs newer than the OS-packaged tex by default land here.
# Each year subdir gets its own `bin/<arch>/` directory. Older Debian /
# Ubuntu packages drop binaries at /usr/bin/. We want the newest version
# found anywhere on disk, falling back to PATH only as a last resort.
TEXLIVE_INSTALL_ROOTS = (
    "/usr/local/texlive",
    "/opt/texlive",
    "/Library/TeX/texlive",
    "/usr/local/Cellar/texlive",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compile LaTeX corpus fixtures to PDF + LaTeXML XML")
    p.add_argument("--corpus-root", default="groundtruth/corpus/latex")
    p.add_argument("--doc")
    p.add_argument("--force", action="store_true")
    p.add_argument(
        "--texlive-bin-dir",
        default=None,
        help=(
            "Explicit TeX Live bin directory to prepend to the resolution "
            "search path (e.g. /usr/local/texlive/2026/bin/x86_64-linux). "
            "Also honoured via the PDF2MD_TEXLIVE_BIN_DIR environment variable."
        ),
    )
    return p.parse_args()


def parse_version_tuple(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def _discover_texlive_bin_dirs(extra_dirs: list[str]) -> list[Path]:
    """Return TeX Live bin directories ordered newest-year first.

    Each install year (e.g. /usr/local/texlive/2026) ships one or more
    arch-specific bin dirs under bin/<arch>/. The newest year is preferred
    so 2026 beats 2024 beats the OS-packaged install.
    """

    seen: set[Path] = set()
    ordered: list[Path] = []

    def _push(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in seen:
            return
        seen.add(resolved)
        ordered.append(resolved)

    for d in extra_dirs:
        p = Path(d)
        if p.is_dir():
            _push(p)

    for root in TEXLIVE_INSTALL_ROOTS:
        if not Path(root).is_dir():
            continue
        # Sort years descending so newer installs win.
        years = sorted(
            (p for p in Path(root).iterdir() if p.is_dir() and p.name.isdigit()),
            key=lambda p: int(p.name),
            reverse=True,
        )
        for year_dir in years:
            bin_root = year_dir / "bin"
            if not bin_root.is_dir():
                continue
            # Prefer arch matching the running host, but fall back to any arch.
            host_arch_hint = platform.machine().lower()
            arch_dirs = sorted(p for p in bin_root.iterdir() if p.is_dir())
            preferred = [p for p in arch_dirs if host_arch_hint in p.name]
            for d in preferred + [p for p in arch_dirs if p not in preferred]:
                _push(d)

    return ordered


def _candidate_executables(name: str, search_dirs: list[Path]) -> list[str]:
    """List candidate executable paths for ``name`` (newest TeX Live first)."""

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        if path and path not in seen and Path(path).is_file() and os.access(path, os.X_OK):
            seen.add(path)
            candidates.append(path)

    for d in search_dirs:
        _add(str(d / name))

    # Also probe every entry on PATH so users with a custom install layout
    # are not penalised.
    path_hit = shutil.which(name)
    if path_hit:
        _add(path_hit)
    for raw in (os.environ.get("PATH") or "").split(os.pathsep):
        if raw:
            _add(str(Path(raw) / name))

    return candidates


def _probe_version(path: str, version_flags: tuple[str, ...] = ("--version",)) -> tuple[int, int, int] | None:
    for flag in version_flags:
        try:
            cp = subprocess.run([path, flag], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            continue
        text = (cp.stdout or "") + (cp.stderr or "")
        ver = parse_version_tuple(text)
        if ver is not None:
            return ver
    return None


def resolve_tool(
    name: str,
    *,
    search_dirs: list[Path],
    version_flags: tuple[str, ...] = ("--version",),
) -> tuple[str | None, tuple[int, int, int] | None]:
    """Return (best_path, best_version) for a TeX-Live executable.

    The best candidate is the one with the highest reported version. If no
    candidate reports a parseable version, the first candidate on disk is
    returned with version=None.
    """

    best_path: str | None = None
    best_ver: tuple[int, int, int] | None = None
    for path in _candidate_executables(name, search_dirs):
        ver = _probe_version(path, version_flags)
        if ver is None:
            if best_path is None:
                best_path = path  # remember a usable fallback
            continue
        if best_ver is None or ver > best_ver:
            best_path = path
            best_ver = ver
    return best_path, best_ver


# Per-invocation tool registry, populated by validate_environment().
TOOLS: dict[str, str] = {}
TOOL_VERSIONS: dict[str, tuple[int, int, int]] = {}


def format_human_task(lines: list[str]) -> None:
    print("HUMAN TASK")
    for line in lines:
        print(f"- {line}")


def run(cmd: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command capturing output, optionally with extra environment vars.

    Extra env (e.g. a prepended PATH pointing at the resolved TeX Live bin
    directory) is merged into the current process environment so subprocesses
    invoked by the called tool — for instance lualatex spawning kpsewhich or
    luaotfload — see the matching TeX Live install.
    """

    env: dict[str, str] | None
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
    else:
        env = None
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, env=env)


def validate_environment(require_biber: bool, *, cli_texlive_bin_dir: str | None = None) -> dict[str, str]:
    versions: dict[str, str] = {}

    extra_dirs: list[str] = []
    env_dir = os.environ.get("PDF2MD_TEXLIVE_BIN_DIR")
    if env_dir:
        extra_dirs.append(env_dir)
    if cli_texlive_bin_dir:
        extra_dirs.append(cli_texlive_bin_dir)

    search_dirs = _discover_texlive_bin_dirs(extra_dirs)

    # --- lualatex --------------------------------------------------------
    lualatex_path, lualatex_ver = resolve_tool("lualatex", search_dirs=search_dirs)
    if lualatex_path is None:
        format_human_task([
            "Missing required executable: lualatex.",
            "Looked in: " + ", ".join(str(d) for d in search_dirs) + " and PATH.",
            "Set --texlive-bin-dir or PDF2MD_TEXLIVE_BIN_DIR to point at the correct install.",
            "Please install TeX Live, MacTeX, MiKTeX, or a compatible minimal TeX distribution.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)

    luacp = subprocess.run([lualatex_path, "--version"], capture_output=True, text=True)
    luatext = (luacp.stdout + luacp.stderr).strip()
    versions["lualatex"] = (
        (luatext.splitlines()[0] if luatext else "unknown") + f"  [{lualatex_path}]"
    )
    if luacp.returncode != 0 or lualatex_ver is None or lualatex_ver < MIN_LUATEX_VERSION:
        detected = lualatex_ver if lualatex_ver is not None else "unknown"
        format_human_task([
            f"LuaTeX/LuaHBTeX {MIN_LUATEX_VERSION[0]}.{MIN_LUATEX_VERSION[1]}.{MIN_LUATEX_VERSION[2]} or newer is required, but the newest detected version is {detected} at {lualatex_path}.",
            "Searched: " + ", ".join(str(d) for d in search_dirs) + " and PATH.",
            "If a newer install lives elsewhere, pass --texlive-bin-dir or set PDF2MD_TEXLIVE_BIN_DIR.",
            "Please update TeX Live, MacTeX, MiKTeX, or install a compatible minimal TeX distribution.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)
    TOOLS["lualatex"] = lualatex_path
    if lualatex_ver:
        TOOL_VERSIONS["lualatex"] = lualatex_ver

    # The resolved lualatex's directory is prepended to PATH for every
    # downstream invocation so subprocesses (kpsewhich, luaotfload, ...)
    # match the same TeX Live install.
    TOOLS["_texlive_bin_dir"] = str(Path(lualatex_path).parent)

    # --- latexml ---------------------------------------------------------
    latexml_path, _ = resolve_tool(
        "latexml",
        search_dirs=search_dirs,
        version_flags=("--VERSION", "--version"),
    )
    if latexml_path is None:
        format_human_task([
            "Missing required executable: latexml.",
            "Please install LaTeXML and ensure it is on PATH.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)
    TOOLS["latexml"] = latexml_path
    lcp = subprocess.run([latexml_path, "--VERSION"], capture_output=True, text=True)
    if lcp.returncode != 0:
        lcp = subprocess.run([latexml_path, "--version"], capture_output=True, text=True)
    latexml_text = (lcp.stdout + lcp.stderr).strip()
    versions["latexml"] = (
        (latexml_text.splitlines()[0] if latexml_text else "unknown") + f"  [{latexml_path}]"
    )
    if MIN_LATEXML_VERSION:
        lv = parse_version_tuple(latexml_text)
        if lv is None or lv < MIN_LATEXML_VERSION:
            format_human_task([
                f"LaTeXML {MIN_LATEXML_VERSION[0]}.{MIN_LATEXML_VERSION[1]}.{MIN_LATEXML_VERSION[2]} or newer is required, but the detected version is {lv if lv else 'unknown'}.",
                "Please update LaTeXML installation.",
                "This script does not install external dependencies.",
            ])
            raise SystemExit(42)

    # --- biber (optional) -----------------------------------------------
    if require_biber:
        biber_path, _ = resolve_tool("biber", search_dirs=search_dirs)
        if biber_path is None:
            format_human_task([
                "Missing required executable: biber.",
                "Bibliography processing was detected and biber is required.",
                "This script does not install external dependencies.",
            ])
            raise SystemExit(42)
        TOOLS["biber"] = biber_path
        bcp = subprocess.run([biber_path, "--version"], capture_output=True, text=True)
        versions["biber"] = (
            ((bcp.stdout + bcp.stderr).splitlines()[0] if (bcp.stdout + bcp.stderr) else "unknown")
            + f"  [{biber_path}]"
        )

    # --- kpsewhich -------------------------------------------------------
    kpse_path, _ = resolve_tool("kpsewhich", search_dirs=search_dirs)
    if kpse_path is None:
        format_human_task([
            "Missing required executable: kpsewhich.",
            "A complete LaTeX environment is required for package validation.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)
    TOOLS["kpsewhich"] = kpse_path
    versions["kpsewhich"] = f"available  [{kpse_path}]"

    texlive_env = {"PATH": TOOLS["_texlive_bin_dir"] + os.pathsep + (os.environ.get("PATH") or "")}
    for pkg in REQUIRED_KPSE_PACKAGES:
        cp = run([kpse_path, pkg], extra_env=texlive_env)
        if cp.returncode != 0 or not (cp.stdout or "").strip():
            format_human_task([
                f"Required LaTeX package/resource '{pkg}' was not found via kpsewhich.",
                f"kpsewhich used: {kpse_path}",
                "The LaTeX environment appears incomplete.",
                "This script does not install external dependencies.",
            ])
            raise SystemExit(42)

    return versions


def texlive_env() -> dict[str, str]:
    """Build the extra-env dict that prepends the resolved TeX Live bin dir to PATH."""

    bin_dir = TOOLS.get("_texlive_bin_dir")
    if not bin_dir:
        return {}
    return {"PATH": bin_dir + os.pathsep + (os.environ.get("PATH") or "")}


def discover(corpus_root: Path, doc: str | None) -> list[Path]:
    if not corpus_root.exists() or not corpus_root.is_dir():
        raise SystemExit(f"Corpus root does not exist or is not a directory: {corpus_root}")
    if doc:
        d = corpus_root / doc
        tex = d / f"{doc}.tex"
        if not tex.exists():
            raise SystemExit(f"Document '{doc}' not found at {tex}")
        return [d]
    return [d for d in sorted(corpus_root.iterdir()) if d.is_dir() and (d / f"{d.name}.tex").exists()]


def version_text(cmd: list[str]) -> str:
    cp = run(cmd)
    return (cp.stdout + cp.stderr).strip() if cp.returncode == 0 else ""


def compute_hash(doc_dir: Path, doc_id: str, require_biber: bool) -> str:
    h = hashlib.sha256()
    h.update(SCHEMA.encode())
    h.update((doc_dir / f"{doc_id}.tex").read_bytes())
    for bib in sorted(doc_dir.rglob("*.bib")):
        h.update(bib.relative_to(doc_dir).as_posix().encode())
        h.update(bib.read_bytes())
    assets = doc_dir / "assets"
    if assets.is_dir():
        for f in sorted(assets.rglob("*")):
            if f.is_file():
                h.update(f.relative_to(doc_dir).as_posix().encode())
                h.update(f.read_bytes())
    h.update(version_text([TOOLS["lualatex"], "--version"]).encode())
    h.update(
        (
            version_text([TOOLS["latexml"], "--VERSION"])
            or version_text([TOOLS["latexml"], "--version"])
        ).encode()
    )
    if require_biber and TOOLS.get("biber"):
        h.update(version_text([TOOLS["biber"], "--version"]).encode())
    return h.hexdigest()


def main() -> int:
    args = parse_args()
    docs = discover(Path(args.corpus_root), args.doc)
    biber_any = any("\\addbibresource" in (d / f"{d.name}.tex").read_text(encoding="utf-8", errors="ignore") for d in docs)
    versions = validate_environment(require_biber=biber_any, cli_texlive_bin_dir=args.texlive_bin_dir)
    print("Detected tool versions:")
    for name, value in versions.items():
        print(f"  {name}: {value}")

    failed: list[str] = []
    for d in docs:
        doc = d.name
        tex = d / f"{doc}.tex"
        pdf = d / f"{doc}.pdf"
        xml = d / f"{doc}.latexml.xml"
        log = d / "build.log"

        require_biber = "\\addbibresource" in tex.read_text(encoding="utf-8", errors="ignore")
        build_hash = compute_hash(d, doc, require_biber)
        old = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
        if not args.force and f"build_hash: {build_hash}" in old and pdf.exists() and xml.exists() and xml.stat().st_size > 0:
            print(f"{doc}: skipped (hash match)")
            continue

        warnings: list[str] = []
        errors: list[str] = []
        text = tex.read_text(encoding="utf-8", errors="ignore")
        dm, dc = text.find("\\DocumentMetadata"), text.find("\\documentclass")
        if dm == -1 or dc == -1 or dm > dc:
            warnings.append(r"\DocumentMetadata not found before \documentclass")

        env_overlay = texlive_env()
        with tempfile.TemporaryDirectory(prefix=f"{doc}_latex_") as tdir:
            tmp = Path(tdir)
            ltx = [TOOLS["lualatex"], "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-recorder", "-synctex=1", "-output-directory", str(tmp), f"{doc}.tex"]
            logs: list[str] = []
            for _ in range(2):
                cp = run(ltx, cwd=d, extra_env=env_overlay)
                logs.append(cp.stdout + cp.stderr)
                if cp.returncode != 0:
                    errors.append("lualatex returned non-zero")
                    break
            if not errors and (tmp / f"{doc}.bcf").exists():
                bcp = run([TOOLS["biber"], "--input-directory", str(tmp), "--output-directory", str(tmp), doc], cwd=d, extra_env=env_overlay)
                logs.append(bcp.stdout + bcp.stderr)
                if bcp.returncode != 0:
                    errors.append("biber returned non-zero")
                else:
                    for _ in range(2):
                        cp = run(ltx, cwd=d, extra_env=env_overlay)
                        logs.append(cp.stdout + cp.stderr)
                        if cp.returncode != 0:
                            errors.append("lualatex returned non-zero after biber")
                            break
            # Citation / reference resolution is iterative: first-pass warnings
            # disappear by the final pass. Check ONLY the final lualatex pass
            # for "undefined" diagnostics, but check ALL passes for fatal lines
            # / undefined control sequences (those persist across passes).
            final_log = logs[-1] if logs else ""
            joined = "\n".join(logs)
            if re.search(r"^! ", joined, flags=re.M):
                errors.append("latex fatal line found")
            if "Undefined control sequence" in joined:
                errors.append("undefined control sequence")
            if re.search(r"Citation[^\n]*undefined", final_log, flags=re.I):
                errors.append("unresolved citations")
            if re.search(r"Reference[^\n]*undefined", final_log, flags=re.I):
                errors.append("unresolved references")
            tp = tmp / f"{doc}.pdf"
            if not tp.exists():
                errors.append("final pdf missing")
            if tp.exists():
                shutil.copy2(tp, pdf)
            syn = tmp / f"{doc}.synctex.gz"
            if syn.exists():
                shutil.copy2(syn, d / syn.name)

        lcmd = [TOOLS["latexml"], f"--destination={doc}.latexml.xml", f"--log={doc}.latexml.log", f"--documentid={doc}"]
        if (d / "assets").is_dir(): lcmd.append("--path=assets")
        lcmd.append(f"{doc}.tex")
        lcp = run(lcmd, cwd=d, extra_env=env_overlay)
        out = lcp.stdout + lcp.stderr
        if lcp.returncode != 0:
            errors.append("latexml returned non-zero")
        xml_ok = xml.exists() and xml.stat().st_size > 0
        if re.search(r"\bFatal:", out):
            # Fatal: is unconditionally an error.
            errors.append("latexml fatal output")
        if re.search(r"\bError:", out):
            # Older latexml (0.8.6) emits Error:undefined:\... for
            # phase-III LaTeX directives like \DocumentMetadata even when
            # it still produces usable XML. Treat Error: lines as a
            # warning when the XML was written, not a build failure.
            if xml_ok:
                warnings.append("latexml error-level diagnostics (xml produced)")
            else:
                errors.append("latexml error output without xml")
        if "Warning:" in out:
            warnings.append("latexml warnings present")
        if not xml_ok:
            errors.append("latexml xml missing or empty")

        with log.open("w", encoding="utf-8") as f:
            f.write(f"build_hash: {build_hash}\n")
            f.write(f"doc_id: {doc}\n")
            f.write("tool_versions:\n")
            for k, v in versions.items():
                f.write(f"- {k}: {v}\n")
            if warnings:
                f.write("warnings:\n")
                for w in warnings: f.write(f"- {w}\n")
            if errors:
                f.write("errors:\n")
                for e in errors: f.write(f"- {e}\n")

        print(f"{doc}: {'failed' if errors else 'built'}")
        if errors: failed.append(doc)

    if failed:
        print("Failed documents: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
