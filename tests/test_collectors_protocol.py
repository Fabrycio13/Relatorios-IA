import unittest
from unittest.mock import patch, MagicMock

from src.core.models import Tweet, GitHubRepo, ResearchPaper, SourceCollectionResult, SourceStatus
from src.collectors.base import (
    IngestionSource,
    TwitterSource,
    GitHubSource,
    HuggingFaceSource
)


class TestCollectorsProtocol(unittest.TestCase):

    def test_sources_satisfy_protocol(self):
        twitter = TwitterSource()
        github = GitHubSource()
        hf = HuggingFaceSource()

        self.assertIsInstance(twitter, IngestionSource)
        self.assertIsInstance(github, IngestionSource)
        self.assertIsInstance(hf, IngestionSource)

        self.assertEqual(twitter.name, "twitter")
        self.assertEqual(github.name, "github")
        self.assertEqual(hf.name, "papers")

        self.assertEqual(twitter.target_field, "tweets")
        self.assertEqual(github.target_field, "repos")
        self.assertEqual(hf.target_field, "papers")

    @patch("src.collectors.base.coletar_tweets_vip")
    def test_twitter_source_collect_success(self, mock_coletar):
        dummy_tweet = Tweet(
            author_name="A", author_handle="@a", timestamp="", text="T", url=""
        )
        mock_coletar.return_value = SourceCollectionResult(
            source_name="twitter",
            status=SourceStatus.SUCCESS,
            items=(dummy_tweet,),
            successful_operations=("feed",),
            failed_operations=(),
        )

        source = TwitterSource(headless=True)
        result = source.collect()

        mock_coletar.assert_called_once_with(headless=True)
        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].author_handle, "@a")

    @patch("src.collectors.base.coletar_tweets_vip", side_effect=RuntimeError("Falha de scraping"))
    def test_twitter_source_collect_failure_is_graceful(self, mock_coletar):
        source = TwitterSource()
        result = source.collect()
        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.FAILED)
        self.assertEqual(result.items, ())
        self.assertIn("Falha de scraping", str(result.error_message))

    @patch("src.collectors.base.coletar_github_trending")
    def test_github_source_collect_success(self, mock_coletar):
        dummy_repo = GitHubRepo(
            name="r", full_name="org/r", stars=10, description="", language="Python", url=""
        )
        mock_coletar.return_value = SourceCollectionResult(
            source_name="github",
            status=SourceStatus.SUCCESS,
            items=(dummy_repo,),
            successful_operations=("feed",),
            failed_operations=(),
        )

        source = GitHubSource(dias_atras=7, limite_top=6)
        result = source.collect()

        mock_coletar.assert_called_once_with(dias_atras=7, limite_top=6)
        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].name, "r")

    @patch("src.collectors.base.coletar_github_trending", side_effect=Exception("API Rate Limit"))
    def test_github_source_collect_failure_is_graceful(self, mock_coletar):
        source = GitHubSource()
        result = source.collect()
        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.FAILED)
        self.assertEqual(result.items, ())
        self.assertIn("API Rate Limit", str(result.error_message))

    @patch("src.collectors.base.coletar_papers_huggingface")
    def test_huggingface_source_collect_success(self, mock_coletar):
        dummy_paper = ResearchPaper(
            title="P", arxiv_id="1", summary="", authors=["A"], upvotes=1, url=""
        )
        mock_coletar.return_value = SourceCollectionResult(
            source_name="papers",
            status=SourceStatus.SUCCESS,
            items=(dummy_paper,),
            successful_operations=("feed",),
            failed_operations=(),
        )

        source = HuggingFaceSource(limite_top=3)
        result = source.collect()

        mock_coletar.assert_called_once_with(limite_top=3)
        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.SUCCESS)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "P")

    @patch("src.collectors.base.coletar_papers_huggingface", side_effect=Exception("HF API Timeout"))
    def test_huggingface_source_collect_failure_is_graceful(self, mock_coletar):
        source = HuggingFaceSource()
        result = source.collect()
        self.assertIsInstance(result, SourceCollectionResult)
        self.assertEqual(result.status, SourceStatus.FAILED)
        self.assertEqual(result.items, ())
        self.assertIn("HF API Timeout", str(result.error_message))


if __name__ == "__main__":
    unittest.main()
