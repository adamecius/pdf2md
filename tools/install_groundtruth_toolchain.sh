#!/usr/bin/env bash
# Install the extended ground-truth toolchain required by
# tools/compile_latex_groundth.py:
#
#   - lualatex (LuaHBTeX) >= 1.17.0
#   - latexml
#   - biber
#   - kpsewhich + the article.cls / amsmath / hyperref packages
#
# Usage:
#     bash tools/install_groundtruth_toolchain.sh           # detect + install missing
#     bash tools/install_groundtruth_toolchain.sh --check   # detect only, no install
#     bash tools/install_groundtruth_toolchain.sh --verify  # detect + run compile smoke
#
# The script is idempotent: re-running it on a fully provisioned system
# only prints a tool inventory and exits 0.
#
# It does NOT replace an existing TeX Live install. If a new-enough
# lualatex is found on disk (anywhere under /usr/local/texlive/<year>/,
# /opt/texlive/<year>/, or on PATH), it is reused as-is. Only when no
# acceptable lualatex is found does the script attempt apt-get install
# of texlive-luatex etc.; if that still does not give >= 1.17.0, it
# prints clear next-step instructions for installing TeX Live from
# tug.org/texlive.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

MODE="install"
case "${1:-}" in
    --check)  MODE="check" ;;
    --verify) MODE="verify" ;;
    "" )      MODE="install" ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
esac

MIN_LUATEX_MAJOR=1
MIN_LUATEX_MINOR=17

# --- pretty-print helpers ----------------------------------------------------
hr()  { printf '%s\n' "------------------------------------------------------------"; }
h1()  { printf '\n=== %s ===\n' "$1"; }
ok()  { printf '  [ok]    %s\n' "$1"; }
bad() { printf '  [miss]  %s\n' "$1"; }
warn(){ printf '  [warn]  %s\n' "$1"; }
info(){ printf '  [info]  %s\n' "$1"; }

# --- pick the newest lualatex/biber/kpsewhich on disk ------------------------
# Mirrors the discovery logic in tools/compile_latex_groundth.py so what we
# report is what the compile script will use.
discover_texlive_bin_dirs() {
    local roots=("/usr/local/texlive" "/opt/texlive" "/Library/TeX/texlive" "/usr/local/Cellar/texlive")
    local arch
    arch="$(uname -m | tr '[:upper:]' '[:lower:]')"
    for root in "${roots[@]}"; do
        [ -d "$root" ] || continue
        # sort years descending so 2026 wins over 2024
        for year in $(ls -1 "$root" 2>/dev/null | grep -E '^[0-9]+$' | sort -rn); do
            local bin_root="$root/$year/bin"
            [ -d "$bin_root" ] || continue
            # prefer arch-matching dir, then any other
            for d in $(ls -1 "$bin_root" 2>/dev/null | grep -i "$arch"); do
                printf '%s\n' "$bin_root/$d"
            done
            for d in $(ls -1 "$bin_root" 2>/dev/null | grep -iv "$arch"); do
                printf '%s\n' "$bin_root/$d"
            done
        done
    done
}

# Print version-major.minor for a lualatex path, blank if unparseable.
luatex_version() {
    local p="$1"
    "$p" --version 2>&1 | head -1 \
        | sed -nE 's/.*Version[[:space:]]+([0-9]+)\.([0-9]+).*/\1.\2/p'
}

# Echo the best lualatex path (newest version), blank if none.
best_lualatex() {
    local best_path="" best_major=-1 best_minor=-1
    while IFS= read -r d; do
        local cand="$d/lualatex"
        [ -x "$cand" ] || continue
        local v; v="$(luatex_version "$cand")"
        [ -z "$v" ] && continue
        local maj="${v%%.*}" min="${v##*.}"
        if [ "$maj" -gt "$best_major" ] || { [ "$maj" -eq "$best_major" ] && [ "$min" -gt "$best_minor" ]; }; then
            best_major="$maj"; best_minor="$min"; best_path="$cand"
        fi
    done < <(discover_texlive_bin_dirs)

    # also consider PATH
    if command -v lualatex >/dev/null 2>&1; then
        local cand; cand="$(command -v lualatex)"
        local v; v="$(luatex_version "$cand")"
        if [ -n "$v" ]; then
            local maj="${v%%.*}" min="${v##*.}"
            if [ "$maj" -gt "$best_major" ] || { [ "$maj" -eq "$best_major" ] && [ "$min" -gt "$best_minor" ]; }; then
                best_major="$maj"; best_minor="$min"; best_path="$cand"
            fi
        fi
    fi

    printf '%s\n%s.%s\n' "$best_path" "$best_major" "$best_minor"
}

