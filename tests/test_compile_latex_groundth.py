from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import compile_latex_groundth as m


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def make_doc(root: Path, doc_id: str, body: str = "Hello") -> Path:
    doc_dir = root / doc_id
    doc_dir.mkdir(parents=True)
    (doc_dir / f"{doc_id}.tex").write_text(
        "\\DocumentMetadata{}\n\\documentclass{article}\n\\begin{document}\n"
        f"{body}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    return doc_dir


# ---------------------------------------------------------------------------
# Post-PR-#100 tool-discovery mocking helpers.
#
# PR #100 restructured tool resolution: validate_environment() now resolves
# each executable through ``resolve_tool(name, search_dirs=...)`` (which scans
# /usr/local/texlive/<year>/bin/<arch>/ and probes versions via
# ``subprocess.run``), then main() invokes the resolved absolute paths stored
# in the module-level ``TOOLS`` registry. These helpers patch those seams so
# the tests neither touch the host TeX install nor depend on PATH.
# ---------------------------------------------------------------------------
def _mock_resolve_tool(monkeypatch: pytest.MonkeyPatch, table: dict[str, tuple[str | None, tuple[int, int, int] | None]]) -> None:
    """Patch ``resolve_tool`` to return canned ``(path, version)`` per tool."""
    monkeypatch.setattr(m, "resolve_tool", lambda name, **_: table.get(name, (None, None)))


def _mock_version_probes(monkeypatch: pytest.MonkeyPatch, stdout: str = "This is LuaHBTeX, Version 1.17.0") -> None:
    """Patch the direct ``subprocess.run`` version probes in validate_environment."""
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs: completed(stdout=stdout))


