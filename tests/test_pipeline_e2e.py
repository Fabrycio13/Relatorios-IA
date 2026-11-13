import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.models import (
    Tweet,
    GitHubRepo,
    ResearchPaper,
    DailyIngestionBatch,
    SourceCollectionResult,
    SourceStatus,
)
from src.collectors.base import IngestionSource
from src.collectors.pipeline import IngestionPipeline
from src.processors.ai_summarizer import gerar_resumo_ia
import main


class TestPipelineE2EAndGovernance(unittest.TestCase):
    """Suíte abrangente de testes de integração, governança e CLI para o Ticket 22.

    Cobre os 24 cenários mandatórios divididos em 4 pilares:
    - Pipeline (1 a 9)
    - Snapshots e Fallback (10 a 15)
    - CLI e Códigos de Saída (16 a 19)
    - Síntese Editorial e Degradação Graciosa (20 a 24)
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp_dir.name)
        self.reports_dir = self.data_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.sleep_patcher = patch("time.sleep", return_value=None)
        self.sleep_patcher.start()

        self.sample_tweet = Tweet(
            author_name="Alice",
            author_handle="@alice",
            timestamp=datetime.now(timezone.utc).isoformat(),
            text="Novidade em agentes de IA",
            url="https://x.com/alice/status/1",
        )
        self.sample_repo = GitHubRepo(
            name="agent-framework",
            full_name="org/agent-framework",
            stars=1200,
            description="Framework para IA",
            language="Python",
            url="https://github.com/org/agent-framework",
        )
        self.sample_paper = ResearchPaper(
            title="Reasoning with Agents",
            arxiv_id="2601.12345",
            summary="Artigo sobre LLMs",
            authors=["Dr. Smith"],
            upvotes=42,
            url="https://arxiv.org/abs/2601.12345",
        )

    def tearDown(self):
        self.sleep_patcher.stop()
        self.tmp_dir.cleanup()

    # =========================================================================
    # Pilar 1: Pipeline (Cenários 1 a 9)
    # =========================================================================

    def _criar_mock_source(self, name: str, field_name: str, result: SourceCollectionResult) -> MagicMock:
        src = MagicMock(spec=IngestionSource)
        src.name = name
        src.target_field = field_name
        src.collect.return_value = result
        return src

    def test_01_pipeline_todas_fontes_success(self):
        """1. Todas as fontes SUCCESS persistem dados atômicos e atualizam manifesto com completed."""
        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.SUCCESS,
            items=(self.sample_tweet,),
            successful_operations=("feed",),
        )
        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )
        res_hf = SourceCollectionResult(
            source_name="papers",
            status=SourceStatus.SUCCESS,
            items=(self.sample_paper,),
            successful_operations=("daily_papers",),
        )

        sources = [
            self._criar_mock_source("twitter", "tweets", res_tw),
            self._criar_mock_source("github", "repos", res_gh),
            self._criar_mock_source("papers", "papers", res_hf),
        ]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        batch = pipeline.run()

        self.assertFalse(batch.is_empty())
        self.assertEqual(len(batch.tweets), 1)
        self.assertEqual(len(batch.repos), 1)
        self.assertEqual(len(batch.papers), 1)
        self.assertEqual(batch.results["twitter"].status, SourceStatus.SUCCESS)

        meta_path = self.data_dir / "snapshot_metadata.json"
        self.assertTrue(meta_path.exists())
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(meta["last_attempt"]["status"], "completed")
        self.assertEqual(meta["sources"]["twitter"]["status"], "success")
        self.assertEqual(meta["sources"]["github"]["status"], "success")
        self.assertEqual(meta["sources"]["papers"]["status"], "success")

    def test_02_pipeline_uma_fonte_failed_com_snapshot_anterior_valido(self):
        """2. Uma fonte FAILED com snapshot anterior preserva dados pré-existentes sem sobrescrita (DEF-01)."""
        batch_antigo = DailyIngestionBatch(tweets=[self.sample_tweet])
        batch_antigo.save_snapshot(self.data_dir)
        tweets_file = self.data_dir / "tweets_coletados.json"
        conteudo_antigo = tweets_file.read_text(encoding="utf-8")

        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.FAILED,
            items=(),
            failed_operations=("home",),
            error_message="Falha de rede ao acessar /home",
        )
        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )

        sources = [
            self._criar_mock_source("twitter", "tweets", res_tw),
            self._criar_mock_source("github", "repos", res_gh),
        ]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        batch = pipeline.run()

        # Arquivo antigo de tweets não pode ter sido sobrescrito com lista vazia []
        self.assertEqual(tweets_file.read_text(encoding="utf-8"), conteudo_antigo)
        # GitHub foi gravado normalmente
        self.assertTrue((self.data_dir / "github_trending.json").exists())
        self.assertEqual(batch.results["twitter"].status, SourceStatus.FAILED)

    def test_03_pipeline_uma_fonte_failed_sem_snapshot_anterior(self):
        """3. Uma fonte FAILED sem snapshot anterior registra falha sem inventar arquivos vazios nem hashes."""
        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.FAILED,
            items=(),
            failed_operations=("scrape",),
            error_message="Timeout no Playwright",
        )
        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )

        sources = [
            self._criar_mock_source("twitter", "tweets", res_tw),
            self._criar_mock_source("github", "repos", res_gh),
        ]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        batch = pipeline.run()

        self.assertFalse((self.data_dir / "tweets_coletados.json").exists())
        meta = json.loads((self.data_dir / "snapshot_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["sources"]["twitter"]["status"], "failed")
        self.assertIsNone(meta["sources"]["twitter"]["sha256"])

    def test_04_pipeline_partial_com_itens(self):
        """4. PARTIAL com itens persiste os dados válidos coletados e marca status partial."""
        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.PARTIAL,
            items=(self.sample_tweet,),
            successful_operations=("feed",),
            failed_operations=("profile:svpino",),
            error_message="Timeout no Radar VIP",
        )
        sources = [self._criar_mock_source("twitter", "tweets", res_tw)]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        batch = pipeline.run()

        self.assertEqual(len(batch.tweets), 1)
        meta = json.loads((self.data_dir / "snapshot_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["sources"]["twitter"]["status"], "partial")
        self.assertEqual(meta["sources"]["twitter"]["count"], 1)

    def test_05_pipeline_partial_sem_itens(self):
        """5. PARTIAL sem itens não sobrescreve snapshot pré-existente no disco."""
        batch_antigo = DailyIngestionBatch(tweets=[self.sample_tweet])
        batch_antigo.save_snapshot(self.data_dir)
        tweets_file = self.data_dir / "tweets_coletados.json"
        conteudo_antigo = tweets_file.read_text(encoding="utf-8")

        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.PARTIAL,
            items=(),
            successful_operations=("home",),
            failed_operations=("feed",),
            error_message="Nenhum tweet obtido antes da interrupção",
        )
        sources = [self._criar_mock_source("twitter", "tweets", res_tw)]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        pipeline.run()

        self.assertEqual(tweets_file.read_text(encoding="utf-8"), conteudo_antigo)

    def test_06_pipeline_empty_legitimo(self):
        """6. EMPTY legítimo persiste lista vazia [] e registra count=0 com status empty no manifesto."""
        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.EMPTY,
            items=(),
            successful_operations=("feed", "vip"),
        )
        sources = [self._criar_mock_source("twitter", "tweets", res_tw)]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        pipeline.run()

        tweets_file = self.data_dir / "tweets_coletados.json"
        self.assertTrue(tweets_file.exists())
        self.assertEqual(json.loads(tweets_file.read_text(encoding="utf-8")), [])

        meta = json.loads((self.data_dir / "snapshot_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["sources"]["twitter"]["status"], "empty")
        self.assertEqual(meta["sources"]["twitter"]["count"], 0)

    def test_07_pipeline_fonte_not_run(self):
        """7. Fonte NOT_RUN não é gravada no disco nem substitui metadados de fontes não executadas."""
        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )
        sources = [self._criar_mock_source("github", "repos", res_gh)]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        batch = pipeline.run()

        self.assertNotIn("twitter", batch.results)
        self.assertFalse((self.data_dir / "tweets_coletados.json").exists())

    def test_08_pipeline_coleta_isolada_sem_alterar_outras_fontes(self):
        """8. Coleta isolada (--step collect-github) altera exclusivamente a fonte alvo."""
        tweets_file = self.data_dir / "tweets_coletados.json"
        tweets_file.write_text(json.dumps([self.sample_tweet.to_dict()]), encoding="utf-8")

        meta_inicial = {
            "version": 2,
            "collected_at": "2026-11-12T07:00:00+00:00",
            "last_attempt": {"started_at": "2026-11-12T07:00:00+00:00", "status": "completed", "trigger": "sched", "pid": 1},
            "sources": {
                "twitter": {
                    "updated_at": "2026-11-12T07:00:00+00:00",
                    "sha256": "0" * 64,
                    "count": 1,
                    "status": "success",
                    "quality": "verified",
                }
            },
        }
        (self.data_dir / "snapshot_metadata.json").write_text(json.dumps(meta_inicial), encoding="utf-8")

        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )
        sources = [
            self._criar_mock_source("twitter", "tweets", MagicMock()),
            self._criar_mock_source("github", "repos", res_gh),
        ]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        pipeline.run(target_source="collect-github")

        meta_pos = json.loads((self.data_dir / "snapshot_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta_pos["sources"]["twitter"]["updated_at"], "2026-11-12T07:00:00+00:00")
        self.assertIn("github", meta_pos["sources"])

    def test_09_pipeline_falha_de_persistencia_propagada(self):
        """9. Falha de persistência atômica em disco propaga exceção sem declarar completed."""
        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )
        sources = [self._criar_mock_source("github", "repos", res_gh)]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        with patch("src.core.models._atomic_write_snapshot_json", side_effect=OSError("Disco cheio")):
            with self.assertRaises(OSError):
                pipeline.run()

    # =========================================================================
    # Pilar 2: Snapshots e Fallback (Cenários 10 a 15)
    # =========================================================================

    def test_10_snapshot_verified_e_fresco(self):
        """10. Snapshot verified e dentro da janela temporal de frescor é aceito diretamente."""
        batch = DailyIngestionBatch(
            tweets=[self.sample_tweet],
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
        batch.save_snapshot(self.data_dir)

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 1)
        self.assertEqual(loaded.tweets[0].author_handle, "@alice")
        self.assertEqual(loaded.sources_metadata.get("twitter", {}).get("quality"), "verified")

    def test_11_snapshot_verified_mas_stale(self):
        """11. Snapshot verified com mais de 36 horas é detectado como obsoleto (stale)."""
        ts_antigo = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        batch = DailyIngestionBatch(
            tweets=[self.sample_tweet],
            collected_at=ts_antigo,
        )
        batch.save_snapshot(self.data_dir)

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 1)

        from src.core.manifest import is_source_fresh
        tw_meta = loaded.sources_metadata.get("twitter", {})
        self.assertFalse(is_source_fresh(tw_meta.get("updated_at"), max_hours=36.0))

    def test_12_snapshot_legacy_unverified(self):
        """12. Snapshot com quality legacy_unverified é preservado e carregado como contingência."""
        # Cria arquivo v1 legado
        (self.data_dir / "tweets_coletados.json").write_text(json.dumps([self.sample_tweet.to_dict()]), encoding="utf-8")
        v1_meta = {
            "collected_at": "2026-11-10T08:00:00+00:00",
            "sources": {"twitter": "2026-11-10T08:00:00+00:00"},
        }
        (self.data_dir / "snapshot_metadata.json").write_text(json.dumps(v1_meta), encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 1)
        self.assertEqual(loaded.sources_metadata.get("twitter", {}).get("quality"), "legacy_unverified")

    def test_13_snapshot_recovered_apos_corrupcao_do_ativo(self):
        """13. Arquivo ativo corrompido recupera do .prev íntegro marcando qualidade correspondente."""
        # Grava snapshot A válido
        batch_a = DailyIngestionBatch(tweets=[self.sample_tweet], collected_at="2026-11-12T08:00:00+00:00")
        batch_a.save_snapshot(self.data_dir)

        # Grava snapshot B válido (movendo A para .prev)
        tweet_b = Tweet(author_name="B", author_handle="@b", timestamp="", text="B", url="")
        batch_b = DailyIngestionBatch(tweets=[tweet_b], collected_at="2026-11-12T09:00:00+00:00")
        batch_b.save_snapshot(self.data_dir)

        # Corrompe arquivo ativo de tweets
        (self.data_dir / "tweets_coletados.json").write_text("{corrompido", encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        # Recuperou A do .prev
        self.assertEqual(len(loaded.tweets), 1)
        self.assertEqual(loaded.tweets[0].author_handle, "@alice")

    def test_14_snapshot_com_hash_divergente_rejeitado(self):
        """14. Arquivo com hash SHA-256 divergente sem .prev válido é movido para quarentena e rejeitado."""
        (self.data_dir / "tweets_coletados.json").write_text('[{"text": "adulterado"}]', encoding="utf-8")
        meta = {
            "version": 2,
            "collected_at": "2026-11-12T08:00:00+00:00",
            "last_attempt": {"started_at": "2026-11-12T08:00:00+00:00", "status": "completed", "trigger": "t", "pid": 1},
            "sources": {
                "twitter": {
                    "updated_at": "2026-11-12T08:00:00+00:00",
                    "sha256": "f" * 64,  # hash incorreto
                    "count": 1,
                    "status": "success",
                    "quality": "verified",
                }
            },
        }
        (self.data_dir / "snapshot_metadata.json").write_text(json.dumps(meta), encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Dados com hash divergente não podem ser injetados no batch")
        quarantine_files = list((self.data_dir / "quarantine").glob("*corrupted*"))
        self.assertGreaterEqual(len(quarantine_files), 1)

    def test_15_manifesto_com_last_attempt_running_nao_permite_dirty_read(self):
        """15. Manifesto com status running impede dirty reads de dados transitórios."""
        (self.data_dir / "tweets_coletados.json").write_text('[{"text": "transitorio"}]', encoding="utf-8")
        meta_running = {
            "version": 2,
            "collected_at": "2026-11-12T08:00:00+00:00",
            "last_attempt": {"started_at": "2026-11-12T08:00:00+00:00", "status": "running", "trigger": "cli", "pid": 9999},
            "sources": {},
        }
        (self.data_dir / "snapshot_metadata.json").write_text(json.dumps(meta_running), encoding="utf-8")

        loaded = DailyIngestionBatch.load_snapshot(self.data_dir)
        self.assertEqual(len(loaded.tweets), 0, "Execução em andamento ('running') proíbe dirty reads")

    # =========================================================================
    # Pilar 3: CLI e Códigos de Saída (Cenários 16 a 19)
    # =========================================================================

    @patch("main.aguardar_conexao_internet", return_value=False)
    @patch("main.notificar_windows")
    def test_16_cli_exit_code_2_falha_de_rede_timeout(self, mock_notify, mock_net):
        """16. Falha de rede após timeout de 60s sai com sys.exit(2) (contrato com Task Scheduler)."""
        with patch("sys.argv", ["main.py", "--step", "collect"]):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 2)

    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.IngestionPipeline")
    def test_17_cli_distincao_entre_coleta_vazia_e_falha_de_coleta(self, mock_pipeline_cls, mock_net):
        """17. Falha de coleta em step exclusivo sai com código 1; coleta vazia legítima sai com 0."""
        # Cenário A: Falha na coleta da fonte exclusiva -> sys.exit(1)
        mock_pipe = MagicMock()
        mock_pipeline_cls.return_value = mock_pipe
        batch_failed = DailyIngestionBatch(
            tweets=[],
            results={"twitter": SourceCollectionResult(source_name="twitter", status=SourceStatus.FAILED, items=(), failed_operations=("scrape",), error_message="Rate limit")},
        )
        mock_pipe.run.return_value = batch_failed

        with patch("sys.argv", ["main.py", "--step", "collect-twitter"]):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)

        # Cenário B: Coleta executou com sucesso mas vazia legítima (EMPTY) -> encerra com sucesso (código 0 ou retorno limpo)
        batch_empty = DailyIngestionBatch(
            tweets=[],
            results={"twitter": SourceCollectionResult(source_name="twitter", status=SourceStatus.EMPTY, items=(), successful_operations=("feed",))},
        )
        mock_pipe.run.return_value = batch_empty

        with patch("sys.argv", ["main.py", "--step", "collect-twitter"]):
            try:
                main.main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)

    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.IngestionPipeline")
    @patch("main.gerar_resumo_ia")
    @patch("main.despachar_relatorio", return_value=True)
    def test_18_cli_suporte_a_todos_os_steps(self, mock_despachar, mock_resumo, mock_pipe_cls, mock_net):
        """18. CLI suporta todos os steps canônicos da Spec sem exceção não tratada."""
        mock_pipe = MagicMock()
        mock_pipe_cls.return_value = mock_pipe
        batch_ok = DailyIngestionBatch(
            repos=[self.sample_repo],
            results={"github": SourceCollectionResult(source_name="github", status=SourceStatus.SUCCESS, items=(self.sample_repo,), successful_operations=("search",))},
        )
        mock_pipe.run.return_value = batch_ok
        mock_resumo.return_value = self.reports_dir / "resumo.md"

        steps = ["collect-github", "collect-papers", "collect", "summarize", "all"]
        for step in steps:
            with patch("sys.argv", ["main.py", "--step", step, "--force", "--preview"]):
                try:
                    main.main()
                except SystemExit as e:
                    self.assertEqual(e.code, 0, f"Step '{step}' falhou com código de saída {e.code}")

    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.IngestionPipeline")
    def test_19_falha_de_coleta_nao_convertida_silenciosamente_em_sucesso(self, mock_pipe_cls, mock_net):
        """19. Falha de coleta não pode ser mascarada como sucesso."""
        mock_pipe = MagicMock()
        mock_pipe_cls.return_value = mock_pipe
        batch_fail = DailyIngestionBatch(
            tweets=[],
            results={"twitter": SourceCollectionResult(source_name="twitter", status=SourceStatus.FAILED, items=(), failed_operations=("scrape",), error_message="Crash")},
        )
        mock_pipe.run.return_value = batch_fail

        with patch("sys.argv", ["main.py", "--step", "collect-twitter"]):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)

    # =========================================================================
    # Pilar 4: Síntese Editorial e Degradação Graciosa (Cenários 20 a 24)
    # =========================================================================

    @patch("src.processors.ai_summarizer.chamar_openai", return_value="# Resumo do Dia\nConteúdo gerado.")
    @patch("src.processors.ai_summarizer.retry_with_backoff", side_effect=lambda fn, **kw: fn())
    def test_20_sintetizador_utiliza_somente_dados_autorizados(self, mock_retry, mock_openai):
        """20. O sintetizador utiliza apenas fontes com dados elegíveis e válidos no batch."""
        output_file = self.reports_dir / "relatorio.md"
        batch = DailyIngestionBatch(
            tweets=[self.sample_tweet],
            repos=[self.sample_repo],
            papers=[self.sample_paper],
            collected_at=datetime.now(timezone.utc).isoformat(),
            sources_metadata={
                "twitter": {"status": "success", "quality": "verified", "updated_at": datetime.now(timezone.utc).isoformat()},
                "github": {"status": "success", "quality": "verified", "updated_at": datetime.now(timezone.utc).isoformat()},
                "papers": {"status": "success", "quality": "verified", "updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )

        res = gerar_resumo_ia(batch=batch, output_path=output_file, data_dir=self.data_dir)
        self.assertIsNotNone(res)
        self.assertTrue(output_file.exists())

    @patch("src.processors.ai_summarizer.chamar_openai", return_value="# Resumo\nTexto.")
    @patch("src.processors.ai_summarizer.retry_with_backoff", side_effect=lambda fn, **kw: fn())
    def test_21_dados_legados_ou_recuperados_recebem_advertencia_editorial(self, mock_retry, mock_openai):
        """21. Dados legados (legacy_unverified) inserem advertência editorial de transparência."""
        output_file = self.reports_dir / "relatorio.md"
        batch = DailyIngestionBatch(
            tweets=[self.sample_tweet],
            repos=[self.sample_repo],
            collected_at=datetime.now(timezone.utc).isoformat(),
            sources_metadata={
                "twitter": {"status": "success", "quality": "legacy_unverified", "updated_at": datetime.now(timezone.utc).isoformat()},
                "github": {"status": "success", "quality": "verified", "updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )

        from src.processors.ai_summarizer import logger as summarizer_logger
        with self.assertLogs(summarizer_logger, level="WARNING") as cm:
            res = gerar_resumo_ia(batch=batch, output_path=output_file, data_dir=self.data_dir)
            self.assertIsNotNone(res)
            # Log explícito mandatório da Spec
            self.assertTrue(any("legacy_unverified" in log for log in cm.output))

        conteudo = output_file.read_text(encoding="utf-8")
        self.assertIn("Aviso Editorial", conteudo)
        self.assertIn("histórico coletado anteriormente", conteudo)

    @patch("src.processors.ai_summarizer.chamar_openai", return_value="# Resumo\nTexto.")
    @patch("src.processors.ai_summarizer.retry_with_backoff", side_effect=lambda fn, **kw: fn())
    def test_22_relatorio_sinaliza_degradacao_graciosa_quando_fonte_ausente_ou_stale(self, mock_retry, mock_openai):
        """22. Fonte stale ou vazia/failed não aborta relatório se houver dados úteis e insere aviso editorial."""
        output_file = self.reports_dir / "relatorio.md"
        ts_antigo = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
        batch = DailyIngestionBatch(
            tweets=[],  # Twitter falhou
            repos=[self.sample_repo],  # GitHub fresco
            collected_at=datetime.now(timezone.utc).isoformat(),
            sources_metadata={
                "twitter": {"status": "failed", "quality": "verified", "updated_at": ts_antigo},
                "github": {"status": "success", "quality": "verified", "updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )

        res = gerar_resumo_ia(batch=batch, output_path=output_file, data_dir=self.data_dir)
        self.assertIsNotNone(res)
        conteudo = output_file.read_text(encoding="utf-8")
        self.assertIn("não pôde ser atualizada", conteudo)

    def test_23_ausencia_total_de_dados_elegiveis_impede_geracao_enganosa(self):
        """23. Lote totalmente vazio ou sem dados elegíveis retorna None impedindo relatório falso."""
        output_file = self.reports_dir / "relatorio.md"
        empty_batch = DailyIngestionBatch(tweets=[], repos=[], papers=[])

        res = gerar_resumo_ia(batch=empty_batch, output_path=output_file, data_dir=self.data_dir)
        self.assertIsNone(res)
        self.assertFalse(output_file.exists())

    @patch("main.aguardar_conexao_internet", return_value=True)
    @patch("main.IngestionPipeline")
    @patch("main.gerar_resumo_ia", return_value=None)
    @patch("main.despachar_relatorio")
    def test_24_decisao_de_envio_subordinada_ao_sucesso_da_sintese(self, mock_despachar, mock_resumo, mock_pipe_cls, mock_net):
        """24. Se a síntese falhar (retornando None), o e-mail não é enviado e main sai com código 1."""
        mock_pipe = MagicMock()
        mock_pipe_cls.return_value = mock_pipe
        mock_pipe.run.return_value = DailyIngestionBatch()

        with patch("sys.argv", ["main.py", "--step", "all", "--force"]):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)
            mock_despachar.assert_not_called()

    @patch("src.processors.ai_summarizer._executar_chamada_openai", return_value="Síntese OpenAI mockada")
    @patch("src.processors.ai_summarizer.retry_with_backoff", side_effect=lambda fn, **kw: fn())
    def test_25_pipeline_fallback_chega_a_sintese_com_aviso_historico(self, mock_retry, mock_openai):
        """25. Fallback histórico elegível (<36h) após falha do Twitter chega à síntese com aviso editorial."""
        # 1. Snapshot anterior do Twitter, verified, com 15 tweets e idade de 8h (<36h)
        ts_anterior = (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()
        tweets_anteriores = [
            Tweet(
                author_name=f"Autor_{i}",
                author_handle=f"@autor_{i}",
                timestamp=ts_anterior,
                text=f"Tweet histórico relevante sobre IA número {i}",
                url=f"https://x.com/autor_{i}/status/{i}",
                likes=10 * i,
                reposts=i,
            )
            for i in range(1, 16)
        ]
        batch_antigo = DailyIngestionBatch(tweets=tweets_anteriores, collected_at=ts_anterior)
        batch_antigo.save_snapshot(self.data_dir)

        # 2. Na execução atual, Twitter retorna FAILED com items=()
        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.FAILED,
            items=(),
            failed_operations=("playwright_crash",),
            error_message="Timeout ao carregar feed do Twitter",
        )
        # 3. GitHub retorna SUCCESS com dados atuais
        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )
        sources = [
            self._criar_mock_source("twitter", "tweets", res_tw),
            self._criar_mock_source("github", "repos", res_gh),
        ]

        # 4. IngestionPipeline.run() preserva o arquivo anterior do Twitter e retorna o batch atual
        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        batch = pipeline.run()

        # O arquivo anterior de tweets foi preservado com 15 itens
        tweets_file = self.data_dir / "tweets_coletados.json"
        self.assertTrue(tweets_file.exists())
        self.assertEqual(len(json.loads(tweets_file.read_text(encoding="utf-8"))), 15)
        # O batch foi hidratado com os 15 tweets de fallback
        self.assertEqual(len(batch.tweets), 15)
        self.assertEqual(batch.results["twitter"].status, SourceStatus.FAILED)

        # 5. Passa exatamente esse batch retornado para gerar_resumo_ia(batch=batch)
        output_file = self.reports_dir / "relatorio.md"
        res_path = gerar_resumo_ia(batch=batch, output_path=output_file, data_dir=self.data_dir)
        self.assertIsNotNone(res_path)

        # 6. Verifique que a síntese recebe os dados anteriores do Twitter como fallback
        mock_openai.assert_called()
        first_call_payload = mock_openai.call_args_list[0][0][1]
        tweets_payload_xml = first_call_payload["messages"][1]["content"]
        self.assertIn('<tweet_item id="15"', tweets_payload_xml)
        self.assertIn("Tweet histórico relevante sobre IA número 15", tweets_payload_xml)

        # 7. Confirme que a saída identifica claramente que os tweets são históricos
        conteudo = output_file.read_text(encoding="utf-8")
        self.assertIn("Aviso Editorial", conteudo)
        self.assertIn("último estado histórico coletado anteriormente", conteudo)
        # E GitHub foi sintetizado normalmente
        self.assertIn("GitHub Trending", conteudo)

    def test_26_pipeline_falha_na_persistencia_aborta_sem_falso_sucesso(self):
        """26. Falha durante save_snapshot não comunica falso sucesso e registra failed no manifesto."""
        # Configura snapshot anterior recuperável
        batch_antigo = DailyIngestionBatch(tweets=[self.sample_tweet])
        batch_antigo.save_snapshot(self.data_dir)
        conteudo_antigo = (self.data_dir / "tweets_coletados.json").read_text(encoding="utf-8")

        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )
        pipeline = IngestionPipeline(
            sources=[self._criar_mock_source("github", "repos", res_gh)],
            data_dir=self.data_dir,
        )

        # Injeta erro na persistência
        with patch.object(DailyIngestionBatch, "save_snapshot", side_effect=IOError("Falha de I/O em disco")):
            with self.assertRaises(IOError):
                pipeline.run()

        # Manifesto não declarou completed e foi atualizado para failed
        meta_path = self.data_dir / "snapshot_metadata.json"
        self.assertTrue(meta_path.exists())
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(meta["last_attempt"]["status"], "failed")

        # Dados anteriores recuperáveis permanecem preservados
        self.assertEqual((self.data_dir / "tweets_coletados.json").read_text(encoding="utf-8"), conteudo_antigo)

        # CLI com essa falha sai com código 1 e não envia e-mail
        with patch("main.aguardar_conexao_internet", return_value=True), \
             patch("main.IngestionPipeline.run", side_effect=IOError("Falha de I/O")), \
             patch("main.despachar_relatorio") as mock_despachar, \
             patch("sys.argv", ["main.py", "--step", "all", "--force"]):
            with self.assertRaises(SystemExit) as cm:
                main.main()
            self.assertEqual(cm.exception.code, 1)
            mock_despachar.assert_not_called()

    @patch("src.processors.ai_summarizer._executar_chamada_openai", return_value="Síntese OpenAI mockada")
    @patch("src.processors.ai_summarizer.retry_with_backoff", side_effect=lambda fn, **kw: fn())
    def test_27_fallback_com_snapshot_stale_nao_sintetiza_tweets_como_atuais(self, mock_retry, mock_openai):
        """27. Snapshot anterior com idade > 36h é rejeitado por obsolescência e Twitter sofre degradação graciosa."""
        # 1. Snapshot anterior com 50 horas de idade (> 36h)
        ts_antigo = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
        batch_antigo = DailyIngestionBatch(tweets=[self.sample_tweet], collected_at=ts_antigo)
        batch_antigo.save_snapshot(self.data_dir)

        # Atualiza o timestamp no manifesto para 50h atrás explicitamente
        meta_file = self.data_dir / "snapshot_metadata.json"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        meta["sources"]["twitter"]["updated_at"] = ts_antigo
        meta_file.write_text(json.dumps(meta), encoding="utf-8")

        res_tw = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.FAILED,
            items=(),
            failed_operations=("scrape",),
            error_message="Falha de rede",
        )
        res_gh = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(self.sample_repo,),
            successful_operations=("search",),
        )
        sources = [
            self._criar_mock_source("twitter", "tweets", res_tw),
            self._criar_mock_source("github", "repos", res_gh),
        ]

        pipeline = IngestionPipeline(sources=sources, data_dir=self.data_dir)
        batch = pipeline.run()

        output_file = self.reports_dir / "relatorio.md"
        res_path = gerar_resumo_ia(batch=batch, output_path=output_file, data_dir=self.data_dir)
        self.assertIsNotNone(res_path)

        conteudo = output_file.read_text(encoding="utf-8")
        # Não apresentou tweets stale como se fossem atuais no texto
        self.assertIn("Aviso Editorial", conteudo)
        self.assertIn("não pôde ser atualizada", conteudo)
        self.assertIn("GitHub Trending", conteudo)


if __name__ == "__main__":
    unittest.main()
