import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.models import Tweet, GitHubRepo, ResearchPaper, DailyIngestionBatch
from src.collectors.base import IngestionSource
from src.collectors.pipeline import IngestionPipeline


class DummySource:
    def __init__(self, name: str, items: list, target_field: str | None = None):
        self.name = name
        self.items = items
        self.target_field = target_field or ("tweets" if name == "twitter" else ("repos" if name == "github" else "papers"))
        self.called = False

    def collect(self):
        self.called = True
        return self.items


class FailingSource:
    def __init__(self, name: str, target_field: str | None = None):
        self.name = name
        self.target_field = target_field or ("tweets" if name == "twitter" else ("repos" if name == "github" else "papers"))

    def collect(self):
        raise RuntimeError(f"Falha intencional na fonte {self.name}")


class TestIngestionPipeline(unittest.TestCase):

    def setUp(self):
        self.tweet = Tweet(
            author_name="A", author_handle="@a", timestamp="", text="T", url=""
        )
        self.repo = GitHubRepo(
            name="r", full_name="org/r", stars=10, description="", language="Python", url=""
        )
        self.paper = ResearchPaper(
            title="P", arxiv_id="1", summary="", authors=["A"], upvotes=1, url=""
        )

    def test_pipeline_default_sources(self):
        pipeline = IngestionPipeline()
        self.assertEqual(len(pipeline.sources), 3)
        names = [s.name for s in pipeline.sources]
        self.assertEqual(names, ["twitter", "github", "papers"])

    def test_pipeline_run_all_sources(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_twitter = DummySource("twitter", [self.tweet])
            source_github = DummySource("github", [self.repo])
            source_papers = DummySource("papers", [self.paper])

            pipeline = IngestionPipeline(
                sources=[source_twitter, source_github, source_papers],
                data_dir=tmp_path
            )

            batch = pipeline.run()

            self.assertTrue(source_twitter.called)
            self.assertTrue(source_github.called)
            self.assertTrue(source_papers.called)

            self.assertFalse(batch.is_empty())
            self.assertEqual(len(batch.tweets), 1)
            self.assertEqual(len(batch.repos), 1)
            self.assertEqual(len(batch.papers), 1)

            # Garante que o snapshot foi salvo em disco
            self.assertTrue((tmp_path / "tweets_coletados.json").exists())
            self.assertTrue((tmp_path / "github_trending.json").exists())
            self.assertTrue((tmp_path / "hf_papers.json").exists())

    def test_pipeline_run_single_source(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_twitter = DummySource("twitter", [self.tweet])
            source_github = DummySource("github", [self.repo])
            source_papers = DummySource("papers", [self.paper])

            pipeline = IngestionPipeline(
                sources=[source_twitter, source_github, source_papers],
                data_dir=tmp_path
            )

            # Executa apenas github
            batch = pipeline.run("github")

            self.assertFalse(source_twitter.called)
            self.assertTrue(source_github.called)
            self.assertFalse(source_papers.called)

            self.assertEqual(len(batch.repos), 1)

    def test_pipeline_resilience_to_exception(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            failing_twitter = FailingSource("twitter")
            source_github = DummySource("github", [self.repo])
            source_papers = DummySource("papers", [self.paper])

            pipeline = IngestionPipeline(
                sources=[failing_twitter, source_github, source_papers],
                data_dir=tmp_path
            )

            # Executa com twitter falhando
            batch = pipeline.run()

            self.assertEqual(batch.tweets, [])
            self.assertEqual(len(batch.repos), 1)
            self.assertEqual(len(batch.papers), 1)
            self.assertFalse(batch.is_empty())

    def test_pipeline_run_single_source_isolates_data_and_preserves_other_files(self):
        """
        Valida que executar uma única fonte (ex: github) não sobrescreve nem altera
        arquivos de outras fontes pré-existentes em data/, garantindo isolamento temporal.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # 1. Simula coleta completa de ontem
            old_tweets_file = tmp_path / "tweets_coletados.json"
            old_tweets_file.write_text('[{"author_name": "Old", "author_handle": "@old", "timestamp": "2026-10-26T12:00:00Z", "text": "Old tweet", "url": ""}]', encoding="utf-8")
            old_content = old_tweets_file.read_text(encoding="utf-8")

            source_twitter = DummySource("twitter", [self.tweet])
            source_github = DummySource("github", [self.repo])
            source_papers = DummySource("papers", [self.paper])

            pipeline = IngestionPipeline(
                sources=[source_twitter, source_github, source_papers],
                data_dir=tmp_path
            )

            # 2. Executa apenas a fonte github
            batch = pipeline.run("github")

            # 3. Garante que o lote retornado contém APENAS os dados do github (sem mesclagem de ontem)
            self.assertEqual(batch.tweets, [], "O lote não deve conter tweets antigos de dias anteriores.")
            self.assertEqual(len(batch.repos), 1)
            self.assertEqual(batch.papers, [])

            # 4. Garante que tweets_coletados.json permaneceu intocado em disco
            self.assertEqual(old_tweets_file.read_text(encoding="utf-8"), old_content)
            # 5. Garante que github_trending.json foi salvo
            self.assertTrue((tmp_path / "github_trending.json").exists())

    def test_pipeline_invalid_target_field_is_safely_ignored(self):
        """Valida que fontes com target_field fora dos campos permitidos são ignoradas com warning."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rogue_source = DummySource("rogue", [{"hack": True}], target_field="unauthorized_attr")

            pipeline = IngestionPipeline(
                sources=[rogue_source],
                data_dir=tmp_path
            )

            batch = pipeline.run()
            self.assertFalse(hasattr(batch, "unauthorized_attr"))
            self.assertTrue(batch.is_empty())


if __name__ == "__main__":
    unittest.main()
