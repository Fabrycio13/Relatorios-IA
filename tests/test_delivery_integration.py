import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import main
from src.core.models import DailyIngestionBatch, Tweet, GitHubRepo, ResearchPaper
from src.delivery.base import DeliveryChannel, EmailDeliveryChannel, FilePreviewDeliveryChannel


class TestDeliveryIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp_dir_base = tempfile.TemporaryDirectory()
        self.mock_status_file = Path(self.tmp_dir_base.name) / "ultimo_envio.txt"
        self.status_file_patch = patch("main.STATUS_FILE", self.mock_status_file)
        self.status_file_patch.start()

        self.mock_data_dir = Path(self.tmp_dir_base.name)
        self.data_dir_patch = patch("src.delivery.banner_selector.DATA_DIR", self.mock_data_dir)
        self.data_dir_patch.start()

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

    def tearDown(self):
        self.status_file_patch.stop()
        self.data_dir_patch.stop()
        self.tmp_dir_base.cleanup()

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
                 patch("src.delivery.base.REPORTS_DIR", tmp_path), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"), \
                 patch("src.delivery.banner_selector.DATA_DIR", tmp_path):

                test_args = ["main.py", "--preview"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                # 1. Garante que o preview.html foi gerado fisicamente
                self.assertTrue(preview_dest.exists(), "O arquivo preview.html deveria ter sido gerado.")
                html_content = preview_dest.read_text(encoding="utf-8")
                self.assertIn("<!DOCTYPE html>", html_content)
                self.assertIn("Test Repo", html_content)

                # Valida presença do link HD, rel noopener, title dinâmico e alt no banner
                self.assertIn('class="newspaper-photo"', html_content)
                self.assertIn('target="_blank"', html_content)
                self.assertIn('rel="noopener noreferrer"', html_content)
                self.assertIn('title="', html_content)
                self.assertIn('alt="Arte da Edição:', html_content)

                # 2. Garante abertura no navegador
                mock_browser.assert_called_once_with(preview_dest.resolve().as_uri())

                # 3. Garante ZERO conexões SMTP
                mock_smtp_ssl.assert_not_called()
                mock_smtp_regular.assert_not_called()

                # 4. Garante que a trava antirrepetição e histórico NUNCA são gravados em preview
                mock_registrar_sucesso.assert_not_called()
                self.assertFalse((tmp_path / "historico_banners.json").exists())

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
                 patch("src.delivery.base.REPORTS_DIR", tmp_path), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"), \
                 patch("src.delivery.banner_selector.DATA_DIR", tmp_path):

                test_args = ["main.py", "--step", "email", "--preview"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                self.assertTrue(preview_dest.exists())
                html_content = preview_dest.read_text(encoding="utf-8")
                self.assertIn('class="newspaper-photo"', html_content)
                self.assertIn('rel="noopener noreferrer"', html_content)
                self.assertIn('alt="Arte da Edição:', html_content)
                mock_smtp_ssl.assert_not_called()
                mock_registrar_sucesso.assert_not_called()
                self.assertFalse((tmp_path / "historico_banners.json").exists())

    @patch("main.confirmar_banner_utilizado")
    @patch("main.registrar_envio_sucesso")
    @patch("main.notificar_windows")
    @patch("smtplib.SMTP_SSL")
    def test_e2e_step_email_production_uses_smtp_ssl(
        self,
        mock_smtp_ssl,
        mock_notificar,
        mock_registrar_sucesso,
        mock_confirmar_banner
    ):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dummy_report = Path(tmp_dir) / "Resumo_IA_2026-10-27.md"
            dummy_report.write_text("# Relatório Produção", encoding="utf-8")

            with patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("src.delivery.base.config.get_email_credentials", return_value=("sender@gmail.com", "secret123", "dest@domain.com")), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"):

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
                mock_confirmar_banner.assert_called_once()

    @patch("main.notificar_windows")
    @patch("smtplib.SMTP_SSL")
    def test_envio_smtp_sucesso_confirma_historico_banner(
        self,
        mock_smtp_ssl,
        mock_notificar
    ):
        """Valida que o envio SMTP bem-sucedido invoca confirmar_banner_utilizado e atualiza o histórico."""
        import json
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dummy_report = tmp_path / "Resumo_IA_2026-10-29.md"
            dummy_report.write_text("# Relatório Produção", encoding="utf-8")
            historico_path = tmp_path / "historico_banners.json"

            with patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("src.delivery.base.config.get_email_credentials", return_value=("sender@gmail.com", "secret123", "dest@domain.com")), \
                 patch("src.delivery.banner_selector.DATA_DIR", tmp_path), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"):

                test_args = ["main.py", "--step", "email", "--force"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                # Verifica que historico_banners.json foi criado após o envio com sucesso
                self.assertTrue(historico_path.exists())
                dados = json.loads(historico_path.read_text(encoding="utf-8"))
                hoje_str = datetime.now().strftime("%Y-%m-%d")
                self.assertIn(hoje_str, dados["ultimo_envio_por_data"])

    @patch("main.notificar_windows")
    @patch("smtplib.SMTP_SSL")
    def test_falha_envio_smtp_nao_confirma_historico_banner(
        self,
        mock_smtp_ssl,
        mock_notificar
    ):
        """Valida que falha no transporte SMTP NÃO confirma nem queima imagem no histórico."""
        mock_smtp_ssl.side_effect = Exception("Falha de conexão SMTP simulada")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dummy_report = tmp_path / "Resumo_IA_2026-10-29.md"
            dummy_report.write_text("# Relatório Produção", encoding="utf-8")
            historico_path = tmp_path / "historico_banners.json"

            with patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("src.delivery.base.config.get_email_credentials", return_value=("sender@gmail.com", "secret123", "dest@domain.com")), \
                 patch("src.delivery.banner_selector.DATA_DIR", tmp_path), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"):

                test_args = ["main.py", "--step", "email", "--force"]
                with patch.object(sys, "argv", test_args):
                    with self.assertRaises(SystemExit) as cm:
                        main.main()
                    self.assertEqual(cm.exception.code, 1)

                # Garante que historico_banners.json NÃO foi criado
                self.assertFalse(historico_path.exists())

    def test_concorrencia_pipeline_bloqueia_segundo_processo(self):
        """Valida que uma segunda execução concorrente do pipeline é bloqueada e encerra com código 0."""
        from src.core.lock import adquirir_trava_pipeline

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            lock_path = tmp_path / "ultimo_envio.lock"

            # Primeiro processo adquire a trava exclusiva
            with adquirir_trava_pipeline(lock_path):
                # Segundo processo tenta rodar main() com a trava já ocupada
                with patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"):
                    test_args = ["main.py", "--step", "email", "--force"]
                    with patch.object(sys, "argv", test_args):
                        with self.assertRaises(SystemExit) as cm:
                            main.main()
                        # Código 0: encerramento silencioso seguro para agendador
                        self.assertEqual(cm.exception.code, 0)

    def test_status_flag_nao_adquire_trava_e_executa_com_lock_ocupado(self):
        """Valida que a flag --status pode ser consultada mesmo enquanto outro processo detém a trava."""
        from src.core.lock import adquirir_trava_pipeline

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            lock_path = tmp_path / "ultimo_envio.lock"
            status_path = tmp_path / "ultimo_envio.txt"
            status_path.write_text("2026-10-29", encoding="utf-8")

            with adquirir_trava_pipeline(lock_path):
                with patch("main.STATUS_FILE", status_path):
                    test_args = ["main.py", "--status"]
                    with patch.object(sys, "argv", test_args):
                        with self.assertRaises(SystemExit) as cm:
                            main.main()
                        self.assertEqual(cm.exception.code, 0)

    @patch("main.executar_healthcheck", return_value=True)
    def test_check_auth_flag_nao_adquire_trava_e_executa_com_lock_ocupado(self, mock_healthcheck):
        """Valida que a flag --check-auth executa sem bloqueio mesmo com a trava ocupada."""
        from src.core.lock import adquirir_trava_pipeline

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            lock_path = tmp_path / "ultimo_envio.lock"

            with adquirir_trava_pipeline(lock_path):
                with patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"):
                    test_args = ["main.py", "--check-auth"]
                    with patch.object(sys, "argv", test_args):
                        with self.assertRaises(SystemExit) as cm:
                            main.main()
                        self.assertEqual(cm.exception.code, 0)
                        mock_healthcheck.assert_called_once()

    def test_trava_pipeline_liberada_apos_sys_exit_em_encerramento_antecipado(self):
        """Valida que saídas com sys.exit liberam a trava permitindo nova execução imediata."""
        from src.core.lock import adquirir_trava_pipeline

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            lock_path = tmp_path / "ultimo_envio.lock"
            status_path = tmp_path / "ultimo_envio.txt"
            status_path.write_text("2026-10-29", encoding="utf-8")

            # Executa main.py sem --force quando já foi enviado hoje -> dispara sys.exit(0)
            with patch("main.STATUS_FILE", status_path):
                test_args = ["main.py", "--step", "all"]
                with patch.object(sys, "argv", test_args):
                    with self.assertRaises(SystemExit) as cm:
                        main.main()
                    self.assertEqual(cm.exception.code, 0)

            # Verifica que a trava foi liberada e pode ser adquirida imediatamente sem erro
            with adquirir_trava_pipeline(lock_path) as f:
                self.assertIsNotNone(f)

    def test_concorrencia_multiprocesso_real_com_subprocess_bloqueia_segundo_processo(self):
        """Valida concorrência real entre processos SO independentes com subprocess.

        Garante:
        1. Confirmação explícita de aquisição da trava pelo primeiro processo antes da disputa.
        2. Execução de processo independente (Processo 2) bloqueado com encerramento silencioso (código 0).
        3. Encerramento ordenado do Processo 1 com liberação limpa da trava.
        4. Confirmação de que após a liberação da trava, um novo processo adquire a trava com sucesso.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            lock_path = tmp_path / "ultimo_envio.lock"
            status_path = tmp_path / "ultimo_envio.txt"

            proc1_code = (
                "import sys\n"
                "sys.path.insert(0, '.')\n"
                "from pathlib import Path\n"
                "from src.core.lock import adquirir_trava_pipeline\n"
                "p = Path(sys.argv[1])\n"
                "trava = adquirir_trava_pipeline(p)\n"
                "trava.__enter__()\n"
                "print('TRAVA_ADQUIRIDA', flush=True)\n"
                "sys.stdin.readline()\n"
                "trava.__exit__(None, None, None)\n"
                "print('TRAVA_LIBERADA', flush=True)\n"
            )

            proc1 = subprocess.Popen(
                [sys.executable, "-c", proc1_code, str(lock_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            try:
                # 1. Confirma que o primeiro processo adquiriu a trava antes de iniciar a disputa
                line1 = proc1.stdout.readline().strip()
                self.assertEqual(line1, "TRAVA_ADQUIRIDA")

                # 2. Executa Processo 2 como um processo SO independente disputando a trava
                proc2_code = (
                    "import sys\n"
                    "sys.path.insert(0, '.')\n"
                    "from pathlib import Path\n"
                    "from unittest.mock import patch\n"
                    "import main\n"
                    "main.STATUS_FILE = Path(sys.argv[1])\n"
                    "sys.argv = ['main.py', '--step', 'email', '--force']\n"
                    "with patch('main.despachar_relatorio', return_value=True):\n"
                    "    main.main()\n"
                )
                res2 = subprocess.run(
                    [sys.executable, "-c", proc2_code, str(status_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                # Código 0: encerramento silencioso e seguro para agendador
                self.assertEqual(res2.returncode, 0)
                output2 = res2.stdout + res2.stderr
                # Confirma que encerrou estritamente pela detecção de concorrência
                self.assertIn("Outro processo do pipeline", output2)
                # Confirma que não avançou para a execução do pipeline
                self.assertNotIn("INICIANDO PIPELINE DIÁRIO DE IA", output2)

                # 3. Libera ordenadamente a trava no Processo 1
                proc1.stdin.write("\n")
                proc1.stdin.flush()
                line_lib = proc1.stdout.readline().strip()
                self.assertEqual(line_lib, "TRAVA_LIBERADA")
                proc1.wait(timeout=5)

                # 4. Confirma o comportamento esperado quando a trava é liberada (aquisição bem-sucedida)
                proc3_code = (
                    "import sys\n"
                    "sys.path.insert(0, '.')\n"
                    "from pathlib import Path\n"
                    "from src.core.lock import adquirir_trava_pipeline\n"
                    "p = Path(sys.argv[1])\n"
                    "with adquirir_trava_pipeline(p):\n"
                    "    print('SUCESSO_TRAVA_LIVRE', flush=True)\n"
                )
                res3 = subprocess.run(
                    [sys.executable, "-c", proc3_code, str(lock_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                self.assertEqual(res3.returncode, 0)
                self.assertIn("SUCESSO_TRAVA_LIVRE", res3.stdout)

            finally:
                if proc1.poll() is None:
                    proc1.kill()
                    proc1.wait()

    @patch("main.reconciliar_historico_se_necessario")
    @patch("main.confirmar_banner_utilizado")
    @patch("main.despachar_relatorio", return_value=True)
    def test_main_executa_reconciliacao_quando_executando_envio(
        self,
        mock_despachar,
        mock_confirmar,
        mock_reconciliar
    ):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dummy_report = tmp_path / "Resumo_IA_2026-10-29.md"
            dummy_report.write_text("# Relatório Produção", encoding="utf-8")

            with patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"):
                test_args = ["main.py", "--step", "email", "--force"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                mock_reconciliar.assert_called_once()


    @patch("src.delivery.base.webbrowser.open")
    @patch("smtplib.SMTP_SSL")
    @patch("main.notificar_windows")
    @patch("main.registrar_envio_sucesso")
    def test_e2e_preview_com_banner_dinamico_e_link_hd(
        self,
        mock_registrar_sucesso,
        mock_notificar,
        mock_smtp_ssl,
        mock_browser
    ):
        """Valida E2E que python main.py --preview renderiza o banner dinâmico com link HD e title,
        sem acionar SMTP, sem criar histórico e sem alterar a trava diária."""
        import json
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            banners_dir = tmp_path / "banners"
            banners_dir.mkdir()
            (banners_dir / "halloween.jpg").write_bytes(b"arte_halloween")
            manifesto = {
                "legenda_padrao": "Legenda Padrão",
                "feriados": {
                    "10-31": {
                        "arquivo": "halloween.jpg",
                        "legenda": "Edição Especial de Halloween E2E"
                    }
                },
                "catalogo_geral": []
            }
            (banners_dir / "manifesto.json").write_text(json.dumps(manifesto), encoding="utf-8")

            preview_dest = tmp_path / "preview.html"
            dummy_report = tmp_path / "Resumo_IA_2026-10-31.md"
            dummy_report.write_text("# Relatório Halloween", encoding="utf-8")

            with patch("main.IngestionPipeline.run", return_value=self.sample_batch), \
                 patch("main.gerar_resumo_ia", return_value=dummy_report), \
                 patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("src.delivery.base.REPORTS_DIR", tmp_path), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"), \
                 patch("src.delivery.banner_selector.DATA_DIR", tmp_path), \
                 patch("src.delivery.banner_selector.BANNERS_DIR", banners_dir), \
                 patch("main.datetime") as mock_dt:

                mock_dt.now.return_value = datetime(2026, 10, 31, 10, 0)
                mock_dt.strftime = datetime.strftime

                test_args = ["main.py", "--preview"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                self.assertTrue(preview_dest.exists())
                html = preview_dest.read_text(encoding="utf-8")

                # Valida link HD apontando para a imagem do dia com rel noopener
                self.assertIn("halloween.jpg?v=20261021_v2", html)
                self.assertIn('rel="noopener noreferrer"', html)
                # Valida title dinâmico e alt com o tema
                self.assertIn('title="Edição Especial de Halloween E2E (Clique para abrir a imagem original em alta resolução)"', html)
                self.assertIn('alt="Arte da Edição: Edição Especial de Halloween E2E"', html)
                self.assertIn("Edição Especial de Halloween E2E", html)

                # Zero conexões SMTP, zero gravação de histórico, zero alteração na trava diária
                mock_smtp_ssl.assert_not_called()
                mock_registrar_sucesso.assert_not_called()
                self.assertFalse((tmp_path / "historico_banners.json").exists())
                self.assertFalse((tmp_path / "ultimo_envio.txt").exists())
                mock_browser.assert_called_once_with(preview_dest.resolve().as_uri())

    @patch("src.delivery.base.webbrowser.open")
    @patch("smtplib.SMTP_SSL")
    @patch("main.notificar_windows")
    @patch("main.registrar_envio_sucesso")
    def test_preview_isolamento_detectaria_regressao_sem_tocar_producao(
        self,
        mock_registrar_sucesso,
        mock_notificar,
        mock_smtp_ssl,
        mock_browser
    ):
        """Valida que o preview é estritamente isolado e que, se ocorresse uma regressão
        tentando persistir histórico, o teste detectaria a falha em tmp_path sem jamais
        tocar no diretório de dados real de produção."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            preview_dest = tmp_path / "preview.html"
            dummy_report = tmp_path / "Resumo_IA_2026-10-27.md"
            dummy_report.write_text("# Relatório Teste", encoding="utf-8")

            with patch("src.core.config.config.obter_ultimo_relatorio", return_value=dummy_report), \
                 patch("src.delivery.base.REPORTS_DIR", tmp_path), \
                 patch("main.STATUS_FILE", tmp_path / "ultimo_envio.txt"), \
                 patch("src.delivery.banner_selector.DATA_DIR", tmp_path):

                test_args = ["main.py", "--step", "email", "--preview"]
                with patch.object(sys, "argv", test_args):
                    main.main()

                # Em execução normal de preview: histórico NÃO existe em tmp_path nem em produção
                self.assertFalse((tmp_path / "historico_banners.json").exists())

                # Simula uma regressão: se confirmar_banner_utilizado fosse chamado,
                # ele gravaria no DATA_DIR injetado (tmp_path), provando que o patch é eficaz
                from src.delivery.banner_selector import confirmar_banner_utilizado
                confirmar_banner_utilizado(data_envio=datetime(2026, 10, 27))
                self.assertTrue(
                    (tmp_path / "historico_banners.json").exists(),
                    "Uma regressão que escreva no histórico DEVE ser capturada no tmp_path."
                )


if __name__ == "__main__":
    unittest.main()
