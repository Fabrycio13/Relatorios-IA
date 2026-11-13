import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

from src.core.config import BASE_DIR, config
from src.core.logger import get_logger
from src.core.models import Tweet, SourceCollectionResult, SourceStatus

logger = get_logger("twitter_collector")
SESSION_DIR = BASE_DIR / ".session"
MAX_EXECUTION_SECONDS = 300  # Timeout global de segurança: 5 minutos
MAX_CONSECUTIVE_OLD_TWEETS = 8  # Limite de segurança: 8 tweets consecutivos fora da janela indicam fim do horizonte temporal
MAX_EMPTY_SCROLLS = 3  # Limite de scrolls consecutivos sem novos tweets antes de abortar
DEFAULT_MAX_SCROLLS = 25

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

def _extrair_tweet(art, fallback_name: str | None = None, fallback_handle: str | None = None) -> Tweet | None:
    """Extrai e valida um objeto Tweet a partir do elemento article do DOM do X."""
    try:
        text_el = art.locator("div[data-testid='tweetText']").first
        if not text_el.is_visible(timeout=1000):
            return None
        tweet_text = text_el.inner_text().strip()
        if not tweet_text:
            return None

        time_el = art.locator("time").first
        timestamp = time_el.get_attribute("datetime") if time_el.is_visible(timeout=1000) else ""

        # Autor e @handle
        author_name = fallback_name or "Autor Desconhecido"
        author_handle = fallback_handle or "@desconhecido"
        author_name_el = art.locator("div[data-testid='User-Name']").first
        if author_name_el.is_visible(timeout=1000):
            lines = [line.strip() for line in author_name_el.inner_text().split("\n") if line.strip()]
            if lines and not fallback_name:
                author_name = lines[0]
            handles = [line for line in lines if line.startswith("@")]
            if handles and not fallback_handle:
                author_handle = handles[0]

        # Métricas de engajamento
        def get_metric(test_id):
            try:
                el = art.locator(f"button[data-testid='{test_id}']").first
                if el.is_visible(timeout=400):
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
            if view_el.is_visible(timeout=400):
                views = view_el.inner_text().strip() or "0"
        except Exception:
            pass

        # Link permanente do tweet
        tweet_url = ""
        try:
            link_el = art.locator("a[href*='/status/']").first
            if link_el.is_visible(timeout=400):
                href = link_el.get_attribute("href") or ""
                if href.startswith("http"):
                    tweet_url = href
                elif href:
                    tweet_url = "https://x.com" + href
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

        return Tweet(
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
        )
    except Exception:
        return None

def _selecionar_aba_seguindo(page: Page) -> bool:
    """Clica na aba 'Seguindo' ou 'Following' se visível para garantir feed cronológico."""
    try:
        following_tab = page.locator("a[href='/home'][role='tab']:has-text('Seguindo'), a[href='/home'][role='tab']:has-text('Following')").first
        if following_tab.is_visible(timeout=3000):
            following_tab.click()
            logger.info("Aba 'Seguindo / Following' selecionada com sucesso.")
            time.sleep(2)
            return True
        else:
            logger.debug("Aba 'Seguindo / Following' não visível ou feed já unificado.")
            return False
    except Exception as e:
        logger.warning(f"Aviso ao selecionar aba Seguindo: {e}")
        return False