def _install_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate the per-invocation tool registry main() reads from.

    The integration tests mock ``validate_environment`` wholesale, so they
    must seed ``TOOLS`` themselves; the bare command names keep the existing
    ``cmd[0] == "lualatex"`` assertions valid.
    """
    monkeypatch.setattr(
        m,
        "TOOLS",
        {
            "lualatex": "lualatex",
            "latexml": "latexml",
            "biber": "biber",
            "kpsewhich": "kpsewhich",
            "_texlive_bin_dir": "/usr/bin",
        },
    )


def run_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path, *args: str) -> tuple[int, list[tuple[list[str], Path | None]]]:
    calls: list[tuple[list[str], Path | None]] = []
    monkeypatch.setattr(sys, "argv", ["compile_latex_groundth.py", "--corpus-root", str(root), *args])
    monkeypatch.setattr(m, "validate_environment", lambda require_biber, **_: {"lualatex": "LuaHBTeX 1.17.0", "latexml": "LaTeXML 0.8.7", "kpsewhich": "available"})
    monkeypatch.setattr(m, "version_text", lambda cmd: "version")
    _install_tools(monkeypatch)

    def fake_run(cmd: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None):
        calls.append((cmd, cwd))
        if cmd[0] == "lualatex":
            out_dir = Path(cmd[cmd.index("-output-directory") + 1])
            doc_id = Path(cmd[-1]).stem
            (out_dir / f"{doc_id}.pdf").write_bytes(b"%PDF-1.7\n")
            return completed()
        if cmd[0] == "latexml":
            dest = next(part.split("=", 1)[1] for part in cmd if part.startswith("--destination="))
            assert cwd is not None
            (cwd / dest).write_text("<document/>", encoding="utf-8")
            return completed()
        if cmd[0] == "biber":
            return completed()
        return completed()

    monkeypatch.setattr(m, "run", fake_run)
    return m.main(), calls


def test_cli_help_exits_without_checking_tex_tools(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["compile_latex_groundth.py", "--help"])
    monkeypatch.setattr(m.shutil, "which", lambda name: pytest.fail(f"checked unexpected tool {name}"))
    with pytest.raises(SystemExit) as exc:
        m.parse_args()
    assert exc.value.code == 0


def test_discover_finds_fixtures_and_ignores_unrelated_dirs(tmp_path: Path):
    root = tmp_path / "groundtruth" / "corpus" / "latex"
    b_dir = make_doc(root, "b_doc")
    a_dir = make_doc(root, "a_doc")
    (root / "not_a_fixture").mkdir()
    (root / "not_a_fixture" / "other.tex").write_text("ignored", encoding="utf-8")
    assert m.discover(root, None) == [a_dir, b_dir]


def test_doc_argument_restricts_execution_to_one_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "corpus"
    make_doc(root, "alpha")
    make_doc(root, "beta")
    code, calls = run_main(monkeypatch, tmp_path, root, "--doc", "beta")
    assert code == 0
    assert [cwd.name for cmd, cwd in calls if cmd[0] == "latexml"] == ["beta"]


def test_discover_missing_root_exits(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        m.discover(tmp_path / "missing", None)
    assert "Corpus root" in str(exc.value)


def test_discover_missing_doc_exits(tmp_path: Path):
    root = tmp_path / "corpus"
    root.mkdir()
    with pytest.raises(SystemExit) as exc:
        m.discover(root, "abc")
    assert "not found" in str(exc.value)


def test_validate_env_missing_lualatex(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    # No tool resolves -> lualatex is reported missing and the script exits.
    _mock_resolve_tool(monkeypatch, {})
    with pytest.raises(SystemExit) as exc:
        m.validate_environment(False, cli_texlive_bin_dir=None)
    assert exc.value.code == 42
    out = capsys.readouterr().out
    assert "HUMAN TASK" in out
    assert "lualatex" in out


def test_validate_env_missing_latexml(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    _mock_resolve_tool(monkeypatch, {"lualatex": ("/tl/bin/lualatex", (1, 17, 0))})
    _mock_version_probes(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        m.validate_environment(False, cli_texlive_bin_dir=None)
    assert exc.value.code == 42
    out = capsys.readouterr().out
    assert "HUMAN TASK" in out
    assert "latexml" in out


def test_validate_env_old_luatex(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    # lualatex resolves but its version is below the minimum.
    _mock_resolve_tool(monkeypatch, {"lualatex": ("/tl/bin/lualatex", (1, 15, 0))})
    _mock_version_probes(monkeypatch, stdout="This is LuaHBTeX, Version 1.15.0")
    with pytest.raises(SystemExit) as exc:
        m.validate_environment(False, cli_texlive_bin_dir=None)
    assert exc.value.code == 42
    assert "LuaTeX/LuaHBTeX 1.17.0 or newer is required" in capsys.readouterr().out


def test_validate_env_incomplete_kpse(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    # All executables resolve, but a required kpsewhich package lookup fails.
    _mock_resolve_tool(
        monkeypatch,
        {
            "lualatex": ("/tl/bin/lualatex", (1, 17, 0)),
            "latexml": ("/tl/bin/latexml", None),
            "kpsewhich": ("/tl/bin/kpsewhich", None),
        },
    )
    _mock_version_probes(monkeypatch)
    monkeypatch.setattr(m, "run", lambda cmd, cwd=None, extra_env=None: completed(returncode=1))
    with pytest.raises(SystemExit) as exc:
        m.validate_environment(False, cli_texlive_bin_dir=None)
    assert exc.value.code == 42
    assert "incomplete" in capsys.readouterr().out.lower()


def test_lualatex_and_latexml_commands_include_required_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "corpus"
    make_doc(root, "paper")
    code, calls = run_main(monkeypatch, tmp_path, root)
    assert code == 0
    lualatex_cmd = next(cmd for cmd, _ in calls if cmd[0] == "lualatex")
    assert "-interaction=nonstopmode" in lualatex_cmd
    assert "-halt-on-error" in lualatex_cmd
    assert "-file-line-error" in lualatex_cmd
    assert "-recorder" in lualatex_cmd
    assert "-synctex=1" in lualatex_cmd
    assert "-output-directory" in lualatex_cmd
    latexml_cmd = next(cmd for cmd, _ in calls if cmd[0] == "latexml")
    assert "--destination=paper.latexml.xml" in latexml_cmd
    assert "--log=paper.latexml.log" in latexml_cmd
    assert "--documentid=paper" in latexml_cmd


def test_latexml_receives_assets_path_when_assets_dir_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "corpus"
    doc_dir = make_doc(root, "paper")
    (doc_dir / "assets").mkdir()
    code, calls = run_main(monkeypatch, tmp_path, root)
    assert code == 0
    latexml_cmd = next(cmd for cmd, _ in calls if cmd[0] == "latexml")
    assert "--path=assets" in latexml_cmd


def test_bcf_after_first_lualatex_pass_triggers_biber(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "corpus"
    make_doc(root, "paper", "\\addbibresource{refs.bib}")
    (root / "paper" / "refs.bib").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["compile_latex_groundth.py", "--corpus-root", str(root)])
    monkeypatch.setattr(m, "validate_environment", lambda require_biber, **_: {"lualatex": "LuaHBTeX 1.17.0", "latexml": "LaTeXML 0.8.7", "biber": "biber", "kpsewhich": "available"})
    monkeypatch.setattr(m, "version_text", lambda cmd: "version")
    _install_tools(monkeypatch)
    calls: list[list[str]] = []
    lualatex_count = 0

    def fake_run(cmd: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None):
        nonlocal lualatex_count
        calls.append(cmd)
        if cmd[0] == "lualatex":
            lualatex_count += 1
            out_dir = Path(cmd[cmd.index("-output-directory") + 1])
            if lualatex_count == 1:
                (out_dir / "paper.bcf").write_text("bcf", encoding="utf-8")
            (out_dir / "paper.pdf").write_bytes(b"%PDF")
        elif cmd[0] == "latexml":
            assert cwd is not None
            (cwd / "paper.latexml.xml").write_text("<document/>", encoding="utf-8")
        return completed()

    monkeypatch.setattr(m, "run", fake_run)
    assert m.main() == 0
    assert any(cmd[0] == "biber" for cmd in calls)
    assert sum(cmd[0] == "lualatex" for cmd in calls) == 4


def test_matching_hash_skips_unless_force_is_passed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "corpus"
    doc_dir = make_doc(root, "paper")
    (doc_dir / "paper.pdf").write_bytes(b"%PDF")
    (doc_dir / "paper.latexml.xml").write_text("<document/>", encoding="utf-8")
    (doc_dir / "build.log").write_text("build_hash: fixed\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["compile_latex_groundth.py", "--corpus-root", str(root)])
    monkeypatch.setattr(m, "validate_environment", lambda require_biber, **_: {})
    monkeypatch.setattr(m, "compute_hash", lambda doc_dir, doc_id, require_biber: "fixed")
    _install_tools(monkeypatch)
    calls: list[list[str]] = []
    monkeypatch.setattr(m, "run", lambda cmd, cwd=None, extra_env=None: calls.append(cmd) or completed())
    assert m.main() == 0
    assert calls == []

    monkeypatch.setattr(sys, "argv", ["compile_latex_groundth.py", "--corpus-root", str(root), "--force"])
    code, force_calls = run_main(monkeypatch, tmp_path, root, "--force")
    assert code == 0
    assert any(cmd[0] == "lualatex" for cmd, _ in force_calls)


@pytest.mark.parametrize(
    ("latex_log", "latexml_log"),
    [
        ("! fatal error", ""),
        ("Citation `x' undefined", ""),
        ("Reference `x' undefined", ""),
        ("", "Fatal: latexml failed"),
    ],
)
def test_blocking_errors_cause_nonzero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, latex_log: str, latexml_log: str):
    root = tmp_path / "corpus"
    make_doc(root, "paper")
    monkeypatch.setattr(sys, "argv", ["compile_latex_groundth.py", "--corpus-root", str(root)])
    monkeypatch.setattr(m, "validate_environment", lambda require_biber, **_: {})
    monkeypatch.setattr(m, "version_text", lambda cmd: "version")
    _install_tools(monkeypatch)

    def fake_run(cmd: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None):
        if cmd[0] == "lualatex":
            out_dir = Path(cmd[cmd.index("-output-directory") + 1])
            (out_dir / "paper.pdf").write_bytes(b"%PDF")
            return completed(stdout=latex_log)
        if cmd[0] == "latexml":
            assert cwd is not None
            (cwd / "paper.latexml.xml").write_text("<document/>", encoding="utf-8")
            return completed(stdout=latexml_log)
        return completed()

    monkeypatch.setattr(m, "run", fake_run)
    assert m.main() == 1


def test_script_never_rewrites_tex_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    root = tmp_path / "corpus"
    doc_dir = make_doc(root, "paper")
    tex = doc_dir / "paper.tex"
    before = tex.read_bytes()
    code, _ = run_main(monkeypatch, tmp_path, root)
    assert code == 0
    assert tex.read_bytes() == before
