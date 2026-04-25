#!/usr/bin/env bash

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_DIR="${ROOT_DIR}/sandbox/backend-installs"
LOG_DIR="${BASE_DIR}/logs"
SUMMARY_FILE="${BASE_DIR}/summary.md"
PYTHON_BIN="${PYTHON_BIN:-python3}"

KNOWN_BACKENDS=(core mineru paddleocr_vl)

mkdir -p "${BASE_DIR}" "${LOG_DIR}" "${BASE_DIR}/pip-cache" "${BASE_DIR}/pycache" "${BASE_DIR}/tmp" "${BASE_DIR}/xdg-cache"

export PIP_CACHE_DIR="${BASE_DIR}/pip-cache"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONPYCACHEPREFIX="${BASE_DIR}/pycache"
export TMPDIR="${BASE_DIR}/tmp"
export XDG_CACHE_HOME="${BASE_DIR}/xdg-cache"

cd "${ROOT_DIR}" || exit 1

usage() {
    cat <<EOF
Usage: bash install_scripts/check_backend_installs.sh [core|mineru|paddleocr_vl|all]...

Creates isolated backend install sandboxes below:
  sandbox/backend-installs

No models are downloaded by this script. It validates dependency installation
and import smoke tests only.
EOF
}

is_known_backend() {
    local backend="$1"
    local known
    for known in "${KNOWN_BACKENDS[@]}"; do
        if [[ "${backend}" == "${known}" ]]; then
            return 0
        fi
    done
    return 1
}

select_backends() {
    SELECTED_BACKENDS=()

    if [[ "$#" -eq 0 ]]; then
        SELECTED_BACKENDS=("${KNOWN_BACKENDS[@]}")
        return 0
    fi

    local arg
    for arg in "$@"; do
        case "${arg}" in
            -h|--help)
                usage
                exit 0
                ;;
            all)
                SELECTED_BACKENDS=("${KNOWN_BACKENDS[@]}")
                return 0
                ;;
            *)
                if ! is_known_backend "${arg}"; then
                    printf 'Unknown backend id: %s\n\n' "${arg}" >&2
                    usage >&2
                    exit 2
                fi
                SELECTED_BACKENDS+=("${arg}")
                ;;
        esac
    done
}

log_line() {
    printf '%s\n' "$*" | tee -a "${LOG_FILE}"
}

log_command() {
    local quoted=()
    local part
    for part in "$@"; do
        quoted+=("$(printf '%q' "${part}")")
    done
    log_line ""
    log_line "+ ${quoted[*]}"
}

run_logged() {
    log_command "$@"
    "$@" >>"${LOG_FILE}" 2>&1
    local status=$?
    log_line "exit status: ${status}"
    return "${status}"
}

last_relevant_error_lines() {
    local lines
    lines="$(grep -Eai 'error|failed|failure|could not|no matching distribution|timeout|timed out|connection|network|traceback|exception|fatal|denied' "${LOG_FILE}" | tail -n 12 || true)"
    if [[ -z "${lines}" ]]; then
        lines="$(tail -n 12 "${LOG_FILE}" || true)"
    fi
    if [[ -z "${lines}" ]]; then
        printf 'none'
    else
        printf '%s' "${lines}"
    fi
}

write_status() {
    local backend="$1"
    local python_version="$2"
    local pip_version="$3"
    local install_success="$4"
    local failed_package="$5"
    local smoke_success="$6"
    local last_error_lines="$7"
    local backend_dir="${BASE_DIR}/${backend}"
    local status_file="${backend_dir}/status.env"

    mkdir -p "${backend_dir}"
    {
        printf 'BACKEND=%q\n' "${backend}"
        printf 'PYTHON_VERSION=%q\n' "${python_version}"
        printf 'PIP_VERSION=%q\n' "${pip_version}"
        printf 'INSTALL_SUCCESS=%q\n' "${install_success}"
        printf 'FAILED_PACKAGE=%q\n' "${failed_package}"
        printf 'SMOKE_SUCCESS=%q\n' "${smoke_success}"
        printf 'LAST_ERROR_LINES=%q\n' "${last_error_lines}"
        printf 'UPDATED_AT=%q\n' "$(date -Iseconds)"
    } >"${status_file}"
}

