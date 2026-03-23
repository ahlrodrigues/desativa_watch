# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/sgp_contratos.py
# Comentário: amplia os seletores para o link de edição (fallbacks além de a.edit).

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import re
from urllib.parse import urljoin

LOC_EDIT_LINKS = [
    (By.CSS_SELECTOR, "a.edit"),
    (By.CSS_SELECTOR, 'a[href*="/edit"]'),
    (By.XPATH, '//a[@title="Editar" or contains(@aria-label,"Editar")]'),
    (By.XPATH, '//*[self::button or self::a][@title="Editar" or contains(@class,"edit") or contains(@aria-label,"Editar")]'),
    (By.XPATH, '//i[contains(@class,"fa-pencil") or contains(@class,"glyphicon-pencil")]/ancestor::a[1]'),
    (By.XPATH, '//img[contains(translate(@alt,"EDITAR","editar"),"editar")]/ancestor::a[1]'),
]

LOC_TAB_CONTRATOS = [
    (By.CSS_SELECTOR, "a#contratosdo.ui-tabs-anchor"),
    (By.XPATH, "//a[@href='#contratos' and (normalize-space()='Contratos' or contains(normalize-space(),'Contratos'))]"),
    (By.XPATH, "//a[contains(@class,'ui-tabs-anchor') and @href='#contratos']"),
]

LOC_PAINEL_CONTRATOS = [
    (By.CSS_SELECTOR, "#contratos"),
    (By.XPATH, "//*[@id='contratos']")
]

XPATH_ROW_WATCH_ATIVO = (
    ".//tr[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'WATCH')]"
    "[.//a[normalize-space()='Ativo']]"
)

XPATH_LINK_WATCH_ATIVO = (
    ".//a[contains(@href, '/admin/servicos/tv/') and "
    "contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'WATCH') and "
    "contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'ATIVO')]"
)

XPATH_LINK_WATCH = (
    ".//a[contains(@href, '/admin/servicos/tv/') and "
    "contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'WATCH')]"
)

LOC_BTN_DESATIVAR = [
    (By.XPATH, "//a[contains(@class,'button') and contains(@class,'red') and contains(normalize-space(),'Desativar')]"),
    (By.CSS_SELECTOR, "a.button.red")
]

LOC_STATUS_ATIVO_SERVICO = [
    (By.XPATH, "//*[contains(normalize-space(),'Status:')]/span[contains(normalize-space(),'Ativo')]"),
    (By.XPATH, "//*[contains(normalize-space(),'Situação:')]/strong[contains(normalize-space(),'Ativo')]"),
]

LOC_STATUS_INATIVO_SERVICO = [
    (By.XPATH, "//*[contains(normalize-space(),'Status:')]/span[contains(normalize-space(),'Inativo')]"),
    (By.XPATH, "//*[contains(normalize-space(),'Situação:')]/strong[contains(normalize-space(),'Inativo')]"),
]

LOC_STATUS_DESATIVAR_CONFIRM = [
    (By.XPATH, "//*[self::h1 or self::h2 or self::div or self::span][contains(normalize-space(),'Desativar')]"),
    (By.XPATH, "//form//input[@type='submit' and contains(@value,'Desativar')]"),
    (By.XPATH, "//button[contains(normalize-space(),'Desativar')]"),
]

LOC_CAMPO_GATEWAY_ID = [
    (By.CSS_SELECTOR, "#id_servicot-gateway_id"),
]

LOC_CAMPO_SMARTCARD = [
    (By.CSS_SELECTOR, "#id_servicot-smartcard"),
]

LOC_BTN_SALVAR_SERVICO = [
    (By.XPATH, "//input[@type='submit' and contains(@value,'Salvar')]"),
    (By.XPATH, "//button[@type='submit' and contains(normalize-space(),'Salvar')]"),
]

def _wait_any(driver, locators, timeout=20, click=False):
    last_err = None
    for by, sel in locators:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))
            if click:
                try: el.click()
                except WebDriverException: driver.execute_script("arguments[0].click();", el)
            return el
        except Exception as e:
            last_err = e
    raise TimeoutException(str(last_err) if last_err else "Elemento não encontrado")

def clicar_link_editar_cliente(driver):
    """Clica no link/botão 'Editar' do cliente após a consulta (sem depender só de a.edit)."""
    _wait_any(driver, LOC_EDIT_LINKS, timeout=20, click=True)

def _cliente_id_da_url(url: str) -> str | None:
    m = re.search(r"/admin/cliente/(\d+)(?:/|$)", url or "")
    return m.group(1) if m else None

def abrir_aba_contratos(driver):
    cliente_id = _cliente_id_da_url(driver.current_url or "")
    if cliente_id:
        url_contratos = urljoin(driver.current_url, f"/admin/cliente/{cliente_id}/contratos/")
        driver.get(url_contratos)
        WebDriverWait(driver, 12).until(lambda d: "/contratos/" in (d.current_url or ""))
        for locator in LOC_PAINEL_CONTRATOS:
            try:
                WebDriverWait(driver, 12).until(EC.visibility_of_element_located(locator))
                return
            except Exception:
                continue
    _wait_any(driver, LOC_TAB_CONTRATOS, timeout=20, click=True)
    for locator in LOC_PAINEL_CONTRATOS:
        try:
            WebDriverWait(driver, 12).until(EC.visibility_of_element_located(locator))
            return
        except Exception:
            continue
    raise TimeoutException("Painel #contratos não ficou visível após clicar na aba.")


