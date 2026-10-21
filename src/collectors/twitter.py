import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

from src.core.config import BASE_DIR, TWEETS_DATA_FILE, config
from src.core.logger import get_logger
from src.core.models import Tweet

logger = get_logger("twitter_collector")
SESSION_DIR = BASE_DIR / ".session"

if sys.platform == "linux" or os.environ.get("CI"):
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
else:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

def carregar_cookies_se_existir(context):
    cookies = []
    token_val, ct0_val = config.get_twitter_credentials()

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
        logger.info(f"Cookies de autenticação do X ({len(cookies)}) aplicados com sucesso.")

def coletar_tweets_vip(max_scrolls=25, headless=True):
    logger.info("=" * 60)
    logger.info("Coletando posts do X (Feed Seguindo / Following)...")
    logger.info(f"Data da execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("Objetivo: Coletar ciclo completo das últimas 24h a 36h")
    logger.info("=" * 60)

    tweets_coletados = []
    seen_texts = set()
    limite_tempo = datetime.now(timezone.utc) - timedelta(hours=48)
    alcancou_limite = False

    with sync_playwright() as p:
        launch_args = {
            "user_data_dir": str(SESSION_DIR),
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
                logger.error(f"Erro ao abrir contexto do Chromium: {e}")
                sys.exit(1)

        # Remove propriedade webdriver para evitar detecção
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        carregar_cookies_se_existir(context)

        page = context.pages[0] if context.pages else context.new_page()

        logger.info("Acessando https://x.com/home ...")
        try:
            page.goto("https://x.com/home", wait_until="networkidle", timeout=60000)
        except Exception:
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        current_url = page.url
        logger.info(f"Página acessada. URL: {current_url} | Título: {page.title()}")

        if "login" in current_url or "onboarding" in current_url:
            logger.warning("A sessão ainda não está autenticada no X.")
            context.close()
            sys.exit(1)

        # Clica na aba Seguindo
        try:
            following_tab = page.locator("a[href='/home'][role='tab'] >> text='Seguindo'").first
            if following_tab.is_visible(timeout=3000):
                following_tab.click()
                time.sleep(2)
        except Exception:
            pass

        # Realiza scroll
        for scroll_num in range(max_scrolls):
            if alcancou_limite:
                break

            articles = page.locator("article[data-testid='tweet']").all()
            for art in articles:
                try:
                    text_el = art.locator("div[data-testid='tweetText']").first
                    if not text_el.is_visible(timeout=1000):
                        continue
                    tweet_text = text_el.inner_text().strip()
                    if not tweet_text or tweet_text in seen_texts:
                        continue
                    seen_texts.add(tweet_text)

                    time_el = art.locator("time").first
                    timestamp = time_el.get_attribute("datetime") if time_el.is_visible(timeout=1000) else ""

                    if timestamp:
                        try:
                            tweet_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            if tweet_dt < limite_tempo:
                                alcancou_limite = True
                        except Exception:
                            pass

                    # Autor
                    author_name_el = art.locator("div[data-testid='User-Name']").first
                    author_name = author_name_el.inner_text().split("\n")[0] if author_name_el.is_visible(timeout=1000) else "Autor Desconhecido"
                    author_handle = ""
                    try:
                        handle_part = [line for line in author_name_el.inner_text().split("\n") if line.startswith("@")]
                        if handle_part:
                            author_handle = handle_part[0]
                    except Exception:
                        pass

                    # Métricas
                    def get_metric(test_id):
                        try:
                            el = art.locator(f"button[data-testid='{test_id}']").first
                            if el.is_visible(timeout=500):
                                return el.inner_text().strip() or "0"
                        except Exception:
                            pass
                        return "0"

                    replies = get_metric("reply")
                    reposts = get_metric("retweet")
                    likes = get_metric("like")
                    views = "0"
                    try:
                        view_el = art.locator("a[href*='/analytics']").first
                        if view_el.is_visible(timeout=500):
                            views = view_el.inner_text().strip() or "0"
                    except Exception:
                        pass

                    # URL
                    tweet_url = ""
                    try:
                        link_el = art.locator("a[href*='/status/']").first
                        if link_el.is_visible(timeout=500):
                            tweet_url = "https://x.com" + link_el.get_attribute("href")
                    except Exception:
                        pass

                    # Links externos
                    card_links = []
                    try:
                        links = art.locator("a[target='_blank']").all()
                        for l in links:
                            href = l.get_attribute("href")
                            if href and "t.co" in href:
                                card_links.append(href)
                    except Exception:
                        pass

                    tweets_coletados.append(Tweet(
                        author_name=author_name,
                        author_handle=author_handle,
                        timestamp=timestamp,
                        text=tweet_text,
                        url=tweet_url,
                        likes=likes,
                        reposts=reposts,
                        replies=replies,
                        views=views,
                        external_links=list(set(card_links))
                    ))
                except Exception:
                    continue

            page.mouse.wheel(0, 1500)
            time.sleep(1.5)

        # VIP Radar (Perfis de Referência)
        vip_profiles = [
            ("mattpocockuk", "Matt Pocock"),
            ("svpino", "Santiago Valdarrama"),
            ("swyx", "Swyx / Latent Space"),
            ("karpathy", "Andrej Karpathy"),
            ("jxnlco", "Jason Liu"),
            ("chipro", "Chip Huyen")
        ]

        logger.info("\n--- COLETANDO RADAR VIP DE PERFIS ESPECÍFICOS ---")
        for handle, nome_vip in vip_profiles:
            url_perfil = f"https://x.com/{handle}"
            logger.info(f"Acessando perfil VIP de {nome_vip} (@{handle})...")
            try:
                page.goto(url_perfil, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                articles_vip = page.locator("article[data-testid='tweet']").all()[:5]
                for art in articles_vip:
                    try:
                        text_el = art.locator("div[data-testid='tweetText']").first
                        if not text_el.is_visible(timeout=1000):
                            continue
                        tweet_text = text_el.inner_text().strip()
                        if not tweet_text or tweet_text in seen_texts:
                            continue
                        seen_texts.add(tweet_text)

                        time_el = art.locator("time").first
                        timestamp = time_el.get_attribute("datetime") if time_el.is_visible(timeout=1000) else ""

                        # Janela flexível de 4 dias para VIPs
                        if timestamp:
                            try:
                                tweet_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                if tweet_dt < (datetime.now(timezone.utc) - timedelta(days=4)):
                                    continue
                            except Exception:
                                pass

                        def get_metric(test_id):
                            try:
                                el = art.locator(f"button[data-testid='{test_id}']").first
                                if el.is_visible(timeout=500):
                                    return el.inner_text().strip() or "0"
                            except Exception:
                                pass
                            return "0"

                        replies = get_metric("reply")
                        reposts = get_metric("retweet")
                        likes = get_metric("like")
                        views = "0"
                        try:
                            view_el = art.locator("a[href*='/analytics']").first
                            if view_el.is_visible(timeout=500):
                                views = view_el.inner_text().strip() or "0"
                        except Exception:
                            pass

                        tweet_url = ""
                        try:
                            link_el = art.locator("a[href*='/status/']").first
                            if link_el.is_visible(timeout=500):
                                tweet_url = "https://x.com" + link_el.get_attribute("href")
                        except Exception:
                            pass

                        card_links = []
                        try:
                            links = art.locator("a[target='_blank']").all()
                            for l in links:
                                href = l.get_attribute("href")
                                if href and "t.co" in href:
                                    card_links.append(href)
                        except Exception:
                            pass

                        tweets_coletados.append(Tweet(
                            author_name=nome_vip,
                            author_handle=f"@{handle}",
                            timestamp=timestamp,
                            text=tweet_text,
                            url=tweet_url,
                            likes=likes,
                            reposts=reposts,
                            replies=replies,
                            views=views,
                            external_links=list(set(card_links))
                        ))
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Aviso ao consultar perfil de @{handle}: {e}")

        context.close()

    if len(tweets_coletados) == 0:
        logger.error("Nenhum tweet coletado nesta execução. O arquivo anterior foi preservado.")
        return []

    logger.info(f"Total de tweets coletados: {len(tweets_coletados)}")
    with open(TWEETS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([t.to_dict() for t in tweets_coletados], f, ensure_ascii=False, indent=2)

    logger.info(f"Arquivo gerado em: {TWEETS_DATA_FILE}")
    return tweets_coletados

if __name__ == "__main__":
    is_headless = "--headed" not in sys.argv
    coletar_tweets_vip(headless=is_headless)