markdown_cell() {
    local value="${1:-not run}"
    value="${value//$'\n'/<br>}"
    value="${value//|/\\|}"
    value="${value//$'\r'/}"
    if [[ -z "${value}" ]]; then
        printf 'not run'
    else
        printf '%s' "${value}"
    fi
}

generate_summary() {
    local generated_at
    generated_at="$(date -Iseconds)"

    {
        printf '# Backend Install Summary\n\n'
        printf 'Generated: %s\n\n' "${generated_at}"
        printf 'Generated state root: `sandbox/backend-installs`\n\n'
        printf 'This report validates dependency installability and import smoke tests only. It does not download models or validate extraction quality.\n\n'
        printf '| Backend | Updated | Python version | pip version | Installation succeeded | Failed package | Import smoke tests | Last relevant error lines |\n'
        printf '|---|---|---|---|---|---|---|---|\n'

        local backend
        for backend in "${KNOWN_BACKENDS[@]}"; do
            local status_file="${BASE_DIR}/${backend}/status.env"
            local BACKEND="${backend}"
            local PYTHON_VERSION="not run"
            local PIP_VERSION="not run"
            local INSTALL_SUCCESS="not run"
            local FAILED_PACKAGE="not run"
            local SMOKE_SUCCESS="not run"
            local LAST_ERROR_LINES="not run"
            local UPDATED_AT="not run"

            if [[ -f "${status_file}" ]]; then
                # shellcheck disable=SC1090
                source "${status_file}"
            fi

            printf '| `%s` | %s | %s | %s | %s | %s | %s | %s |\n' \
                "${BACKEND}" \
                "$(markdown_cell "${UPDATED_AT}")" \
                "$(markdown_cell "${PYTHON_VERSION}")" \
                "$(markdown_cell "${PIP_VERSION}")" \
                "$(markdown_cell "${INSTALL_SUCCESS}")" \
                "$(markdown_cell "${FAILED_PACKAGE}")" \
                "$(markdown_cell "${SMOKE_SUCCESS}")" \
                "$(markdown_cell "${LAST_ERROR_LINES}")"
        done
    } >"${SUMMARY_FILE}"
}

record_failure_without_venv() {
    local backend="$1"
    local failed_package="$2"
    local smoke_success="no"
    local last_errors
    last_errors="$(last_relevant_error_lines)"
    write_status "${backend}" "unknown" "unknown" "no" "${failed_package}" "${smoke_success}" "${last_errors}"
}

install_backend_packages() {
    local backend="$1"

    FAILED_PACKAGE="none"

    if ! run_logged "${VENV_PY}" -m pip install -r "${ROOT_DIR}/requirements.txt"; then
        FAILED_PACKAGE="requirements.txt"
        return 1
    fi

    if ! run_logged "${VENV_PY}" -m pip install pytest; then
        FAILED_PACKAGE="pytest"
        return 1
    fi

    case "${backend}" in
        core)
            return 0
            ;;
        mineru)
            if ! run_logged "${VENV_PY}" -m pip install mineru; then
                FAILED_PACKAGE="mineru"
                return 1
            fi
            ;;
        paddleocr_vl)
            if ! run_logged "${VENV_PY}" -m pip install paddleocr; then
                FAILED_PACKAGE="paddleocr"
                return 1
            fi
            if ! run_logged "${VENV_PY}" -m pip install paddlepaddle; then
                FAILED_PACKAGE="paddlepaddle"
                return 1
            fi
            ;;
    esac

    return 0
}

run_smoke_tests() {
    local backend="$1"

    case "${backend}" in
        core)
            run_logged "${VENV_PY}" -c 'import fitz, yaml, doc2md; print("core smoke imports ok")'
            ;;
        mineru)
            run_logged "${VENV_PY}" -c 'import importlib, importlib.util; import mineru; print("mineru import ok"); spec = importlib.util.find_spec("magic_pdf"); importlib.import_module("magic_pdf") if spec else None; print("magic_pdf import ok" if spec else "magic_pdf import skipped: not installed")'
            ;;
        paddleocr_vl)
            run_logged "${VENV_PY}" -c 'import paddleocr, paddle; print("paddleocr and paddle smoke imports ok")'
            ;;
    esac
}

