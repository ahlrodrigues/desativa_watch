#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python não encontrado: $PYTHON_BIN" >&2
  exit 1
fi

echo "==> Projeto: $ROOT_DIR"
echo "==> Python: $PYTHON_BIN"

if [ ! -d "$VENV_DIR" ]; then
  echo "==> Criando virtualenv em $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "==> Atualizando pip"
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "==> Instalando dependências"
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "==> Validando módulos principais"
"$VENV_DIR/bin/python" -m py_compile src/main_consulta_tv.py src/panel_server.py

echo
echo "Ambiente pronto."
echo "Próximo passo:"
echo "  bash scripts/install-panel-service.sh"
