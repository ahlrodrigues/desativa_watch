# /seu_projeto_sgp/src/sgp_login.py
# Comentário: Fluxo de login no SGP. 
# Ajuste apenas os seletores caso o HTML do seu SGP seja diferente.

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .config import SGP_BASE_URL, SGP_USER, SGP_PASS, IMPLICIT_WAIT

# === Seletor centralizado para facilitar manutenção ===
# Dica: copie do DASH SERASA o mesmo padrão de nomes se já usamos lá.
SEL_INPUT_USER = 'input[name="username"], input#username, input[name="login"]'
SEL_INPUT_PASS = 'input[name="password"], input#password'
SEL_BTN_SUBMIT = 'button[type="submit"], button#btnLogin, button.login-button'

def _find_first_present(driver, css_selector, timeout=15):
    """
    Tenta localizar o primeiro elemento que casa com um seletor CSS, dentre vários candidatos
    separados por vírgula. Isso ajuda quando os ambientes mudam IDs/classes.
    """
    for piece in map(str.strip, css_selector.split(",")):
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, piece))
            )
        except Exception:
            continue
    raise TimeoutError(f"Nenhum seletor encontrado para: {css_selector}")

def login(driver):
    """
    Realiza o login no SGP:
    1) Abre a página de login (SGP_BASE_URL + /accounts/login)
    2) Preenche usuário/senha
    3) Submete e aguarda redirecionamento
    Retorna quando o login for bem-sucedido (URL muda ou aparece um elemento pós-login).
    """
    # Alguns SGPs redirecionam / para /accounts/login; por isso acessamos direto a rota /accounts/login
    # Se sua tela de login estiver na raiz, basta trocar para SGP_BASE_URL.
    login_url = f"{SGP_BASE_URL}/accounts/login"
    driver.get(login_url)

    # Espera implícita leve para páginas mais pesadas
    driver.implicitly_wait(IMPLICIT_WAIT)

    # Preenche credenciais
    el_user = _find_first_present(driver, SEL_INPUT_USER, timeout=20)
    el_user.clear()
    el_user.send_keys(SGP_USER)

    el_pass = _find_first_present(driver, SEL_INPUT_PASS, timeout=20)
    el_pass.clear()
    el_pass.send_keys(SGP_PASS)

    btn_submit = _find_first_present(driver, SEL_BTN_SUBMIT, timeout=20)
    btn_submit.click()

    # Estratégias de confirmação de login:
    # - aguardar URL sair de /login
    # - OU aguardar um elemento típico do dashboard (ajustável quando você me disser)
    WebDriverWait(driver, 30).until_not(EC.url_contains("/login"))

    # Caso precise: aqui podemos garantir um elemento do pós-login
    # WebDriverWait(driver, 30).until(
    #     EC.presence_of_element_located((By.CSS_SELECTOR, "nav .menu-dashboard"))
    # )
