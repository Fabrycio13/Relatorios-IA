import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
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
if sys.platform == "linux" or os.environ.get("CI"):
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
else:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

def carregar_cookies_se_existir(context):
    cookies = []
    env_token = os.environ.get("X_AUTH_TOKEN")
    env_ct0 = os.environ.get("X_CT0")

    token_val = env_token.strip() if env_token else None
    ct0_val = env_ct0.strip() if env_ct0 else None

    if not token_val and os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            token_val = data.get("auth_token")
            ct0_val = data.get("ct0")
        except Exception as e:
            print(f"Aviso ao carregar auth.json: {e}")

    if token_val:
        for domain in [".x.com", "x.com", ".twitter.com", "twitter.com"]:
            cookies.append({
                "name": "auth_token",
                "value": token_val,
                "domain": domain,
                "path": "/",
                "secure": True,
                "httpOnly": True
            })
            if ct0_val:
                cookies.append({
                    "name": "ct0",
                    "value": ct0_val,
                    "domain": domain,
                    "path": "/",
                    "secure": True
                })

    if cookies:
        context.add_cookies(cookies)
        print(f"Cookies de autenticação ({len(cookies)}) aplicados com sucesso.")

def coletar_tweets(max_scrolls=18, headless=True):
    print("=" * 60)
    print("Coletando posts do X (Feed Seguindo / Following)...")
    print(f"Data da execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Objetivo: Coletar ciclo completo das últimas 24h a 36h")
    print("=" * 60)

    tweets_coletados = []
    seen_texts = set()
    limite_tempo = datetime.now(timezone.utc) - timedelta(hours=48)
    alcancou_limite = False

    with sync_playwright() as p:
        launch_args = {
            "user_data_dir": SESSION_DIR,
            "headless": headless,
            "user_agent": USER_AGENT,
            "viewport": {"width": 1280, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"]
        }

        context = None
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

        # Remove propriedade webdriver para evitar detecção
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        carregar_cookies_se_existir(context)

        page = context.pages[0] if context.pages else context.new_page()

        print("Acessando https://x.com/home ...")
        try:
            page.goto("https://x.com/home", wait_until="networkidle", timeout=60000)
        except Exception:
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        current_url = page.url
        print(f"Página acessada. URL: {current_url} | Título: {page.title()}")

        if "login" in current_url or "onboarding" in current_url:
            print("\n[AVISO DE AUTENTICAÇÃO]")
            print("A sessão ainda não está autenticada no X.")
            print(f"URL retornada: {current_url}")
            context.close()
            sys.exit(1)

        # Fecha eventuais banners de cookies ou popups
        try:
            for btn_text in ["Accept all cookies", "Refuse non-essential cookies", "Aceitar todos os cookies", "Aceitar", "Dismiss"]:
                b = page.locator(f"button:has-text('{btn_text}'), span:has-text('{btn_text}')")
                if b.count() > 0:
                    b.first.click()
                    print(f"Banner/Popup dispensado: {btn_text}")
                    time.sleep(1)
                    break
        except Exception:
            pass

        # Espera carregar a lista de tweets ou abas
        try:
            page.wait_for_selector("article[data-testid='tweet'], div[role='tablist']", timeout=15000)
        except Exception as e:
            print(f"Aviso ao aguardar timeline: {e}")

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

                    if timestamp:
                        try:
                            dt_tweet = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            if dt_tweet < limite_tempo:
                                alcancou_limite = True
                        except Exception:
                            pass

                    # Extrai métricas de engajamento (curtidas, comentários, reposts, visualizações)
                    likes = ""
                    reposts = ""
                    replies = ""
                    views = ""
                    try:
                        like_btn = art.locator("button[data-testid='like']")
                        if like_btn.count() > 0:
                            likes = like_btn.inner_text().strip()
                        retweet_btn = art.locator("button[data-testid='retweet']")
                        if retweet_btn.count() > 0:
                            reposts = retweet_btn.inner_text().strip()
                        reply_btn = art.locator("button[data-testid='reply']")
                        if reply_btn.count() > 0:
                            replies = reply_btn.inner_text().strip()
                        analytics_link = art.locator("a[href*='/analytics']")
                        if analytics_link.count() > 0:
                            views = analytics_link.inner_text().strip()
                    except Exception:
                        pass

                    tweets_coletados.append({
                        "author_name": name,
                        "author_handle": handle_str,
                        "timestamp": timestamp,
                        "text": tweet_text,
                        "url": tweet_url,
                        "likes": likes,
                        "reposts": reposts,
                        "replies": replies,
                        "views": views
                    })
                except Exception:
                    continue

            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2.5)

            if alcancou_limite and len(tweets_coletados) >= 15:
                print(f"\n[OK] Ciclo de 24h a 36h já totalmente coberto ({len(tweets_coletados)} tweets capturados). Encerrando rolagens.")
                break

        if len(tweets_coletados) == 0:
            print("\n[DIAGNÓSTICO] Nenhum tweet foi capturado.")
            print(f"Título da página: {page.title()}")
            print(f"URL final: {page.url}")
            try:
                body_sample = page.inner_text("body")[:400].replace("\n", " ")
                print(f"Amostra de texto da página: {body_sample}")
            except Exception:
                pass

        context.close()

    if len(tweets_coletados) == 0:
        print("\n[ERRO] Nenhum tweet coletado nesta execução. O arquivo anterior foi preservado.")
        sys.exit(1)

    print(f"\n[OK] Total de tweets coletados: {len(tweets_coletados)}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tweets_coletados, f, ensure_ascii=False, indent=2)

    print(f"Arquivo gerado em: {OUTPUT_FILE}")
    return tweets_coletados

if __name__ == "__main__":
    is_headless = "--headed" not in sys.argv
    coletar_tweets(headless=is_headless)
