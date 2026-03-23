# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/files.py
# Comentário: localizar e abrir planilhas exportadas (export_never_YYYYMMDD*.xls/xlsx),
# com suporte a .xls "de verdade" (BIFF) e .xls-HTML (arquivo HTML salvo com .xls).

import os
import glob
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple, List

from .config import DOWNLOADS_DIR

def _valida_data_yyyymmdd(date_str: str) -> bool:
    """Valida se a string está no formato YYYYMMDD."""
    if len(date_str) != 8 or not date_str.isdigit():
        return False
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return True
    except ValueError:
        return False

def resolve_data_para_busca(date_str: Optional[str] = None) -> str:
    """
    Retorna a data (YYYYMMDD) a ser usada na busca.
    - Se date_str for válida, usa ela; caso contrário, usa a data atual.
    """
    if date_str and _valida_data_yyyymmdd(date_str):
        return date_str
    return datetime.now().strftime("%Y%m%d")

def localizar_arquivo_export_never(date_str: str) -> Tuple[str, List[str]]:
    """
    Procura arquivos no padrão export_never_YYYYMMDD*.(xls|xlsx) no diretório de downloads.
    Retorna:
      - caminho do arquivo mais recente (por mtime)
      - lista de todos os arquivos encontrados
    Lança FileNotFoundError se não encontrar nenhum.
    """
    padrao_xlsx = os.path.join(DOWNLOADS_DIR, f"export_never_{date_str}*.xlsx")
    padrao_xls  = os.path.join(DOWNLOADS_DIR, f"export_never_{date_str}*.xls")
    matches = glob.glob(padrao_xlsx) + glob.glob(padrao_xls)

    if not matches:
        raise FileNotFoundError(
            "Nenhum arquivo encontrado com padrões:\n"
            f" - {padrao_xlsx}\n"
            f" - {padrao_xls}\n"
            "Dica: confira DOWNLOADS_DIR e a data (YYYYMMDD)."
        )

    # Seleciona o mais recente por mtime
    mais_recente = max(matches, key=lambda p: os.path.getmtime(p))
    return mais_recente, matches

def _eh_html(path: str) -> bool:
    """
    Heurística rápida: verifica os primeiros bytes do arquivo por marcador HTML.
    Alguns exports .xls são, na prática, HTML.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(512).lower()
        return b"<html" in head or b"<!doctype html" in head
    except Exception:
        return False

def _escolher_melhor_tabela(tabelas: List[pd.DataFrame]) -> pd.DataFrame:
    """
    Escolhe a tabela mais "provável" dentre as lidas via read_html:
    critério: maior (linhas x colunas). Em caso de empate, a primeira.
    """
    if not tabelas:
        raise ValueError("read_html não retornou tabelas.")
    def score(df: pd.DataFrame) -> int:
        return int(df.shape[0]) * max(1, int(df.shape[1]))
    tabelas_ordenadas = sorted(tabelas, key=score, reverse=True)
    return tabelas_ordenadas[0]

def abrir_planilha_export_never(path_arquivo: str) -> pd.DataFrame:
    """
    Abre a planilha e retorna um DataFrame.
    Regras:
      - .xlsx → openpyxl
      - .xls:
           * se for BIFF real → xlrd
           * se for HTML disfarçado → pandas.read_html (lxml/bs4)
    """
    ext = os.path.splitext(path_arquivo)[1].lower()

    # .xlsx normal
    if ext == ".xlsx":
        return pd.read_excel(path_arquivo, engine="openpyxl")

    # .xls: pode ser BIFF de verdade ou HTML disfarçado
    if ext == ".xls":
        # Detecta HTML pelo cabeçalho
        if _eh_html(path_arquivo):
            tabelas = pd.read_html(path_arquivo, flavor="lxml")
            return _escolher_melhor_tabela(tabelas)
        # Tenta xlrd (BIFF)
        try:
            return pd.read_excel(path_arquivo, engine="xlrd")
        except Exception as e:
            # Fallback extra: se xlrd falhar e for HTML, tenta read_html
            if _eh_html(path_arquivo):
                tabelas = pd.read_html(path_arquivo, flavor="lxml")
                return _escolher_melhor_tabela(tabelas)
            raise e

    raise ValueError(f"Extensão não suportada: {ext}")
