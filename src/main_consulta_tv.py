# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/main_consulta_tv.py
# Comentário: Fluxo end-to-end consolidado (teste com 2 e-mails) com:
#  - abertura e ordenação da planilha (ordenação por INTEGRACAO como datetime aplicada ao DF inteiro)
#  - recorte TOP 50 e extração de e-mails únicos
#  - login → Consultar V2 → Serviço de TV
#  - consulta robusta do e-mail na aba Serviço de TV
#  - NOVO: aguarda links de cliente na grade, clica a linha correspondente ao e-mail, entra em "Editar"
#  - aba Contratos → se existir WATCH "Ativo": Desativar
#  - LOG CSV com timestamp da desativação
#  - reabrir "Serviço de TV" entre e-mails e em caso de retorno em branco (sem resultados)
#
# Variáveis relevantes no .env:
#   SERVICO_TV_REOPEN_MODE=click_path|reload|new_tab
#   SERVICO_TV_MAX_RETRY_ON_EMPTY=1
#   FULL_REOPEN_BETWEEN_EMAILS=true
#   SERVICO_TV_WAIT_SECONDS=3.0
#   STRICT_INPUT_ASSIGNMENT=true|false
#
# Observação: este script mantém o lote limitado a 2 e-mails para teste controlado.

import sys
import time
from datetime import datetime

# === Config / arquivos / dados ===
from .config import (
    TARGET_DATE_YYYYMMDD,
    SERVICO_TV_REOPEN_MODE,
    SERVICO_TV_MAX_RETRY_ON_EMPTY,
    FULL_REOPEN_BETWEEN_EMAILS,
)
from .files import (
    resolve_data_para_busca,
    localizar_arquivo_export_never,
    abrir_planilha_export_never,
)
from .data_ops import sort_df_by_integracao_datetime, top_n_rows
from .email_utils import extrair_emails

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
from .log_utils import new_exec_id, append_log

# Pequena pausa entre consultas para não sobrecarregar o SGP
PAUSA_ENTRE_CONSULTAS = 0.4  # segundos


def run():
    """
    Orquestra o fluxo consolidado com diagnóstico detalhado e o novo caminho pós-consulta:
    clicar no cliente da grade → entrar em "Editar" → aba "Contratos" → desativar WATCH "Ativo".
    Mantém o lote de teste limitado a 2 e-mails.
    """
    # ---------------------------
    # 1) Planilha: resolver data, localizar e abrir
    # ---------------------------
    data_cli = sys.argv[1] if len(sys.argv) > 1 else None
    date_str = resolve_data_para_busca(TARGET_DATE_YYYYMMDD or data_cli)
    print(f"🗓️  Data de busca: {date_str}")

    caminho, _ = localizar_arquivo_export_never(date_str)
    print(f"📄 Planilha: {caminho}")

    df = abrir_planilha_export_never(caminho)
    print(f"ℹ️  Linhas totais: {len(df)} | Colunas: {list(df.columns)}")

    # ---------------------------
    # 2) Ordenar por INTEGRACAO (datetime) e pegar TOP 50
    # ---------------------------
    df_sorted, metodo, col_real = sort_df_by_integracao_datetime(
        df, candidates=("INTEGRACAO", "INTEGRAÇÃO"), ascending=True
    )
    print(f"✅ Ordenado por '{col_real}' como datetime (método: {metodo})")

    df_top50 = top_n_rows(df_sorted, n=50)
    print(f"🔸 Recorte TOP 50 pronto (linhas: {len(df_top50)})")

    # ---------------------------
    # 3) Extrair e-mails do TOP 50
    # ---------------------------
    emails = extrair_emails(df_top50, coluna_preferida="EMAIL")
    print(f"📧 E-mails únicos no TOP 50: {len(emails)}")
    if not emails:
        print("⚠️ Nenhum e-mail encontrado — encerrando.")
        return

    # Limita o lote a 2 e-mails para o teste
    lote = emails[:2]
    print(f"🧪 Rodando teste com {len(lote)} e-mails.")

    # ---------------------------
    # 4) Logger desta execução
    # ---------------------------
    exec_id = new_exec_id()
    print(f"🧾 exec_id: {exec_id}")

    # ---------------------------
    # 5) Selenium: login e navegação até Serviço de TV
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
        # 6) Loop principal (2 e-mails)
        # ---------------------------
        for idx, email in enumerate(lote, start=1):
            print(f"\n▶️  [{idx}/{len(lote)}] Email: {email}")
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
                                "SEM_RESULTADO",
                                desativado_em="",
                                observacao="Sem links de cliente / e-mail no HTML após consulta",
                            )
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
                        print(f"   ✅ WATCH 'Ativo' DESATIVADO em {dt_desativ}")
                        append_log(exec_id, email, "OK_DESATIVADO", desativado_em=dt_desativ, observacao="")
                    else:
                        print("   ➖ Sem contrato WATCH 'Ativo'")
                        append_log(exec_id, email, "SEM_WATCH_ATIVO", desativado_em="", observacao="")

                    sucesso = True
                    break  # sucesso na tentativa atual — sai do while

                if not sucesso:
                    # já registramos o motivo acima; segue para o próximo e-mail
                    pass

            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                print(f"   ⚠️ ERRO: {msg}")
                append_log(exec_id, email, "ERRO", desativado_em="", observacao=msg)

            # --- Reabrir do zero entre e-mails (evita estado quebrado) ---
            if FULL_REOPEN_BETWEEN_EMAILS:
                reabrir_servico_de_tv(driver, mode=SERVICO_TV_REOPEN_MODE)

            time.sleep(PAUSA_ENTRE_CONSULTAS)

        print("\n✅ Lote concluído. Veja o CSV em data/output/ (prefixo: desativa_watch_log_...).")
        input("Pressione ENTER para finalizar...")

    finally:
        driver.quit()


if __name__ == "__main__":
    run()
