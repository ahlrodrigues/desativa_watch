#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
GIT_USER_NAME="${GIT_USER_NAME:-}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-}"
GIT_REMOTE_URL="${GIT_REMOTE_URL:-}"
GIT_DEFAULT_BRANCH="${GIT_DEFAULT_BRANCH:-main}"
GIT_CONFIG_SCOPE="${GIT_CONFIG_SCOPE:-local}"

cd "$ROOT_DIR"

if [ "$GIT_CONFIG_SCOPE" != "local" ] && [ "$GIT_CONFIG_SCOPE" != "global" ]; then
  echo "GIT_CONFIG_SCOPE deve ser 'local' ou 'global'." >&2
  exit 1
fi

git_cfg() {
  if [ "$GIT_CONFIG_SCOPE" = "global" ]; then
    git config --global "$@"
  else
    git config "$@"
  fi
}

echo "==> Pasta do projeto: $ROOT_DIR"

if [ ! -d .git ]; then
  echo "==> Repositório Git não encontrado. Inicializando..."
  git init
  git branch -M "$GIT_DEFAULT_BRANCH"
else
  echo "==> Repositório Git já existe."
fi

if [ -n "$GIT_USER_NAME" ]; then
  echo "==> Configurando user.name"
  git_cfg user.name "$GIT_USER_NAME"
fi

if [ -n "$GIT_USER_EMAIL" ]; then
  echo "==> Configurando user.email"
  git_cfg user.email "$GIT_USER_EMAIL"
fi

if [ -n "$GIT_REMOTE_URL" ]; then
  if git remote get-url origin >/dev/null 2>&1; then
    echo "==> Atualizando remote origin"
    git remote set-url origin "$GIT_REMOTE_URL"
  else
    echo "==> Criando remote origin"
    git remote add origin "$GIT_REMOTE_URL"
  fi
fi

echo
echo "==> Estado atual do Git"
git status --short --branch || true

if git remote get-url origin >/dev/null 2>&1; then
  echo
  echo "==> Remote origin"
  git remote -v
  echo
  echo "==> Fazendo fetch do remoto"
  git fetch origin "$GIT_DEFAULT_BRANCH" || true

  if git show-ref --verify --quiet "refs/remotes/origin/$GIT_DEFAULT_BRANCH"; then
    echo "==> Branch remota encontrada: origin/$GIT_DEFAULT_BRANCH"
    if ! git show-ref --verify --quiet "refs/heads/$GIT_DEFAULT_BRANCH"; then
      git checkout -b "$GIT_DEFAULT_BRANCH" --track "origin/$GIT_DEFAULT_BRANCH"
    fi
  fi
fi

echo
echo "Configuração concluída."
echo "Próximos passos possíveis:"
echo "  git pull origin $GIT_DEFAULT_BRANCH"
echo "  bash scripts/setup-panel-server.sh"
echo "  bash scripts/install-panel-service.sh"
