# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/main_login_test.py
# Comentário: Teste de login + navegação até Consultar V2 + clique em Serviço de TV.

from .driver import build_driver
from .sgp_login import login
from .sgp_navigation import ir_para_consultar_v2, abrir_servico_de_tv
# Alternativa: from .sgp_navigation import ir_para_consultar_v2_e_servico_tv

def run():
    driver = build_driver()
    try:
        login(driver)
        print("✅ Login OK")

        ir_para_consultar_v2(driver)
        print("✅ Consultar V2 aberto")

        abrir_servico_de_tv(driver)
        print("✅ Serviço de TV aberto")

        input("Pressione ENTER para fechar...")  # útil com HEADLESS=false
    finally:
        driver.quit()

if __name__ == "__main__":
    run()
