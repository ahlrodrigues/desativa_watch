# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/data_ops.py
# Comentário: utilitários de dados — localizar coluna ignorando acentos/caixa e ordenar SEMPRE por datetime,
# aplicando a ordenação ao DataFrame inteiro (todas as colunas).

import unicodedata
from typing import Iterable, Tuple
import pandas as pd
import numpy as np

# ------------------------------
# Normalização de nomes de colunas
# ------------------------------

def _strip_accents(s: str) -> str:
    """Remove acentos/diacríticos de uma string."""
    if s is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(s))
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

def _norm_colname(s: str) -> str:
    """Normaliza nome de coluna: remove acentos e põe minúsculas."""
    return _strip_accents(s).lower().strip()

def find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str:
    """
    Encontra uma coluna no DataFrame ignorando acentos/caixa.
    Retorna o nome REAL da coluna no DF.
    """
    norm_map = {_norm_colname(c): c for c in df.columns}
    for cand in candidates:
        key = _norm_colname(cand)
        if key in norm_map:
            return norm_map[key]
    # fallback: contém o termo base
    base_terms = [_norm_colname(c) for c in candidates]
    for norm_name, real_name in norm_map.items():
        if any(bt in norm_name for bt in base_terms):
            return real_name
    raise KeyError(f"Não encontrei nenhuma das colunas candidatas: {list(candidates)}. Colunas: {list(df.columns)}")

# ------------------------------
# Forçar parsing como datetime
# ------------------------------

def _parse_datetime_best(series: pd.Series) -> Tuple[pd.Series, str]:
    """
    Tenta parse de datetime de forma robusta SEMPRE:
      1) tenta dayfirst=True
      2) tenta dayfirst=False
      3) se a maioria for número (serial do Excel), tenta converter via origem 1899-12-30
    Retorna (serie_datetime, metodo_usado).
    """
    # 1) dayfirst=True
    dt1 = pd.to_datetime(series, errors="coerce", dayfirst=True, infer_datetime_format=True, utc=False)
    r1 = dt1.notna().mean()

    # 2) dayfirst=False
    dt2 = pd.to_datetime(series, errors="coerce", dayfirst=False, infer_datetime_format=True, utc=False)
    r2 = dt2.notna().mean()

    # se algum atingir conversão razoável, escolhe o melhor
    if r1 >= r2 and r1 > 0:
        return dt1, "datetime(dayfirst=True)"
    if r2 > r1 and r2 > 0:
        return dt2, "datetime(dayfirst=False)"

    # 3) possível serial numérico do Excel (dias desde 1899-12-30)
    as_num = pd.to_numeric(series, errors="coerce")
    num_ratio = as_num.notna().mean()
    if num_ratio > 0.6:
        dt3 = pd.to_datetime(as_num, unit="d", origin="1899-12-30", errors="coerce", utc=False)
        return dt3, "excel_serial_days"

    # Se nada funcionou, ainda retornamos dt2 (pode ter alguns válidos) para não quebrar
    return dt2, "fallback_partial"

def sort_df_by_integracao_datetime(
    df: pd.DataFrame,
    candidates=("INTEGRACAO", "INTEGRAÇÃO"),
    ascending: bool = True
) -> Tuple[pd.DataFrame, str, str]:
    """
    Ordena o DataFrame INTEIRO pela coluna INTEGRACAO (ou variações), SEMPRE como datetime.
    - Aplica ordenação estável (kind='stable').
    - NaN/NaT vão para o fim (padrão do pandas).
    Retorna (df_ordenado, metodo_de_parse, nome_coluna_real).
    """
    col = find_column(df, candidates)
    dt_series, method = _parse_datetime_best(df[col])

    # adiciona chave temporária e ordena o DF INTEIRO (todas as colunas acompanham)
    sorted_df = (
        df.assign(_sort_key=dt_series)
          .sort_values(by="_sort_key", ascending=ascending, kind="stable")
          .drop(columns=["_sort_key"])
          .reset_index(drop=True)
    )
    return sorted_df, method, col

def top_n_rows(df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
    """Retorna as primeiras N linhas (ou todas, se menos de N)."""
    n = max(0, int(n))
    return df.head(n)
