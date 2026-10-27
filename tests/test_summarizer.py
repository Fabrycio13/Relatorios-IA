import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.models import Tweet, GitHubRepo, ResearchPaper, DailyIngestionBatch
from src.processors.ai_summarizer import (
    gerar_resumo_ia,
    montar_payload_tweets_xml,
    _anexar_secao_github,
    _anexar_secao_papers,
    _anexar_secao_takeaway,
    remover_travessoes
)
from src.processors.prompts import get_prompt_resumo_ia


class TestAISummarizer(unittest.TestCase):

    def setUp(self):
        self.sample_tweet = Tweet(
            author_name="Matt Pocock",
            author_handle="@mattpocockuk",
            timestamp="2026-10-26T12:00:00Z",
            text="Autonomous coding agents are reshaping software development.",
            url="https://x.com/mattpocockuk/status/123",
            likes="2500",
            reposts="340",
            replies="80",
            views="120000",
            external_links=["https://github.com/example/agent"]
        )
        self.sample_repo = GitHubRepo(
            name="blender-mcp",
            full_name="org/blender-mcp",
            stars=1200,
            description="Blender MCP Addon for AI Agents",
            language="Python",
            url="https://github.com/org/blender-mcp",
            topics=["mcp", "ai-agents"]
        )
        self.sample_paper = ResearchPaper(
            title="Reasoning Agents at Scale",
            arxiv_id="2610.99999",
            summary="A comprehensive survey on reasoning capabilities in coding agents.",
            authors=["Alice Researcher", "Bob Engineer"],
            upvotes=55,
            url="https://huggingface.co/papers/2610.99999"
        )
        self.sample_batch = DailyIngestionBatch(
            tweets=[self.sample_tweet],
            repos=[self.sample_repo],
            papers=[self.sample_paper],
            collected_at="2026-10-27T08:00:00"
        )

    def test_remover_travessoes(self):
        texto = "**Repo — Subtitle:** Descrição — com travessão solto."
        limpo = remover_travessoes(texto)
        self.assertNotIn(" — ", limpo)
        self.assertIn("**Repo (Subtitle):**", limpo)

    @patch("src.processors.ai_summarizer._executar_chamada_openai")
    def test_anexar_secao_github_com_entidades_em_memoria(self, mock_openai):
        mock_openai.return_value = "### Blender MCP\nRepositório focado em MCP para Blender."
        base_md = "# Relatório Base\n"
        resultado = _anexar_secao_github(base_md, "test-key", repos=[self.sample_repo])

        self.assertIn("## 🔥 GitHub Trending: Repositórios de IA em Alta no Dia", resultado)
        self.assertIn("Blender MCP", resultado)
        mock_openai.assert_called_once()

    @patch("src.processors.ai_summarizer._executar_chamada_openai")
    def test_anexar_secao_papers_com_entidades_em_memoria(self, mock_openai):
        mock_openai.return_value = "### Reasoning Agents\nPesquisa sobre agentes de raciocínio."
        base_md = "# Relatório Base\n"
        resultado = _anexar_secao_papers(base_md, "test-key", papers=[self.sample_paper])

        self.assertIn("## 📄 Papers em Destaque: Pesquisa & Estado da Arte (Hugging Face / ArXiv)", resultado)
        self.assertIn("Reasoning Agents", resultado)
        mock_openai.assert_called_once()

    @patch("src.processors.ai_summarizer._executar_chamada_openai")
    def test_gerar_resumo_ia_com_batch_em_memoria_sem_ler_disco(self, mock_openai):
        mock_openai.side_effect = [
            "# Resumo Principal da Síntese\nPrincipais avanços de hoje.",
            "### GitHub Destaques",
            "### Papers Destaques",
            "### Takeaway de Engenharia"
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "test_report.md"

            # Executa a síntese diretamente do lote tipado em memória
            resultado = gerar_resumo_ia(batch=self.sample_batch, output_path=output_file)

            self.assertIsNotNone(resultado)
            self.assertEqual(resultado, output_file)
            self.assertTrue(output_file.exists())

            conteudo = output_file.read_text(encoding="utf-8")
            self.assertIn("Resumo Principal da Síntese", conteudo)
            self.assertIn("GitHub Trending", conteudo)
            self.assertIn("Papers em Destaque", conteudo)
            self.assertIn("Takeaway Prático de Engenharia", conteudo)

    def test_gerar_resumo_ia_lote_totalmente_vazio_retorna_none(self):
        empty_batch = DailyIngestionBatch(tweets=[], repos=[], papers=[])
        self.assertTrue(empty_batch.is_empty())
        resultado = gerar_resumo_ia(batch=empty_batch)
        self.assertIsNone(resultado)

    @patch("src.processors.ai_summarizer._executar_chamada_openai")
    def test_gerar_resumo_ia_sem_tweets_mas_com_repos_prossegue(self, mock_openai):
        mock_openai.return_value = "### Destaque GitHub"
        batch_sem_tweets = DailyIngestionBatch(
            tweets=[],
            repos=[self.sample_repo],
            papers=[self.sample_paper]
        )
        self.assertFalse(batch_sem_tweets.is_empty())

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "test_no_tweets.md"
            resultado = gerar_resumo_ia(batch=batch_sem_tweets, output_path=output_file)

            self.assertIsNotNone(resultado)
            self.assertTrue(output_file.exists())
            conteudo = output_file.read_text(encoding="utf-8")
            self.assertIn("Nenhum post recente capturado no radar do X", conteudo)
            self.assertIn("GitHub Trending", conteudo)

    @patch("src.processors.ai_summarizer._executar_chamada_openai")
    @patch("src.core.models.DailyIngestionBatch.load_snapshot")
    def test_gerar_resumo_ia_fallback_sem_batch_carrega_snapshot(self, mock_load, mock_openai):
        mock_load.return_value = self.sample_batch
        mock_openai.return_value = "# Síntese Carregada do Snapshot"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "test_report_snapshot.md"

            resultado = gerar_resumo_ia(batch=None, output_path=output_file)

            mock_load.assert_called_once()
            self.assertIsNotNone(resultado)
            self.assertTrue(output_file.exists())

    def test_montar_payload_tweets_xml_preserva_urls_e_external_links(self):
        """Valida que o payload XML preserva a URL permanente do post e múltiplos links externos."""
        tweet1 = Tweet(
            author_name="Jason Liu",
            author_handle="@jxnlco",
            timestamp="2026-10-27T07:00:00Z",
            text="Novo benchmark para coding agents com tool use.",
            url="https://x.com/jxnlco/status/1982736173070442654",
            likes="350",
            reposts="45",
            replies="12",
            views="25000",
            external_links=["https://t.co/abc1", "https://t.co/def2"]
        )
        xml = montar_payload_tweets_xml([tweet1])

        self.assertIn("<tweets_feed>", xml)
        self.assertIn("</tweets_feed>", xml)
        self.assertIn('<tweet_item id="1" author="Jason Liu (@jxnlco)" metrics="Likes: 350, Reposts: 45">', xml)
        self.assertIn("<url>https://x.com/jxnlco/status/1982736173070442654</url>", xml)
        self.assertIn("<external_links>https://t.co/abc1 | https://t.co/def2</external_links>", xml)
        self.assertIn("<content>Novo benchmark para coding agents com tool use.</content>", xml)

    def test_montar_payload_tweets_xml_trata_external_links_vazio_corretamente(self):
        """Valida que quando external_links é vazio, o campo é preenchido com 'Nenhum' sem falhas."""
        tweet = Tweet(
            author_name="Swyx",
            author_handle="@swyx",
            timestamp="2026-10-27T06:00:00Z",
            text="Reflexão rápida sobre modelos de raciocínio.",
            url="https://x.com/swyx/status/99887766",
            likes="120",
            reposts="10",
            replies="5",
            views="10000",
            external_links=[]
        )
        xml = montar_payload_tweets_xml([tweet])

        self.assertIn("<url>https://x.com/swyx/status/99887766</url>", xml)
        self.assertIn("<external_links>Nenhum</external_links>", xml)

    def test_montar_payload_tweets_xml_trata_url_vazia_sem_inventar_dados(self):
        """Valida que quando url é vazia, a tag permanece vazia sem placeholders fictícios."""
        tweet = Tweet(
            author_name="Desconhecido",
            author_handle="@anon",
            timestamp="2026-10-27T05:00:00Z",
            text="Tweet sem URL de status.",
            url="",
            likes="0",
            reposts="0",
            replies="0",
            views="0",
            external_links=[]
        )
        xml = montar_payload_tweets_xml([tweet])

        self.assertIn("<url></url>", xml)
        self.assertNotIn("https://x.com", xml)

    def test_prompt_resumo_ia_solicita_rastreabilidade_post_obrigatorio(self):
        """Valida que o prompt de curadoria instrui imperativamente a inclusão de ([Post](url)) e proíbe links fictícios."""
        prompt = get_prompt_resumo_ia("27/10/2026", "26/10/2026")

        self.assertIn("([Post](url))", prompt)
        self.assertIn("<url>", prompt)
        self.assertIn("<external_links>", prompt)
        self.assertIn("NUNCA invente URLs", prompt)
        self.assertIn("RASTREABILIDADE", prompt)

    @patch("src.processors.ai_summarizer._executar_chamada_openai")
    def test_gerar_resumo_ia_transmite_payload_completo_para_openai(self, mock_openai):
        """Valida que gerar_resumo_ia repassa URLs e links externos no payload para a chamada da OpenAI."""
        mock_openai.return_value = "## 📌 Destaques\n* Notícia com ([Post](https://x.com/mattpocockuk/status/123))"

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "test_report_links.md"
            gerar_resumo_ia(batch=self.sample_batch, output_path=output_file)

            # Verifica que a primeira chamada (resumo do feed) recebeu o XML com a URL do tweet
            first_call_args = mock_openai.call_args_list[0]
            payload_enviado = first_call_args[0][1]  # payload dict enviado à OpenAI
            messages = payload_enviado["messages"]
            user_content = messages[1]["content"]

            self.assertIn("<url>https://x.com/mattpocockuk/status/123</url>", user_content)
            self.assertIn("<external_links>https://github.com/example/agent</external_links>", user_content)


if __name__ == "__main__":
    unittest.main()
