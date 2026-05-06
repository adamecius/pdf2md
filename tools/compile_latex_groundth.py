#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compile LaTeX corpus fixtures to PDF + LaTeXML XML")
    p.add_argument("--corpus-root", default="groundtruth/corpus/latex")
    p.add_argument("--doc")
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def parse_version_tuple(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def format_human_task(lines: list[str]) -> None:
    print("HUMAN TASK")
    for line in lines:
        print(f"- {line}")


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)


def validate_environment(require_biber: bool) -> dict[str, str]:
    versions: dict[str, str] = {}

    if not shutil.which("lualatex"):
        format_human_task([
            "Missing required executable: lualatex.",
            "Please install TeX Live, MacTeX, MiKTeX, or a compatible minimal TeX distribution.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)

    luacp = run(["lualatex", "--version"])
    luatext = (luacp.stdout + luacp.stderr).strip()
    versions["lualatex"] = luatext.splitlines()[0] if luatext else "unknown"
    luaver = parse_version_tuple(luatext)
    if luacp.returncode != 0 or luaver is None or luaver < MIN_LUATEX_VERSION:
        detected = luaver if luaver is not None else "unknown"
        format_human_task([
            f"LuaTeX/LuaHBTeX {MIN_LUATEX_VERSION[0]}.{MIN_LUATEX_VERSION[1]}.{MIN_LUATEX_VERSION[2]} or newer is required, but the detected version is {detected}.",
            "Please update TeX Live, MacTeX, MiKTeX, or install a compatible minimal TeX distribution.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)

    if not shutil.which("latexml"):
        format_human_task([
            "Missing required executable: latexml.",
            "Please install LaTeXML and ensure it is on PATH.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)
    lcp = run(["latexml", "--VERSION"])
    if lcp.returncode != 0:
        lcp = run(["latexml", "--version"])
    latexml_text = (lcp.stdout + lcp.stderr).strip()
    versions["latexml"] = latexml_text.splitlines()[0] if latexml_text else "unknown"
    if MIN_LATEXML_VERSION:
        lv = parse_version_tuple(latexml_text)
        if lv is None or lv < MIN_LATEXML_VERSION:
            format_human_task([
                f"LaTeXML {MIN_LATEXML_VERSION[0]}.{MIN_LATEXML_VERSION[1]}.{MIN_LATEXML_VERSION[2]} or newer is required, but the detected version is {lv if lv else 'unknown'}.",
                "Please update LaTeXML installation.",
                "This script does not install external dependencies.",
            ])
            raise SystemExit(42)

    if require_biber:
        if not shutil.which("biber"):
            format_human_task([
                "Missing required executable: biber.",
                "Bibliography processing was detected and biber is required.",
                "This script does not install external dependencies.",
            ])
            raise SystemExit(42)
        bcp = run(["biber", "--version"])
        versions["biber"] = (bcp.stdout + bcp.stderr).splitlines()[0] if (bcp.stdout + bcp.stderr) else "unknown"

    kpse = shutil.which("kpsewhich")
    if not kpse:
        format_human_task([
            "Missing required executable: kpsewhich.",
            "A complete LaTeX environment is required for package validation.",
            "This script does not install external dependencies.",
        ])
        raise SystemExit(42)
    versions["kpsewhich"] = "available"
    for pkg in REQUIRED_KPSE_PACKAGES:
        cp = run(["kpsewhich", pkg])
        if cp.returncode != 0 or not (cp.stdout or "").strip():
            format_human_task([
                f"Required LaTeX package/resource '{pkg}' was not found via kpsewhich.",
                "The LaTeX environment appears incomplete.",
                "This script does not install external dependencies.",
            ])
            raise SystemExit(42)

    return versions


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
    h.update(version_text(["lualatex", "--version"]).encode())
    h.update((version_text(["latexml", "--VERSION"]) or version_text(["latexml", "--version"])).encode())
    if require_biber:
        h.update(version_text(["biber", "--version"]).encode())
    return h.hexdigest()


def main() -> int:
    args = parse_args()
    docs = discover(Path(args.corpus_root), args.doc)
    biber_any = any("\\addbibresource" in (d / f"{d.name}.tex").read_text(encoding="utf-8", errors="ignore") for d in docs)
    versions = validate_environment(require_biber=biber_any)
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

        with tempfile.TemporaryDirectory(prefix=f"{doc}_latex_") as tdir:
            tmp = Path(tdir)
            ltx = ["lualatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-recorder", "-synctex=1", "-output-directory", str(tmp), f"{doc}.tex"]
            logs = []
            for _ in range(2):
                cp = run(ltx, cwd=d)
                logs.append(cp.stdout + cp.stderr)
                if cp.returncode != 0:
                    errors.append("lualatex returned non-zero")
                    break
            if not errors and (tmp / f"{doc}.bcf").exists():
                bcp = run(["biber", "--input-directory", str(tmp), "--output-directory", str(tmp), doc], cwd=d)
                logs.append(bcp.stdout + bcp.stderr)
                if bcp.returncode != 0:
                    errors.append("biber returned non-zero")
                else:
                    for _ in range(2):
                        cp = run(ltx, cwd=d)
                        logs.append(cp.stdout + cp.stderr)
                        if cp.returncode != 0:
                            errors.append("lualatex returned non-zero after biber")
                            break
            joined = "\n".join(logs)
            if re.search(r"^! ", joined, flags=re.M): errors.append("latex fatal line found")
            if "Undefined control sequence" in joined: errors.append("undefined control sequence")
            if re.search(r"Citation[^\n]*undefined", joined, flags=re.I): errors.append("unresolved citations")
            if re.search(r"Reference[^\n]*undefined", joined, flags=re.I): errors.append("unresolved references")
            tp = tmp / f"{doc}.pdf"
            if not tp.exists(): errors.append("final pdf missing")
            if tp.exists(): shutil.copy2(tp, pdf)
            syn = tmp / f"{doc}.synctex.gz"
            if syn.exists(): shutil.copy2(syn, d / syn.name)

        lcmd = ["latexml", f"--destination={doc}.latexml.xml", f"--log={doc}.latexml.log", f"--documentid={doc}"]
        if (d / "assets").is_dir(): lcmd.append("--path=assets")
        lcmd.append(f"{doc}.tex")
        lcp = run(lcmd, cwd=d)
        out = lcp.stdout + lcp.stderr
        if lcp.returncode != 0: errors.append("latexml returned non-zero")
        if re.search(r"\b(Fatal|Error):", out): errors.append("latexml fatal/error output")
        if "Warning:" in out: warnings.append("latexml warnings present")
        if not xml.exists() or xml.stat().st_size == 0: errors.append("latexml xml missing or empty")

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
