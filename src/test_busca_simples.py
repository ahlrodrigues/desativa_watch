# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/test_busca_simples.py
# Comentário: teste mínimo V2 com diagnósticos detalhados e tratamento de 'stale element'.
# Uso:
#   python -m src.test_busca_simples <email> [modo]
# modos:
#   click (padrão) | enter | form_submit
#
# O que este teste faz:
#  1) Login → Consultar V2 → Serviço de TV
#  2) Preenche #id_login_tv com o e-mail (sem sanitização extra)
#  3) Dispara a consulta pelo modo escolhido com re-localização em caso de 'stale'
#  4) Coleta fingerprints ANTES/DEPOIS + diagnósticos:
#      - ocorrências do e-mail no HTML
#      - qtd. de links /admin/cliente/… e /edit/
#      - amostra de até 5 hrefs relevantes
#      - qtd. total de linhas <tr> em tabelas (exclui <thead>)
#      - presença de mensagens de "nenhum resultado"
#  5) Polling até 10s; salva artefatos (HTML/PNG) antes e depois

import sys
import time
import re
import hashlib
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    StaleElementReferenceException,
    InvalidSessionIdException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .driver import build_driver
from .sgp_login import login
from .sgp_navigation import ir_para_consultar_v2, abrir_servico_de_tv
from .debug_utils import dump_page_artifacts
from .sgp_resultados import localizar_contexto_resultado

# Seletores essenciais
SEL_INPUT = (By.CSS_SELECTOR, "#id_login_tv")
SEL_BTN   = (By.CSS_SELECTOR, "#botao_consulta")

# Heurísticas para achar "Editar"
EDIT_CANDIDATES = [
    (By.CSS_SELECTOR, "a.edit"),
    (By.CSS_SELECTOR, 'a[href*="/edit"]'),
    (By.XPATH, '//a[@title="Editar" or contains(@aria-label,"Editar")]'),
    (By.XPATH, '//*[self::button or self::a][@title="Editar" or contains(@class,"edit") or contains(@aria-label,"Editar")]'),
    (By.XPATH, '//i[contains(@class,"fa-pencil") or contains(@class,"glyphicon-pencil")]/ancestor::a[1]'),
    (By.XPATH, '//img[contains(translate(@alt,"EDITAR","editar"),"editar")]/ancestor::a[1]'),
]

# Mensagens típicas de "nenhum resultado"
NO_RESULT_PATTERNS = [
    "Nenhum registro encontrado",
    "Nenhum resultado encontrado",
    "Não há registros",
    "Sem resultados",
]

def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8", "ignore")).hexdigest()

def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")

def _normalize_email(e: str) -> str:
    return (e or "").strip().lower()

def _safe_find(driver, by, sel, visible_only=False):
    try:
        els = driver.find_elements(by, sel)
        if visible_only:
            els = [e for e in els if e.is_displayed()]
        return els
    except Exception:
        return []

def _reacquire(driver, locator, timeout=20):
    by, sel = locator
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def _click_stable(driver, locator, retries=3):
    last_exc = None
    for _ in range(retries):
        try:
            el = _reacquire(driver, locator, timeout=20)
            el.click()
            return True
        except StaleElementReferenceException as e:
            last_exc = e
            time.sleep(0.2)
            continue
        except WebDriverException as e:
            last_exc = e
            # tenta via JS como fallback
            try:
                el = _reacquire(driver, locator, timeout=20)
                driver.execute_script("arguments[0].click();", el)
                return True
            except Exception as e2:
                last_exc = e2
                time.sleep(0.2)
                continue
    if last_exc:
        raise last_exc
    return False

def _fingerprint(driver):
    """Coleta impressão básica; não explode se a sessão cair."""
    try:
        url = driver.current_url
        src = driver.page_source or ""
    except InvalidSessionIdException:
        return {"url": "<invalid-session>", "len": 0, "md5": "", "has_edit": False}
    src_len = len(src)
    src_md5 = _md5(src[:2_000_000])
    has_edit = False
    for by, sel in EDIT_CANDIDATES:
        try:
            if driver.find_elements(by, sel):
                has_edit = True
                break
        except Exception:
            pass
    return {"url": url, "len": src_len, "md5": src_md5, "has_edit": has_edit, "src": src}


def _fingerprint_any_context(driver, email_norm: str):
    try:
        best = localizar_contexto_resultado(driver, email_norm, max_depth=4)
    except Exception:
        best = {"path": [], "none_msg": False}
    fp = _fingerprint(driver)
    fp["frame_path"] = best.get("path", [])
    fp["none_msg"] = best.get("none_msg", False)
    return fp

def _print_fp(tag, fp):
    print(f"[{_now()}] {tag} URL={fp['url']} | len={fp['len']} | md5={fp['md5']} | has_edit={fp['has_edit']}")

def _diagnosticos_resultado(driver, email_norm: str, src: str | None = None):
    """Extrai diagnósticos úteis do HTML atual."""
    try:
        if src is None:
            src = driver.page_source or ""
    except InvalidSessionIdException:
        src = ""
    src_low = src.lower()

    # 1) ocorrências do e-mail no HTML
    email_count = src_low.count(email_norm)

    # 2) links de cliente e edit
    anchors_cliente = _safe_find(driver, By.XPATH, "//a[contains(@href,'/admin/cliente/')]")
    anchors_edit = [a for a in anchors_cliente if "/edit" in (a.get_attribute("href") or "")]
    sample_hrefs = []
    for a in anchors_cliente[:5]:
        try:
            sample_hrefs.append(a.get_attribute("href"))
        except Exception:
            pass

    # 3) linhas em tabelas (exclui thead)
    try:
        rows_total = len(_safe_find(driver, By.XPATH, "//table//tbody//tr"))
    except Exception:
        rows_total = 0

    # 4) mensagens de "nenhum resultado"
    msg_none = any(pat.lower() in src_low for pat in NO_RESULT_PATTERNS)

    return {
        "email_count": email_count,
        "anchors_cliente": len(anchors_cliente),
        "anchors_edit": len(anchors_edit),
        "rows_total": rows_total,
        "none_msg": msg_none,
        "sample_hrefs": sample_hrefs,
    }

