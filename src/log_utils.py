# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/log_utils.py
# Comentário: utilitários de log em CSV (um arquivo por execução), com data/hora da desativação.

import os
import csv
from datetime import datetime
from typing import Dict, Iterable

from .config import OUTPUT_DIR

HEADERS = ["exec_id", "ts", "email", "resultado", "desativado_em", "observacao"]

def ensure_dir(path: str):
    """Garante a existência de uma pasta."""
    os.makedirs(path, exist_ok=True)

def now_ts() -> str:
    """Timestamp legível."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def new_exec_id() -> str:
    """ID de execução (para agrupar linhas no mesmo arquivo)."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def log_path(exec_id: str) -> str:
    """Monta caminho do CSV de log desta execução."""
    ensure_dir(OUTPUT_DIR)
    return os.path.join(OUTPUT_DIR, f"desativa_watch_log_{exec_id}.csv")

def init_log(exec_id: str) -> str:
    """Cria o arquivo com cabeçalho se não existir."""
    path = log_path(exec_id)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=HEADERS).writeheader()
    return path

def append_log(exec_id: str, email: str, resultado: str, desativado_em: str = "", observacao: str = ""):
    """Acrescenta uma linha no CSV."""
    path = init_log(exec_id)
    row = {
        "exec_id": exec_id,
        "ts": now_ts(),
        "email": email,
        "resultado": resultado,           # ex.: OK_DESATIVADO | SEM_WATCH_ATIVO | ERRO
        "desativado_em": desativado_em,   # data/hora em que clicamos "Desativar"
        "observacao": observacao,         # msg livre/erro
    }
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writerow(row)
