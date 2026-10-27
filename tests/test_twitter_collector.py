import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.core.models import Tweet
from src.collectors.twitter import (
    _extrair_tweet,
    _selecionar_aba_seguindo,
    coletar_feed_principal,
    MAX_CONSECUTIVE_OLD_TWEETS,
    MAX_EMPTY_SCROLLS
)


def make_mock_article(
    text: str,
    timestamp: str = "",
    handle: str = "@user",
    author: str = "User",
    url_path: str = "/user/status/123",
    likes: str = "10",
    reposts: str = "2",
    replies: str = "1",
    views: str = "100",
    external_links: list[str] | None = None
) -> MagicMock:
    """Cria um mock hermético de elemento article do Playwright."""
    mock_art = MagicMock()

    # tweetText
    mock_text_el = MagicMock()
    mock_text_el.is_visible.return_value = bool(text)
    mock_text_el.inner_text.return_value = text

    # time
    mock_time_el = MagicMock()
    mock_time_el.is_visible.return_value = bool(timestamp)
    mock_time_el.get_attribute.return_value = timestamp

    # User-Name
    mock_user_name_el = MagicMock()
    mock_user_name_el.is_visible.return_value = True
    mock_user_name_el.inner_text.return_value = f"{author}\n{handle}"

    # link de status
    mock_link_el = MagicMock()
    mock_link_el.is_visible.return_value = bool(url_path)
    mock_link_el.get_attribute.return_value = url_path

    # links externos
    mock_ext_links = []
    if external_links:
        for link in external_links:
            link_mock = MagicMock()
            link_mock.get_attribute.return_value = link
            mock_ext_links.append(link_mock)

    def locator_side_effect(selector: str):
        loc = MagicMock()
        if "tweetText" in selector:
            loc.first = mock_text_el
            return loc
        elif selector == "time":
            loc.first = mock_time_el
            return loc
        elif "User-Name" in selector:
            loc.first = mock_user_name_el
            return loc
        elif "status/" in selector:
            loc.first = mock_link_el
            return loc
        elif "analytics" in selector:
            loc.first.is_visible.return_value = bool(views)
            loc.first.inner_text.return_value = views
            return loc
        elif "button[data-testid='like']" in selector:
            loc.first.is_visible.return_value = True
            loc.first.inner_text.return_value = likes
            return loc
        elif "button[data-testid='retweet']" in selector:
            loc.first.is_visible.return_value = True
            loc.first.inner_text.return_value = reposts
            return loc
        elif "button[data-testid='reply']" in selector:
            loc.first.is_visible.return_value = True
            loc.first.inner_text.return_value = replies
            return loc
        elif "target='_blank'" in selector:
            loc.all.return_value = mock_ext_links
            return loc
        return loc

    mock_art.locator.side_effect = locator_side_effect
    return mock_art


