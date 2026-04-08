from __future__ import annotations

import json
import os
from urllib import error, parse, request


def telegram_enabled() -> bool:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    return bool(token and chat_id)


def send_telegram_message(text: str) -> bool:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return False

    payload = parse.urlencode({
        "chat_id": chat_id,
        "text": text,
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = request.Request(url, data=payload, method="POST")

    try:
        with request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except (error.URLError, error.HTTPError, TimeoutError) as exc:
        print(f"⚠️ Falha ao enviar notificação Telegram: {type(exc).__name__}: {exc}")
        return False


def build_run_summary(exec_id: str, total_emails: int, counts: dict[str, int]) -> str:
    lines = [
        "Desativa Watch finalizado.",
        f"Execução: {exec_id}",
        f"Total na fila: {total_emails}",
    ]

    interesting_statuses = [
        "SUCCESS_OK_DESATIVADO",
        "INFO_SEM_WATCH_ATIVO",
        "FAIL_SEM_RESULTADO",
        "FAIL_ERRO",
    ]
    for status in interesting_statuses:
        if counts.get(status):
            lines.append(f"{status}: {counts[status]}")

    return "\n".join(lines)
