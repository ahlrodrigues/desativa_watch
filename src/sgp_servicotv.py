# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/sgp_servicotv.py
# Comentário: Ações da aba "Serviço de TV" com suporte à overlay de pré-busca.
# Mudanças principais:
#   - Antes: disparava a consulta e já validava retorno.
#   - Agora: após o disparo, chamamos ensure_overlay_after_submit(...) para
#            aguardar/forçar a remoção de .pre-search.
#
# (restante do cabeçalho e imports originais mantidos)

from __future__ import annotations

from time import sleep, time as now
from typing import Dict, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
)

from .config import SERVICO_TV_WAIT_SECONDS, STRICT_INPUT_ASSIGNMENT
from .debug_utils import dump_page_artifacts
from .text_sanitizer import sanitize_email_for_input, codepoints
from .sgp_filters import ensure_filtros_visiveis
from .overlay_patch import ensure_overlay_after_submit   # ⬅️ NOVO

# =========================
# Seletores principais
# =========================
SEL_INPUT_LOGIN_TV: Tuple[str, str] = (By.CSS_SELECTOR, "#id_login_tv")
SEL_BTN_CONSULTAR: Tuple[str, str]  = (By.CSS_SELECTOR, "#botao_consulta")

CANDIDATES_EDIT = [
    (By.CSS_SELECTOR, "a.edit"),
    (By.CSS_SELECTOR, 'a[href*="/edit"]'),
    (By.XPATH, '//a[@title="Editar" or contains(@aria-label,"Editar")]'),
    (By.XPATH, '//*[self::button or self::a][@title="Editar" or contains(@class,"edit") or contains(@aria-label,"Editar")]'),
    (By.XPATH, '//i[contains(@class,"fa-pencil") or contains(@class,"glyphicon-pencil")]/ancestor::a[1]'),
    (By.XPATH, '//img[contains(translate(@alt,"EDITAR","editar"),"editar")]/ancestor::a[1]'),
]

# =========================
# Helpers (inalterados ou com comentários extras)
# =========================
def _esperar_clickable(driver, locator, timeout: int = 20):
    el = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))

def _limpar_input(driver, el_input) -> None:
    try:
        el_input.clear()
    except WebDriverException:
        pass
    try:
        el_input.send_keys(Keys.CONTROL, "a"); el_input.send_keys(Keys.DELETE)
    except WebDriverException:
        pass
    try:
        driver.execute_script("arguments[0].value='';", el_input)
    except WebDriverException:
        pass

def _disparar_eventos(driver, el_input, blur: bool = True) -> None:
    try:
        driver.execute_script(
            "const el=arguments[0]; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));",
            el_input,
        )
    except WebDriverException:
        pass
    if blur:
        try:
            driver.execute_script("arguments[0].blur();", el_input)
        except WebDriverException:
            pass

def _btn_debug(driver, btn) -> Dict:
    try:
        outer = driver.execute_script("return arguments[0].outerHTML;", btn)
    except Exception:
        outer = "<outerHTML indisponível>"
    try:
        rect = driver.execute_script("const r=arguments[0].getBoundingClientRect();return {{x:r.x,y:r.y,w:r.width,h:r.height}};", btn)
    except Exception:
        rect = {}
    return {
        "displayed": getattr(btn, "is_displayed", lambda: None)(),
        "enabled": getattr(btn, "is_enabled", lambda: None)(),
        "disabled_attr": btn.get_attribute("disabled"),
        "outerHTML": outer,
        "rect": rect,
    }

def _try_click_methods(driver, el_input, btn) -> Tuple[str, bool]:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    except WebDriverException:
        pass
    methods = [
        ("click", lambda: btn.click()),
        ("actions_click", lambda: ActionChains(driver).move_to_element(btn).pause(0.05).click(btn).perform()),
        ("js_mouse_event", lambda: driver.execute_script(
            "arguments[0].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));", btn)),
        ("form_requestSubmit", lambda: driver.execute_script(
            "let n=arguments[0];while(n&&n.tagName!=='FORM')n=n.parentElement; if(n){n.requestSubmit?n.requestSubmit(arguments[0]):n.submit();}else{throw new Error('form not found');}",
            btn)),
        ("enter_on_input", lambda: el_input.send_keys(Keys.ENTER)),
    ]
    for name, fn in methods:
        try:
            fn(); return name, True
        except WebDriverException:
            continue
    return "none", False

