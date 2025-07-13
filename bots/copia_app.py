import time
import logging
import re
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta
from playwright.sync_api import sync_playwright, expect
import sys
import requests
import asyncio
import websockets

logging.basicConfig(level=logging.INFO)

async def enviar_alerta():
    async with websockets.connect('ws://localhost:8000') as websocket:
        await websocket.send("encerramento_concluido")

def main():
    cnpj = sys.argv[1]  # CNPJ
    periodo_inicial = sys.argv[2]  # Período inicial
    periodo_final = sys.argv[3]  # Período final

    print(f"Encerrando movimento para CNPJ: {cnpj}, de {periodo_inicial} até {periodo_final}")

def save_to_database(dados):
    """Salva dados no banco SQLite com substituição de duplicados"""
    conn = sqlite3.connect('empresas.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS empresas (
        im TEXT, 
        cnpj TEXT UNIQUE,
        nome TEXT, 
        omisso TEXT, 
        debito TEXT
    )''')
    
    c.executemany('INSERT OR REPLACE INTO empresas VALUES (?, ?, ?, ?, ?)', dados)
    conn.commit()
    conn.close()

def gerar_periodos(mes_inicio, ano_inicio, mes_fim, ano_fim):
    """Gera lista de períodos no formato (MM, AAAA)"""
    periodos = []
    data_inicio = datetime(int(ano_inicio), int(mes_inicio), 1)
    data_fim = datetime(int(ano_fim), int(mes_fim), 1)
    
    atual = data_inicio
    while atual <= data_fim:
        periodos.append((f"{atual.month:02d}", str(atual.year)))
        atual += relativedelta(months=1)
    return periodos

def encerrar_movimento(page, cnpj, periodo_inicial, periodo_final):
    try:
        page.get_by_role("button", name="Movimento").click()
        main_frame = page.frame_locator('#main')

        # Extrai mês e ano do periodo_inicial e periodo_final (formato MMAAAA)
        mes_inicial = periodo_inicial[:2]  # Primeiros 2 caracteres para o mês
        ano_inicial = periodo_inicial[2:]  # Últimos 4 caracteres para o ano
        mes_final = periodo_final[:2]  # Primeiros 2 caracteres para o mês
        ano_final = periodo_final[2:]  # Últimos 4 caracteres para o ano

        # Gerar a lista de períodos a partir das entradas de início e fim
        periodos = gerar_periodos(mes_inicial, ano_inicial, mes_final, ano_final)

        for mes, ano in periodos:
            try:
                main_frame.get_by_role("button", name="Alterar").click()
                main_frame.locator('select[name="mes"]').select_option(value=mes)
                main_frame.locator('input[name="ano"]').fill(ano)
                main_frame.get_by_role("button", name="Ok").click()
                time.sleep(1)

                page.locator("#main").content_frame.get_by_text("Encerramento").nth(3).click()
                time.sleep(1)

                encerrado_locator = main_frame.locator(
                    'xpath=//a[@href="../fechamento/tomado.php" and normalize-space()="A Escrituração já foi Encerrada"]'
                )

                if encerrado_locator.is_visible():
                    print(f"⏭️ {mes}/{ano} já encerrado. Pulando...")
                    continue

                link_encerrar = page.locator("#main").content_frame.get_by_role("link", name="Encerrar Escrituração")
                link_encerrar.click()
                page.locator("#main").content_frame.get_by_role("button", name="Encerrar Mês").click()
                page.locator("#main").content_frame.get_by_role("row", name="Encerramento Livro Fiscal - Serviços Tomados", exact=True).locator("div").click()
                
                print(f"✅ {mes}/{ano} encerrado com sucesso!")
                time.sleep(3)

            except Exception as e:                
                print(f"❌ Falha em {mes}/{ano}: {str(e)}")
                continue

    except Exception as e:
        print(f"❌ Erro crítico: {str(e)}")
        raise

def run(playwright, cnpj, periodo_inicial, periodo_final):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Login
        page.goto("https://acailandia.sigiss.com.br/acailandia/index.php")
        expect(page).to_have_title(".:: PREFEITURA - Açailândia ::.")

        # Acesso à área de contadores
        page.get_by_role("row", name="Acesso para acompanhamento de declarações e gestão de contribuintes vinculados a contadores no município de Açailândia.", exact=True).get_by_role("link").click()
        
        # Preenchimento das credenciais
        page.get_by_role("textbox", name="CRC do Contador").fill("012452")
        page.get_by_role("textbox", name="******").fill("romario12")
        
        # Espera para CAPTCHA manual
        time.sleep(15)
        page.get_by_role("button", name="  Login").click()

        # Navegação para a carteira de clientes
        page.get_by_role("button", name="Contribuinte").click()
        page.get_by_role("link", name="Carteira de Clientes").click()

        # Extração de dados
        main_frame = page.frame_locator('#main')
        main_frame.locator("tr.line").first.wait_for(timeout=15000)
        
        dados = []
        rows = main_frame.locator("tr.line")
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            dados.append((
                cells.nth(0).inner_text().strip().replace('\xa0', ''),
                cells.nth(1).inner_text().strip().replace('\xa0', ''),
                cells.nth(2).inner_text().strip().replace('\xa0', ''),
                cells.nth(3).inner_text().strip().replace('\xa0', ''),
                cells.nth(4).inner_text().strip().replace('\xa0', '')
            ))
        
        save_to_database(dados)
        print(f"📊 {len(dados)} registros salvos")

        # input cnpj da empresa para fazer o encerramento
        # Processo de encerramento
        main_frame.locator("#cnpj").fill(cnpj)  # Agora o CNPJ vem da variável cnpj
        main_frame.get_by_role("button", name="Pesquisar").click()
        main_frame.locator(f"td.cell.center:has-text('{cnpj}')").click()  # Usando o cnpj na busca
        main_frame.locator("button[name='btnAcessar']").click()
        
        #periodos = gerar_periodos("09", "2024", "03", "2025")
        encerrar_movimento(page, cnpj, periodo_inicial, periodo_final)

    except Exception as e:
        print(f"❌ Erro geral: {str(e)}")
        page.screenshot(path="erro_geral.png")
    finally:
        time.sleep(3)
        context.close()
        browser.close()

if __name__ == '__main__':
    if len(sys.argv) > 3:
        cnpj = sys.argv[1]
        periodo_inicial = sys.argv[2]
        periodo_final = sys.argv[3]
        
        with sync_playwright() as playwright:
            run(playwright, cnpj, periodo_inicial, periodo_final)
        
        try:
            response = requests.post(
                "http://localhost:5000/api/encerramento",  # Envia um POST para o servidor
                json={  # Passa os dados em formato JSON
                    "status": "concluido",
                    "cnpj": cnpj,
                    "periodo_inicial": periodo_inicial,
                    "periodo_final": periodo_final
                },
                timeout=10  # Define o tempo de espera antes de uma falha
            )
            print(f"Notificação enviada: {response.status_code}")
        except Exception as e:
            print(f"Erro ao notificar servidor: {e}")
