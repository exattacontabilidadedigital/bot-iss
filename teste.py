from playwright.sync_api import sync_playwright

import time
import pytesseract
from PIL import Image
import requests
from io import BytesIO


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headless=False => abre o navegador visível
    page = browser.new_page()
    page.goto("https://acailandia.sigiss.com.br/acailandia/index.php?ref=Site-Prefeitura-Link-home")
    
    print("Página aberta com sucesso!")

    # Acesso à área de contadores
    page.get_by_role("row", name="Acesso para acompanhamento de declarações e gestão de contribuintes vinculados a contadores no município de Açailândia.", exact=True).get_by_role("link").click()
    
    # Preenchimento das credenciais
    page.get_by_role("textbox", name="CRC do Contador").fill("012452")
    page.get_by_role("textbox", name="******").fill("romario12")

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



    
    
    # Mantenha o navegador aberto por 30 segundos para você visualizar
    page.wait_for_timeout(5000)
    
    browser.close()
