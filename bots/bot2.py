import time
import logging
import re
import sqlite3
import json
import sys
from datetime import datetime
from dateutil.relativedelta import relativedelta
from playwright.sync_api import sync_playwright, expect
import requests
import asyncio
import websockets
import pytesseract
from PIL import Image


# Configuração de logging com codificação UTF-8
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   encoding='utf-8')
logger = logging.getLogger('bot')

# Função para enviar alertas via WebSocket
async def enviar_alerta(cnpj, status):
    """Envia alertas via WebSocket para o servidor principal"""
    try:
        # Conecta ao servidor WebSocket na porta 5000 (mesma do Flask)
        async with websockets.connect('ws://localhost:5000') as websocket:
            await websocket.send(json.dumps({
                "tipo": "encerramento_concluido",
                "cnpj": cnpj,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }))
    except Exception as e:
        logger.error(f"Erro ao enviar alerta WebSocket: {e}")



# Função principal chamada pelo servidor
def main(cnpj, periodo_inicial, periodo_final, callback_status=None):
    """Função principal chamada pelo servidor"""
    logger.info(f"Encerrando movimento para CNPJ: {cnpj}, de {periodo_inicial} até {periodo_final}")
    
    # Remover formatação do período (MM/AAAA -> MMAAAA)
    periodo_inicial = periodo_inicial.replace('/', '')
    periodo_final = periodo_final.replace('/', '')
    
    # Se callback_status existir, use-o para atualizar o status
    if callback_status:
        callback_status('iniciando')
    
    with sync_playwright() as playwright:
        run(playwright, cnpj, periodo_inicial, periodo_final, callback_status)

# Configuração do banco de dados
def save_to_database(dados):
    """Salva dados no banco SQLite com substituição de duplicados"""
    try:
        # Abrir conexão com o banco
        with sqlite3.connect('empresas.db') as conn:
            c = conn.cursor()
            
            # Verificar se as colunas existem
            c.execute("PRAGMA table_info(empresas)")
            colunas = [col[1] for col in c.fetchall()]
            
            # Criar a tabela se não existir
            c.execute('''CREATE TABLE IF NOT EXISTS empresas (
                im TEXT, 
                cnpj TEXT UNIQUE,
                nome TEXT, 
                omisso TEXT, 
                debito TEXT,
                status TEXT DEFAULT 'pendente',
                progresso TEXT DEFAULT '0'
            )''')
            
            # Inserir os dados, substituindo os duplicados
            c.executemany('INSERT OR REPLACE INTO empresas (im, cnpj, nome, omisso, debito) VALUES (?, ?, ?, ?, ?)', dados)
            
            # Commit para garantir a gravação dos dados
            conn.commit()
            logger.info(f"{len(dados)} registros salvos com sucesso no banco.")
    
    except sqlite3.Error as e:
        logger.error(f"Erro ao salvar no banco de dados: {e}")

