import json
import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, ".session")
AUTH_FILE = os.path.join(BASE_DIR, "auth.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "tweets_coletados.json")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

def carregar_cookies_se_existir(context):
    cookies = []
    env_token = os.environ.get("X_AUTH_TOKEN")
    env_ct0 = os.environ.get("X_CT0")

    if env_token:
        cookies.append({"name": "auth_token", "value": env_token.strip(), "domain": ".x.com", "path": "/"})
    if env_ct0:
        cookies.append({"name": "ct0", "value": env_ct0.strip(), "domain": ".x.com", "path": "/"})

    if not cookies and os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "auth_token" in data:
                cookies.append({"name": "auth_token", "value": data["auth_token"], "domain": ".x.com", "path": "/"})
            if "ct0" in data:
                cookies.append({"name": "ct0", "value": data["ct0"], "domain": ".x.com", "path": "/"})
        except Exception as e:
            print(f"Aviso ao carregar auth.json: {e}")

    if cookies:
        context.add_cookies(cookies)
        print(f"Cookies de autenticação ({len(cookies)}) aplicados com sucesso.")

def coletar_tweets(max_scrolls=8, headless=True):
    print("=" * 60)
    print("Coletando posts do X (Feed Seguindo / Following)...")
    print(f"Data da execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    tweets_coletados = []
    seen_texts = set()

    with sync_playwright() as p:
        launch_args = {
            "user_data_dir": SESSION_DIR,
            "headless": headless,
            "user_agent": USER_AGENT,
            "viewport": {"width": 1280, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"]
        }

        context = None
        # No ambiente local Windows, tenta Chrome estável; em CI/Linux usa Chromium padrão
        if sys.platform == "win32" and not os.environ.get("CI"):
            try:
                context = p.chromium.launch_persistent_context(channel="chrome", **launch_args)
            except Exception:
                pass

        if context is None:
            try:
                context = p.chromium.launch_persistent_context(**launch_args)
            except Exception as e:
                print(f"Erro ao abrir contexto do Chromium: {e}")
                sys.exit(1)

        carregar_cookies_se_existir(context)

        page = context.pages[0] if context.pages else context.new_page()

        print("Acessando https://x.com/home ...")
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        current_url = page.url
        if "login" in current_url or "onboarding" in current_url:
            print("\n[AVISO DE AUTENTICAÇÃO]")
            print("A sessão ainda não está autenticada no X.")
            print("Você pode autenticar de duas formas:")
            print(" 1) Rodar 'python login_x.py' e fazer login na janela do Chrome;")
            print(" 2) Criar o arquivo 'auth.json' em D:\\Projetos\\Relatorios - IA com:")
            print('    {\n      "auth_token": "seu_cookie_auth_token",\n      "ct0": "seu_cookie_ct0"\n    }')
            context.close()
            sys.exit(1)

        print("Localizando aba 'Seguindo' / 'Following'...")
        try:
            abas = page.locator("div[role='tablist'] a[role='tab']").all()
            for aba in abas:
                texto_aba = aba.inner_text().strip().lower()
                if "seguindo" in texto_aba or "following" in texto_aba:
                    aba.click()
                    print(f"Aba selecionada: '{texto_aba}'")
                    time.sleep(3)
                    break
        except Exception as e:
            print(f"Nota ao selecionar aba: {e}")

        # Rolagem e coleta de tweets
        for scroll in range(max_scrolls):
            articles = page.locator("article[data-testid='tweet']").all()
            print(f"Scroll {scroll + 1}/{max_scrolls} - Tweets encontrados na visualização: {len(articles)}")

            for art in articles:
                try:
                    text_elem = art.locator("div[data-testid='tweetText']")
                    if text_elem.count() == 0:
                        continue
                    tweet_text = text_elem.inner_text().strip()

                    if tweet_text in seen_texts or len(tweet_text) < 15:
                        continue
                    seen_texts.add(tweet_text)

                    user_elem = art.locator("div[data-testid='User-Name']")
                    user_info = user_elem.inner_text() if user_elem.count() > 0 else ""
                    user_lines = [l.strip() for l in user_info.split("\n") if l.strip()]
                    name = user_lines[0] if len(user_lines) > 0 else "Autor Desconhecido"
                    handle = [l for l in user_lines if l.startswith("@")]
                    handle_str = handle[0] if handle else ""

                    time_elem = art.locator("time")
                    timestamp = time_elem.get_attribute("datetime") if time_elem.count() > 0 else ""

                    link_elems = art.locator("a[href*='/status/']").all()
                    tweet_url = ""
                    for le in link_elems:
                        href = le.get_attribute("href")
                        if href and "/status/" in href:
                            tweet_url = f"https://x.com{href}" if href.startswith("/") else href
                            break

                    tweets_coletados.append({
                        "author_name": name,
                        "author_handle": handle_str,
                        "timestamp": timestamp,
                        "text": tweet_text,
                        "url": tweet_url
                    })
                except Exception:
                    continue

            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2.5)

        context.close()

    print(f"\n[OK] Total de tweets coletados: {len(tweets_coletados)}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tweets_coletados, f, ensure_ascii=False, indent=2)

    print(f"Arquivo gerado em: {OUTPUT_FILE}")
    return tweets_coletados

if __name__ == "__main__":
    is_headless = "--headed" not in sys.argv
    coletar_tweets(headless=is_headless)
