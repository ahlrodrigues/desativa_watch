# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/sgp_navigation.py
# Comentário: Navegação pós-login do SGP compatível com Chrome/Firefox e menus Superfish.
# - Abre "Clientes" (hover/click/JS) → "Consultar V2"
# - Depois, "Serviço de TV"
# - Auto-detecção de iframes do menu
# - Logs detalhados de cada tentativa

from __future__ import annotations
from typing import List, Tuple, Optional
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchFrameException
from .config import SGP_BASE_URL

# =========================
# Localizadores tolerantes
# =========================

# Várias formas de achar o item "Clientes"
LOC_CLIENTES_CANDIDATES: List[Tuple[str, str]] = [
    # <a><span>Clientes</span></a> com classes superfish
    (By.XPATH, '//a[contains(@class,"sf-with-ul")][span[normalize-space()="Clientes"]]'),
    # <a>Clientes</a> direto
    (By.XPATH, '//a[normalize-space()="Clientes"]'),
    # <li> ancestral contendo o link com span
    (By.XPATH, '//li[a[span[normalize-space()="Clientes"]]]/a'),
    # qualquer <a> visível com texto Clientes
    (By.XPATH, '//*[self::a or self::button][normalize-space()="Clientes"]'),
]

# "Consultar V2" (case e espaços tolerantes)
LOC_CONSULTAR_V2: List[Tuple[str, str]] = [
    (By.XPATH, '//a[normalize-space()="Consultar V2"]'),
    (By.XPATH, '//a[contains(normalize-space(),"Consultar V2")]'),
    (By.CSS_SELECTOR, 'a[href="/admin/cliente/search/"]'),
    (By.CSS_SELECTOR, 'a[href*="/admin/cliente/search/"]'),
]

# "Serviço de TV" (com e sem acento)
LOC_SERVICO_TV: List[Tuple[str, str]] = [
    (By.XPATH, '//*[self::a or self::button][normalize-space()="Serviço de TV" or contains(normalize-space(),"Serviço de TV")]'),
    (By.XPATH, '//*[self::a or self::button][normalize-space()="Servico de TV" or contains(normalize-space(),"Servico de TV")]'),
]

# =========================
# Utilitários base
# =========================

def _log(msg: str):
    print(f"[NAV] {msg}")

def _wait_visible_clickable(driver, locator, timeout=15):
    by, sel = locator
    el = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((by, sel)))
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def _js_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    driver.execute_script("arguments[0].click();", el)

def _find_first_clickable(driver, candidates: List[Tuple[str, str]], timeout_each=6):
    last_err = None
    for by, sel in candidates:
        try:
            el = _wait_visible_clickable(driver, (by, sel), timeout=timeout_each)
            return el
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise TimeoutException("Nenhum candidato clicável encontrado.")

def _hover(driver, el, pause=0.25):
    ActionChains(driver).move_to_element(el).pause(pause).perform()

def _open_submenu_js(driver, el_clientes):
    """
    Força abertura do submenu via JS:
    - adiciona classe 'sfHover' no <li> ancestral
    - exibe <ul> filho
    """
    li = None
    try:
        li = el_clientes.find_element(By.XPATH, "./ancestor::li[1]")
    except Exception:
        pass
    if li:
        driver.execute_script("""
          const li = arguments[0];
          li.classList.add('sfHover');
          const ul = li.querySelector('ul');
          if (ul) { ul.style.display = 'block'; ul.style.visibility = 'visible'; }
        """, li)


def _abrir_consultar_v2_direto(driver, timeout=10):
    """
    Fallback robusto: navega direto para a rota conhecida de 'Consultar V2'.
    """
    alvo = urljoin(SGP_BASE_URL + "/", "admin/cliente/search/")
    driver.switch_to.default_content()
    driver.get(alvo)
    WebDriverWait(driver, timeout).until(lambda d: "/admin/cliente/search/" in (d.current_url or ""))
    _log(f"'Consultar V2' aberto por URL direta: {alvo}")

def _ensure_menu_context(driver) -> Optional[int]:
    """
    Garante que estamos no contexto (top-level ou iframe) onde o menu está.
    - Primeiro tenta no top-level.
    - Se não achar, varre iframes e troca para o primeiro onde 'Clientes' aparece.
    Retorna o índice do iframe (ou None para top-level).
    """
    driver.switch_to.default_content()
    # top-level?
    for by, sel in LOC_CLIENTES_CANDIDATES:
        if driver.find_elements(by, sel):
            _log("Menu encontrado no top-level.")
            return None

    # procurar em iframes
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for idx in range(len(frames)):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(idx)
            for by, sel in LOC_CLIENTES_CANDIDATES:
                if driver.find_elements(by, sel):
                    _log(f"Menu encontrado no iframe index={idx}.")
                    return idx
        except NoSuchFrameException:
            continue
        except Exception:
            continue

    # não achou; volta ao default
    driver.switch_to.default_content()
    _log("Menu não encontrado em nenhum contexto.")
    return None

