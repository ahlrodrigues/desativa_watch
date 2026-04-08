from __future__ import annotations

from .config import BLACKLIST_PATH, GREENLIST_PATH


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _read_email_list(path: str) -> list[str]:
    emails: list[str] = []
    seen: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                email = _normalize_email(line)
                if email in seen:
                    continue
                emails.append(email)
                seen.add(email)
    except FileNotFoundError:
        return []
    return emails


def load_blacklist() -> list[str]:
    return _read_email_list(BLACKLIST_PATH)


def load_greenlist() -> list[str]:
    return _read_email_list(GREENLIST_PATH)


def remove_email_from_greenlist(email: str) -> bool:
    """
    Remove um e-mail da greenlist preservando comentários e linhas em branco.
    Retorna True se removeu ao menos uma ocorrência.
    """
    email_norm = _normalize_email(email)
    try:
        with open(GREENLIST_PATH, "r", encoding="utf-8") as f:
            linhas = f.readlines()
    except FileNotFoundError:
        return False

    novas_linhas: list[str] = []
    removeu = False
    for linha in linhas:
        conteudo = linha.strip()
        if conteudo and not conteudo.startswith("#") and _normalize_email(conteudo) == email_norm:
            removeu = True
            continue
        novas_linhas.append(linha)

    if removeu:
        with open(GREENLIST_PATH, "w", encoding="utf-8") as f:
            f.writelines(novas_linhas)
    return removeu


def filtrar_emails_por_listas(emails: list[str]) -> tuple[list[str], dict]:
    blacklist = load_blacklist()
    greenlist = load_greenlist()
    blacklist_set = set(blacklist)
    greenlist_set = set(greenlist)

    emails_normalizados: list[str] = []
    seen_input: set[str] = set()
    for email in emails:
        email_norm = _normalize_email(email)
        if not email_norm or email_norm in seen_input:
            continue
        emails_normalizados.append(email_norm)
        seen_input.add(email_norm)

    if greenlist:
        base_emails = [email for email in greenlist if email in seen_input]
    else:
        base_emails = emails_normalizados

    pulados_blacklist = [email for email in base_emails if email in blacklist_set]
    emails_filtrados = [email for email in base_emails if email not in blacklist_set]

    stats = {
        "originais": len(emails_normalizados),
        "blacklist": len(blacklist),
        "greenlist": len(greenlist),
        "base": len(base_emails),
        "pulados_blacklist": len(pulados_blacklist),
        "finais": len(emails_filtrados),
        "emails_pulados_blacklist": pulados_blacklist,
        "usa_greenlist": bool(greenlist),
    }
    return emails_filtrados, stats