def run():
    # ------------ CLI ------------
    if len(sys.argv) < 2:
        print("Uso: python -m src.test_busca_simples <email> [modo]")
        print("  modos: click (padrão) | enter | form_submit")
        return
    email = sys.argv[1]
    modo = (sys.argv[2] if len(sys.argv) > 2 else "click").strip().lower()
    if modo not in ("click", "enter", "form_submit"):
        modo = "click"
    email_norm = _normalize_email(email)
    print(f"[{_now()}] ▶️  Teste simples V2 — email='{email}', modo='{modo}'")

    driver = build_driver()
    try:
        # ------------ Login + Navegação ------------
        login(driver)
        ir_para_consultar_v2(driver)
        abrir_servico_de_tv(driver)

        # ------------ Localiza elementos (sempre re-adquire) ------------
        input_el = _reacquire(driver, SEL_INPUT, timeout=20)
        try:
            input_el.clear()
        except WebDriverException:
            pass
        input_el.send_keys(email)

        # ------------ Fingerprint antes + artefatos ------------
        fp_before = _fingerprint(driver)
        _print_fp("ANTES", fp_before)
        dump_page_artifacts(driver, prefix="busca_simples_pre")

        # ------------ Dispara a busca (com proteção a stale) ------------
        before_handles = list(driver.window_handles)
        if modo == "click":
            _click_stable(driver, SEL_BTN, retries=3)
        elif modo == "enter":
            try:
                input_el = _reacquire(driver, SEL_INPUT, timeout=10)
                input_el.send_keys(Keys.ENTER)
            except StaleElementReferenceException:
                # re-localiza e tenta de novo
                input_el = _reacquire(driver, SEL_INPUT, timeout=10)
                input_el.send_keys(Keys.ENTER)
        else:  # form_submit
            try:
                btn_el = _reacquire(driver, SEL_BTN, timeout=10)
                form = driver.execute_script("""
                    let n = arguments[0];
                    while (n && n.tagName !== 'FORM') n = n.parentElement;
                    return n;
                """, btn_el)
                if form:
                    driver.execute_script("arguments[0].submit();", form)
                else:
                    _click_stable(driver, SEL_BTN, retries=3)
            except Exception:
                _click_stable(driver, SEL_BTN, retries=3)

        # Se abriu nova aba, alterna (curto)
        end = time.time() + 2.0
        while time.time() < end:
            try:
                handles = driver.window_handles
            except InvalidSessionIdException:
                break
            if len(handles) > len(before_handles):
                new_handle = [h for h in handles if h not in before_handles][-1]
                driver.switch_to.window(new_handle)
                print(f"[{_now()}] 🪟 Nova janela/aba detectada. Alternando…")
                break
            time.sleep(0.2)

        # ------------ Polling 10s com prints por ~2s (para reduzir ruído) ------------
        t0 = time.time()
        appeared = False
        while (time.time() - t0) < 10:
            fp_now = _fingerprint(driver)
            _print_fp("CHECK", fp_now)
            di = _diagnosticos_resultado(driver, email_norm, src=fp_now.get("src", ""))
            print(f"   ↳ diag: email_count={di['email_count']} anchors_cliente={di['anchors_cliente']} anchors_edit={di['anchors_edit']} rows_total={di['rows_total']} none_msg={di['none_msg']}")
            if fp_now["has_edit"] or di["anchors_cliente"] > 0 or di["email_count"] > 0 or di["rows_total"] > 0:
                appeared = True
                break
            time.sleep(1.0)

        # ------------ Fingerprint depois + artefatos ------------
        fp_after = _fingerprint_any_context(driver, email_norm)
        _print_fp("DEPOIS", fp_after)
        di_after = _diagnosticos_resultado(driver, email_norm, src=fp_after.get("src", ""))
        print(f"   ↳ diag_final: email_count={di_after['email_count']} anchors_cliente={di_after['anchors_cliente']} anchors_edit={di_after['anchors_edit']} rows_total={di_after['rows_total']} none_msg={di_after['none_msg']} frame_path={fp_after.get('frame_path')}")
        if di_after["sample_hrefs"]:
            print("   ↳ sample_hrefs:")
            for h in di_after["sample_hrefs"]:
                print(f"      - {h}")
        dump_page_artifacts(driver, prefix="busca_simples_post")

        # ------------ Resultado do teste ------------
        changed = (fp_after["md5"] != fp_before["md5"]) or (fp_after["url"] != fp_before["url"]) or (fp_after["len"] != fp_before["len"])
        print(f"[{_now()}] Δ Mudou URL/HTML? {changed} (url_changed={fp_after['url'] != fp_before['url']}, md5_changed={fp_after['md5'] != fp_before['md5']}, len_changed={fp_after['len'] != fp_before['len']})")

        if appeared:
            print(f"[{_now()}] ✅ Vimos indícios de retorno (editar/links/linhas ou e-mail no HTML).")
        elif fp_after.get("none_msg"):
            print(f"[{_now()}] ⚠️ Encontramos o contexto do resultado, mas a tela indica 'sem resultados'.")
        else:
            print(f"[{_now()}] ❌ Nada visível de retorno (sem editar/links/linhas/e-mail no HTML). Confira os artefatos e os diagnósticos.")

        input("Pressione ENTER para fechar o navegador...")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    run()
