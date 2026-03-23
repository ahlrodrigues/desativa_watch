# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/driver.py
# Comentário: fábrica de WebDriver com suporte a Chrome e Firefox (via env BROWSER).
# - Use BROWSER=firefox para testar no Firefox; default = chrome.
# - Respeita HEADLESS, PAGELOAD_TIMEOUT, IMPLICIT_WAIT, LANG, DOWNLOADS_DIR.
# - Permite customizar caminhos dos drivers/binaries via CHROMEDRIVER_PATH/GECKODRIVER_PATH e CHROME_BIN/FIREFOX_BIN.

from __future__ import annotations
import os
from typing import Optional

from selenium.webdriver import Chrome, ChromeOptions, Firefox, FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

from .config import HEADLESS, PAGELOAD_TIMEOUT, IMPLICIT_WAIT, LANG, DOWNLOADS_DIR

def _build_chrome() -> Chrome:
    """Instancia um Chrome WebDriver com opções padrão do projeto."""
    opts = ChromeOptions()
    # Idioma
    opts.add_argument(f"--lang={LANG}")
    # Execução headless opcional
    if HEADLESS:
        opts.add_argument("--headless=new")
    # Estabilidade em containers/VM
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1366,900")
    # Pasta de download e locale
    prefs = {
        "intl.accept_languages": LANG,
        "download.default_directory": os.path.expanduser(DOWNLOADS_DIR),
        "download.prompt_for_download": False,
    }
    opts.add_experimental_option("prefs", prefs)
    # Binário opcional
    chrome_bin = os.getenv("CHROME_BIN")
    if chrome_bin:
        opts.binary_location = chrome_bin

    # Service (chromedriver)
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")  # se não setar, usa o que está no PATH
    service = ChromeService(executable_path=chromedriver_path) if chromedriver_path else ChromeService()

    driver = Chrome(service=service, options=opts)
    _apply_timeouts(driver)
    _print_caps(driver)
    return driver

def _build_firefox() -> Firefox:
    """Instancia um Firefox WebDriver (geckodriver) com opções padrão do projeto."""
    opts = FirefoxOptions()
    if HEADLESS:
        opts.add_argument("-headless")
    # Idioma
    opts.set_preference("intl.accept_languages", LANG)
    # Downloads (se um dia precisarmos baixar algo com FF)
    opts.set_preference("browser.download.useDownloadDir", True)
    opts.set_preference("browser.download.folderList", 2)  # 2 = pasta customizada
    opts.set_preference("browser.download.dir", os.path.expanduser(DOWNLOADS_DIR))
    # Binário opcional
    firefox_bin = os.getenv("FIREFOX_BIN")
    if firefox_bin:
        opts.binary_location = firefox_bin

    geckodriver_path = os.getenv("GECKODRIVER_PATH")  # se não setar, usa o que está no PATH
    service = FirefoxService(executable_path=geckodriver_path) if geckodriver_path else FirefoxService()

    driver = Firefox(service=service, options=opts)
    try:
        driver.set_window_size(1366, 900)
    except Exception:
        pass
    _apply_timeouts(driver)
    _print_caps(driver)
    return driver

def _apply_timeouts(driver):
    """Aplica timeouts globais do projeto."""
    try:
        driver.set_page_load_timeout(PAGELOAD_TIMEOUT)
    except Exception:
        pass
    try:
        driver.implicitly_wait(IMPLICIT_WAIT)
    except Exception:
        pass

def _print_caps(driver):
    """Loga o navegador em uso (útil pra debug)."""
    try:
        caps = driver.capabilities or {}
        name = caps.get("browserName", "?")
        ver = caps.get("browserVersion") or caps.get("version") or "?"
        print(f"🌐 Browser: {name} {ver} | HEADLESS={HEADLESS} | LANG={LANG}")
    except Exception:
        pass

def build_driver():
    """
    Decide o navegador via env BROWSER:
      - chrome (padrão)
      - firefox
    """
    browser = (os.getenv("BROWSER") or "chrome").strip().lower()
    if browser == "firefox":
        return _build_firefox()
    # default
    return _build_chrome()