def _switch_to_new_window_if_opened(driver, before_handles, timeout: float = 2.0) -> bool:
    end = now() + timeout
    while now() < end:
        handles = driver.window_handles
        if len(handles) > len(before_handles):
            new_handle = [h for h in handles if h not in before_handles][-1]
            driver.switch_to.window(new_handle)
            return True
        sleep(0.15)
    return False

def _find_edit_anywhere_top(driver):
    for by, sel in CANDIDATES_EDIT:
        try:
            els = driver.find_elements(by, sel)
            if els:
                return els[0]
        except Exception:
            pass
    return None

# =========================
# API principal (alterada: overlay após submit)
# =========================
def consultar_login_tv(driver, email: str, timeout_pos_click: int = 10) -> Dict:
    """
    Fluxo de consulta na aba 'Serviço de TV':
      1) Garante filtros visíveis (#id_login_tv).
      2) Preenche e dispara a busca por múltiplos métodos.
      3) **NOVO**: aguarda/força a remoção da overlay de pré-busca (.pre-search).
      4) Alterna para nova aba se aberta.
    Retorna dicionário de diagnóstico do disparo.
    """
    # 1) Filtros visíveis
    if not ensure_filtros_visiveis(driver, timeout=10):
        print("   ⚠️ Filtros não ficaram visíveis — tentando mesmo assim…")

    # 2) Elementos essenciais
    el_input = _esperar_clickable(driver, SEL_INPUT_LOGIN_TV, timeout=20)
    btn = _esperar_clickable(driver, SEL_BTN_CONSULTAR,  timeout=20)

    # Preenchimento
    email_san = sanitize_email_for_input(email)
    _limpar_input(driver, el_input)
    if STRICT_INPUT_ASSIGNMENT:
        driver.execute_script("arguments[0].value = arguments[1];", el_input, email_san)
        try: el_input.send_keys(Keys.END)
        except WebDriverException: pass
    else:
        el_input.send_keys(email_san)
    _disparar_eventos(driver, el_input, blur=True)

    val = driver.execute_script("return arguments[0].value;", el_input) or ""
    same = (val == email_san)
    if not same:
        print(f"   🧪 DEBUG input ≠ sanitizado | sanitizado: {email_san} [{codepoints(email_san)}] | lido: {val} [{codepoints(val)}]")

    # 2.b) Disparo dos métodos de submit
    btn_info = _btn_debug(driver, btn)
    print(f"   🔍 Botão 'Consultar' — displayed={btn_info['displayed']} enabled={btn_info['enabled']} disabled_attr={btn_info['disabled_attr']}")

    before = list(driver.window_handles)
    modo, ok_clicked = _try_click_methods(driver, el_input, btn)

    # 3) **NOVO**: tratar overlay de pré-busca
    ensure_overlay_after_submit(driver, timeout=timeout_pos_click)

    # 4) Alterna para nova aba se houver
    switched = _switch_to_new_window_if_opened(driver, before_handles=before, timeout=2.0)

    return {
        "modo": modo,
        "ok_clicked": ok_clicked,
        "match": same,
        "valor_lido": val,
        "btn_info": btn_info,
        "switched_window": switched,
    }

def aguardar_resultado_consulta(driver, max_wait: float | None = None) -> bool:
    """
    Mantido por compatibilidade: espera algum 'Editar' aparecer.
    (Para grid de clientes sem 'Editar', use sgp_resultados.*)
    """
    if max_wait is None:
        max_wait = max(3.0, SERVICO_TV_WAIT_SECONDS * 2.0)
    end = now() + max_wait
    while now() < end:
        try:
            if _find_edit_anywhere_top(driver):
                return True
        except Exception:
            pass
        sleep(0.35)
    dump_page_artifacts(driver, prefix="servico_tv_sem_resultado")
    return False