# Atualização de status no banco de dados
def atualizar_status_db(cnpj, status, progresso):
    """Atualiza o status e progresso no banco de dados"""
    try:
        with sqlite3.connect('empresas.db') as conn:
            c = conn.cursor()
            c.execute('''
                UPDATE empresas 
                SET status = ?, progresso = ? 
                WHERE cnpj = ?
            ''', (status, progresso, cnpj))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Erro ao atualizar status: {e}")

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
def encerrar_movimento(page, cnpj, periodo_inicial, periodo_final, callback_status=None):
    """Executa o encerramento para um CNPJ e um intervalo de períodos"""
    try:       

        # Extrai mês e ano do periodo_inicial e periodo_final (formato MMAAAA)
        mes_inicial = periodo_inicial[:2]  # Primeiros 2 caracteres para o mês
        ano_inicial = periodo_inicial[2:]  # Últimos 4 caracteres para o ano
        mes_final = periodo_final[:2]  # Primeiros 2 caracteres para o mês
        ano_final = periodo_final[2:]  # Últimos 4 caracteres para o ano
        
        # Gerar a lista de períodos a partir das entradas de início e fim
        periodos = gerar_periodos(mes_inicial, ano_inicial, mes_final, ano_final)
        total_periodos = len(periodos)
        
        for i, (mes, ano) in enumerate(periodos):
            try:
                # Calcular progresso
                progresso = int((i / total_periodos) * 100)
                atualizar_status_db(cnpj, 'em_processo', str(progresso))
                if callback_status:
                    callback_status(f'processando_periodo_{mes}_{ano}')
                
                # ----- FASE 1: ALTERAÇÃO DE PERÍODO -----
                # Clica no botão "Movimento" no menu principal
                page.get_by_role("button", name="Movimento").click()
                time.sleep(1)
            
                # Acessa o frame principal
                main_frame = page.frame_locator('#main')

                # Clica no botão "Alterar"
                main_frame.get_by_role("button", name="Alterar").wait_for(timeout=60000)
                main_frame.get_by_role("button", name="Alterar").click()
                time.sleep(1)

                # Preenche período
                main_frame.locator('select[name="mes"]').select_option(value=mes)
                main_frame.locator('input[name="ano"]').fill(ano)
                time.sleep(1)
                main_frame.get_by_role("button", name="Ok").click(timeout=30000)
                time.sleep(3)  # Espera para carregamento da página
                
                # Clique no menu Encerramento
                encerramento_menu = main_frame.locator('//td[@class="textBold" and contains(@onclick, "tableEncerra_t") and contains(., "Encerramento")]')
                encerramento_menu.wait_for(state='visible', timeout=30000)
                encerramento_menu.click()
                time.sleep(2)  # Espera para carregamento do submenu

                # ----- FASE 2: VERIFICAÇÃO DE STATUS -----
                encerrado_locator = main_frame.locator(
                    'xpath=//a[@href="../fechamento/tomado.php" and contains(text(), "Escrituração já foi Encerrada")]'
                )
                
                if encerrado_locator.is_visible(timeout=5000):
                    print(f"⏭️ Período {mes}/{ano} já encerrado. Pulando...")
                    continue  # Pula para o próximo período
                    
                main_frame = page.frame_locator("#main")
                # ----- FASE 3: PROCESSO DE ENCERRAMENTO -----
                # Etapa 3.1: clica no link de encerramento
                link_encerrar = main_frame.locator('a[href="../fechamento/tomado.php"]')
                link_encerrar.wait_for(state='visible', timeout=45000)
                link_encerrar.click(timeout=30000)
                time.sleep(1)
                print('veio ate aqui')
                
                # Etapa 3.2: clicar no botão 'encerrar mês'
                encerrar_btn = page.locator("#main").content_frame.get_by_role("button", name="Encerrar Mês")
                encerrar_btn.wait_for(state='visible', timeout=30000)
                encerrar_btn.click()
                time.sleep(7)
                print('veio ate aqui tbm')

                # Etapa 3.3: Clicar no botão fechar
                page.once("dialog", lambda dialog: dialog.accept())
                time.sleep(3)
                main_frame = page.frame_locator("#main")
                fechar = main_frame.locator(".iconFechar")
                fechar.click()


                #main_frame = page.frame_locator("#main")
                #confirmar_locator = page.locator("xpath=/html/body/form/table/tbody/tr/td/table/tbody/tr[1]/td[2]/div").click()
                #confirmar_locator.wait_for(state='visible', timeout=30000)
                #confirmar_locator.click(timeout=30000)
                time.sleep(1)
                  


                                
                print(f"✅ Período {mes}/{ano} encerrado com sucesso!")
                time.sleep(3)  # Espera para estabilização

            except Exception as e:                
                print(f"❌ Falha no período {mes}/{ano}: {str(e)}")
                page.screenshot(path=f"erro_{mes}_{ano}.png")
                time.sleep(3)
                continue  # Continua para o próximo período

        # Atualizar status final
        atualizar_status_db(cnpj, 'concluido', '100')
        if callback_status:
            callback_status('concluido')

        time.sleep(1)
        
        # Enviar notificação de conclusão
        try:
            asyncio.run(enviar_alerta(cnpj, 'concluido'))
        except Exception as e:
            print(f"Erro ao enviar alerta final: {e}")

    except Exception as e:
        print(f"❌ Erro crítico: {str(e)}")
        atualizar_status_db(cnpj, 'erro', '0')
        if callback_status:
            callback_status('erro')
        raise


