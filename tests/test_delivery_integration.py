import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import main
from src.core.models import DailyIngestionBatch, Tweet, GitHubRepo, ResearchPaper
from src.delivery.base import DeliveryChannel, EmailDeliveryChannel, FilePreviewDeliveryChannel


class TestDeliveryIntegration(unittest.TestCase):

    def setUp(self):
        self.sample_tweet = Tweet(
            author_name="Test Author",
            author_handle="@testauthor",
            timestamp="2026-10-27T10:00:00Z",
            text="Testing delivery channel integration.",
            url="https://x.com/testauthor/status/123",
            likes="10",
            reposts="2",
            replies="1",
            views="100",
            external_links=[]
        )
        self.sample_repo = GitHubRepo(
            name="test-repo",
            full_name="org/test-repo",
            stars=500,
            description="Integration test repo",
            language="Python",
            url="https://github.com/org/test-repo",
            topics=["testing"]
        )
        self.sample_paper = ResearchPaper(
            title="Integration Paper",
            arxiv_id="2610.12345",
            summary="Testing paper delivery.",
            authors=["Bob"],
            upvotes=20,
            url="https://huggingface.co/papers/2610.12345"
        )
        self.sample_batch = DailyIngestionBatch(
            tweets=[self.sample_tweet],
            repos=[self.sample_repo],
            papers=[self.sample_paper]
        )

    def test_channels_implement_protocol(self):
        """Valida que ambos os adaptadores implementam a assinatura do protocolo DeliveryChannel."""
        self.assertTrue(isinstance(EmailDeliveryChannel(), DeliveryChannel))
        self.assertTrue(isinstance(FilePreviewDeliveryChannel(), DeliveryChannel))

    @patch("src.delivery.base.webbrowser.open")
    @patch("smtplib.SMTP_SSL")
    @patch("smtplib.SMTP")
    @patch("main.notificar_windows")
    @patch("main.registrar_envio_sucesso")
    @patch("main.aguardar_conexao_internet", return_value=True)
    def test_e2e_preview_pipeline_generates_html_and_never_touches_smtp_or_lock(
        self,
        mock_internet,
        mock_registrar_sucesso,
        mock_notificar,
        mock_smtp_regular,
        mock_smtp_ssl,
        mock_browser
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            preview_dest = tmp_path / "preview.html"
            dummy_report = tmp_path / "Resumo_IA_2026-10-27.md"
            dummy_report.write_text(
                "# Relatório E2E\n## Repositórios em Alta\n- [Test Repo](https://github.com/org/test-repo)",
                encoding="utf-8"
            )

            with patch("main.IngestionPipeline.run", return_value=self.sample_batch), \
                 patch("main.gerar_resumo_ia", return_value=dummy_report), \
                 patch("src.delivery.base.REPORTS_DIR", tmp_path):

                test_args = ["main.py", "--preview"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                # 1. Garante que o preview.html foi gerado fisicamente
                self.assertTrue(preview_dest.exists(), "O arquivo preview.html deveria ter sido gerado.")
                html_content = preview_dest.read_text(encoding="utf-8")
                self.assertIn("<!DOCTYPE html>", html_content)
                self.assertIn("Test Repo", html_content)

                # 2. Garante abertura no navegador
                mock_browser.assert_called_once_with(preview_dest.resolve().as_uri())

                # 3. Garante ZERO conexões SMTP
                mock_smtp_ssl.assert_not_called()
                mock_smtp_regular.assert_not_called()

                # 4. Garante que a trava antirrepetição NUNCA é registrada
                mock_registrar_sucesso.assert_not_called()

    @patch("src.delivery.base.webbrowser.open")
    @patch("smtplib.SMTP_SSL")
    @patch("main.notificar_windows")
    @patch("main.registrar_envio_sucesso")
    def test_e2e_step_email_preview_does_not_call_smtp(
        self,
        mock_registrar_sucesso,
        mock_notificar,
        mock_smtp_ssl,
        mock_browser
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            preview_dest = tmp_path / "preview.html"
            dummy_report = tmp_path / "Resumo_IA_2026-10-27.md"
            dummy_report.write_text("# Relatório Passo Email", encoding="utf-8")

            with patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("src.delivery.base.REPORTS_DIR", tmp_path):

                test_args = ["main.py", "--step", "email", "--preview"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                self.assertTrue(preview_dest.exists())
                mock_smtp_ssl.assert_not_called()
                mock_registrar_sucesso.assert_not_called()

    @patch("main.registrar_envio_sucesso")
    @patch("main.notificar_windows")
    @patch("smtplib.SMTP_SSL")
    def test_e2e_step_email_production_uses_smtp_ssl(
        self,
        mock_smtp_ssl,
        mock_notificar,
        mock_registrar_sucesso
    ):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_report = Path(tmp_dir) / "Resumo_IA_2026-10-27.md"
            dummy_report.write_text("# Relatório Produção", encoding="utf-8")

            with patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("src.delivery.base.config.get_email_credentials", return_value=("sender@gmail.com", "secret123", "dest@domain.com")):

                test_args = ["main.py", "--step", "email", "--to", "custom@domain.com"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                # Verifica chamada ao servidor SMTP SSL na porta 465
                mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465, timeout=20)
                mock_server.login.assert_called_once_with("sender@gmail.com", "secret123")
                mock_server.sendmail.assert_called_once()
                # Verifica destinatário correto no envio
                call_args = mock_server.sendmail.call_args[0]
                self.assertEqual(call_args[0], "sender@gmail.com")
                self.assertEqual(call_args[1], ["custom@domain.com"])


if __name__ == "__main__":
    unittest.main()
