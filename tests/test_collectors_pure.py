import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.core.models import (
    Tweet,
    GitHubRepo,
    ResearchPaper,
    DailyIngestionBatch,
    SourceCollectionResult,
    SourceStatus,
)
from src.collectors.base import (
    IngestionSource,
    TwitterSource,
    GitHubSource,
    HuggingFaceSource,
)
from src.collectors.github import coletar_github_trending
from src.collectors.huggingface import coletar_papers_huggingface
from src.collectors.twitter import coletar_tweets_vip
from src.collectors.pipeline import IngestionPipeline


class TestCollectorsPure(unittest.TestCase):
    """Suíte de testes de pureza em memória e desacoplamento de I/O (Ticket 21)."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp_dir.name)
        self.sleep_patcher = patch("time.sleep", return_value=None)
        self.sleep_patcher.start()

    def tearDown(self):
        self.sleep_patcher.stop()
        self.tmp_dir.cleanup()

    # 1. GitHub: SUCCESS com itens válidos e ausência de escrita
    @patch("src.collectors.github._consultar_api_github")
    @patch("builtins.open")
    def test_github_collector_success_pure_memory(self, mock_open, mock_api):
        mock_api.return_value = {
            "items": [
                {
                    "name": "repo1",
                    "full_name": "org/repo1",
                    "stargazers_count": 100,
                    "description": "Repo de teste",
                    "language": "Python",
                    "html_url": "https://github.com/org/repo1",
                    "created_at": "2026-11-10T10:00:00Z",
                    "topics": ["llm", "ai"],
                }
            ]
        }

        result = coletar_github_trending(dias_atras=7, limite_top=6)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.source_name, "github")
        self.assertEqual(result.status, SourceStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        self.assertIsInstance(result.items[0], GitHubRepo)
        self.assertEqual(result.items[0].full_name, "org/repo1")
        self.assertEqual(len(result.successful_operations), 4)
        self.assertEqual(len(result.failed_operations), 0)
        self.assertIsNone(result.error_message)

        # Não pode ter aberto arquivo para escrita
        for call_item in mock_open.call_args_list:
            args, kwargs = call_item
            mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
            self.assertNotIn("w", mode, "Coletor não pode abrir arquivos com modo de escrita 'w'")

    # 2. GitHub: EMPTY legítimo sem falhas
    @patch("src.collectors.github._consultar_api_github")
    def test_github_collector_empty_legitimate(self, mock_api):
        mock_api.return_value = {"items": []}

        result = coletar_github_trending(dias_atras=7, limite_top=6)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.EMPTY)
        self.assertEqual(len(result.items), 0)
        self.assertEqual(len(result.successful_operations), 4)
        self.assertEqual(len(result.failed_operations), 0)
        self.assertIsNone(result.error_message)

    # 3. GitHub: PARTIAL com itens e suboperações com falha
    @patch("src.collectors.github._consultar_api_github")
    def test_github_collector_partial_with_items(self, mock_api):
        call_count = 0

        def side_effect(url: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "items": [
                        {
                            "name": "repo_partial",
                            "full_name": "org/repo_partial",
                            "stargazers_count": 50,
                            "description": "desc",
                            "language": "Python",
                            "html_url": "https://github.com/org/repo_partial",
                            "created_at": "2026-11-10T10:00:00Z",
                            "topics": ["llm"],
                        }
                    ]
                }
            raise RuntimeError("GitHub API 503 Service Unavailable")

        mock_api.side_effect = side_effect

        result = coletar_github_trending(dias_atras=7, limite_top=6)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.PARTIAL)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(len(result.successful_operations), 1)
        self.assertEqual(len(result.failed_operations), 3)
        self.assertIn("503", str(result.error_message))

    # 4. GitHub: PARTIAL sem itens, preservando operações bem-sucedidas e falhas
    @patch("src.collectors.github._consultar_api_github")
    def test_github_collector_partial_without_items(self, mock_api):
        call_count = 0

        def side_effect(url: str):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {"items": []}
            raise RuntimeError("Rate limit excedido (429)")

        mock_api.side_effect = side_effect

        result = coletar_github_trending(dias_atras=7, limite_top=6)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.PARTIAL)
        self.assertEqual(len(result.items), 0)
        self.assertEqual(len(result.successful_operations), 2)
        self.assertEqual(len(result.failed_operations), 2)
        self.assertIsNotNone(result.error_message)

    # 5. GitHub: FAILED quando nenhuma operação for bem-sucedida
    @patch("src.collectors.github._consultar_api_github", side_effect=RuntimeError("Falha total DNS"))
    def test_github_collector_failed_total(self, mock_api):
        result = coletar_github_trending(dias_atras=7, limite_top=6)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.FAILED)
        self.assertEqual(len(result.items), 0)
        self.assertEqual(len(result.successful_operations), 0)
        self.assertEqual(len(result.failed_operations), 4)
        self.assertIn("Falha total DNS", str(result.error_message))

    # 6. Hugging Face: SUCCESS com itens válidos e ausência de escrita
    @patch("src.collectors.huggingface._consultar_api_daily_papers")
    @patch("builtins.open")
    def test_huggingface_collector_success_pure_memory(self, mock_open, mock_api):
        mock_api.return_value = [
            {
                "paper": {
                    "id": "2401.00001",
                    "title": "A Great AI Paper",
                    "summary": "Resumo do paper",
                    "authors": [{"name": "Pesquisador A"}],
                },
                "numComments": 10,
                "mediaCount": 5,
            }
        ]

        result = coletar_papers_huggingface(limite_top=3)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.source_name, "papers")
        self.assertEqual(result.status, SourceStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        self.assertIsInstance(result.items[0], ResearchPaper)
        self.assertEqual(result.items[0].arxiv_id, "2401.00001")
        self.assertEqual(len(result.successful_operations), 1)
        self.assertEqual(len(result.failed_operations), 0)

        # Não pode ter aberto arquivo para escrita
        for call_item in mock_open.call_args_list:
            args, kwargs = call_item
            mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
            self.assertNotIn("w", mode)

    # 7. Hugging Face: EMPTY legítimo
    @patch("src.collectors.huggingface._consultar_api_daily_papers", return_value=[])
    def test_huggingface_collector_empty(self, mock_api):
        result = coletar_papers_huggingface(limite_top=3)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.EMPTY)
        self.assertEqual(len(result.items), 0)
        self.assertEqual(len(result.successful_operations), 1)
        self.assertEqual(len(result.failed_operations), 0)

    # 8. Hugging Face: FAILED com detalhes de erro
    @patch("src.collectors.huggingface._consultar_api_daily_papers", side_effect=TimeoutError("Timeout na API HF"))
    def test_huggingface_collector_failed(self, mock_api):
        result = coletar_papers_huggingface(limite_top=3)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.FAILED)
        self.assertEqual(len(result.items), 0)
        self.assertEqual(len(result.successful_operations), 0)
        self.assertEqual(len(result.failed_operations), 1)
        self.assertIn("Timeout na API HF", str(result.error_message))

    # 9. Twitter: FAILED quando não autenticado
    @patch("src.collectors.twitter.sync_playwright")
    def test_twitter_collector_unauthenticated_failed(self, mock_playwright):
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = MagicMock()
        mock_p.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_page.url = "https://x.com/login"

        result = coletar_tweets_vip(headless=True)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.source_name, "twitter")
        self.assertEqual(result.status, SourceStatus.FAILED)
        self.assertEqual(len(result.items), 0)
        self.assertIn("autenticada", str(result.error_message).lower())

    # 10. Twitter: SUCCESS com itens e zero escritas em disco
    @patch("src.collectors.twitter.sync_playwright")
    @patch("src.collectors.twitter.coletar_feed_principal")
    @patch("builtins.open")
    def test_twitter_collector_success_pure_memory(self, mock_open, mock_feed, mock_playwright):
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = MagicMock()
        mock_p.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_page.url = "https://x.com/home"

        sample_tweet = Tweet(
            author_name="Alice",
            author_handle="@alice",
            timestamp="2026-11-12T10:00:00Z",
            text="AI updates",
            url="https://x.com/alice/status/123",
        )
        mock_feed.return_value = ([sample_tweet], {sample_tweet.text})

        # Artigos VIP retornam vazio para simplificar
        mock_page.locator.return_value.all.return_value = []

        result = coletar_tweets_vip(headless=True)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].author_handle, "@alice")

        # Não pode ter aberto arquivo para escrita
        for call_item in mock_open.call_args_list:
            args, kwargs = call_item
            mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
            self.assertNotIn("w", mode)

    # 11. Zero aquisições de snapshot.lock durante a execução dos coletores
    @patch("src.core.lock.adquirir_trava_snapshot")
    @patch("src.collectors.github._consultar_api_github", return_value={"items": []})
    def test_zero_locks_during_scraping(self, mock_api, mock_lock):
        coletar_github_trending()
        mock_lock.assert_not_called()

    # 12. Imutabilidade profunda das entidades retornadas
    @patch("src.collectors.github._consultar_api_github")
    def test_immutability_of_returned_entities(self, mock_api):
        mock_api.return_value = {
            "items": [
                {
                    "name": "r1",
                    "full_name": "org/r1",
                    "stargazers_count": 10,
                    "description": "d",
                    "language": "Python",
                    "html_url": "https://github.com/org/r1",
                    "created_at": "2026-11-10T10:00:00Z",
                    "topics": ["llm"],
                }
            ]
        }
        result = coletar_github_trending()
        self.assertIsInstance(result.items, tuple)
        repo = result.items[0]
        with self.assertRaises((TypeError, AttributeError)):
            repo.stars = 999  # type: ignore

    # 13. Adaptadores em src/collectors/base.py propagam SourceCollectionResult
    @patch("src.collectors.base.coletar_github_trending")
    def test_github_source_adapter_returns_source_collection_result(self, mock_coletar):
        mock_coletar.return_value = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(
                GitHubRepo(name="r", full_name="org/r", stars=1, description="", language="", url=""),
            ),
            successful_operations=("query1",),
            failed_operations=(),
        )
        source = GitHubSource()
        res = source.collect()
        self.assertIsInstance(res, SourceCollectionResult)
        self.assertEqual(res.status, SourceStatus.SUCCESS)

    # 14. Adaptadores não convertem exceções para [] silenciosamente
    @patch("src.collectors.base.coletar_github_trending", side_effect=RuntimeError("Falha na API GitHub"))
    def test_github_source_adapter_handles_exception_without_silent_empty_list(self, mock_coletar):
        source = GitHubSource()
        res = source.collect()
        self.assertIsInstance(res, SourceCollectionResult)
        self.assertEqual(res.status, SourceStatus.FAILED)
        self.assertEqual(len(res.items), 0)
        self.assertIn("Falha na API GitHub", str(res.error_message))

    @patch("src.collectors.base.coletar_papers_huggingface", side_effect=TimeoutError("Timeout HF"))
    def test_huggingface_source_adapter_handles_exception_without_silent_empty_list(self, mock_coletar):
        source = HuggingFaceSource()
        res = source.collect()
        self.assertIsInstance(res, SourceCollectionResult)
        self.assertEqual(res.status, SourceStatus.FAILED)
        self.assertEqual(len(res.items), 0)
        self.assertIn("Timeout HF", str(res.error_message))

    @patch("src.collectors.base.coletar_tweets_vip", side_effect=RuntimeError("Playwright Crash"))
    def test_twitter_source_adapter_handles_exception_without_silent_empty_list(self, mock_coletar):
        source = TwitterSource()
        res = source.collect()
        self.assertIsInstance(res, SourceCollectionResult)
        self.assertEqual(res.status, SourceStatus.FAILED)
        self.assertEqual(len(res.items), 0)
        self.assertIn("Playwright Crash", str(res.error_message))

    # 15. Compatibilidade do pipeline: não sobrescreve snapshot anterior após FAILED
    def test_pipeline_failed_source_preserves_existing_snapshot(self):
        """Ao falhar uma fonte no pipeline, o snapshot existente em disco é preservado integralmente (DEF-01)."""
        tweets_file = self.data_dir / "tweets_coletados.json"
        existing_tweets = [{"author_name": "Antigo", "author_handle": "@antigo", "timestamp": "2026-11-10T00:00:00Z", "text": "Preservado", "url": ""}]
        tweets_file.write_text(json.dumps(existing_tweets), encoding="utf-8")

        failing_twitter = MagicMock(spec=IngestionSource)
        failing_twitter.name = "twitter"
        failing_twitter.target_field = "tweets"
        failing_twitter.collect.return_value = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.FAILED,
            items=(),
            successful_operations=(),
            failed_operations=("network_fail",),
            error_message="Falha de conexão com o Twitter",
        )

        pipeline = IngestionPipeline(sources=[failing_twitter], data_dir=self.data_dir)
        batch = pipeline.run("twitter")

        # Em disco, o arquivo tweets_coletados.json não pode ter sido destruído ou esvaziado
        self.assertTrue(tweets_file.exists())
        content = json.loads(tweets_file.read_text(encoding="utf-8"))
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["text"], "Preservado")

    # 16. Cenário 1: Adaptadores nativos rejeitam retornos que não sejam SourceCollectionResult
    @patch("src.collectors.base.coletar_github_trending")
    def test_github_source_rejects_none_and_invalid_types_as_failed(self, mock_coletar):
        """None, dict ou str retornados pelo coletor produzem FAILED com diagnóstico, nunca EMPTY."""
        source = GitHubSource()

        for invalid_val in (None, {"items": []}, "string_invalida", [1, 2, 3]):
            mock_coletar.return_value = invalid_val
            res = source.collect()
            self.assertIsInstance(res, SourceCollectionResult)
            self.assertEqual(res.status, SourceStatus.FAILED, f"Valor {type(invalid_val)} não pode gerar EMPTY ou SUCCESS")
            self.assertEqual(len(res.items), 0)
            self.assertIsNotNone(res.error_message)
            self.assertIn("SourceCollectionResult", str(res.error_message))

    @patch("src.collectors.base.coletar_papers_huggingface")
    def test_huggingface_source_rejects_none_and_invalid_types_as_failed(self, mock_coletar):
        source = HuggingFaceSource()

        for invalid_val in (None, {}, "erro"):
            mock_coletar.return_value = invalid_val
            res = source.collect()
            self.assertIsInstance(res, SourceCollectionResult)
            self.assertEqual(res.status, SourceStatus.FAILED)
            self.assertEqual(len(res.items), 0)
            self.assertIsNotNone(res.error_message)

    @patch("src.collectors.base.coletar_tweets_vip")
    def test_twitter_source_rejects_none_and_invalid_types_as_failed(self, mock_coletar):
        source = TwitterSource()

        for invalid_val in (None, {"tweets": []}, "invalid"):
            mock_coletar.return_value = invalid_val
            res = source.collect()
            self.assertIsInstance(res, SourceCollectionResult)
            self.assertEqual(res.status, SourceStatus.FAILED)
            self.assertEqual(len(res.items), 0)
            self.assertIsNotNone(res.error_message)

    # 17. Cenário 1: Fallback do pipeline aceita apenas list explícita; None/dict viram FAILED sem sobrescrever disco
    def test_pipeline_fallback_rejects_none_and_unexpected_types_as_failed(self):
        """Pipeline converte retorno None ou tipo inesperado em FAILED e não sobrescreve disco."""
        tweets_file = self.data_dir / "tweets_coletados.json"
        existing = [{"author_name": "A", "author_handle": "@a", "timestamp": "", "text": "Intacto", "url": ""}]
        tweets_file.write_text(json.dumps(existing), encoding="utf-8")

        for bad_return in (None, {"items": []}, "texto", 123):
            bad_source = MagicMock(spec=IngestionSource)
            bad_source.name = "twitter"
            bad_source.target_field = "tweets"
            bad_source.collect.return_value = bad_return

            pipeline = IngestionPipeline(sources=[bad_source], data_dir=self.data_dir)
            batch = pipeline.run("twitter")

            # Em memória, batch.tweets não deve ter sido corrompido
            self.assertEqual(batch.tweets, [])
            # Em disco, tweets_coletados.json deve permanecer com o dado pré-existente
            self.assertEqual(tweets_file.read_text(encoding="utf-8"), json.dumps(existing))

    def test_pipeline_rejects_plain_list_without_source_collection_result(self):
        """Pipeline rejeita lista plana sem SourceCollectionResult marcando FAILED."""
        sample_tweet = Tweet(author_name="A", author_handle="@a", timestamp="", text="T", url="")
        legacy_source = MagicMock(spec=IngestionSource)
        legacy_source.name = "twitter"
        legacy_source.target_field = "tweets"
        legacy_source.collect.return_value = [sample_tweet]

        pipeline = IngestionPipeline(sources=[legacy_source], data_dir=self.data_dir)
        batch = pipeline.run("twitter")
        self.assertEqual(batch.results["twitter"].status, SourceStatus.FAILED)
        self.assertEqual(len(batch.tweets), 0)

    # 18. Cenário 2: Pipeline com subconjunto de fontes preserva fontes não executadas e metadados
    def test_pipeline_subset_sources_preserves_unexecuted_sources_and_metadata(self):
        """Snapshot com Twitter, GitHub e Papers. Executar pipeline apenas com GitHub preserva Twitter e Papers."""
        # 1. Cria snapshots existentes para todas as 3 fontes
        tweets_file = self.data_dir / "tweets_coletados.json"
        github_file = self.data_dir / "github_trending.json"
        papers_file = self.data_dir / "hf_papers.json"
        meta_file = self.data_dir / "snapshot_metadata.json"

        dados_tweets = [{"author_name": "T", "author_handle": "@t", "timestamp": "2026-11-12T07:00:00Z", "text": "Preservar T", "url": ""}]
        dados_github_antigo = [{"name": "old_repo", "full_name": "org/old_repo", "stars": 5, "description": "", "language": "Python", "url": ""}]
        dados_papers = [{"title": "P", "arxiv_id": "1", "summary": "", "authors": ["A"], "upvotes": 1, "url": ""}]

        tweets_file.write_text(json.dumps(dados_tweets), encoding="utf-8")
        github_file.write_text(json.dumps(dados_github_antigo), encoding="utf-8")
        papers_file.write_text(json.dumps(dados_papers), encoding="utf-8")

        import hashlib
        def _h(content_str: str) -> str:
            return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

        meta_inicial = {
            "version": 2,
            "collected_at": "2026-11-12T08:00:00.000000+00:00",
            "last_attempt": {
                "started_at": "2026-11-12T08:00:00.000000+00:00",
                "completed_at": "2026-11-12T08:01:00.000000+00:00",
                "status": "completed",
                "trigger": "scheduled",
                "pid": 1234,
            },
            "sources": {
                "twitter": {
                    "updated_at": "2026-11-12T08:00:00.000000+00:00",
                    "sha256": _h(json.dumps(dados_tweets)),
                    "count": 1,
                    "status": "success",
                    "quality": "verified",
                },
                "github": {
                    "updated_at": "2026-11-12T08:00:00.000000+00:00",
                    "sha256": _h(json.dumps(dados_github_antigo)),
                    "count": 1,
                    "status": "success",
                    "quality": "verified",
                },
                "papers": {
                    "updated_at": "2026-11-12T08:00:00.000000+00:00",
                    "sha256": _h(json.dumps(dados_papers)),
                    "count": 1,
                    "status": "success",
                    "quality": "verified",
                },
            },
        }
        meta_file.write_text(json.dumps(meta_inicial), encoding="utf-8")

        # 2. Instancia pipeline contendo APENAS GitHubSource
        novo_repo = GitHubRepo(
            name="new_repo",
            full_name="org/new_repo",
            stars=100,
            description="Novo",
            language="Python",
            url="http://gh",
        )
        mock_gh = MagicMock(spec=IngestionSource)
        mock_gh.name = "github"
        mock_gh.target_field = "repos"
        mock_gh.collect.return_value = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(novo_repo,),
            successful_operations=("search",),
            failed_operations=(),
        )

        pipeline = IngestionPipeline(sources=[mock_gh], data_dir=self.data_dir)
        # Executa run() SEM target_source
        batch = pipeline.run()

        # 3. Verificações:
        # GitHub foi atualizado em disco
        conteudo_gh = json.loads(github_file.read_text(encoding="utf-8"))
        self.assertEqual(len(conteudo_gh), 1)
        self.assertEqual(conteudo_gh[0]["name"], "new_repo")

        # Twitter e Papers permaneceram intactos em disco
        self.assertEqual(tweets_file.read_text(encoding="utf-8"), json.dumps(dados_tweets))
        self.assertEqual(papers_file.read_text(encoding="utf-8"), json.dumps(dados_papers))

        # Metadados de Twitter e Papers foram preservados intactos no manifesto
        meta_atual = json.loads(meta_file.read_text(encoding="utf-8"))
        self.assertEqual(meta_atual["sources"]["twitter"], meta_inicial["sources"]["twitter"])
        self.assertEqual(meta_atual["sources"]["papers"], meta_inicial["sources"]["papers"])
        # GitHub foi atualizado nos metadados
        self.assertEqual(meta_atual["sources"]["github"]["count"], 1)
        self.assertNotEqual(meta_atual["sources"]["github"]["sha256"], meta_inicial["sources"]["github"]["sha256"])

    # 19. Cenário 2: target_source solicitado sem coletor correspondente não grava lista vazia nem forja EMPTY
    def test_pipeline_target_source_without_registered_collector_does_not_forge_empty(self):
        """Solicitar target_source que não possui coletor registrado não grava [] nem forja EMPTY."""
        tweets_file = self.data_dir / "tweets_coletados.json"
        dados_tweets = [{"author_name": "T", "author_handle": "@t", "timestamp": "", "text": "Preservado", "url": ""}]
        tweets_file.write_text(json.dumps(dados_tweets), encoding="utf-8")

        mock_gh = MagicMock(spec=IngestionSource)
        mock_gh.name = "github"
        mock_gh.target_field = "repos"
        mock_gh.collect.return_value = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(
                GitHubRepo(
                    name="repo", full_name="org/repo", stars=1, description="", language="", url=""
                ),
            ),
            successful_operations=("search",),
            failed_operations=(),
        )

        # Pipeline possui apenas GitHub
        pipeline = IngestionPipeline(sources=[mock_gh], data_dir=self.data_dir)
        batch = pipeline.run(target_source="collect-twitter")

        # tweets_coletados.json NÃO pode ter sido sobrescrito com []
        self.assertEqual(tweets_file.read_text(encoding="utf-8"), json.dumps(dados_tweets))

    # 20. Cenário 3: Falha no page.goto da página inicial do Twitter gera FAILED com failed_operations ("home",)
    @patch("src.collectors.twitter.sync_playwright")
    def test_twitter_collector_page_goto_home_failure(self, mock_playwright):
        """Falha no page.goto('https://x.com/home') registra 'home' em failed_operations e não declara EMPTY."""
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = MagicMock()
        mock_p.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]

        # Simula erro de navegação
        mock_page.goto.side_effect = TimeoutError("Timeout 45000ms exceeded ao acessar /home")

        result = coletar_tweets_vip(headless=True)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.source_name, "twitter")
        self.assertEqual(result.status, SourceStatus.FAILED, "Falha na página inicial deve resultar em FAILED, nunca EMPTY")
        self.assertEqual(len(result.items), 0)
        self.assertIn("home", result.failed_operations)
        self.assertIsNotNone(result.error_message)
        self.assertIn("45000ms", str(result.error_message))

    # 21. Cenário 3: Timeout global durante Radar VIP registra perfis restantes em failed_operations
    @patch("src.collectors.twitter.sync_playwright")
    @patch("src.collectors.twitter.coletar_feed_principal")
    @patch("src.collectors.twitter.time.time")
    def test_twitter_collector_global_timeout_during_vip(self, mock_time, mock_feed, mock_playwright):
        """Timeout global durante o Radar VIP não declara EMPTY legítimo e registra operações não executadas."""
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = MagicMock()
        mock_p.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_page.url = "https://x.com/home"

        # Feed termina com 0 itens
        mock_feed.return_value = ([], set())

        # Simula evolução do tempo via callback para não colidir com chamadas internas do logger
        simulated_time = 0.0
        mock_time.side_effect = lambda: simulated_time

        def feed_sim(*args, **kwargs):
            nonlocal simulated_time
            simulated_time = 305.0  # Ao encerrar feed, tempo já atingiu 305s (> 300s)
            return ([], set())

        mock_feed.side_effect = feed_sim

        result = coletar_tweets_vip(headless=True)

        self.assertIsInstance(result, SourceCollectionResult)
        # Como o feed obteve 0 itens e o Radar VIP sofreu timeout global, não pode ser EMPTY legítimo
        self.assertNotEqual(result.status, SourceStatus.EMPTY, "Timeout durante coleta não pode resultar em EMPTY legítimo")
        # Todos os perfis VIP não visitados devem constar em failed_operations
        self.assertTrue(any(op.startswith("profile:") for op in result.failed_operations))
        self.assertIsNotNone(result.error_message)

    # 22. Cenário 3: Coleta parcialmente completada antes do timeout preserva itens e retorna PARTIAL
    @patch("src.collectors.twitter.sync_playwright")
    @patch("src.collectors.twitter.coletar_feed_principal")
    @patch("src.collectors.twitter.time.time")
    def test_twitter_collector_partial_completed_before_timeout(self, mock_time, mock_feed, mock_playwright):
        """Coleta com tweets obtidos no feed que sofre timeout no Radar VIP preserva itens e marca PARTIAL."""
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = MagicMock()
        mock_p.chromium.launch_persistent_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.pages = [mock_page]
        mock_page.url = "https://x.com/home"

        feed_tweet = Tweet(
            author_name="Alice",
            author_handle="@alice",
            timestamp="2026-11-12T10:00:00Z",
            text="Tweet do feed",
            url="http://x/1",
        )
        mock_feed.return_value = ([feed_tweet], {feed_tweet.text})

        simulated_time = 0.0
        mock_time.side_effect = lambda: simulated_time

        goto_calls = 0
        def on_goto(url, **kwargs):
            nonlocal goto_calls, simulated_time
            goto_calls += 1
            if goto_calls == 1:
                simulated_time = 5.0
            elif goto_calls == 2:
                # 1º perfil (mattpocockuk) é acessado com tempo válido, mas ao concluir atinge timeout
                simulated_time = 305.0

        mock_page.goto.side_effect = on_goto

        # Simula 0 novos tweets do perfil (mantendo o do feed)
        mock_page.locator.return_value.all.return_value = []

        result = coletar_tweets_vip(headless=True)

        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.PARTIAL)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].text, "Tweet do feed")
        self.assertIn("feed", result.successful_operations)
        # svpino e seguintes devem estar em failed_operations
        self.assertIn("profile:svpino", result.failed_operations)
        self.assertIsNotNone(result.error_message)


if __name__ == "__main__":
    unittest.main()
