import logging
import os
from playwright.sync_api import sync_playwright
from sigiss.db import save_to_database
from sigiss.periodos import gerar_periodos
from sigiss.sigiss import SigissPage
from sigiss.periodos import gerar_periodos


# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def run():
    # Carrega credenciais de ambiente ou config
    crc      = os.getenv("SIGISS_CRC",      "012452")
    senha    = os.getenv("SIGISS_SENHA",    "romario12")
    cnpj     = os.getenv("SIGISS_CNPJ",     "35496100000135")
    db_path  = os.getenv("SIGISS_DB_PATH",  "empresas.db")
    inicio_m = os.getenv("SIGISS_INI_MES",  "07")
    inicio_a = os.getenv("SIGISS_INI_ANO",  "2023")
    fim_m    = os.getenv("SIGISS_FIM_MES",  "03")
    fim_a    = os.getenv("SIGISS_FIM_ANO",  "2025")

    periodos = gerar_periodos(inicio_m, inicio_a, fim_m, fim_a)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page    = context.new_page()

        sigiss = SigissPage(page)
        try:
            sigiss.login(crc, senha)
            sigiss.go_to_carteira()
            dados = sigiss.extract_client_list()
            save_to_database(dados, db_path)

            sigiss.open_client(cnpj)
            sigiss.encerrar_movimento(periodos)

        except Exception as e:
            logging.error("Erro no fluxo principal: %s", e, exc_info=True)
            page.screenshot(path="erro_fluxo.png")
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    run()