def coletar_feed_principal(
    page: Page,
    limite_tempo: datetime,
    start_time: float | None = None,
    max_scrolls: int = DEFAULT_MAX_SCROLLS,
    max_consecutive_old: int = MAX_CONSECUTIVE_OLD_TWEETS,
    max_empty_scrolls: int = MAX_EMPTY_SCROLLS,
    scroll_delay: float = 1.5,
    seen_texts: set[str] | None = None,
) -> tuple[list[Tweet], set[str]]:
    """Coleta tweets recentes do feed principal com tratamento robusto de tweets antigos e esgotamento."""
    if start_time is None:
        start_time = time.time()
    if seen_texts is None:
        seen_texts = set()

    tweets_coletados: list[Tweet] = []
    consecutive_old_tweets = 0
    consecutive_empty_scrolls = 0

    for scroll_idx in range(max_scrolls):
        if time.time() - start_time > MAX_EXECUTION_SECONDS:
            logger.warning("Timeout global de segurança de 5 minutos atingido no feed.")
            break

        articles = page.locator("article[data-testid='tweet']").all()
        novos_nesta_rodada = 0
        alcancou_limite_antigos = False

        for art in articles:
            tweet_obj = _extrair_tweet(art)
            if not tweet_obj or tweet_obj.text in seen_texts:
                continue

            seen_texts.add(tweet_obj.text)
            novos_nesta_rodada += 1

            # Validação da janela temporal de 48 horas
            if tweet_obj.timestamp:
                try:
                    tweet_dt = datetime.fromisoformat(tweet_obj.timestamp.replace("Z", "+00:00"))
                    if tweet_dt < limite_tempo:
                        consecutive_old_tweets += 1
                        logger.debug(
                            f"Tweet fora da janela temporal ({tweet_obj.timestamp}): {tweet_obj.text[:40]}... "
                            f"(antigos consecutivos: {consecutive_old_tweets})"
                        )
                        if consecutive_old_tweets >= max_consecutive_old:
                            logger.info(
                                f"Limite de {max_consecutive_old} tweets consecutivos fora da janela atingido. "
                                f"Encerrando coleta do feed."
                            )
                            alcancou_limite_antigos = True
                            break
                        # Descarta tweet antigo isolado (pinned tweet, retweet) e continua analisando os demais
                        continue
                    else:
                        # Tweet válido dentro da janela temporal: zera contador de antigos consecutivos
                        consecutive_old_tweets = 0
                except Exception:
                    pass

            tweets_coletados.append(tweet_obj)

        if alcancou_limite_antigos:
            break

        # Detecção de feed esgotado (sem novos artigos renderizados)
        if novos_nesta_rodada == 0:
            consecutive_empty_scrolls += 1
            if consecutive_empty_scrolls >= max_empty_scrolls:
                logger.info(f"Feed esgotado: {max_empty_scrolls} scrolls consecutivos sem novos tweets.")
                break
        else:
            consecutive_empty_scrolls = 0

        page.mouse.wheel(0, 1500)
        if scroll_delay > 0:
            time.sleep(scroll_delay)

    return tweets_coletados, seen_texts

