import os
import sys
import time
from playwright.sync_api import sync_playwright

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".session")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

def main():
    print("=" * 60)
    print("Iniciando Google Chrome para Login no X...")
    print(f"Diretório de sessão: {SESSION_DIR}")
    print("=" * 60)

    with sync_playwright() as p:
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            channel="chrome",
            headless=False,
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()
        print("\nNavegando para https://x.com/login ...")
        page.goto("https://x.com/login")

        print("\n" + "#" * 60)
        print("POR FAVOR, DIGITE SEU LOGIN E SENHA NA JANELA DO CHROME.")
        print("Assim que você entrar e a timeline do X (x.com/home) carregar,")
        print("o script detectará o sucesso automaticamente!")
        print("#" * 60 + "\n")

        logged_in = False
        start_time = time.time()
        # Aguarda até 10 minutos para dar tempo ao usuário
        while time.time() - start_time < 600:
            try:
                current_url = page.url
                # Se estiver no /home ou se houver elementos da timeline autenticada
                has_nav = page.locator("nav[role='navigation']").count() > 0 or page.locator("article[data-testid='tweet']").count() > 0
                if ("x.com/home" in current_url or has_nav) and "login" not in current_url and "onboarding" not in current_url:
                    logged_in = True
                    print("\n>> SUCESSO! Login confirmado na página inicial do X.")
                    time.sleep(3)
                    break
            except Exception:
                # Janela fechada pelo usuário
                break
            time.sleep(2)

        try:
            browser_context.close()
        except Exception:
            pass

        if logged_in:
            print("\n✓ Sessão autenticada e salva com sucesso em .session!")
            print("Pronto para rodar as coletas diárias em segundo plano.")
        else:
            print("\nJanela fechada antes de confirmar login em x.com/home.")

if __name__ == "__main__":
    main()
