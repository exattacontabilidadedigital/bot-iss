import time
import logging
import re
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta
from playwright.sync_api import sync_playwright, expect


logging.basicConfig(level=logging.INFO)
# Configuração do banco de dados
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

# Geração de períodos
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

# Função principal de encerramento
def encerrar_movimento(page, periodos):
    """Executa o encerramento para lista de períodos com seletores precisos e fluxo otimizado"""
    try:
        page.get_by_role("button", name="Movimento").click()
        main_frame = page.frame_locator('#main')

        for mes, ano in periodos:
            try:
                # ----- FASE 1: ALTERAÇÃO DE PERÍODO -----
                main_frame.get_by_role("button", name="Alterar").wait_for(timeout=30000)
                main_frame.get_by_role("button", name="Alterar").click()

                # Preenche período
                main_frame.locator('select[name="mes"]').select_option(value=mes)
                main_frame.locator('input[name="ano"]').fill(ano)
                main_frame.get_by_role("button", name="Ok").click(timeout=30000)
                time.sleep(1)
                page.locator("#main").content_frame.get_by_text("Encerramento").nth(1).click()
                time.sleep(1)


                print('ate aqui ta ok')

                # ----- FASE 2: VERIFICAÇÃO DE STATUS -----
                encerrado_locator = main_frame.locator(
                    'xpath=//a[@href="../fechamento/prestado.php" and normalize-space()="A Escrituração já foi Encerrada"]'
                )
                
                if encerrado_locator.is_visible():
                    print(f"⏭️ {mes}/{ano} já encerrado. Pulando...")
                    continue  # Pula para próximo período

                # ----- FASE 3: PROCESSO DE ENCERRAMENTO -----
                # Etapa 3.1: clica no botão 'encerrar escrituração'        

                print('vou clicar')
                #page.locator("#main").content_frame.get_by_text("Encerramento").nth(1).click()
                print('clique!!!!!')

                link_encerrar =  page.locator("#main").content_frame.get_by_role("link", name="Encerrar Escrituração")
                link_encerrar.wait_for(state='visible', timeout=45000)
                link_encerrar.click(timeout=30000)

                # Etapa 3.2: clicar no botão 'encerrar mês'
                #expect(main_frame.get_by_role("heading", name="Encerramento Livro Fiscal - Serviços Prestados")).to_be_visible(timeout=60000)
                page.locator("#main").content_frame.get_by_role("button", name="Encerrar Mês.").click()
                
                # Etapa 3.3: Confirmação final
                page.locator("#main").content_frame.get_by_role("row", name="Encerramento Livro Fiscal - Serviços Prestados", exact=True).locator("div").click()
                
                # Etapa 3.4: Retorno ao menu principal
                #main_frame.locator('.iconFechar').click()
                #main_frame.get_by_role("button", name="Voltar").click()
                print(f"✅ {mes}/{ano} encerrado com sucesso!")
                time.sleep(3)

            except Exception as e:                
                print(f"❌ Falha em {mes}/{ano}: {str(e)}")
                time.sleep(3)
                continue  # Não tente clicar em um botão que não existe


    except Exception as e:
        print(f"❌ Erro crítico: {str(e)}")
        raise


# Fluxo principal
def run(playwright):
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

        # Processo de encerramento
        main_frame.locator("#cnpj").fill("35496100000135")
        main_frame.get_by_role("button", name="Pesquisar").click()
        main_frame.locator("td.cell.center:has-text('35496100000135')").click()
        main_frame.locator("button[name='btnAcessar']").click()
        
        periodos = gerar_periodos("09", "2024", "03", "2025")
        encerrar_movimento(page, periodos)

    except Exception as e:
        print(f"❌ Erro geral: {str(e)}")
        page.screenshot(path="erro_geral.png")
    finally:
        time.sleep(3)
        context.close()
        browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
