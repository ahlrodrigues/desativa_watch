#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="${SERVICE_NAME:-desativa-watch-panel}"
SERVICE_USER="${SERVICE_USER:-$(id -un)}"
PANEL_HOST="${PANEL_HOST:-0.0.0.0}"
PANEL_PORT="${PANEL_PORT:-8781}"
TEMPLATE_PATH="$ROOT_DIR/deploy/desativa-watch-panel.service.template"
TMP_FILE="$(mktemp)"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

if [ ! -f "$TEMPLATE_PATH" ]; then
  echo "Template do systemd não encontrado: $TEMPLATE_PATH" >&2
  exit 1
fi

sed \
  -e "s|__USER__|$SERVICE_USER|g" \
  -e "s|__WORKDIR__|$ROOT_DIR|g" \
  -e "s|__PANEL_HOST__|$PANEL_HOST|g" \
  -e "s|__PANEL_PORT__|$PANEL_PORT|g" \
  "$TEMPLATE_PATH" > "$TMP_FILE"

echo "==> Instalando serviço systemd: $SERVICE_NAME"
echo "==> Usuário do serviço: $SERVICE_USER"
echo "==> Porta do painel: $PANEL_PORT"

if command -v sudo >/dev/null 2>&1; then
  sudo cp "$TMP_FILE" "/etc/systemd/system/${SERVICE_NAME}.service"
  sudo systemctl daemon-reload
  sudo systemctl enable --now "${SERVICE_NAME}.service"
  sudo systemctl status "${SERVICE_NAME}.service" --no-pager || true
else
  cp "$TMP_FILE" "/etc/systemd/system/${SERVICE_NAME}.service"
  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}.service"
  systemctl status "${SERVICE_NAME}.service" --no-pager || true
fi

echo
echo "Serviço instalado."
echo "Comandos úteis:"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "  sudo systemctl restart ${SERVICE_NAME}"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
