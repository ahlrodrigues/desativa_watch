# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/email_utils.py
# Comentário: utilitários para extrair, normalizar e iterar e-mails a partir do DataFrame.

import re
from typing import Iterable, Iterator, List, Optional
import pandas as pd

# Regex simples e eficaz (RFC-lite) para e-mails
REGEX_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

def _coluna_email(df: pd.DataFrame, preferida: str = "EMAIL") -> str:
    """
    Encontra a coluna de e-mail no DataFrame, tolerando variações de caixa.
    Retorna o nome real da coluna no DF.
    """
    cols_lower = {c.lower(): c for c in df.columns}
    alvo = preferida.lower()
    if alvo in cols_lower:
        return cols_lower[alvo]
    # fallback: qualquer coluna que contenha 'email'
    for c in df.columns:
        if "email" in str(c).lower():
            return c
    raise KeyError("Não encontrei coluna de e-mail na planilha.")

def normalizar_email(raw: str) -> Optional[str]:
    """
    Limpa/normaliza um e-mail bruto:
    - remove espaços e pontuações nas extremidades
    - converte para minúsculas
    - valida com regex
    Retorna e-mail normalizado ou None se inválido.
    """
    if not raw:
        return None
    s = str(raw).strip().lower().strip(" ;,")
    if not s:
        return None
    return s if REGEX_EMAIL.fullmatch(s) else None

def extrair_emails(df: pd.DataFrame, coluna_preferida: str = "EMAIL") -> List[str]:
    """
    Extrai TODOS os e-mails da coluna indicada (ou detectada),
    lidando com múltiplos e-mails por célula.
    Remove duplicados preservando a ordem.
    """
    col = _coluna_email(df, preferida=coluna_preferida)
    encontrados: List[str] = []
    vistos = set()

    for valor in df[col].fillna("").astype(str):
        possiveis = REGEX_EMAIL.findall(valor)
        for raw in possiveis:
            email = normalizar_email(raw)
            if email and email not in vistos:
                vistos.add(email)
                encontrados.append(email)
    return encontrados

def iterar_emails(emails: Iterable[str]) -> Iterator[str]:
    """Iterador simples: entrega um e-mail por vez."""
    for e in emails:
        yield e

def obter_email_por_indice(emails: List[str], indice: int) -> Optional[str]:
    """Retorna o e-mail na posição 'indice' ou None se estiver fora do range."""
    if 0 <= indice < len(emails):
        return emails[indice]
    return None
