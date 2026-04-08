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
from .debug_utils import dump_page_artifacts, dump_json_artifact
from .text_sanitizer import sanitize_email_for_input, codepoints
from .sgp_filters import ensure_filtros_visiveis
from .overlay_patch import ensure_overlay_after_submit   # ⬅️ NOVO

# =========================
# Seletores principais
# =========================
SEL_INPUT_LOGIN_TV: Tuple[str, str] = (By.CSS_SELECTOR, "#id_login_tv")
SEL_BTN_CONSULTAR: Tuple[str, str]  = (By.CSS_SELECTOR, "#botao_consulta")
SEL_TAB_SERVICO_TV: Tuple[str, str] = (By.CSS_SELECTOR, 'a[href="#fields_search_tv"], #ui-id-4')
SEL_PANEL_SERVICO_TV: Tuple[str, str] = (By.CSS_SELECTOR, "#fields_search_tv")

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


def _preencher_login_tv(driver, el_input, email_san: str) -> Tuple[str, str]:
    """
    Preenche o login colando o valor de uma vez e dispara os eventos esperados da tela.
    Retorna (modo_usado, valor_lido).
    """
    strategies = [
        ("send_keys_full", lambda: (_limpar_input(driver, el_input), el_input.send_keys(email_san), True)[-1]),
    ]

    if STRICT_INPUT_ASSIGNMENT:
        strategies.append((
            "js_assign",
            lambda: (
                driver.execute_script("arguments[0].value = arguments[1];", el_input, email_san),
                True,
            )[-1]
        ))

    last_val = ""
    for mode, fn in strategies:
        try:
            fn()
            _disparar_eventos(driver, el_input, blur=False)
            try:
                el_input.send_keys(Keys.TAB)
            except WebDriverException:
                _disparar_eventos(driver, el_input, blur=True)
            last_val = driver.execute_script("return arguments[0].value;", el_input) or ""
            if last_val == email_san:
                return mode, last_val
        except WebDriverException:
            try:
                last_val = driver.execute_script("return arguments[0].value;", el_input) or ""
            except WebDriverException:
                last_val = ""
            continue

    return "fallback", last_val

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
        "form_id": driver.execute_script("return arguments[0].form ? arguments[0].form.id || '' : '';", btn) if btn else "",
        "outerHTML": outer,
        "rect": rect,
    }

def _submit_form_servico_tv(driver) -> None:
    """
    Submete explicitamente o form de busca, sem depender do botão visual estar bem ancorado no DOM.
    """
    driver.execute_script(
        """
        const form = document.querySelector('#form');
        if (!form) throw new Error('form #form not found');

        let submitter = form.querySelector('input[type="submit"][name="botao_consulta"], button[type="submit"][name="botao_consulta"]');
        let temp = null;
        if (!submitter) {
          temp = document.createElement('input');
          temp.type = 'submit';
          temp.name = 'botao_consulta';
          temp.value = 'Consultar';
          temp.style.display = 'none';
          form.appendChild(temp);
          submitter = temp;
        }

        if (form.requestSubmit) {
          form.requestSubmit(submitter);
        } else {
          submitter.click();
        }
        """
    )


def _snapshot_submit_state(driver) -> Dict:
    try:
        return driver.execute_script(
            """
            const form = document.querySelector('#form');
            const activeTab = document.querySelector('#tabs .ui-tabs-nav li.ui-tabs-active a');
            const formData = [];
            if (form) {
              for (const el of Array.from(form.elements)) {
                if (!el.name || el.disabled) continue;
                const type = (el.type || '').toLowerCase();
                if ((type === 'checkbox' || type === 'radio') && !el.checked) continue;
                if (el.tagName === 'SELECT' && el.multiple) {
                  const selected = Array.from(el.selectedOptions).map(o => o.value);
                  if (selected.length) formData.push({name: el.name, value: selected});
                  continue;
                }
                formData.push({name: el.name, value: el.value});
              }
            }
            return {
              current_url: window.location.href,
              form_action: form ? form.getAttribute('action') || '' : '',
              form_method: form ? (form.getAttribute('method') || form.method || '') : '',
              active_tab_href: activeTab ? activeTab.getAttribute('href') || '' : '',
              active_tab_text: activeTab ? (activeTab.textContent || '').trim() : '',
              form_data: formData,
            };
            """
        ) or {}
    except Exception as e:
        return {"snapshot_error": f"{type(e).__name__}: {e}"}