def coletar_tweets_vip(
    max_scrolls: int = DEFAULT_MAX_SCROLLS,
    headless: bool = True,
    scroll_delay: float = 1.5,
    max_consecutive_old: int = MAX_CONSECUTIVE_OLD_TWEETS,
    max_empty_scrolls: int = MAX_EMPTY_SCROLLS,
) -> SourceCollectionResult[Tweet]:
    """
    Coleta tweets recentes do feed Seguindo e dos perfis do Radar VIP com timeout global de 5 minutos.
    Retorna resultado puro em memória (SourceCollectionResult) sem persistência em disco.
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Coletando posts do X (Feed Seguindo / Following)...")
    logger.info(f"Data da execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    tweets_coletados: list[Tweet] = []
    seen_texts: set[str] = set()
    limite_tempo = datetime.now(timezone.utc) - timedelta(hours=48)
    successful_ops: list[str] = []
    failed_ops: list[str] = []
    last_error: str | None = None
    rate_limited: bool = False

    try:
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
                    return SourceCollectionResult(
                        source_name="twitter",
                        status=SourceStatus.FAILED,
                        items=(),
                        successful_operations=(),
                        failed_operations=("context",),
                        error_message=f"Erro ao abrir contexto do Chromium: {e}",
                    )

            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            carregar_cookies_se_existir(context)

            page = context.pages[0] if context.pages else context.new_page()

            logger.info("Acessando https://x.com/home ...")
            home_loaded = False
            try:
                page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45000)
                successful_ops.append("home")
                home_loaded = True
            except Exception as e:
                logger.warning(f"Aviso no carregamento inicial do X: {e}")
                failed_ops.append("home")
                last_error = f"Erro no carregamento inicial do X: {e}"
            time.sleep(3)

            current_url = getattr(page, "url", "")
            logger.info(f"Página acessada. URL: {current_url} | Título: {page.title()}")

            if current_url and ("login" in current_url or "onboarding" in current_url):
                logger.warning("A sessão ainda não está autenticada no X.")
                context.close()
                return SourceCollectionResult(
                    source_name="twitter",
                    status=SourceStatus.FAILED,
                    items=(),
                    successful_operations=(),
                    failed_operations=("auth",),
                    error_message="A sessão ainda não está autenticada no X.",
                )

            # 1. Coleta no Feed Principal
            if home_loaded:
                # Clica na aba Seguindo/Following se visível para garantir feed cronológico
                _selecionar_aba_seguindo(page)
                try:
                    feed_tweets, seen_texts = coletar_feed_principal(
                        page=page,
                        limite_tempo=limite_tempo,
                        start_time=start_time,
                        max_scrolls=max_scrolls,
                        max_consecutive_old=max_consecutive_old,
                        max_empty_scrolls=max_empty_scrolls,
                        scroll_delay=scroll_delay,
                        seen_texts=seen_texts,
                    )
                    tweets_coletados.extend(feed_tweets)
                    if time.time() - start_time > MAX_EXECUTION_SECONDS:
                        logger.warning("Timeout global de segurança de 5 minutos atingido no feed.")
                        failed_ops.append("feed:timeout")
                        last_error = "Timeout global de 5 minutos atingido no feed"
                    else:
                        successful_ops.append("feed")
                except Exception as e:
                    logger.warning(f"Aviso ao coletar feed principal do Twitter: {e}")
                    failed_ops.append("feed")
                    last_error = str(e)
                    if "rate limit" in str(e).lower() or "429" in str(e):
                        rate_limited = True
            else:
                logger.warning("Feed principal ignorado devido à falha de carregamento da página inicial.")
                failed_ops.append("feed")

            # 2. Coleta no Radar VIP (Perfis de Referência)
            vip_profiles = [
                ("mattpocockuk", "Matt Pocock"),
                ("svpino", "Santiago Valdarrama"),
                ("swyx", "Swyx / Latent Space"),
                ("karpathy", "Andrej Karpathy"),
                ("jxnlco", "Jason Liu"),
                ("chipro", "Chip Huyen")
            ]

            logger.info("\n--- COLETANDO RADAR VIP DE PERFIS ESPECÍFICOS ---")
            for i, (handle, nome_vip) in enumerate(vip_profiles):
                op_id = f"profile:{handle}"
                if time.time() - start_time > MAX_EXECUTION_SECONDS:
                    logger.warning(f"Timeout global atingido. Interrompendo coleta VIP em @{handle}.")
                    last_error = f"Timeout global de segurança ({MAX_EXECUTION_SECONDS}s) atingido durante Radar VIP"
                    for remaining_handle, _ in vip_profiles[i:]:
                        failed_ops.append(f"profile:{remaining_handle}")
                    break

                url_perfil = f"https://x.com/{handle}"
                logger.info(f"Acessando perfil VIP de {nome_vip} (@{handle})...")
                try:
                    page.goto(url_perfil, wait_until="domcontentloaded", timeout=25000)
                    time.sleep(2)
                    articles_vip = page.locator("article[data-testid='tweet']").all()[:5]
                    for art in articles_vip:
                        tweet_obj = _extrair_tweet(art, fallback_name=nome_vip, fallback_handle=f"@{handle}")
                        if not tweet_obj or tweet_obj.text in seen_texts:
                            continue

                        # Janela flexível de 4 dias para autores VIP
                        if tweet_obj.timestamp:
                            try:
                                tweet_dt = datetime.fromisoformat(tweet_obj.timestamp.replace("Z", "+00:00"))
                                if tweet_dt < (datetime.now(timezone.utc) - timedelta(days=4)):
                                    continue
                            except Exception:
                                pass

                        seen_texts.add(tweet_obj.text)
                        tweets_coletados.append(tweet_obj)
                    successful_ops.append(op_id)
                except Exception as e:
                    logger.warning(f"Aviso ao consultar perfil de @{handle}: {e}")
                    failed_ops.append(op_id)
                    last_error = str(e)
                    if "rate limit" in str(e).lower() or "429" in str(e):
                        rate_limited = True

            context.close()
    except Exception as e:
        logger.error(f"Erro fatal na execução do Playwright no coletor do Twitter: {e}")
        return SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.FAILED,
            items=(),
            successful_operations=(),
            failed_operations=("playwright",),
            error_message=str(e),
            rate_limited=rate_limited,
        )

    items_tuple = tuple(tweets_coletados)
    logger.info(f"Total de tweets coletados: {len(items_tuple)}")

    # Determinação rigorosa de status
    if len(failed_ops) == 0:
        status = SourceStatus.SUCCESS if len(items_tuple) > 0 else SourceStatus.EMPTY
        err_msg = None
    elif len(successful_ops) > 0:
        # Alguma operação obteve êxito, mas houve falhas parciais (ex: perfis VIP restantes ou timeout) -> PARTIAL
        status = SourceStatus.PARTIAL
        err_msg = last_error or "Falha parcial na coleta do Twitter"
    else:
        # Nenhuma operação obteve êxito -> FAILED
        status = SourceStatus.FAILED
        err_msg = last_error or "Nenhuma operação de coleta do Twitter obteve êxito"

    return SourceCollectionResult(
        source_name="twitter",
        status=status,
        items=items_tuple,
        successful_operations=tuple(successful_ops),
        failed_operations=tuple(failed_ops),
        error_message=err_msg,
        rate_limited=rate_limited,
    )

if __name__ == "__main__":
    is_headless = "--headed" not in sys.argv
    coletar_tweets_vip(headless=is_headless)
