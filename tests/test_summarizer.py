import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.models import Tweet, GitHubRepo, ResearchPaper, DailyIngestionBatch
from src.processors.ai_summarizer import (
    gerar_resumo_ia,
    _anexar_secao_github,
    _anexar_secao_papers,
    _anexar_secao_takeaway,
    remover_travessoes
)


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


if __name__ == "__main__":
    unittest.main()