# Find any tool on a TeX Live bin dir or PATH (first hit wins).
find_tool() {
    local name="$1"
    while IFS= read -r d; do
        [ -x "$d/$name" ] && { printf '%s\n' "$d/$name"; return 0; }
    done < <(discover_texlive_bin_dirs)
    command -v "$name" 2>/dev/null
}

# --- step 1: detect ----------------------------------------------------------
h1 "Detecting ground-truth toolchain"

mapfile -t LUA_INFO < <(best_lualatex)
LUALATEX_PATH="${LUA_INFO[0]:-}"
LUALATEX_VER="${LUA_INFO[1]:--1.-1}"
LUALATEX_MAJ="${LUALATEX_VER%%.*}"
LUALATEX_MIN="${LUALATEX_VER##*.}"

LATEXML_PATH="$(find_tool latexml)"
BIBER_PATH="$(find_tool biber)"
KPSE_PATH="$(find_tool kpsewhich)"

LUALATEX_OK=0
if [ -n "$LUALATEX_PATH" ] && [ "$LUALATEX_MAJ" -ge "$MIN_LUATEX_MAJOR" ] 2>/dev/null; then
    if [ "$LUALATEX_MAJ" -gt "$MIN_LUATEX_MAJOR" ] || [ "$LUALATEX_MIN" -ge "$MIN_LUATEX_MINOR" ]; then
        LUALATEX_OK=1
    fi
fi

if [ "$LUALATEX_OK" -eq 1 ]; then
    ok "lualatex $LUALATEX_VER ($LUALATEX_PATH)"
else
    bad "lualatex >= ${MIN_LUATEX_MAJOR}.${MIN_LUATEX_MINOR}.0   (found: ${LUALATEX_PATH:-none}, version ${LUALATEX_VER})"
fi

if [ -n "$LATEXML_PATH" ]; then
    LATEXML_LINE="$("$LATEXML_PATH" --VERSION 2>&1 | head -1)"
    ok "latexml ($LATEXML_PATH) — $LATEXML_LINE"
else
    bad "latexml"
fi

if [ -n "$BIBER_PATH" ]; then
    BIBER_LINE="$("$BIBER_PATH" --version 2>&1 | head -1)"
    ok "biber ($BIBER_PATH) — $BIBER_LINE"
else
    bad "biber"
fi

if [ -n "$KPSE_PATH" ]; then
    ok "kpsewhich ($KPSE_PATH)"
else
    bad "kpsewhich"
fi

# Verify the core LaTeX packages every fixture in groundtruth/corpus/latex/
# uses (article.cls + amsmath + hyperref). DocumentMetadata is part of the
# LaTeX kernel since 2023 and is checked indirectly by the compile run.
PKG_OK=1
if [ -n "$KPSE_PATH" ]; then
    for pkg in article.cls amsmath.sty hyperref.sty; do
        if "$KPSE_PATH" "$pkg" >/dev/null 2>&1 && [ -n "$("$KPSE_PATH" "$pkg" 2>/dev/null)" ]; then
            ok "package $pkg"
        else
            bad "package $pkg (kpsewhich could not locate it)"
            PKG_OK=0
        fi
    done
else
    PKG_OK=0
fi

# --- step 2: decide whether to attempt install -------------------------------
NEED_INSTALL=0
[ "$LUALATEX_OK" -ne 1 ] && NEED_INSTALL=1
[ -z "$LATEXML_PATH" ]   && NEED_INSTALL=1
[ -z "$BIBER_PATH"   ]   && NEED_INSTALL=1
[ -z "$KPSE_PATH"    ]   && NEED_INSTALL=1
[ "$PKG_OK" -ne 1 ]      && NEED_INSTALL=1

if [ "$NEED_INSTALL" -eq 0 ]; then
    h1 "Toolchain status"
    ok "All required tools and packages are present. Nothing to install."
