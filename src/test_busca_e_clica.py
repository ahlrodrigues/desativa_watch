# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/test_busca_e_clica.py
# Comentário: Teste E2E (1 e-mail) agora aguardando a overlay sumir após a consulta.
# - Injeta/espera a overlay ir embora antes de diagnosticar a grade e clicar no cliente.

from __future__ import annotations
import sys
from datetime import datetime

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from .driver import build_driver
from .sgp_login import login
from .sgp_navigation import ir_para_consultar_v2, abrir_servico_de_tv
from .sgp_servicotv import consultar_login_tv
from .sgp_resultados import (
    aguardar_resultado_busca_cliente,
    clicar_resultado_por_email,
    entrar_em_modo_edicao_no_cliente,
)
from .overlay_patch import wait_overlay_gone   # ⬅️ NOVO
from .debug_utils import dump_page_artifacts

def _now():
    return datetime.now().strftime("%H:%M:%S")

def _normalize_diag(diag, driver, email: str):
    if isinstance(diag, dict):
        for k in ("found", "anchors_cliente", "rows_total", "email_present", "sample_hrefs"):
            diag.setdefault(k, False if k in ("found", "email_present") else 0 if k in ("anchors_cliente", "rows_total") else [])
        return diag
    try:
        src = (driver.page_source or "").lower()
    except Exception:
        src = ""
    email_present = (email or "").lower() in src
    return {"found": bool(diag), "anchors_cliente": 0, "rows_total": 0, "email_present": email_present, "sample_hrefs": []}

def run():
    if len(sys.argv) < 2:
        print("Uso: python -m src.test_busca_e_clica <email>")
        return

    email = sys.argv[1].strip()
    print(f"[{_now()}] ▶️  Teste busca+clique — email='{email}'")

    d = build_driver()
    try:
        login(d)
        ir_para_consultar_v2(d)
        abrir_servico_de_tv(d)

        dump_page_artifacts(d, prefix="e2e_pre_consulta")
        info = consultar_login_tv(d, email, timeout_pos_click=8)
        print(f"[{_now()}] 🚀 Disparo: modo={info['modo']} ok_clicked={info['ok_clicked']} match_input={info['match']}")

        # ⬇️ Aguarda overlay sumir antes de diagnosticar a página
        wait_overlay_gone(d, timeout=12)

        raw = aguardar_resultado_busca_cliente(d, email, timeout=10)
        diag = _normalize_diag(raw, d, email)
        print(f"[{_now()}] 🔎 diag: found={diag['found']} anchors_cliente={diag['anchors_cliente']} rows_total={diag['rows_total']} email_present={diag['email_present']}")
        if diag["sample_hrefs"]:
            print("   ↳ sample_hrefs:")
            for h in diag["sample_hrefs"]:
                print(f"      - {h}")

        dump_page_artifacts(d, prefix="e2e_pos_consulta")

        if not diag["found"]:
            print(f"[{_now()}] ❌ Sem resultados visíveis/diagnosticáveis. Confira os artefatos em data/output/.")
            input("Pressione ENTER para fechar...")
            return

        clicar_resultado_por_email(d, email, retries=4)
        WebDriverWait(d, 10).until(EC.url_contains("/admin/cliente/"))
        print(f"[{_now()}] 🧭 Entrou na página do cliente (URL: {d.current_url})")
        dump_page_artifacts(d, prefix="e2e_pos_click_result")

        try:
            entrar_em_modo_edicao_no_cliente(d, timeout=10)
            print(f"[{_now()}] ✏️  Abriu 'Editar' do cliente (URL: {d.current_url})")
            dump_page_artifacts(d, prefix="e2e_pos_editar")
        except Exception as e:
            print(f"[{_now()}] ⚠️ Não achei 'Editar': {type(e).__name__}: {e}")

        input("Pressione ENTER para fechar...")
    finally:
        try: d.quit()
        except Exception: pass

if __name__ == "__main__":
    run()