# Fluxo principal
def run(playwright, cnpj, periodo_inicial, periodo_final, callback_status=None):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        if callback_status:
            callback_status('iniciando_login')
            
        # Login
        page.goto("https://acailandia.sigiss.com.br/acailandia/index.php")
        expect(page).to_have_title(".:: PREFEITURA - Açailândia ::.")

        # Acesso à área de contadores
        page.get_by_role("row", name="Acesso para acompanhamento de declarações e gestão de contribuintes vinculados a contadores no município de Açailândia.", exact=True).get_by_role("link").click()
        
        # Preenchimento das credenciais
        page.get_by_role("textbox", name="CRC do Contador").fill("012452")
        page.get_by_role("textbox", name="******").fill("romario12")
        
        ################### OCRC ###############################
        tentativas = 0
        sucesso = False

        while tentativas < 10:
            tentativas += 1

            # Espera a imagem aparecer e capturar
            captcha_element = page.query_selector('div#div-img-captcha img')
            captcha_element.screenshot(path="captcha.png")

            # abre a imagem e converte para preto e branco e aumenta o tamanho para o ocr
            img = Image.open("captcha.png")
            img = img.convert('L')
            img = img.point(lambda x: 0 if x < 140 else 255, '1')

            # ocr da imagem
            texto_ocr = pytesseract.image_to_string(img).strip()
            print(f"OCR capturado: '{texto_ocr}'")

            # Validar o OCR (exemplo: captcha deve ter 6 caracteres alfanuméricos)
            if len(texto_ocr) == 4 and texto_ocr.isalnum():
                print("OCR válido, preenchendo campo...")
                page.fill('#confirma', texto_ocr)
                #page.get_by_role("button", name="  Login").click()

                time.sleep(1)
                # clicar no btn login
                page.get_by_role("button", name="  Login").click()

                # Espera um pouco para verificar se o login foi bem-sucedido
                page.wait_for_timeout(3000)

                # Verifica se ainda está na tela do captcha (indicando falha)
                erro_captcha = page.query_selector("#mensagem-erro")  # ou outro seletor de erro, se existir
                #erro_captcha = page.query_selector('//html/body/table/tbody/tr[2]/td/div/div/div/div/div/div/form/div[2]/div[4]/table/tbody/tr/td[1]')


                if erro_captcha and erro_captcha.inner_text().strip() != "":
                    print("Captcha incorreto, tentando novamente...")
                    # Atualiza o captcha clicando no div (caso necessário)
                    page.click("#div-img-captcha")
                    page.wait_for_function(f"document.querySelector('div#div-img-captcha img').getAttribute('src') != '{src}'")
                    continue
                else:
                    print("Login provavelmente bem-sucedido.")
                    sucesso = True
                    break
            else:
                img.save(f"captcha_tentativa_{tentativas}.png")
                print("OCR inválido, atualizando captcha para tentar de novo...")
                page.click("#div-img-captcha")  # atualiza a imagem clicando
                page.wait_for_timeout(1000)  # espera recarregar

        if not sucesso:
            print("Não foi possível resolver o captcha após várias tentativas.")



        ################### OCRC ###############################

        if callback_status:
            callback_status('extraindo_dados')

        # Navegação para a carteira de clientes
        page.get_by_role("button", name="Contribuinte").click()
        page.get_by_role("link", name="Carteira de Clientes").click()

        # Acesso ao frame principal e espera pela tabela
        main_frame = page.frame_locator('#main')
        
               
        # Espera pelo primeiro elemento da tabela com timeout maior
        #main_frame.locator("tr.line").nth(0).wait_for(state='visible', timeout=60000)
        main_frame.locator("tr.line").first.wait_for(state='visible', timeout=60000)

        # Extração dos dados
        rows = main_frame.locator("tr.line")
        dados = []
        
        for i in range(rows.count()):
            try:
                row = rows.nth(i)
                cells = row.locator("td")
                
                if cells.count() >= 5:
                    im = cells.nth(0).inner_text().strip().replace('\xa0', '')
                    cnpj_empresa = cells.nth(1).inner_text().strip().replace('\xa0', '')
                    nome = cells.nth(2).inner_text().strip().replace('\xa0', '')
                    omisso = cells.nth(3).inner_text().strip().replace('\xa0', '')
                    debito = cells.nth(4).inner_text().strip().replace('\xa0', '')
                    
                    dados.append((im, cnpj_empresa, nome, omisso, debito))
                else:
                    logger.warning(f"Linha {i+1} não tem o número esperado de células.")
            except Exception as e:
                logger.error(f"Erro ao processar a linha {i+1}: {e}")
                continue

        # Salvar no banco de dados
        save_to_database(dados)
        logger.info(f"Dados salvos: {len(dados)} registros")

        if callback_status:
            callback_status('iniciando_encerramento')

        # Processo de encerramento
        main_frame = page.frame_locator('#main')
        
        
        # input cnpj da empresa para fazer o encerramento
        # Processo de encerramento
        main_frame.locator("#cnpj").fill(cnpj)  # Agora o CNPJ vem da variável cnpj
        main_frame.get_by_role("button", name="Pesquisar").click()
        main_frame.locator(f"td.cell.center:has-text('{cnpj}')").click()  # Usando o cnpj na busca
                
        # Clica no botão de acesso
        main_frame.locator("button[name='btnAcessar']").click()
        
        # Executa o encerramento
        encerrar_movimento(page, cnpj, periodo_inicial, periodo_final, callback_status=None)

       


    except Exception as e:
        logger.error(f"Erro geral: {str(e)}")
        page.screenshot(path="erro_geral.png")
        if callback_status:
            callback_status('erro')
        raise
    finally:
        time.sleep(3)
        context.close()
        browser.close()

if __name__ == '__main__':
    # Configurar saída para UTF-8
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    if len(sys.argv) > 3:
        cnpj = sys.argv[1]
        periodo_inicial = sys.argv[2]
        periodo_final = sys.argv[3]
        
        with sync_playwright() as playwright:
            run(playwright, cnpj, periodo_inicial, periodo_final)
        
        # Após finalizar tudo, enviar o alerta para o frontend
        try:
            response = requests.post(
                "http://localhost:5000/encerramento_concluido",
                json={"status": "concluido", "cnpj": cnpj}
            )
            logger.info(f"Resposta do front: {response.status_code}")
        except Exception as e:
            logger.error(f"Erro ao enviar alerta para o frontend: {e}")

        # Enviar também via websocket
        try:
            asyncio.run(enviar_alerta(cnpj, 'concluido'))
        except Exception as e:
            logger.error(f"Erro ao enviar alerta WebSocket: {e}")
    else:
        logger.error("Faltando parâmetros para execução!")
        print("Uso: python bot.py <cnpj> <periodo_inicial> <periodo_final>")