else
    if [ "$MODE" = "check" ]; then
        h1 "Toolchain status"
        warn "One or more components missing — re-run without --check to attempt install."
        exit 1
    fi

    h1 "Installing missing components"

    if ! command -v apt-get >/dev/null 2>&1; then
        warn "apt-get not found; this auto-installer targets Debian/Ubuntu."
        info "Install equivalents of: texlive-luatex texlive-latex-extra texlive-fonts-recommended texlive-bibtex-extra biber latexml"
        info "Then re-run this script."
        exit 3
    fi

    SUDO=""
    if [ "$(id -u)" -ne 0 ]; then
        SUDO="sudo"
        if ! command -v sudo >/dev/null 2>&1; then
            warn "Not running as root and 'sudo' is unavailable."
            info "Re-run this script as root, or apt-get install the packages manually."
            exit 3
        fi
    fi

    PKGS=()
    [ "$LUALATEX_OK" -ne 1 ] && PKGS+=(texlive-luatex texlive-latex-extra texlive-fonts-recommended)
    [ -z "$LATEXML_PATH" ]   && PKGS+=(latexml)
    [ -z "$BIBER_PATH"   ]   && PKGS+=(biber texlive-bibtex-extra)
    [ -z "$KPSE_PATH"    ]   && PKGS+=(texlive-base)
    [ "$PKG_OK" -ne 1 ] && {
        # if amsmath/hyperref missing, ensure latex-extra is in the set
        case " ${PKGS[*]} " in *" texlive-latex-extra "*) ;; *) PKGS+=(texlive-latex-extra) ;; esac
    }

    info "apt-get install -y ${PKGS[*]}"
    $SUDO apt-get update -qq
    if ! $SUDO apt-get install -y "${PKGS[@]}"; then
        warn "apt-get install failed. Inspect the output above."
        exit 4
    fi

    # Re-detect after install
    mapfile -t LUA_INFO < <(best_lualatex)
    LUALATEX_PATH="${LUA_INFO[0]:-}"
    LUALATEX_VER="${LUA_INFO[1]:--1.-1}"
    LUALATEX_MAJ="${LUALATEX_VER%%.*}"
    LUALATEX_MIN="${LUALATEX_VER##*.}"
    LUALATEX_OK=0
    if [ -n "$LUALATEX_PATH" ] && [ "$LUALATEX_MAJ" -ge "$MIN_LUATEX_MAJOR" ] 2>/dev/null; then
        if [ "$LUALATEX_MAJ" -gt "$MIN_LUATEX_MAJOR" ] || [ "$LUALATEX_MIN" -ge "$MIN_LUATEX_MINOR" ]; then
            LUALATEX_OK=1
        fi
    fi

    if [ "$LUALATEX_OK" -ne 1 ]; then
        h1 "lualatex too old after apt-get"
        warn "Detected lualatex version: $LUALATEX_VER at ${LUALATEX_PATH:-none}"
        warn "Debian/Ubuntu's packaged TeX Live is older than ${MIN_LUATEX_MAJOR}.${MIN_LUATEX_MINOR}.0."
        info "Install the upstream TeX Live distribution instead:"
        info "  https://tug.org/texlive/quickinstall.html"
        info "After install, expose its bin dir via PDF2MD_TEXLIVE_BIN_DIR or add it to PATH."
        exit 5
    fi

    ok "Install step completed."
fi

# --- step 3: optional verify (run a minimal compile) -------------------------
if [ "$MODE" = "verify" ] || [ "$MODE" = "install" ]; then
    h1 "Compile smoke test (one fixture)"
    SMOKE_DOC="linked_sections_figures"
    if [ ! -d "$REPO_ROOT/groundtruth/corpus/latex/$SMOKE_DOC" ]; then
        warn "Smoke fixture not found: $REPO_ROOT/groundtruth/corpus/latex/$SMOKE_DOC"
        warn "Skipping compile smoke."
    else
        # Make the TeX Live bin dir we resolved win on PATH so the python
        # script's discovery hits the same install.
        TEXLIVE_BIN_DIR="$(dirname "$LUALATEX_PATH")"
        export PATH="$TEXLIVE_BIN_DIR:$PATH"
        export PDF2MD_TEXLIVE_BIN_DIR="$TEXLIVE_BIN_DIR"

        info "Using TeX Live bin dir: $TEXLIVE_BIN_DIR"
        info "Forcing rebuild of fixture: $SMOKE_DOC"

        if python3 "$REPO_ROOT/tools/compile_latex_groundth.py" \
            --corpus-root "$REPO_ROOT/groundtruth/corpus/latex" \
            --doc "$SMOKE_DOC" \
            --force; then
            ok "Smoke compile succeeded."
        else
            warn "Smoke compile failed. Inspect $REPO_ROOT/groundtruth/corpus/latex/$SMOKE_DOC/build.log"
            exit 6
        fi
    fi
fi

h1 "Done"
ok "Ground-truth toolchain ready."
exit 0