# =========================
# Fluxos de navegação
# =========================

def ir_para_consultar_v2(driver, timeout=20):
    """
    Abre o menu 'Clientes' e clica em 'Consultar V2' com múltiplas estratégias:
      1) hover no item Clientes
      2) click no item Clientes (Firefox muitas vezes exige click)
      3) força com JS (classe sfHover + display:block)
    Tenta automaticamente o contexto top-level e, se necessário, percorre iframes.
    """
    # 0) Contexto correto (top/iframe)
    iframe_idx = _ensure_menu_context(driver)

    # 1) Localiza 'Clientes'
    el_clientes = _find_first_clickable(driver, LOC_CLIENTES_CANDIDATES, timeout_each=timeout//2)
    _log("Item 'Clientes' localizado.")

    # 2) Tentativas para abrir o submenu
    opened = False
    # 2.1 hover
    try:
        _hover(driver, el_clientes, pause=0.35)
        WebDriverWait(driver, 3).until(lambda d: any(d.find_elements(*loc) for loc in LOC_CONSULTAR_V2))
        opened = True
        _log("Submenu aberto por HOVER.")
    except Exception:
        _log("Hover não exibiu submenu.")

    # 2.2 click (se ainda não)
    if not opened:
        try:
            el_clientes.click()
            WebDriverWait(driver, 3).until(lambda d: any(d.find_elements(*loc) for loc in LOC_CONSULTAR_V2))
            opened = True
            _log("Submenu aberto por CLICK.")
        except WebDriverException:
            try:
                _js_click(driver, el_clientes)
                WebDriverWait(driver, 3).until(lambda d: any(d.find_elements(*loc) for loc in LOC_CONSULTAR_V2))
                opened = True
                _log("Submenu aberto por JS-click.")
            except Exception:
                _log("Click/JS-click não exibiram submenu.")

    # 2.3 força via JS (classe/estilo)
    if not opened:
        _open_submenu_js(driver, el_clientes)
        try:
            WebDriverWait(driver, 3).until(lambda d: any(d.find_elements(*loc) for loc in LOC_CONSULTAR_V2))
            opened = True
            _log("Submenu aberto forçando via JS (sfHover/display:block).")
        except Exception:
            pass

    if not opened:
        raise TimeoutException("Não foi possível abrir o submenu de 'Clientes'.")

    # 3) Clicar 'Consultar V2'
    try:
        el_consultar = _find_first_clickable(driver, LOC_CONSULTAR_V2, timeout_each=timeout//2)
        try:
            el_consultar.click()
        except WebDriverException:
            _js_click(driver, el_consultar)
        _log("'Consultar V2' clicado.")
    except Exception:
        _log("Link visível de 'Consultar V2' não apareceu; tentando URL direta.")
        _abrir_consultar_v2_direto(driver, timeout=timeout)
        driver.switch_to.default_content()
        return

    # 4) Após clique, voltar ao top-level (se vínhamos de iframe)
    driver.switch_to.default_content()

def abrir_servico_de_tv(driver, timeout=20):
    """
    Na tela 'Consultar V2', clica no item/aba/link 'Serviço de TV'.
    Usa clique normal e fallback JS.
    """
    # Pode haver re-render; busque até ficar clicável
    last_err = None
    for by, sel in LOC_SERVICO_TV:
        try:
            el = _wait_visible_clickable(driver, (by, sel), timeout=timeout)
            try:
                el.click()
            except WebDriverException:
                _js_click(driver, el)
            _log("'Serviço de TV' clicado.")
            return
        except Exception as e:
            last_err = e

    raise TimeoutException(f"'Serviço de TV' não encontrado/clicável. Último erro: {last_err}")

def ir_para_consultar_v2_e_servico_tv(driver, timeout=20):
    """Atalho: abre 'Consultar V2' e depois 'Serviço de TV'."""
    ir_para_consultar_v2(driver, timeout=timeout)
    abrir_servico_de_tv(driver, timeout=timeout)

def reabrir_servico_de_tv(driver, mode: str = "click_path", timeout: int = 20):
    """
    Reabre a tela 'Serviço de TV' evitando histórico/back.
    modes:
      - 'reload': refresh e valida input
      - 'click_path': Clientes → Consultar V2 → Serviço de TV
      - 'new_tab': use a versão com navegação via href/aba (não incluída aqui pra simplicidade)
    """
    driver.switch_to.default_content()

    if mode == "reload":
        try:
            driver.refresh()
            _log("Reaberto por reload().")
            return
        except Exception:
            _log("Reload falhou; tentando caminho completo.")

    # caminho completo
    ir_para_consultar_v2(driver, timeout=timeout)
    abrir_servico_de_tv(driver, timeout=timeout)