class TestTwitterCollector(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.limite_tempo = self.now - timedelta(hours=48)

    def _format_time(self, hours_ago: float) -> str:
        dt = self.now - timedelta(hours=hours_ago)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def test_extrair_tweet_preserves_url_and_metadata(self):
        """Valida que a extração preserva a URL absoluta, relativa e metadados."""
        # 1. URL relativa
        art_rel = make_mock_article(
            text="Tweet com link relativo",
            timestamp=self._format_time(1),
            url_path="/johndoe/status/987654321",
            likes="42",
            external_links=["https://t.co/abc123xyz"]
        )
        tweet_rel = _extrair_tweet(art_rel)
        self.assertIsNotNone(tweet_rel)
        self.assertEqual(tweet_rel.url, "https://x.com/johndoe/status/987654321")
        self.assertEqual(tweet_rel.likes, "42")
        self.assertEqual(tweet_rel.external_links, ["https://t.co/abc123xyz"])

        # 2. URL absoluta pré-existente
        art_abs = make_mock_article(
            text="Tweet com link absoluto",
            timestamp=self._format_time(2),
            url_path="https://x.com/janedoe/status/11223344",
        )
        tweet_abs = _extrair_tweet(art_abs)
        self.assertIsNotNone(tweet_abs)
        self.assertEqual(tweet_abs.url, "https://x.com/janedoe/status/11223344")

    def test_old_tweet_between_recent_tweets_is_skipped_and_collection_continues(self):
        """Cenário 1: Um tweet antigo (ex: retweet de 60h atrás) entre publicações recentes."""
        recent_1 = make_mock_article("Recente 1", timestamp=self._format_time(2), url_path="/u/status/1")
        old_between = make_mock_article("Antigo no meio", timestamp=self._format_time(60), url_path="/u/status/2")
        recent_2 = make_mock_article("Recente 2", timestamp=self._format_time(5), url_path="/u/status/3")

        mock_page = MagicMock()
        mock_page.locator("article[data-testid='tweet']").all.return_value = [
            recent_1, old_between, recent_2
        ]

        tweets, seen = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=1,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 2)
        self.assertEqual(tweets[0].text, "Recente 1")
        self.assertEqual(tweets[1].text, "Recente 2")
        self.assertNotIn("Antigo no meio", [t.text for t in tweets])
        self.assertIn("Antigo no meio", seen)

    def test_pinned_old_tweet_at_start_of_feed_is_ignored(self):
        """Cenário 2: Um tweet fixado antigo no início do feed não interrompe a coleta."""
        pinned_old = make_mock_article("Tweet fixado antigo", timestamp=self._format_time(240), url_path="/u/status/pin")
        recent_1 = make_mock_article("Recente 1", timestamp=self._format_time(1), url_path="/u/status/1")
        recent_2 = make_mock_article("Recente 2", timestamp=self._format_time(3), url_path="/u/status/2")

        mock_page = MagicMock()
        mock_page.locator("article[data-testid='tweet']").all.return_value = [
            pinned_old, recent_1, recent_2
        ]

        tweets, _ = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=1,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 2)
        self.assertEqual(tweets[0].text, "Recente 1")
        self.assertEqual(tweets[1].text, "Recente 2")

    def test_non_chronological_sequence_handled_properly(self):
        """Cenário 3: Sequência não-cronológica com múltiplos tweets fora de ordem."""
        t1 = make_mock_article("Recente 10h", timestamp=self._format_time(10), url_path="/u/status/1")
        t2 = make_mock_article("Antigo 52h", timestamp=self._format_time(52), url_path="/u/status/2")
        t3 = make_mock_article("Recente 5h", timestamp=self._format_time(5), url_path="/u/status/3")
        t4 = make_mock_article("Antigo 70h", timestamp=self._format_time(70), url_path="/u/status/4")
        t5 = make_mock_article("Recente 20h", timestamp=self._format_time(20), url_path="/u/status/5")

        mock_page = MagicMock()
        mock_page.locator("article[data-testid='tweet']").all.return_value = [t1, t2, t3, t4, t5]

        tweets, _ = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=1,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 3)
        self.assertEqual([t.text for t in tweets], ["Recente 10h", "Recente 5h", "Recente 20h"])

    def test_feed_genuinely_exhausted_stops_cleanly(self):
        """Cenário 4: Um feed realmente esgotado interrompe após MAX_EMPTY_SCROLLS."""
        t1 = make_mock_article("Recente único", timestamp=self._format_time(1), url_path="/u/status/1")

        mock_page = MagicMock()
        # Primeira rodada retorna t1; rodadas seguintes não retornam nenhum item novo
        mock_page.locator("article[data-testid='tweet']").all.side_effect = [
            [t1],
            [t1],  # já visto
            [t1],  # já visto
            [t1],  # já visto -> atinge MAX_EMPTY_SCROLLS=3
            [t1],
        ]

        tweets, _ = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=10,
            max_empty_scrolls=3,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 1)
        self.assertEqual(tweets[0].text, "Recente único")
        # Deve ter parado na 4ª rodada (1 inicial + 3 vazias consecutivas)
        self.assertEqual(mock_page.locator("article[data-testid='tweet']").all.call_count, 4)

    def test_feed_with_no_publications_stops_cleanly(self):
        """Cenário 5: Feed sem nenhuma publicação desde o início."""
        mock_page = MagicMock()
        mock_page.locator("article[data-testid='tweet']").all.return_value = []

        tweets, seen = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=10,
            max_empty_scrolls=3,
            scroll_delay=0.0
        )

        self.assertEqual(tweets, [])
        self.assertEqual(len(seen), 0)
        self.assertEqual(mock_page.locator("article[data-testid='tweet']").all.call_count, 3)

    def test_max_scroll_limit_enforced(self):
        """Cenário 6: Limite máximo de scrolls é estritamente respeitado em feed infinito."""
        mock_page = MagicMock()

        # Cada scroll retorna 1 tweet novo
        def dynamic_articles():
            idx = mock_page.locator("article[data-testid='tweet']").all.call_count
            return [make_mock_article(f"Tweet scroll {idx}", timestamp=self._format_time(1), url_path=f"/u/{idx}")]

        mock_page.locator("article[data-testid='tweet']").all.side_effect = dynamic_articles

        tweets, _ = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=5,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 5)
        self.assertEqual(mock_page.mouse.wheel.call_count, 5)

    def test_consecutive_old_tweets_boundary_terminates_loop(self):
        """Valida que o limite de tweets antigos consecutivos interrompe a coleta ao cruzar 48h."""
        recent_1 = make_mock_article("Recente 1", timestamp=self._format_time(1), url_path="/u/1")
        recent_2 = make_mock_article("Recente 2", timestamp=self._format_time(2), url_path="/u/2")

        # Gera 4 tweets antigos
        old_articles = [
            make_mock_article(f"Antigo {i}", timestamp=self._format_time(50 + i), url_path=f"/u/old_{i}")
            for i in range(4)
        ]

        mock_page = MagicMock()
        mock_page.locator("article[data-testid='tweet']").all.return_value = [
            recent_1, recent_2, *old_articles
        ]

        # Com max_consecutive_old=4, deve parar exatamente ao atingir o 4º tweet antigo
        tweets, _ = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=10,
            max_consecutive_old=4,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 2)
        self.assertEqual([t.text for t in tweets], ["Recente 1", "Recente 2"])

    def test_old_tweet_persisting_in_dom_across_scrolls_is_not_double_counted(self):
        """Valida que um mesmo tweet antigo mantido no DOM virtual não incrementa o contador repetidamente."""
        recent_1 = make_mock_article("Recente 1", timestamp=self._format_time(1), url_path="/u/1")
        old_pinned = make_mock_article("Antigo Fixo", timestamp=self._format_time(80), url_path="/u/pin")
        recent_2 = make_mock_article("Recente 2", timestamp=self._format_time(2), url_path="/u/2")
        old_item = make_mock_article("Antigo 1", timestamp=self._format_time(60), url_path="/u/old1")

        mock_page = MagicMock()
        # Scroll 1: Recente 1 e Antigo Fixo no DOM
        # Scroll 2: Antigo Fixo continua no DOM (virtualização), e Recente 2 aparece
        # Scroll 3: Antigo Fixo continua no DOM, e Antigo 1 aparece
        mock_page.locator("article[data-testid='tweet']").all.side_effect = [
            [recent_1, old_pinned],
            [old_pinned, recent_2],
            [old_pinned, old_item],
        ]

        # Com max_consecutive_old=2: se 'Antigo Fixo' fosse contado 2 vezes, quebraria prematuramente
        tweets, seen = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=3,
            max_consecutive_old=2,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 2)
        self.assertEqual([t.text for t in tweets], ["Recente 1", "Recente 2"])
        self.assertIn("Antigo Fixo", seen)
        self.assertIn("Antigo 1", seen)

    def test_async_loading_delayed_two_scrolls_resumes_collection(self):
        """Valida que atrasos no carregamento assíncrono (até 2 scrolls vazios) não abortam a coleta se novos dados chegam."""
        recent_1 = make_mock_article("Recente 1", timestamp=self._format_time(1), url_path="/u/1")
        recent_2 = make_mock_article("Recente 2", timestamp=self._format_time(3), url_path="/u/2")

        mock_page = MagicMock()
        mock_page.locator("article[data-testid='tweet']").all.side_effect = [
            [recent_1],
            [recent_1],  # 1º scroll vazio (DOM inalterado aguardando fetch de rede)
            [recent_1],  # 2º scroll vazio
            [recent_1, recent_2],  # 3º scroll: novo lote renderizado assincronamente!
        ]

        tweets, _ = coletar_feed_principal(
            page=mock_page,
            limite_tempo=self.limite_tempo,
            max_scrolls=4,
            max_empty_scrolls=3,
            scroll_delay=0.0
        )

        self.assertEqual(len(tweets), 2)
        self.assertEqual([t.text for t in tweets], ["Recente 1", "Recente 2"])

    def test_global_timeout_terminates_feed_collection(self):
        """Valida que o timeout global de 300 segundos interrompe a coleta mesmo antes do limite de scrolls."""
        recent_1 = make_mock_article("Recente 1", timestamp=self._format_time(1), url_path="/u/1")
        mock_page = MagicMock()
        mock_page.locator("article[data-testid='tweet']").all.return_value = [recent_1]

        # Simula start_time de 301 segundos atrás
        past_start_time = 1000.0
        with patch("src.collectors.twitter.time.time", side_effect=[1305.0]):
            tweets, _ = coletar_feed_principal(
                page=mock_page,
                limite_tempo=self.limite_tempo,
                start_time=past_start_time,
                max_scrolls=10,
                scroll_delay=0.0
            )

        self.assertEqual(tweets, [])
        mock_page.mouse.wheel.assert_not_called()

    def test_selecionar_aba_seguindo_portuguese(self):
        """Valida a seleção da aba 'Seguindo' em interface configurada em Português."""
        mock_page = MagicMock()
        mock_tab = MagicMock()
        mock_tab.is_visible.return_value = True

        mock_page.locator.return_value.first = mock_tab

        with patch("time.sleep"):
            success = _selecionar_aba_seguindo(mock_page)

        self.assertTrue(success)
        mock_tab.click.assert_called_once()

    def test_selecionar_aba_following_english(self):
        """Valida a seleção da aba 'Following' em interface configurada em Inglês."""
        mock_page = MagicMock()
        mock_tab = MagicMock()
        mock_tab.is_visible.return_value = True

        # Locator de Seguindo/Following é chamado
        mock_page.locator.return_value.first = mock_tab

        with patch("time.sleep"):
            success = _selecionar_aba_seguindo(mock_page)

        self.assertTrue(success)
        mock_tab.click.assert_called_once()

    def test_selecionar_aba_seguindo_not_visible(self):
        """Valida comportamento resiliente quando a aba não está visível."""
        mock_page = MagicMock()
        mock_tab = MagicMock()
        mock_tab.is_visible.return_value = False

        mock_page.locator.return_value.first = mock_tab

        success = _selecionar_aba_seguindo(mock_page)
        self.assertFalse(success)
        mock_tab.click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
