# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/text_sanitizer.py
# Comentário: limpeza e diagnóstico de strings para inputs (remove invisíveis, aspas etc.).

import re

# Conjunto de caracteres "seguros" para e-mails ASCII comuns
# (se você tiver e-mails IDN/Unicode, avise para relaxarmos essa regra)
_EMAIL_SAFE = re.compile(r"[^A-Za-z0-9._%+\-@]")

# Zero-width e espaços problemáticos comuns
_ZERO_WIDTH = [
    "\u200B",  # ZERO WIDTH SPACE
    "\u200C",  # ZERO WIDTH NON-JOINER
    "\u200D",  # ZERO WIDTH JOINER
    "\uFEFF",  # ZERO WIDTH NO-BREAK SPACE (BOM)
]
_SPACE_LIKE = [
    "\u00A0",  # NO-BREAK SPACE
]

def remove_zero_width_and_space_likes(s: str) -> str:
    """Remove caracteres invisíveis (zero-width) e espaços não-quebrantes."""
    for ch in _ZERO_WIDTH + _SPACE_LIKE:
        s = s.replace(ch, "")
    return s

def strip_quotes(s: str) -> str:
    """Remove aspas simples e duplas nas extremidades e internas comuns."""
    return s.strip().strip("'").strip('"')

def sanitize_email_for_input(email: str) -> str:
    """
    Limpeza rigorosa para inputs:
      - remove zero-width e NBSP
      - remove aspas
      - recorta espaços nas bordas
      - remove qualquer char fora do conjunto ASCII típico de e-mail
    """
    e = str(email or "")
    e = remove_zero_width_and_space_likes(e)
    e = strip_quotes(e).strip()
    e = _EMAIL_SAFE.sub("", e)
    return e

def codepoints(s: str) -> str:
    """Retorna os codepoints da string (p/ debug): ex. U+0040 para '@'."""
    return " ".join(f"U+{ord(c):04X}" for c in s)