def _try_click_methods(driver, el_input, btn) -> Tuple[str, bool]:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    except WebDriverException:
        pass
    methods = [
        ("form_requestSubmit_explicit", lambda: _submit_form_servico_tv(driver)),
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
    try:
        WebDriverWait(driver, timeout).until(lambda d: len(d.window_handles) > len(before_handles))
        handles = driver.window_handles
        new_handle = [h for h in handles if h not in before_handles][-1]
        driver.switch_to.window(new_handle)
        return True
    except Exception:
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


def _aba_servico_tv_ativa(driver) -> bool:
    try:
        return bool(driver.execute_script(
            """
            const panel = document.querySelector('#fields_search_tv');
            const tab = document.querySelector('a[href="#fields_search_tv"], #ui-id-4');
            if (!panel || !tab) return false;
            const li = tab.closest('li');
            const panelVisible = panel.getAttribute('aria-hidden') === 'false' || panel.style.display !== 'none';
            const tabActive = !!(li && (li.classList.contains('ui-tabs-active') || li.getAttribute('aria-selected') === 'true'));
            return panelVisible && tabActive;
            """
        ))
    except Exception:
        return False


def _forcar_aba_servico_tv(driver) -> bool:
    """
    Garante que a aba 'Serviço de TV' fique ativa mesmo após o submit.
    """
    try:
        ok = driver.execute_script(
            """
            const tab = document.querySelector('a[href="#fields_search_tv"], #ui-id-4');
            const panel = document.querySelector('#fields_search_tv');
            const tabs = document.querySelector('#tabs');
            if (!tab || !panel) return false;

            try {
              if (window.jQuery && jQuery.fn && jQuery.fn.tabs && tabs) {
                const $tabs = jQuery(tabs);
                const idx = jQuery(tab).closest('li').index();
                if (idx >= 0) {
                  try { $tabs.tabs('option', 'active', idx); } catch (e) {}
                }
              }
            } catch (e) {}

            const li = tab.closest('li');
            document.querySelectorAll('#tabs .ui-tabs-nav li').forEach((node) => {
              node.classList.remove('ui-tabs-active', 'ui-state-active');
              node.setAttribute('aria-selected', 'false');
              node.setAttribute('tabindex', '-1');
            });
            document.querySelectorAll('#tabs .ui-tabs-panel').forEach((node) => {
              node.setAttribute('aria-hidden', 'true');
              node.style.display = 'none';
            });

            if (li) {
              li.classList.add('ui-tabs-active', 'ui-state-active');
              li.setAttribute('aria-selected', 'true');
              li.setAttribute('tabindex', '0');
            }
            panel.setAttribute('aria-hidden', 'false');
            panel.style.display = 'block';

            try { tab.click(); } catch (e) {}
            try {
              tab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            } catch (e) {}
            return true;
            """
        )
        return bool(ok)
    except Exception:
        return False


def _garantir_aba_servico_tv(driver, timeout: int = 10) -> bool:
    try:
        WebDriverWait(driver, timeout).until(lambda d: _aba_servico_tv_ativa(d) or _forcar_aba_servico_tv(d))
    except Exception:
        pass
    return _aba_servico_tv_ativa(driver)

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
    _garantir_aba_servico_tv(driver, timeout=5)

    # 2) Elementos essenciais
    el_input = _esperar_clickable(driver, SEL_INPUT_LOGIN_TV, timeout=20)
    btn = _esperar_clickable(driver, SEL_BTN_CONSULTAR,  timeout=20)

    # Preenchimento
    email_san = sanitize_email_for_input(email)
    fill_mode, val = _preencher_login_tv(driver, el_input, email_san)

    same = (val == email_san)
    if not same:
        print(f"   🧪 DEBUG input ≠ sanitizado | sanitizado: {email_san} [{codepoints(email_san)}] | lido: {val} [{codepoints(val)}]")

    # 2.b) Disparo dos métodos de submit
    btn_info = _btn_debug(driver, btn)
    print(f"   🔍 Botão 'Consultar' — displayed={btn_info['displayed']} enabled={btn_info['enabled']} disabled_attr={btn_info['disabled_attr']}")
    submit_snapshot = _snapshot_submit_state(driver)
    dump_json_artifact(
        {
            "email": email,
            "email_sanitizado": email_san,
            "fill_mode": fill_mode,
            "btn_info": btn_info,
            "submit_snapshot": submit_snapshot,
        },
        prefix="servico_tv_submit_payload",
    )

    before = list(driver.window_handles)
    modo, ok_clicked = _try_click_methods(driver, el_input, btn)

    # 3) **NOVO**: tratar overlay de pré-busca
    ensure_overlay_after_submit(driver, timeout=timeout_pos_click)
    aba_preservada = _garantir_aba_servico_tv(driver, timeout=timeout_pos_click)

    # 4) Alterna para nova aba se houver
    switched = _switch_to_new_window_if_opened(driver, before_handles=before, timeout=2.0)

    return {
        "modo": modo,
        "fill_mode": fill_mode,
        "ok_clicked": ok_clicked,
        "match": same,
        "valor_lido": val,
        "btn_info": btn_info,
        "switched_window": switched,
        "aba_servico_tv_ativa": aba_preservada,
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