check_backend() {
    local backend="$1"
    local backend_dir="${BASE_DIR}/${backend}"
    local venv_dir="${backend_dir}/venv"
    LOG_FILE="${LOG_DIR}/${backend}.log"
    VENV_PY="${venv_dir}/bin/python"
    PYTHON_VERSION="unknown"
    PIP_VERSION="unknown"
    INSTALL_SUCCESS="no"
    SMOKE_SUCCESS="no"
    FAILED_PACKAGE="none"

    mkdir -p "${backend_dir}" "${LOG_DIR}"
    : >"${LOG_FILE}"

    log_line "Backend install check: ${backend}"
    log_line "Started: $(date -Iseconds)"
    log_line "Repository root: ${ROOT_DIR}"
    log_line "Sandbox root: ${BASE_DIR}"
    log_line "Backend environment: ${venv_dir}"
    log_line "Python launcher: ${PYTHON_BIN}"
    log_line "Model downloads: disabled by design; this script only installs packages and imports modules."

    if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
        log_line "ERROR: Python launcher not found: ${PYTHON_BIN}"
        record_failure_without_venv "${backend}" "python"
        generate_summary
        return 1
    fi

    rm -rf "${venv_dir}"

    if ! run_logged "${PYTHON_BIN}" -m venv "${venv_dir}"; then
        record_failure_without_venv "${backend}" "venv"
        generate_summary
        return 1
    fi

    if [[ ! -x "${VENV_PY}" ]]; then
        log_line "ERROR: venv Python was not created at ${VENV_PY}"
        record_failure_without_venv "${backend}" "venv"
        generate_summary
        return 1
    fi

    PYTHON_VERSION="$("${VENV_PY}" -c 'import sys; print(sys.version.replace("\n", " "))' 2>>"${LOG_FILE}" || printf 'unknown')"
    PIP_VERSION="$("${VENV_PY}" -m pip --version 2>>"${LOG_FILE}" || printf 'unknown')"
    log_line "Python version: ${PYTHON_VERSION}"
    log_line "pip version: ${PIP_VERSION}"

    if install_backend_packages "${backend}"; then
        INSTALL_SUCCESS="yes"
    else
        INSTALL_SUCCESS="no"
        log_line "ERROR: installation failed while installing ${FAILED_PACKAGE}"
    fi

    if run_smoke_tests "${backend}"; then
        SMOKE_SUCCESS="yes"
    else
        SMOKE_SUCCESS="no"
        log_line "ERROR: import smoke tests failed for ${backend}"
    fi

    local last_errors
    last_errors="$(last_relevant_error_lines)"
    write_status "${backend}" "${PYTHON_VERSION}" "${PIP_VERSION}" "${INSTALL_SUCCESS}" "${FAILED_PACKAGE}" "${SMOKE_SUCCESS}" "${last_errors}"
    generate_summary

    log_line "Finished: $(date -Iseconds)"
    log_line "Summary: ${SUMMARY_FILE}"

    if [[ "${INSTALL_SUCCESS}" == "yes" && "${SMOKE_SUCCESS}" == "yes" ]]; then
        printf 'Backend %s: succeeded. Log: %s\n' "${backend}" "${LOG_FILE}"
        return 0
    fi

    printf 'Backend %s: failed. Log: %s\n' "${backend}" "${LOG_FILE}" >&2
    printf 'Summary: %s\n' "${SUMMARY_FILE}" >&2
    return 1
}

main() {
    select_backends "$@"

    local failures=0
    local backend
    for backend in "${SELECTED_BACKENDS[@]}"; do
        printf 'Checking backend install sandbox: %s\n' "${backend}"
        if ! check_backend "${backend}"; then
            failures=$((failures + 1))
        fi
    done

    generate_summary
    printf 'Backend install summary: %s\n' "${SUMMARY_FILE}"

    if [[ "${failures}" -gt 0 ]]; then
        return 1
    fi
    return 0
}

main "$@"
