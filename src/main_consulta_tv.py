# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/main_consulta_tv.py
# Comentário: Fluxo end-to-end consolidado usando a greenlist como fila principal:
#  - lê os e-mails diretamente da greenlist
#  - aplica apenas blacklist sobre essa fila
#  - login → Consultar V2 → Serviço de TV
#  - consulta robusta do e-mail na aba Serviço de TV
#  - clica no cliente da grade → entra em "Editar"
#  - aba Contratos → se existir WATCH "Ativo": Desativar
#  - LOG CSV + resumo texto por execução
#  - remove da greenlist cada e-mail tratado com sucesso
#  - reabre "Serviço de TV" entre e-mails e em caso de retorno em branco

from datetime import datetime
import os
import sys

# === Config / arquivos / dados ===
from .config import (
    SERVICO_TV_REOPEN_MODE,
    SERVICO_TV_MAX_RETRY_ON_EMPTY,
    FULL_REOPEN_BETWEEN_EMAILS,
)
from .email_lists import load_blacklist, load_greenlist, remove_email_from_greenlist

# === Selenium (driver + navegação no SGP) ===
from .driver import build_driver
from .sgp_login import login
from .sgp_navigation import (
    ir_para_consultar_v2,
    abrir_servico_de_tv,
    reabrir_servico_de_tv,
)
from .sgp_servicotv import consultar_login_tv
from .sgp_resultados import (
    aguardar_resultado_busca_cliente,
    clicar_resultado_por_email,
    entrar_em_modo_edicao_no_cliente,
)
from .sgp_contratos import (
    abrir_aba_contratos,
    verificar_e_desativar_watch,
)

# === Logger CSV ===
from .log_utils import new_exec_id, append_log, summary_path

