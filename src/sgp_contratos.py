# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/sgp_contratos.py
# Comentário: amplia os seletores para o link de edição (fallbacks além de a.edit).

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from time import sleep

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

LOC_BTN_DESATIVAR = [
    (By.XPATH, "//a[contains(@class,'button') and contains(@class,'red') and contains(normalize-space(),'Desativar')]"),
    (By.CSS_SELECTOR, "a.button.red")
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

def abrir_aba_contratos(driver):
    _wait_any(driver, LOC_TAB_CONTRATOS, timeout=20, click=True)
    for locator in LOC_PAINEL_CONTRATOS:
        try:
            WebDriverWait(driver, 20).until(EC.visibility_of_element_located(locator))
            return
        except Exception:
            continue
    raise TimeoutException("Painel #contratos não ficou visível após clicar na aba.")

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
    if not rows:
        return False

    row = rows[0]
    link_ativo = row.find_element(By.XPATH, ".//a[normalize-space()='Ativo']")
    try: link_ativo.click()
    except WebDriverException: driver.execute_script("arguments[0].click();", link_ativo)

    btn = _wait_any(driver, LOC_BTN_DESATIVAR, timeout=20, click=False)
    try: btn.click()
    except WebDriverException: driver.execute_script("arguments[0].click();", btn)

    sleep(0.5)
    return True
