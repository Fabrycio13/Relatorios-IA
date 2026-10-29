import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import main
from src.core.config import DATA_DIR
from src.core.models import Tweet, GitHubRepo, ResearchPaper, DailyIngestionBatch


class TestMainIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp_dir_base = tempfile.TemporaryDirectory()
        self.mock_status_file = Path(self.tmp_dir_base.name) / "ultimo_envio.txt"
        self.status_file_patch = patch("main.STATUS_FILE", self.mock_status_file)
        self.status_file_patch.start()

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
            external_links=[]
        )
        self.sample_repo = GitHubRepo(
            name="blender-mcp",
            full_name="org/blender-mcp",
            stars=1200,
            description="Blender MCP Addon for AI Agents",
            language="Python",
            url="https://github.com/org/blender-mcp",
            topics=["mcp"]
        )
        self.sample_paper = ResearchPaper(
            title="Reasoning Agents at Scale",
            arxiv_id="2610.99999",
            summary="A comprehensive survey on reasoning capabilities in coding agents.",
            authors=["Alice"],
            upvotes=55,
            url="https://huggingface.co/papers/2610.99999"
        )
        self.sample_batch = DailyIngestionBatch(
            tweets=[self.sample_tweet],
            repos=[self.sample_repo],
            papers=[self.sample_paper],
            collected_at="2026-10-27T08:00:00"
        )

    def tearDown(self):
        self.status_file_patch.stop()
        self.tmp_dir_base.cleanup()

    @patch("main.confirmar_banner_utilizado")
    @patch("main.registrar_envio_sucesso")
    @patch("main.notificar_windows")
    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.despachar_relatorio", return_value=True)
    @patch("main.gerar_resumo_ia", return_value=Path("reports/test.md"))
    @patch("main.IngestionPipeline.run")
    def test_main_all_delegates_to_pipeline_and_passes_batch_to_summarizer(
        self,
        mock_pipeline_run,
        mock_gerar_resumo,
        mock_despachar,
        mock_internet,
        mock_notificar,
        mock_registrar_sucesso,
        mock_confirmar_banner
    ):
        mock_pipeline_run.return_value = self.sample_batch

        test_args = ["main.py", "--force"]
        with patch.object(sys, "argv", test_args):
            main.main()

        # 1. Valida delegação ao IngestionPipeline com target "all"
        mock_pipeline_run.assert_called_once_with(target_source="all")

        # 2. Valida que gerar_resumo_ia recebeu o lote retornado
        mock_gerar_resumo.assert_called_once_with(batch=self.sample_batch)

        # 3. Valida despacho via EmailDeliveryChannel e confirmação de envio
        mock_despachar.assert_called_once()
        channel_used = mock_despachar.call_args.kwargs.get("channel") or mock_despachar.call_args[1].get("channel")
        from src.delivery.base import EmailDeliveryChannel
        self.assertIsInstance(channel_used, EmailDeliveryChannel)
        mock_registrar_sucesso.assert_called_once()
        mock_confirmar_banner.assert_called_once()

    @patch("main.registrar_envio_sucesso")
    @patch("main.notificar_windows")
    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.despachar_relatorio", return_value=True)
    @patch("main.gerar_resumo_ia", return_value=Path("reports/test.md"))
    @patch("main.IngestionPipeline.run")
    def test_main_preview_uses_file_preview_channel_and_never_registers_success(
        self,
        mock_pipeline_run,
        mock_gerar_resumo,
        mock_despachar,
        mock_internet,
        mock_notificar,
        mock_registrar_sucesso
    ):
        mock_pipeline_run.return_value = self.sample_batch

        test_args = ["main.py", "--preview"]
        with patch.object(sys, "argv", test_args):
            main.main()

        # Valida que despachar_relatorio foi chamado com FilePreviewDeliveryChannel
        mock_despachar.assert_called_once()
        channel_used = mock_despachar.call_args.kwargs.get("channel") or mock_despachar.call_args[1].get("channel")
        from src.delivery.base import FilePreviewDeliveryChannel
        self.assertIsInstance(channel_used, FilePreviewDeliveryChannel)

        # Valida que a trava antirrepetição NUNCA foi chamada em modo preview
        mock_registrar_sucesso.assert_not_called()

        # Valida notificação toast de preview
        mock_notificar.assert_any_call("👁️ Diário de IA: Preview", "Prévia do Diário de IA gerada no navegador.")

    @patch("main.registrar_envio_sucesso")
    @patch("main.notificar_windows")
    @patch("main.despachar_relatorio", return_value=True)
    @patch("src.core.config.config.obter_ultimo_relatorio", return_value=Path("reports/ultimo.md"))
    def test_main_email_step_with_preview(
        self,
        mock_obter_ultimo,
        mock_despachar,
        mock_notificar,
        mock_registrar_sucesso
    ):
        test_args = ["main.py", "--step", "email", "--preview"]
        with patch.object(sys, "argv", test_args):
            main.main()

        mock_despachar.assert_called_once()
        channel_used = mock_despachar.call_args.kwargs.get("channel") or mock_despachar.call_args[1].get("channel")
        from src.delivery.base import FilePreviewDeliveryChannel
        self.assertIsInstance(channel_used, FilePreviewDeliveryChannel)
        mock_registrar_sucesso.assert_not_called()

    @patch("main.notificar_windows")
    @patch("main.gerar_resumo_ia", return_value=Path("reports/test.md"))
    @patch("main.IngestionPipeline.run")
    def test_main_summarize_step_skips_pipeline_and_passes_none_batch(
        self,
        mock_pipeline_run,
        mock_gerar_resumo,
        mock_notificar
    ):
        test_args = ["main.py", "--step", "summarize"]
        with patch.object(sys, "argv", test_args):
            main.main()

        mock_pipeline_run.assert_not_called()
        mock_gerar_resumo.assert_called_once_with(batch=None)

    @patch("main.notificar_windows")
    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.gerar_resumo_ia")
    @patch("main.IngestionPipeline.run")
    def test_main_collect_steps_delegate_to_pipeline_and_skip_summary(
        self,
        mock_pipeline_run,
        mock_gerar_resumo,
        mock_internet,
        mock_notificar
    ):
        mock_pipeline_run.return_value = self.sample_batch

        for step in ["collect", "collect-twitter", "collect-github", "collect-papers"]:
            mock_pipeline_run.reset_mock()
            mock_gerar_resumo.reset_mock()

            test_args = ["main.py", "--step", step]
            with patch.object(sys, "argv", test_args):
                main.main()

            mock_pipeline_run.assert_called_once_with(target_source=step)
            mock_gerar_resumo.assert_not_called()

    @patch("main.notificar_windows")
    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.IngestionPipeline.run")
    def test_main_exclusive_collect_step_failure_aborts(self, mock_pipeline_run, mock_internet, mock_notificar):
        # Batch vazio para o passo exclusivo collect-github
        empty_batch = DailyIngestionBatch(tweets=[], repos=[], papers=[])
        mock_pipeline_run.return_value = empty_batch

        test_args = ["main.py", "--step", "collect-github"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
