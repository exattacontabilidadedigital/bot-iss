from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # janela visível
        page = browser.new_page()
        page.goto("https://example.com")
        print("Título da página:", page.title())
        input("Pressione ENTER para fechar o navegador...")  # pausa pra ver a janela
        browser.close()

if __name__ == "__main__":
    run()