def _limpar_campo(driver, locators):
    campo = _wait_any(driver, locators, timeout=20, click=False)
    valor_atual = (campo.get_attribute("value") or "").strip()
    estava_preenchido = bool(valor_atual)
    if not estava_preenchido:
        return campo, False
    try:
        campo.click()
    except WebDriverException:
        pass
    try:
        campo.clear()
    except WebDriverException:
        pass
    try:
        campo.send_keys(Keys.CONTROL, "a")
        campo.send_keys(Keys.DELETE)
    except WebDriverException:
        pass
    try:
        driver.execute_script("arguments[0].value='';", campo)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
            campo,
        )
    except WebDriverException:
        pass
    return campo, estava_preenchido


def limpar_gateway_id_e_smartcard(driver):
    gateway_campo = _wait_any(driver, LOC_CAMPO_GATEWAY_ID, timeout=20, click=False)
    smartcard_campo = _wait_any(driver, LOC_CAMPO_SMARTCARD, timeout=20, click=False)
    gateway_valor = (gateway_campo.get_attribute("value") or "").strip()
    smartcard_valor = (smartcard_campo.get_attribute("value") or "").strip()

    gateway_preenchido = bool(gateway_valor)
    smartcard_preenchido = bool(smartcard_valor)
    if not (gateway_preenchido or smartcard_preenchido):
        return {
            "gateway_preenchido": False,
            "smartcard_preenchido": False,
            "salvou": False,
        }

    if gateway_preenchido:
        _limpar_campo(driver, LOC_CAMPO_GATEWAY_ID)
    if smartcard_preenchido:
        _limpar_campo(driver, LOC_CAMPO_SMARTCARD)

    btn = _wait_any(driver, LOC_BTN_SALVAR_SERVICO, timeout=20, click=False)
    try:
        btn.click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", btn)
    WebDriverWait(driver, 20).until(
        lambda d: "salvo com sucesso" in (d.page_source or "").lower()
        or "status:" in (d.page_source or "").lower()
        or any(d.find_elements(by, sel) for by, sel in LOC_CAMPO_GATEWAY_ID)
    )
    page_low = (driver.page_source or "").lower()
    gateway_vazio = driver.find_element(*LOC_CAMPO_GATEWAY_ID[0]).get_attribute("value") == ""
    smart_vazio = (driver.find_element(*LOC_CAMPO_SMARTCARD[0]).get_attribute("value") or "").strip() == ""
    if not (gateway_vazio and smart_vazio):
        raise TimeoutException("Gateway ID/SmartCard não ficaram vazios após salvar.")
    return {
        "gateway_preenchido": gateway_preenchido,
        "smartcard_preenchido": smartcard_preenchido,
        "salvou": True,
    }

def verificar_e_desativar_watch(driver) -> bool:
    painel = None
    for by, sel in LOC_PAINEL_CONTRATOS:
        try:
            painel = WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, sel)))
            break
        except Exception:
            continue
    if painel is None:
        raise TimeoutException("Painel 'Contratos' não encontrado.")

    rows = painel.find_elements(By.XPATH, XPATH_ROW_WATCH_ATIVO)
    if rows:
        row = rows[0]
        link_ativo = row.find_element(By.XPATH, ".//a[normalize-space()='Ativo']")
        try:
            link_ativo.click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", link_ativo)
        WebDriverWait(driver, 20).until(EC.url_contains("/admin/servicos/"))
    else:
        links_watch = painel.find_elements(By.XPATH, XPATH_LINK_WATCH_ATIVO)
        if not links_watch:
            links_watch = painel.find_elements(By.XPATH, XPATH_LINK_WATCH)
        if not links_watch:
            return False
        watch_link = links_watch[0]
        watch_href = watch_link.get_attribute("href") or ""
        if watch_href:
            driver.get(watch_href)
        else:
            try:
                watch_link.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", watch_link)
        WebDriverWait(driver, 20).until(EC.url_contains("/admin/servicos/tv/"))
        if any(driver.find_elements(by, sel) for by, sel in LOC_STATUS_INATIVO_SERVICO):
            return False
        _wait_any(driver, LOC_STATUS_ATIVO_SERVICO, timeout=20, click=False)
    limpar_gateway_id_e_smartcard(driver)

    btn = _wait_any(driver, LOC_BTN_DESATIVAR, timeout=20, click=False)
    deact_href = btn.get_attribute("href") or ""
    if deact_href:
        driver.get(deact_href)
    else:
        try:
            btn.click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", btn)
    WebDriverWait(driver, 20).until(
        lambda d: any(
            d.find_elements(by, sel) for by, sel in LOC_STATUS_DESATIVAR_CONFIRM
        ) or "serviço desativado com sucesso" in (d.page_source or "").lower() or any(
            d.find_elements(by, sel) for by, sel in LOC_STATUS_ATIVO_SERVICO
        )
    )
    page_low = (driver.page_source or "").lower()
    confirmed = (
        "serviço desativado com sucesso" in page_low
        or "status: <span class=\"tbold\"> inativo" in page_low
        or "situação: <strong>inativo" in page_low
        or "ativar</a>" in page_low
    )
    if not confirmed:
        raise TimeoutException("A página não confirmou a mudança do serviço após desativar.")
    return True
