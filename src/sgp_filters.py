# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/sgp_filters.py
# Comentário: garante que o painel de filtros esteja visível (para enxergar #id_login_tv).
# Procura por botões/links de "Mostrar/Exibir filtros", "Filtros", "Nova pesquisa"/"Pesquisar novamente".
# Se não achar, tenta um fallback via JS para exibir containers comuns de filtros.

from __future__ import annotations
from typing import List, Tuple
from time import sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Campo que precisamos ver
SEL_INPUT_LOGIN_TV = (By.CSS_SELECTOR, "#id_login_tv")

# Candidatos de toggle dos filtros por texto/classe/id
TOGGLE_CANDIDATES: List[Tuple[str, str]] = [
    # textos mais comuns
    (By.XPATH, '//*[self::a or self::button][normalize-space()="Mostrar filtros" or contains(normalize-space(),"Mostrar filtros")]'),
    (By.XPATH, '//*[self::a or self::button][normalize-space()="Exibir filtros"  or contains(normalize-space(),"Exibir filtros")]'),
    (By.XPATH, '//*[self::a or self::button][normalize-space()="Filtros"        or contains(normalize-space(),"Filtros")]'),
    (By.XPATH, '//*[self::a or self::button][normalize-space()="Nova pesquisa"  or contains(normalize-space(),"Nova pesquisa")]'),
    (By.XPATH, '//*[self::a or self::button][contains(normalize-space(),"Pesquisar novamente")]'),
    # por classes/ids sugestivos
    (By.CSS_SELECTOR, 'a[id*="filtro"], button[id*="filtro"], a[class*="filtro"], button[class*="filtro"]'),
    (By.CSS_SELECTOR, 'a[id*="pesquisa"], button[id*="pesquisa"], a[class*="pesquisa"], button[class*="pesquisa"]'),
]

# Possíveis containers de filtros para fallback JS
FILTER_BOXES: List[Tuple[str, str]] = [
    (By.CSS_SELECTOR, "#filtros, #filtro, #filters, #search-filters, .filtros, .filters, .box-filtros, .search-box"),
]

def _log(msg: str):
    print(f"[FILTROS] {msg}")

def _input_visivel(driver) -> bool:
    try:
        el = driver.find_element(*SEL_INPUT_LOGIN_TV)
        return el.is_displayed()
    except Exception:
        return False

def _click(driver, el):
    try:
        el.click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", el)

def _tentar_clicks_toggle(driver) -> bool:
    """Tenta clicar em algum controle que revele os filtros."""
    for by, sel in TOGGLE_CANDIDATES:
        try:
            els = driver.find_elements(by, sel)
            for el in els:
                if not el.is_displayed():
                    continue
                _click(driver, el)
                # dá um tempo pro DOM atualizar
                for _ in range(10):
                    if _input_visivel(driver):
                        return True
                    sleep(0.1)
        except Exception:
            continue
    return False

def _fallback_js_exibir(driver) -> bool:
    """Último recurso: tenta exibir containers de filtro via JS (remove hidden, display:block)."""
    try:
        for by, sel in FILTER_BOXES:
            for box in driver.find_elements(by, sel):
                driver.execute_script("""
                    const el = arguments[0];
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                    el.classList.remove('hidden');
                    el.removeAttribute('hidden');
                """, box)
        # reaplica em algum loop curto
        for _ in range(10):
            if _input_visivel(driver):
                return True
            sleep(0.1)
    except Exception:
        pass
    return False

def ensure_filtros_visiveis(driver, timeout: int = 10) -> bool:
    """
    Garante que #id_login_tv esteja visível:
      1) se já está visível → OK
      2) tenta clicar toggles conhecidos
      3) fallback: forçar exibição de caixas de filtro via JS
    Retorna True/False. Lança TimeoutException se explicitamente solicitado (não aqui).
    """
    # caso já esteja ok
    if _input_visivel(driver):
        _log("Input de login visível.")
        return True

    _log("Input não visível; tentando abrir filtros (toggles).")
    if _tentar_clicks_toggle(driver):
        _log("Filtros exibidos via toggle.")
        return True

    _log("Toggles não funcionaram; tentando fallback JS.")
    if _fallback_js_exibir(driver):
        _log("Filtros exibidos via fallback JS.")
        return True

    _log("Não foi possível exibir os filtros.")
    return False