def run():
    """
    Orquestra o fluxo consolidado com diagnóstico detalhado e o novo caminho pós-consulta:
    clicar no cliente da grade → entrar em "Editar" → aba "Contratos" → desativar WATCH "Ativo".
    Usa a greenlist como fila de processamento.
    """
    # ---------------------------
    # 1) Montar lote a partir da greenlist
    # ---------------------------
    greenlist = load_greenlist()
    blacklist = set(load_blacklist())
    emails = [email for email in greenlist if email not in blacklist]
    emails_pulados_blacklist = [email for email in greenlist if email in blacklist]

    print(
        "🧹 Fila de processamento:"
        f" greenlist={len(greenlist)}"
        f" blacklist={len(blacklist)}"
        f" pulados_blacklist={len(emails_pulados_blacklist)}"
        f" finais={len(emails)}/{len(greenlist)}"
    )
    if emails_pulados_blacklist:
        for email_pulado in emails_pulados_blacklist:
            print(f"⏭️  Pulado por blacklist: {email_pulado}")
    if not emails:
        print("⚠️ Nenhum e-mail restou na greenlist após aplicar blacklist — encerrando.")
        return

    lote = list(emails)
    print(f"🧪 Rodando com {len(lote)} e-mails após filtros.")

    # ---------------------------
    # 2) Logger desta execução
    # ---------------------------
    exec_id = new_exec_id()
    print(f"🧾 exec_id: {exec_id}")
    resumo_path = summary_path(exec_id)

    # ---------------------------
    # 3) Selenium: login e navegação até Serviço de TV
    # ---------------------------
    driver = build_driver()
    try:
        login(driver)
        print("🔐 Login OK")

        ir_para_consultar_v2(driver)
        print("📂 Consultar V2 aberto")

        abrir_servico_de_tv(driver)
        print("📺 Serviço de TV aberto")

        # ---------------------------
        # 4) Loop principal
        # ---------------------------
        for idx, email in enumerate(lote, start=1):
            print(f"\n▶️  [{idx}/{len(lote)}] Email: {email}")
            email_finalizado = False
            try:
                # --- Retry quando resultado vier em branco ---
                attempt = 0
                sucesso = False
                while attempt <= SERVICO_TV_MAX_RETRY_ON_EMPTY:
                    attempt += 1

                    # 6.1) Dispara a consulta (com múltiplos fallbacks internos)
                    info = consultar_login_tv(driver, email, timeout_pos_click=10)
                    print(
                        f"   🚀 Disparo: modo={info['modo']} ok_clicked={info['ok_clicked']} "
                        f"| match_input={info['match']}"
                    )

                    # 6.2) Aguarda resultado na grade (links de cliente / e-mail no HTML)
                    ok_res = aguardar_resultado_busca_cliente(driver, email, timeout=10)
                    print(f"   🔎 Resultado (links cliente ou e-mail no HTML)? {ok_res}")

                    if not ok_res:
                        if attempt <= SERVICO_TV_MAX_RETRY_ON_EMPTY:
                            print("   🔁 Branco — reabrindo 'Serviço de TV' e tentando novamente...")
                            reabrir_servico_de_tv(driver, mode=SERVICO_TV_REOPEN_MODE)
                            continue
                        else:
                            print("   ❌ Sem resultado após retries.")
                            append_log(
                                exec_id,
                                email,
                                "FAIL_SEM_RESULTADO",
                                desativado_em="",
                                observacao="Sem links de cliente / e-mail no HTML após consulta",
                            )
                            email_finalizado = True
                            # Reabre para garantir estado limpo para o próximo e-mail
                            reabrir_servico_de_tv(driver, mode=SERVICO_TV_REOPEN_MODE)
                            break  # sai do while, segue para o próximo e-mail

                    # 6.3) Clica no cliente correspondente (prioriza linha com o e-mail)
                    clicar_resultado_por_email(driver, email)
                    print("   🧭 Entrou na página do cliente")

                    # 6.4) Entra em "Editar" na página do cliente
                    entrar_em_modo_edicao_no_cliente(driver)
                    print("   ✏️  Modo de edição do cliente aberto")

                    # 6.5) Aba Contratos → desativar WATCH "Ativo"
                    abrir_aba_contratos(driver)
                    print("   📑 Aba 'Contratos' aberta")

                    desativou = verificar_e_desativar_watch(driver)
                    if desativou:
                        dt_desativ = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"   SUCCESS: WATCH desativado em {dt_desativ}")
                        append_log(exec_id, email, "SUCCESS_OK_DESATIVADO", desativado_em=dt_desativ, observacao=driver.current_url)
                    else:
                        print("   INFO: sem contrato WATCH ativo")
                        append_log(exec_id, email, "INFO_SEM_WATCH_ATIVO", desativado_em="", observacao=driver.current_url)

                    email_finalizado = True
                    sucesso = True
                    break  # sucesso na tentativa atual — sai do while

                if not sucesso:
                    # já registramos o motivo acima; segue para o próximo e-mail
                    pass

            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                print(f"   FAIL: {msg}")
                append_log(exec_id, email, "FAIL_ERRO", desativado_em="", observacao=msg)
                email_finalizado = True

            if email_finalizado and remove_email_from_greenlist(email):
                print(f"   🗑️  Removido da greenlist: {email}")

            # --- Reabrir do zero entre e-mails (evita estado quebrado) ---
            if FULL_REOPEN_BETWEEN_EMAILS:
                reabrir_servico_de_tv(driver, mode=SERVICO_TV_REOPEN_MODE)

        print("\n✅ Lote concluído.")
        print(f"📝 Resumo salvo em: {resumo_path}")
        try:
            with open(resumo_path, "r", encoding="utf-8") as f:
                resumo = f.read().strip()
            print("\n===== LOG FINAL =====")
            print(resumo or "(sem linhas no resumo)")
            print("=====================")
        except Exception as e:
            print(f"⚠️ Não foi possível abrir o resumo final: {type(e).__name__}: {e}")
        pause_disabled = os.getenv("DESATIVA_WATCH_NO_PAUSE", "").strip().lower() in {"1", "true", "yes", "on"}
        if not pause_disabled and sys.stdin.isatty():
            input("Pressione ENTER para finalizar...")

    finally:
        driver.quit()


if __name__ == "__main__":
    run()
