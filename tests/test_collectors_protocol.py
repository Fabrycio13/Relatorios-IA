import unittest
from unittest.mock import patch, MagicMock

from src.core.models import Tweet, GitHubRepo, ResearchPaper
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
        mock_coletar.return_value = [dummy_tweet]

        source = TwitterSource(headless=True)
        items = source.collect()

        mock_coletar.assert_called_once_with(headless=True)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].author_handle, "@a")

    @patch("src.collectors.base.coletar_tweets_vip", side_effect=RuntimeError("Falha de scraping"))
    def test_twitter_source_collect_failure_is_graceful(self, mock_coletar):
        source = TwitterSource()
        items = source.collect()
        self.assertEqual(items, [])

    @patch("src.collectors.base.coletar_github_trending")
    def test_github_source_collect_success(self, mock_coletar):
        dummy_repo = GitHubRepo(
            name="r", full_name="org/r", stars=10, description="", language="Python", url=""
        )
        mock_coletar.return_value = [dummy_repo]

        source = GitHubSource(dias_atras=7, limite_top=6)
        items = source.collect()

        mock_coletar.assert_called_once_with(dias_atras=7, limite_top=6)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "r")

    @patch("src.collectors.base.coletar_github_trending", side_effect=Exception("API Rate Limit"))
    def test_github_source_collect_failure_is_graceful(self, mock_coletar):
        source = GitHubSource()
        items = source.collect()
        self.assertEqual(items, [])

    @patch("src.collectors.base.coletar_papers_huggingface")
    def test_huggingface_source_collect_success(self, mock_coletar):
        dummy_paper = ResearchPaper(
            title="P", arxiv_id="1", summary="", authors=["A"], upvotes=1, url=""
        )
        mock_coletar.return_value = [dummy_paper]

        source = HuggingFaceSource(limite_top=3)
        items = source.collect()

        mock_coletar.assert_called_once_with(limite_top=3)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "P")

    @patch("src.collectors.base.coletar_papers_huggingface", side_effect=Exception("HF API Timeout"))
    def test_huggingface_source_collect_failure_is_graceful(self, mock_coletar):
        source = HuggingFaceSource()
        items = source.collect()
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
