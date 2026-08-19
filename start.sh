#!/usr/bin/env bash
# Wrapper fino para run_app.py — inicia backend + frontend + navegador.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERRO: Python não encontrado no PATH. Instale em https://www.python.org/downloads/"
    exit 1
fi

exec "$PYTHON_BIN" run_app.py "$@"
