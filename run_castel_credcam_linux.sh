#!/usr/bin/env bash
set -Eeuo pipefail

# Arranca siempre desde la raiz del proyecto y usa el entorno virtual aislado.
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_bin="$repo_dir/.venv/bin/python"

on_error() {
    printf '[ERROR] CastelCredCam no pudo iniciar. Revisa la terminal o logs/gui_qt_*.log.\n' >&2
}
trap on_error ERR

if [[ ! -x "$python_bin" ]]; then
    printf '[ERROR] Falta el entorno virtual en %s\n' "$python_bin" >&2
    printf '[INFO] Créalo con: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt\n' >&2
    exit 1
fi

printf '[INFO] Iniciando CastelCredCam en Linux...\n'
cd -- "$repo_dir"
exec "$python_bin" "$repo_dir/GUI/castel_credcam_qt.py" "$@"
