from __future__ import annotations

from .config import BLACKLIST_PATH, GREENLIST_PATH


def _read_email_list(path: str) -> set[str]:
    emails: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                emails.add(line.lower())
    except FileNotFoundError:
        return set()
    return emails


def load_blacklist() -> set[str]:
    return _read_email_list(BLACKLIST_PATH)


def load_greenlist() -> set[str]:
    return _read_email_list(GREENLIST_PATH)


def filtrar_emails_por_listas(emails: list[str]) -> tuple[list[str], dict]:
    blacklist = load_blacklist()
    greenlist = load_greenlist()

    emails_normalizados = []
    for email in emails:
        email_norm = (email or "").strip().lower()
        if email_norm:
            emails_normalizados.append(email_norm)

    emails_apos_blacklist = [email for email in emails_normalizados if email not in blacklist]
    if greenlist:
        emails_filtrados = [email for email in emails_apos_blacklist if email in greenlist]
    else:
        emails_filtrados = emails_apos_blacklist

    stats = {
        "originais": len(emails_normalizados),
        "blacklist": len(blacklist),
        "greenlist": len(greenlist),
        "apos_blacklist": len(emails_apos_blacklist),
        "finais": len(emails_filtrados),
    }
    return emails_filtrados, stats
